import sys
import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import time
import threading
import tkinter as tk
from tkinter import ttk
import math
import config
from settings_gui import create_settings_gui
from webcam_selector import select_camera_gui
from shared_state import set_running, get_running





# Selezione della webcam
selected_cam = select_camera_gui()

# Dopo la selezione webcam, lancia la GUI delle impostazioni in un thread
gui_thread = threading.Thread(target=create_settings_gui)
gui_thread.daemon = True
gui_thread.start()

# Impostazioni iniziali
pyautogui.FAILSAFE = False
screen_w, screen_h = pyautogui.size()

# Impostazioni specifiche per vision_controller (non più in config.py)
preferred_hand = "Right"  
drag_mode_enabled = True
enable_right_click = True

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
# Modificato per rilevare entrambe le mani
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,  # Modificato da 1 a 2 per rilevare entrambe le mani
    model_complexity=0,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# Apertura della webcam selezionata
cap = cv2.VideoCapture(selected_cam)
if not cap.isOpened():
    raise SystemExit("Impossibile aprire la webcam selezionata")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# Parametri del filtro di Kalman
xk = np.array([screen_w / 2, screen_h / 2, 0, 0], dtype=np.float32)
Pk = np.eye(4, dtype=np.float32) * 300
F = np.eye(4, dtype=np.float32)
H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
Q = np.diag([3, 3, 12, 12]).astype(np.float32)
R = np.diag([25, 25]).astype(np.float32)
I4 = np.eye(4, dtype=np.float32)

smooth_x, smooth_y = xk[0], xk[1]
click_held = False
right_click_cooldown = 0.0
last_click_time = 0.0

# Parametri per lo zoom
zoom_scale = 0.6
last_zoom_distance = None
zoom_sensitivity = 5 # Aumenta la sensibilità dello zoom
zoom_cooldown = 0.0      # Cooldown per lo zoom
zoom_cooldown_time = 0.5 # Riduci il cooldown per lo zoom
zoom_threshold = 40       # Riduci la soglia per un cambiamento significativo
zoom_distances = []      # Lista per lo smoothing delle distanze
zoom_smooth_factor = 5   # Numero di campioni per lo smoothing
zoom_mode_active = True # Flag per attivare/disattivare la modalità zoom
zoom_max_distance = 160 


# Parametri per lo slide
slide_cooldown = 0.0
slide_cooldown_time = 0.4  # Tempo di cooldown in secondi
slide_threshold = 0.2      # Soglia per il riconoscimento dello slide 

# Funzione per determinare quali dita sono alzate
def fingers_up(landmarks):
    fingers = []
    # Indice
    if landmarks[8][1] < landmarks[6][1]:
        fingers.append(1)
    else:
        fingers.append(0)
    
    # Medio
    if landmarks[12][1] < landmarks[10][1]:
        fingers.append(1)
    else:
        fingers.append(0)
    
    # Anulare
    if landmarks[16][1] < landmarks[14][1]:
        fingers.append(1)
    else:
        fingers.append(0)
    
    # Mignolo
    if landmarks[20][1] < landmarks[18][1]:
        fingers.append(1)
    else:
        fingers.append(0)
    
    return fingers

# Funzione per calcolare la distanza tra due punti
def distance_between_points(p1, p2):
    return np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

# Funzione per determinare l'orientamento della mano
def get_hand_orientation(landmarks, frame_width, frame_height):
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

# Funzione per eseguire lo slide
def perform_slide(direction):
    #print(f"Esecuzione slide: {direction}")
    if direction == "left":
        pyautogui.press("left")
    elif direction == "right":
        pyautogui.press("right")
    elif direction == "up":
        pyautogui.press("up")
    elif direction == "down":
        pyautogui.press("down")

# Funzione per calcolare la media delle distanze per lo smoothing
def smooth_distance(distances):
    if not distances:
        return 0
    return sum(distances) / len(distances)

# Funzione per verificare se entrambi gli indici sono alzati (per attivare lo zoom)

def check_zoom_gesture(right_fingers, left_fingers):
    return right_fingers[0] == 1 and left_fingers[0] == 1



# Ciclo principale per il riconoscimento della mano e il movimento del cursore
while get_running:
    
    ret, frame = cap.read()
    if not ret:
        continue

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    h, w, _ = frame.shape
    right_hand_landmarks = None
    left_hand_landmarks = None
    right_hand_points = None
    left_hand_points = None
    right_finger_state = None
    left_finger_state = None

    # Elabora le mani rilevate
    if result.multi_hand_landmarks:
        for hand_idx, (hand_landmarks, hand_info) in enumerate(zip(result.multi_hand_landmarks, result.multi_handedness)):
            # Determina se è la mano destra o sinistra
            hand_label = hand_info.classification[0].label
            
            # Disegna i landmark della mano
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            # Estrai i punti della mano
            points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]
            
            # Assegna i punti alla mano corrispondente
            # Associa la mano destra o sinistra in base alla preferenza
            if hand_label == preferred_hand:
                right_hand_landmarks = hand_landmarks
                right_hand_points = points
                right_finger_state = fingers_up(points)
            else:
                left_hand_landmarks = hand_landmarks
                left_hand_points = points
                left_finger_state = fingers_up(points)


        # Aggiungi etichette per identificare le mani
        if right_hand_points:
            cv2.putText(frame, "Destra", (right_hand_points[0][0], right_hand_points[0][1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        if left_hand_points:
            cv2.putText(frame, "Sinistra", (left_hand_points[0][0], left_hand_points[0][1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # Gestione della mano destra (controllo del mouse)
        if right_hand_points and right_finger_state and preferred_hand == "Right":
            index_up, middle_up, ring_up, pinky_up = right_finger_state
            ix, iy = right_hand_points[8]  # Indice
            px, py = right_hand_points[4]  # Pollice

            # Mappatura schermo con sensibilità e velocità in tempo reale
            ix_centered = (ix - w / 2) * config.overscan_x + w / 2
            iy_centered = (iy - h / 2) * config.overscan_y + h / 2
            ix_clipped = np.clip(ix_centered, 0, w - 1)
            iy_clipped = np.clip(iy_centered, 0, h - 1)

            zx = np.interp(ix_clipped, [0, w - 1], [0, screen_w - 1]) * config.cursor_speed_multiplier
            zy = np.interp(iy_clipped, [0, h - 1], [0, screen_h - 1]) * config.cursor_speed_multiplier

            dist = distance_between_points((ix, iy), (px, py))

            smooth_x += config.alpha_smooth * (zx - smooth_x)
            smooth_y += config.alpha_smooth * (zy - smooth_y)

            pyautogui.moveTo(int(smooth_x), int(smooth_y), _pause=False)

            # Gestione del click - SOLO PER LA MANO DESTRA
            if dist < config.click_distance_threshold:
                if drag_mode_enabled:
                    if not click_held and time.time() - last_click_time >= config.click_cooldown:
                        pyautogui.mouseDown()
                        click_held = True
                        last_click_time = time.time()
                else:
                    if time.time() - last_click_time >= config.click_cooldown:
                        pyautogui.click()
                        last_click_time = time.time()
            else:
                if click_held:
                    pyautogui.mouseUp()
                    click_held = False

            if enable_right_click and not pinky_up and time.time() - right_click_cooldown >= 1.0:
                pyautogui.click(button='right')
                right_click_cooldown = time.time()

        # Gestione della mano sinistra (zoom e slide)
        if left_hand_points and left_finger_state:
            # Verifica se il palmo è aperto (almeno 3 dita alzate)
            left_palm_closed = sum(left_finger_state) == 0
            
            # Visualizza lo stato delle dita della mano sinistra
            finger_status = "Dita SX: " + "".join(["↑" if f else "↓" for f in left_finger_state])
            cv2.putText(frame, finger_status, (10, 150), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Visualizza se il palmo è considerato aperto
            palm_status = "Palmo aperto" if left_palm_closed else "Palmo chiuso"
            cv2.putText(frame, palm_status, (10, 170), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Visualizza lo stato del cooldown dello slide
            slide_cooldown_remaining = max(0, slide_cooldown_time - (time.time() - slide_cooldown))
            if slide_cooldown_remaining > 0:
                cv2.putText(frame, f"Slide cooldown: {slide_cooldown_remaining:.1f}s", (10, 190), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Gestione dello slide con il palmo aperto
            if left_palm_closed:
                # Coordinate del palmo (punto 0)
                palm_x, palm_y = left_hand_points[0]
                
                # Visualizza coordinate
                cv2.putText(frame, f"Pugno: ({palm_x}, {palm_y})", (10, 210),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                # Determina la direzione in base alla posizione
                direction = "center"
                margin_x = w * 0.3
                margin_y = h * 0.3

                if palm_y < margin_y:
                    direction = "up"
                elif palm_y > h - margin_y:
                    direction = "down"
                elif palm_x < margin_x:
                    direction = "left"
                elif palm_x > w - margin_x:
                    direction = "right"

                if direction != "center" and time.time() - slide_cooldown >= slide_cooldown_time:
                    perform_slide(direction)
                    slide_cooldown = time.time()
                    cv2.putText(frame, f"Slide: {direction}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Gestione dello zoom (richiede entrambe le mani)
        if right_hand_points and left_hand_points and right_finger_state and left_finger_state:
            # Verifica se è attiva la gesture per lo zoom (solo indici alzati)
            zoom_gesture_active = check_zoom_gesture(right_finger_state, left_finger_state)
            
            # Indici delle due mani
            right_index = right_hand_points[8]
            left_index = left_hand_points[8]
            
            # Calcola la distanza tra gli indici
            current_distance = distance_between_points(right_index, left_index)
            # print(f"Right index: {right_index}, Left index: {left_index}")
            # print(f"Distance: {current_distance}")

            
            # Visualizza se la gesture di zoom è attiva
            zoom_status = "Zoom gesture: " + ("Attiva" if zoom_gesture_active else "Inattiva")
            cv2.putText(frame, zoom_status, (10, 230), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Aggiungi la distanza corrente alla lista per lo smoothing
            zoom_distances.append(current_distance)
            if len(zoom_distances) > zoom_smooth_factor:
                zoom_distances.pop(0)
            
            # Calcola la distanza media per lo smoothing
            smoothed_distance = smooth_distance(zoom_distances)
            
            # Visualizza la distanza sullo schermo
            cv2.line(frame, right_index, left_index, (0, 255, 0), 2)
            cv2.putText(frame, f"Dist: {int(smoothed_distance)}", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Visualizza lo stato del cooldown
            cooldown_remaining = max(0, zoom_cooldown_time - (time.time() - zoom_cooldown))
            if cooldown_remaining > 0:
                cv2.putText(frame, f"Zoom cooldown: {cooldown_remaining:.1f}s", (10, 120), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Applica lo zoom SOLO se la gesture è attiva e la distanza è inferiore alla soglia massima
            if zoom_gesture_active and smoothed_distance < zoom_max_distance:
                if last_zoom_distance is not None and time.time() - zoom_cooldown >= zoom_cooldown_time:
                    # Calcola la differenza di distanza
                    zoom_diff = smoothed_distance - last_zoom_distance
                    
                    # Applica lo zoom solo se la differenza è significativa
                    if abs(zoom_diff) > zoom_threshold:
                        # Zoom in (allontanamento delle dita)
                        if zoom_diff > 0:
                            pyautogui.keyDown('ctrl')
                            pyautogui.scroll(10)  # Zoom in
                            pyautogui.keyUp('ctrl')
                            cv2.putText(frame, "Zoom In", (10, 90), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        # Zoom out (avvicinamento delle dita)
                        else:
                            pyautogui.keyDown('ctrl')
                            pyautogui.scroll(-10)  # Zoom out
                            pyautogui.keyUp('ctrl')
                            cv2.putText(frame, "Zoom Out", (10, 90), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        
                        # Aggiorna il cooldown
                        zoom_cooldown = time.time()
                        # Resetta la distanza precedente per evitare zoom continui
                        last_zoom_distance = smoothed_distance
                
                # Aggiorna la distanza precedente se non è in cooldown
                elif time.time() - zoom_cooldown >= zoom_cooldown_time:
                    last_zoom_distance = smoothed_distance
            else:
                # Reset della distanza precedente se la gesture non è attiva
                last_zoom_distance = None
    else:
        # Reset delle variabili se non ci sono mani rilevate
        last_zoom_distance = None
        zoom_distances = []
        if click_held:
            pyautogui.mouseUp()
            click_held = False

    cv2.imshow("Hand Mouse Control", frame) #Commenta questa riga per evitare il Bud dei thread
    # Controllo chiusura con ESC (opzionale)
    key = cv2.waitKey(1)
    if key == 27:  # ESC key
        set_running(False)
    
    if not get_running():
        break
    


def terminate_app():
    """Chiude tutto forzatamente"""
    global running, cap, gui_thread
    
    running = False
    
    try:
        cv2.destroyAllWindows()
    except:
        pass
        
    try:
        if cap is not None and cap.isOpened():
            cap.release()
    except:
        pass
        
    try:
        if gui_thread is not None and gui_thread.is_alive():
            gui_thread.join(timeout=0.5)
    except:
        pass
    
    sys.exit(0)


terminate_app()



# smoothed_distance = smooth_distance(zoom_distances)
# print(f"Smoothed distance: {smoothed_distance}")  # Debug

# # Aggiungi un print per verificare lo stato della gesture
# zoom_gesture_active = check_zoom_gesture(right_finger_state, left_finger_state)
# print(f"Zoom gesture active: {zoom_gesture_active}")  # Debug







