"""
Test della procedura di calibrazione, senza webcam ne' finestra.

La prima versione della calibrazione non funzionava perche' richiedeva di
tenere premuto un tasto mentre `cv2.waitKey` faceva polling, e non c'era nessun
test che percorresse il flusso: la logica di calcolo era giusta, ma la
procedura non arrivava mai a raccogliere un campione. Questi test percorrono la
macchina a stati dall'inizio alla fine.

    python test_calibrate.py
"""

import sys

import calibrate
from calibrate import (
    Calibration, Samples, compute, SEQUENCE, COUNTDOWN, CAPTURE, MIN_SAMPLES,
    IDLE, COUNTING, CAPTURING, DONE,
)

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print("  ok    %s" % name)
    else:
        print("  FALLITO  %s  %s" % (name, detail))
        FAILURES.append(name)


class FakeHand:
    """Mano sintetica con misure controllate."""

    def __init__(self, extension, pinch, middle=1.2):
        self.index_extension = extension
        self._pinch = pinch
        self._middle = middle

    def ratio(self, a, b):
        from hand_tracker import MIDDLE_TIP
        return self._middle if b == MIDDLE_TIP else self._pinch


# Valori plausibili per le tre pose.
POSE_HANDS = {
    "pointing": FakeHand(1.42, 1.30),
    "pinching": FakeHand(1.06, 0.24),
    "fist": FakeHand(0.52, 0.34),
}


def drive(cal, fps=30.0, hand_for=None, drop_frames=0, limit=4000):
    """
    Fa girare la procedura come farebbe il loop reale.

    `hand_for(pose_key)` decide quale mano mostrare; `drop_frames` simula
    fotogrammi senza mano durante la registrazione.
    """
    hand_for = hand_for or (lambda key: POSE_HANDS[key])
    now = 1000.0
    dt = 1.0 / fps
    dropped = 0
    frames = 0

    while cal.state not in (DONE, IDLE) and frames < limit:
        frames += 1
        now += dt
        pose = cal.pose
        hand = hand_for(pose[0]) if pose else None
        if dropped < drop_frames and cal.state == CAPTURING:
            hand = None
            dropped += 1
        cal.tick(hand, now)
    return frames, now


def test_full_run_collects_all_poses():
    cal = Calibration()
    check("parte in stato idle", cal.state == IDLE)
    cal.start(1000.0)
    check("SPAZIO avvia il conto alla rovescia", cal.state == COUNTING)

    frames, _ = drive(cal)
    check("la procedura arriva a termine da sola", cal.state == DONE,
          "stato %r dopo %d fotogrammi" % (cal.state, frames))

    for key, title, _ in SEQUENCE:
        n = len(cal.samples.get(key, ()))
        check("posa %-9s raccoglie campioni sufficienti" % key,
              n >= MIN_SAMPLES, "solo %d campioni" % n)


def test_thresholds_are_produced_and_ordered():
    cal = Calibration()
    cal.start(1000.0)
    drive(cal)
    result = {k: v for k, v in cal.result.items() if not k.startswith("_")}

    check("produce le soglie", bool(result), "risultato: %r" % cal.result)
    for key in ("index_control_ratio", "pinch_close_ratio", "pinch_open_ratio",
                "pinch_freeze_ratio"):
        check("calcola %s" % key, key in result, "mancante")

    if result:
        ordered = (result["pinch_close_ratio"] < result["pinch_open_ratio"]
                   < result["pinch_freeze_ratio"])
        check("soglie del pinch in ordine", ordered, "%r" % result)

        # La soglia di controllo deve lasciar passare il pinch e fermare il pugno.
        ctrl = result["index_control_ratio"]
        check("il pinch supera la soglia di controllo",
              POSE_HANDS["pinching"].index_extension > ctrl,
              "pinch %.2f contro soglia %.2f"
              % (POSE_HANDS["pinching"].index_extension, ctrl))
        check("il pugno resta sotto la soglia di controllo",
              POSE_HANDS["fist"].index_extension < ctrl,
              "pugno %.2f contro soglia %.2f"
              % (POSE_HANDS["fist"].index_extension, ctrl))

        # Il cursore deve restare libero a mano aperta.
        check("il cursore resta libero a mano aperta",
              POSE_HANDS["pointing"]._pinch > result["pinch_freeze_ratio"],
              "aperta %.2f contro blocco %.2f"
              % (POSE_HANDS["pointing"]._pinch, result["pinch_freeze_ratio"]))


def test_missing_hand_pauses_capture():
    """Senza mano il tempo non deve scorrere, altrimenti la posa esce vuota."""
    cal = Calibration()
    cal.start(1000.0)
    frames, _ = drive(cal, drop_frames=40)
    check("i fotogrammi senza mano non consumano la registrazione",
          cal.state == DONE and all(
              len(cal.samples.get(k, ())) >= MIN_SAMPLES for k, _, _ in SEQUENCE),
          "campioni: %r" % {k: len(v) for k, v in cal.samples.items()})


def test_low_framerate_still_collects_enough():
    """Su hardware lento (10 fps) la finestra di cattura deve bastare comunque."""
    cal = Calibration()
    cal.start(1000.0)
    drive(cal, fps=10.0)
    counts = {k: len(cal.samples.get(k, ())) for k, _, _ in SEQUENCE}
    check("a 10 fps raccoglie ancora abbastanza campioni",
          all(n >= MIN_SAMPLES for n in counts.values()), "campioni: %r" % counts)


def test_overlapping_poses_are_rejected():
    """Pose indistinguibili non devono produrre soglie inservibili."""
    cal = Calibration()
    cal.start(1000.0)
    # Pugno e pinch con la stessa estensione: non separabili.
    drive(cal, hand_for=lambda key: {
        "pointing": FakeHand(1.42, 1.30),
        "pinching": FakeHand(0.60, 0.24),
        "fist": FakeHand(0.62, 0.34),
    }[key])
    check("segnala la sovrapposizione", "_overlap" in cal.result,
          "risultato: %r" % cal.result)
    check("non propone una soglia di controllo sbagliata",
          "index_control_ratio" not in cal.result)


def test_cancel_resets():
    cal = Calibration()
    cal.start(1000.0)
    drive(cal)
    cal.cancel()
    check("R riporta allo stato iniziale",
          cal.state == IDLE and cal.step == 0)


def test_recording_does_not_depend_on_key_repeat():
    """
    Regressione sul bug originale.

    Un solo `start()` deve bastare a raccogliere tutte e tre le pose: nessuna
    ulteriore pressione di tasti durante la procedura.
    """
    cal = Calibration()
    cal.start(1000.0)
    drive(cal)   # nessun altro input
    total = sum(len(s) for s in cal.samples.values())
    check("una sola pressione basta per l'intera procedura",
          cal.state == DONE and total >= MIN_SAMPLES * 3,
          "%d campioni totali, stato %r" % (total, cal.state))


def main():
    print("Test della procedura di calibrazione\n")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        print(test.__name__)
        test()
        print()

    if FAILURES:
        print("%d test falliti: %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("Tutti i %d gruppi di test sono passati." % len(tests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
