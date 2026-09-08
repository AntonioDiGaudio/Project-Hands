"""
Gestione della webcam.

Tre problemi risolti rispetto alla versione precedente:

1. **Portabilita'.** L'enumerazione usava `v4l2-ctl`, che esiste solo su Linux:
   su Windows lanciava un'eccezione a ogni avvio. Ora c'e' un percorso per
   piattaforma con fallback a sondaggio degli indici.

2. **Latenza.** Senza `CAP_PROP_BUFFERSIZE=1` il driver accoda i frame: se
   l'elaborazione e' piu' lenta della camera si finisce a lavorare su immagini
   vecchie di centinaia di ms e il cursore sembra "in ritardo". Con il thread di
   cattura si tiene sempre e solo l'ultimo frame disponibile.

3. **Scelta del backend.** Misurato su questa macchina: DSHOW 16.9 fps contro
   MSMF 30.1 fps sulla stessa camera. Il backend giusto cambia da PC a PC,
   quindi in modalita' "auto" vengono provati in ordine e si tiene il primo che
   consegna davvero un frame.
"""

import platform
import threading
import time
import tkinter as tk
from tkinter import messagebox

import cv2

import config
from gui_theme import (
    GUI_FONT, GUI_BG_COLOR, GUI_FG_COLOR,
    GUI_BUTTON_BG, GUI_BUTTON_FG, GUI_HIGHLIGHT_COLOR, GUI_FONT_BOLD_TITLE,
)
from shared_state import get_running, set_running

_SYSTEM = platform.system()

_BACKENDS = {
    "msmf": getattr(cv2, "CAP_MSMF", 0),
    "dshow": getattr(cv2, "CAP_DSHOW", 0),
    "v4l2": getattr(cv2, "CAP_V4L2", 0),
    "avfoundation": getattr(cv2, "CAP_AVFOUNDATION", 0),
    "any": cv2.CAP_ANY,
}


def _backend_order():
    """Backend da provare, in ordine di preferenza per la piattaforma."""
    name = str(getattr(config, "camera_backend", "auto")).lower()
    if name != "auto" and name in _BACKENDS:
        return [_BACKENDS[name], cv2.CAP_ANY]
    if _SYSTEM == "Windows":
        # MSMF prima: misurato quasi il doppio degli fps di DSHOW.
        return [_BACKENDS["msmf"], _BACKENDS["dshow"], cv2.CAP_ANY]
    if _SYSTEM == "Linux":
        return [_BACKENDS["v4l2"], cv2.CAP_ANY]
    if _SYSTEM == "Darwin":
        return [_BACKENDS["avfoundation"], cv2.CAP_ANY]
    return [cv2.CAP_ANY]


class FrameGrabber:
    """
    Legge dalla webcam in un thread dedicato tenendo solo l'ultimo frame.

    Cosi' l'inferenza non e' mai in attesa della camera e non elabora mai un
    frame vecchio: se il modello e' piu' lento della camera, i frame in eccesso
    vengono semplicemente scartati invece di accodarsi.
    """

    def __init__(self, cap):
        self.cap = cap
        self._lock = threading.Lock()
        self._frame = None
        self._seq = 0
        self._running = False
        self._thread = None
        self._new_frame = threading.Event()
        self.dropped = 0

    def start(self):
        if self._running:
            return self
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="webcam-grabber")
        self._thread.start()
        return self

    def _loop(self):
        while self._running:
            ok, frame = self.cap.read()
            if not ok:
                # La camera puo' essere stata staccata: non bruciare la CPU.
                time.sleep(0.01)
                continue
            with self._lock:
                if self._frame is not None:
                    self.dropped += 1
                self._frame = frame
                self._seq += 1
            self._new_frame.set()

    def read(self, timeout=1.0):
        """
        Restituisce (ok, frame, seq) consumando l'ultimo frame disponibile.

        Blocca fino a `timeout` se non c'e' ancora niente di nuovo.
        """
        if not self._new_frame.wait(timeout):
            return False, None, self._seq
        with self._lock:
            frame = self._frame
            self._frame = None
            seq = self._seq
            self._new_frame.clear()
        if frame is None:
            return False, None, seq
        return True, frame, seq

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._new_frame.set()


class WebcamManager:
    """Selezione, apertura e rilascio della webcam."""

    def __init__(self):
        self.selected_camera = None
        self.cap = None
        self.grabber = None
        self.backend_used = None

    # -- enumerazione ------------------------------------------------------
    @staticmethod
    def get_camera_names():
        """
        Nomi leggibili delle webcam, quando la piattaforma li espone.

        Non e' essenziale: se fallisce si ricade su "Webcam #n".
        """
        names = {}
        if _SYSTEM == "Linux":
            try:
                import subprocess
                out = subprocess.run(
                    ["v4l2-ctl", "--list-devices"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=3,
                ).stdout.decode("utf-8", "replace")
                current = ""
                for line in out.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if not stripped.startswith("/dev"):
                        current = stripped
                    elif stripped.startswith("/dev/video"):
                        try:
                            names[int(stripped.replace("/dev/video", ""))] = current
                        except ValueError:
                            pass
            except Exception:
                pass
        elif _SYSTEM == "Windows":
            try:
                import subprocess
                ps = (
                    "Get-CimInstance Win32_PnPEntity | "
                    "Where-Object { $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' } | "
                    "Select-Object -ExpandProperty Name"
                )
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                ).stdout.decode("utf-8", "replace")
                for i, line in enumerate(l.strip() for l in out.splitlines() if l.strip()):
                    names[i] = line
            except Exception:
                pass
        return names

    def try_camera(self, index, found, names):
        """Verifica che la camera all'indice dato consegni davvero un frame."""
        for backend in _backend_order():
            cap = None
            try:
                cap = cv2.VideoCapture(index, backend)
                if not cap.isOpened():
                    continue
                ok, _ = cap.read()
                if ok:
                    found.append((index, names.get(index, "Webcam #%d" % index)))
                    return
            except cv2.error:
                continue
            finally:
                if cap is not None:
                    cap.release()

    def list_available_cameras(self, max_cams=4, stop_event=None):
        """Elenca le webcam funzionanti, sondando gli indici in parallelo."""
        found = []
        names = self.get_camera_names()

        threads = []
        for i in range(max_cams):
            if stop_event is not None and stop_event.is_set():
                break
            t = threading.Thread(target=self.try_camera, args=(i, found, names),
                                 daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=4.0)

        found.sort(key=lambda item: item[0])
        return found

    # -- apertura ----------------------------------------------------------
    def open_camera(self, camera_index=None):
        """Apre la webcam e avvia il thread di cattura."""
        if camera_index is None:
            camera_index = self.selected_camera
        if camera_index is None:
            raise ValueError("Nessuna webcam selezionata")

        self.release_camera()

        cap = None
        for backend in _backend_order():
            candidate = cv2.VideoCapture(camera_index, backend)
            if candidate.isOpened():
                self._configure(candidate)
                ok, _ = candidate.read()
                if ok:
                    cap = candidate
                    self.backend_used = backend
                    break
            candidate.release()

        if cap is None:
            raise RuntimeError("Impossibile aprire la webcam %s" % camera_index)

        self.selected_camera = camera_index
        self.cap = cap
        self.grabber = FrameGrabber(cap).start()
        return self.grabber

    @staticmethod
    def _configure(cap):
        """Applica risoluzione, codec e profondita' del buffer."""
        fourcc = getattr(config, "camera_fourcc", "") or ""
        if len(fourcc) == 4:
            try:
                # MJPG evita il trasferimento raw su USB: su USB 2.0 e su
                # Raspberry Pi e' spesso la differenza fra 10 e 30 fps.
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
            except Exception:
                pass
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera_height)
        try:
            # Buffer a 1: nessun frame vecchio in coda, nessuna latenza accumulata.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, int(config.camera_buffer_size))
        except Exception:
            pass
        try:
            cap.set(cv2.CAP_PROP_FPS, float(config.target_fps))
        except Exception:
            pass

    def actual_resolution(self):
        if self.cap is None:
            return (0, 0)
        return (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    def release_camera(self):
        if self.grabber is not None:
            self.grabber.stop()
            self.grabber = None
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    # -- GUI di selezione --------------------------------------------------
    def select_camera_gui(self):
        """Finestra di selezione della webcam. Restituisce l'indice scelto."""
        if not get_running():
            return None

        selected = []
        stop_search = threading.Event()

        def on_select(index):
            selected.append(index)
            stop_search.set()
            root.destroy()

        def show_cameras(cameras):
            label.config(text="Seleziona una webcam:")
            for widget in frame.winfo_children():
                widget.destroy()
            for idx, name in cameras:
                tk.Button(
                    frame, text=name, command=lambda i=idx: on_select(i),
                    font=GUI_FONT, bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG,
                    activebackground=GUI_HIGHLIGHT_COLOR, relief="flat",
                    wraplength=380, justify="center",
                ).pack(pady=5, padx=10, fill="x")

        def search_and_show():
            cancel_btn.config(state=tk.NORMAL)

            def worker():
                cameras = self.list_available_cameras(stop_event=stop_search)
                if stop_search.is_set():
                    return
                if not cameras:
                    root.after(0, lambda: label.config(text="Nessuna webcam trovata."))
                    return
                root.after(0, lambda: show_cameras(cameras))

            threading.Thread(target=worker, daemon=True).start()

        def on_close():
            stop_search.set()
            set_running(False)
            root.destroy()

        root = tk.Tk()
        root.title("AirMouse")
        root.geometry("450x450")
        root.configure(bg=GUI_BG_COLOR)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", on_close)

        label = tk.Label(root, text="Ricerca webcam in corso...",
                         font=GUI_FONT_BOLD_TITLE, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR)
        label.pack(pady=10)

        frame = tk.Frame(root, bg=GUI_BG_COLOR)
        frame.pack(expand=True, fill="both")

        cancel_btn = tk.Button(
            root, text="Annulla", command=on_close,
            font=GUI_FONT, bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG,
            activebackground=GUI_HIGHLIGHT_COLOR, relief="flat", state=tk.DISABLED,
        )
        cancel_btn.pack(pady=8, padx=40, fill="x")

        root.after(100, search_and_show)
        root.mainloop()

        if not selected:
            raise SystemExit("Nessuna webcam selezionata.")

        self.selected_camera = selected[0]
        return self.selected_camera


def select_camera_gui():
    """Helper di compatibilita'."""
    return WebcamManager().select_camera_gui()
