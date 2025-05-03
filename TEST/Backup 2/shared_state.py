import threading

running = True
lock = threading.Lock()

def set_running(value):
    global running
    with lock:
        running = value

def get_running():
    with lock:
        return running