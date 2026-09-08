"""
Controllo del cursore e degli eventi di mouse.

Punti chiave:

* il filtro One Euro usa il **dt reale** fra due campioni invece di una
  frequenza fissa: se il frame rate oscilla (e su CPU deboli oscilla parecchio)
  un filtro tarato su 30 Hz costante diventa troppo molle o troppo nervoso;
* niente filtro di Kalman a valle. Nella versione precedente la deadzone
  usciva dalla funzione *prima* di `kf.correct()`, quindi il Kalman divergeva
  durante le pause e il cursore saltava appena si riprendeva a muovere;
* su Windows il cursore si muove con `SetCursorPos` via ctypes, misurato circa
  2.2x piu' veloce di `pyautogui.moveTo`, con fallback a pyautogui altrove;
* la rotellina NON passa da `pyautogui.scroll`. Su Windows quella funzione
  inoltra il suo argomento tale e quale a `mouse_event(MOUSEEVENTF_WHEEL, ...,
  dwData=n)`, ma li' l'unita' e' WHEEL_DELTA e **uno scatto vale 120**. Era il
  motivo per cui lo zoom non faceva assolutamente nulla: `pyautogui.scroll(3)`
  con ctrl premuto manda il 2.5% di uno scatto, e nessuna applicazione zooma
  per cosi' poco. Qui si moltiplica per WHEEL_DELTA e si parla in scatti.
"""

import math
import platform
import time

import pyautogui

pyautogui.PAUSE = 0
pyautogui.MINIMUM_DURATION = 0
pyautogui.MINIMUM_SLEEP = 0
pyautogui.FAILSAFE = False

_IS_WINDOWS = platform.system() == "Windows"

# Unita' della rotellina secondo l'API Win32: un click di rotellina = 120.
WHEEL_DELTA = 120

if _IS_WINDOWS:
    import ctypes

    _user32 = ctypes.windll.user32
    _MOUSEEVENTF_WHEEL = 0x0800
    # dwData deve poter essere negativo: senza argtypes espliciti ctypes lo
    # tratterebbe come unsigned e uno scroll all'indietro diventerebbe un
    # salto enorme in avanti.
    _user32.mouse_event.argtypes = (ctypes.c_uint, ctypes.c_long, ctypes.c_long,
                                    ctypes.c_int, ctypes.c_void_p)
    _user32.mouse_event.restype = None

    def _set_cursor(x, y):
        _user32.SetCursorPos(int(x), int(y))

    def _wheel(notches):
        """Ruota la rotellina di `notches` scatti nella posizione corrente."""
        _user32.mouse_event(_MOUSEEVENTF_WHEEL, 0, 0,
                            int(notches) * WHEEL_DELTA, None)
else:
    def _set_cursor(x, y):
        pyautogui.moveTo(int(x), int(y), _pause=False)

    def _wheel(notches):
        # Su X11 e macOS pyautogui parla gia' in scatti.
        pyautogui.scroll(int(notches))


class OneEuroFilter:
    """
    Filtro One Euro 1D.

    Bilancia jitter e latenza: da fermo filtra molto (cursore stabile), in
    movimento filtra poco (cursore reattivo).

    min_cutoff: piu' basso = piu' stabile da fermo
    beta:       piu' alto  = segue meglio i movimenti rapidi
    """

    __slots__ = ("min_cutoff", "beta", "d_cutoff", "_x_prev", "_dx_prev", "_t_prev")

    def __init__(self, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self._x_prev is None:
            self._x_prev = x
            self._t_prev = t
            return x

        dt = t - self._t_prev
        # Un dt assurdo (freeze, sospensione, primo frame dopo una pausa)
        # falserebbe la derivata: lo si riporta in un intervallo sensato.
        if dt <= 0.0 or dt > 0.5:
            dt = 1.0 / 30.0
        self._t_prev = t

        dx = (x - self._x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1.0 - a_d) * self._dx_prev

        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1.0 - a) * self._x_prev

        self._x_prev = x_hat
        self._dx_prev = dx_hat
        return x_hat

    def reset(self):
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None


class MouseController:
    """Applica gli eventi delle gesture al mouse di sistema."""

    def __init__(self, cfg):
        self.config = cfg
        self.screen_w, self.screen_h = pyautogui.size()

        self.filter_x = OneEuroFilter(
            cfg.one_euro_min_cutoff, cfg.one_euro_beta, cfg.one_euro_d_cutoff)
        self.filter_y = OneEuroFilter(
            cfg.one_euro_min_cutoff, cfg.one_euro_beta, cfg.one_euro_d_cutoff)

        self.last_pos = None          # ultima posizione effettivamente applicata
        self.target_pos = None        # ultima posizione filtrata (anche se congelata)
        self.drag_active = False
        self.last_zoom_ratio = None
        self.zoom_cooldown = 0.0
        self._zoom_window = []
        self.last_slide_time = 0.0

    # -- cursore -----------------------------------------------------------
    def map_to_screen(self, nx, ny):
        """
        Mappa una coordinata normalizzata della camera (0..1) in pixel schermo.

        L'overscan allarga l'area utile attorno al centro: con overscan 1.6 basta
        muoversi nel 62% centrale dell'inquadratura per coprire tutto lo schermo,
        cosi' non serve arrivare ai bordi (dove il tracking e' peggiore).
        """
        cfg = self.config
        cx = (nx - 0.5) * cfg.overscan_x + 0.5
        cy = (ny - 0.5) * cfg.overscan_y + 0.5

        cx = 0.0 if cx < 0.0 else (1.0 if cx > 1.0 else cx)
        cy = 0.0 if cy < 0.0 else (1.0 if cy > 1.0 else cy)

        sx = cx * (self.screen_w - 1) * cfg.cursor_speed_multiplier
        sy = cy * (self.screen_h - 1) * cfg.cursor_speed_multiplier
        return sx, sy

    def update_cursor(self, nx, ny, now, frozen=False):
        """
        Filtra e applica la posizione del cursore.

        Args:
            nx, ny: coordinate normalizzate della camera.
            now: timestamp del frame.
            frozen: se True filtra ma non muove il cursore (fase di click).

        Returns:
            tuple: posizione schermo corrente, utile al riconoscitore.
        """
        cfg = self.config
        # Riallinea i parametri se cambiati a caldo dalla GUI.
        self.filter_x.min_cutoff = self.filter_y.min_cutoff = cfg.one_euro_min_cutoff
        self.filter_x.beta = self.filter_y.beta = cfg.one_euro_beta
        self.filter_x.d_cutoff = self.filter_y.d_cutoff = cfg.one_euro_d_cutoff

        sx, sy = self.map_to_screen(nx, ny)
        fx = self.filter_x(sx, now)
        fy = self.filter_y(sy, now)
        self.target_pos = (fx, fy)

        if frozen:
            # Il filtro continua ad aggiornarsi (cosi' non c'e' uno scatto alla
            # ripresa) ma il cursore resta dove sta.
            return self.last_pos if self.last_pos else (fx, fy)

        if self.last_pos is not None:
            if (abs(fx - self.last_pos[0]) < cfg.deadzone_threshold
                    and abs(fy - self.last_pos[1]) < cfg.deadzone_threshold):
                return self.last_pos

        ix = int(fx)
        iy = int(fy)
        ix = 0 if ix < 0 else (self.screen_w - 1 if ix >= self.screen_w else ix)
        iy = 0 if iy < 0 else (self.screen_h - 1 if iy >= self.screen_h else iy)
        _set_cursor(ix, iy)
        self.last_pos = (fx, fy)
        return self.last_pos

    def reset_cursor_filter(self):
        self.filter_x.reset()
        self.filter_y.reset()

    # -- eventi ------------------------------------------------------------
    def left_click(self):
        pyautogui.click()

    def right_click(self):
        pyautogui.click(button="right")

    def drag_start(self):
        if not self.drag_active:
            pyautogui.mouseDown()
            self.drag_active = True

    def drag_end(self):
        if self.drag_active:
            pyautogui.mouseUp()
            self.drag_active = False

    def scroll(self, notches):
        """`notches` e' in scatti di rotellina, non in unita' grezze."""
        if notches:
            _wheel(notches)

    def perform_slide(self, direction):
        key = {"left": "left", "right": "right", "up": "up", "down": "down"}.get(direction)
        if key:
            pyautogui.press(key)

    # -- zoom a due mani ---------------------------------------------------
    def handle_zoom(self, ratio, active, now=None):
        """
        Zoom basato sulla distanza fra gli indici delle due mani.

        `ratio` e' gia' normalizzato sulla dimensione della mano, quindi lo zoom
        non dipende da quanto si e' lontani dalla webcam. Si reagisce alla
        **variazione relativa** della distanza, non alla distanza assoluta.
        """
        now = now if now is not None else time.time()
        cfg = self.config

        if not active:
            self.last_zoom_ratio = None
            self._zoom_window.clear()
            return False, None

        self._zoom_window.append(ratio)
        if len(self._zoom_window) > max(1, int(cfg.zoom_smooth_factor)):
            self._zoom_window.pop(0)
        smooth = sum(self._zoom_window) / len(self._zoom_window)

        if self.last_zoom_ratio is None:
            self.last_zoom_ratio = smooth
            return False, None

        if now - self.zoom_cooldown < cfg.zoom_cooldown_time:
            return False, None

        base = self.last_zoom_ratio
        if base < 1e-6:
            return False, None
        change = (smooth - base) / base

        if abs(change) < cfg.zoom_trigger_ratio:
            return False, None

        direction = "in" if change > 0 else "out"
        notches = max(1, int(getattr(cfg, "zoom_notches", 1)))
        pyautogui.keyDown("ctrl")
        try:
            _wheel(notches if change > 0 else -notches)
        finally:
            pyautogui.keyUp("ctrl")

        self.zoom_cooldown = now
        self.last_zoom_ratio = smooth
        return True, direction

    # -- pulizia -----------------------------------------------------------
    def reset(self):
        """Rilascia tutto: chiamata in chiusura, non deve lasciare tasti premuti."""
        self.drag_end()
        try:
            pyautogui.keyUp("ctrl")
        except Exception:
            pass
        self.last_zoom_ratio = None
        self._zoom_window.clear()
        self.reset_cursor_filter()
