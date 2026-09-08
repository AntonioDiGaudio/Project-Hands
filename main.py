"""
Punto di ingresso di AirMouse.

    python main.py                  avvio normale
    python main.py --no-window      senza finestra di debug (piu' leggero)
    python main.py --profile        attiva il profiler per modulo
    python main.py --benchmark      misura le prestazioni e esce
"""

import argparse
import logging
import os
import sys
import tempfile

import instance_check


def setup_logging(verbose=False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(tempfile.gettempdir(), "airmouse.log"),
                                encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("AirMouse")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="AirMouse: mouse controllato dai gesti.")
    parser.add_argument("--no-window", action="store_true",
                        help="non aprire la finestra di debug con la webcam")
    parser.add_argument("--no-overlay", action="store_true",
                        help="finestra di debug senza pannello dei parametri")
    parser.add_argument("--profile", action="store_true",
                        help="attiva il profiler per modulo (rallenta l'esecuzione)")
    parser.add_argument("--benchmark", action="store_true",
                        help="misura le prestazioni della macchina e termina")
    parser.add_argument("--no-auto-perf", action="store_true",
                        help="disattiva la degradazione automatica della qualita'")
    parser.add_argument("--allow-multiple", action="store_true",
                        help="permette piu' istanze contemporanee")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    logger = setup_logging(args.verbose)

    lock = None
    if not args.allow_multiple:
        lock = instance_check.acquire_lock()
        if lock is None:
            logger.error("Un'altra istanza di AirMouse e' gia' in esecuzione.")
            return 1

    try:
        import config

        if args.no_window:
            config.show_debug_window = False
        if args.no_overlay:
            config.overlay_enabled = False
        if args.no_auto_perf:
            config.auto_performance = False
        if args.profile:
            config.enable_profiler = True

        if args.benchmark:
            from benchmark import run_benchmark
            return run_benchmark()

        # Il profiler usa sys.setprofile, che intercetta ogni chiamata Python
        # del processo: utile per diagnosticare, ma va tenuto spento in uso
        # normale. Prima era sempre attivo.
        if config.enable_profiler:
            from module_profiler import start as start_profiler
            logger.warning("Profiler attivo: le prestazioni saranno ridotte.")
            start_profiler()

        from app import main as run_app

        logger.info("Avvio di AirMouse...")
        run_app()
        return 0
    except Exception:
        logger.exception("Errore durante l'esecuzione")
        return 1
    finally:
        instance_check.release_lock()


if __name__ == "__main__":
    sys.exit(main())
