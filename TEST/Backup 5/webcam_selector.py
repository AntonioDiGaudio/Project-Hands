import cv2
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from shared_state import get_running, set_running
from gui_theme import (
    GUI_FONT, GUI_BG_COLOR, GUI_FG_COLOR,
    GUI_BUTTON_BG, GUI_BUTTON_FG, GUI_HIGHLIGHT_COLOR,
    GUI_WINDOW_SIZE
)


# Funzione per ottenere i nomi delle webcam su Linux

def get_camera_names():

    result = subprocess.run(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output = result.stdout.decode('utf-8')

    cameras = []

    lines = output.splitlines()

    for i in range(len(lines)):

        if lines[i].strip() != "" and "video" in lines[i]:

            cameras.append(lines[i].strip())

    return cameras



# Funzione per cercare le webcam disponibili

def try_camera(i, found, camera_names):

    try:

        cap = cv2.VideoCapture(i)

        if cap.isOpened():

            ret, frame = cap.read()

            if ret:

                camera_name = camera_names[i] if i < len(camera_names) else f"Webcam #{i}"

                found.append((i, camera_name))

            cap.release()

        else:

            print(f"Webcam {i} non disponibile.")

    except cv2.error as e:

        print(f"Errore durante l'accesso alla videocamera {i}: {e}")

def list_available_cameras(max_cams=2, stop_event=None):
    found = []
    camera_names = get_camera_names()
    max_cams = min(max_cams, len(camera_names)) if camera_names else max_cams

    for i in range(max_cams):
        if stop_event and stop_event.is_set():
            break
        try_camera(i, found, camera_names or [])
    return found

def select_camera_gui():
    if not get_running():  
        return None 
    
    selected_index = []
    stop_search = threading.Event()

    def on_select(i):
        nonlocal selected_index
        try:
            test_cap = cv2.VideoCapture(i)
            if not test_cap.isOpened():
                messagebox.showerror("Errore", f"Impossibile aprire la webcam #{i}.")
                return
            test_cap.release()
            selected_index.append(i)
            stop_search.set()
            root.destroy()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile aprire la webcam #{i}. Dettagli errore: {str(e)}")

    def search_and_show():
        label.config(text="Ricerca webcam in corso...")
        cancel_btn.config(state=tk.NORMAL)
        
        # Esegui la ricerca in un thread separato per non bloccare la GUI
        def search_thread():
            cameras = list_available_cameras(stop_event=stop_search)
            if not cameras and not stop_search.is_set():
                root.after(0, lambda: label.config(text="Nessuna webcam trovata."))
                return
            
            if not stop_search.is_set():
                root.after(0, lambda: show_cameras(cameras))
        
        threading.Thread(target=search_thread, daemon=True).start()

    def show_cameras(cameras):
        label.config(text="Seleziona una webcam:")
        for widget in frame.winfo_children():
            widget.destroy()

        for idx, cam_name in cameras:
            btn = tk.Button(
                frame, text=f"{cam_name}",
                command=lambda i=idx: on_select(i),
                font=GUI_FONT,
                bg=GUI_BUTTON_BG,
                fg=GUI_BUTTON_FG,
                activebackground=GUI_HIGHLIGHT_COLOR,
                relief="flat"
            )
            btn.pack(pady=5, padx=10, fill='x')

    def on_close():
        stop_search.set()
        set_running(False)
        root.destroy()
        raise SystemExit("Selezione webcam annullata dall'utente")

    root = tk.Tk()
    root.title("AirMouse")
    root.geometry(GUI_WINDOW_SIZE)
    root.configure(bg=GUI_BG_COLOR)
    root.resizable(False, False)
    root.protocol("WM_DELETE_WINDOW", on_close)

    label = tk.Label(root, text="Ricerca webcam in corso...", font=GUI_FONT, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR)
    label.pack(pady=10)

    frame = tk.Frame(root, bg=GUI_BG_COLOR)
    frame.pack(expand=True, fill='both')

    cancel_btn = tk.Button(
        root, text="Annulla", command=on_close,
        font=GUI_FONT, bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG,
        activebackground=GUI_HIGHLIGHT_COLOR, relief="flat",
        state=tk.DISABLED
    )
    cancel_btn.pack(pady=10, fill='x')

    root.after(100, search_and_show)
    root.mainloop()

    if not selected_index:
        raise SystemExit("Nessuna webcam selezionata.")

    return selected_index[0]