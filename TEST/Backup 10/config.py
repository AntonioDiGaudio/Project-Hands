"""
Modulo di configurazione per l'applicazione AirMouse.
Contiene i parametri configurabili per il controllo del mouse e il riconoscimento dei gesti.
"""

# Parametri per il controllo del mouse
alpha_smooth = 0.25  # Fattore di smoothing per il movimento del cursore
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
