"""
Modulo per l'interfaccia grafica delle impostazioni dell'applicazione AirMouse.
Fornisce funzionalità per modificare e salvare le impostazioni.
"""

import tkinter as tk
from tkinter import ttk
import config
import os
from shared_state import set_running
from gui_theme import (
    GUI_FONT, GUI_BG_COLOR, GUI_FG_COLOR,
    GUI_BUTTON_BG, GUI_BUTTON_FG, GUI_HIGHLIGHT_COLOR
)


# Percorso del file delle impostazioni
PROFILE_PATH = "Profiles/settings.txt"


class SettingsGUI:
    """
    Classe per gestire l'interfaccia grafica delle impostazioni.
    Fornisce metodi per modificare e salvare le impostazioni.
    """
    
    def __init__(self):
        """Inizializza l'interfaccia grafica delle impostazioni."""
        self.root = None
        self.sliders = {}
        self.checkboxes = {}
        self.radio_buttons = {}
        self.resolution_var = None
        self.model_var = None
        self.hw_accel_var = None
        self.hand_confidence_var = None
    
    def update_zoom_threshold(self, val):
        """
        Aggiorna la soglia per il riconoscimento dello zoom.
        
        Args:
            val (str): Valore della soglia.
        """
        config.zoom_threshold = float(val)
    
    def update_slide_cooldown_time(self, val):
        """
        Aggiorna il tempo di cooldown per lo slide.
        
        Args:
            val (str): Valore del tempo di cooldown.
        """
        config.slide_cooldown_time = float(val) / 10  # Mappato da 1-10 a 0.1-1.0
    
    def update_zoom_max_distance(self, val):
        """
        Aggiorna la distanza massima per lo zoom.
        
        Args:
            val (str): Valore della distanza massima.
        """
        config.zoom_max_distance = float(val) * 20  # Mappato da 1-10 a 20-200
    
    def update_sensitivity(self, val):
        """
        Aggiorna la sensibilità del cursore.
        
        Args:
            val (str): Valore della sensibilità.
        """
        config.alpha_smooth = float(val)
    
    def update_overscan_x(self, val):
        """
        Aggiorna l'overscan orizzontale.
        
        Args:
            val (str): Valore dell'overscan orizzontale.
        """
        config.overscan_x = float(val)
    
    def update_overscan_y(self, val):
        """
        Aggiorna l'overscan verticale.
        
        Args:
            val (str): Valore dell'overscan verticale.
        """
        config.overscan_y = float(val)
    
    def update_click_threshold(self, val):
        """
        Aggiorna la soglia per il riconoscimento del clic.
        
        Args:
            val (str): Valore della soglia.
        """
        config.click_distance_threshold = float(val)
    
    def update_click_cooldown(self, val):
        """
        Aggiorna il tempo di attesa tra clic consecutivi.
        
        Args:
            val (str): Valore del tempo di attesa.
        """
        config.click_cooldown = float(val)
    
    def update_speed(self, val):
        """
        Aggiorna la velocità del cursore.
        
        Args:
            val (str): Valore della velocità.
        """
        config.cursor_speed_multiplier = float(val)
    
    def update_hand_confidence(self, val):
        """
        Aggiorna il valore di confidenza per il riconoscimento delle mani.
        
        Args:
            val (str): Valore della confidenza.
        """
        confidence = float(val) / 100  # Mappato da 50-100 a 0.5-1.0
        config.min_detection_confidence = confidence
        config.min_tracking_confidence = confidence
    
    def update_hardware_acceleration(self):
        """
        Aggiorna lo stato dell'accelerazione hardware.
        """
        config.use_hardware_acceleration = bool(self.hw_accel_var.get())
    
    def update_camera_resolution(self):
        """
        Aggiorna la risoluzione della camera.
        """
        resolution_map = {
            "160x120": (160, 120),
            "320x240": (320, 240),
            "640x480": (640, 480)
        }
        selected = self.resolution_var.get()
        if selected in resolution_map:
            config.camera_width, config.camera_height = resolution_map[selected]
    
    def update_model_complexity(self):
        """
        Aggiorna la complessità del modello.
        """
        config.model_complexity = int(self.model_var.get())
    
    def save_settings(self):
        """Salva le impostazioni correnti nel file di configurazione."""
        # Assicurati che la cartella Profiles esista
        if not os.path.exists("Profiles"):
            os.makedirs("Profiles")
        
        with open(PROFILE_PATH, "w") as f:
            f.write(f"alpha_smooth = {config.alpha_smooth}\n")
            f.write(f"overscan_x = {config.overscan_x}\n")
            f.write(f"overscan_y = {config.overscan_y}\n")
            f.write(f"click_cooldown = {config.click_cooldown}\n")
            f.write(f"click_distance_threshold = {config.click_distance_threshold}\n")
            f.write(f"cursor_speed_multiplier = {config.cursor_speed_multiplier}\n")
            f.write(f"zoom_threshold = {config.zoom_threshold}\n")
            f.write(f"slide_cooldown_time = {config.slide_cooldown_time}\n")
            f.write(f"zoom_max_distance = {config.zoom_max_distance}\n")
            f.write(f"use_hardware_acceleration = {int(config.use_hardware_acceleration)}\n")
            f.write(f"camera_width = {config.camera_width}\n")
            f.write(f"camera_height = {config.camera_height}\n")
            f.write(f"model_complexity = {config.model_complexity}\n")
            f.write(f"min_detection_confidence = {config.min_detection_confidence}\n")
            f.write(f"min_tracking_confidence = {config.min_tracking_confidence}\n")
    
    def load_settings(self):
        """Carica le impostazioni dal file di configurazione."""
        default_settings = """alpha_smooth = 0.3
overscan_x = 1.6
overscan_y = 1.6
click_cooldown = 0.1
click_distance_threshold = 25
cursor_speed_multiplier = 1.0
zoom_threshold = 40
slide_cooldown_time = 0.2
zoom_max_distance = 160
use_hardware_acceleration = 0
camera_width = 320
camera_height = 240
model_complexity = 0
min_detection_confidence = 0.8
min_tracking_confidence = 0.8
"""
        
        # Assicurati che la cartella Profiles esista
        if not os.path.exists("Profiles"):
            os.makedirs("Profiles")
            print("Cartella 'Profiles' creata.")
        
        # Crea il file settings.txt se non esiste
        if not os.path.isfile(PROFILE_PATH):
            with open(PROFILE_PATH, "w") as f:
                f.write(default_settings)
            print("File 'settings.txt' creato con valori predefiniti.")
        
        try:
            # Carica i parametri dal file settings.txt
            with open(PROFILE_PATH, "r") as f:
                values = dict(line.strip().split(" = ") for line in f if line.strip())
            
            # Aggiorna i valori di config con i valori letti
            config.alpha_smooth = float(values.get("alpha_smooth", 0.3))
            config.overscan_x = float(values.get("overscan_x", 1.6))
            config.overscan_y = float(values.get("overscan_y", 1.6))
            config.click_cooldown = float(values.get("click_cooldown", 0.1))
            config.click_distance_threshold = float(values.get("click_distance_threshold", 25))
            config.cursor_speed_multiplier = float(values.get("cursor_speed_multiplier", 1.0))
            config.zoom_threshold = float(values.get("zoom_threshold", 40))
            
            # Supporto per la retrocompatibilità: slide_threshold -> slide_cooldown_time
            if "slide_threshold" in values:
                config.slide_cooldown_time = float(values.get("slide_threshold", 0.2))
            else:
                config.slide_cooldown_time = float(values.get("slide_cooldown_time", 0.2))
                
            config.zoom_max_distance = float(values.get("zoom_max_distance", 160))
            config.use_hardware_acceleration = bool(int(values.get("use_hardware_acceleration", 0)))
            config.camera_width = int(values.get("camera_width", 320))
            config.camera_height = int(values.get("camera_height", 240))
            config.model_complexity = int(values.get("model_complexity", 0))
            config.min_detection_confidence = float(values.get("min_detection_confidence", 0.8))
            config.min_tracking_confidence = float(values.get("min_tracking_confidence", 0.8))
            
            # Aggiorna la GUI per riflettere i nuovi valori
            self.sliders['alpha_smooth'].set(int(round(config.alpha_smooth / 0.05)))
            self.sliders['cursor_speed_multiplier'].set(int(round(config.cursor_speed_multiplier)))
            self.sliders['overscan_x'].set(int(round(config.overscan_x)))
            self.sliders['overscan_y'].set(int(round(config.overscan_y)))
            self.sliders['click_distance_threshold'].set(int(round(config.click_distance_threshold / 25)))
            self.sliders['click_cooldown'].set(int(round(config.click_cooldown / 0.05)))
            self.sliders['zoom_threshold'].set(int(round(config.zoom_threshold)))
            self.sliders['slide_cooldown_time'].set(int(round(config.slide_cooldown_time * 10)))
            self.sliders['zoom_max_distance'].set(int(round(config.zoom_max_distance / 20)))
            self.sliders['hand_confidence'].set(int(round(config.min_detection_confidence * 100)))
            
            # Aggiorna i controlli per le nuove impostazioni
            self.hw_accel_var.set(int(config.use_hardware_acceleration))
            
            # Imposta la risoluzione della camera
            resolution = f"{config.camera_width}x{config.camera_height}"
            if resolution in ["160x120", "320x240", "640x480"]:
                self.resolution_var.set(resolution)
            else:
                self.resolution_var.set("320x240")  # Default
            
            # Imposta la complessità del modello
            self.model_var.set(str(config.model_complexity))
            
            print("Impostazioni caricate.")
        except Exception as e:
            print(f"Errore durante il caricamento delle impostazioni: {e}, uso dei valori predefiniti")
            self.reset_values()
    
    def reset_values(self):
        """Ripristina i valori predefiniti delle impostazioni."""
        default_values = {
            'alpha_smooth': 0.3,
            'overscan_x': 1.6,
            'overscan_y': 1.6,
            'click_cooldown': 0.1,
            'click_distance_threshold': 25,
            'cursor_speed_multiplier': 1.0,
            'zoom_threshold': 40,
            'slide_cooldown_time': 0.2,
            'zoom_max_distance': 160,
            'use_hardware_acceleration': False,
            'camera_width': 320,
            'camera_height': 240,
            'model_complexity': 0,
            'min_detection_confidence': 0.8,
            'min_tracking_confidence': 0.8,
        }
        
        self.update_sensitivity(default_values['alpha_smooth'])
        self.update_overscan_x(default_values['overscan_x'])
        self.update_overscan_y(default_values['overscan_y'])
        self.update_click_cooldown(default_values['click_cooldown'])
        self.update_click_threshold(default_values['click_distance_threshold'])
        self.update_speed(default_values['cursor_speed_multiplier'])
        self.update_zoom_threshold(default_values['zoom_threshold'])
        self.update_slide_cooldown_time(default_values['slide_cooldown_time'] * 10)
        self.update_zoom_max_distance(default_values['zoom_max_distance'] / 20)
        
        # Aggiorna i valori dei controlli
        self.sliders['alpha_smooth'].set(int(round(default_values['alpha_smooth'] / 0.05)))
        self.sliders['cursor_speed_multiplier'].set(int(round(default_values['cursor_speed_multiplier'])))
        self.sliders['overscan_x'].set(int(round(default_values['overscan_x'])))
        self.sliders['overscan_y'].set(int(round(default_values['overscan_y'])))
        self.sliders['click_cooldown'].set(int(round(default_values['click_cooldown'] / 0.05)))
        self.sliders['click_distance_threshold'].set(int(round(default_values['click_distance_threshold'] / 25)))
        self.sliders['zoom_threshold'].set(int(round(default_values['zoom_threshold'])))
        self.sliders['slide_cooldown_time'].set(int(round(default_values['slide_cooldown_time'] * 10)))
        self.sliders['zoom_max_distance'].set(int(round(default_values['zoom_max_distance'] / 20)))
        self.sliders['hand_confidence'].set(int(round(default_values['min_detection_confidence'] * 100)))
        
        # Aggiorna i controlli per le nuove impostazioni
        self.hw_accel_var.set(0)
        self.resolution_var.set("320x240")
        self.model_var.set("0")
        
        # Aggiorna i valori di config
        config.use_hardware_acceleration = default_values['use_hardware_acceleration']
        config.camera_width = default_values['camera_width']
        config.camera_height = default_values['camera_height']
        config.model_complexity = default_values['model_complexity']
        config.min_detection_confidence = default_values['min_detection_confidence']
        config.min_tracking_confidence = default_values['min_tracking_confidence']
    
    def show_info_popup(self):
        """Mostra un popup con le informazioni sulle gesture disponibili."""
        info_win = tk.Toplevel(self.root)
        info_win.title("Istruzioni gesture")
        info_win.configure(bg=GUI_BG_COLOR)
        info_win.geometry("600x400")
        info_win.resizable(False, False)
        
        info_text = (
            "Gesture disponibili:\n\n"
            "Click sinistro: Avvicina indice e pollice (mano destra)\n"
            "Trascina sinistro: Tieni premuto indice e pollice (mano destra)\n"
            "Click destro: Abbassa il mignolo (mano destra)\n"
            "Zoom in: Allontana indici (mano destra e sinistra)\n"
            "Zoom out: Avvicina indici (mano destra e sinistra)\n"
            "Frecce direzionali: Chiudi la mano sinistra a pugno e muovila nella direzione desiderata"
        )
        
        tk.Label(info_win, text=info_text, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT, justify="left", wraplength=550).pack(padx=20, pady=20)
        
        tk.Button(info_win, text="Chiudi", command=info_win.destroy,
                  bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
                  activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(pady=(0, 20))
    
    def create_gui(self):
        """Crea l'interfaccia grafica delle impostazioni."""
        self.root = tk.Tk()
        self.root.title("AirMouse")
        self.root.geometry("500x700")  # Aumentata l'altezza per le nuove impostazioni
        self.root.configure(bg=GUI_BG_COLOR)
        self.root.resizable(False, False)
        
        # Creazione del contenitore principale con scrollbar
        main_frame = tk.Frame(self.root, bg=GUI_BG_COLOR)
        main_frame.pack(fill='both', expand=True)
        
        # Creazione della canvas e scrollbar
        canvas = tk.Canvas(main_frame, bg=GUI_BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        
        # Frame che conterrà tutti i widget (scrollabile)
        scrollable_frame = tk.Frame(canvas, bg=GUI_BG_COLOR)
        
        # Configurazione della canvas
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="n")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Layout della canvas e scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Abilitazione dello scrolling con la rotellina del mouse
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Frame centrale per contenere tutti i widget
        center_frame = tk.Frame(scrollable_frame, bg=GUI_BG_COLOR)
        center_frame.pack(expand=True, fill='both', padx=20)
        
        frm = center_frame
        frm.configure(padx=10, pady=10)
        
        self.sliders = {}
        
        def make_label(text):
            tk.Label(frm, text=text, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
                    font=GUI_FONT).pack(pady=(10, 0), anchor='center')
        
        def make_scale(name, from_, to, tick, command):
            frame = tk.Frame(frm, bg=GUI_BG_COLOR)
            frame.pack(fill='x', pady=(0, 10), expand=True)
            
            self.sliders[name] = tk.Scale(
                frame, from_=from_, to=to, orient='horizontal', tickinterval=tick,
                command=command, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, font=GUI_FONT,
                highlightbackground=GUI_BG_COLOR, troughcolor=GUI_BUTTON_BG
            )
            self.sliders[name].pack(fill='x', expand=True)
        
        # Creazione dei controlli
        make_label("Sensibilità cursore (1-10)")
        make_scale('alpha_smooth', 1, 10, 1, lambda v: self.update_sensitivity(float(v) * 0.05))
        
        make_label("Velocità cursore (1-10)")
        make_scale('cursor_speed_multiplier', 1, 10, 1, lambda v: self.update_speed(float(v)))
        
        make_label("Sensibilità orizzontale (1-10)")
        make_scale('overscan_x', 1, 10, 1, lambda v: self.update_overscan_x(float(v)))
        
        make_label("Sensibilità verticale (1-10)")
        make_scale('overscan_y', 1, 10, 1, lambda v: self.update_overscan_y(float(v)))
        
        make_label("Soglia distanza click (1-10)")
        make_scale('click_distance_threshold', 1, 10, 1, lambda v: self.update_click_threshold(int(v) * 25))
        
        make_label("Cooldown click (1-10)")
        make_scale('click_cooldown', 1, 10, 1, lambda v: self.update_click_cooldown(float(v) * 0.05))
        
        make_label("Soglia zoom (1-10)")
        make_scale('zoom_threshold', 1, 10, 1, lambda v: self.update_zoom_threshold(float(v)))
        
        make_label("Tempo cooldown slide (1-10)")
        make_scale('slide_cooldown_time', 1, 10, 1, lambda v: self.update_slide_cooldown_time(float(v)))
        
        make_label("Distanza massima zoom (1-10)")
        make_scale('zoom_max_distance', 1, 10, 1, lambda v: self.update_zoom_max_distance(float(v)))
        
        make_label("Confidenza riconoscimento mani (50-100)")
        make_scale('hand_confidence', 50, 100, 10, lambda v: self.update_hand_confidence(float(v)))
        
        # Separatore
        tk.Frame(frm, height=2, bg=GUI_HIGHLIGHT_COLOR).pack(fill='x', pady=10)
        
        # Nuove impostazioni
        
        # Accelerazione hardware
        hw_frame = tk.Frame(frm, bg=GUI_BG_COLOR)
        hw_frame.pack(fill='x', pady=5)
        
        tk.Label(hw_frame, text="Accelerazione hardware:", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
                font=GUI_FONT).pack(side='left', padx=5)
        
        self.hw_accel_var = tk.IntVar()
        hw_checkbox = tk.Checkbutton(
            hw_frame, variable=self.hw_accel_var, 
            command=self.update_hardware_acceleration,
            bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
            selectcolor=GUI_BG_COLOR, activebackground=GUI_BG_COLOR
        )
        hw_checkbox.pack(side='left')
        
        # Risoluzione camera
        res_frame = tk.Frame(frm, bg=GUI_BG_COLOR)
        res_frame.pack(fill='x', pady=10)
        
        tk.Label(res_frame, text="Risoluzione camera:", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
                font=GUI_FONT).pack(anchor='w', padx=5, pady=(0, 5))
        
        self.resolution_var = tk.StringVar(value="320x240")
        
        for res in ["160x120", "320x240", "640x480"]:
            rb = tk.Radiobutton(
                res_frame, text=res, value=res, 
                variable=self.resolution_var, 
                command=self.update_camera_resolution,
                bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
                selectcolor=GUI_BG_COLOR, activebackground=GUI_BG_COLOR
            )
            rb.pack(anchor='w', padx=20)
        
        # Scelta modello
        model_frame = tk.Frame(frm, bg=GUI_BG_COLOR)
        model_frame.pack(fill='x', pady=10)
        
        tk.Label(model_frame, text="Complessità modello:", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
                font=GUI_FONT).pack(anchor='w', padx=5, pady=(0, 5))
        
        self.model_var = tk.StringVar(value="0")
        
        rb1 = tk.Radiobutton(
            model_frame, text="Leggero (0)", value="0", 
            variable=self.model_var, 
            command=self.update_model_complexity,
            bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
            selectcolor=GUI_BG_COLOR, activebackground=GUI_BG_COLOR
        )
        rb1.pack(anchor='w', padx=20)
        
        rb2 = tk.Radiobutton(
            model_frame, text="Pesante (1)", value="1", 
            variable=self.model_var, 
            command=self.update_model_complexity,
            bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
            selectcolor=GUI_BG_COLOR, activebackground=GUI_BG_COLOR
        )
        rb2.pack(anchor='w', padx=20)
        
        # Carica le impostazioni
        self.load_settings()
        
        # Bottone Reset
        tk.Button(frm, text="Reset", command=self.reset_values,
                  bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
                  activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(pady=10, fill='x', padx=100)
        
        # Bottoni Salva e Carica
        btn_frame = tk.Frame(frm, bg=GUI_BG_COLOR)
        btn_frame.pack(pady=20, fill='x')
        
        tk.Button(btn_frame, text="Salva profilo", command=self.save_settings,
                  bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
                  activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(side='left', padx=10, expand=True, fill='x')
        
        tk.Button(btn_frame, text="Carica profilo", command=self.load_settings,
                  bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
                  activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(side='left', padx=10, expand=True, fill='x')
        
        # Bottone per aprire popup info
        tk.Button(frm, text="ℹ Info gesture", command=self.show_info_popup,
                  bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
                  activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(pady=10, fill='x', padx=100)
        
        def on_close():
            set_running(False)
            self.root.quit()
            self.root.destroy()
        
        self.root.protocol("WM_DELETE_WINDOW", on_close)
        self.root.mainloop()


# Funzione di utilità per creare l'interfaccia grafica delle impostazioni
def create_settings_gui():
    """
    Funzione di compatibilità per creare l'interfaccia grafica delle impostazioni.
    """
    gui = SettingsGUI()
    gui.create_gui()