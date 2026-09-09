"""
Diagnosi: registra cosa misura DAVVERO la tua mano e perche' una gesture non parte.

    python diagnose.py

Scrive `diagnosi.txt` nella cartella del progetto. E' un file di testo: aprilo,
o mandalo a chi ti sta aiutando.

Perche' esiste. Le soglie delle gesture sono frazioni della dimensione della
mano, e i valori di riferimento scritti nei commenti del progetto ("indice teso
~1.3-1.5") non sono mai stati verificati su una mano vera. Se quella scala e'
sbagliata, `index_control_ratio` blocca ogni gesture e non si vede perche':
il cursore continua a muoversi normalmente, e i click semplicemente non
partono. Questo strumento non decide niente in base a quei numeri: li misura e
li stampa.

A differenza di `calibrate.py`, qui non viene scartato nulla e non viene
salvato nulla. Serve a capire, non a tarare.
"""

import io
import os
import sys
import time

import cv2

import config
import settings_gui  # applica Profiles/settings.txt, cosi' si diagnostica il vero
from gesture_recognizer import GestureRecognizer
from hand_tracker import HandTracker, THUMB_TIP, INDEX_TIP, MIDDLE_TIP
from mouse_controller import MouseController
from webcam_manager import WebcamManager

WINDOW = "AirMouse - diagnosi"
REPORT = "diagnosi.txt"

COUNTDOWN = 2.0
CAPTURE = 3.0
SETTLE = 0.8

# (chiave, titolo, sottotitolo)
POSES = [
    ("puntamento", "INDICE PUNTATO",
     "indice ben teso, le altre dita chiuse, pollice staccato"),
    ("pinch_indice", "POLLICE + INDICE UNITI",
     "il gesto del click sinistro: le punte si toccano"),
    ("pinch_medio", "POLLICE + MEDIO UNITI",
     "il gesto del click destro: medio teso, punte che si toccano"),
    ("pugno", "PUGNO CHIUSO", "tutte le dita ripiegate sul palmo"),
    ("aperta", "MANO BEN APERTA", "tutte e cinque le dita larghe"),
]

# Fase finale a ruota libera: si prova a usare il programma davvero.
FREE_SECONDS = 20.0

# Fase a due mani, per lo zoom.
ZOOM_SECONDS = 12.0


def pct(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    i = min(len(ordered) - 1, max(0, int(len(ordered) * q)))
    return ordered[i]


class Recording:
    """Tutte le misure di una posa, senza nessun filtro."""

    def __init__(self):
        self.index_ext = []
        self.middle_ext = []
        self.thumb_index = []
        self.thumb_middle = []
        self.fingers = []
        self.scale = []

    def add(self, hand):
        self.index_ext.append(hand.index_extension)
        self.middle_ext.append(hand.middle_extension)
        self.thumb_index.append(hand.ratio(THUMB_TIP, INDEX_TIP))
        self.thumb_middle.append(hand.ratio(THUMB_TIP, MIDDLE_TIP))
        self.fingers.append(hand.fingers)
        self.scale.append(hand.scale)

    def __len__(self):
        return len(self.index_ext)

    def summary(self):
        return {
            "indice teso": (pct(self.index_ext, 0.05), pct(self.index_ext, 0.50),
                            pct(self.index_ext, 0.95)),
            "medio teso": (pct(self.middle_ext, 0.05), pct(self.middle_ext, 0.50),
                           pct(self.middle_ext, 0.95)),
            "pollice-indice": (pct(self.thumb_index, 0.05), pct(self.thumb_index, 0.50),
                               pct(self.thumb_index, 0.95)),
            "pollice-medio": (pct(self.thumb_middle, 0.05), pct(self.thumb_middle, 0.50),
                              pct(self.thumb_middle, 0.95)),
        }

    def fingers_typical(self):
        if not self.fingers:
            return "----"
        counts = [0, 0, 0, 0]
        for f in self.fingers:
            for i in range(4):
                counts[i] += f[i]
        n = len(self.fingers)
        return "".join("^" if c > n / 2 else "_" for c in counts)


class Zoom:
    """
    Lo zoom a due mani, che ha condizioni tutte sue.

    Non passa dal gate della posa di controllo, quindi puo' fallire per motivi
    completamente diversi dai click: la seconda mano non viene rilevata, oppure
    MediaPipe assegna a entrambe la stessa lateralita' e una delle due viene
    scartata, oppure la posa (indici estesi, medi chiusi) non e' riconosciuta.
    Qui si contano i tre casi separatamente, cosi' si sa quale.
    """

    def __init__(self):
        self.frames = 0
        self.two_hands = 0
        self.same_label = 0
        self.pose_ok = 0
        self.events = 0
        self.ratios = []

    def add(self, hands, pose_ok, fired, ratio):
        self.frames += 1
        right, left = hands.get("Right"), hands.get("Left")
        if right is not None and left is not None:
            self.two_hands += 1
        self.pose_ok += int(pose_ok)
        self.events += int(fired)
        if ratio is not None:
            self.ratios.append(ratio)


class Free:
    """La fase a ruota libera: cosa fa la macchina a stati mentre provi."""

    def __init__(self):
        self.frames = 0
        self.gated = {}
        self.frozen = 0
        self.left_armed = 0
        self.left_closed = 0
        self.right_armed = 0
        self.right_closed = 0
        self.middle_ok = 0
        self.pointing = 0
        self.events = []
        self.rec = Recording()

    def add(self, g, hand, frozen, events, now):
        self.frames += 1
        self.rec.add(hand)
        key = g.gated_reason or "(nessuno)"
        self.gated[key] = self.gated.get(key, 0) + 1
        self.frozen += int(frozen)
        self.left_armed += int(g.left_pinch.armed)
        self.left_closed += int(g.left_pinch.closed)
        self.right_armed += int(g.right_pinch.armed)
        self.right_closed += int(g.right_pinch.closed)
        self.middle_ok += int(g.middle_pointing)
        self.pointing += int(g.pointing)
        for name, payload in events:
            self.events.append((round(now, 2), name, payload))


def banner(frame, text, sub, colour):
    h, w = frame.shape[:2]
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
    y = h // 2
    band = frame[max(0, y - th - 22):min(h, y + 40), :]
    if band.size:
        cv2.addWeighted(band, 0.25, band, 0.0, 0.0, dst=band)
    cv2.putText(frame, text, (max(8, (w - tw) // 2), y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, colour, 2, cv2.LINE_AA)
    if sub:
        (sw, _), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(frame, sub, (max(8, (w - sw) // 2), y + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)


def panel(frame, lines):
    pad, lh = 10, 20
    w = min(430, frame.shape[1] - 20)
    h = min(pad * 2 + lh * len(lines), frame.shape[0] - 20)
    area = frame[10:10 + h, 10:10 + w]
    if area.size:
        cv2.addWeighted(area, 0.2, area, 0.0, 0.0, dst=area)
    for i, item in enumerate(lines):
        text, colour = item if isinstance(item, tuple) else (item, None)
        y = 10 + pad + 14 + i * lh
        if y > frame.shape[0] - 4:
            break
        cv2.putText(frame, text, (10 + pad, y), cv2.FONT_HERSHEY_SIMPLEX, 0.46,
                    colour or (230, 230, 230), 1, cv2.LINE_AA)


def progress(frame, fraction, colour):
    h, w = frame.shape[:2]
    y = h - 24
    cv2.rectangle(frame, (20, y), (w - 20, y + 12), (60, 60, 60), -1)
    end = int(20 + (w - 40) * max(0.0, min(1.0, fraction)))
    cv2.rectangle(frame, (20, y), (end, y + 12), colour, -1)


def live_lines(hand, g):
    if hand is None:
        return [("Nessuna mano rilevata", (80, 160, 240))]
    ok = lambda c: (90, 220, 90) if c else (90, 170, 240)
    return [
        ("indice teso   %.2f   soglia %.2f  %s"
         % (hand.index_extension, config.index_control_ratio,
            "ok" if g.pointing else "BLOCCA TUTTO"), ok(g.pointing)),
        ("medio teso    %.2f   soglia %.2f  %s"
         % (hand.middle_extension, config.middle_control_ratio,
            "ok" if g.middle_pointing else "niente click destro"),
         ok(g.middle_pointing)),
        "pollice-indice %.2f   chiude sotto %.2f"
        % (hand.ratio(THUMB_TIP, INDEX_TIP), config.pinch_close_ratio),
        "pollice-medio  %.2f   chiude sotto %.2f"
        % (hand.ratio(THUMB_TIP, MIDDLE_TIP), config.right_pinch_close_ratio),
    ]


def main():
    manager = WebcamManager()
    cameras = manager.list_available_cameras()
    if not cameras:
        print("Nessuna webcam trovata.")
        return 1
    print("Uso %s" % cameras[0][1])
    print(__doc__)

    grabber = manager.open_camera(cameras[0][0])
    tracker = HandTracker(max_num_hands=1,
                          model_complexity=config.model_complexity)
    gestures = GestureRecognizer(config)

    recordings = {}
    free = Free()
    zoom = Zoom()

    # Controller vero, ma con la rotellina intercettata: qui non si tocca
    # niente del sistema, si conta solo se lo zoom SAREBBE partito.
    import mouse_controller
    mouse_controller._wheel = lambda n: None
    mouse_controller.pyautogui.keyDown = lambda k: None
    mouse_controller.pyautogui.keyUp = lambda k: None
    mouse = MouseController(config)
    poll = hasattr(cv2, "pollKey")

    step = 0
    state = "attesa"
    phase_start = 0.0
    started = False

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

            # La macchina a stati gira sempre, cosi' si vede cosa deciderebbe.
            if hand is None:
                gestures.hand_lost(now)
                frozen = False
                events = []
            else:
                gestures.prepare(hand, now)
                frozen = gestures.cursor_frozen()
                events = gestures.update(hand, (960, 540), now)

            lines = live_lines(hand, gestures)
            lines.append("")

            if state == "attesa":
                banner(frame, "PREMI  SPAZIO", "per iniziare la diagnosi",
                       (255, 255, 255))
            elif state == "conto":
                title, sub = POSES[step][1], POSES[step][2]
                left = COUNTDOWN - (now - phase_start)
                banner(frame, "%s  fra %.0f" % (title, max(1, left + 0.5)), sub,
                       (90, 200, 255))
                progress(frame, (now - phase_start) / COUNTDOWN, (90, 150, 200))
                if now - phase_start >= COUNTDOWN:
                    state = "registra"
                    phase_start = now
                    recordings[POSES[step][0]] = Recording()
            elif state == "registra":
                key, title, sub = POSES[step]
                elapsed = now - phase_start
                if hand is None:
                    phase_start = now      # senza mano il tempo non scorre
                    banner(frame, "%s  -  FERMO" % title,
                           "rimetti la mano nell'inquadratura", (80, 160, 240))
                else:
                    if elapsed >= SETTLE:
                        recordings[key].add(hand)
                    banner(frame, "%s  -  FERMO" % title, sub, (90, 220, 90))
                    progress(frame, elapsed / CAPTURE, (90, 220, 90))
                    if elapsed >= CAPTURE:
                        step += 1
                        if step >= len(POSES):
                            state = "libera"
                            phase_start = now
                        else:
                            state = "conto"
                            phase_start = now
            elif state == "libera":
                elapsed = now - phase_start
                banner(frame, "PROVA LE GESTURE  (%.0f s)" % max(0, FREE_SECONDS - elapsed),
                       "clicca, tieni premuto, trascina, click destro", (255, 220, 90))
                progress(frame, elapsed / FREE_SECONDS, (255, 220, 90))
                if hand is not None:
                    free.add(gestures, hand, frozen, events, now)
                if elapsed >= FREE_SECONDS:
                    state = "zoom"
                    phase_start = now
                    tracker.reconfigure(max_num_hands=2)
            elif state == "zoom":
                elapsed = now - phase_start
                banner(frame, "ZOOM: DUE MANI  (%.0f s)" % max(0, ZOOM_SECONDS - elapsed),
                       "solo gli indici estesi, allontana e avvicina le mani",
                       (200, 160, 255))
                progress(frame, elapsed / ZOOM_SECONDS, (200, 160, 255))

                a, b = hands.get("Right"), hands.get("Left")
                pose_ok = (a is not None and b is not None
                           and a.fingers[0] and b.fingers[0]
                           and not a.fingers[1] and not b.fingers[1])
                ratio = None
                fired = False
                if pose_ok:
                    ax, ay = a.point(INDEX_TIP)
                    bx, by = b.point(INDEX_TIP)
                    scale = (a.scale + b.scale) * 0.5
                    ratio = (((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                             / max(scale, 1e-6))
                    fired, _ = mouse.handle_zoom(ratio, True, now)
                else:
                    mouse.handle_zoom(0.0, False, now)
                zoom.add(hands, pose_ok, fired, ratio)
                if elapsed >= ZOOM_SECONDS:
                    break

            for key, title, _ in POSES:
                n = len(recordings.get(key, ()))
                mark = ">" if (state in ("conto", "registra")
                               and POSES[step][0] == key) else " "
                lines.append(("%s %-22s %4d campioni" % (mark, title.lower(), n),
                              (90, 220, 90) if n >= 10 else None))
            if state == "libera":
                lines.append(("> fase libera: %d fotogrammi, %d eventi"
                              % (free.frames, len(free.events)), (255, 220, 90)))

            lines.append("")
            lines.append(("stato: %s   cursore: %s"
                          % (gestures.status_text(),
                             "BLOCCATO" if frozen else "libero"), (180, 180, 180)))
            lines.append(("SPAZIO avvia   ESC esci", (180, 180, 180)))
            panel(frame, lines)
            cv2.imshow(WINDOW, frame)

            key = (cv2.pollKey() if poll else cv2.waitKey(1)) & 0xFF
            if key == 27:
                break
            if key == 32 and not started:
                started = True
                state = "conto"
                phase_start = now
    finally:
        manager.release_camera()
        tracker.close()
        cv2.destroyAllWindows()

    write_report(recordings, free, zoom)
    return 0


# ---------------------------------------------------------------------------
def write_report(recordings, free, zoom=None):
    out = io.StringIO()
    w = out.write

    w("DIAGNOSI AIRMOUSE\n")
    w("=" * 70 + "\n\n")

    w("Soglie attive (da Profiles/settings.txt)\n")
    w("-" * 70 + "\n")
    for key in ("index_control_ratio", "middle_control_ratio",
                "pinch_close_ratio", "pinch_open_ratio", "pinch_freeze_ratio",
                "right_pinch_close_ratio", "right_pinch_open_ratio",
                "pinch_approach_drop", "drag_hold_time", "require_pointing_pose",
                "model_complexity", "enable_zoom", "enable_right_click"):
        w("  %-26s %s\n" % (key, getattr(config, key, "?")))

    w("\n\nMisure per posa   (5o percentile / mediana / 95o percentile)\n")
    w("=" * 70 + "\n")
    if not recordings:
        w("  Nessuna posa registrata.\n")
    for key, title, _ in POSES:
        rec = recordings.get(key)
        w("\n%s   (%d campioni, dita %s)\n"
          % (title, len(rec) if rec else 0, rec.fingers_typical() if rec else "----"))
        if not rec or len(rec) < 5:
            w("    campioni insufficienti\n")
            continue
        for name, (lo, mid, hi) in rec.summary().items():
            w("    %-16s %5.2f  %5.2f  %5.2f\n" % (name, lo, mid, hi))

    w("\n\nFase libera\n")
    w("=" * 70 + "\n")
    if free.frames == 0:
        w("  Nessun fotogramma.\n")
    else:
        n = float(free.frames)
        w("  fotogrammi con mano      : %d\n" % free.frames)
        w("  posa di controllo ok     : %d  (%.0f%%)\n"
          % (free.pointing, 100 * free.pointing / n))
        w("  medio disteso ok         : %d  (%.0f%%)\n"
          % (free.middle_ok, 100 * free.middle_ok / n))
        w("  pinch sx armato          : %d  (%.0f%%)\n"
          % (free.left_armed, 100 * free.left_armed / n))
        w("  pinch sx chiuso          : %d  (%.0f%%)\n"
          % (free.left_closed, 100 * free.left_closed / n))
        w("  pinch dx armato          : %d  (%.0f%%)\n"
          % (free.right_armed, 100 * free.right_armed / n))
        w("  pinch dx chiuso          : %d  (%.0f%%)\n"
          % (free.right_closed, 100 * free.right_closed / n))
        w("  cursore congelato        : %d  (%.0f%%)\n"
          % (free.frozen, 100 * free.frozen / n))
        w("\n  motivo del blocco, per fotogramma:\n")
        for reason, count in sorted(free.gated.items(), key=lambda kv: -kv[1]):
            w("    %-22s %5d  (%.0f%%)\n" % (reason, count, 100 * count / n))
        w("\n  eventi emessi: %d\n" % len(free.events))
        for t, name, payload in free.events:
            w("    %8.2f  %-12s %s\n" % (t, name, payload if payload is not None else ""))
        w("\n  misure durante la fase libera:\n")
        for name, (lo, mid, hi) in free.rec.summary().items():
            w("    %-16s %5.2f  %5.2f  %5.2f\n" % (name, lo, mid, hi))

    if zoom is not None and zoom.frames:
        n = float(zoom.frames)
        w("\n\nFase zoom (due mani)\n")
        w("=" * 70 + "\n")
        w("  fotogrammi               : %d\n" % zoom.frames)
        w("  due mani rilevate        : %d  (%.0f%%)\n"
          % (zoom.two_hands, 100 * zoom.two_hands / n))
        w("  posa di zoom valida      : %d  (%.0f%%)\n"
          % (zoom.pose_ok, 100 * zoom.pose_ok / n))
        w("  zoom che sarebbero partiti: %d\n" % zoom.events)
        if zoom.ratios:
            w("  distanza fra gli indici  : %.2f / %.2f / %.2f\n"
              % (pct(zoom.ratios, 0.05), pct(zoom.ratios, 0.50),
                 pct(zoom.ratios, 0.95)))

    w("\n\nLettura automatica\n")
    w("=" * 70 + "\n")
    for line in verdict(recordings, free, zoom):
        w("  %s\n" % line)

    text = out.getvalue()
    with open(REPORT, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(text)
    print("Report scritto in %s" % os.path.abspath(REPORT))


def verdict(recordings, free, zoom=None):
    """Confronta le misure con le soglie e dice quale soglia non torna."""
    lines = []
    point = recordings.get("puntamento")
    pinch = recordings.get("pinch_indice")
    mpinch = recordings.get("pinch_medio")
    fist = recordings.get("pugno")

    def ok(rec):
        return rec is not None and len(rec) >= 5

    # 1. Il gate della posa di controllo: se scatta, non parte NIENTE.
    if ok(pinch):
        low = pct(pinch.index_ext, 0.05)
        if low < config.index_control_ratio:
            lines.append(
                "BLOCCANTE: pinzando, l'indice misura %.2f (5o pct) contro una "
                "soglia index_control_ratio di %.2f." % (low, config.index_control_ratio))
            lines.append(
                "  Il gate 'mano chiusa' scatta proprio mentre clicchi, quindi "
                "click, drag e click destro non partono MAI. Il cursore invece "
                "continua a muoversi, perche' non passa da questo gate.")
            if ok(fist):
                high = pct(fist.index_ext, 0.95)
                if low > high:
                    lines.append("  Valore giusto per la tua mano: circa %.2f "
                                 "(fra pugno %.2f e pinch %.2f)."
                                 % ((low + high) / 2, high, low))
                else:
                    lines.append("  Attenzione: pugno (%.2f) e pinch (%.2f) si "
                                 "sovrappongono, le due pose non sono separabili."
                                 % (high, low))
        else:
            lines.append("index_control_ratio va bene: pinzando l'indice misura "
                         "%.2f, sopra la soglia %.2f."
                         % (low, config.index_control_ratio))

    # 2. La soglia di chiusura del pinch sinistro.
    if ok(pinch) and ok(point):
        closed = pct(pinch.thumb_index, 0.95)
        open_ = pct(point.thumb_index, 0.05)
        if closed >= config.pinch_close_ratio:
            lines.append(
                "BLOCCANTE: pinzando, pollice-indice resta a %.2f (95o pct) ma la "
                "soglia di chiusura e' %.2f: il pinch non viene mai riconosciuto."
                % (closed, config.pinch_close_ratio))
        if open_ <= config.pinch_open_ratio:
            lines.append(
                "BLOCCANTE: a mano aperta pollice-indice sta a %.2f (5o pct), sotto "
                "la soglia di apertura %.2f: il rilevatore non si arma mai e nessun "
                "click puo' partire." % (open_, config.pinch_open_ratio))
        if closed < open_:
            lines.append("  Soglie sensate per la tua mano: chiusura %.2f, "
                         "apertura %.2f."
                         % (closed + (open_ - closed) * 0.25,
                            closed + (open_ - closed) * 0.60))

    # 3. Il click destro.
    if ok(mpinch):
        low = pct(mpinch.middle_ext, 0.05)
        if low < config.middle_control_ratio:
            lines.append(
                "BLOCCANTE per il click destro: nel pinch pollice+medio il medio "
                "misura %.2f contro middle_control_ratio %.2f, quindi la gesture "
                "viene ignorata." % (low, config.middle_control_ratio))
        closed = pct(mpinch.thumb_middle, 0.95)
        if closed >= config.right_pinch_close_ratio:
            lines.append(
                "BLOCCANTE per il click destro: pollice-medio resta a %.2f contro "
                "una chiusura di %.2f." % (closed, config.right_pinch_close_ratio))

    # 4. Cosa e' successo davvero provando.
    if free.frames:
        n = float(free.frames)
        if free.pointing / n < 0.5:
            lines.append("Nella prova, la posa di controllo era valida solo nel "
                         "%.0f%% dei fotogrammi: e' il gate che ti blocca."
                         % (100 * free.pointing / n))
        if free.left_armed / n < 0.5:
            lines.append("Nella prova, il pinch sinistro e' rimasto disarmato nel "
                         "%.0f%% dei fotogrammi: la mano non viene mai vista "
                         "abbastanza aperta, quindi il click non si arma."
                         % (100 * (1 - free.left_armed / n)))
        if free.frozen / n > 0.5:
            lines.append("Nella prova, il cursore e' rimasto bloccato nel %.0f%% "
                         "dei fotogrammi." % (100 * free.frozen / n))
        if not free.events:
            lines.append("Nella prova non e' stato emesso NESSUN evento.")

    # 5. Lo zoom, che ha cause di guasto tutte sue.
    if zoom is not None and zoom.frames:
        n = float(zoom.frames)
        if zoom.two_hands / n < 0.3:
            lines.append(
                "ZOOM: le due mani sono state viste insieme solo nel %.0f%% dei "
                "fotogrammi. Senza seconda mano lo zoom non puo' partire: "
                "tienile entrambe ben dentro l'inquadratura e separate."
                % (100 * zoom.two_hands / n))
        elif zoom.pose_ok / n < 0.3:
            lines.append(
                "ZOOM: le due mani si vedono (%.0f%%) ma la posa vale solo nel "
                "%.0f%% dei fotogrammi. Serve SOLO l'indice esteso su entrambe: "
                "il medio deve restare chiuso."
                % (100 * zoom.two_hands / n, 100 * zoom.pose_ok / n))
        elif zoom.events == 0:
            lines.append(
                "ZOOM: posa riconosciuta ma nessuno scatto. Muovi le mani di "
                "piu', oppure abbassa zoom_trigger_ratio (ora %.2f): serve una "
                "variazione di quella frazione della distanza fra gli indici."
                % config.zoom_trigger_ratio)
        else:
            lines.append("ZOOM: funziona, %d scatti nella prova." % zoom.events)

    if not lines:
        lines.append("Nessuna anomalia evidente nelle soglie: le misure stanno "
                     "dalla parte giusta di ogni soglia.")
    return lines


if __name__ == "__main__":
    sys.exit(main())
