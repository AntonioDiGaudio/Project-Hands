#import sys
import tkinter as tk
from tkinter import ttk
import config
import os
from shared_state import set_running, get_running
from gui_theme import (
    GUI_FONT, GUI_FONT_BOLD, GUI_BG_COLOR, GUI_FG_COLOR,
    GUI_BUTTON_BG, GUI_BUTTON_FG, GUI_HIGHLIGHT_COLOR,
    GUI_WINDOW_SIZE
)






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

from gui_theme import (
    GUI_FONT, GUI_FONT_BOLD, GUI_BG_COLOR, GUI_FG_COLOR,
    GUI_BUTTON_BG, GUI_BUTTON_FG, GUI_HIGHLIGHT_COLOR,
    GUI_WINDOW_SIZE
)

def create_settings_gui():
    global running
    root = tk.Tk()
    root.title("AirMouse")
    root.geometry("700x850")
    root.configure(bg=GUI_BG_COLOR)
    root.resizable(False, False)

    frm = tk.Frame(root, bg=GUI_BG_COLOR, padx=10, pady=10)
    frm.pack(fill='both', expand=True)

    sliders = {}

    def make_label(text):
        tk.Label(frm, text=text, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, font=GUI_FONT).pack(pady=(10, 0))

    def make_scale(name, from_, to, tick, command):
        sliders[name] = tk.Scale(
            frm, from_=from_, to=to, orient='horizontal', tickinterval=tick,
            command=command, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, font=GUI_FONT,
            highlightbackground=GUI_BG_COLOR, troughcolor=GUI_BUTTON_BG
        )
        sliders[name].pack(fill='x', pady=(0, 10))

    make_label("Sensibilità cursore (1-10)")
    make_scale('alpha_smooth', 1, 10, 1, lambda v: update_sensitivity(float(v) * 0.05))

    make_label("Velocità cursore (1-10)")
    make_scale('cursor_speed_multiplier', 1, 10, 1, lambda v: update_speed(float(v)))

    make_label("Sensibilità orizzontale (1-10)")
    make_scale('overscan_x', 1, 10, 1, lambda v: update_overscan_x(float(v)))

    make_label("Sensibilità verticale (1-10)")
    make_scale('overscan_y', 1, 10, 1, lambda v: update_overscan_y(float(v)))

    make_label("Soglia distanza click (1-10)")
    make_scale('click_distance_threshold', 1, 10, 1, lambda v: update_click_threshold(int(v) * 25))

    make_label("Cooldown click (1-10)")
    make_scale('click_cooldown', 1, 10, 1, lambda v: update_click_cooldown(float(v) * 0.05))

    load_settings(sliders)

    def reset_values():
        default_values = {
            'alpha_smooth': 0.3,
            'overscan_x': 1.6,
            'overscan_y': 1.6,
            'click_cooldown': 0.1,
            'click_distance_threshold': 25,
            'cursor_speed_multiplier': 1.0,
        }
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
    tk.Button(frm, text="Reset", command=reset_values,
              bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
              activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(pady=10, fill='x')

    # Bottoni Salva e Carica
    btn_frame = tk.Frame(frm, bg=GUI_BG_COLOR)
    btn_frame.pack(pady=20, fill='x')

    tk.Button(btn_frame, text="Salva profilo", command=save_settings,
              bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
              activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(side='left', padx=10, expand=True, fill='x')

    tk.Button(btn_frame, text="Carica profilo", command=lambda: load_settings(sliders),
              bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
              activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(side='left', padx=10, expand=True, fill='x')
    
        # Bottone Info con popup
    def show_info_popup():
        info_win = tk.Toplevel(root)
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

    # Bottone per aprire popup info
    tk.Button(frm, text="ℹ Info gesture", command=show_info_popup,
              bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG, font=GUI_FONT,
              activebackground=GUI_HIGHLIGHT_COLOR, relief="flat").pack(pady=10, fill='x')


   
    def on_close():
        set_running(False)
        root.quit()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
