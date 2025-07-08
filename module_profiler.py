"""Utility per monitorare l'uso della CPU per modulo.

Questo modulo avvia un profiler che calcola il tempo di CPU speso in ogni modulo
Python. Ogni ``interval`` secondi stampa a video i moduli che hanno consumato
più tempo nell'intervallo precedente.
"""

import sys
import time
import threading
from collections import defaultdict
from types import FrameType


def start(interval: float = 2.0, top_n: int = 5) -> None:
    """Avvia il profiler per monitorare l'uso della CPU per modulo.

    Args:
        interval: intervallo in secondi tra un report e il successivo.
        top_n: numero di moduli da visualizzare nel report.
    """

    module_times: defaultdict[str, float] = defaultdict(float)
    call_times: dict[FrameType, float] = {}

    def profiler(frame: FrameType, event: str, arg) -> None:
        if event == "call":
            call_times[frame] = time.perf_counter()
        elif event == "return":
            start = call_times.pop(frame, None)
            if start is not None:
                module = frame.f_globals.get("__name__", "")
                duration = time.perf_counter() - start
                module_times[module] += duration

    def reporter() -> None:
        while True:
            time.sleep(interval)
            print("\n--- CPU per modulo (ultimi %.1fs) ---" % interval)
            ranked = sorted(module_times.items(), key=lambda x: x[1], reverse=True)
            for mod, t in ranked[:top_n]:
                print(f"{mod}: {t:.4f}s")
            module_times.clear()

    sys.setprofile(profiler)
    t = threading.Thread(target=reporter, daemon=True)
    t.start()
