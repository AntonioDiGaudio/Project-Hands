"""
Modulo per gestire lo stato condiviso tra i diversi componenti dell'applicazione.
Fornisce funzionalità per impostare e ottenere lo stato di esecuzione.
"""

import threading

# Evento per gestire lo stato di esecuzione dell'applicazione
running_event = threading.Event()
running_event.set()  # Default a True

def set_running(value):
    """
    Imposta lo stato di esecuzione dell'applicazione.
    
    Args:
        value (bool): True per avviare, False per fermare.
    """
    if value:
        running_event.set()
    else:
        running_event.clear()

def get_running():
    """
    Ottiene lo stato di esecuzione dell'applicazione.
    
    Returns:
        bool: True se l'applicazione è in esecuzione, False altrimenti.
    """
    return running_event.is_set()
