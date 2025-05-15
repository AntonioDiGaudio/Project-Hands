"""
Modulo ottimizzato per il rilevamento e il tracciamento delle mani utilizzando MediaPipe.
"""

import cv2
import mediapipe as mp
import numpy as np
import config


class HandTracker:
    """
    Classe per rilevare e tracciare le mani utilizzando MediaPipe.
    Versione ottimizzata per ridurre il consumo di CPU.
    """
    
    def __init__(self, static_image_mode=False, max_num_hands=1, 
                 model_complexity=None, min_detection_confidence=None, 
                 min_tracking_confidence=None):
        """
        Inizializza il HandTracker con le impostazioni specificate.
        
        Args:
            static_image_mode (bool): Se True, tratta ogni frame come un'immagine statica.
            max_num_hands (int): Numero massimo di mani da rilevare.
            model_complexity (int): Complessità del modello (0, 1 o 2).
            min_detection_confidence (float): Confidenza minima per la rilevazione.
            min_tracking_confidence (float): Confidenza minima per il tracciamento.
        """
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        
        # Usa i valori di configurazione se non specificati
        if model_complexity is None:
            model_complexity = config.model_complexity
        if min_detection_confidence is None:
            min_detection_confidence = config.min_detection_confidence
        if min_tracking_confidence is None:
            min_tracking_confidence = config.min_tracking_confidence
        
        # Configura l'accelerazione hardware se disponibile
        if hasattr(config, 'use_hardware_acceleration') and config.use_hardware_acceleration:
            # Imposta le opzioni per l'accelerazione hardware
            self.hands = self.mp_hands.Hands(
                static_image_mode=static_image_mode,
                max_num_hands=max_num_hands,
                model_complexity=model_complexity,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence
            )
        else:
            # Configurazione standard senza accelerazione hardware
            self.hands = self.mp_hands.Hands(
                static_image_mode=static_image_mode,
                max_num_hands=max_num_hands,
                model_complexity=model_complexity,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence
            )
        
        # Cache per i risultati
        self.last_results = None
        self.cache_valid = False
        self.cache_counter = 0
        self.cache_max = 2  # Usa la cache per 2 frame
    
    def find_hands(self, frame, draw=False):
        """
        Rileva le mani in un frame.
        
        Args:
            frame (numpy.ndarray): Frame da analizzare.
            draw (bool): Se True, disegna i punti di riferimento sul frame.
            
        Returns:
            tuple: (frame modificato, risultati del rilevamento)
        """
        # Usa la cache se valida
        if self.cache_valid and self.cache_counter < self.cache_max:
            self.cache_counter += 1
            if self.last_results and self.last_results.multi_hand_landmarks and draw:
                for hand_landmarks in self.last_results.multi_hand_landmarks:
                    self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
            return frame, self.last_results
        
        # Altrimenti elabora il frame
        self.cache_counter = 0
        
        # Ridimensiona il frame per l'elaborazione
        h, w, _ = frame.shape
        process_w, process_h = 320, 240  # Risoluzione ridotta per l'elaborazione
        
        # Ridimensiona solo se necessario
        if w > process_w or h > process_h:
            small_frame = cv2.resize(frame, (process_w, process_h))
            rgb = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Elabora il frame
        self.last_results = self.hands.process(rgb)
        self.cache_valid = True
        
        if self.last_results.multi_hand_landmarks and draw:
            for hand_landmarks in self.last_results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
        
        return frame, self.last_results
    
    def find_positions(self, frame, results):
        """
        Estrae le posizioni dei punti di riferimento delle mani.
        
        Args:
            frame (numpy.ndarray): Frame analizzato.
            results: Risultati del rilevamento delle mani.
            
        Returns:
            dict: Dizionario con le mani rilevate e le loro posizioni.
        """
        h, w, _ = frame.shape
        hands_data = {"Right": None, "Left": None}
        
        if results.multi_hand_landmarks:
            for hand_idx, (hand_landmarks, hand_info) in enumerate(
                zip(results.multi_hand_landmarks, results.multi_handedness)
            ):
                # Determina se è la mano destra o sinistra
                hand_label = hand_info.classification[0].label
                
                # Estrai solo i punti necessari per ottimizzare
                # Indici dei punti importanti: 0 (palmo), 4 (pollice), 8 (indice), 12 (medio), 16 (anulare), 20 (mignolo)
                important_indices = [0, 4, 8, 12, 16, 20]
                
                # Per i gesti più complessi, aggiungi anche i punti intermedi
                if self.needs_intermediate_points():
                    important_indices.extend([6, 10, 14, 18])
                
                # Estrai solo i punti necessari
                points = []
                for i in range(21):  # MediaPipe ha 21 punti per mano
                    if i in important_indices:
                        lm = hand_landmarks.landmark[i]
                        points.append((int(lm.x * w), int(lm.y * h)))
                    else:
                        points.append(None)  # Placeholder per i punti non estratti
                
                # Assegna i punti alla mano corrispondente
                hands_data[hand_label] = points
        
        return hands_data
    
    def needs_intermediate_points(self):
        """
        Determina se sono necessari i punti intermedi per i gesti.
        
        Returns:
            bool: True se sono necessari i punti intermedi, False altrimenti.
        """
        # Implementa la logica per determinare se sono necessari i punti intermedi
        # Ad esempio, se sono abilitati gesti complessi
        return True
    
    def fingers_up(self, landmarks):
        """
        Determina quali dita sono alzate.
        
        Args:
            landmarks (list): Lista di punti di riferimento della mano.
            
        Returns:
            list: Lista di booleani che indicano se ogni dito è alzato.
        """
        if landmarks is None:
            return [0, 0, 0, 0]
        
        # Verifica che i punti necessari non siano None
        if landmarks[8] is None or landmarks[6] is None or \
           landmarks[12] is None or landmarks[10] is None or \
           landmarks[16] is None or landmarks[14] is None or \
           landmarks[20] is None or landmarks[18] is None:
            return [0, 0, 0, 0]
        
        return [
            int(landmarks[8][1] < landmarks[6][1]),   # Indice
            int(landmarks[12][1] < landmarks[10][1]), # Medio
            int(landmarks[16][1] < landmarks[14][1]), # Anulare
            int(landmarks[20][1] < landmarks[18][1])  # Mignolo
        ]
    
    def distance_between_points(self, p1, p2):
        """
        Calcola la distanza euclidea tra due punti.
        
        Args:
            p1 (tuple): Primo punto (x, y).
            p2 (tuple): Secondo punto (x, y).
            
        Returns:
            float: Distanza tra i due punti.
        """
        if p1 is None or p2 is None:
            return float('inf')
        return np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
    
    def check_zoom_gesture(self, right_fingers, left_fingers):
        """
        Verifica se è attivo il gesto per lo zoom (entrambi gli indici alzati).
        
        Args:
            right_fingers (list): Stato delle dita della mano destra.
            left_fingers (list): Stato delle dita della mano sinistra.
            
        Returns:
            bool: True se il gesto per lo zoom è attivo, False altrimenti.
        """
        if right_fingers is None or left_fingers is None:
            return False
        return right_fingers[0] == 1 and left_fingers[0] == 1
