"""
Test della macchina a stati delle gesture, senza webcam.

Simula sequenze di mani sintetiche e verifica che gli eventi emessi siano
esattamente quelli attesi. Serve soprattutto a dimostrare che i falsi positivi
della versione precedente non possono piu' verificarsi: il caso "mignolo
chiuso" che sparava un click destro al secondo e' il primo test qui sotto.

    python test_gestures.py
"""

import math
import sys

import config
from gesture_recognizer import (
    GestureRecognizer, LEFT_CLICK, RIGHT_CLICK, DRAG_START, DRAG_END, SCROLL,
)
from hand_tracker import HandObservation

SCALE = 0.15  # dimensione mano in unita' normalizzate

# Quanto e' distesa la punta dell'indice rispetto alla nocca, per posa.
#
# Questi valori sono la ragione per cui la prima versione dei test dava un
# falso "tutto a posto": il fixture teneva l'indice sempre esteso durante il
# pinch, mentre nella realta' pinzare l'indice lo piega. La macchina a stati
# bloccava quindi ogni click e i test non se ne accorgevano.
EXT_POINTING = 1.40   # indice teso
EXT_PINCHING = 1.05   # indice piegato in punta per pinzare
EXT_FIST = 0.50       # indice ripiegato sul palmo


def make_hand(index_pinch=1.0, middle_pinch=1.0, fingers=(1, 0, 0, 0),
              wrist=(0.5, 0.8), reacquired=False, index_extension=None):
    """
    Costruisce una HandObservation sintetica.

    `index_pinch` e `middle_pinch` sono i rapporti desiderati fra pollice e
    rispettiva punta, in frazioni di dimensione mano.

    `index_extension` di default e' dedotto dal pinch: se il pinch e' chiuso,
    l'indice risulta piegato come succede davvero pinzando.
    """
    if index_extension is None:
        index_extension = EXT_PINCHING if index_pinch < 0.7 else EXT_POINTING

    pts = [(0.0, 0.0)] * 21
    wx, wy = wrist
    pts[0] = (wx, wy)
    pts[9] = (wx, wy - SCALE)                      # nocca del medio
    pts[4] = (wx - 0.05, wy - SCALE * 0.8)         # pollice
    tx, ty = pts[4]
    pts[8] = (tx + index_pinch * SCALE, ty)        # punta indice
    pts[12] = (tx + middle_pinch * SCALE, ty)      # punta medio
    pts[5] = (wx + 0.02, wy - SCALE * 0.9)         # nocca indice
    return HandObservation("Right", 0.98, pts, SCALE, tuple(fingers), reacquired,
                           index_extension)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def advance(self, seconds):
        self.t += seconds
        return self.t


def run(recognizer, clock, hand, frames=1, dt=1 / 30, cursor=(960, 540)):
    """Alimenta il riconoscitore per N frame e raccoglie tutti gli eventi."""
    events = []
    for _ in range(frames):
        events.extend(recognizer.update(hand, cursor, clock.advance(dt)))
    return [name for name, _ in events]


def settle(recognizer, clock, cursor=(960, 540)):
    """Supera il periodo di grazia dopo il riaggancio e stabilizza lo stato."""
    open_hand = make_hand(1.0, 1.0)
    run(recognizer, clock, open_hand, frames=20)


# ---------------------------------------------------------------------------
FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print("  ok    %s" % name)
    else:
        print("  FALLITO  %s  %s" % (name, detail))
        FAILURES.append(name)


def test_pinky_does_not_fire_right_click():
    """
    Il bug principale della versione precedente.

    Il click destro era legato allo STATO del mignolo: in una normale posa di
    puntamento il mignolo e' chiuso, quindi partiva un click destro al secondo,
    all'infinito. Qui il mignolo chiuso deve essere del tutto irrilevante.
    """
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    # Mano che punta: indice esteso, tutto il resto chiuso, mignolo compreso.
    hand = make_hand(1.0, 1.0, fingers=(1, 0, 0, 0))
    events = run(r, clock, hand, frames=300)  # 10 secondi
    check("mignolo chiuso per 10s non genera click destri",
          events == [], "eventi ottenuti: %r" % events)


def test_left_click():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    run(r, clock, make_hand(1.0, 1.0), frames=3)
    run(r, clock, make_hand(0.2, 1.0), frames=4)   # pinch chiuso
    events = run(r, clock, make_hand(1.0, 1.0), frames=6)  # riaperto
    check("pinch breve produce un click sinistro",
          events.count(LEFT_CLICK) == 1, "eventi: %r" % events)


def test_pinch_hold_becomes_drag():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    events = run(r, clock, make_hand(0.2, 1.0), frames=30)  # 1 s tenuto
    check("pinch tenuto avvia il drag", DRAG_START in events, "eventi: %r" % events)
    check("pinch tenuto non produce anche un click",
          LEFT_CLICK not in events, "eventi: %r" % events)
    events = run(r, clock, make_hand(1.0, 1.0), frames=6)
    check("riapertura chiude il drag", DRAG_END in events, "eventi: %r" % events)


def test_drag_survives_single_bad_frame():
    """Un fotogramma sbagliato del modello non deve interrompere il drag."""
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    run(r, clock, make_hand(0.2, 1.0), frames=30)
    check("drag attivo", r.dragging)
    events = run(r, clock, make_hand(1.5, 1.0), frames=1)   # un frame sbagliato
    events += run(r, clock, make_hand(0.2, 1.0), frames=5)  # torna normale
    check("un frame anomalo non interrompe il drag",
          DRAG_END not in events and r.dragging, "eventi: %r" % events)


def test_right_click_fires_once_per_gesture():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    run(r, clock, make_hand(1.0, 0.2), frames=40)   # pinch medio tenuto a lungo
    events = run(r, clock, make_hand(1.0, 1.0), frames=6)
    check("pinch pollice+medio produce esattamente un click destro",
          events.count(RIGHT_CLICK) == 1, "eventi: %r" % events)


def test_hysteresis_blocks_chatter():
    """
    Un valore che oscilla intorno alla soglia non deve produrre eventi.

    Con una soglia sola (versione precedente) questo genererebbe una raffica di
    click. Con l'isteresi il segnale non attraversa mai entrambe le soglie.
    """
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    mid = (config.pinch_close_ratio + config.pinch_open_ratio) / 2
    events = []
    for i in range(200):
        ratio = mid + (0.01 if i % 2 else -0.01)
        events.extend(run(r, clock, make_hand(ratio, 1.0), frames=1))
    check("oscillazione intorno alla soglia non genera click",
          events == [], "eventi: %r" % events)


def test_reacquired_hand_is_gated():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    # La mano rientra gia' in posizione di pinch: non deve cliccare.
    hand = make_hand(0.2, 1.0, reacquired=True)
    events = run(r, clock, hand, frames=3)
    check("mano appena riagganciata non clicca",
          events == [], "eventi: %r" % events)


def test_fast_motion_blocks_click():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    # Cursore che sfreccia: il click deve essere scartato.
    x = 100
    for _ in range(6):
        x += 400
        run(r, clock, make_hand(0.2, 1.0), frames=1, cursor=(x, 540))
    events = []
    for _ in range(6):
        x += 400
        events.extend(run(r, clock, make_hand(1.0, 1.0), frames=1, cursor=(x, 540)))
    check("click ignorato a mano lanciata",
          LEFT_CLICK not in events, "velocita' %.0f, eventi %r" % (r.hand_speed, events))


def test_closed_hand_is_inert():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    # Pugno vero: pollice e indice vicini MA indice ripiegato sul palmo.
    hand = make_hand(0.2, 0.2, fingers=(0, 0, 0, 0), index_extension=EXT_FIST)
    events = run(r, clock, hand, frames=120)
    check("pugno chiuso non produce nessun evento",
          events == [], "eventi: %r" % events)


def test_pinch_that_bends_the_index_still_clicks():
    """
    Il caso segnalato dall'uso reale.

    Pinzando, l'indice si piega. La prima versione lo misurava dal polso e lo
    dichiarava "non esteso" proprio durante il pinch: il gate della posa di
    controllo azzerava la macchina a stati e non usciva ne' click ne' drag.
    """
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    run(r, clock, make_hand(1.0, 1.0), frames=3)
    # Durante il pinch anche il conteggio dita dice indice abbassato.
    run(r, clock, make_hand(0.2, 1.0, fingers=(0, 0, 0, 0)), frames=4)
    events = run(r, clock, make_hand(1.0, 1.0), frames=6)
    check("il pinch che piega l'indice produce comunque il click",
          events.count(LEFT_CLICK) == 1,
          "eventi: %r, blocco: %r" % (events, r.gated_reason))


def test_held_pinch_with_bent_index_drags():
    """Stesso caso del click, ma tenuto: deve diventare un drag."""
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    events = run(r, clock, make_hand(0.2, 1.0, fingers=(0, 0, 0, 0)), frames=30)
    check("il pinch tenuto con indice piegato avvia il drag",
          DRAG_START in events, "eventi: %r, blocco: %r" % (events, r.gated_reason))
    events = run(r, clock, make_hand(1.0, 1.0), frames=6)
    check("e lo rilascia riaprendo", DRAG_END in events, "eventi: %r" % events)


def test_pinch_and_fist_are_distinguished():
    """
    Pinch e pugno hanno entrambi pollice e indice vicini: a separarli e' solo
    quanto e' disteso l'indice. Questa e' la misura su cui regge tutto il
    comportamento "mano chiusa = inerte".
    """
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    run(r, clock, make_hand(0.2, 1.0, index_extension=EXT_PINCHING), frames=4)
    pinch_events = run(r, clock, make_hand(1.0, 1.0), frames=6)

    r2 = GestureRecognizer(config)
    clock2 = Clock()
    settle(r2, clock2)
    run(r2, clock2, make_hand(0.2, 1.0, index_extension=EXT_FIST), frames=4)
    fist_events = run(r2, clock2, make_hand(1.0, 1.0), frames=6)

    check("il pinch clicca", pinch_events.count(LEFT_CLICK) == 1,
          "eventi: %r" % pinch_events)
    check("il pugno no", fist_events == [], "eventi: %r" % fist_events)


def test_cursor_freezes_before_pinch_completes():
    """
    Il congelamento deve scattare durante l'AVVICINAMENTO delle dita.

    Se scatta solo a pinch completato, la punta dell'indice (che e' il cursore)
    ha gia' fatto in tempo a spostarsi e il click cade fuori bersaglio.
    """
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    run(r, clock, make_hand(1.4, 1.0), frames=3)
    check("cursore libero a mano ben aperta", not r.cursor_frozen())
    # Dita che si stanno avvicinando, pinch ancora ben lontano dalla chiusura.
    r.prepare(make_hand(0.85, 1.0), clock.advance(1 / 30))
    check("cursore gia' congelato durante l'avvicinamento", r.cursor_frozen(),
          "rapporto %.2f, soglia %.2f" % (r.left_ratio, config.pinch_freeze_ratio))


def test_scroll_pose():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    events = []
    y = 0.8
    for _ in range(20):
        y -= 0.01
        events.extend(run(r, clock,
                          make_hand(1.0, 1.0, fingers=(1, 1, 0, 0), wrist=(0.5, y)),
                          frames=1))
    check("posa a due dita produce scroll", SCROLL in events, "eventi: %r" % events)
    check("lo scroll non produce click",
          LEFT_CLICK not in events and RIGHT_CLICK not in events)


def test_cursor_freeze_during_pinch():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    run(r, clock, make_hand(1.0, 1.0), frames=3)
    check("cursore libero a mano aperta", not r.cursor_frozen())
    run(r, clock, make_hand(0.3, 1.0), frames=3)
    check("cursore congelato durante il pinch", r.cursor_frozen())
    run(r, clock, make_hand(0.2, 1.0), frames=30)
    check("cursore libero durante il drag", not r.cursor_frozen())


def test_hand_lost_releases_drag():
    r = GestureRecognizer(config)
    clock = Clock()
    settle(r, clock)
    run(r, clock, make_hand(0.2, 1.0), frames=30)
    check("drag avviato", r.dragging)
    events = [name for name, _ in r.update(None, (960, 540), clock.advance(0.03))]
    check("la mano che sparisce rilascia il tasto",
          DRAG_END in events, "eventi: %r" % events)


def test_scale_invariance():
    """La stessa gesture deve funzionare a qualsiasi distanza dalla webcam."""
    global SCALE
    original = SCALE
    outcomes = []
    for scale in (0.06, 0.15, 0.32):   # mano lontana, media, vicina
        SCALE = scale
        r = GestureRecognizer(config)
        clock = Clock()
        settle(r, clock)
        run(r, clock, make_hand(1.0, 1.0), frames=3)
        run(r, clock, make_hand(0.2, 1.0), frames=4)
        events = run(r, clock, make_hand(1.0, 1.0), frames=6)
        outcomes.append(events.count(LEFT_CLICK))
    SCALE = original
    check("un click a ogni distanza dalla webcam",
          outcomes == [1, 1, 1], "click per distanza: %r" % outcomes)


def main():
    print("Test della macchina a stati delle gesture\n")
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
