"""
Script principale per avviare l'applicazione AirMouse.
"""

import os
import sys
import socket
import tempfile
import logging
from app import main
from module_profiler import start as start_profiler

def setup_logging():
    """Configura il sistema di logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(tempfile.gettempdir(), "airmouse.log")),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("AirMouse")

def is_already_running():
    """
    Verifica se un'altra istanza dell'applicazione è già in esecuzione.
    
    Returns:
        bool: True se un'altra istanza è in esecuzione, False altrimenti.
    """
    # Crea un percorso univoco per il socket basato sul nome dell'applicazione
    socket_path = os.path.join(tempfile.gettempdir(), 'airmouse.lock')
    
    # Crea un socket
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    
    try:
        # Tenta di legare il socket al percorso
        lock_socket.bind('\0' + socket_path)
        # Se ha successo, nessun'altra istanza è in esecuzione
        return False, lock_socket
    except socket.error:
        # Se fallisce, un'altra istanza è già in esecuzione
        return True, None

if __name__ == "__main__":
    logger = setup_logging()
    
    # Verifica se un'altra istanza è già in esecuzione
    already_running, lock_socket = is_already_running()
    
    if already_running:
        logger.error("Un'altra istanza di AirMouse è già in esecuzione.")
        sys.exit(1)

    # Avvia il profiler per monitorare i moduli più pesanti
    start_profiler()

    try:
        logger.info("Avvio di AirMouse...")
        main()
    except Exception as e:
        logger.exception(f"Errore durante l'esecuzione: {e}")
    finally:
        
        if lock_socket:
            lock_socket.close()