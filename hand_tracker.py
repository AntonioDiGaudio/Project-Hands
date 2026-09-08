"""
Rilevamento e tracciamento delle mani con MediaPipe.

Differenze principali rispetto alla versione precedente:

* i landmark restano in **float normalizzati** (0..1) invece di essere
  arrotondati a pixel interi: a 640x480 su uno schermo 1920x1080 un pixel di
  camera vale 3 pixel di schermo, arrotondare significa buttare via precisione
  e introdurre jitter;
* l'estensione delle dita e' misurata in modo **invariante alla rotazione**
  (distanza dal polso) invece di confrontare le sole coordinate Y, che si
  rompe non appena si inclina la mano;
* ogni dito ha **isteresi + conferma su piu' frame**, cosi' lo stato non
  sfarfalla al confine della soglia;
* le mani con handedness poco affidabile vengono scartate;
* un salto improvviso della mano viene trattato come riaggancio e non come
  movimento reale.
"""

import math
import os

# Silenzia il logging verboso di MediaPipe/absl prima dell'import.
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import cv2
import mediapipe as mp

import config

# Indici dei landmark MediaPipe usati di frequente.
WRIST = 0
THUMB_TIP = 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_PIP, RING_TIP = 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

_FINGERS = (
    (INDEX_TIP, INDEX_PIP),
    (MIDDLE_TIP, MIDDLE_PIP),
    (RING_TIP, RING_PIP),
    (PINKY_TIP, PINKY_PIP),
)


class HandObservation:
    """Una mano rilevata in un frame, con tutte le misure gia' normalizzate."""

    __slots__ = ("label", "score", "points", "scale", "fingers", "reacquired",
                 "index_extension", "middle_extension")

    def __init__(self, label, score, points, scale, fingers, reacquired,
                 index_extension, middle_extension=1.4):
        self.label = label            # "Right" / "Left"
        self.score = score            # confidenza handedness 0..1
        self.points = points          # lista di (x, y) float normalizzati 0..1
        self.scale = scale            # dimensione della mano, in unita' normalizzate
        self.fingers = fingers        # (indice, medio, anulare, mignolo) 0/1
        self.reacquired = reacquired  # True se la mano e' appena comparsa o e' saltata

        # Quanto e' disteso l'indice, misurato dalla NOCCA e non dal polso.
        #
        # Serve a distinguere tre pose che il conteggio dita da solo confonde:
        #
        #     indice teso      ~1.3 - 1.5
        #     indice che pinza ~0.9 - 1.2   (piegato in punta verso il pollice)
        #     pugno chiuso     ~0.4 - 0.6   (ripiegato sul palmo)
        #
        # La misura basata sul polso non va bene qui: quando pinzi, la punta
        # dell'indice scende verso il pollice e finisce piu' vicina al polso
        # della falange, quindi l'indice risulta "non esteso" proprio mentre
        # stai facendo click. Misurando dalla nocca il pinch resta ben
        # separato dal pugno.
        self.index_extension = index_extension

        # Stessa misura per il medio, e serve per lo stesso motivo.
        #
        # Il click destro e' "pollice + medio uniti", ma la sola distanza fra
        # le due punte non basta a riconoscerlo: nella normale posa di
        # puntamento il medio e' ripiegato nel palmo e il pollice gli si
        # appoggia sopra, quindi quella distanza vale gia' circa 0.35 della
        # mano, cioe' meno della soglia di chiusura. Senza sapere se il medio
        # e' DISTESO, la posa di puntamento e' indistinguibile da un pinch
        # medio: il cursore si congela e al primo movimento parte un click
        # destro non richiesto.
        self.middle_extension = middle_extension

    def point(self, idx):
        return self.points[idx]

    def ratio(self, a, b):
        """Distanza fra due landmark espressa in frazioni di dimensione mano."""
        ax, ay = self.points[a]
        bx, by = self.points[b]
        return math.hypot(ax - bx, ay - by) / self.scale


class _FingerState:
    """Stato con isteresi e conferma temporale di un singolo dito."""

    __slots__ = ("up", "pending", "count")

    def __init__(self):
        self.up = 0
        self.pending = 0
        self.count = 0

    def update(self, raw_up, confirm_frames):
        if raw_up == self.up:
            self.pending = raw_up
            self.count = 0
            return self.up
        if raw_up != self.pending:
            self.pending = raw_up
            self.count = 1
        else:
            self.count += 1
        if self.count >= confirm_frames:
            self.up = raw_up
            self.count = 0
        return self.up

    def reset(self):
        self.up = 0
        self.pending = 0
        self.count = 0


class _HandState:
    """Storia per mano, usata per isteresi e rilevamento dei salti."""

    def __init__(self):
        self.fingers = [_FingerState() for _ in range(4)]
        self.last_wrist = None
        self.missing_frames = 999

    def reset(self):
        for f in self.fingers:
            f.reset()
        self.last_wrist = None


class HandTracker:
    """Wrapper su MediaPipe Hands con post-processing anti falsi positivi."""

    def __init__(self, max_num_hands=None, model_complexity=None,
                 min_detection_confidence=None, min_tracking_confidence=None):
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_styles = mp.solutions.drawing_styles

        self.max_num_hands = max_num_hands if max_num_hands is not None else 1
        self.model_complexity = (
            model_complexity if model_complexity is not None else config.model_complexity
        )
        self.min_detection_confidence = (
            min_detection_confidence if min_detection_confidence is not None
            else config.min_detection_confidence
        )
        self.min_tracking_confidence = (
            min_tracking_confidence if min_tracking_confidence is not None
            else config.min_tracking_confidence
        )

        self._states = {"Right": _HandState(), "Left": _HandState()}
        self._rgb_buffer = None
        self.hands = self._build()

    # -- ciclo di vita -----------------------------------------------------
    def _build(self):
        return self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=self.max_num_hands,
            model_complexity=self.model_complexity,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
        )

    def reconfigure(self, max_num_hands=None, model_complexity=None,
                    min_detection_confidence=None, min_tracking_confidence=None):
        """Ricrea il grafo MediaPipe solo se qualche parametro e' davvero cambiato."""
        new = (
            self.max_num_hands if max_num_hands is None else max_num_hands,
            self.model_complexity if model_complexity is None else model_complexity,
            self.min_detection_confidence if min_detection_confidence is None
            else min_detection_confidence,
            self.min_tracking_confidence if min_tracking_confidence is None
            else min_tracking_confidence,
        )
        current = (
            self.max_num_hands, self.model_complexity,
            self.min_detection_confidence, self.min_tracking_confidence,
        )
        if new == current:
            return False

        (self.max_num_hands, self.model_complexity,
         self.min_detection_confidence, self.min_tracking_confidence) = new
        self.close()
        self.hands = self._build()
        for state in self._states.values():
            state.reset()
        return True

    def close(self):
        try:
            self.hands.close()
        except Exception:
            pass

    # -- inferenza ---------------------------------------------------------
    def process(self, frame_bgr):
        """Esegue il modello su un frame BGR e restituisce i risultati grezzi."""
        h, w = frame_bgr.shape[:2]
        if self._rgb_buffer is None or self._rgb_buffer.shape[:2] != (h, w):
            self._rgb_buffer = frame_bgr.copy()
        # Riusa il buffer: evita una allocazione da circa 1 MB per frame.
        cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB, dst=self._rgb_buffer)
        # read-only permette a MediaPipe di saltare una copia interna.
        self._rgb_buffer.flags.writeable = False
        try:
            return self.hands.process(self._rgb_buffer)
        finally:
            self._rgb_buffer.flags.writeable = True

    def observe(self, results):
        """
        Trasforma i risultati MediaPipe in HandObservation validate.

        Returns:
            dict: {"Right": HandObservation|None, "Left": HandObservation|None}
        """
        out = {"Right": None, "Left": None}
        seen = set()

        if results.multi_hand_landmarks and results.multi_handedness:
            for landmarks, info in zip(results.multi_hand_landmarks,
                                       results.multi_handedness):
                cls = info.classification[0]
                score = cls.score
                if score < config.min_handedness_score:
                    continue
                label = cls.label
                if label not in out:
                    continue
                # Se lo stesso lato viene proposto due volte tiene il piu' confidente.
                prev = out[label]
                if prev is not None and prev.score >= score:
                    continue
                obs = self._build_observation(label, score, landmarks)
                if obs is not None:
                    out[label] = obs
                    seen.add(label)

        # Aggiorna gli stati delle mani sparite.
        for label, state in self._states.items():
            if label in seen:
                state.missing_frames = 0
            else:
                state.missing_frames += 1
                if state.missing_frames == 1:
                    state.reset()

        return out

    def _build_observation(self, label, score, landmarks):
        state = self._states[label]
        pts = [(lm.x, lm.y) for lm in landmarks.landmark]

        wx, wy = pts[WRIST]
        mx, my = pts[MIDDLE_MCP]
        scale = math.hypot(mx - wx, my - wy)
        if scale < 1e-4:
            # Mano degenere: scarta invece di dividere per quasi zero.
            return None

        # Un salto grosso significa che il tracker ha riagganciato un'altra
        # mano (o un falso positivo): meglio inibire le gesture per un attimo.
        reacquired = state.missing_frames > 0
        if state.last_wrist is not None:
            jump = math.hypot(wx - state.last_wrist[0], wy - state.last_wrist[1])
            if jump > config.teleport_reset_ratio:
                reacquired = True
                for f in state.fingers:
                    f.reset()
        state.last_wrist = (wx, wy)

        fingers = self._fingers_up(pts, state)

        ix, iy = pts[INDEX_TIP]
        kx, ky = pts[INDEX_MCP]
        index_extension = math.hypot(ix - kx, iy - ky) / scale

        tx2, ty2 = pts[MIDDLE_TIP]
        middle_extension = math.hypot(tx2 - mx, ty2 - my) / scale

        return HandObservation(label, score, pts, scale, fingers, reacquired,
                               index_extension, middle_extension)

    @staticmethod
    def _fingers_up(pts, state):
        """
        Estensione delle dita invariante alla rotazione.

        Un dito e' esteso quando la punta e' piu' lontana dal polso di quanto lo
        sia la falange intermedia. Confrontando distanze anziche' coordinate Y
        il risultato non cambia se la mano e' inclinata o ruotata.
        """
        wx, wy = pts[WRIST]
        result = []
        for i, (tip, pip) in enumerate(_FINGERS):
            tx, ty = pts[tip]
            px, py = pts[pip]
            d_tip = math.hypot(tx - wx, ty - wy)
            d_pip = math.hypot(px - wx, py - wy)
            fs = state.fingers[i]
            if d_pip < 1e-6:
                raw = 0
            else:
                ratio = d_tip / d_pip
                # Isteresi: serve superare extend per alzarsi, scendere sotto
                # retract per abbassarsi.
                if fs.up:
                    raw = 1 if ratio > config.finger_retract_ratio else 0
                else:
                    raw = 1 if ratio > config.finger_extend_ratio else 0
            result.append(fs.update(raw, config.finger_confirm_frames))
        return tuple(result)

    # -- disegno -----------------------------------------------------------
    def draw(self, frame, results):
        if not results.multi_hand_landmarks:
            return frame
        for landmarks in results.multi_hand_landmarks:
            self.mp_draw.draw_landmarks(
                frame, landmarks, self.mp_hands.HAND_CONNECTIONS,
                self.mp_styles.get_default_hand_landmarks_style(),
                self.mp_styles.get_default_hand_connections_style(),
            )
        return frame
