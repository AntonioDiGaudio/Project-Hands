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
    GUI_BUTTON_BG, GUI_BUTTON_FG, GUI_HIGHLIGHT_COLOR,GUI_FONT_BOLD_TITLE,GUI_FONT_BOLD_SUBTITLE
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
        self.info_window = None
    
    def update_zoom_threshold(self, val):
        """
        Aggiorna la soglia per il riconoscimento dello zoom.
        
        Args:
            val (str): Valore della soglia.
        """
        config.zoom_threshold = float(val)
        
    def update_zoom_cooldown_time(self, val):
        """
        Aggiorna tempo cooldown dello zoom.
        
        Args:
            val (str): Valore della soglia.
        """
        config.zoom_cooldown_time = float(val)

    def update_zoom_smooth_factor(self, val):
        """
        Aggiorna il fattore di smoothing dello zoom.
        
        Args:
            val (str): Valore della soglia.
        """
        config.zoom_smooth_factor = float(val) 
        
    
    def update_slide_cooldown_time(self, val):
        """
        Aggiorna il tempo di cooldown per lo slide.
        
        Args:
            val (str): Valore del tempo di cooldown.
        """
        config.slide_cooldown_time = float(val) *0.1 # Mappato da 0.1  a 10
    
    def update_zoom_max_distance(self, val):
        """
        Aggiorna la distanza massima per lo zoom.
        
        Args:
            val (str): Valore della distanza massima.
        """
        config.zoom_max_distance = float(val) * 5  # Mappato da   a 50-500
    
    def update_sensitivity(self, val):
        """
        Aggiorna la sensibilità del cursore.
        
        Args:
            val (str): Valore della sensibilità.
        """
        config.alpha_smooth = float(val) /10
    
    def update_overscan_x(self, val):
        """
        Aggiorna l'overscan orizzontale.
        
        Args:
            val (str): Valore dell'overscan orizzontale.
        """
        config.overscan_x = float(val) /10
    
    def update_overscan_y(self, val):
        """
        Aggiorna l'overscan verticale.
        
        Args:
            val (str): Valore dell'overscan verticale.
        """
        config.overscan_y = float(val) /10
    
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
        config.cursor_speed_multiplier = float(val) /10
    
    def update_hand_confidence(self, val):
        """
        Aggiorna il valore di confidenza per il riconoscimento delle mani.
        
        Args:
            val (str): Valore della confidenza.
        """
        confidence = float(val) / 100  # Mappato da   a 0.5-1.0
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
            f.write(f"zoom_cooldown_time = {config.zoom_cooldown_time}\n")
            f.write(f"zoom_smooth_factor = {config.zoom_smooth_factor}\n")
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
        default_settings = {
            'alpha_smooth': 0.5,
            'overscan_x': 1.8,
            'overscan_y': 1.9,
            'click_cooldown': 0.05,
            'click_distance_threshold': 20.0,
            'cursor_speed_multiplier': 1.1,
            'zoom_threshold': 10.0,
            'zoom_cooldown_time': 1.1,
            'zoom_smooth_factor': 2.0,
            'slide_cooldown_time': 0.0,
            'zoom_max_distance': 425.0,
            'use_hardware_acceleration': False,
            'camera_width': 320,
            'camera_height': 240,
            'model_complexity': 0,
            'min_detection_confidence': 0.9,
            'min_tracking_confidence': 0.9,
        }
        
        
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
            config.zoom_cooldown_time = float(values.get("zoom_cooldown_time", 0.5))
            config.zoom_smooth_factor = float(values.get("zoom_smooth_factor", 5))
            
            # Supporto per la retrocompatibilità: slide_threshold -> slide_cooldown_time
            if "slide_threshold" in values:
                config.slide_cooldown_time = float(values.get("slide_threshold", 0.2))
            else:
                config.slide_cooldown_time = float(values.get("slide_cooldown_time", 0.01))
                
            config.zoom_max_distance = float(values.get("zoom_max_distance", 160))
            config.use_hardware_acceleration = bool(int(values.get("use_hardware_acceleration", 0)))
            config.camera_width = int(values.get("camera_width", 320))
            config.camera_height = int(values.get("camera_height", 240))
            config.model_complexity = int(values.get("model_complexity", 0))
            config.min_detection_confidence = float(values.get("min_detection_confidence", 0.8))
            config.min_tracking_confidence = float(values.get("min_tracking_confidence", 0.8))
            
            # Aggiorna la GUI per riflettere i nuovi valori
            self.sliders['alpha_smooth'].set(int(round(config.alpha_smooth *10)))
            self.sliders['cursor_speed_multiplier'].set(int(round(config.cursor_speed_multiplier*10)))
            self.sliders['overscan_x'].set(int(round(config.overscan_x *10)))
            self.sliders['overscan_y'].set(int(round(config.overscan_y *10)))
            self.sliders['click_distance_threshold'].set(int(round(config.click_distance_threshold / 5)))
            self.sliders['click_cooldown'].set(int(round(config.click_cooldown / 0.05)))
            self.sliders['zoom_threshold'].set(int(round(config.zoom_threshold)))
            self.sliders['zoom_cooldown_time'].set(int(round(config.zoom_cooldown_time *10)))
            self.sliders['zoom_smooth_factor'].set(int(round(config.zoom_smooth_factor)))
            self.sliders['slide_cooldown_time'].set(int(round(config.slide_cooldown_time *10)))
            self.sliders['zoom_max_distance'].set(int(round(config.zoom_max_distance / 5)))
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
            'alpha_smooth': 0.5,
            'overscan_x': 1.8,
            'overscan_y': 1.9,
            'click_cooldown': 0.05,
            'click_distance_threshold': 20.0,
            'cursor_speed_multiplier': 1.1,
            'zoom_threshold': 10.0,
            'zoom_cooldown_time': 1.1,
            'zoom_smooth_factor': 2.0,
            'slide_cooldown_time': 0.0,
            'zoom_max_distance': 425.0,
            'use_hardware_acceleration': False,
            'camera_width': 320,
            'camera_height': 240,
            'model_complexity': 0,
            'min_detection_confidence': 0.9,
            'min_tracking_confidence': 0.9,
        }
        
        self.update_sensitivity(default_values['alpha_smooth'])
        self.update_overscan_x(default_values['overscan_x'])
        self.update_overscan_y(default_values['overscan_y'])
        self.update_click_cooldown(default_values['click_cooldown'])
        self.update_click_threshold(default_values['click_distance_threshold'])
        self.update_speed(default_values['cursor_speed_multiplier'])
        self.update_zoom_threshold(default_values['zoom_threshold'])
        self.update_zoom_cooldown_time(default_values['zoom_cooldown_time'])
        self.update_zoom_smooth_factor(default_values['zoom_smooth_factor'])
        self.update_slide_cooldown_time(default_values['slide_cooldown_time'] / 0.01)
        self.update_zoom_max_distance(default_values['zoom_max_distance'] / 20)
        
        # Aggiorna i valori dei controlli
        self.sliders['alpha_smooth'].set(int(round(default_values['alpha_smooth']*10)))
        self.sliders['cursor_speed_multiplier'].set(int(round(default_values['cursor_speed_multiplier']*10)))
        self.sliders['overscan_x'].set(int(round(default_values['overscan_x']*10)))
        self.sliders['overscan_y'].set(int(round(default_values['overscan_y']*10)))
        self.sliders['click_cooldown'].set(int(round(default_values['click_cooldown'] / 0.05)))
        self.sliders['click_distance_threshold'].set(int(round(default_values['click_distance_threshold'] / 25)))
        self.sliders['zoom_threshold'].set(int(round(default_values['zoom_threshold'])))
        self.sliders['zoom_cooldown_time'].set(int(round(default_values['zoom_cooldown_time']*10)))
        self.sliders['zoom_smooth_factor'].set(int(round(default_values['zoom_smooth_factor'])))
        self.sliders['slide_cooldown_time'].set(int(round(default_values['slide_cooldown_time'] / 0.01)))
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
        if self.info_window is not None and self.info_window.winfo_exists():
            self.info_window.lift()  # Porta la finestra in primo piano
            self.info_window.focus_force()  # Dà il focus alla finestra
            return
    
        # Crea una nuova finestra
        self.info_window = tk.Toplevel(self.root)
        self.info_window.title("Istruzioni gesture e guida alle impostazioni di AirMouse")
        self.info_window.configure(bg=GUI_BG_COLOR)
        self.info_window.geometry("650x450")
        self.info_window.resizable(True, True)
        
        # Configura la funzione da chiamare quando la finestra viene chiusa
        self.info_window.protocol("WM_DELETE_WINDOW", self._on_info_window_close)
            
        container = tk.Frame(self.info_window, bg=GUI_BG_COLOR)
        container.pack(fill='both', expand=True)

        canvas = tk.Canvas(container, bg=GUI_BG_COLOR, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=GUI_BG_COLOR)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")



        tk.Label(scrollable_frame, text="GESTURE DISPONIBILI", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT_BOLD_TITLE, justify="center").pack(padx=20, pady=(10, 5))

        gesture_info = {
            "Click tasto sinistro": "Avvicina l'indice mano destra e il pollice mano destra",
            "Trascinamento": "Tieni premuto l'indice della mano destra e il pollice della mano destra",
            "Click tasto destro": "Abbassa il mignolo della mano destra",
            "Zoom in": "Allontana gli indici della mano destra e sinistra",
            "Zoom out": "Avvicina gli indici della mano destra e sinistra",
            "Frecce direzionali": "Chiudi la mano sinistra a pugno e muovila nella direzione desiderata"
        }

        for title, desc in gesture_info.items():
            tk.Label(scrollable_frame, text=title, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                     font=GUI_FONT_BOLD_SUBTITLE, justify="center").pack(padx=20, pady=(8, 0))
            tk.Label(scrollable_frame, text=desc, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                     font=GUI_FONT, justify="center", wraplength=550).pack(padx=20, pady=(0, 5))

        tk.Frame(scrollable_frame, height=2, bg=GUI_HIGHLIGHT_COLOR).pack(padx=15, fill='x', pady=15)

    
        tk.Label(scrollable_frame, text="GUIDA ALLE IMPOSTAZIONI", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT_BOLD_TITLE, justify="center").pack(padx=20, pady=(10, 5))

        settings_info = {
            "Sensibilità cursore": "Regola quanto il movimento del cursore viene smussato per ridurre tremolii. Più il valore è basso, più il movimento è fluido ma reattivo. Più è alto, più il cursore si muove in modo lento e stabile.",
            "Velocità cursore": "Moltiplica la velocità generale del cursore. Aumentando questo valore il cursore si muoverà più velocemente rispetto al movimento della mano.",
            "Sensibilità orizzontale": "Estende l'area utile in orizzontale per il controllo del cursore, aumentando la sensibilità ai movimenti laterali.",
            "Sensibilità verticale": "Estende l'area utile in verticale per il controllo del cursore, aumentando la sensibilità ai movimenti verticali.",
            "Soglia distanza click": "Imposta quanto le dita devono avvicinarsi per essere riconosciute come un clic. Più basso il valore, più sensibile sarà il rilevamento del gesto.",
            "Cooldown click": "Imposta un intervallo in secondi tra due clic consecutivi per evitare clic involontari.",
            "Soglia zoom": "Determina la variazione minima nella distanza tra le due mani necessaria per attivare uno zoom. Valori più alti rendono lo zoom meno sensibile.",
            "Distanza massima zoom": "Imposta la distanza tra i due indici oltre la quale il gesto di zoom viene ignorato.",
            "Cooldown zoom": "Imposta quanto tempo deve passare tra due azioni di zoom per evitarne l'attivazione involontaria.",
            "Fattore di smoothing di zoom": "Numero di letture recenti usate per calcolare la distanza media tra gli indici, rendendo lo zoom più stabile.",
            "Tempo cooldown slide": "Imposta un tempo tra due movimenti di slide nelle 4 direzioni.",
            "Confidenza riconoscimento mani": "Imposta la soglia di affidabilità per considerare rilevata una mano. Valori alti riducono i falsi positivi, ma possono appesantire l'esecuzione del programma.",
            "Accelerazione hardware": "Se abilitato, utilizza l'accelerazione hardware (se supportata) per migliorare le prestazioni, ma può appesantire l'esecuzione del programma. In particolare delega il compito computazionale alla GPU, in questo momemnto è in fase Beta e non è del tutto implementata",
            "Risoluzione camera": "Definisce la risoluzione del feed video della fotocamera. Valori più alti aumentano la precisione ma anche il carico di calcolo.",
            "Complessità del modello": "Determina la complessità della rete neurale che rileva le mani. Il modello 0 è veloce e leggero ma meno accurato, il modello 1 è più preciso ma più pesante."
        }

        for title, desc in settings_info.items():
            tk.Label(scrollable_frame, text=title, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                     font=GUI_FONT_BOLD_SUBTITLE, justify="center").pack(padx=20, pady=(8, 0))
            tk.Label(scrollable_frame, text=desc, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                     font=GUI_FONT, justify="center", wraplength=550).pack(padx=20, pady=(0, 5))
            
        
        tk.Frame(scrollable_frame, height=2, bg=GUI_HIGHLIGHT_COLOR).pack(padx=15, fill='x', pady=15)

        tk.Label(scrollable_frame, text="INFORMAZIONI ALL'USO", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT_BOLD_TITLE, justify="center").pack(padx=20, pady=(10, 5))
        


        info_utili_text = (
            "Quando si vuole aggiornare i seguenti parametri:\n\n"
            "• Complessità del modello\n"
            "• Risoluzione camera\n"
            "• Confidenza riconoscimento mani\n"
            "• Accelerazione hardware (Beta)\n\n"
            "Sarà necessario seguire i seguenti passaggi nell'ordine indicato:\n\n"
            "•  Mettere i valori desiderati e salvare il profilo\n"
            "•  Chiudere l'app\n"
            "•  Riaprire l'app\n\n"
            "Così da avere i valori desiderati aggiornati.\n\n"
            "Per quanto riguarda tutti gli altri parametri, modificando gli slider "
            "si modificheranno in tempo reale senza bisogno di salvare e riavviare l'app."
        )


        tk.Label(scrollable_frame, text=info_utili_text, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT, justify="center", wraplength=550).pack(padx=20, pady=(10, 5))

        
        
        
        tk.Frame(scrollable_frame, height=2, bg=GUI_HIGHLIGHT_COLOR).pack(padx=15, fill='x', pady=15)


        tk.Label(scrollable_frame, text="CONSIGLI", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT_BOLD_TITLE, justify="center").pack(padx=20, pady=(10, 5))
        


        info_consigli_text=(
            "Per avere le variabili di default, cliccare RESET.\n\n"
            "Se non si riesce ad arrivare in tutte le parti dello schemro, sopratutto quelle esterne, si consigli di modifcare i primi 4 valori, in particolare la Velocità del cursore\n"
        )


        tk.Label(scrollable_frame, text=info_consigli_text, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT, justify="center", wraplength=550).pack(padx=20, pady=(10, 5))

        tk.Frame(scrollable_frame, height=2, bg=GUI_HIGHLIGHT_COLOR).pack(padx=15, fill='x', pady=15)



        tk.Button(scrollable_frame, text="Chiudi", command=self.info_window.destroy,
                  bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
                  activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(pady=(20, 20))
    

    def _on_info_window_close(self):
        """Gestisce la chiusura della finestra di informazioni."""
        if self.info_window is not None:
            self.info_window.destroy()
            self.info_window = None


    def create_gui(self):
        """Crea l'interfaccia grafica delle impostazioni."""
        self.root = tk.Tk()
        self.root.title("AirMouse")
        self.root.geometry("650x850")  
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
        
        def make_section_title(text):
            tk.Label(
                frm,
                text=text,
                bg=GUI_BG_COLOR,
                fg=GUI_FG_COLOR,
                font=GUI_FONT_BOLD_TITLE,
                justify="center",
                wraplength=550
            ).pack(padx=20, pady=(20, 10))
        
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

        make_section_title("CONFIGURAZIONI MOUSE")
        
        make_label("Sensibilità cursore")
        make_scale('alpha_smooth', 0, 100, 10, lambda v: self.update_sensitivity(float(v)))

        make_label("Velocità cursore")
        make_scale('cursor_speed_multiplier', 0, 100, 10, lambda v: self.update_speed(float(v)))

        make_label("Sensibilità orizzontale")
        make_scale('overscan_x', 0, 100, 10, lambda v: self.update_overscan_x(float(v)))

        make_label("Sensibilità verticale")
        make_scale('overscan_y', 0, 100, 10, lambda v: self.update_overscan_y(float(v)))
        
        make_label("Soglia distanza click")
        make_scale('click_distance_threshold', 0, 100, 10, lambda v: self.update_click_threshold(int(v) * 5))
        
        make_label("Cooldown click")
        make_scale('click_cooldown', 1, 10, 1, lambda v: self.update_click_cooldown(float(v) * 0.05))
        
        make_label("Soglia zoom")
        make_scale('zoom_threshold', 0, 100, 10, lambda v: self.update_zoom_threshold(float(v)))

        make_label("Distanza massima zoom")
        make_scale('zoom_max_distance', 0, 100, 10, lambda v: self.update_zoom_max_distance(float(v)*5))

        make_label("Cooldown zoom")
        make_scale('zoom_cooldown_time', 0, 100, 10, lambda v: self.update_zoom_cooldown_time(float(v)*0.1))

        make_label("Fattore di smoothing di zoom")
        make_scale('zoom_smooth_factor', 1, 10, 1, lambda v: self.update_zoom_smooth_factor(float(v)))
        
        make_label("Tempo cooldown slide")
        make_scale('slide_cooldown_time', 0, 100, 10, lambda v: self.update_slide_cooldown_time(float(v)*0.1))
        

        
        # Separatore
        tk.Frame(frm, height=2, bg=GUI_HIGHLIGHT_COLOR).pack(fill='x', pady=10)
        
        make_section_title("CONFIGURAZIONI PRESTAZIONI")
        make_label("Confidenza riconoscimento mani")
        make_scale('hand_confidence', 50, 100, 10, lambda v: self.update_hand_confidence(float(v)))
        
        # Accelerazione hardware
        hw_frame = tk.Frame(frm, bg=GUI_BG_COLOR)
        hw_frame.pack(pady=5)
        
        tk.Label(hw_frame, text="Accelerazione hardware (Beta)", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, justify="center",
                font=GUI_FONT).pack(pady=(0, 5))
        
        self.hw_accel_var = tk.IntVar()
        hw_checkbox = tk.Checkbutton(
            hw_frame, variable=self.hw_accel_var, 
            command=self.update_hardware_acceleration,
            bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
            selectcolor=GUI_BG_COLOR, activebackground=GUI_BG_COLOR
        )
        hw_checkbox.pack()
        
        # Risoluzione camera
        res_frame = tk.Frame(frm, bg=GUI_BG_COLOR)
        res_frame.pack(fill='x', pady=10)
        
        tk.Label(res_frame, text="Risoluzione camera", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
                font=GUI_FONT).pack(anchor='center', padx=5, pady=(0, 5))
        
        self.resolution_var = tk.StringVar(value="320x240")
        
        for res in ["160x120", "320x240", "640x480"]:
            rb = tk.Radiobutton(
                res_frame, text=res, value=res, 
                variable=self.resolution_var, 
                command=self.update_camera_resolution,
                bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
                selectcolor=GUI_BG_COLOR, activebackground=GUI_BG_COLOR
            )
            rb.pack(anchor='center', padx=20)
        
        # Scelta modello
        model_frame = tk.Frame(frm, bg=GUI_BG_COLOR)
        model_frame.pack(fill='x', pady=10)
        
        tk.Label(model_frame, text="Complessità modello", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
                font=GUI_FONT).pack(anchor='center', padx=5, pady=(0, 5))
        
        self.model_var = tk.StringVar(value="0")
        
        rb1 = tk.Radiobutton(
            model_frame, text="Leggero (0)", value="0", 
            variable=self.model_var, 
            command=self.update_model_complexity,
            bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
            selectcolor=GUI_BG_COLOR, activebackground=GUI_BG_COLOR
        )
        rb1.pack(anchor='center', padx=20)
        
        rb2 = tk.Radiobutton(
            model_frame, text="Pesante (1)", value="1", 
            variable=self.model_var, 
            command=self.update_model_complexity,
            bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, 
            selectcolor=GUI_BG_COLOR, activebackground=GUI_BG_COLOR
        )
        rb2.pack(anchor='center', padx=20)

        # Separatore
        tk.Frame(frm, height=2, bg=GUI_HIGHLIGHT_COLOR).pack(fill='x', pady=10)

        
        
        # Carica le impostazioni
        self.load_settings()
        
        # Bottone Reset
        tk.Button(frm, text="Resetta valori", command=self.reset_values,
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
        tk.Button(frm, text="ℹ Info", command=self.show_info_popup,
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