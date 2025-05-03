import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import time
import threading
import tkinter as tk
from tkinter import ttk

import config
from settings_gui import create_settings_gui
from webcam_selector import select_camera_gui

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
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
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

# Funzione per determinare quali dita sono alzate
def fingers_up(landmarks):
    return [landmarks[i][1] < landmarks[i - 2][1] for i in (8, 12, 16, 20)]

# Funzione per calcolare la distanza tra due punti
def distance_between_points(p1, p2):
    return np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

# Ciclo principale per il riconoscimento della mano e il movimento del cursore
while True:
    ret, frame = cap.read()
    if not ret:
        continue

    
    # DEBUG  print settings
    # print(f"SMOOTH: {config.alpha_smooth:.2f}, SPEED: {config.cursor_speed_multiplier:.2f}, "
    #     f"OVR_X: {config.overscan_x:.2f}, OVR_Y: {config.overscan_y:.2f}, "
    #     f"CLICK_THRESH: {config.click_distance_threshold}, "
    #     f"CLICK_COOLDOWN: {config.click_cooldown}")

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    if result.multi_hand_landmarks:
        for hand_landmarks, hand_type in zip(result.multi_hand_landmarks, result.multi_handedness):
            label = hand_type.classification[0].label
            if preferred_hand != "Auto" and label != preferred_hand:
                continue

            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            h, w, _ = frame.shape
            points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

            finger_state = fingers_up(points)
            index_up, middle_up, ring_up, pinky_up = finger_state
            ix, iy = points[8]  # Indice
            px, py = points[4]  # Pollice

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

            # Gestione del click
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

    else:
        if click_held:
            pyautogui.mouseUp()
            click_held = False

    cv2.imshow("Hand Mouse Control", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()