"""
Test dello zoom a due mani, senza webcam e senza toccare il mouse.

Lo zoom era l'unica gesture senza nessuna copertura, ed e' anche quella che si
e' rotta nel modo piu' silenzioso: `pyautogui.scroll(3)` con ctrl premuto non
faceva assolutamente niente, perche' su Windows quell'argomento finisce tale e
quale in `mouse_event(dwData=n)` dove **uno scatto di rotellina vale 120**.
Mandare 3 significa mandare il 2.5% di uno scatto, e nessuna applicazione zooma
per cosi' poco. Non c'era nessun errore, nessuna eccezione, nessun log: la
gesture veniva riconosciuta correttamente e non succedeva niente.

I test qui sotto guardano quindi due cose diverse:

* che la gesture venga riconosciuta (la posa giusta, e solo quella);
* che l'evento che ne esce sia nell'unita' che Windows si aspetta.

    python test_zoom.py
"""

import sys

import config
import mouse_controller
from test_gestures import make_hand, EXT_POINTING

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print("  ok    %s" % name)
    else:
        print("  FALLITO  %s  %s" % (name, detail))
        FAILURES.append(name)


class WheelRecorder:
    """Intercetta le rotellate al posto di mandarle al sistema."""

    def __init__(self):
        self.deltas = []
        self.ctrl = 0
        self._wheel = mouse_controller._wheel
        self._down = mouse_controller.pyautogui.keyDown
        self._up = mouse_controller.pyautogui.keyUp

    def __enter__(self):
        mouse_controller._wheel = lambda n: self.deltas.append(int(n) * 120)
        mouse_controller.pyautogui.keyDown = self._note_down
        mouse_controller.pyautogui.keyUp = self._note_up
        return self

    def __exit__(self, *exc):
        mouse_controller._wheel = self._wheel
        mouse_controller.pyautogui.keyDown = self._down
        mouse_controller.pyautogui.keyUp = self._up
        return False

    def _note_down(self, key):
        if key == "ctrl":
            self.ctrl += 1

    def _note_up(self, key):
        if key == "ctrl":
            self.ctrl -= 1


def new_controller():
    """MouseController senza toccare pyautogui.size() ne' lo schermo."""
    m = mouse_controller.MouseController.__new__(mouse_controller.MouseController)
    m.config = config
    m.last_zoom_ratio = None
    m.zoom_cooldown = 0.0
    m._zoom_window = []
    return m


# ---------------------------------------------------------------------------
def test_spreading_hands_zoom_in():
    m = new_controller()
    with WheelRecorder() as rec:
        t = 1000.0
        for i in range(10):
            m.handle_zoom(1.0 + i * 0.06, True, t + i)
    check("allontanare le mani produce uno zoom", bool(rec.deltas),
          "nessun evento")
    check("lo zoom va IN (rotellina in avanti)",
          all(d > 0 for d in rec.deltas), "delta: %r" % rec.deltas)


def test_closing_hands_zoom_out():
    m = new_controller()
    with WheelRecorder() as rec:
        t = 1000.0
        for i in range(10):
            m.handle_zoom(2.0 - i * 0.12, True, t + i)
    check("avvicinare le mani produce uno zoom", bool(rec.deltas))
    check("lo zoom va OUT (rotellina indietro)",
          all(d < 0 for d in rec.deltas), "delta: %r" % rec.deltas)


def test_zoom_uses_a_whole_wheel_notch():
    """
    Il bug vero e proprio.

    L'unita' di `mouse_event(MOUSEEVENTF_WHEEL, ..., dwData=n)` e' WHEEL_DELTA,
    che vale 120 per uno scatto. Prima qui passava un 3.
    """
    m = new_controller()
    with WheelRecorder() as rec:
        t = 1000.0
        for i in range(10):
            m.handle_zoom(1.0 + i * 0.06, True, t + i)
    expected = 120 * max(1, int(config.zoom_notches))
    check("ogni passo di zoom vale almeno uno scatto intero",
          rec.deltas and all(abs(d) >= 120 for d in rec.deltas),
          "delta: %r (uno scatto = 120)" % rec.deltas)
    check("l'ampiezza segue zoom_notches",
          all(abs(d) == expected for d in rec.deltas),
          "attesi %d, ottenuti %r" % (expected, rec.deltas))


def test_ctrl_is_released_after_every_zoom():
    """Ctrl non deve mai restare premuto: bloccherebbe la tastiera."""
    m = new_controller()
    with WheelRecorder() as rec:
        t = 1000.0
        for i in range(10):
            m.handle_zoom(1.0 + i * 0.06, True, t + i)
        check("ctrl e' stato premuto", rec.ctrl == 0 and rec.deltas,
              "bilancio ctrl: %d" % rec.ctrl)


def test_still_hands_do_not_zoom():
    m = new_controller()
    with WheelRecorder() as rec:
        t = 1000.0
        for i in range(40):
            m.handle_zoom(1.30, True, t + i * 0.05)
    check("mani ferme non producono zoom", rec.deltas == [],
          "delta: %r" % rec.deltas)


def test_inactive_pose_resets_the_reference():
    """Uscendo dalla posa la distanza di riferimento deve essere dimenticata."""
    m = new_controller()
    with WheelRecorder() as rec:
        m.handle_zoom(1.0, True, 1000.0)
        m.handle_zoom(0.0, False, 1001.0)
        check("la posa interrotta azzera il riferimento",
              m.last_zoom_ratio is None)
        # Ripartendo da una distanza molto diversa non deve scattare nulla:
        # sarebbe un salto di zoom fantasma.
        m.handle_zoom(2.0, True, 1002.0)
        check("riprendendo la posa non parte uno zoom fantasma",
              rec.deltas == [], "delta: %r" % rec.deltas)


# ---------------------------------------------------------------------------
# La posa, lato applicazione.
# ---------------------------------------------------------------------------
def _app():
    import app as appmod

    a = appmod.AirMouseApp.__new__(appmod.AirMouseApp)
    a.mouse_controller = new_controller()
    return a


def _two_hands(index_up_a=1, middle_up_a=0, index_up_b=1, middle_up_b=0,
               separation=1.0, pinch_a=1.0, pinch_b=1.0):
    a = make_hand(pinch_a, fingers=(index_up_a, middle_up_a, 0, 0),
                  wrist=(0.3, 0.6), index_extension=EXT_POINTING)
    b = make_hand(pinch_b, fingers=(index_up_b, middle_up_b, 0, 0),
                  wrist=(0.3 + separation * 0.2, 0.6),
                  index_extension=EXT_POINTING)
    return a, b


def test_pose_gate():
    """
    La posa e': indici estesi su entrambe le mani, e nessuna delle due che
    pinza.

    Prima si chiedeva anche il medio CHIUSO su entrambe. Misurato con
    `diagnose.py` su una mano vera: quella condizione valeva in 0 fotogrammi su
    350, perche' chi punta l'indice tiene spesso le altre dita distese — sulla
    stessa mano il medio misura 1.06 di estensione, piu' dell'indice. Lo zoom
    non poteva partire, e nessun errore lo diceva.
    """
    a = _app()
    with WheelRecorder() as rec:
        t = 1000.0
        # Una mano che pinza: lo zoom non deve rubare il click.
        for i in range(12):
            h1, h2 = _two_hands(pinch_a=0.2, separation=1.0 + i * 0.20)
            a._handle_zoom(h1, h2, t + i)
        check("con una mano che pinza lo zoom non parte", rec.deltas == [],
              "delta: %r" % rec.deltas)

        # Il medio esteso invece NON deve piu' bloccare niente.
        rec.deltas.clear()
        a.mouse_controller = new_controller()
        for i in range(12):
            h1, h2 = _two_hands(middle_up_a=1, middle_up_b=1,
                                separation=1.0 + i * 0.20)
            a._handle_zoom(h1, h2, t + 50 + i)
        check("con il medio esteso lo zoom parte lo stesso", bool(rec.deltas),
              "delta: %r" % rec.deltas)

        # Una mano sola: niente zoom.
        rec.deltas.clear()
        for i in range(10):
            h1, _ = _two_hands(separation=1.0 + i * 0.15)
            a._handle_zoom(h1, None, t + 100 + i)
        check("con una mano sola lo zoom non parte", rec.deltas == [],
              "delta: %r" % rec.deltas)

        # Posa giusta: indici estesi, mani aperte che si allontanano.
        rec.deltas.clear()
        a.mouse_controller = new_controller()
        for i in range(12):
            h1, h2 = _two_hands(separation=1.0 + i * 0.20)
            a._handle_zoom(h1, h2, t + 200 + i)
        check("la posa corretta produce uno zoom", bool(rec.deltas),
              "delta: %r" % rec.deltas)
        check("e lo produce in scatti interi",
              all(abs(d) >= 120 for d in rec.deltas), "delta: %r" % rec.deltas)


def test_zoom_survives_a_lost_hand():
    """
    Perdere una mano per qualche fotogramma non deve azzerare il riferimento.

    Misurato: con due mani in campo il modello le vede insieme solo nel 65% dei
    fotogrammi. Azzerando a ogni buco, la variazione riparte da capo e il 18%
    richiesto non si raggiunge mai — che e' esattamente il motivo per cui lo
    zoom "non funzionava".
    """
    a = _app()
    with WheelRecorder() as rec:
        t = 1000.0
        for i in range(14):
            h1, h2 = _two_hands(separation=1.0 + i * 0.12)
            if i % 3 == 2:
                # Fotogramma in cui la seconda mano non viene rilevata.
                a._handle_zoom(h1, None, t + i * 0.05)
            else:
                a._handle_zoom(h1, h2, t + i * 0.05)
    check("lo zoom parte anche perdendo una mano ogni tre fotogrammi",
          bool(rec.deltas), "delta: %r" % rec.deltas)


def test_zoom_disabled_is_inert():
    a = _app()
    original = config.enable_zoom
    config.enable_zoom = False
    try:
        with WheelRecorder() as rec:
            for i in range(12):
                h1, h2 = _two_hands(separation=1.0 + i * 0.20)
                a._handle_zoom(h1, h2, 1000.0 + i)
        check("con enable_zoom spento non succede niente", rec.deltas == [],
              "delta: %r" % rec.deltas)
    finally:
        config.enable_zoom = original


def main():
    print("Test dello zoom a due mani\n")
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
