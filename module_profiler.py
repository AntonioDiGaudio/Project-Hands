"""
Profiler per modulo, attivabile con `python main.py --profile`.

Due problemi della versione precedente sono stati corretti:

* partiva sempre. `sys.setprofile` intercetta ogni chiamata Python del
  processo: e' uno strumento di diagnosi, non qualcosa da lasciare acceso in
  esecuzione normale.
* il dizionario dei frame in corso non veniva mai ripulito. Un frame che non
  emette l'evento "return" (eccezioni, generatori abbandonati) restava dentro
  per sempre: memoria che cresce senza limite in un processo a esecuzione lunga.
"""

import sys
import threading
import time
from collections import defaultdict

_started = False


def start(interval=2.0, top_n=6):
    """Avvia il profiler. Chiamate successive alla prima non fanno nulla."""
    global _started
    if _started:
        return
    _started = True

    module_times = defaultdict(float)
    call_times = {}
    lock = threading.Lock()

    def profiler(frame, event, arg):
        if event == "call":
            # Cap di sicurezza: se i frame orfani si accumulano si riparte da
            # zero invece di far crescere la memoria all'infinito.
            if len(call_times) > 20000:
                call_times.clear()
            call_times[frame] = time.perf_counter()
        elif event == "return":
            start_time = call_times.pop(frame, None)
            if start_time is not None:
                name = frame.f_globals.get("__name__", "?")
                with lock:
                    module_times[name] += time.perf_counter() - start_time

    def reporter():
        while _started:
            time.sleep(interval)
            with lock:
                ranked = sorted(module_times.items(), key=lambda kv: kv[1],
                                reverse=True)[:top_n]
                module_times.clear()
            if not ranked:
                continue
            print("\n--- CPU per modulo (ultimi %.1fs) ---" % interval)
            for module, seconds in ranked:
                print("  %-28s %7.1f ms" % (module, seconds * 1000))

    sys.setprofile(profiler)
    threading.Thread(target=reporter, daemon=True, name="profiler").start()


def stop():
    global _started
    _started = False
    sys.setprofile(None)
