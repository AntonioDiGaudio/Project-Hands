"""
Modulo per la gestione della webcam e la selezione della fotocamera.
Fornisce funzionalità per elencare, testare e selezionare le webcam disponibili.
"""

import cv2
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from shared_state import get_running, set_running
from gui_theme import (
    GUI_FONT, GUI_BG_COLOR, GUI_FG_COLOR,
    GUI_BUTTON_BG, GUI_BUTTON_FG, GUI_HIGHLIGHT_COLOR,GUI_FONT_BOLD_TITLE
)
import config


class WebcamManager:
    """
    Classe per gestire la selezione e l'accesso alle webcam.
    Fornisce metodi per elencare le webcam disponibili e selezionarne una tramite GUI.
    """
    
    def __init__(self):
        """Inizializza il WebcamManager."""
        self.selected_camera = None
        self.cap = None
    
    def get_camera_names(self):
        """
        Restituisce un dizionario {index: nome leggibile della webcam}
        """
        result = subprocess.run(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = result.stdout.decode('utf-8')
        lines = output.splitlines()

        camera_dict = {}
        name = ""
        for i in range(len(lines)):
            line = lines[i].strip()
            if not line:
                continue
            if not line.startswith("/dev"):  # è il nome del device
                name = line
            elif line.startswith("/dev/video"):
                index = int(line.replace("/dev/video", "").strip())
                camera_dict[index] = name

        return camera_dict

    
    def try_camera(self, index, found, camera_names_dict):
        """
        Tenta di aprire una webcam e verifica se è disponibile.
        """
        try:
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    name = camera_names_dict.get(index, f"Webcam #{index}")
                    found.append((index, name))
                cap.release()
        except cv2.error as e:
            print(f"Errore webcam {index}: {e}")

    
    def list_available_cameras(self, max_cams=5, stop_event=None):
        """
        Elenca le webcam disponibili nel sistema, in parallelo.
        """
        found = []
        camera_names = self.get_camera_names()
        max_cams = min(max_cams, len(camera_names)) if camera_names else max_cams

        threads = []
        for i in range(max_cams):
            if stop_event and stop_event.is_set():
                break
            t = threading.Thread(target=self.try_camera, args=(i, found, camera_names))
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=1.5)  # aspetta max 2 sec per ogni thread

        return found

    
    def select_camera_gui(self):
        """
        Mostra una GUI per selezionare una webcam tra quelle disponibili.
        
        Returns:
            int: Indice della webcam selezionata o None se nessuna è selezionata.
        """
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
                cameras = self.list_available_cameras(stop_event=stop_search)
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
        root.geometry("450x450")
        root.configure(bg=GUI_BG_COLOR)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", on_close)
        
        
        label = tk.Label(root, text="Ricerca webcam in corso...", font=GUI_FONT_BOLD_TITLE, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR)
        label.pack(pady=10)
        
        frame = tk.Frame(root, bg=GUI_BG_COLOR)
        frame.pack(expand=True, fill='both')
        
        cancel_btn = tk.Button(
            root, text="Annulla", command=on_close,
            font=GUI_FONT, bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG,
            activebackground=GUI_HIGHLIGHT_COLOR, relief="flat",
            state=tk.DISABLED
        )
        cancel_btn.pack(pady=8,padx=40, fill='x')
        
        root.after(100, search_and_show)
        root.mainloop()
        
        if not selected_index:
            raise SystemExit("Nessuna webcam selezionata.")
        
        self.selected_camera = selected_index[0]
        return self.selected_camera
    
    def open_camera(self, camera_index=None):
        """
        Apre la webcam selezionata.
        
        Args:
            camera_index (int, optional): Indice della webcam da aprire. Se None, usa quella selezionata.
            
        Returns:
            cv2.VideoCapture: Oggetto VideoCapture per la webcam aperta.
        """
        if camera_index is None:
            if self.selected_camera is None:
                raise ValueError("Nessuna webcam selezionata")
            camera_index = self.selected_camera
        
        self.cap = cv2.VideoCapture(camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Impossibile aprire la webcam {camera_index}")
        
        # Imposta la risoluzione in base alla configurazione
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera_height)
        
        return self.cap
    
    def release_camera(self):
        """Rilascia la webcam se è aperta."""
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None


# Funzione di utilità per selezionare una webcam 
def select_camera_gui():
    """
    Funzione di compatibilità per selezionare una webcam.
    
    Returns:
        int: Indice della webcam selezionata.
    """
    manager = WebcamManager()
    return manager.select_camera_gui()