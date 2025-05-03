# Movimento del cursore: mano chiusa (pugno).
#Click sinistro: solo indice alzato.
#Click destro: solo medio alzato.
#Tieni premuto: solo indice alzato mantenuto per oltre 0.5 secondi.


import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time

# Inizializzazione della webcam
cap = cv2.VideoCapture(1)
cap.set(3, 640)
cap.set(4, 480)

# Inizializzazione di MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.8,
    min_tracking_confidence=0.8
)
mp_draw = mp.solutions.drawing_utils

# Dimensioni dello schermo
screen_width, screen_height = pyautogui.size()

# Variabili di stato
clicking = False
holding = False
hold_start_time = 0

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

            # Solo la mano destra
            if hand_label == "Right":
                lm_list = []
                for lm in hand_landmarks.landmark:
                    lm_x = int(lm.x * frame.shape[1])
                    lm_y = int(lm.y * frame.shape[0])
                    lm_list.append((lm_x, lm_y))

                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # Stato delle dita
                up = fingers_up(lm_list)

                # Movimento del cursore: mano chiusa (nessun dito alzato)
                if up == [False, False, False, False]:
                    wrist = lm_list[0]
                    x_screen = np.interp(wrist[0], (0, frame.shape[1]), (0, screen_width))
                    y_screen = np.interp(wrist[1], (0, frame.shape[0]), (0, screen_height))
                    pyautogui.moveTo(x_screen, y_screen, duration=0)

                # Click sinistro: solo indice alzato
                elif up == [True, False, False, False]:
                    if not clicking:
                        clicking = True
                        pyautogui.click()
                    # Tieni premuto: indice alzato mantenuto per oltre 0.5 secondi
                    if not holding:
                        hold_start_time = time.time()
                        holding = True
                    elif time.time() - hold_start_time > 0.5:
                        pyautogui.mouseDown()
                else:
                    if clicking:
                        clicking = False
                    if holding:
                        pyautogui.mouseUp()
                        holding = False

                # Click destro: solo medio alzato
                if up == [False, True, False, False]:
                    pyautogui.rightClick()
                    time.sleep(0.5)  # Prevenire clic multipli

    cv2.imshow("Hand Controller", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

