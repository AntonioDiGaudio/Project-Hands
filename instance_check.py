"""
Lock a istanza singola, cross-platform.

La versione precedente usava `socket.AF_UNIX`, che su Windows non esiste: la
chiamata sollevava `AttributeError` prima ancora di avviare l'applicazione.

Qui si usa un socket TCP in ascolto su localhost: la porta si libera da sola
quando il processo termina, anche in caso di crash, quindi non restano lock
orfani come succede con i file di lock.
"""

import socket

_LOCK_PORT = 47821
_lock_socket = None


def acquire_lock(port=_LOCK_PORT):
    """
    Tenta di acquisire il lock di istanza singola.

    Returns:
        socket.socket | None: il socket da tenere vivo, o None se un'altra
        istanza e' gia' in esecuzione.
    """
    global _lock_socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Niente SO_REUSEADDR: qui il conflitto e' esattamente il segnale che
        # vogliamo rilevare.
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
    except OSError:
        sock.close()
        return None
    _lock_socket = sock
    return sock


def release_lock():
    global _lock_socket
    if _lock_socket is not None:
        try:
            _lock_socket.close()
        except OSError:
            pass
        _lock_socket = None


def is_already_running():
    """True se un'altra istanza detiene gia' il lock."""
    return acquire_lock() is None
