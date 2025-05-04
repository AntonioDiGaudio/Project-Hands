"""
Modulo per il controllo del mouse tramite gesti delle mani.
Fornisce funzionalità per muovere il cursore, fare clic e gestire lo zoom.
"""

import pyautogui
import numpy as np
import time


class MouseController:
    """
    Classe per controllare il mouse tramite gesti delle mani.
    Fornisce metodi per muovere il cursore, fare clic e gestire lo zoom.
    """
    
    def __init__(self, config):
        """
        Inizializza il MouseController con le configurazioni specificate.
        
        Args:
            config: Oggetto di configurazione con i parametri per il controllo del mouse.
        """
        self.config = config
        pyautogui.FAILSAFE = False
        self.screen_w, self.screen_h = pyautogui.size()
        
        # Parametri del filtro di Kalman
        self.xk = np.array([self.screen_w / 2, self.screen_h / 2, 0, 0], dtype=np.float32)
        self.Pk = np.eye(4, dtype=np.float32) * 300
        self.F = np.eye(4, dtype=np.float32)
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
        self.Q = np.diag([3, 3, 12, 12]).astype(np.float32)
        self.R = np.diag([25, 25]).astype(np.float32)
        self.I4 = np.eye(4, dtype=np.float32)
        
        self.smooth_x, self.smooth_y = self.xk[0], self.xk[1]
        self.click_held = False
        self.right_click_cooldown = 0.0
        self.last_click_time = 0.0
        
        # Parametri per lo zoom
        self.last_zoom_distance = None
        self.zoom_cooldown = 0.0
        self.zoom_cooldown_time = 0.5
        self.zoom_distances = []
        self.zoom_smooth_factor = 5
        
        # Parametri per il click
        self.click_start_time = 0.0
        self.click_detection_active = False
    
    def move_cursor(self, ix, iy, frame_width, frame_height):
        """
        Muove il cursore del mouse in base alle coordinate dell'indice.
        
        Args:
            ix (int): Coordinata x dell'indice.
            iy (int): Coordinata y dell'indice.
            frame_width (int): Larghezza del frame.
            frame_height (int): Altezza del frame.
        """
        # Mappatura schermo con sensibilità e velocità in tempo reale
        half_w, half_h = frame_width / 2, frame_height / 2
        ix_centered = (ix - half_w) * self.config.overscan_x + half_w
        iy_centered = (iy - half_h) * self.config.overscan_y + half_h
        ix_clipped = np.clip(ix_centered, 0, frame_width - 1)
        iy_clipped = np.clip(iy_centered, 0, frame_height - 1)
        
        zx = np.interp(ix_clipped, [0, frame_width - 1], [0, self.screen_w - 1]) * self.config.cursor_speed_multiplier
        zy = np.interp(iy_clipped, [0, frame_height - 1], [0, self.screen_h - 1]) * self.config.cursor_speed_multiplier
        
        # Smoothing del movimento
        self.smooth_x += self.config.alpha_smooth * (zx - self.smooth_x)
        self.smooth_y += self.config.alpha_smooth * (zy - self.smooth_y)
        
        pyautogui.moveTo(int(self.smooth_x), int(self.smooth_y), _pause=False)
    
    def handle_click(self, dist, drag_mode_enabled=True, enable_right_click=True, pinky_up=True):
        """
        Gestisce i clic del mouse in base alla distanza tra indice e pollice.
        
        Args:
            dist (float): Distanza tra indice e pollice.
            drag_mode_enabled (bool): Se True, abilita la modalità di trascinamento.
            enable_right_click (bool): Se True, abilita il clic destro.
            pinky_up (bool): Se True, il mignolo è alzato.
            
        Returns:
            bool: True se è stato eseguito un clic, False altrimenti.
        """
        click_performed = False
        current_time = time.time()
        
        # Gestione del clic sinistro
        if dist < self.config.click_distance_threshold:
            # Se non siamo già in modalità click, registra l'inizio del click
            if not self.click_detection_active:
                self.click_detection_active = True
                self.click_start_time = current_time
            # Se siamo in modalità drag e il click è mantenuto abbastanza a lungo, attiva il drag
            elif drag_mode_enabled and not self.click_held and (current_time - self.click_start_time) > 0.3:
                pyautogui.mouseDown()
                self.click_held = True
                click_performed = True
        else:
            # Se eravamo in modalità click ma ora non lo siamo più
            if self.click_detection_active:
                # Se eravamo in drag mode, rilascia il mouse
                if self.click_held:
                    pyautogui.mouseUp()
                    self.click_held = False
                # Altrimenti, se il tempo di attesa è stato breve, è un click normale
                elif (current_time - self.click_start_time) < 0.3:
                    # Verifica se è passato abbastanza tempo dall'ultimo click
                    if current_time - self.last_click_time >= self.config.click_cooldown:
                        pyautogui.click()
                        self.last_click_time = current_time
                        click_performed = True
            
            # Reset dello stato di rilevamento click
            self.click_detection_active = False
        
        # Gestione del clic destro
        if enable_right_click and not pinky_up and time.time() - self.right_click_cooldown >= 1.0:
            pyautogui.click(button='right')
            self.right_click_cooldown = time.time()
            click_performed = True
        
        return click_performed
    
    def perform_slide(self, direction):
        """
        Esegue lo scorrimento nella direzione specificata.
        
        Args:
            direction (str): Direzione dello scorrimento ("left", "right", "up" o "down").
        """
        if direction == "left":
            pyautogui.press("left")
        elif direction == "right":
            pyautogui.press("right")
        elif direction == "up":
            pyautogui.press("up")
        elif direction == "down":
            pyautogui.press("down")
    
    def handle_zoom(self, current_distance, zoom_gesture_active):
        """
        Gestisce lo zoom in base alla distanza tra gli indici delle due mani.
        
        Args:
            current_distance (float): Distanza attuale tra gli indici.
            zoom_gesture_active (bool): Se True, il gesto per lo zoom è attivo.
            
        Returns:
            tuple: (zoom_performed, zoom_direction)
        """
        zoom_performed = False
        zoom_direction = None
        
        # Aggiungi la distanza corrente alla lista per lo smoothing
        self.zoom_distances.append(current_distance)
        if len(self.zoom_distances) > self.zoom_smooth_factor:
            self.zoom_distances.pop(0)
        
        # Calcola la distanza media per lo smoothing
        smoothed_distance = self.smooth_distance(self.zoom_distances)
        
        # Applica lo zoom SOLO se la gesture è attiva e la distanza è inferiore alla soglia massima
        if zoom_gesture_active and smoothed_distance < self.config.zoom_max_distance:
            if self.last_zoom_distance is not None and time.time() - self.zoom_cooldown >= self.zoom_cooldown_time:
                # Calcola la differenza di distanza
                zoom_diff = smoothed_distance - self.last_zoom_distance
                
                # Applica lo zoom solo se la differenza è significativa
                if abs(zoom_diff) > self.config.zoom_threshold:
                    # Zoom in (allontanamento delle dita)
                    if zoom_diff > 0:
                        pyautogui.keyDown('ctrl')
                        pyautogui.scroll(10)  # Zoom in
                        pyautogui.keyUp('ctrl')
                        zoom_direction = "in"
                    # Zoom out (avvicinamento delle dita)
                    else:
                        pyautogui.keyDown('ctrl')
                        pyautogui.scroll(-10)  # Zoom out
                        pyautogui.keyUp('ctrl')
                        zoom_direction = "out"
                    
                    # Aggiorna il cooldown
                    self.zoom_cooldown = time.time()
                    # Resetta la distanza precedente per evitare zoom continui
                    self.last_zoom_distance = smoothed_distance
                    zoom_performed = True
            
            # Aggiorna la distanza precedente se non è in cooldown
            elif time.time() - self.zoom_cooldown >= self.zoom_cooldown_time:
                self.last_zoom_distance = smoothed_distance
        else:
            # Reset della distanza precedente se la gesture non è attiva
            self.last_zoom_distance = None
        
        return zoom_performed, zoom_direction
    
    def smooth_distance(self, distances):
        """
        Calcola la media delle distanze per lo smoothing.
        
        Args:
            distances (list): Lista di distanze.
            
        Returns:
            float: Media delle distanze.
        """
        return np.mean(distances) if distances else 0
    
    def reset(self):
        """Resetta lo stato del controller."""
        if self.click_held:
            pyautogui.mouseUp()
            self.click_held = False
        
        self.last_zoom_distance = None
        self.zoom_distances = []
        self.click_detection_active = False