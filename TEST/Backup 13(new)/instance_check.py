import os
import sys
import socket
import tempfile

def is_already_running():
    """
    Verifica se un'altra istanza dell'applicazione è già in esecuzione
    utilizzando un socket locale come lock file.
    
    Returns:
        bool: True se un'altra istanza è in esecuzione, False altrimenti
    """
    # Crea un percorso univoco per il socket basato sul nome dell'applicazione
    socket_path = os.path.join(tempfile.gettempdir(), 'airmouse.lock')
    
    # Crea un socket
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    
    try:
        # Tenta di legare il socket al percorso
        lock_socket.bind('\0' + socket_path)
        # Se ha successo, nessun'altra istanza è in esecuzione
        return False
    except socket.error:
        # Se fallisce, un'altra istanza è già in esecuzione
        return True

# Esempio di utilizzo
if is_already_running():
    print("Un'altra istanza di AirMouse è già in esecuzione.")
    sys.exit(1)
else:
    print("Avvio di AirMouse...")
    