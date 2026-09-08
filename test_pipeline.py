"""
Test di integrazione della pipeline con webcam reale, senza toccare il mouse.

Misura il costo effettivo per fotogramma di ogni stadio (cattura, inferenza,
gesture) e verifica che nessun evento venga emesso su una scena senza mani: un
evento qui sarebbe un falso positivo puro.

    python test_pipeline.py [secondi]
"""

import sys
import time

import cv2

import config
from gesture_recognizer import GestureRecognizer
from hand_tracker import HandTracker, INDEX_TIP
from webcam_manager import WebcamManager


class _NullMouse:
    """Sostituto del controller che registra invece di agire sul sistema."""

    def __init__(self):
        self.screen_w, self.screen_h = 1920, 1080
        self.events = []

    def update_cursor(self, nx, ny, now, frozen=False):
        return (nx * self.screen_w, ny * self.screen_h)


def main(duration=8.0):
    print("Test pipeline: %.0f secondi. Il mouse NON verra' mosso.\n" % duration)

    manager = WebcamManager()
    cameras = manager.list_available_cameras()
    if not cameras:
        print("Nessuna webcam disponibile: test saltato.")
        return 0
    index = cameras[0][0]
    print("Uso %s\n" % cameras[0][1])

    grabber = manager.open_camera(index)
    tracker = HandTracker(max_num_hands=1)
    gestures = GestureRecognizer(config)
    mouse = _NullMouse()

    stats = {"capture": 0.0, "flip": 0.0, "infer": 0.0, "gest": 0.0}
    frames = 0
    events = []
    hand_frames = 0
    skipped = 0
    last_hand_seen = 0.0
    last_infer = 0.0

    print("%dx%d, backend %s" % (manager.actual_resolution() + (manager.backend_used,)))
    print("Muovi la mano davanti alla webcam per vedere il rilevamento.\n")

    deadline = time.perf_counter() + duration
    while time.perf_counter() < deadline:
        t = time.perf_counter()
        ok, frame, _ = grabber.read(timeout=0.5)
        stats["capture"] += time.perf_counter() - t
        if not ok:
            continue
        now = time.perf_counter()
        frames += 1

        t = time.perf_counter()
        frame = cv2.flip(frame, 1)
        stats["flip"] += time.perf_counter() - t

        idle = (now - last_hand_seen) > config.idle_after_seconds
        if idle and config.idle_throttle:
            if now - last_infer < 1.0 / config.idle_detect_fps:
                skipped += 1
                continue

        t = time.perf_counter()
        results = tracker.process(frame)
        stats["infer"] += time.perf_counter() - t
        last_infer = now

        t = time.perf_counter()
        hands = tracker.observe(results)
        hand = hands.get("Right") or hands.get("Left")
        if hand is not None:
            hand_frames += 1
            last_hand_seen = now
            nx, ny = hand.point(INDEX_TIP)
            pos = mouse.update_cursor(nx, ny, now, gestures.cursor_frozen())
            events.extend(gestures.update(hand, pos, now))
        else:
            events.extend(gestures.hand_lost(now))
        stats["gest"] += time.perf_counter() - t

    manager.release_camera()
    tracker.close()

    inferred = frames - skipped
    print("=" * 58)
    print("Fotogrammi ricevuti      : %d" % frames)
    print("  con inferenza          : %d" % inferred)
    print("  saltati (idle)         : %d  (%.0f%%)"
          % (skipped, 100.0 * skipped / max(1, frames)))
    print("  con una mano rilevata  : %d" % hand_frames)
    print("Frame scartati dal grabber: %d (latenza evitata)" % grabber.dropped)
    print("\nCosto medio per fotogramma (ms):")
    print("  attesa cattura         : %6.2f" % (stats["capture"] / max(1, frames) * 1000))
    print("  flip                   : %6.2f" % (stats["flip"] / max(1, frames) * 1000))
    print("  inferenza              : %6.2f" % (stats["infer"] / max(1, inferred) * 1000))
    print("  gesture                : %6.3f" % (stats["gest"] / max(1, inferred) * 1000))
    print("\nFPS effettivi            : %.1f" % (frames / duration))

    busy = stats["infer"] + stats["gest"] + stats["flip"]
    print("CPU occupata dal loop    : %.0f%%" % (100.0 * busy / duration))

    if hand_frames == 0:
        real = [name for name, _ in events]
        print("\nNessuna mano inquadrata; eventi emessi: %d" % len(real))
        if real:
            print("  FALSO POSITIVO: %r" % real[:10])
            return 1
        print("  ok: nessun falso positivo.")
    else:
        names = [name for name, _ in events]
        print("\nEventi rilevati: %r" % names[:20])
    return 0


if __name__ == "__main__":
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    sys.exit(main(seconds))
