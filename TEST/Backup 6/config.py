"""
Modulo di configurazione per l'applicazione AirMouse.
Contiene i parametri configurabili per il controllo del mouse e il riconoscimento dei gesti.
"""

# Parametri per il controllo del mouse
alpha_smooth = 0.45  # Fattore di smoothing per il movimento del cursore
overscan_x = 1.2     # Fattore di overscan orizzontale
overscan_y = 1.2     # Fattore di overscan verticale
cursor_speed_multiplier = 1.0  # Moltiplicatore di velocità del cursore

# Parametri per il riconoscimento dei gesti
click_cooldown = 0.05  # Tempo di attesa tra clic consecutivi
click_distance_threshold = 25  # Soglia di distanza per il riconoscimento del clic

# Parametri per lo zoom
zoom_threshold = 40  # Soglia per il riconoscimento dello zoom
zoom_max_distance = 160  # Distanza massima per lo zoom

# Parametri per lo slide
slide_threshold = 0.2  # Soglia per il riconoscimento dello slide
