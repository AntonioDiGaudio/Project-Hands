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
    """
    Mano sintetica con misure controllate.

    I numeri qui sotto sono arbitrari di proposito, e vanno letti come tali. Le
    soglie di estensione delle dita non hanno una scala assoluta prevedibile:
    dipendono dalle proporzioni della mano vera. Questi test verificano che
    `compute` ricavi le soglie NELLA POSIZIONE GIUSTA rispetto alle pose
    misurate, non che una certa mano dia un certo numero. E' la distinzione che
    prima mancava: i valori di riferimento erano scritti nei commenti e mai
    verificati, e le soglie di fabbrica ci si appoggiavano.
    """

    def __init__(self, extension, pinch, middle=1.2, middle_extension=0.30):
        self.index_extension = extension
        self.middle_extension = middle_extension
        self._pinch = pinch
        self._middle = middle

    def ratio(self, a, b):
        from hand_tracker import MIDDLE_TIP
        return self._middle if b == MIDDLE_TIP else self._pinch


# Valori plausibili per le quattro pose.
#
# Il terzo numero (pollice-medio) e' quello che la versione precedente
# raccoglieva e poi buttava via, copiando le soglie del pinch indice su quello
# medio. Le due geometrie non coincidono: qui pointing ha 0.95 e middle_pinch
# 0.20, mentre sull'indice gli stessi due valori sono 1.30 e 0.24.
POSE_HANDS = {
    #                    indice  poll-ind  poll-medio  medio teso
    "pointing":     FakeHand(1.42, 1.30, 0.95, 0.30),
    "pinching":     FakeHand(1.06, 0.24, 0.80, 0.32),
    "middle_pinch": FakeHand(1.35, 0.85, 0.20, 0.90),
    "fist":         FakeHand(0.52, 0.34, 0.30, 0.22),
    "open":         FakeHand(1.45, 1.35, 1.40, 0.95),
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
        "pointing": FakeHand(1.42, 1.30, 0.95, 0.30),
        "pinching": FakeHand(0.60, 0.24, 0.80, 0.32),
        "middle_pinch": FakeHand(1.35, 0.85, 0.20, 0.90),
        "fist": FakeHand(0.62, 0.34, 0.30, 0.22),
        "open": FakeHand(1.45, 1.35, 1.40, 0.95),
    }[key])
    check("segnala la sovrapposizione", "_overlap" in cal.result,
          "risultato: %r" % cal.result)
    check("non propone una soglia di controllo sbagliata",
          "index_control_ratio" not in cal.result)


def test_middle_control_ratio_is_calibrated():
    """
    Regressione: `middle_control_ratio` non veniva calibrato affatto.

    Il parametro esisteva ed era usato dal riconoscitore per decidere se il
    pinch pollice+medio conta come click destro, ma `compute` non lo produceva
    mai: restava al valore di fabbrica. Se quel valore e' piu' alto di quanto
    misura la mano vera, il click destro viene ignorato in silenzio — nessun
    errore, nessun evento, niente.
    """
    cal = Calibration()
    cal.start(1000.0)
    drive(cal)
    r = cal.result
    check("calcola middle_control_ratio", "middle_control_ratio" in r,
          "risultato: %r" % r)
    if "middle_control_ratio" not in r:
        return
    ctrl = r["middle_control_ratio"]
    check("il medio pinzato supera la soglia",
          POSE_HANDS["middle_pinch"].middle_extension > ctrl,
          "medio pinzato %.2f contro soglia %.2f"
          % (POSE_HANDS["middle_pinch"].middle_extension, ctrl))
    check("il pugno resta sotto la soglia",
          POSE_HANDS["fist"].middle_extension < ctrl,
          "pugno %.2f contro soglia %.2f"
          % (POSE_HANDS["fist"].middle_extension, ctrl))


def test_thresholds_survive_an_unusual_hand_scale():
    """
    Una mano le cui estensioni stanno su una scala diversa deve calibrarsi
    lo stesso.

    E' il caso che ha rotto tutto in pratica. I limiti di plausibilita' erano
    stati scritti copiando i valori di riferimento dei commenti ("indice teso
    ~1.3-1.5"); una mano reale ne ha misurati circa un quarto e la calibrazione
    si e' vista rifiutare valori corretti, restando su un default che blocca
    ogni gesture. La soglia non ha una scala assoluta: conta solo che stia fra
    pugno e pinch.
    """
    small = {
        "pointing":     FakeHand(0.88, 1.30, 0.95, 0.30),
        "pinching":     FakeHand(0.42, 0.24, 0.80, 0.32),
        "middle_pinch": FakeHand(0.85, 0.85, 0.20, 0.55),
        "fist":         FakeHand(0.25, 0.34, 0.30, 0.18),
        "open":         FakeHand(0.92, 1.35, 1.40, 0.62),
    }
    cal = Calibration()
    cal.start(1000.0)
    drive(cal, hand_for=lambda key: small[key])
    r = cal.result

    check("la soglia viene comunque prodotta", "index_control_ratio" in r,
          "risultato: %r (scartati: %r)" % (r, r.get("_rifiutati")))
    check("nessun valore corretto viene rifiutato", "_rifiutati" not in r,
          "scartati: %r" % r.get("_rifiutati"))
    if "index_control_ratio" in r:
        ctrl = r["index_control_ratio"]
        check("sta fra pugno e pinch",
              small["fist"].index_extension < ctrl < small["pinching"].index_extension,
              "pugno %.2f, soglia %.2f, pinch %.2f"
              % (small["fist"].index_extension, ctrl,
                 small["pinching"].index_extension))


def test_curled_middle_is_reported_not_silently_accepted():
    """
    Regressione dal caso reale.

    L'utente ha eseguito "pollice + medio" ripiegando il medio nel palmo e
    toccandolo col pollice, invece di distenderlo verso il pollice. Misurato:
    medio a 0.47 nella posa del click destro contro 0.46 puntando, cioe'
    identici. Le due pose sono la stessa cosa e nessuna soglia le separa.

    La calibrazione deve accorgersene e dirlo, non produrre un numero che
    farebbe cliccare a destra ogni volta che punti.
    """
    curled = {
        "pointing":     FakeHand(1.42, 1.30, 0.95, 0.46),
        "pinching":     FakeHand(1.06, 0.24, 0.80, 0.84),
        "middle_pinch": FakeHand(1.35, 0.85, 0.20, 0.47),   # medio ripiegato
        "fist":         FakeHand(0.52, 0.34, 0.30, 0.32),
        "open":         FakeHand(1.45, 1.35, 1.40, 0.94),
    }
    cal = Calibration()
    cal.start(1000.0)
    drive(cal, hand_for=lambda key: curled[key])
    r = cal.result

    check("segnala che il medio era ripiegato", "_middle_curled" in r,
          "risultato: %r" % r)
    ctrl = r.get("middle_control_ratio")
    check("propone comunque una soglia sicura", ctrl is not None, "%r" % r)
    if ctrl is not None:
        check("la soglia esclude la posa di puntamento",
              curled["pointing"].middle_extension < ctrl,
              "puntamento %.2f contro soglia %.2f"
              % (curled["pointing"].middle_extension, ctrl))
        check("e lascia passare un medio davvero disteso",
              curled["pinching"].middle_extension > ctrl,
              "medio disteso %.2f contro soglia %.2f"
              % (curled["pinching"].middle_extension, ctrl))


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
          cal.state == DONE and total >= MIN_SAMPLES * len(SEQUENCE),
          "%d campioni totali, stato %r" % (total, cal.state))


def test_right_pinch_has_its_own_thresholds():
    """
    Regressione: le soglie del click destro venivano COPIATE da quelle
    dell'indice. Le due distanze non hanno niente a che vedere fra loro, e con
    la soglia dell'indice il pinch destro risulta chiuso gia' nella posa di
    puntamento: primo movimento della mano, click destro non richiesto.
    """
    cal = Calibration()
    cal.start(1000.0)
    drive(cal)
    r = cal.result
    for key in ("right_pinch_close_ratio", "right_pinch_open_ratio"):
        check("calcola %s" % key, key in r, "risultato: %r" % r)
    if "right_pinch_close_ratio" not in r:
        return

    check("non e' una copia delle soglie dell'indice",
          r["right_pinch_close_ratio"] != r["pinch_close_ratio"],
          "entrambe %.2f" % r["right_pinch_close_ratio"])
    check("le soglie destre sono in ordine",
          r["right_pinch_close_ratio"] < r["right_pinch_open_ratio"], "%r" % r)
    check("la posa di puntamento resta sopra la chiusura del pinch destro",
          POSE_HANDS["pointing"]._middle > r["right_pinch_open_ratio"],
          "puntamento %.2f contro apertura %.2f"
          % (POSE_HANDS["pointing"]._middle, r["right_pinch_open_ratio"]))
    check("il pinch medio sta sotto la chiusura",
          POSE_HANDS["middle_pinch"]._middle < r["right_pinch_close_ratio"],
          "pinch medio %.2f contro chiusura %.2f"
          % (POSE_HANDS["middle_pinch"]._middle, r["right_pinch_close_ratio"]))


def test_transition_frames_are_discarded():
    """
    Regressione sul profilo reale che ha rotto il click sinistro.

    La registrazione partiva subito dopo il conto alla rovescia, quindi i primi
    fotogrammi erano la mano ancora in viaggio verso la posa. Con il 95o
    percentile, quei fotogrammi finivano dritti nella soglia: il profilo salvato
    aveva pinch_close_ratio = 0.82, cioe' il valore di una mano aperta.
    """
    import calibrate as cal_mod

    def moving(key):
        # Per i primi istanti di ogni posa mostra ancora la mano aperta.
        return POSE_HANDS[key]

    cal = Calibration()
    cal.start(1000.0)
    now = 1000.0
    dt = 1 / 30.0
    while cal.state not in (DONE, IDLE):
        now += dt
        pose = cal.pose
        key = pose[0] if pose else None
        hand = POSE_HANDS[key] if key else None
        # Durante l'assestamento la mano e' ancora quella aperta della posa
        # precedente: il caso reale.
        if (cal.state == CAPTURING
                and now - cal.phase_start < cal_mod.SETTLE):
            hand = POSE_HANDS["pointing"]
        cal.tick(hand, now)

    r = cal.result
    check("i fotogrammi di transizione non inquinano la soglia",
          r.get("pinch_close_ratio", 9.9) < 0.60,
          "pinch_close_ratio = %r" % r.get("pinch_close_ratio"))
    check("nessun valore implausibile viene proposto",
          "_rifiutati" not in r, "scartati: %r" % r.get("_rifiutati"))


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
