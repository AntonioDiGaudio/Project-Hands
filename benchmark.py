"""
Benchmark della macchina: `python main.py --benchmark`.

Serve a sapere con numeri concreti che cosa costa cosa su questo hardware, e a
suggerire dei default sensati. Utile soprattutto quando si porta il programma su
una macchina debole (Raspberry Pi e simili), dove tirare a indovinare i
parametri fa perdere molto piu' tempo che misurarli.
"""

import platform
import time

import cv2
import numpy as np

import config


def _timed(fn, warmup=3, runs=20):
    for _ in range(warmup):
        fn()
    start = time.perf_counter()
    for _ in range(runs):
        fn()
    return (time.perf_counter() - start) / runs


def _grab_reference_frame():
    """Un frame vero dalla webcam; se non c'e', un'immagine sintetica."""
    from webcam_manager import WebcamManager, _backend_order

    for backend in _backend_order():
        cap = cv2.VideoCapture(0, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            for _ in range(5):
                cap.read()
            ok, frame = cap.read()
            cap.release()
            if ok:
                return frame, True
        cap.release()
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8), False


def run_benchmark():
    print("=" * 62)
    print("AirMouse - benchmark")
    print("%s %s | Python %s" % (platform.system(), platform.machine(),
                                 platform.python_version()))
    print("=" * 62)

    frame, live = _grab_reference_frame()
    print("Frame di riferimento: %dx%d (%s)"
          % (frame.shape[1], frame.shape[0],
             "webcam" if live else "sintetico, nessuna webcam"))

    # -- backend camera ---------------------------------------------------
    print("\n[1] Backend webcam")
    from webcam_manager import _BACKENDS
    for name in ("msmf", "dshow", "v4l2", "avfoundation"):
        api = _BACKENDS.get(name, 0)
        if not api:
            continue
        cap = cv2.VideoCapture(0, api)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        ok, _ = cap.read()
        if ok:
            start = time.perf_counter()
            for _ in range(30):
                cap.read()
            fps = 30.0 / (time.perf_counter() - start)
            print("    %-14s %5.1f fps" % (name, fps))
        cap.release()

    # -- inferenza --------------------------------------------------------
    print("\n[2] Modello MediaPipe (ms per fotogramma)")
    import mediapipe as mp

    results = {}
    for hands_n in (1, 2):
        for complexity in (0, 1):
            model = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=hands_n,
                model_complexity=complexity,
                min_detection_confidence=config.min_detection_confidence,
                min_tracking_confidence=config.min_tracking_confidence,
            )
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            dt = _timed(lambda: model.process(rgb), warmup=3, runs=15)
            model.close()
            results[(hands_n, complexity)] = dt * 1000.0
            print("    %d mano/i, complessita' %d : %6.1f ms  (%5.1f fps)"
                  % (hands_n, complexity, dt * 1000.0, 1.0 / dt))

    # -- costo del contorno ----------------------------------------------
    print("\n[3] Costo per fotogramma del contorno (ms)")
    buf = frame.copy()
    print("    flip                : %6.2f" % (_timed(lambda: cv2.flip(frame, 1)) * 1000))
    print("    cvtColor con dst    : %6.2f"
          % (_timed(lambda: cv2.cvtColor(frame, cv2.COLOR_BGR2RGB, dst=buf)) * 1000))
    print("    cvtColor allocante  : %6.2f"
          % (_timed(lambda: cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)) * 1000))
    overlay = frame.copy()
    print("    overlay vecchio     : %6.2f" % (_timed(
        lambda: cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame.copy())) * 1000))

    # -- verdetto ---------------------------------------------------------
    best = results[(1, 0)]
    budget = 1000.0 / config.target_fps
    print("\n" + "=" * 62)
    print("Configurazione suggerita")
    print("=" * 62)
    print("  Costo minimo per fotogramma : %.1f ms (%.0f fps di soffitto)"
          % (best, 1000.0 / best))

    if best > 90:
        print("  Macchina molto lenta.")
        print("    enable_zoom         = False   (una mano sola)")
        print("    show_debug_window   = False")
        print("    draw_landmarks      = False")
        print("    target_fps          = 15")
        print("    idle_detect_fps     = 4")
    elif best > 45:
        print("  Macchina modesta.")
        print("    draw_landmarks      = False")
        print("    target_fps          = 24")
        print("    idle_detect_fps     = 6")
    else:
        print("  Macchina adeguata: i default vanno bene.")

    # Il costo scala con le mani effettivamente RILEVATE, non con il tetto
    # impostato: se in questo frame non c'era nessuna mano, la differenza fra
    # 1 e 2 misurata qui sopra e' solo rumore. Va detto, altrimenti il numero
    # induce in errore.
    delta = results[(2, 0)] - results[(1, 0)]
    print("\n  1 mano contro 2 mani: %+.1f ms su questo fotogramma." % delta)
    if abs(delta) < 2.0:
        print("    Differenza nel rumore: nel fotogramma di riferimento non")
        print("    c'era nessuna mano. Il costo cresce solo con le mani")
        print("    effettivamente rilevate, quindi il tetto da solo non pesa.")
    print("  Complessita' 1 contro 0: %+.1f ms." % (results[(1, 1)] - results[(1, 0)]))

    idle_cost = best * config.target_fps / 1000.0
    idle_saved = best * config.idle_detect_fps / 1000.0
    print("\n  CPU a riposo (nessuna mano inquadrata):")
    print("    senza idle_throttle : %.0f%% di un core" % (idle_cost * 100))
    print("    con idle_throttle   : %.0f%% di un core" % (idle_saved * 100))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_benchmark())
