import tkinter as tk
from tkinter import ttk
import config
import os

PROFILE_PATH = "Profiles/settings.txt"

def save_settings():
    with open("Profiles/settings.txt", "w") as f:
        f.write(f"alpha_smooth = {config.alpha_smooth}\n")
        f.write(f"overscan_x = {config.overscan_x}\n")
        f.write(f"overscan_y = {config.overscan_y}\n")
        f.write(f"click_cooldown = {config.click_cooldown}\n")
        f.write(f"click_distance_threshold = {config.click_distance_threshold}\n")
        f.write(f"cursor_speed_multiplier = {config.cursor_speed_multiplier}\n")
        

def load_settings(sliders):
    if not os.path.exists(PROFILE_PATH):
        print("File di impostazioni non trovato. Caricamento impostazioni predefinite.")
        return

    # Carica i parametri dal file settings.txt
    with open(PROFILE_PATH, "r") as f:
        values = dict(line.strip().split(" = ") for line in f if line.strip())  # Leggi e formatta le linee
    
    # Aggiorna i valori di config con i valori letti
    config.alpha_smooth = float(values.get("alpha_smooth", 0.3))
    config.overscan_x = float(values.get("overscan_x", 1.6))
    config.overscan_y = float(values.get("overscan_y", 1.6))
    config.click_cooldown = float(values.get("click_cooldown", 0.1))
    config.click_distance_threshold = float(values.get("click_distance_threshold", 25))
    config.cursor_speed_multiplier = float(values.get("cursor_speed_multiplier", 1.0))

    # Aggiorna la GUI per riflettere i nuovi valori
    sliders['alpha_smooth'].set(int(round(config.alpha_smooth / 0.05)))
    sliders['cursor_speed_multiplier'].set(int(round(config.cursor_speed_multiplier)))
    sliders['overscan_x'].set(int(round(config.overscan_x)))
    sliders['overscan_y'].set(int(round(config.overscan_y)))
    sliders['click_distance_threshold'].set(int(round(config.click_distance_threshold / 25)))
    sliders['click_cooldown'].set(int(round(config.click_cooldown / 0.05)))

    print("Impostazioni caricate.")

   


def update_sensitivity(val):
    config.alpha_smooth = float(val)

def update_overscan_x(val):
    config.overscan_x = float(val)

def update_overscan_y(val):
    config.overscan_y = float(val)

def update_click_threshold(val):
    config.click_distance_threshold = float(val)

def update_click_cooldown(val):
    config.click_cooldown = float(val)

def update_speed(val):
    config.cursor_speed_multiplier = float(val)

def create_settings_gui():
    root = tk.Tk()
    root.title("Impostazioni Controllo Mouse")
    root.geometry("500x650")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill='both', expand=True)

    # Sliders dictionary to access them for setting values later
    sliders = {}

    tk.Label(frm, text="Sensibilità cursore (1-10)").pack()
    sliders['alpha_smooth'] = tk.Scale(frm, from_=1, to=10, orient='horizontal', tickinterval=1,
        command=lambda v: update_sensitivity(float(v) * 0.05))
    sliders['alpha_smooth'].pack(fill='x')

    tk.Label(frm, text="Velocità cursore (1-10)").pack()
    sliders['cursor_speed_multiplier'] = tk.Scale(frm, from_=1, to=10, orient='horizontal', tickinterval=1,
        command=lambda v: update_speed(float(v)))
    sliders['cursor_speed_multiplier'].pack(fill='x')

    tk.Label(frm, text="Sensibilità orizzontale (1-10)").pack()
    sliders['overscan_x'] = tk.Scale(frm, from_=1, to=10, orient='horizontal', tickinterval=1,
        command=lambda v: update_overscan_x(float(v)))
    sliders['overscan_x'].pack(fill='x')

    tk.Label(frm, text="Sensibilità verticale (1-10)").pack()
    sliders['overscan_y'] = tk.Scale(frm, from_=1, to=10, orient='horizontal', tickinterval=1,
        command=lambda v: update_overscan_y(float(v)))
    sliders['overscan_y'].pack(fill='x')

    tk.Label(frm, text="Soglia distanza click (1-10)").pack()
    sliders['click_distance_threshold'] = tk.Scale(frm, from_=1, to=10, orient='horizontal', tickinterval=1,
        command=lambda v: update_click_threshold(int(v) * 25))
    sliders['click_distance_threshold'].pack(fill='x')

    tk.Label(frm, text="Cooldown click (1-10)").pack()
    sliders['click_cooldown'] = tk.Scale(frm, from_=1, to=10, orient='horizontal', tickinterval=1,
        command=lambda v: update_click_cooldown(float(v) * 0.05))
    sliders['click_cooldown'].pack(fill='x')

    # Carica le impostazioni dal file subito dopo la creazione della GUI
    load_settings(sliders)

    # Funzione di reset
    def reset_values():
        default_values = {
            'alpha_smooth': 0.3,
            'overscan_x': 1.6,
            'overscan_y': 1.6,
            'click_cooldown': 0.1,
            'click_distance_threshold': 25,
            'cursor_speed_multiplier': 1.0,
        }

        # Applica i valori e aggiorna sliders
        update_sensitivity(default_values['alpha_smooth'])
        update_overscan_x(default_values['overscan_x'])
        update_overscan_y(default_values['overscan_y'])
        update_click_cooldown(default_values['click_cooldown'])
        update_click_threshold(default_values['click_distance_threshold'])
        update_speed(default_values['cursor_speed_multiplier'])

        sliders['alpha_smooth'].set(int(round(default_values['alpha_smooth'] / 0.05)))
        sliders['cursor_speed_multiplier'].set(int(round(default_values['cursor_speed_multiplier'])))
        sliders['overscan_x'].set(int(round(default_values['overscan_x'])))
        sliders['overscan_y'].set(int(round(default_values['overscan_y'])))
        sliders['click_cooldown'].set(int(round(default_values['click_cooldown'] / 0.05)))
        sliders['click_distance_threshold'].set(int(round(default_values['click_distance_threshold'] / 25)))

    # Bottone Reset
    ttk.Button(frm, text="Reset", command=reset_values).pack(pady=10)

    # Bottoni Salva e Carica
    btn_frame = ttk.Frame(frm)
    btn_frame.pack(pady=20, fill='x')

    ttk.Button(btn_frame, text="Salva profilo", command=save_settings).pack(side='left', padx=10, expand=True, fill='x')
    ttk.Button(btn_frame, text="Carica profilo", command=lambda: load_settings(sliders)).pack(side='left', padx=10, expand=True, fill='x')

    def on_close():
        root.quit()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()