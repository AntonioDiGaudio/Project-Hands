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
    
    def update_zoom_threshold(self, val):
        """
        Aggiorna la soglia per il riconoscimento dello zoom.
        
        Args:
            val (str): Valore della soglia.
        """
        config.zoom_threshold = float(val)
    
    def update_slide_threshold(self, val):
        """
        Aggiorna la soglia per il riconoscimento dello slide.
        
        Args:
            val (str): Valore della soglia.
        """
        config.slide_threshold = float(val) / 10  # Mappato da 1-10 a 0.1-1.0
    
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
            f.write(f"slide_threshold = {config.slide_threshold}\n")
            f.write(f"zoom_max_distance = {config.zoom_max_distance}\n")
    
    def load_settings(self):
        """Carica le impostazioni dal file di configurazione."""
        default_settings = """alpha_smooth = 0.3
overscan_x = 1.6
overscan_y = 1.6
click_cooldown = 0.1
click_distance_threshold = 25
cursor_speed_multiplier = 1.0
zoom_threshold = 40
slide_threshold = 0.2
zoom_max_distance = 160
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
            config.slide_threshold = float(values.get("slide_threshold", 0.2))
            config.zoom_max_distance = float(values.get("zoom_max_distance", 160))
            
            # Aggiorna la GUI per riflettere i nuovi valori
            self.sliders['alpha_smooth'].set(int(round(config.alpha_smooth / 0.05)))
            self.sliders['cursor_speed_multiplier'].set(int(round(config.cursor_speed_multiplier)))
            self.sliders['overscan_x'].set(int(round(config.overscan_x)))
            self.sliders['overscan_y'].set(int(round(config.overscan_y)))
            self.sliders['click_distance_threshold'].set(int(round(config.click_distance_threshold / 25)))
            self.sliders['click_cooldown'].set(int(round(config.click_cooldown / 0.05)))
            self.sliders['zoom_threshold'].set(int(round(config.zoom_threshold)))
            self.sliders['slide_threshold'].set(int(round(config.slide_threshold * 10)))
            self.sliders['zoom_max_distance'].set(int(round(config.zoom_max_distance / 20)))
            
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
            'slide_threshold': 0.2,
            'zoom_max_distance': 160,
        }
        
        self.update_sensitivity(default_values['alpha_smooth'])
        self.update_overscan_x(default_values['overscan_x'])
        self.update_overscan_y(default_values['overscan_y'])
        self.update_click_cooldown(default_values['click_cooldown'])
        self.update_click_threshold(default_values['click_distance_threshold'])
        self.update_speed(default_values['cursor_speed_multiplier'])
        self.update_zoom_threshold(default_values['zoom_threshold'])
        self.update_slide_threshold(default_values['slide_threshold'] * 10)
        self.update_zoom_max_distance(default_values['zoom_max_distance'] / 20)
        
        self.sliders['alpha_smooth'].set(int(round(default_values['alpha_smooth'] / 0.05)))
        self.sliders['cursor_speed_multiplier'].set(int(round(default_values['cursor_speed_multiplier'])))
        self.sliders['overscan_x'].set(int(round(default_values['overscan_x'])))
        self.sliders['overscan_y'].set(int(round(default_values['overscan_y'])))
        self.sliders['click_cooldown'].set(int(round(default_values['click_cooldown'] / 0.05)))
        self.sliders['click_distance_threshold'].set(int(round(default_values['click_distance_threshold'] / 25)))
        self.sliders['zoom_threshold'].set(int(round(default_values['zoom_threshold'])))
        self.sliders['slide_threshold'].set(int(round(default_values['slide_threshold'] * 10)))
        self.sliders['zoom_max_distance'].set(int(round(default_values['zoom_max_distance'] / 20)))
    
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
        self.root.geometry("500x300")
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
        
        make_label("Soglia slide (1-10)")
        make_scale('slide_threshold', 1, 10, 1, lambda v: self.update_slide_threshold(float(v)))
        
        make_label("Distanza massima zoom (1-10)")
        make_scale('zoom_max_distance', 1, 10, 1, lambda v: self.update_zoom_max_distance(float(v)))
        
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
