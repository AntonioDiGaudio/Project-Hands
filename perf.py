"""
Auto-tuning delle prestazioni.

L'idea: non esiste una configurazione buona sia per un desktop moderno sia per
un Raspberry Pi, quindi invece di indovinare i default si misura il tempo reale
di inferenza e si scala la qualita' finche' l'applicazione non sta dentro il
budget di frame.

La scala di degradazione va dal livello 0 (massima qualita') al livello 3
(minimo indispensabile). Si scende in fretta quando si e' in affanno e si
risale con calma, per non oscillare fra due livelli.

Cosa viene sacrificato, in ordine:

    livello 0  tutto attivo
    livello 1  niente landmark disegnati, niente overlay
    livello 2  modello lite forzato
    livello 3  niente finestra di debug, risoluzione ridotta

L'ordine e' stato rifatto sulle misure, perche' quello precedente spendeva i
primi due livelli su cose che non costano niente. Con `cv2.pollKey()` al posto
di `cv2.waitKey(1)`, l'intero `_render` (imshow + overlay + tastiera) costa
0.99 ms mediani contro i 15.7 ms di prima: chiudere la finestra di debug non e'
piu' un risparmio. Il modello si': complessita' 1 contro 0 vale 2.3 ms
misurati, cioe' l'unica leva vera. Quindi il modello viene prima della
finestra, non dopo.

**Il governor non spegne funzioni, solo qualita' visiva.** Prima al livello 2
disattivava `enable_zoom`: l'utente perdeva lo zoom senza nessuna indicazione
del perche', e la cosa si mangiava anche `max_num_hands`, che in `app` segue
proprio `enable_zoom` — i due si rincorrevano ricostruendo il grafo MediaPipe.
Ridurre la qualita' e' legittimo, togliere una gesture no.

Nota importante emersa dai benchmark: **ridurre la risoluzione della camera non
accelera l'inferenza** (MediaPipe ridimensiona comunque a 192x192 al suo
interno). Serve solo a ridurre il costo di decodifica e di `cvtColor`, che su un
Raspberry Pi non e' trascurabile ma non e' il collo di bottiglia. Per questo la
risoluzione e' l'ultima cosa che viene toccata.
"""

import time

import config

MAX_LEVEL = 3

_LEVEL_NAMES = {
    0: "massima",
    1: "alta",
    2: "ridotta",
    3: "minima",
}


class PerformanceGovernor:
    """Misura il carico e degrada o ripristina la qualita' di conseguenza."""

    def __init__(self, cfg=config):
        self.config = cfg
        self.level = 0
        self.fps = 0.0
        self.inference_ms = 0.0

        self._last_change = 0.0
        self._over_budget_since = None
        self._under_budget_since = None

        # Valori scelti dall'utente, per poterli ripristinare quando si risale.
        self._user_prefs = None

    # ------------------------------------------------------------------
    def note_frame(self, dt):
        """Registra la durata di un giro di loop."""
        if dt <= 0.0:
            return
        inst = 1.0 / dt
        # Media esponenziale: la lettura istantanea e' troppo rumorosa per
        # pilotare delle decisioni.
        self.fps = inst if self.fps == 0.0 else 0.9 * self.fps + 0.1 * inst

    def note_inference(self, seconds):
        ms = seconds * 1000.0
        self.inference_ms = ms if self.inference_ms == 0.0 else \
            0.85 * self.inference_ms + 0.15 * ms

    def level_name(self):
        return _LEVEL_NAMES.get(self.level, str(self.level))

    # ------------------------------------------------------------------
    def _capture_prefs(self):
        if self._user_prefs is None:
            cfg = self.config
            self._user_prefs = {
                "draw_landmarks": cfg.draw_landmarks,
                "show_debug_window": cfg.show_debug_window,
                "overlay_enabled": cfg.overlay_enabled,
                "model_complexity": cfg.model_complexity,
                "camera_width": cfg.camera_width,
                "camera_height": cfg.camera_height,
            }

    def tick(self, hand_tracker=None, now=None):
        """
        Da chiamare una volta per frame.

        Confronta il tempo di inferenza con il budget e decide se cambiare
        livello di qualita'.
        """
        cfg = self.config
        if not cfg.auto_performance:
            if self.level != 0:
                self._restore(hand_tracker)
            return

        now = now if now is not None else time.time()
        if self.inference_ms <= 0.0:
            return

        # Non reagire prima di aver raccolto abbastanza campioni.
        if now - self._last_change < 2.5:
            return

        budget_ms = 1000.0 / max(1.0, float(cfg.perf_min_detect_fps))
        headroom = budget_ms * cfg.perf_target_headroom

        if self.inference_ms > budget_ms:
            if self._over_budget_since is None:
                self._over_budget_since = now
            self._under_budget_since = None
            if now - self._over_budget_since > 2.0 and self.level < MAX_LEVEL:
                self._degrade(hand_tracker)
                self._last_change = now
                self._over_budget_since = None
        elif self.inference_ms < headroom * 0.6:
            if self._under_budget_since is None:
                self._under_budget_since = now
            self._over_budget_since = None
            # Si risale solo dopo un periodo lungo di calma: risalire in fretta
            # significa oscillare avanti e indietro fra due livelli.
            if now - self._under_budget_since > 8.0 and self.level > 0:
                self._upgrade(hand_tracker)
                self._last_change = now
                self._under_budget_since = None
        else:
            self._over_budget_since = None
            self._under_budget_since = None

    # ------------------------------------------------------------------
    def _degrade(self, hand_tracker):
        cfg = self.config
        self._capture_prefs()
        self.level += 1
        print("[perf] inferenza %.1f ms: scendo a qualita' '%s'"
              % (self.inference_ms, self.level_name()))

        if self.level >= 1:
            cfg.draw_landmarks = False
            cfg.overlay_enabled = False
        if self.level >= 2:
            # La leva vera: 2.3 ms misurati. Viene prima della finestra.
            cfg.model_complexity = 0
            if hand_tracker is not None:
                hand_tracker.reconfigure(model_complexity=0)
        if self.level >= 3:
            cfg.show_debug_window = False
            cfg.camera_width, cfg.camera_height = 424, 240

    def _upgrade(self, hand_tracker):
        cfg = self.config
        prefs = self._user_prefs or {}
        self.level -= 1
        print("[perf] margine disponibile: risalgo a qualita' '%s'" % self.level_name())

        if self.level < 3:
            cfg.show_debug_window = prefs.get("show_debug_window", True)
            cfg.camera_width = prefs.get("camera_width", cfg.camera_width)
            cfg.camera_height = prefs.get("camera_height", cfg.camera_height)
        if self.level < 2:
            cfg.model_complexity = prefs.get("model_complexity", cfg.model_complexity)
            if hand_tracker is not None:
                hand_tracker.reconfigure(model_complexity=cfg.model_complexity)
        if self.level < 1:
            cfg.draw_landmarks = prefs.get("draw_landmarks", True)
            cfg.overlay_enabled = prefs.get("overlay_enabled", True)

    def _restore(self, hand_tracker):
        """Torna alle preferenze dell'utente (auto_performance disattivato)."""
        cfg = self.config
        for key, value in (self._user_prefs or {}).items():
            setattr(cfg, key, value)
        if hand_tracker is not None:
            hand_tracker.reconfigure(model_complexity=cfg.model_complexity)
        self.level = 0
