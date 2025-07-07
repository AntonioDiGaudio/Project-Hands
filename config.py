"""
Modulo di configurazione per l'applicazione AirMouse.
Contiene i parametri configurabili per il controllo del mouse e il riconoscimento dei gesti.
"""

# Parametri per il controllo del mouse
# Aumentato per rendere il movimento del cursore più fluido
alpha_smooth = 0.4  # Fattore di smoothing per il movimento del cursore
overscan_x = 2     # Fattore di overscan orizzontale
overscan_y = 2     # Fattore di overscan verticale
cursor_speed_multiplier = 1.0  # Moltiplicatore di velocità del cursore

# Parametri per il riconoscimento dei gesti
click_cooldown = 0.1  # Tempo di attesa tra clic consecutivi
click_distance_threshold = 25  # Soglia di distanza per il riconoscimento del clic

# Parametri per lo zoom
zoom_threshold = 100  # Soglia per il riconoscimento dello zoom
zoom_max_distance = 160  # Distanza massima per lo zoom
zoom_cooldown_time = 0.8  # Cooldown per lo zoom, tempo in secondi tra due zoom consecutivi
zoom_smooth_factor = 5  # Numero di valori da mediare per lo smoothing della distanza

# Parametri per lo slide
slide_cooldown_time = 0.01  # Tempo di cooldown per lo slide

# Nuovi parametri
use_hardware_acceleration = False  # Accelerazione hardware
camera_width = 320  # Larghezza della risoluzione della camera
camera_height = 240  # Altezza della risoluzione della camera
model_complexity = 0  # Complessità del modello (0 = leggero, 1 = pesante)
min_detection_confidence = 0.8  # Confidenza minima per il rilevamento delle mani
min_tracking_confidence = 0.8  # Confidenza minima per il tracciamento delle mani



deadzone_threshold = 7  # Zona morta, con cui si considera il movimento del mouse come nullo
# Maggior fps per una maggiore reattività
target_fps = 30
# Parametri per rendere più stabile il trascinamento
drag_release_frames = 5  # Numero di fotogrammi consecutivi oltre la soglia per rilasciare il drag
drag_release_multiplier = 2.0  # Moltiplicatore della soglia per riconoscere il rilascio del drag

