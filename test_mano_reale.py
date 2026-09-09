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
POSE["pinch_medio_corretto"] = (0.93, 0.84, 0.74, 0.12, (1, 1, 1, 1))

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print("  ok    %s" % name)
    else:
        print("  FALLITO  %s  %s" % (name, detail))
        FAILURES.append(name)


def hand(pose, reacquired=False):
    """HandObservation che riproduce esattamente le distanze misurate."""
    idx_ext, mid_ext, thumb_index, thumb_middle, fingers = POSE[pose]
    pts = [(0.0, 0.0)] * 21
    wx, wy = 0.5, 0.8
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


def test_right_click_with_extended_middle():
    """Il click destro fatto come dice la guida: medio disteso."""
    r, clock = settled()
    feed(r, clock, "aperta", frames=8)            # arma il rilevatore destro
    feed(r, clock, "pinch_medio_corretto", frames=6)
    events = feed(r, clock, "aperta", frames=8)
    check("con il medio disteso il click destro parte",
          events.count(RIGHT_CLICK) == 1, "eventi: %r" % events)


def test_curled_middle_pinch_is_ignored():
    """
    Il click destro fatto col medio ripiegato viene ignorato, e deve esserlo.

    Su questa mano quella posa e' indistinguibile dal puntamento: il medio
    misura 0.47 in entrambe. Accettarla significherebbe cliccare a destra
    ogni volta che si punta.
    """
    r, clock = settled()
    feed(r, clock, "aperta", frames=8)
    feed(r, clock, "pinch_medio", frames=6)
    events = feed(r, clock, "aperta", frames=8)
    check("il pinch medio col medio ripiegato non clicca",
          RIGHT_CLICK not in events, "eventi: %r" % events)


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
    print("soglie attive: indice >=%.2f | medio >=%.2f | pinch <%.2f / >%.2f\n"
          % (config.index_control_ratio, config.middle_control_ratio,
             config.pinch_close_ratio, config.pinch_open_ratio))
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
