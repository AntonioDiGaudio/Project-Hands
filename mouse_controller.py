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
* i tasti si premono con `mouse_event` diretto e non con `pyautogui.click()`.
  Quella funzione, prima di premere, chiama `moveTo` sulla posizione corrente:
  un `SetCursorPos` in piu' fra la mira e la pressione, cioe' l'unico punto in
  cui il cursore poteva ancora spostarsi. Qui down e up partono senza niente in
  mezzo, e il secondo click di un doppio puo' essere inchiodato sul pixel
  esatto del primo;
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
    import ctypes.wintypes

    _user32 = ctypes.windll.user32
    _MOUSEEVENTF_WHEEL = 0x0800
    _MOUSEEVENTF_LEFTDOWN = 0x0002
    _MOUSEEVENTF_LEFTUP = 0x0004
    _MOUSEEVENTF_RIGHTDOWN = 0x0008
    _MOUSEEVENTF_RIGHTUP = 0x0010
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

    def _button(flags):
        _user32.mouse_event(flags, 0, 0, 0, None)

    def _left_down():
        _button(_MOUSEEVENTF_LEFTDOWN)

    def _left_up():
        _button(_MOUSEEVENTF_LEFTUP)

    def _right_click():
        _button(_MOUSEEVENTF_RIGHTDOWN)
        _button(_MOUSEEVENTF_RIGHTUP)

    def _cursor_pixel():
        point = ctypes.wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)

    def system_double_click_time():
        """Intervallo massimo fra due click perche' Windows li accoppi."""
        try:
            return max(0.05, _user32.GetDoubleClickTime() / 1000.0)
        except Exception:
            return 0.5
else:
    def _set_cursor(x, y):
        pyautogui.moveTo(int(x), int(y), _pause=False)

    def _wheel(notches):
        # Su X11 e macOS pyautogui parla gia' in scatti.
        pyautogui.scroll(int(notches))

    def _left_down():
        pyautogui.mouseDown()

    def _left_up():
        pyautogui.mouseUp()

    def _right_click():
        pyautogui.click(button="right")

    def _cursor_pixel():
        pos = pyautogui.position()
        return (int(pos[0]), int(pos[1]))

    def system_double_click_time():
        # macOS e le varie X11 hanno ognuno la propria impostazione e nessuna
        # API portabile: 0.5 s e' il valore di fabbrica ovunque.
        return 0.5


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
        self.last_pixel = None        # stessa cosa, in pixel interi gia' limitati
        self.last_click_pixel = None  # dove e' caduto l'ultimo click
        self.target_pos = None        # ultima posizione filtrata (anche se congelata)
        self._was_frozen = False
        self._offset = (0.0, 0.0)     # scarto lasciato da un congelamento
        self._last_update = None
        self.drag_active = False
        self.last_zoom_ratio = None
        self.zoom_cooldown = 0.0
        self._zoom_window = []
        self._zoom_seen = 0.0
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

        dt = 0.0 if self._last_update is None else max(0.0, now - self._last_update)
        self._last_update = now

        if frozen:
            # Il filtro continua ad aggiornarsi (cosi' non c'e' uno scatto alla
            # ripresa) ma il cursore resta dove sta.
            self._was_frozen = True
            return self.last_pos if self.last_pos is not None else (fx, fy)

        # Fine del congelamento. Il cursore era fermo, la mano no: la posizione
        # vera adesso e' altrove, e applicarla di colpo fa SALTARE il cursore.
        #
        # Lo scarto diventa un OFFSET della mappatura, che si riassorbe da solo
        # col tempo ma NON mentre un tasto e' premuto. Prima era
        # un'animazione a tempo fisso, e all'inizio di un drag faceva scivolare
        # il cursore di un centinaio di pixel a tasto gia' premuto, portandosi
        # dietro quello che avevi appena afferrato. Congelando l'offset durante
        # il trascinamento, la presa resta dove l'hai fatta e la mano continua a
        # comandare uno a uno.
        if self._was_frozen:
            self._was_frozen = False
            if self.last_pos is not None:
                self._offset = self._clamp_offset(self.last_pos[0] - fx,
                                                  self.last_pos[1] - fy)

        ox, oy = self._offset
        if (ox or oy) and not self.drag_active and dt > 0.0:
            if abs(ox) < 0.5 and abs(oy) < 0.5:
                ox = oy = 0.0
            else:
                # Decadimento esponenziale: indipendente dal frame rate, e non
                # ha un istante di fine da mancare se il ciclo salta un colpo.
                k = math.exp(-dt / max(1e-3, float(cfg.cursor_settle_time)))
                ox *= k
                oy *= k
            self._offset = (ox, oy)
        fx += ox
        fy += oy

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
        self.last_pixel = (ix, iy)
        return self.last_pos

    def _clamp_offset(self, dx, dy):
        """Tiene l'offset entro un quarto di schermo: oltre non e' piu' un rientro."""
        limit = 0.25 * (self.screen_w * self.screen_w
                        + self.screen_h * self.screen_h) ** 0.5
        span = (dx * dx + dy * dy) ** 0.5
        if span > limit:
            k = limit / span
            dx *= k
            dy *= k
        return (dx, dy)

    def reset_cursor_filter(self):
        self.filter_x.reset()
        self.filter_y.reset()
        self._was_frozen = False
        self._offset = (0.0, 0.0)
        self._last_update = None

    # -- eventi ------------------------------------------------------------
    def left_click(self, same_spot=False):
        """
        Click sinistro.

        `same_spot` rimette il cursore ESATTAMENTE dove e' caduto il click
        precedente prima di premere, ed e' quello che rende possibile il doppio
        click: Windows accoppia due click solo se cadono a pochi pixel l'uno
        dall'altro (SM_CXDOUBLECLK, di fabbrica 4). Un cursore guidato dalla
        mano non ci arriva per caso — nemmeno con il congelamento, che lavora
        sulla posizione filtrata e non sul pixel finale.
        """
        if same_spot and self.last_click_pixel is not None:
            _set_cursor(*self.last_click_pixel)
        else:
            self.last_click_pixel = self.last_pixel or _cursor_pixel()
        _left_down()
        _left_up()

    def right_click(self):
        _right_click()

    def drag_start(self):
        if not self.drag_active:
            _left_down()
            self.drag_active = True

    def drag_end(self):
        if self.drag_active:
            _left_up()
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
            # Il riferimento non si butta al primo fotogramma senza posa.
            # Con due mani in campo il modello ne perde una di continuo
            # (misurato: due mani viste nel 65% dei fotogrammi), e ripartire da
            # capo a ogni buco significa non raggiungere mai la variazione
            # richiesta: lo zoom non parte e niente dice perche'.
            if (self.last_zoom_ratio is not None
                    and now - self._zoom_seen > cfg.zoom_lost_grace):
                self.last_zoom_ratio = None
                self._zoom_window.clear()
            return False, None

        self._zoom_seen = now
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
        self._zoom_seen = 0.0
        self.reset_cursor_filter()
