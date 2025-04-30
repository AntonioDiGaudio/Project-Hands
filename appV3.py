import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time

pyautogui.FAILSAFE = False

cap = cv2.VideoCapture(1)
cap.set(3, 640)  
cap.set(4, 480)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.8, min_tracking_confidence=0.8)
mp_draw = mp.solutions.drawing_utils

screen_width, screen_height = pyautogui.size()

# Variabili iniziali
prev_x, prev_y = 0, 0
click_held = False
right_click_cooldown = 0

def fingers_up(lm_list):
    tips = [8, 12, 16, 20]  # Indice, Medio, Anulare, Mignolo
    up = []
    for tip in tips:
        up.append(lm_list[tip][1] < lm_list[tip - 2][1])
    return up  # [Indice, Medio, Anulare, Mignolo]

while True:


    success, frame = cap.read()
    if not success:
        continue

    frame = cv2.flip(frame, 1)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(frame_rgb)

    if results.multi_hand_landmarks:
        for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
            hand_label = handedness.classification[0].label

            if hand_label == "Right":
                lm_list = []
                for lm in hand_landmarks.landmark:
                    lm_x = int(lm.x * frame.shape[1])
                    lm_y = int(lm.y * frame.shape[0])
                    lm_list.append((lm_x, lm_y))

                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                up = fingers_up(lm_list)

                wrist = lm_list[0]
                # Mappatura diretta senza margini, direttamente sullo schermo
                x_screen = np.interp(wrist[0], (0, frame.shape[1]), (0, screen_width))
                y_screen = np.interp(wrist[1], (0, frame.shape[0]), (0, screen_height))

                dx = x_screen - prev_x
                dy = y_screen - prev_y

                # Caso 1: solo indice alzato = click sinistro tenuto + movimento
                if up == [True, False, False, False]:
                    if not click_held:
                        pyautogui.mouseDown()
                        click_held = True
                    if abs(dx) > 1 or abs(dy) > 1:
                        pyautogui.moveRel(dx, dy, duration=0)
                        prev_x, prev_y = x_screen, y_screen

                # Caso 2: solo pugno chiuso = movimento senza click
                elif up == [False, False, False, False]:
                    if click_held:
                        pyautogui.mouseUp()
                        click_held = False
                    if abs(dx) > 1 or abs(dy) > 1:
                        pyautogui.moveRel(dx, dy, duration=0)
                        prev_x, prev_y = x_screen, y_screen

                # Caso 3: solo medio alzato = click destro (con cooldown)
                elif up == [False, True, False, False]:
                    current_time = time.time()
                    if current_time - right_click_cooldown > 1:  # 1 secondo tra due click
                        pyautogui.rightClick()
                        right_click_cooldown = current_time

                # Altri gesti = rilascia eventuale click sinistro
                else:
                    if click_held:
                        pyautogui.mouseUp()
                        click_held = False

    else:
        if click_held:
            pyautogui.mouseUp()
            click_held = False

    
    cv2.imshow("Hand Controller", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
