"""
Loop principale di AirMouse.

Struttura: un thread cattura i frame, il thread principale esegue il modello e
applica le gesture. Fra i due c'e' una casella da un elemento, quindi se il
modello e' piu' lento della camera i frame in eccesso vengono scartati invece di
accumularsi in coda (che e' quello che faceva sembrare il cursore in ritardo).

Due misure hanno guidato la struttura del loop.

**Il costo scala con le mani effettivamente rilevate, non con il tetto
impostato.** Con nessuna mano inquadrata, `max_num_hands` a 1 o a 2 costa
uguale (misurato: 22.7 contro 22.0 ms). Il tracciamento adattivo evita quindi
di far girare il modello dei landmark su una seconda mano che e' inquadrata ma
non serve, non dimezza il costo in assoluto.

**Senza mani il modello costa comunque circa 22 ms per fotogramma**, perche' il
rilevatore di palmo cerca a vuoto su tutta l'immagine; quando una mano e'
agganciata quel passaggio viene saltato. Siccome l'applicazione sta senza mani
per la maggior parte del tempo, abbassare il ritmo in quella fase e' il
risparmio piu' grosso disponibile: misurato, la CPU a riposo passa da circa il
72% di un core al 17%.
"""

import threading
import time

import cv2

import config
from gesture_recognizer import (
    GestureRecognizer, LEFT_CLICK, RIGHT_CLICK, DRAG_START, DRAG_END, SCROLL,
)
from hand_tracker import HandTracker, INDEX_TIP
from mouse_controller import MouseController
from perf import PerformanceGovernor
from settings_gui import create_settings_gui
from shared_state import get_running, set_running
from webcam_manager import WebcamManager

WINDOW_NAME = "AirMouse"

# `cv2.waitKey(1)` non costa 1 ms: su Windows entra nel ciclo di messaggi Win32
# e si allinea alla risoluzione del timer di sistema, che di default e' 15.6 ms.
# Misurato su questa macchina: imshow + waitKey(1) = 15.7 ms per fotogramma,
# imshow + pollKey() = 0.37 ms. Il modello ne costa 14: la finestra di debug
# costava piu' del riconoscimento, e quei 15 ms erano latenza pura sul cursore.
_POLL_KEY = getattr(cv2, "pollKey", None)


def _pump_window():
    """Svuota la coda eventi della finestra e restituisce il tasto premuto."""
    if _POLL_KEY is not None:
        return _POLL_KEY() & 0xFF
    return cv2.waitKey(1) & 0xFF


class AirMouseApp:
    """Applicazione AirMouse."""

    def __init__(self):
        self.webcam_manager = WebcamManager()
        self.hand_tracker = None
        self.mouse_controller = MouseController(config)
        self.gestures = GestureRecognizer(config)
        self.perf = PerformanceGovernor(config)

        self.grabber = None
        self.window_open = False

        # Stato del tracciamento adattivo delle mani.
        self.tracking_two_hands = False
        self._last_two_hand_probe = 0.0
        self._last_second_hand_seen = 0.0

        self._applied = self._config_snapshot()
        self._slide_cooldown = 0.0

        # Throttling in idle.
        self._last_hand_seen = 0.0
        self._last_inference = 0.0
        self._idle = False
        self._last_results = None
        self._last_hands = {"Right": None, "Left": None}
        self._hand_streak = 0
        self._missing_frames = 0

    # ------------------------------------------------------------------
    @staticmethod
    def _config_snapshot():
        """Parametri che, se cambiano, richiedono di ricostruire qualcosa."""
        return {
            "resolution": (config.camera_width, config.camera_height),
            "model": (config.model_complexity,
                      config.min_detection_confidence,
                      config.min_tracking_confidence),
        }

    def initialize(self):
        """Seleziona la webcam, avvia la GUI impostazioni e apre la camera."""
        try:
            selected = self.webcam_manager.select_camera_gui()
            if selected is None or not get_running():
                return False

            gui_thread = threading.Thread(target=create_settings_gui, daemon=True,
                                          name="settings-gui")
            gui_thread.start()

            self.grabber = self.webcam_manager.open_camera(selected)
            self.hand_tracker = HandTracker(
                max_num_hands=1,
                model_complexity=config.model_complexity,
                min_detection_confidence=config.min_detection_confidence,
                min_tracking_confidence=config.min_tracking_confidence,
            )
            self._applied = self._config_snapshot()
            print("Webcam aperta a %dx%d" % self.webcam_manager.actual_resolution())
            return True
        except SystemExit:
            return False
        except Exception as exc:
            print("Errore durante l'inizializzazione: %s" % exc)
            return False

    # ------------------------------------------------------------------
    def run(self):
        if self.grabber is None or self.hand_tracker is None:
            print("Applicazione non inizializzata")
            return

        last_loop = time.perf_counter()

        while get_running():
            ok, frame, _ = self.grabber.read(timeout=0.5)
            if not ok:
                continue

            now = time.perf_counter()
            self.perf.note_frame(now - last_loop)
            last_loop = now

            self._apply_config_changes()

            frame = cv2.flip(frame, 1)

            inferred = self._should_infer(now)
            if inferred:
                t0 = time.perf_counter()
                results = self.hand_tracker.process(frame)
                self.perf.note_inference(time.perf_counter() - t0)
                self._last_inference = now
                self._last_results = results

                hands = self.hand_tracker.observe(results)
                self._last_hands = hands
                if any(h is not None for h in hands.values()):
                    self._last_hand_seen = now

                self._handle_hands(hands, now)
                self._update_hand_count(hands, now)
            else:
                # Fotogramma saltato in modalita' risparmio: nessuna gesture
                # viene valutata, quindi non puo' nascerne un evento spurio.
                results = None
                hands = self._last_hands

            if config.show_debug_window:
                if not self._render(frame, results, hands):
                    break
            elif self.window_open:
                self._close_window()

            self.perf.tick(self.hand_tracker)

            # Tetto sugli fps: senza, su una macchina veloce il loop girerebbe
            # a vuoto bruciando CPU per nulla.
            budget = 1.0 / max(1.0, float(config.target_fps))
            elapsed = time.perf_counter() - now
            if elapsed < budget:
                time.sleep(budget - elapsed)

    # ------------------------------------------------------------------
    def _should_infer(self, now):
        """
        Decide se eseguire il modello su questo fotogramma.

        Si salta solo quando non si vede una mano da un po'. In quella fase il
        modello sta spendendo circa 22 ms per fotogramma per cercare un palmo
        che non c'e', e abbassare il ritmo a `idle_detect_fps` riduce la CPU a
        riposo di circa quattro volte. Appena una mano compare si torna subito
        a pieno ritmo: il ritardo massimo di aggancio e' un intervallo di idle.
        """
        if not config.idle_throttle:
            self._idle = False
            return True

        idle = (now - self._last_hand_seen) > config.idle_after_seconds
        if idle != self._idle:
            self._idle = idle
        if not idle:
            return True

        interval = 1.0 / max(1.0, float(config.idle_detect_fps))
        return (now - self._last_inference) >= interval

    def _handle_hands(self, hands, now):
        """Applica le gesture della mano dominante e, se attivo, lo zoom."""
        dominant_label = config.preferred_hand if config.preferred_hand in hands else "Right"
        hand = hands.get(dominant_label)
        other = hands.get("Left" if dominant_label == "Right" else "Right")

        if hand is None:
            # Il modello perde l'aggancio per un fotogramma isolato di
            # continuo. Dichiarare subito la mano persa azzerava la macchina a
            # stati, apriva 0.25 s di grazia e rilasciava un eventuale drag: il
            # cursore singhiozzava e i trascinamenti si spezzavano a meta'.
            # Qui un buco breve viene semplicemente ignorato.
            self._missing_frames += 1
            if self._missing_frames > config.hand_lost_frames:
                self._hand_streak = 0
                for name, payload in self.gestures.hand_lost(now):
                    self._dispatch(name, payload)
                self.mouse_controller.reset_cursor_filter()
        else:
            self._missing_frames = 0
            self._hand_streak += 1
            nx, ny = hand.point(INDEX_TIP)
            # prepare() per primo: calcola i rapporti di pinch su QUESTO
            # fotogramma, cosi' il congelamento del cursore scatta subito e non
            # con un fotogramma di ritardo.
            self.gestures.prepare(hand, now)
            # Una rilevazione isolata di un solo fotogramma e' quasi sempre un
            # falso positivo del modello. Muovere il cursore su quel dato lo
            # farebbe teletrasportare: si aspetta che l'aggancio sia confermato.
            engaging = self._hand_streak < config.cursor_engage_frames
            frozen = engaging or self.gestures.cursor_frozen()
            pos = self.mouse_controller.update_cursor(nx, ny, now, frozen=frozen)
            for name, payload in self.gestures.update(hand, pos, now):
                self._dispatch(name, payload)

        self._handle_zoom(hand, other, now)
        self._handle_slide(other, now)

    def _dispatch(self, name, payload):
        mc = self.mouse_controller
        if name == LEFT_CLICK:
            mc.left_click()
        elif name == RIGHT_CLICK:
            mc.right_click()
        elif name == DRAG_START:
            mc.drag_start()
        elif name == DRAG_END:
            mc.drag_end()
        elif name == SCROLL:
            mc.scroll(payload)

    def _handle_zoom(self, hand, other, now):
        if not config.enable_zoom or hand is None or other is None:
            self.mouse_controller.handle_zoom(0.0, False, now)
            return
        # Lo zoom richiede una posa esplicita: solo gli indici estesi su
        # entrambe le mani. Cosi' non parte mentre si usa il mouse normalmente.
        active = bool(hand.fingers[0] and other.fingers[0]
                      and not hand.fingers[1] and not other.fingers[1])
        if not active:
            self.mouse_controller.handle_zoom(0.0, False, now)
            return

        ax, ay = hand.point(INDEX_TIP)
        bx, by = other.point(INDEX_TIP)
        # Normalizzato sulla media delle due dimensioni di mano.
        scale = (hand.scale + other.scale) * 0.5
        ratio = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 / max(scale, 1e-6)
        self.mouse_controller.handle_zoom(ratio, True, now)

    def _handle_slide(self, other, now):
        if not config.enable_slide or other is None:
            return
        # Pugno chiuso della mano non dominante vicino a un bordo.
        if any(other.fingers):
            return
        if now - self._slide_cooldown < config.slide_cooldown_time:
            return
        px, py = other.point(0)
        margin = config.slide_margin
        direction = None
        if py < margin:
            direction = "up"
        elif py > 1.0 - margin:
            direction = "down"
        elif px < margin:
            direction = "left"
        elif px > 1.0 - margin:
            direction = "right"
        if direction:
            self.mouse_controller.perform_slide(direction)
            self._slide_cooldown = now

    # ------------------------------------------------------------------
    def _update_hand_count(self, hands, now):
        """
        Tiene il tetto di mani allineato alle funzioni attive.

        Qui c'era un sondaggio periodico che alternava fra 1 e 2 mani per
        scoprire se ce ne fosse una seconda. E' stato tolto: `reconfigure`
        ricostruisce il grafo MediaPipe, misurato circa 25 ms, e soprattutto
        azzera lo stato di tracciamento, quindi produceva uno scatto visibile
        del cursore a ogni sondaggio. Costava piu' di quanto rendesse.

        Non serve nemmeno: il costo del modello scala con le mani
        effettivamente rilevate, non con il tetto impostato (misurato: senza
        mani inquadrate, 1 e 2 mani costano uguale). Basta quindi impostare il
        tetto una volta e lasciarlo stare.
        """
        target = 2 if config.enable_zoom else 1
        if self.hand_tracker.max_num_hands != target:
            self.hand_tracker.reconfigure(max_num_hands=target)
            self.tracking_two_hands = target == 2

    # ------------------------------------------------------------------
    def _apply_config_changes(self):
        """Recepisce le modifiche fatte a caldo dalla GUI impostazioni."""
        snapshot = self._config_snapshot()
        if snapshot["resolution"] != self._applied["resolution"]:
            try:
                self.grabber = self.webcam_manager.open_camera()
            except Exception as exc:
                print("Errore riapertura camera: %s" % exc)
            self._applied["resolution"] = snapshot["resolution"]

        if snapshot["model"] != self._applied["model"]:
            complexity, det, track = snapshot["model"]
            self.hand_tracker.reconfigure(
                model_complexity=complexity,
                min_detection_confidence=det,
                min_tracking_confidence=track,
            )
            self._applied["model"] = snapshot["model"]

    # ------------------------------------------------------------------
    def _render(self, frame, results, hands):
        """
        Disegna la finestra di debug. Restituisce False per uscire.

        `results` e' None sui fotogrammi in cui l'inferenza e' stata saltata:
        li' non si disegna nulla, perche' ridisegnare i landmark del fotogramma
        precedente mostrerebbe una mano ferma dove non c'e' piu'.
        """
        if config.draw_landmarks and results is not None:
            self.hand_tracker.draw(frame, results)
        if config.overlay_enabled:
            self._draw_overlay(frame, hands)

        cv2.imshow(WINDOW_NAME, frame)
        self.window_open = True

        key = _pump_window()
        if key == 27:  # ESC
            set_running(False)
            return False
        if key in (ord("d"), ord("D")):
            config.draw_landmarks = not config.draw_landmarks
        elif key in (ord("o"), ord("O")):
            config.overlay_enabled = not config.overlay_enabled
        elif key in (ord("h"), ord("H")):
            config.show_debug_window = False
        return True

    def _draw_overlay(self, frame, hands):
        """
        Overlay leggero.

        Niente `frame.copy()` + `addWeighted` a piena risoluzione come prima:
        quello costava una copia e una fusione dell'intero frame a ogni
        fotogramma. Qui si fonde solo il rettangolo del pannello.
        """
        g = self.gestures
        lines = [
            "%s  |  %.0f fps  |  %.1f ms modello" % (
                g.status_text(), self.perf.fps, self.perf.inference_ms),
            "pinch sx %.2f (soglia %.2f)%s" % (
                g.left_ratio, config.pinch_close_ratio,
                "" if g.left_pinch.armed else "  DISARMATO"),
            "pinch dx %.2f (soglia %.2f)%s" % (
                g.right_ratio, config.right_pinch_close_ratio,
                "" if g.middle_pointing else "  medio chiuso"),
            "indice %.2f  medio %.2f  (soglie %.2f / %.2f)" % (
                g.index_extension, g.middle_extension,
                config.index_control_ratio, config.middle_control_ratio),
            "cursore: %s" % ("BLOCCATO" if g.frozen else "libero"),
            "velocita' %.0f px/s (max %.0f)" % (g.hand_speed, config.max_gesture_speed),
            "mani tracciate: %d%s" % (
                self.hand_tracker.max_num_hands,
                "  [IDLE]" if self._idle else ""),
            "qualita': %s" % self.perf.level_name(),
            "ESC esci | D landmark | O overlay | H nascondi",
        ]
        hand = hands.get(config.preferred_hand) or hands.get("Right")
        if hand is not None:
            lines.insert(1, "dita %s  conf %.2f" % (
                "".join("^" if f else "_" for f in hand.fingers), hand.score))

        pad = 8
        line_h = 18
        w = min(400, frame.shape[1] - 20)
        h = min(pad * 2 + line_h * len(lines), frame.shape[0] - 20)

        panel = frame[10:10 + h, 10:10 + w]
        if panel.size:
            # Scurisce solo la porzione del pannello. La versione precedente
            # copiava l'intero frame e ci applicava addWeighted sopra: 0.34 ms
            # per fotogramma contro 0.02 ms di questa.
            cv2.addWeighted(panel, 0.25, panel, 0.0, 0.0, dst=panel)

        colour = (90, 220, 90) if not g.gated_reason else (90, 170, 240)
        for i, text in enumerate(lines):
            y = 10 + pad + 12 + i * line_h
            if y > frame.shape[0] - 4:
                break
            cv2.putText(frame, text, (10 + pad, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.42, colour if i == 0 else (230, 230, 230), 1,
                        cv2.LINE_AA)

    def _close_window(self):
        try:
            cv2.destroyWindow(WINDOW_NAME)
        except Exception:
            pass
        self.window_open = False

    # ------------------------------------------------------------------
    def terminate(self):
        """Rilascia tutto. Non deve lasciare tasti del mouse premuti."""
        try:
            self.mouse_controller.reset()
        except Exception:
            pass
        try:
            self.webcam_manager.release_camera()
        except Exception:
            pass
        if self.hand_tracker is not None:
            self.hand_tracker.close()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        set_running(False)


def main():
    app = AirMouseApp()
    if not app.initialize():
        print("Impossibile inizializzare l'applicazione")
        return
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.terminate()


if __name__ == "__main__":
    main()
