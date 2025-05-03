import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import time

pyautogui.FAILSAFE = False
screen_w, screen_h = pyautogui.size()

# MediaPipe hands setup
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=0,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# VideoCapture forced to device 0
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    raise SystemExit("Camera not accessible")

# Set lower resolution for better performance
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# Kalman Filter Initialization
xk = np.array([screen_w / 2, screen_h / 2, 0, 0], dtype=np.float32)
Pk = np.eye(4, dtype=np.float32) * 300
F = np.eye(4, dtype=np.float32)
H = np.array([[1, 0, 0, 0],
              [0, 1, 0, 0]], dtype=np.float32)
Q = np.diag([3, 3, 12, 12]).astype(np.float32)
R = np.diag([25, 25]).astype(np.float32)
I4 = np.eye(4, dtype=np.float32)

# Motion smoothing
smooth_x, smooth_y = xk[0], xk[1]
alpha_smooth = 0.3

# Click logic
click_held = False
right_click_cooldown = 0.0
overscan_x, overscan_y = 1.6, 1.6  # AUMENTATI per migliorare la copertura

prev_time = time.time()

def fingers_up(landmarks):
    return [landmarks[i][1] < landmarks[i - 2][1] for i in (8, 12, 16, 20)]

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    if result.multi_hand_landmarks:
        for hand_landmarks, hand_type in zip(result.multi_hand_landmarks, result.multi_handedness):
            if hand_type.classification[0].label != "Right":
                continue

            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            h, w, _ = frame.shape
            points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]

            finger_state = fingers_up(points)
            ix, iy = points[8]

            # NUOVA mappatura per coprire tutto lo schermo
            ix_centered = (ix - w / 2) * overscan_x + w / 2
            iy_centered = (iy - h / 2) * overscan_y + h / 2

            ix_clipped = np.clip(ix_centered, 0, w - 1)
            iy_clipped = np.clip(iy_centered, 0, h - 1)

            zx = np.interp(ix_clipped, [0, w - 1], [0, screen_w - 1])
            zy = np.interp(iy_clipped, [0, h - 1], [0, screen_h - 1])

            # Kalman prediction & correction
            now = time.time()
            dt = now - prev_time
            prev_time = now

            F[:2, 2:] = np.array([[dt, 0], [0, dt]])
            xk = F @ xk
            Pk = F @ Pk @ F.T + Q

            z = np.array([zx, zy], dtype=np.float32)
            y = z - H @ xk
            S = H @ Pk @ H.T + R
            K = Pk @ H.T @ np.linalg.inv(S)
            xk = xk + K @ y
            Pk = (I4 - K @ H) @ Pk

            # Smoothing mouse position
            smooth_x += alpha_smooth * (xk[0] - smooth_x)
            smooth_y += alpha_smooth * (xk[1] - smooth_y)

            pyautogui.moveTo(int(smooth_x), int(smooth_y), _pause=False)

            # Click handling
            if finger_state == [True, False, False, False]:  # Index up only
                if not click_held:
                    pyautogui.mouseDown()
                    click_held = True
            elif finger_state == [False, False, False, False]:  # Fist
                if click_held:
                    pyautogui.mouseUp()
                    click_held = False
            elif finger_state == [False, True, False, False]:  # Middle up only
                t = time.time()
                if t - right_click_cooldown > 0.6:
                    pyautogui.rightClick()
                    right_click_cooldown = t
            else:
                if click_held:
                    pyautogui.mouseUp()
                    click_held = False
    else:
        if click_held:
            pyautogui.mouseUp()
            click_held = False

    cv2.imshow("Hand Mouse Control (Linux)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
