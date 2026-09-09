"""
Test della macchina a stati sulle misure di UNA MANO VERA.

Gli altri test usano una mano sintetica: verificano la logica, ma i numeri che
le danno in pasto sono inventati. E' il motivo per cui passavano al 100% mentre
in mano all'utente non partiva un click. I valori di riferimento scritti nei
commenti del progetto ("indice teso ~1.3-1.5") non erano mai stati verificati:
la misura reale dice 0.79-0.95, cioe' un fattore 1.6 di distanza, e le soglie
di fabbrica erano tarate su quei commenti.

Qui le pose sono le misure registrate da `diagnose.py` su una mano vera
(5o percentile / mediana / 95o percentile per ogni grandezza). Se una soglia
non funziona su questa mano, questi test lo dicono.

    python test_mano_reale.py
"""

import sys

import config
from gesture_recognizer import (
    GestureRecognizer, LEFT_CLICK, RIGHT_CLICK, DRAG_START, DRAG_END,
)
from hand_tracker import HandObservation

SCALE = 0.15

# Misure reali, da diagnosi.txt. Per ogni posa:
#   (indice teso, medio teso, pollice-indice, pollice-medio, dita)
# I valori sono le mediane; gli estremi sono nel report.
POSE = {
    "puntamento":   (0.93, 0.46, 1.19, 0.22, (1, 0, 0, 0)),
    "pinch_indice": (0.46, 0.84, 0.14, 0.98, (0, 1, 1, 1)),
    "pinch_medio":  (0.73, 0.47, 0.74, 0.12, (1, 0, 1, 1)),
    "pugno":        (0.27, 0.32, 0.20, 0.28, (0, 0, 0, 0)),
    "aperta":       (0.79, 0.94, 0.96, 1.29, (1, 1, 1, 1)),
}

# Come sopra, ma con il medio davvero disteso: e' il click destro fatto come
# dice la guida. Il medio teso viene dalla posa "pollice + indice uniti", dove
# la stessa mano lo tiene effettivamente esteso (0.84).
# Il click destro nuovo: pollice + indice + medio tutti insieme. Entrambe le
# punte toccano il pollice, quindi tutte e due le distanze scendono al valore
# che l'indice ha nel pinch semplice (0.14 misurato).
POSE["tre_dita"] = (0.46, 0.47, 0.14, 0.16, (0, 0, 1, 1))

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print("  ok    %s" % name)
    else:
        print("  FALLITO  %s  %s" % (name, detail))
        FAILURES.append(name)


def hand(pose, reacquired=False, wrist=(0.5, 0.8)):
    """HandObservation che riproduce esattamente le distanze misurate."""
    idx_ext, mid_ext, thumb_index, thumb_middle, fingers = POSE[pose]
    pts = [(0.0, 0.0)] * 21
    wx, wy = wrist
    pts[0] = (wx, wy)
    pts[9] = (wx, wy - SCALE)                 # nocca del medio -> scale
    pts[4] = (wx - 0.05, wy - SCALE * 0.8)    # pollice
    tx, ty = pts[4]
    pts[8] = (tx + thumb_index * SCALE, ty)   # punta indice
    pts[12] = (tx + thumb_middle * SCALE, ty)  # punta medio
    pts[5] = (wx + 0.02, wy - SCALE * 0.9)    # nocca indice
    return HandObservation("Right", 0.98, pts, SCALE, fingers, reacquired,
                           idx_ext, mid_ext)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def advance(self, dt=1 / 30.0):
        self.t += dt
        return self.t


def feed(r, clock, pose, frames=1, cursor=(960, 540)):
    events = []
    for _ in range(frames):
        h = hand(pose)
        now = clock.advance()
        r.prepare(h, now)
        events.extend(name for name, _ in r.update(h, cursor, now))
    return events


def settled():
    """Riconoscitore gia' agganciato, con la mano in posa di puntamento."""
    r = GestureRecognizer(config)
    clock = Clock()
    feed(r, clock, "puntamento", frames=20)
    return r, clock


# ---------------------------------------------------------------------------
def test_pointing_pose_is_not_gated():
    """
    Il gate della posa di controllo non deve scattare su una mano normale.

    Con index_control_ratio = 0.75 (il vecchio default) la mano vera misura
    0.93 puntando ma 0.46 pinzando: il gate scattava proprio durante il click.
    """
    r, clock = settled()
    feed(r, clock, "puntamento", frames=10)
    check("puntando, nessun blocco", r.gated_reason == "",
          "blocco: %r (indice %.2f, soglia %.2f)"
          % (r.gated_reason, r.index_extension, config.index_control_ratio))


def test_pinching_pose_is_not_gated():
    r, clock = settled()
    feed(r, clock, "pinch_indice", frames=4)
    check("pinzando, nessun blocco", r.gated_reason == "",
          "blocco: %r (indice %.2f, soglia %.2f)"
          % (r.gated_reason, r.index_extension, config.index_control_ratio))


def test_fist_is_still_gated():
    """La soglia deve continuare a fermare il pugno, o torna il falso positivo."""
    r, clock = settled()
    feed(r, clock, "pugno", frames=10)
    check("il pugno resta bloccato", r.gated_reason != "",
          "nessun blocco (indice %.2f, soglia %.2f)"
          % (r.index_extension, config.index_control_ratio))


def test_left_click_fires():
    r, clock = settled()
    feed(r, clock, "puntamento", frames=5)
    feed(r, clock, "pinch_indice", frames=6)      # ~0.2 s
    events = feed(r, clock, "puntamento", frames=8)
    check("il click sinistro parte", events.count(LEFT_CLICK) == 1,
          "eventi: %r" % events)


def test_drag_fires_and_releases():
    r, clock = settled()
    feed(r, clock, "puntamento", frames=5)
    events = feed(r, clock, "pinch_indice", frames=30)   # 1 s tenuto
    check("il drag parte", DRAG_START in events, "eventi: %r" % events)
    check("il drag non produce anche un click", LEFT_CLICK not in events,
          "eventi: %r" % events)
    events = feed(r, clock, "puntamento", frames=8)
    check("il drag si chiude riaprendo", DRAG_END in events, "eventi: %r" % events)


def test_pointing_does_not_fire_right_click():
    """
    Su questa mano il pollice sta appoggiato sul medio ripiegato gia' mentre
    punta: pollice-medio vale 0.22, sotto la soglia di chiusura. E' il caso che
    prima produceva un click destro non richiesto.
    """
    r, clock = settled()
    feed(r, clock, "puntamento", frames=60)
    events = feed(r, clock, "aperta", frames=20)
    check("puntando e poi aprendo non parte un click destro",
          RIGHT_CLICK not in events, "eventi: %r" % events)


def test_three_finger_pinch_right_clicks():
    """Il click destro nuovo: pollice + indice + medio insieme."""
    r, clock = settled()
    feed(r, clock, "puntamento", frames=5)
    feed(r, clock, "tre_dita", frames=6)
    events = feed(r, clock, "puntamento", frames=8)
    check("il pinch a tre dita produce un click destro",
          events.count(RIGHT_CLICK) == 1, "eventi: %r" % events)


def test_three_finger_pinch_does_not_also_left_click():
    """
    Chiudendo tre dita l'indice tocca il pollice per primo, quindi il
    rilevatore sinistro si chiude comunque. Non deve uscirne anche un click
    sinistro.
    """
    r, clock = settled()
    feed(r, clock, "puntamento", frames=5)
    feed(r, clock, "tre_dita", frames=6)
    events = feed(r, clock, "puntamento", frames=8)
    check("il click destro non porta con se' un click sinistro",
          LEFT_CLICK not in events, "eventi: %r" % events)


def test_thumb_middle_alone_is_not_a_right_click():
    """
    Il vecchio gesto pollice+medio non deve piu' fare niente.

    Su questa mano non era separabile dal puntamento: pollice-medio vale 0.22
    puntando contro 0.12 nel pinch, margine dentro il rumore del tracciamento.
    """
    r, clock = settled()
    feed(r, clock, "aperta", frames=8)
    feed(r, clock, "pinch_medio", frames=6)
    events = feed(r, clock, "aperta", frames=8)
    check("il solo pollice+medio non clicca a destra",
          RIGHT_CLICK not in events, "eventi: %r" % events)


def test_pointing_never_right_clicks():
    """Il puntamento ha gia' il pollice sul medio: non deve mai cliccare."""
    r, clock = settled()
    events = feed(r, clock, "puntamento", frames=90)
    events += feed(r, clock, "aperta", frames=20)
    events += feed(r, clock, "puntamento", frames=30)
    check("puntando non parte mai un click destro",
          RIGHT_CLICK not in events, "eventi: %r" % events)


def test_double_click():
    """
    Due pinch ravvicinati devono produrre due click, non uno.

    Il secondo esce alla CHIUSURA del secondo pinch: aspettare la riapertura
    costava i fotogrammi di conferma del rilascio e faceva sforare i 500 ms
    che Windows concede fra i due click.
    """
    r, clock = settled()
    feed(r, clock, "puntamento", frames=5)
    events = feed(r, clock, "pinch_indice", frames=5)
    events += feed(r, clock, "puntamento", frames=5)
    events += feed(r, clock, "pinch_indice", frames=5)
    events += feed(r, clock, "puntamento", frames=8)
    check("due pinch ravvicinati danno due click",
          events.count(LEFT_CLICK) == 2, "eventi: %r" % events)


def test_double_click_fits_the_system_window():
    """I due click devono stare dentro la finestra di Windows (500 ms)."""
    r, clock = settled()
    feed(r, clock, "puntamento", frames=5)
    times = []
    start = clock.t
    for pose, n in (("pinch_indice", 5), ("puntamento", 5),
                    ("pinch_indice", 5), ("puntamento", 8)):
        for _ in range(n):
            h = hand(pose)
            now = clock.advance()
            r.prepare(h, now)
            for name, _p in r.update(h, (960, 540), now):
                if name == LEFT_CLICK:
                    times.append(now)
    check("escono due click", len(times) == 2, "istanti: %r" % times)
    if len(times) == 2:
        gap = times[1] - times[0]
        check("i due click stanno dentro 0.5 s", gap <= 0.5,
              "intervallo %.3f s" % gap)


def test_cursor_stays_still_between_the_two_clicks():
    """
    Fra i due click il cursore deve restare fermo.

    Se si sposta, il secondo click cade altrove e Windows non li accoppia: e'
    il motivo per cui il doppio click "spostava il puntatore".
    """
    r, clock = settled()
    feed(r, clock, "puntamento", frames=5)
    feed(r, clock, "pinch_indice", frames=5)
    feed(r, clock, "puntamento", frames=4)
    frozen = 0
    for _ in range(8):
        h = hand("puntamento")
        now = clock.advance()
        r.prepare(h, now)
        if r.cursor_frozen():
            frozen += 1
        r.update(h, (960, 540), now)
    check("il cursore resta bloccato nella finestra del doppio click",
          frozen == 8, "congelato %d/8" % frozen)


def test_single_click_releases_the_cursor_when_the_hand_moves():
    """
    Ma il blocco deve cadere subito se la mano si sposta davvero, altrimenti
    ogni click singolo lascerebbe il cursore incollato per mezzo secondo.
    """
    r, clock = settled()
    feed(r, clock, "puntamento", frames=5)
    feed(r, clock, "pinch_indice", frames=5)
    # 4 fotogrammi: pinch_release_frames e' 3, quindi qui il click e' gia'
    # uscito e siamo dentro la finestra del doppio click.
    feed(r, clock, "puntamento", frames=4)
    # Stessa posa, ma la mano si e' spostata nell'inquadratura.
    frozen = 0
    for _ in range(6):
        h = hand("puntamento", wrist=(0.75, 0.5))
        now = clock.advance()
        r.prepare(h, now)
        if r.cursor_frozen():
            frozen += 1
        r.update(h, (960, 540), now)
    check("muovendo la mano il cursore si libera subito", frozen == 0,
          "congelato %d/6" % frozen)


def test_cursor_free_while_pointing():
    r, clock = settled()
    frozen = 0
    for _ in range(60):
        h = hand("puntamento")
        now = clock.advance()
        r.prepare(h, now)
        if r.cursor_frozen():
            frozen += 1
        r.update(h, (960, 540), now)
    check("il cursore resta libero puntando", frozen == 0,
          "congelato %d/60" % frozen)


def test_cursor_freezes_when_starting_a_pinch():
    r, clock = settled()
    feed(r, clock, "puntamento", frames=10)
    h = hand("pinch_indice")
    now = clock.advance()
    r.prepare(h, now)
    check("il cursore si congela iniziando il pinch", r.cursor_frozen(),
          "pollice-indice %.2f, soglia %.2f" % (r.left_ratio, config.pinch_freeze_ratio))


def _run_all():
    print("soglie attive: indice >=%.2f | pinch <%.2f / >%.2f | tre dita <%.2f\n"
          % (config.index_control_ratio, config.pinch_close_ratio,
             config.pinch_open_ratio, config.right_pinch_close_ratio))
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        print(test.__name__)
        test()
        print()
    return len(tests)


def main():
    """
    Due giri: valori di fabbrica e profilo salvato.

    Il primo giro e' quello che conta di piu'. Un utente nuovo parte dai default
    di `config.py` senza aver calibrato niente: se su una mano vera quei default
    bloccano i click, l'applicazione e' rotta appena installata — ed e'
    esattamente com'era, perche' i default erano tarati su valori di riferimento
    scritti nei commenti e mai misurati.
    """
    total = 0
    print("Test sulle misure di una mano vera\n")
    print("=" * 58)
    print("1/2  valori di fabbrica (config.py)")
    print("=" * 58)
    total += _run_all()

    print("=" * 58)
    print("2/2  profilo salvato (Profiles/settings.txt)")
    print("=" * 58)
    import settings_gui  # noqa: F401  (l'import applica il profilo a config)
    total += _run_all()

    if FAILURES:
        print("%d test falliti: %s" % (len(FAILURES), ", ".join(sorted(set(FAILURES)))))
        return 1
    print("Tutti i %d gruppi di test sono passati (fabbrica + profilo)." % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
