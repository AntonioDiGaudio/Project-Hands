import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess



# Funzione per ottenere i nomi delle webcam su Linux
def get_camera_names():
    result = subprocess.run(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    cameras = []
    lines = output.splitlines()
    for i in range(len(lines)):
        if lines[i].strip() != "" and "video" in lines[i]:
            cameras.append(lines[i].strip())
    return cameras

# Funzione per cercare le webcam disponibili
def try_camera(i, found, camera_names):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            camera_name = camera_names[i] if i < len(camera_names) else f"Webcam #{i}"
            found.append((i, camera_name))
    cap.release()

# Funzione per ottenere le webcam disponibili
def list_available_cameras(max_cams=3):
    found = []
    threads = []
    camera_names = get_camera_names()
    max_cams = min(max_cams, len(camera_names))

    for i in range(max_cams):
        t = threading.Thread(target=try_camera, args=(i, found, camera_names))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return found

# Funzione per la GUI di selezione della webcam
def select_camera_gui():
    selected_index = []

    def on_select(i):
        test_cap = cv2.VideoCapture(i)
        if not test_cap.isOpened():
            messagebox.showerror("Errore", f"Impossibile aprire la webcam #{i}.")
            return
        test_cap.release()
        selected_index.append(i)
        root.destroy()

    def search_and_show():
        label.config(text="Ricerca webcam in corso...")
        cameras = list_available_cameras()
        if not cameras:
            label.config(text="Nessuna webcam trovata.")
            return

        label.config(text="Seleziona una webcam:")

        for widget in frame.winfo_children():
            widget.destroy()

        for idx, cam_name in cameras:
            btn = ttk.Button(frame, text=f"{cam_name}", command=lambda i=idx: on_select(i))
            btn.pack(pady=5, padx=10, fill='x')

    root = tk.Tk()
    root.title("Seleziona la Webcam")
    root.geometry("300x300")
    root.resizable(False, False)

    label = ttk.Label(root, text="Ricerca webcam in corso...", font=("Helvetica", 12))
    label.pack(pady=10)

    frame = ttk.Frame(root)
    frame.pack(expand=True, fill='both')

    root.after(100, search_and_show)
    root.mainloop()

    if not selected_index:
        raise SystemExit("Nessuna webcam selezionata.")

    return selected_index[0]

# Funzione per aggiornare la sensibilità
def update_sensitivity(val):
    global alpha_smooth
    alpha_smooth = float(val)

# Funzione per aggiornare il parametro overscan
def update_overscan_x(val):
    global overscan_x
    overscan_x = float(val)

def update_overscan_y(val):
    global overscan_y
    overscan_y = float(val)

# Funzione per aggiornare la soglia click
def update_click_threshold(val):
    global click_distance_threshold
    click_distance_threshold = float(val)

# Funzione per aggiornare il cooldown
def update_click_cooldown(val):
    global click_cooldown
    click_cooldown = float(val)

# Funzione per aggiornare la velocità
def update_speed(val):
    global cursor_speed_multiplier
    cursor_speed_multiplier = float(val)

# Funzione per attivare/disattivare il click destro
def toggle_right_click():
    global enable_right_click
    enable_right_click = not enable_right_click

# Funzione per attivare/disattivare la modalità di trascinamento
def toggle_drag_mode():
    global drag_mode_enabled
    drag_mode_enabled = not drag_mode_enabled

# Funzione per creare la GUI delle impostazioni
def create_settings_gui():
    global alpha_smooth, overscan_x, overscan_y, click_cooldown, enable_right_click
    global click_distance_threshold, cursor_speed_multiplier, drag_mode_enabled, preferred_hand

    root = tk.Tk()
    root.title("Impostazioni Controllo Mouse")
    root.geometry("400x500")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill='both', expand=True)

    ttk.Label(frm, text="Sensibilità cursore").pack()
    ttk.Scale(frm, from_=0.05, to=1.0, value=alpha_smooth, command=update_sensitivity).pack(fill='x')

    ttk.Label(frm, text="Velocità cursore").pack()
    ttk.Scale(frm, from_=0.5, to=3.0, value=cursor_speed_multiplier, command=update_speed).pack(fill='x')

    ttk.Label(frm, text="Sensibilità orizzontale").pack()
    ttk.Scale(frm, from_=1.0, to=3.0, value=overscan_x, command=update_overscan_x).pack(fill='x')

    ttk.Label(frm, text="Sensibilità verticale").pack()
    ttk.Scale(frm, from_=1.0, to=3.0, value=overscan_y, command=update_overscan_y).pack(fill='x')

    ttk.Label(frm, text="Soglia distanza click (indice-pollice)").pack()
    ttk.Scale(frm, from_=5, to=100, value=click_distance_threshold, command=update_click_threshold).pack(fill='x')

    ttk.Label(frm, text="Cooldown click (secondi)").pack()
    ttk.Scale(frm, from_=0.05, to=1.0, value=click_cooldown, command=update_click_cooldown).pack(fill='x')

    right_click_check = ttk.Checkbutton(frm, text="Abilita click destro", command=toggle_right_click)
    right_click_check.state(['!alternate'])
    right_click_check.state(['selected'] if enable_right_click else ['!selected'])
    right_click_check.pack(pady=5)

    drag_mode_check = ttk.Checkbutton(frm, text="Modalità trascinamento (drag)", command=toggle_drag_mode)
    drag_mode_check.state(['!alternate'])
    drag_mode_check.state(['selected'] if drag_mode_enabled else ['!selected'])
    drag_mode_check.pack(pady=5)

    # Rimuovi la parte della GUI per scegliere la mano dominante

    def on_close():
        root.quit()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

# Impostazioni iniziali
pyautogui.FAILSAFE = False
screen_w, screen_h = pyautogui.size()

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=0,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# Selezione della webcam
selected_cam = select_camera_gui()

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
alpha_smooth = 0.3
overscan_x, overscan_y = 1.6, 1.6
click_held = False
right_click_cooldown = 0.0
last_click_time = 0.0
click_cooldown = 0.1
click_distance_threshold = 25
cursor_speed_multiplier = 1.0
enable_right_click = True
drag_mode_enabled = True
preferred_hand = "Right"  # Impostato a destra

prev_time = time.time()

# Funzione per determinare quali dita sono alzate
def fingers_up(landmarks):
    return [landmarks[i][1] < landmarks[i - 2][1] for i in (8, 12, 16, 20)]

# Funzione per calcolare la distanza tra due punti
def distance_between_points(p1, p2):
    return np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

# Avvia la GUI per le impostazioni in un thread separato
gui_thread = threading.Thread(target=create_settings_gui)
gui_thread.start()

# Ciclo principale per il riconoscimento della mano e il movimento del cursore
while True:
    ret, frame = cap.read()
    if not ret:
        continue

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

            # Mappatura schermo
            ix_centered = (ix - w / 2) * overscan_x + w / 2
            iy_centered = (iy - h / 2) * overscan_y + h / 2
            ix_clipped = np.clip(ix_centered, 0, w - 1)
            iy_clipped = np.clip(iy_centered, 0, h - 1)

            zx = np.interp(ix_clipped, [0, w - 1], [0, screen_w - 1]) * cursor_speed_multiplier
            zy = np.interp(iy_clipped, [0, h - 1], [0, screen_h - 1]) * cursor_speed_multiplier

            dist = distance_between_points((ix, iy), (px, py))

            smooth_x += alpha_smooth * (zx - smooth_x)
            smooth_y += alpha_smooth * (zy - smooth_y)

            pyautogui.moveTo(int(smooth_x), int(smooth_y), _pause=False)

            if dist < click_distance_threshold:
                if drag_mode_enabled:
                    if not click_held and time.time() - last_click_time >= click_cooldown:
                        pyautogui.mouseDown()
                        click_held = True
                        last_click_time = time.time()
                else:
                    if time.time() - last_click_time >= click_cooldown:
                        pyautogui.click()
                        last_click_time = time.time()
            else:
                if click_held:
                    pyautogui.mouseUp()
                    click_held = False

            if enable_right_click and not pinky_up and time.time() - right_click_cooldown >= 1.0:
                pyautogui.click(button='right')
                right_click_cooldown = time.time()
                cv2.putText(frame, "Right Click", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    else:
        if click_held:
            pyautogui.mouseUp()
            click_held = False

    cv2.imshow("Hand Mouse Control (Linux)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
