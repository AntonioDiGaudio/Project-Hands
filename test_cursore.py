"""
Test del percorso completo mano -> cursore, senza toccare il mouse vero.

Gli altri test si fermano agli EVENTI: dicono che un click esce, non DOVE
cade. E' la meta' che mancava, perche' i sintomi riportati dall'uso reale
("cliccando il puntatore scende", "il doppio click non lo prende", "il drag si
stacca da solo") non sono eventi mancanti: sono eventi giusti nel posto
sbagliato. Qui il cursore viene mosso davvero attraverso `MouseController`, con
`_set_cursor` sostituito da un registratore, e si misurano i pixel.

La mano e' parametrica su un solo numero: quanto e' avanti il pinch, da 0
(indice puntato) a 1 (pollice e indice uniti). Tutte le grandezze interpolano
fra le misure reali di `diagnosi.txt`, punta dell'indice compresa: e' la punta
che porta il cursore, ed e' la punta che si sposta quando pinzi.

    python test_cursore.py
"""

import sys

import config
import mouse_controller
from gesture_recognizer import (
    GestureRecognizer, LEFT_CLICK, RIGHT_CLICK, DRAG_START, DRAG_END,
)
from hand_tracker import HandObservation
from mouse_controller import MouseController

SCALE = 0.15
SCREEN_W, SCREEN_H = 1920, 1080

# Misure reali, dai due estremi del gesto (mediane di diagnosi.txt).
#            indice teso   medio teso   poll-indice   poll-medio
PUNTAMENTO = (0.93,        0.46,        1.19,         0.22)
PINCH      = (0.46,        0.84,        0.14,         0.98)

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print("  ok    %s" % name)
    else:
        print("  FALLITO  %s  %s" % (name, detail))
        FAILURES.append(name)


def _lerp(a, b, t):
    return a + (b - a) * t


def hand(t=0.0, wrist=(0.5, 0.8), fingers=None, reacquired=False,
         middle_pinch=None):
    """
    Mano a meta' strada fra puntamento (t=0) e pinch chiuso (t=1).

    `middle_pinch`, se dato, sovrascrive la distanza pollice-medio: serve al
    pinch a tre dita, dove anche il medio va sul pollice.
    """
    idx_ext = _lerp(PUNTAMENTO[0], PINCH[0], t)
    mid_ext = _lerp(PUNTAMENTO[1], PINCH[1], t)
    thumb_index = _lerp(PUNTAMENTO[2], PINCH[2], t)
    thumb_middle = middle_pinch if middle_pinch is not None else _lerp(
        PUNTAMENTO[3], PINCH[3], t)
    if fingers is None:
        fingers = (1, 0, 0, 0) if t < 0.5 else (0, 1, 1, 1)

    wx, wy = wrist
    pts = [(0.0, 0.0)] * 21
    pts[0] = (wx, wy)
    pts[9] = (wx, wy - SCALE)                  # nocca del medio
    kx, ky = wx + 0.02, wy - SCALE * 0.9       # nocca dell'indice
    pts[5] = (kx, ky)
    # La punta sta sopra la nocca, a una distanza pari all'estensione: e' la
    # definizione stessa di index_extension, quindi chiudendo il pinch la punta
    # SCENDE, esattamente come sulla mano vera.
    pts[8] = (kx, ky - idx_ext * SCALE)
    # Il pollice si mette alla distanza voluta dalla punta dell'indice...
    pts[4] = (pts[8][0] + thumb_index * SCALE, pts[8][1])
    # ...e la punta del medio alla distanza voluta dal pollice.
    pts[12] = (pts[4][0], pts[4][1] + thumb_middle * SCALE)
    return HandObservation("Right", 0.98, pts, SCALE, fingers, reacquired,
                           idx_ext, mid_ext)


class Rig:
    """Riconoscitore + controller cablati come li cabla `app.py`."""

    def __init__(self):
        self.moves = []
        self.clicks = []          # (istante, pixel, tipo)
        self.buttons = []         # sequenza grezza di down/up
        self._real = (mouse_controller._set_cursor,
                      mouse_controller._left_down,
                      mouse_controller._left_up,
                      mouse_controller._right_click)
        mouse_controller._set_cursor = self._move
        mouse_controller._left_down = lambda: self.buttons.append("down")
        mouse_controller._left_up = lambda: self.buttons.append("up")
        mouse_controller._right_click = lambda: self.buttons.append("right")

        self.mouse = MouseController(config)
        self.mouse.screen_w, self.mouse.screen_h = SCREEN_W, SCREEN_H
        self.gestures = GestureRecognizer(config)
        self.now = 1000.0
        self.events = []

    def close(self):
        (mouse_controller._set_cursor, mouse_controller._left_down,
         mouse_controller._left_up, mouse_controller._right_click) = self._real

    def _move(self, x, y):
        self.moves.append((x, y))

    @property
    def cursor(self):
        return self.moves[-1] if self.moves else None

    def feed(self, h, frames=1, dt=1 / 30.0):
        """Un giro identico a quello di `AirMouseApp._handle_hands`."""
        out = []
        for _ in range(frames):
            self.now += dt
            nx, ny = h.point(8)
            self.gestures.prepare(h, self.now)
            frozen = self.gestures.cursor_frozen()
            pos = self.mouse.update_cursor(nx, ny, self.now, frozen=frozen)
            for name, payload in self.gestures.update(h, pos, self.now):
                out.append(name)
                if name == LEFT_CLICK:
                    self.mouse.left_click(same_spot=payload == "double")
                    self.clicks.append((self.now, self.mouse.last_click_pixel,
                                        payload))
                elif name == RIGHT_CLICK:
                    self.mouse.right_click()
                elif name == DRAG_START:
                    self.mouse.drag_start()
                elif name == DRAG_END:
                    self.mouse.drag_end()
        self.events.extend(out)
        return out

    def pinch_cycle(self, close_frames=5, hold_frames=3, open_frames=5,
                    wrist=(0.5, 0.8), middle=None, gate_flicker=False):
        """
        Un pinch completo: chiusura graduale, tenuta, riapertura graduale.

        `gate_flicker` sporca un fotogramma della chiusura portando l'indice
        sotto la soglia della posa di controllo, come fa il modello ogni tanto.
        """
        for i in range(1, close_frames + 1):
            h = hand(i / float(close_frames), wrist=wrist, middle_pinch=middle)
            if gate_flicker and i == max(1, close_frames // 2):
                h.index_extension = 0.30
            self.feed(h)
        self.feed(hand(1.0, wrist=wrist, middle_pinch=middle),
                  frames=hold_frames)
        for i in range(open_frames, 0, -1):
            self.feed(hand((i - 1) / float(open_frames), wrist=wrist,
                           middle_pinch=middle))
        # Mano riaperta e ferma: e' li' che cade la conferma di rilascio, e
        # quindi il click. Senza questi fotogrammi il ciclo finirebbe prima
        # dell'evento che sta misurando.
        self.feed(hand(0.0, wrist=wrist, middle_pinch=middle), frames=4)


def aim(rig, wrist=(0.5, 0.8), frames=25):
    """Mano ferma in posa di puntamento: il cursore si stabilizza sul bersaglio."""
    rig.feed(hand(0.0, wrist=wrist), frames=frames)
    return rig.cursor


# ---------------------------------------------------------------------------
def test_click_lands_where_you_aimed():
    """
    Il sintomo numero uno: "se faccio click, il puntatore scende in basso".

    Il cursore segue la punta dell'indice, e pinzare piega l'indice: misurato
    su una mano vera l'estensione passa da 0.93 a 0.46, cioe' la punta scende di
    mezza lunghezza di dito. Sullo schermo sono un centinaio di pixel. Il
    congelamento deve intercettare la discesa quando e' appena cominciata.
    """
    rig = Rig()
    try:
        target = aim(rig)
        rig.pinch_cycle()
        click = [c for c in rig.clicks if c[2] != "double"]
        check("il click esce", len(click) == 1, "click: %r" % rig.clicks)
        if click:
            dy = click[0][1][1] - target[1]
            dx = click[0][1][0] - target[0]
            check("il click cade dove puntavi (entro 15 px)",
                  abs(dy) <= 15 and abs(dx) <= 15,
                  "scarto x %.0f px, y %+.0f px" % (dx, dy))
    finally:
        rig.close()


def test_click_survives_a_gate_flicker():
    """
    Un solo fotogramma in cui l'indice misura poco non deve costare il click.

    Misurato su questo banco con la versione precedente: quel singolo
    fotogramma azzerava i rilevatori, e con loro la storia dei rapporti su cui
    si regge il congelamento. Risultato, nessun click affatto — e nei casi in
    cui il click usciva lo stesso, il cursore era sceso di 113 px perche' il
    blocco non poteva piu' accorgersi dell'avvicinamento.
    """
    rig = Rig()
    try:
        target = aim(rig)
        rig.pinch_cycle(gate_flicker=True)
        click = [c for c in rig.clicks if c[2] != "double"]
        check("il click esce lo stesso", len(click) == 1,
              "click: %r" % rig.clicks)
        if click:
            dy = click[0][1][1] - target[1]
            check("e cade ancora sul bersaglio", abs(dy) <= 15,
                  "scarto y %+.0f px" % dy)
    finally:
        rig.close()


def test_slow_pinch_lands_on_target():
    """
    Mezzo secondo per chiudere le dita: il blocco deve reggere anche cosi'.

    E' il caso in cui la sola distanza pollice-indice non basta: il massimo
    recente si aggiorna insieme alla discesa, quindi un avvicinamento lento non
    supera mai la soglia di calo. La piega dell'indice invece si vede subito.
    """
    rig = Rig()
    try:
        target = aim(rig)
        rig.pinch_cycle(close_frames=15, hold_frames=2, open_frames=4)
        click = [c for c in rig.clicks if c[2] != "double"]
        check("il click esce", len(click) == 1, "click: %r" % rig.clicks)
        if click:
            dy = click[0][1][1] - target[1]
            check("un pinch lento cade comunque sul bersaglio", abs(dy) <= 15,
                  "scarto y %+.0f px" % dy)
    finally:
        rig.close()


def test_every_pinch_is_either_a_click_or_a_drag():
    """
    Nessuna durata deve cadere nel vuoto.

    E' il sintomo "il click non funziona, a volte lo confonde con un drag".
    La durata del pinch veniva misurata dalla soglia di CHIUSURA (0.41) a quella
    di APERTURA (0.77), quindi comprendeva la corsa dell'isteresi: un tap da
    0.25 s ne contava 0.40, cioe' oltre `drag_hold_time`, e usciva un drag —
    tasto premuto che si sposta con la mano. Correggere solo la misura apriva
    una zona morta di un paio di fotogrammi in cui non usciva NIENTE.

    Qui si spazza tutta la scala delle durate: ogni pinch deve produrre
    esattamente una cosa, un click o un trascinamento.
    """
    vuoti, doppi, scala = [], [], []
    for hold in range(1, 26):
        rig = Rig()
        try:
            aim(rig, frames=20)
            rig.pinch_cycle(hold_frames=hold)
            click = LEFT_CLICK in rig.events
            drag = DRAG_START in rig.events
            scala.append("%.2f:%s" % (rig.gestures.last_hold,
                                      "click" if click else ("drag" if drag else "-")))
            if not click and not drag:
                vuoti.append("%d fotogrammi tenuti" % hold)
            if click and drag:
                doppi.append("%d fotogrammi tenuti" % hold)
        finally:
            rig.close()
    check("nessun pinch resta senza evento", not vuoti,
          "niente per: %s   [%s]" % (", ".join(vuoti), " ".join(scala)))
    check("nessun pinch produce click E drag insieme", not doppi,
          "entrambi per: %s" % ", ".join(doppi))


def test_a_quick_tap_is_not_a_drag():
    """Un tap breve resta un click, col tasto che non si sposta di un pixel."""
    rig = Rig()
    try:
        aim(rig)
        rig.pinch_cycle(hold_frames=6)
        check("un tap di 0.30 s e' un click", LEFT_CLICK in rig.events,
              "eventi: %r" % rig.events)
        check("e non un drag", DRAG_START not in rig.events,
              "eventi: %r" % rig.events)
        check("al sistema arriva una pressione pulita",
              rig.buttons == ["down", "up"], "sequenza: %r" % rig.buttons)
    finally:
        rig.close()


def test_cursor_comes_back_after_the_click():
    """Il blocco non deve lasciare il cursore alla deriva dopo il click."""
    rig = Rig()
    try:
        target = aim(rig)
        rig.pinch_cycle()
        rig.feed(hand(0.0), frames=40)   # oltre la finestra del doppio click
        dy = rig.cursor[1] - target[1]
        check("finito il click il cursore torna sul bersaglio", abs(dy) <= 6,
              "scarto y %+.0f px" % dy)
    finally:
        rig.close()


def test_double_click_lands_on_one_pixel():
    """
    "doppio click non lo prende": Windows accoppia due click solo se cadono a
    pochi pixel l'uno dall'altro (SM_CXDOUBLECLK, di fabbrica 4) e dentro
    GetDoubleClickTime. Due click a 40 px di distanza sono due click singoli,
    per quanto ravvicinati nel tempo.
    """
    rig = Rig()
    try:
        aim(rig)
        rig.pinch_cycle()
        rig.feed(hand(0.0), frames=2)
        rig.pinch_cycle()
        check("escono due click", len(rig.clicks) == 2,
              "click: %r" % rig.clicks)
        if len(rig.clicks) == 2:
            (t1, p1, _), (t2, p2, _) = rig.clicks
            check("i due click cadono sullo stesso pixel", p1 == p2,
                  "%r contro %r" % (p1, p2))
            limit = mouse_controller.system_double_click_time()
            check("e dentro la finestra di sistema", t2 - t1 <= limit,
                  "%.3f s contro %.3f s concessi" % (t2 - t1, limit))
            check("al sistema arrivano due pressioni pulite",
                  rig.buttons == ["down", "up", "down", "up"],
                  "sequenza: %r" % rig.buttons)
    finally:
        rig.close()


def test_drag_does_not_slide_after_the_grab():
    """
    Il congelamento finisce a tasto GIA' premuto: se lo scarto accumulato viene
    riassorbito muovendo il cursore, il drag parte trascinando l'oggetto per un
    centinaio di pixel da solo. Con la mano ferma, dopo il DRAG_START il
    cursore non deve andare da nessuna parte.
    """
    rig = Rig()
    try:
        aim(rig)
        for i in range(1, 6):
            rig.feed(hand(i / 5.0))
        rig.feed(hand(1.0), frames=12)        # oltre drag_hold_time
        check("il drag e' partito", rig.gestures.dragging,
              "stato: %s" % rig.gestures.status_text())
        start = rig.cursor
        rig.feed(hand(1.0), frames=30)        # un secondo di mano ferma
        drift = ((rig.cursor[0] - start[0]) ** 2
                 + (rig.cursor[1] - start[1]) ** 2) ** 0.5
        check("a mano ferma il drag non scivola", drift <= 8,
              "scivolato di %.0f px" % drift)
    finally:
        rig.close()


def test_drag_follows_the_hand_one_to_one():
    """E muovendo la mano, l'oggetto deve seguirla senza guadagnare o perdere strada."""
    rig = Rig()
    try:
        aim(rig)
        for i in range(1, 6):
            rig.feed(hand(i / 5.0))
        rig.feed(hand(1.0), frames=12)
        start = rig.cursor
        for step in range(1, 21):
            rig.feed(hand(1.0, wrist=(0.5 + 0.004 * step, 0.8)))
        rig.feed(hand(1.0, wrist=(0.5 + 0.004 * 20, 0.8)), frames=15)
        # 0.08 di inquadratura * overscan * larghezza schermo.
        atteso = 0.08 * config.overscan_x * (SCREEN_W - 1)
        fatto = rig.cursor[0] - start[0]
        check("il cursore percorre quanto la mano", abs(fatto - atteso) <= 25,
              "attesi %.0f px, fatti %.0f px" % (atteso, fatto))
        check("il drag e' ancora attivo", rig.gestures.dragging)
    finally:
        rig.close()


def test_right_click_does_not_move_the_cursor():
    """Il menu contestuale deve aprirsi dove puntavi, non piu' in basso."""
    rig = Rig()
    try:
        target = aim(rig)
        for i in range(1, 6):
            rig.feed(hand(i / 5.0, middle_pinch=_lerp(0.22, 0.16, i / 5.0)))
        rig.feed(hand(1.0, middle_pinch=0.16), frames=4)
        check("il click destro esce", "right" in rig.buttons,
              "pulsanti: %r" % rig.buttons)
        dy = rig.cursor[1] - target[1]
        check("il cursore non e' sceso", abs(dy) <= 15, "scarto y %+.0f px" % dy)
    finally:
        rig.close()


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        print(test.__name__)
        test()
        print()
    return len(tests)


def main():
    print("Test del percorso mano -> cursore (il mouse NON viene mosso)\n")
    print("=" * 58)
    print("1/2  valori di fabbrica (config.py)")
    print("=" * 58)
    total = _run_all()

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
