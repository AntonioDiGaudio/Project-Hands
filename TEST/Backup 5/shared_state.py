import threading

running_event = threading.Event()
running_event.set()  # Default to True

def set_running(value):
    if value:
        running_event.set()
    else:
        running_event.clear()

def get_running():
    return running_event.is_set()