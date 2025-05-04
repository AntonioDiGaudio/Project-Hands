"""
Modulo per il rilevamento e il tracciamento delle mani utilizzando MediaPipe.
Fornisce funzionalità per rilevare le mani, i punti di riferimento e i gesti.
"""

import cv2
import mediapipe as mp
import numpy as np


class HandTracker:
    """
    Classe per rilevare e tracciare le mani utilizzando MediaPipe.
    Fornisce metodi per rilevare le mani, i punti di riferimento e i gesti.
    """
    
    def __init__(self, static_image_mode=False, max_num_hands=2, 
                 model_complexity=0, min_detection_confidence=0.8, 
                 min_tracking_confidence=0.8):
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
        
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
    
    def find_hands(self, frame, draw=False):
        """
        Rileva le mani in un frame.
        
        Args:
            frame (numpy.ndarray): Frame da analizzare.
            draw (bool): Se True, disegna i punti di riferimento sul frame.
            
        Returns:
            tuple: (frame modificato, risultati del rilevamento)
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)
        
        if results.multi_hand_landmarks and draw:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
        
        return frame, results
    
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
                
                # Estrai i punti della mano
                points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]
                
                # Assegna i punti alla mano corrispondente
                hands_data[hand_label] = points
        
        return hands_data
    
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
        
        return [
            int(landmarks[8][1] < landmarks[6][1]),   # Indice
            int(landmarks[12][1] < landmarks[10][1]), # Medio
            int(landmarks[16][1] < landmarks[14][1]), # Anulare
            int(landmarks[20][1] < landmarks[18][1])  # Mignolo
        ]
    
    def get_hand_orientation(self, landmarks, frame_width, frame_height, slide_threshold):
        """
        Determina l'orientamento della mano.
        
        Args:
            landmarks (list): Lista di punti di riferimento della mano.
            frame_width (int): Larghezza del frame.
            frame_height (int): Altezza del frame.
            slide_threshold (float): Soglia per determinare l'orientamento.
            
        Returns:
            str: Orientamento della mano ("left", "right", "up", "down" o "center").
        """
        if landmarks is None:
            return "center"
        
        # Calcola il centro del palmo (punto 0)
        palm_x, palm_y = landmarks[0]
        
        # Normalizza le coordinate rispetto al centro dello schermo
        norm_x = (palm_x / frame_width) - 0.5  # -0.5 a 0.5
        norm_y = (palm_y / frame_height) - 0.5  # -0.5 a 0.5
        
        # Determina l'orientamento in base alla posizione normalizzata
        if abs(norm_x) > abs(norm_y):
            # Movimento orizzontale predominante
            if norm_x < -slide_threshold:
                return "left"
            elif norm_x > slide_threshold:
                return "right"
        else:
            # Movimento verticale predominante
            if norm_y < -slide_threshold:
                return "up"
            elif norm_y > slide_threshold:
                return "down"
        
        # Se non supera la soglia in nessuna direzione
        return "center"
    
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
