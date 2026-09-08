"""
Riconoscimento delle gesture: macchina a stati esplicita.

Il set di gesture e' pensato per essere a falsi positivi quasi nulli. Le regole
che lo rendono affidabile sono cinque, e valgono per ogni gesture:

1. **Normalizzazione sulla dimensione della mano.** Nessuna soglia e' in pixel:
   tutte sono frazioni della distanza polso-nocca. Avvicinare o allontanare la
   mano dalla webcam non cambia il comportamento.

2. **Isteresi (trigger di Schmitt).** Chiudere un pinch richiede di scendere
   sotto `pinch_close_ratio`, riaprirlo richiede di risalire sopra
   `pinch_open_ratio`. Fra le due soglie non succede nulla, quindi non c'e'
   sfarfallio al confine.

3. **Conferma temporale.** Un cambio di stato deve reggere per N frame
   consecutivi. Un singolo frame sbagliato del modello non produce eventi.

4. **Fronte, non livello.** Ogni click e' emesso sulla *transizione*, e va
   riarmato riaprendo la mano. E' il bug che rendeva il click destro un
   generatore continuo di eventi: era legato allo stato del mignolo, quindi
   sparava di continuo finche' il mignolo restava chiuso.

5. **Gating.** Niente gesture se: la mano e' appena stata riagganciata, la mano
   si muove troppo velocemente, la mano e' chiusa, o un altro gesto e' gia'
   attivo (mutua esclusione).

Le gesture, tutte a una mano:

    posa di controllo   indice non ripiegato     -> cursore attivo
    click sinistro      pinch pollice+indice     -> tap breve
    drag                pinch pollice+indice     -> tenuto oltre drag_hold_time
    click destro        pinch pollice+medio      -> tap
    scroll              indice+medio estesi      -> movimento verticale

Sulla posa di controllo, una trappola che e' costata un bug: pinzare **piega**
l'indice. Misurando l'estensione dal polso, l'indice risulta "non esteso"
proprio durante il click, il gate scatta e annulla la gesture — niente click,
niente drag. La misura corretta e' la distanza punta-nocca (`index_extension`),
che separa il pinch dal pugno invece di confonderlo con esso.
"""

import time

from hand_tracker import (
    THUMB_TIP, INDEX_TIP, MIDDLE_TIP, INDEX_MCP,
)

# Eventi emessi dal riconoscitore.
LEFT_CLICK = "left_click"
RIGHT_CLICK = "right_click"
DRAG_START = "drag_start"
DRAG_END = "drag_end"
SCROLL = "scroll"

# Stati del pinch principale.
_IDLE = 0
_PENDING = 1    # pinch chiuso, non sappiamo ancora se click o drag
_DRAGGING = 2


class _Pinch:
    """
    Rilevatore di pinch con isteresi e conferma su piu' frame.

    Espone `closed` (stato stabile) e `just_closed` / `just_opened` (fronti).
    """

    def __init__(self, close_ratio, open_ratio, confirm_frames, release_frames):
        self.close_ratio = close_ratio
        self.open_ratio = open_ratio
        self.confirm_frames = confirm_frames
        self.release_frames = release_frames
        self.closed = False
        self.just_closed = False
        self.just_opened = False
        self._count = 0

    def update(self, ratio):
        self.just_closed = False
        self.just_opened = False

        if self.closed:
            # Per riaprire serve superare la soglia alta, per release_frames volte.
            if ratio > self.open_ratio:
                self._count += 1
                if self._count >= self.release_frames:
                    self.closed = False
                    self.just_opened = True
                    self._count = 0
            else:
                self._count = 0
        else:
            # Per chiudere serve scendere sotto la soglia bassa, per confirm_frames volte.
            if ratio < self.close_ratio:
                self._count += 1
                if self._count >= self.confirm_frames:
                    self.closed = True
                    self.just_closed = True
                    self._count = 0
            else:
                self._count = 0
        return self.closed

    def reset(self):
        self.closed = False
        self.just_closed = False
        self.just_opened = False
        self._count = 0


class GestureRecognizer:
    """
    Traduce una sequenza di HandObservation in eventi di alto livello.

    L'uso e' `events = recognizer.update(hand, cursor_xy, now)`; `events` e' una
    lista di tuple `(nome_evento, payload)`.
    """

    def __init__(self, cfg):
        self.config = cfg

        self.left_pinch = _Pinch(
            cfg.pinch_close_ratio, cfg.pinch_open_ratio,
            cfg.pinch_confirm_frames, cfg.pinch_release_frames,
        )
        self.right_pinch = _Pinch(
            cfg.right_pinch_close_ratio, cfg.right_pinch_open_ratio,
            cfg.pinch_confirm_frames, cfg.pinch_release_frames,
        )

        self.state = _IDLE
        self.pinch_start_time = 0.0
        self.pinch_start_pos = None
        self.max_travel = 0.0

        self.last_click_time = 0.0
        self.last_right_click_time = 0.0
        self.last_scroll_time = 0.0

        self.reacquire_until = 0.0
        self.hand_speed = 0.0

        self._last_cursor = None
        self._last_time = None
        self._scroll_anchor = None
        self._scroll_active = False

        self._prepared_at = None

        # Esposti per la UI di debug.
        self.left_ratio = 9.9
        self.right_ratio = 9.9
        self.index_extension = 0.0
        self.pointing = False
        self.gated_reason = ""

    # ------------------------------------------------------------------
    def _sync_thresholds(self):
        """Riallinea le soglie se sono state cambiate a caldo dalla GUI."""
        cfg = self.config
        self.left_pinch.close_ratio = cfg.pinch_close_ratio
        self.left_pinch.open_ratio = cfg.pinch_open_ratio
        self.left_pinch.confirm_frames = cfg.pinch_confirm_frames
        self.left_pinch.release_frames = cfg.pinch_release_frames
        self.right_pinch.close_ratio = cfg.right_pinch_close_ratio
        self.right_pinch.open_ratio = cfg.right_pinch_open_ratio
        self.right_pinch.confirm_frames = cfg.pinch_confirm_frames
        self.right_pinch.release_frames = cfg.pinch_release_frames

    def hand_lost(self, now=None):
        """
        La mano non e' piu' visibile.

        Se un drag era in corso va chiuso, altrimenti il tasto resterebbe
        premuto per sempre.
        """
        now = now or time.time()
        events = []
        if self.state == _DRAGGING:
            events.append((DRAG_END, None))
        self.state = _IDLE
        self.left_pinch.reset()
        self.right_pinch.reset()
        self._scroll_anchor = None
        self._scroll_active = False
        self._last_cursor = None
        self._last_time = None
        self._prepared_at = None
        self.hand_speed = 0.0
        self.left_ratio = self.right_ratio = 9.9
        self.index_extension = 0.0
        self.pointing = False
        self.reacquire_until = now + self.config.hand_reacquire_grace
        return events

    # ------------------------------------------------------------------
    def prepare(self, hand, now=None):
        """
        Calcola misure e gating per questo fotogramma.

        Va chiamata PRIMA di muovere il cursore, perche' `cursor_frozen()`
        dipende dai rapporti calcolati qui. Nella versione precedente il
        congelamento leggeva i valori del fotogramma precedente e scattava
        quindi con un frame di ritardo, lasciando scivolare il cursore
        all'inizio di ogni pinch.
        """
        now = now if now is not None else time.time()
        cfg = self.config
        self._sync_thresholds()

        self._prepared_at = now
        if hand is None:
            self.left_ratio = self.right_ratio = 9.9
            self.pointing = False
            self.gated_reason = ""
            return

        self.left_ratio = hand.ratio(THUMB_TIP, INDEX_TIP)
        self.right_ratio = hand.ratio(THUMB_TIP, MIDDLE_TIP)
        self.index_extension = hand.index_extension
        # Posa di controllo: l'indice non e' ripiegato sul palmo. Misurata
        # dalla nocca, quindi resta vera anche mentre l'indice si piega per
        # pinzare: e' esattamente il caso che prima annullava il click.
        self.pointing = hand.index_extension >= cfg.index_control_ratio

        if hand.reacquired:
            self.reacquire_until = now + cfg.hand_reacquire_grace

        if now < self.reacquire_until:
            self.gated_reason = "riaggancio"
        elif cfg.require_pointing_pose and not self.pointing:
            self.gated_reason = "mano chiusa"
        else:
            self.gated_reason = ""

    def update(self, hand, cursor_xy, now=None):
        """
        Args:
            hand: HandObservation della mano dominante.
            cursor_xy: posizione del cursore sullo schermo, in pixel.
            now: timestamp; se None usa time.time().

        Returns:
            list[(str, payload)]: eventi da eseguire.
        """
        now = now if now is not None else time.time()
        cfg = self.config
        events = []

        if hand is None:
            return self.hand_lost(now)

        # Idempotente: se il chiamante ha gia' invocato prepare() per questo
        # fotogramma questo non cambia nulla, altrimenti allinea le misure.
        if self._prepared_at != now:
            self.prepare(hand, now)
        self._prepared_at = None

        # -- velocita' della mano, per il gating dei click ------------------
        if self._last_cursor is not None and self._last_time is not None:
            dt = now - self._last_time
            if dt > 1e-4:
                dx = cursor_xy[0] - self._last_cursor[0]
                dy = cursor_xy[1] - self._last_cursor[1]
                inst = (dx * dx + dy * dy) ** 0.5 / dt
                # Media esponenziale: una singola lettura e' troppo rumorosa.
                self.hand_speed = 0.6 * self.hand_speed + 0.4 * inst
        self._last_cursor = cursor_xy
        self._last_time = now

        index_up, middle_up, ring_up, pinky_up = hand.fingers
        gated = self.gated_reason

        if gated:
            # In gating chiudiamo un eventuale drag e azzeriamo i rilevatori,
            # cosi' non si accumula stato che poi esplode in un evento falso.
            if self.state == _DRAGGING:
                events.append((DRAG_END, None))
            self.state = _IDLE
            self.left_pinch.reset()
            self.right_pinch.reset()
            self._scroll_anchor = None
            self._scroll_active = False
            return events

        # -- scroll a due dita ---------------------------------------------
        # Ha priorita' sui pinch, ma richiede che nessun pinch sia in corso:
        # e' una posa (indice+medio estesi, anulare e mignolo chiusi) che non
        # puo' coesistere con un pinch, quindi non c'e' ambiguita'.
        scroll_pose = (
            cfg.enable_scroll and index_up and middle_up
            and not ring_up and not pinky_up and self.state == _IDLE
        )
        if scroll_pose:
            events.extend(self._update_scroll(hand, now))
            self.left_pinch.reset()
            self.right_pinch.reset()
            return events
        self._scroll_anchor = None
        self._scroll_active = False

        # -- pinch --------------------------------------------------------
        left_closed = self.left_pinch.update(self.left_ratio)
        # Mutua esclusione: il pinch destro viene valutato solo se il sinistro
        # e' aperto e nessun drag e' attivo.
        if self.state == _IDLE and not left_closed:
            self.right_pinch.update(self.right_ratio)
        else:
            self.right_pinch.reset()

        events.extend(self._update_left(now))
        events.extend(self._update_right(now))
        return events

    # ------------------------------------------------------------------
    def _update_left(self, now):
        """Click sinistro e drag: stesso pinch, li distingue la durata."""
        cfg = self.config
        events = []
        pinch = self.left_pinch

        if self.state == _IDLE:
            if pinch.just_closed:
                self.state = _PENDING
                self.pinch_start_time = now
                self.pinch_start_pos = self._last_cursor
                self.max_travel = 0.0

        elif self.state == _PENDING:
            # Traccia quanto ha vagato il cursore da quando il pinch e' chiuso:
            # un click "vero" e' quasi immobile.
            if self.pinch_start_pos is not None and self._last_cursor is not None:
                dx = self._last_cursor[0] - self.pinch_start_pos[0]
                dy = self._last_cursor[1] - self.pinch_start_pos[1]
                self.max_travel = max(self.max_travel, (dx * dx + dy * dy) ** 0.5)

            if pinch.just_opened:
                held = now - self.pinch_start_time
                if (held < cfg.drag_hold_time
                        and self.max_travel <= cfg.click_max_travel
                        and self.hand_speed <= cfg.max_gesture_speed
                        and now - self.last_click_time >= cfg.click_cooldown):
                    events.append((LEFT_CLICK, None))
                    self.last_click_time = now
                self.state = _IDLE
            elif cfg.drag_mode_enabled and (now - self.pinch_start_time) >= cfg.drag_hold_time:
                events.append((DRAG_START, None))
                self.state = _DRAGGING

        elif self.state == _DRAGGING:
            if pinch.just_opened:
                events.append((DRAG_END, None))
                self.state = _IDLE

        return events

    def _update_right(self, now):
        """Click destro: emesso sul fronte di apertura, mai sullo stato."""
        cfg = self.config
        events = []
        if not cfg.enable_right_click:
            return events
        if self.right_pinch.just_opened:
            if (self.hand_speed <= cfg.max_gesture_speed
                    and now - self.last_right_click_time >= cfg.right_click_cooldown):
                events.append((RIGHT_CLICK, None))
                self.last_right_click_time = now
        return events

    def _update_scroll(self, hand, now):
        """Scroll proporzionale allo spostamento verticale della posa a due dita."""
        cfg = self.config
        events = []
        # Ancora sulla nocca dell'indice: e' molto piu' stabile della punta.
        _, y = hand.point(INDEX_MCP)

        if self._scroll_anchor is None:
            self._scroll_anchor = y
            self._scroll_active = True
            return events

        delta = self._scroll_anchor - y
        if abs(delta) < cfg.scroll_deadzone:
            return events
        if now - self.last_scroll_time < cfg.scroll_cooldown:
            return events

        amount = delta * cfg.scroll_gain * 100.0
        clicks = int(amount)
        if clicks != 0:
            events.append((SCROLL, clicks))
            self.last_scroll_time = now
            self._scroll_anchor = y
        return events

    # ------------------------------------------------------------------
    @property
    def dragging(self):
        return self.state == _DRAGGING

    def cursor_frozen(self):
        """
        True quando il cursore va tenuto fermo sull'ultima posizione buona.

        Serve perche' il cursore segue la punta dell'indice, che e' anche il
        dito che si muove per fare il pinch: senza questo, ogni click finirebbe
        qualche pixel piu' in basso del bersaglio mirato. Congelando appena il
        pinch inizia a chiudersi il click cade esattamente dove si puntava.

        Durante il drag il cursore deve invece muoversi, quindi li' non si
        congela.
        """
        if self.state == _DRAGGING:
            return False
        if self._scroll_active:
            return True
        cfg = self.config
        if self.state == _PENDING:
            return True
        # Fase di avvicinamento. La soglia e' piu' larga di quella di
        # riapertura del pinch, cosi' il blocco scatta appena le dita iniziano
        # a chiudersi invece che a pinch quasi completato.
        if self.left_ratio < cfg.pinch_freeze_ratio:
            return True
        if cfg.enable_right_click and self.right_ratio < cfg.pinch_freeze_ratio:
            return True
        return False

    def status_text(self):
        """Riga di stato compatta per l'overlay di debug."""
        if self.gated_reason:
            return "BLOCCATO: " + self.gated_reason
        if self.state == _DRAGGING:
            return "DRAG"
        if self.state == _PENDING:
            return "pinch..."
        if self._scroll_active:
            return "SCROLL"
        return "pronto" if self.pointing else "inattivo"
