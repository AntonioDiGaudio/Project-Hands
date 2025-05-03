import cv2
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from shared_state import get_running
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

# Funzione per ottenere le webcam disponibili
def list_available_cameras(max_cams=2):
    found = []
    threads = []
    camera_names = get_camera_names()
    max_cams = min(max_cams, len(camera_names))  # Limita il numero massimo di webcam da cercare

    for i in range(max_cams):
        t = threading.Thread(target=try_camera, args=(i, found, camera_names))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return found

# Funzione per la GUI di selezione della webcam
def select_camera_gui():
    if not get_running:  # Aggiungi questo controllo all'inizio
        return None 
    selected_index = []

    def on_select(i):
        nonlocal selected_index
        try:
            test_cap = cv2.VideoCapture(i)
            if not test_cap.isOpened():
                messagebox.showerror("Errore", f"Impossibile aprire la webcam #{i}.")
                return
            test_cap.release()
            selected_index.append(i)
            root.destroy()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile aprire la webcam #{i}. Dettagli errore: {str(e)}")

    def search_and_show():
        label.config(text="Ricerca webcam in corso...")
        cameras = list_available_cameras()
        if not cameras:
            label.config(text="Nessuna webcam trovata.")
            return

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

    root = tk.Tk()
    root.title("AirMouse")
    root.geometry(GUI_WINDOW_SIZE)
    root.configure(bg=GUI_BG_COLOR)
    root.resizable(False, False)


    label = tk.Label(root, text="Ricerca webcam in corso...", font=GUI_FONT, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR)

    label.pack(pady=10)

    frame = tk.Frame(root, bg=GUI_BG_COLOR)
    frame.pack(expand=True, fill='both')


    root.after(100, search_and_show)
    root.mainloop()

    if not selected_index:
        raise SystemExit("Nessuna webcam selezionata.")

    return selected_index[0]