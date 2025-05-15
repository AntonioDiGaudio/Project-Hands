"""
Configurazione ottimizzata per l'applicazione AirMouse.
"""

# Parametri di controllo del mouse
alpha_smooth = 0.3  # Fattore di smoothing per il movimento del cursore
overscan_x = 1.6  # Fattore di overscan orizzontale
overscan_y = 1.6  # Fattore di overscan verticale
click_cooldown = 0.1  # Tempo di attesa tra clic consecutivi
click_distance_threshold = 25  # Soglia per il riconoscimento del clic
cursor_speed_multiplier = 1.0  # Moltiplicatore di velocità del cursore

# Parametri per lo zoom
zoom_threshold = 40  # Soglia per il riconoscimento dello zoom
zoom_cooldown_time = 0.2  # Tempo di attesa tra zoom consecutivi
zoom_smooth_factor = 5  # Fattore di smoothing per lo zoom
zoom_max_distance = 160  # Distanza massima per lo zoom

# Parametri per lo slide
slide_cooldown_time = 0.01  # Tempo di attesa tra slide consecutivi

# Parametri per la webcam
camera_width = 320  # Larghezza della webcam
camera_height = 240  # Altezza della webcam

# Parametri per MediaPipe
use_hardware_acceleration = False  # Usa l'accelerazione hardware
model_complexity = 0  # Complessità del modello (0, 1 o 2)
min_detection_confidence = 0.8  # Confidenza minima per la rilevazione
min_tracking_confidence = 0.8  # Confidenza minima per il tracciamento



# Parametri di ottimizzazione
frame_skip = 1  # Elabora 1 frame ogni N (1=no skip)
throttle_fps = 28  # Limita  FPS
enable_caching = True  # Abilita la cache per i risultati di Mediapipe
cache_frames = 3  # Numero di frame da memorizzare nella cache
