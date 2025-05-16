"""
Modulo per il riconoscimento dei gesti delle mani.
Fornisce funzionalità per riconoscere gesti specifici come clic, zoom e scorrimento.
"""

import numpy as np
import time


class GestureRecognizer:
    """
    Classe per riconoscere i gesti delle mani.
    Fornisce metodi per riconoscere gesti specifici come clic, zoom e scorrimento.
    """
    
    def __init__(self, config):
        """
        Inizializza il GestureRecognizer con le configurazioni specificate.
        
        Args:
            config: Oggetto di configurazione con i parametri per il riconoscimento dei gesti.
        """
        self.config = config
        
        # Parametri per lo zoom
        self.zoom_distances = []
        self.zoom_smooth_factor = 5
        self.last_zoom_distance = None
        self.zoom_cooldown = 0.0
        self.zoom_cooldown_time = 0.5
        
        # Parametri per lo slide
        self.slide_cooldown = 0.0
        self.slide_cooldown_time = 0.01

        self.previous_index_thumb_distance = None
        self.block_cursor_movement = False


    def should_block_cursor(self, current_distance):
        """
        Determina se il cursore deve essere bloccato mentre l'indice si avvicina al pollice.
        """
        block = False
        if self.previous_index_thumb_distance is not None:
            delta = self.previous_index_thumb_distance - current_distance
            if delta > 0.8:  #se blocca troppo tardi abbassa, se blocca troppo presto alza
                block = True

        self.previous_index_thumb_distance = current_distance
        self.block_cursor_movement = block
        return block

    
    def recognize_click(self, index_thumb_distance, last_click_time):
        """
        Riconosce il gesto di clic in base alla distanza tra indice e pollice.
        
        Args:
            index_thumb_distance (float): Distanza tra indice e pollice.
            last_click_time (float): Timestamp dell'ultimo clic.
            
        Returns:
            tuple: (click_recognized, new_last_click_time)
        """
        if index_thumb_distance < self.config.click_distance_threshold:
            if time.time() - last_click_time >= self.config.click_cooldown:
                return True, time.time()
        return False, last_click_time
    
    def recognize_drag(self, index_thumb_distance, drag_active, last_click_time):
        """
        Riconosce il gesto di trascinamento in base alla distanza tra indice e pollice.
        
        Args:
            index_thumb_distance (float): Distanza tra indice e pollice.
            drag_active (bool): Se True, il trascinamento è già attivo.
            last_click_time (float): Timestamp dell'ultimo clic.
            
        Returns:
            tuple: (drag_start, drag_end, new_drag_active, new_last_click_time)
        """
        drag_start = False
        drag_end = False
        
        if index_thumb_distance < self.config.click_distance_threshold:
            if not drag_active and time.time() - last_click_time >= self.config.click_cooldown:
                drag_start = True
                drag_active = True
                last_click_time = time.time()
        else:
            if drag_active:
                drag_end = True
                drag_active = False
        
        return drag_start, drag_end, drag_active, last_click_time
    
    def recognize_right_click(self, pinky_up, last_right_click_time, cooldown=1.0):
        """
        Riconosce il gesto di clic destro in base allo stato del mignolo.
        
        Args:
            pinky_up (bool): Se True, il mignolo è alzato.
            last_right_click_time (float): Timestamp dell'ultimo clic destro.
            cooldown (float): Tempo di attesa tra clic destri consecutivi.
            
        Returns:
            tuple: (right_click_recognized, new_last_right_click_time)
        """
        if not pinky_up and time.time() - last_right_click_time >= cooldown:
            return True, time.time()
        return False, last_right_click_time
    
    def recognize_slide(self, palm_position, frame_width, frame_height):
        """
        Riconosce il gesto di scorrimento in base alla posizione del palmo.
        
        Args:
            palm_position (tuple): Posizione del palmo (x, y).
            frame_width (int): Larghezza del frame.
            frame_height (int): Altezza del frame.
            
        Returns:
            tuple: (slide_recognized, direction, new_slide_cooldown)
        """
        if time.time() - self.slide_cooldown < self.slide_cooldown_time:
            return False, None, self.slide_cooldown
        
        palm_x, palm_y = palm_position
        direction = "center"
        margin_x = frame_width * 0.3
        margin_y = frame_height * 0.3
        
        if palm_y < margin_y:
            direction = "up"
        elif palm_y > frame_height - margin_y:
            direction = "down"
        elif palm_x < margin_x:
            direction = "left"
        elif palm_x > frame_width - margin_x:
            direction = "right"
        
        if direction != "center":
            self.slide_cooldown = time.time()
            return True, direction, self.slide_cooldown
        
        return False, None, self.slide_cooldown
    
    def recognize_zoom(self, right_index, left_index, zoom_gesture_active):
        """
        Riconosce il gesto di zoom in base alla distanza tra gli indici delle due mani.
        
        Args:
            right_index (tuple): Posizione dell'indice della mano destra.
            left_index (tuple): Posizione dell'indice della mano sinistra.
            zoom_gesture_active (bool): Se True, il gesto per lo zoom è attivo.
            
        Returns:
            tuple: (zoom_recognized, zoom_in, zoom_out, smoothed_distance, new_last_zoom_distance, new_zoom_cooldown)
        """
        if not zoom_gesture_active:
            self.last_zoom_distance = None
            return False, False, False, 0, None, self.zoom_cooldown
        
        # Calcola la distanza tra gli indici
        current_distance = np.sqrt((right_index[0] - left_index[0])**2 + (right_index[1] - left_index[1])**2)
        
        # Aggiungi la distanza corrente alla lista per lo smoothing
        self.zoom_distances.append(current_distance)
        if len(self.zoom_distances) > self.zoom_smooth_factor:
            self.zoom_distances.pop(0)
        
        # Calcola la distanza media per lo smoothing
        smoothed_distance = np.mean(self.zoom_distances) if self.zoom_distances else 0
        
        # Verifica se è possibile eseguire lo zoom
        if smoothed_distance >= self.config.zoom_max_distance:
            return False, False, False, smoothed_distance, self.last_zoom_distance, self.zoom_cooldown
        
        if self.last_zoom_distance is None:
            self.last_zoom_distance = smoothed_distance
            return False, False, False, smoothed_distance, self.last_zoom_distance, self.zoom_cooldown
        
        # Verifica il cooldown
        if time.time() - self.zoom_cooldown < self.config.zoom_cooldown_time:
            return False, False, False, smoothed_distance, self.last_zoom_distance, self.zoom_cooldown
        
        # Calcola la differenza di distanza
        zoom_diff = smoothed_distance - self.last_zoom_distance
        
        # Verifica se la differenza è significativa
        if abs(zoom_diff) <= self.config.zoom_threshold:
            return False, False, False, smoothed_distance, self.last_zoom_distance, self.zoom_cooldown
        
        # Determina il tipo di zoom
        zoom_in = zoom_diff > 0
        zoom_out = zoom_diff < 0
        
        # Aggiorna il cooldown e la distanza precedente
        self.zoom_cooldown = time.time()
        self.last_zoom_distance = smoothed_distance
        
        return True, zoom_in, zoom_out, smoothed_distance, self.last_zoom_distance, self.zoom_cooldown

