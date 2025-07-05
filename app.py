"""
Modulo principale dell'applicazione AirMouse.
Gestisce l'inizializzazione e l'esecuzione dell'applicazione.
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
    Gestisce l'inizializzazione e l'esecuzione dell'applicazione.
    """
    
    def __init__(self):
        """Inizializza l'applicazione AirMouse."""
        self.webcam_manager = WebcamManager()
        self.hand_tracker = HandTracker()
        self.mouse_controller = MouseController(config)
        
        # Impostazioni specifiche
        self.preferred_hand = "Right"
        self.drag_mode_enabled = True
        self.enable_right_click = True
        
    
        self.slide_cooldown = 0.0

        
        self.cap = None
        self.gesture_recognizer = GestureRecognizer(config)

        # Salva le impostazioni correnti per rilevare eventuali modifiche "live"
        self.current_camera_resolution = (config.camera_width, config.camera_height)
        self.current_hand_params = (
            config.model_complexity,
            config.min_detection_confidence,
            config.min_tracking_confidence,
            config.use_hardware_acceleration,
        )


        

    
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
            self.current_camera_resolution = (config.camera_width, config.camera_height)
            
            return True
        except Exception as e:
            print(f"Errore durante l'inizializzazione: {e}")
            return False
    
    def run(self):
        """Esegue il ciclo principale dell'applicazione."""
        if self.cap is None:
            print("Webcam non inizializzata")
            return
        



        frame_counter = 0
        skip_frames = 3 
        # Ciclo principale per il riconoscimento della mano e il movimento del cursore
        while get_running():
            current_time = time.time()

            # Verifica se qualche parametro di configurazione è cambiato
            self.check_config_updates()

            #frame_skipping
            frame_counter += 1
            if frame_counter % skip_frames != 0:
                continue  # Salta il frame
                
            #fps frame skipping
            last_frame_time = 0
            frame_interval = 1.0 / config.target_fps
            if current_time - last_frame_time < frame_interval:
                continue  # Salta questo frame
            last_frame_time = current_time
           

          
            
            ret, frame = self.cap.read()
            
            if not ret:
                continue
            
            frame = cv2.flip(frame, 1)
            frame, results = self.hand_tracker.find_hands(frame, draw=True) # Debug, metti true per vedere i landmark
            
            h, w, _ = frame.shape
            hands_data = self.hand_tracker.find_positions(frame, results)
            
            right_hand_points = hands_data.get("Right")
            left_hand_points = hands_data.get("Left")
            
            right_finger_state = self.hand_tracker.fingers_up(right_hand_points)
            left_finger_state = self.hand_tracker.fingers_up(left_hand_points)
            
            # Aggiungi etichette per identificare le mani
            # if right_hand_points:
            #     cv2.putText(frame, "Destra", (right_hand_points[0][0], right_hand_points[0][1] - 10), 
            #                 cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            # if left_hand_points:
            #     cv2.putText(frame, "Sinistra", (left_hand_points[0][0], left_hand_points[0][1] - 10), 
            #                 cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Gestione della mano destra (controllo del mouse)
            if right_hand_points and right_finger_state and self.preferred_hand == "Right":
                index_up, middle_up, ring_up, pinky_up = right_finger_state
                ix, iy = right_hand_points[8]  # Indice
                px, py = right_hand_points[4]  # Pollice
                
                # Muovi il cursore
                dist = self.hand_tracker.distance_between_points((ix, iy), (px, py))

                # Controllo blocco cursore durante il gesto di click
                index_up, middle_up, ring_up, pinky_up = right_finger_state

                # blocca il cursore se l’anulare è abbassato (ring_up == 0)
                if ring_up == 1:
                    self.mouse_controller.move_cursor(ix, iy, w, h)

                # # Gestione del click (sempre eseguita)
                # self.mouse_controller.handle_click(dist, self.drag_mode_enabled, self.enable_right_click, pinky_up)

                
                # Gestione del click
                dist = self.hand_tracker.distance_between_points((ix, iy), (px, py))
                self.mouse_controller.handle_click(dist, self.drag_mode_enabled, self.enable_right_click, pinky_up, ring_up)
            
            # Gestione della mano sinistra (zoom e slide)
            if left_hand_points and left_finger_state:
                # Verifica se il palmo è aperto (almeno 3 dita alzate)
                left_palm_closed = sum(left_finger_state) == 0
                
                # Visualizza lo stato delle dita della mano sinistra
                # finger_status = "Dita SX: " + "".join(["↑" if f else "↓" for f in left_finger_state])
                # cv2.putText(frame, finger_status, (10, 150), 
                #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Visualizza se il palmo è considerato aperto
                # palm_status = "Palmo aperto" if left_palm_closed else "Palmo chiuso"
                # cv2.putText(frame, palm_status, (10, 170), 
                #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Gestione dello slide con il palmo aperto
                if left_palm_closed:
                    # Coordinate del palmo (punto 0)
                    palm_x, palm_y = left_hand_points[0]
                    
                    # Visualizza coordinate
                    # cv2.putText(frame, f"Pugno: ({palm_x}, {palm_y})", (10, 210),
                    #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
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
                        #debug
                        # print("Slide cooldown attivo con valore:", config.slide_cooldown_time)
                        # print("Direzione:", direction)
                        self.mouse_controller.perform_slide(direction)
                        self.slide_cooldown = time.time()
                        # cv2.putText(frame, f"Slide: {direction}", (10, 30),
                        #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Gestione dello zoom (richiede entrambe le mani)
            if right_hand_points and left_hand_points and right_finger_state and left_finger_state:
                # Verifica se è attiva la gesture per lo zoom (solo indici alzati)
                zoom_gesture_active = self.hand_tracker.check_zoom_gesture(right_finger_state, left_finger_state)
                
                # Indici delle due mani
                right_index = right_hand_points[8]
                left_index = left_hand_points[8]
                
                # Calcola la distanza tra gli indici
                current_distance = self.hand_tracker.distance_between_points(right_index, left_index)
                
                # Visualizza se la gesture di zoom è attiva
                # zoom_status = "Zoom gesture: " + ("Attiva" if zoom_gesture_active else "Inattiva")
                # cv2.putText(frame, zoom_status, (10, 230), 
                #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Visualizza la distanza sullo schermo
                # cv2.line(frame, right_index, left_index, (0, 255, 0), 2)
                # cv2.putText(frame, f"Dist: {int(current_distance)}", (10, 60), 
                #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Gestione dello zoom
                zoom_performed, zoom_direction = self.mouse_controller.handle_zoom(current_distance, zoom_gesture_active)
                
                # if zoom_performed and zoom_direction:
                #     cv2.putText(frame, f"Zoom {zoom_direction}", (10, 90), 
                #                 cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                # Reset delle variabili se non ci sono mani rilevate
                self.mouse_controller.last_zoom_distance = None
                self.mouse_controller.zoom_distances = []
            
            # Aggiungi un overlay con i valori di configurazione attuali
            overlay = frame.copy()
            # Sfondo semi-trasparente per migliorare la leggibilità
            cv2.rectangle(overlay, (10, 10), (300, 350), (0, 0, 0), -1)
            
            # Aggiungi i valori di configurazione
            config_values = [
                f"Sensibilita': {config.alpha_smooth:.2f}",
                f"Velocità cursore: {config.cursor_speed_multiplier:.2f}",
                f"Overscan X: {config.overscan_x:.2f}",
                f"Overscan Y: {config.overscan_y:.2f}",
                f"Soglia click: {config.click_distance_threshold:.1f}",
                f"Cooldown click: {config.click_cooldown:.2f}s",
                f"Soglia zoom: {config.zoom_threshold:.1f}",
                f"Cooldown zoom: {config.zoom_cooldown_time:.2f}s",
                f"Smoothing zoom: {config.zoom_smooth_factor:.1f}",
                f"Distanza max zoom: {config.zoom_max_distance:.1f}",
                f"Cooldown slide: {config.slide_cooldown_time:.3f}s",
                f"Zona morta: {config.deadzone_threshold}",
                f"Confidenza rilevamento: {config.min_detection_confidence:.2f}",
                f"Confidenza tracking: {config.min_tracking_confidence:.2f}",
                f"Complessita' modello: {config.model_complexity}",
                f"Risoluzione: {config.camera_width}x{config.camera_height}",
                f"Accel. hardware: {'Sì' if config.use_hardware_acceleration else 'No'}"
            ]
            
            # Disegna i valori
            for i, text in enumerate(config_values):
                cv2.putText(overlay, text, (15, 30 + i * 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Applica l'overlay con trasparenza
            alpha = 0.7  # Trasparenza dell'overlay
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
            
            # Debug
            cv2.imshow("Hand Mouse Control", frame)
            time.sleep(0.005)
            
            # Controllo chiusura con ESC
            key = cv2.waitKey(1)
            if key == 27:  # ESC key
                set_running(False)
            
            if not get_running():
                break

    def check_config_updates(self):
        """Ricarica camera o tracker se i parametri sono cambiati."""
        # Controllo risoluzione webcam
        current_res = (config.camera_width, config.camera_height)
        if current_res != self.current_camera_resolution:
            self.reload_camera()
            self.current_camera_resolution = current_res

        # Controllo parametri HandTracker
        current_hand = (
            config.model_complexity,
            config.min_detection_confidence,
            config.min_tracking_confidence,
            config.use_hardware_acceleration,
        )
        if current_hand != self.current_hand_params:
            self.reload_hand_tracker()
            self.current_hand_params = current_hand

    def reload_camera(self):
        """Riapre la webcam con la nuova risoluzione."""
        try:
            self.webcam_manager.release_camera()
            self.cap = self.webcam_manager.open_camera(self.webcam_manager.selected_camera)
            self.current_camera_resolution = (config.camera_width, config.camera_height)
        except Exception as e:
            print(f"Errore riapertura camera: {e}")

    def reload_hand_tracker(self):
        """Ricrea l'oggetto HandTracker con le impostazioni attuali."""
        try:
            self.hand_tracker.hands.close()
        except Exception:
            pass
        self.hand_tracker = HandTracker(
            model_complexity=config.model_complexity,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
    
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
