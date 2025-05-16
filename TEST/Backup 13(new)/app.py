"""
Versione ottimizzata del modulo principale dell'applicazione AirMouse.
"""

import cv2
import threading
import time
from webcam_manager import WebcamManager
from hand_tracker import HandTracker
from mouse_controller import MouseController
from settings_gui import create_settings_gui
from shared_state import set_running, get_running
import config
from gesture_recognizer import GestureRecognizer


class AirMouseApp:
    """
    Classe principale dell'applicazione AirMouse.
    Versione ottimizzata per ridurre il consumo di CPU.
    """
    
    def __init__(self):
        """Inizializza l'applicazione AirMouse."""
        self.webcam_manager = WebcamManager()
        self.hand_tracker = HandTracker(max_num_hands=2)  
        self.mouse_controller = MouseController(config)
        
        # Impostazioni specifiche
        self.preferred_hand = "Right"
        self.drag_mode_enabled = True
        self.enable_right_click = True
        
        self.slide_cooldown = 0.0
        self.cap = None
        self.gesture_recognizer = GestureRecognizer(config)
        
        # Parametri di ottimizzazione
        self.frame_skip = config.frame_skip
        self.frame_counter = 0
        self.last_process_time = 0
        self.throttle_fps = config.throttle_fps
        self.min_frame_time = 1.0 / self.throttle_fps
    
    def initialize(self):
        """
        Inizializza l'applicazione selezionando la webcam e avviando la GUI delle impostazioni.
        
        Returns:
            bool: True se l'inizializzazione è riuscita, False altrimenti.
        """
        try:
            # Selezione della webcam
            selected_cam = self.webcam_manager.select_camera_gui()
            
            # Dopo la selezione webcam, lancia la GUI delle impostazioni in un thread
            gui_thread = threading.Thread(target=create_settings_gui)
            gui_thread.daemon = True
            gui_thread.start()
            
            # Apertura della webcam selezionata
            self.cap = self.webcam_manager.open_camera(selected_cam)
            
            # Imposta un framerate più basso per ridurre il carico
            self.cap.set(cv2.CAP_PROP_FPS, config.throttle_fps)
            
            # Verifica e imposta il backend ottimale per la cattura video
            # Su Linux, prova a usare V4L2 che è generalmente più efficiente
            if cv2.ocl.useOpenCL():
                cv2.ocl.setUseOpenCL(True)
                print("OpenCL abilitato per l'accelerazione CPU")
            
            return True
        except Exception as e:
            print(f"Errore durante l'inizializzazione: {e}")
            return False
    
    def run(self):
        """Esegue il ciclo principale dell'applicazione."""
        if self.cap is None:
            print("Webcam non inizializzata")
            return
        
        # Ciclo principale per il riconoscimento della mano e il movimento del cursore
        while get_running():
            # Throttling per limitare il framerate
            current_time = time.time()
            elapsed = current_time - self.last_process_time
            if elapsed < self.min_frame_time:
                # Dormi per il tempo rimanente per raggiungere il framerate target
                time.sleep(self.min_frame_time - elapsed)
                continue
            
            self.last_process_time = time.time()
            
            # Acquisizione frame
            ret, frame = self.cap.read()
            
            if not ret:
                continue
            
            # Frame skipping per ridurre il carico
            self.frame_counter += 1
            if self.frame_counter % self.frame_skip != 0:
                continue
            
            # Ridimensiona il frame per accelerare l'elaborazione
            # frame = cv2.resize(frame, (320, 240))
            
            frame = cv2.flip(frame, 1)
            frame, results = self.hand_tracker.find_hands(frame, draw=False)
            
            if results.multi_hand_landmarks:
                h, w, _ = frame.shape
                hands_data = self.hand_tracker.find_positions(frame, results)
                
                right_hand_points = hands_data.get("Right")
                left_hand_points = hands_data.get("Left")
                
                right_finger_state = self.hand_tracker.fingers_up(right_hand_points)
                left_finger_state = self.hand_tracker.fingers_up(left_hand_points)
                
                # Gestione della mano destra (controllo del mouse)
                if right_hand_points and right_finger_state and self.preferred_hand == "Right":
                    index_up, middle_up, ring_up, pinky_up = right_finger_state
                    ix, iy = right_hand_points[8]  # Indice
                    px, py = right_hand_points[4]  # Pollice
                    
                    # Muovi il cursore
                    dist = self.hand_tracker.distance_between_points((ix, iy), (px, py))
                    
                    # Controllo blocco cursore durante il gesto di click
                    block_cursor = self.gesture_recognizer.should_block_cursor(dist)
                    
                    if not block_cursor:
                        self.mouse_controller.move_cursor(ix, iy, w, h)
                    
                    # Gestione del click
                    self.mouse_controller.handle_click(dist, self.drag_mode_enabled, self.enable_right_click, pinky_up)
                
                # Gestione della mano sinistra (zoom e slide)
                if left_hand_points and left_finger_state:
                    # Verifica se il palmo è aperto (almeno 3 dita alzate)
                    left_palm_closed = sum(left_finger_state) == 0
                    
                    # Gestione dello slide con il palmo aperto
                    if left_palm_closed:
                        # Coordinate del palmo (punto 0)
                        palm_x, palm_y = left_hand_points[0]
                        
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
                        
                        if direction != "center" and time.time() - self.slide_cooldown >= config.slide_cooldown_time:
                            self.mouse_controller.perform_slide(direction)
                            self.slide_cooldown = time.time()
                
                # Gestione dello zoom (richiede entrambe le mani)
                if right_hand_points and left_hand_points and right_finger_state and left_finger_state:
                    # Verifica se è attiva la gesture per lo zoom (solo indici alzati)
                    zoom_gesture_active = self.hand_tracker.check_zoom_gesture(right_finger_state, left_finger_state)
                    
                    # Indici delle due mani
                    right_index = right_hand_points[8]
                    left_index = left_hand_points[8]
                    
                    # Calcola la distanza tra gli indici
                    current_distance = self.hand_tracker.distance_between_points(right_index, left_index)
                    
                    # Gestione dello zoom
                    self.mouse_controller.handle_zoom(current_distance, zoom_gesture_active)
                else:
                    # Reset delle variabili se non ci sono mani rilevate
                    self.mouse_controller.last_zoom_distance = None
                    self.mouse_controller.zoom_distances = []
            
            # Controllo chiusura con ESC
            key = cv2.waitKey(1)
            if key == 27:  # ESC key
                set_running(False)
            
            if not get_running():
                break
    
    def terminate(self):
        """Chiude l'applicazione e rilascia le risorse."""
        try:
            cv2.destroyAllWindows()
        except:
            pass
        
        try:
            if self.cap is not None:
                self.webcam_manager.release_camera()
        except:
            pass
        
        set_running(False)


def main():
    """Funzione principale per avviare l'applicazione."""
    app = AirMouseApp()
    if app.initialize():
        try:
            app.run()
        except Exception as e:
            print(f"Errore durante l'esecuzione: {e}")
        finally:
            app.terminate()
    else:
        print("Impossibile inizializzare l'applicazione")


if __name__ == "__main__":
    main()
