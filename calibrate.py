"""
Calibrazione guidata: misura le soglie sulla tua mano invece di indovinarle.

    python calibrate.py

Il motivo per cui esiste: le soglie delle gesture dipendono dalla forma della
mano e da come la tieni davanti alla webcam. Valori scelti a tavolino possono
sembrare corretti e non esserlo.

Come funziona: premi SPAZIO una volta sola e il programma ti guida attraverso
tre pose, con un conto alla rovescia per ciascuna, registrando da solo.

Nota sul perche' non si tiene premuto un tasto: la prima versione chiedeva di
tenere premuto 1/2/3 mentre `cv2.waitKey` faceva polling. Non funziona. La
ripetizione dei tasti ha mezzo secondo di ritardo iniziale, dipende dal backend
grafico e pretende che la finestra abbia il focus: il contatore dei campioni
restava a zero. Qui l'unica interazione e' un tasto premuto una volta.
"""

import sys
import time

import cv2

import config
from hand_tracker import HandTracker, INDEX_TIP, THUMB_TIP, MIDDLE_TIP
from webcam_manager import WebcamManager

WINDOW = "AirMouse - calibrazione"

# (chiave, istruzione mostrata a schermo)
SEQUENCE = [
    ("pointing", "INDICE PUNTATO", "indice ben teso, pollice staccato"),
    ("pinching", "POLLICE + INDICE UNITI", "il gesto del click, tienilo fermo"),
    ("fist", "PUGNO CHIUSO", "tutte le dita ripiegate sul palmo"),
]

COUNTDOWN = 2.5   # secondi di preparazione prima di ogni posa
CAPTURE = 2.5     # secondi di registrazione
MIN_SAMPLES = 12  # sotto questa soglia la posa non e' utilizzabile

# Stati della procedura.
IDLE, COUNTING, CAPTURING, DONE = "idle", "counting", "capturing", "done"


class Samples:
    """Raccoglie le misure di una posa."""

    def __init__(self):
        self.extension = []
        self.pinch = []
        self.middle_pinch = []

    def add(self, hand):
        self.extension.append(hand.index_extension)
        self.pinch.append(hand.ratio(THUMB_TIP, INDEX_TIP))
        self.middle_pinch.append(hand.ratio(THUMB_TIP, MIDDLE_TIP))

    def __len__(self):
        return len(self.extension)

    @staticmethod
    def span(values):
        """(5° percentile, mediana, 95° percentile)."""
        if not values:
            return (0.0, 0.0, 0.0)
        ordered = sorted(values)
        n = len(ordered)
        return (ordered[int(n * 0.05)], ordered[n // 2],
                ordered[min(n - 1, int(n * 0.95))])


def compute(samples):
    """
    Ricava le soglie dalle pose registrate.

    `index_control_ratio` va nel mezzo fra il pinch (che deve passare) e il
    pugno (che deve essere fermato): li' la separazione fra le due pose e' piu'
    ampia possibile, quindi la soglia tollera meglio il rumore.
    """
    out = {}
    pointing = samples.get("pointing")
    pinching = samples.get("pinching")
    fist = samples.get("fist")

    enough = lambda s: s is not None and len(s) >= MIN_SAMPLES

    if enough(pinching) and enough(fist):
        pinch_low = Samples.span(pinching.extension)[0]
        fist_high = Samples.span(fist.extension)[2]
        if pinch_low > fist_high:
            out["index_control_ratio"] = round((pinch_low + fist_high) / 2, 2)
            out["_margin"] = round(pinch_low - fist_high, 2)
        else:
            out["_overlap"] = (round(fist_high, 2), round(pinch_low, 2))

    if enough(pointing) and enough(pinching):
        open_low = Samples.span(pointing.pinch)[0]
        pinch_high = Samples.span(pinching.pinch)[2]
        if open_low > pinch_high:
            gap = open_low - pinch_high
            out["pinch_close_ratio"] = round(pinch_high + gap * 0.25, 2)
            out["pinch_open_ratio"] = round(pinch_high + gap * 0.60, 2)
            out["right_pinch_close_ratio"] = out["pinch_close_ratio"]
            out["right_pinch_open_ratio"] = out["pinch_open_ratio"]
            # Il congelamento sta appena SOTTO la mano aperta piu' stretta: le
            # dita rilassate lasciano il cursore libero, ma appena iniziano ad
            # avvicinarsi il cursore si inchioda.
            out["pinch_freeze_ratio"] = round(open_low - gap * 0.20, 2)
        else:
            out["_pinch_overlap"] = (round(pinch_high, 2), round(open_low, 2))

    # Le soglie devono restare in ordine, altrimenti l'isteresi si inverte e le
    # gesture sfarfallano. Meglio accorgersene qui che in uso.
    close = out.get("pinch_close_ratio")
    if close is not None:
        open_ = out["pinch_open_ratio"]
        freeze = out["pinch_freeze_ratio"]
        if not (close < open_ < freeze):
            out["_bad_order"] = (close, open_, freeze)
            for key in ("pinch_close_ratio", "pinch_open_ratio",
                        "pinch_freeze_ratio", "right_pinch_close_ratio",
                        "right_pinch_open_ratio"):
                out.pop(key, None)
    return out


class Calibration:
    """
    Procedura guidata, separata dal disegno per poter essere testata da sola.

    `tick()` fa avanzare la macchina a stati; non tocca ne' OpenCV ne' la
    webcam, quindi il flusso si verifica senza finestra.
    """

    def __init__(self):
        self.samples = {}
        self.state = IDLE
        self.step = 0
        self.phase_start = 0.0
        self.result = {}
        self.message = "Premi SPAZIO per iniziare"

    @property
    def pose(self):
        if 0 <= self.step < len(SEQUENCE):
            return SEQUENCE[self.step]
        return None

    def start(self, now):
        self.samples = {}
        self.result = {}
        self.step = 0
        self.state = COUNTING
        self.phase_start = now

    def cancel(self):
        self.state = IDLE
        self.step = 0
        self.message = "Premi SPAZIO per iniziare"

    def tick(self, hand, now):
        """
        Avanza di un fotogramma.

        Returns:
            float: avanzamento della fase corrente, 0..1 (per la barra).
        """
        if self.state in (IDLE, DONE):
            return 0.0

        elapsed = now - self.phase_start
        pose = self.pose
        if pose is None:
            return 0.0
        key = pose[0]

        if self.state == COUNTING:
            if elapsed >= COUNTDOWN:
                self.state = CAPTURING
                self.phase_start = now
                self.samples[key] = Samples()
                return 0.0
            return elapsed / COUNTDOWN

        # CAPTURING
        if hand is None:
            # Senza mano il tempo non scorre: meglio aspettare che raccogliere
            # una posa vuota e poi fallire il calcolo.
            self.phase_start = now
            self.message = "Mano non rilevata: rimettila nell'inquadratura"
            return 0.0

        self.samples[key].add(hand)
        self.message = ""
        if elapsed >= CAPTURE:
            self.step += 1
            if self.step >= len(SEQUENCE):
                self.state = DONE
                self.result = compute(self.samples)
            else:
                self.state = COUNTING
                self.phase_start = now
            return 1.0
        return elapsed / CAPTURE


def _panel(frame, lines):
    pad, line_h = 10, 22
    w = min(470, frame.shape[1] - 20)
    h = min(pad * 2 + line_h * len(lines), frame.shape[0] - 20)
    panel = frame[10:10 + h, 10:10 + w]
    if panel.size:
        cv2.addWeighted(panel, 0.2, panel, 0.0, 0.0, dst=panel)
    for i, item in enumerate(lines):
        text, colour = item if isinstance(item, tuple) else (item, None)
        y = 10 + pad + 15 + i * line_h
        if y > frame.shape[0] - 4:
            break
        cv2.putText(frame, text, (10 + pad, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    colour or (230, 230, 230), 1, cv2.LINE_AA)


def _banner(frame, text, sub, colour):
    """Istruzione grande al centro: deve leggersi mentre guardi la tua mano."""
    h, w = frame.shape[:2]
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.95, 2)
    x = max(8, (w - tw) // 2)
    y = h // 2
    band = frame[max(0, y - th - 22):min(h, y + 40), :]
    if band.size:
        cv2.addWeighted(band, 0.25, band, 0.0, 0.0, dst=band)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.95, colour, 2,
                cv2.LINE_AA)
    if sub:
        (sw, _), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(frame, sub, (max(8, (w - sw) // 2), y + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)


def _progress(frame, fraction, colour):
    h, w = frame.shape[:2]
    y = h - 26
    cv2.rectangle(frame, (20, y), (w - 20, y + 12), (60, 60, 60), -1)
    end = int(20 + (w - 40) * max(0.0, min(1.0, fraction)))
    cv2.rectangle(frame, (20, y), (end, y + 12), colour, -1)


def main():
    manager = WebcamManager()
    cameras = manager.list_available_cameras()
    if not cameras:
        print("Nessuna webcam trovata.")
        return 1
    print("Uso %s" % cameras[0][1])
    print(__doc__)

    grabber = manager.open_camera(cameras[0][0])
    tracker = HandTracker(max_num_hands=1)
    cal = Calibration()
    no_key_since = time.time()

    try:
        while True:
            ok, frame, _ = grabber.read(timeout=0.5)
            if not ok:
                continue
            frame = cv2.flip(frame, 1)
            now = time.time()

            results = tracker.process(frame)
            tracker.draw(frame, results)
            hands = tracker.observe(results)
            hand = hands.get("Right") or hands.get("Left")

            fraction = cal.tick(hand, now)

            lines = []
            if hand is None:
                lines.append(("Nessuna mano rilevata", (80, 160, 240)))
            else:
                ext = hand.index_extension
                active = ext >= config.index_control_ratio
                lines.append((
                    "indice teso  %.2f   soglia %.2f  ->  %s"
                    % (ext, config.index_control_ratio,
                       "ATTIVO" if active else "mano chiusa"),
                    (90, 220, 90) if active else (90, 170, 240)))
                lines.append("pinch indice %.2f   chiude sotto %.2f"
                             % (hand.ratio(THUMB_TIP, INDEX_TIP),
                                config.pinch_close_ratio))
                lines.append("pinch medio  %.2f   chiude sotto %.2f"
                             % (hand.ratio(THUMB_TIP, MIDDLE_TIP),
                                config.right_pinch_close_ratio))

            lines.append("")
            for i, (key, title, _) in enumerate(SEQUENCE):
                count = len(cal.samples.get(key, ()))
                mark = ">" if (cal.state != DONE and i == cal.step) else " "
                good = count >= MIN_SAMPLES
                lines.append(("%s %-24s %4d campioni%s"
                              % (mark, title.lower(), count,
                                 "" if good else "  (pochi)" if count else ""),
                              (90, 220, 90) if good else None))

            if cal.state == IDLE:
                _banner(frame, "PREMI  SPAZIO", "per iniziare la calibrazione",
                        (255, 255, 255))
                if now - no_key_since > 12:
                    lines.append("")
                    lines.append(("Se SPAZIO non risponde, clicca prima sulla",
                                  (90, 170, 240)))
                    lines.append(("finestra per darle il focus.", (90, 170, 240)))
            elif cal.state == COUNTING:
                pose = cal.pose
                left = COUNTDOWN - (now - cal.phase_start)
                _banner(frame, "%s  fra %.0f" % (pose[1], max(1, left + 0.5)),
                        pose[2], (90, 200, 255))
                _progress(frame, fraction, (90, 150, 200))
            elif cal.state == CAPTURING:
                pose = cal.pose
                _banner(frame, "%s  -  FERMO" % pose[1],
                        cal.message or "registrazione in corso", (90, 220, 90))
                _progress(frame, fraction, (90, 220, 90))
            elif cal.state == DONE:
                _banner(frame, "FATTO", "S salva   R rifai   ESC esci",
                        (255, 255, 255))
                lines.append("")
                clean = {k: v for k, v in cal.result.items()
                         if not k.startswith("_")}
                if clean:
                    for key, value in sorted(clean.items()):
                        lines.append(("  %s = %.2f" % (key, value), (90, 220, 90)))
                    lines.append(("  premi S per salvare", (255, 255, 255)))
                else:
                    lines.append(("  Pose non separabili: premi R e rifai",
                                  (80, 160, 240)))

            lines.append("")
            lines.append(("SPAZIO avvia   R rifai   S salva   ESC esci",
                          (180, 180, 180)))
            _panel(frame, lines)
            cv2.imshow(WINDOW, frame)

            key = cv2.waitKey(1) & 0xFF
            if key != 255:
                no_key_since = now
            if key == 27:
                break
            if key == 32:  # SPAZIO
                cal.start(now)
            elif key in (ord("r"), ord("R")):
                cal.cancel()
            elif key in (ord("s"), ord("S")) and cal.state == DONE:
                if _save(cal):
                    break
    finally:
        manager.release_camera()
        tracker.close()
        cv2.destroyAllWindows()
    return 0


def _save(cal):
    """Stampa il riepilogo e scrive il profilo. True se ha salvato."""
    print("\n" + "=" * 58)
    print("Misure registrate")
    print("=" * 58)
    for key, title, _ in SEQUENCE:
        s = cal.samples.get(key)
        if not s:
            print("  %-22s nessun campione" % title.lower())
            continue
        lo, mid, hi = Samples.span(s.extension)
        plo, pmid, phi = Samples.span(s.pinch)
        print("  %-22s %3d campioni" % (title.lower(), len(s)))
        print("      indice teso  %.2f - %.2f  (mediana %.2f)" % (lo, hi, mid))
        print("      pinch        %.2f - %.2f  (mediana %.2f)" % (plo, phi, pmid))

    values = cal.result
    if "_overlap" in values:
        print("\n  Pugno e pinch si sovrappongono (%.2f contro %.2f)."
              % values["_overlap"])
        print("  Chiudi meglio il pugno, o tieni l'indice piu' disteso pinzando.")
    if "_pinch_overlap" in values:
        print("\n  Mano aperta e pinch si sovrappongono (%.2f contro %.2f)."
              % values["_pinch_overlap"])
        print("  Separa di piu' pollice e indice nella posa a indice puntato.")
    if "_bad_order" in values:
        print("\n  Soglie del pinch scartate: fuori ordine %r."
              % (values["_bad_order"],))

    clean = {k: v for k, v in values.items() if not k.startswith("_")}
    if not clean:
        print("\n  Niente da salvare: rifai la procedura con R.")
        return False

    print("\n" + "=" * 58)
    print("Soglie calcolate")
    print("=" * 58)
    for key, value in sorted(clean.items()):
        print("  %-26s %.2f   (era %.2f)" % (key, value, getattr(config, key)))
    if "_margin" in values:
        print("\n  Margine fra pugno e pinch: %.2f" % values["_margin"])
        if values["_margin"] < 0.15:
            print("  Margine stretto: le due pose si somigliano molto.")

    for key, value in clean.items():
        setattr(config, key, value)

    import settings_gui
    settings_gui.save_settings()
    print("\n  Salvate in %s. Riavvia AirMouse per usarle."
          % settings_gui.PROFILE_PATH)
    return True


if __name__ == "__main__":
    sys.exit(main())
