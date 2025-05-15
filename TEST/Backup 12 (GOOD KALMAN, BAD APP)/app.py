import cv2
import threading
import time
from webcam_manager import WebcamManager
from hand_tracker import HandTracker
from hand_tracker import HandTrackerThreaded
from mouse_controller import MouseController
from settings_gui import create_settings_gui
from shared_state import set_running, get_running
import config
from gesture_recognizer import GestureRecognizer


class AirMouseApp:
    def __init__(self):
        self.webcam_manager = WebcamManager()
        
        # Istanza originale di HandTracker
        hand_tracker_orig = HandTracker(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=config.model_complexity,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence
        )
        
        # Versione threadata con skip frame = 2 (puoi modificare)
        self.hand_tracker = HandTrackerThreaded(hand_tracker_orig, skip_frames=1)
        
        self.mouse_controller = MouseController(config)
        
        self.preferred_hand = "Right"
        self.drag_mode_enabled = True
        self.enable_right_click = True
        
        self.slide_cooldown = 0.0
        self.cap = None
        self.gesture_recognizer = GestureRecognizer(config)
        self.frame_count = 0
    
    def initialize(self):
        try:
            selected_cam = self.webcam_manager.select_camera_gui()
            gui_thread = threading.Thread(target=create_settings_gui)
            gui_thread.daemon = True
            gui_thread.start()
            self.cap = self.webcam_manager.open_camera(selected_cam)
            return True
        except Exception as e:
            print(f"Errore durante l'inizializzazione: {e}")
            return False
    
    def run(self):
        if self.cap is None:
            print("Webcam non inizializzata")
            return
        
        self.hand_tracker.start()
        
        while get_running():

            
            ret, frame = self.cap.read()

            if not ret:
                continue
            
            frame = cv2.flip(frame, 1)
            
            self.hand_tracker.update_frame(frame)
            results = self.hand_tracker.get_results()
           

            
            frame_to_show = frame.copy()
            
            # # Disegna landmark se disponibili DEBUG
            # if results and results.multi_hand_landmarks:
            #     for hand_landmarks in results.multi_hand_landmarks:
            #         self.hand_tracker.hand_tracker.mp_draw.draw_landmarks(
            #             frame_to_show, hand_landmarks, self.hand_tracker.hand_tracker.mp_hands.HAND_CONNECTIONS
            #         )
            
            h, w, _ = frame.shape
            hands_data = {"Right": None, "Left": None}
            
            if results:
                hands_data = self.hand_tracker.hand_tracker.find_positions(frame_to_show, results)
            t_process_end = time.time()



            right_hand_points = hands_data.get("Right")
            left_hand_points = hands_data.get("Left")
            
            right_finger_state = self.hand_tracker.hand_tracker.fingers_up(right_hand_points)
            left_finger_state = self.hand_tracker.hand_tracker.fingers_up(left_hand_points)
            
            # Etichette mani
            if right_hand_points:
                cv2.putText(frame_to_show, "Destra", (right_hand_points[0][0], right_hand_points[0][1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            if left_hand_points:
                cv2.putText(frame_to_show, "Sinistra", (left_hand_points[0][0], left_hand_points[0][1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Controllo mano destra (mouse)
            if right_hand_points and right_finger_state and self.preferred_hand == "Right":
                index_up, middle_up, ring_up, pinky_up = right_finger_state
                ix, iy = right_hand_points[8]
                px, py = right_hand_points[4]
                dist = self.hand_tracker.hand_tracker.distance_between_points((ix, iy), (px, py))
                
                block_cursor = self.gesture_recognizer.should_block_cursor(dist)
                if not block_cursor:
                    self.mouse_controller.move_cursor(ix, iy, w, h)
                
                self.mouse_controller.handle_click(dist, self.drag_mode_enabled, self.enable_right_click, pinky_up)
            
            # Controllo mano sinistra (zoom e slide)
            if left_hand_points and left_finger_state:
                left_palm_closed = sum(left_finger_state) == 0
                
                finger_status = "Dita SX: " + "".join(["↑" if f else "↓" for f in left_finger_state])
                cv2.putText(frame_to_show, finger_status, (10, 150), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                palm_status = "Palmo aperto" if left_palm_closed else "Palmo chiuso"
                cv2.putText(frame_to_show, palm_status, (10, 170), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                if left_palm_closed:
                    palm_x, palm_y = left_hand_points[0]
                    
                    cv2.putText(frame_to_show, f"Pugno: ({palm_x}, {palm_y})", (10, 210),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
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
                        #Denug
                        # print("Slide cooldown attivo con valore:", config.slide_cooldown_time)
                        # print("Direzione:", direction)
                        self.mouse_controller.perform_slide(direction)
                        self.slide_cooldown = time.time()
                        cv2.putText(frame_to_show, f"Slide: {direction}", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Gestione zoom (entrambe le mani)
            if right_hand_points and left_hand_points and right_finger_state and left_finger_state:
                zoom_gesture_active = self.hand_tracker.hand_tracker.check_zoom_gesture(right_finger_state, left_finger_state)
                
                right_index = right_hand_points[8]
                left_index = left_hand_points[8]
                
                current_distance = self.hand_tracker.hand_tracker.distance_between_points(right_index, left_index)
                
                zoom_status = "Zoom gesture: " + ("Attiva" if zoom_gesture_active else "Inattiva")
                cv2.putText(frame_to_show, zoom_status, (10, 230), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                cv2.line(frame_to_show, right_index, left_index, (0, 255, 0), 2)
                cv2.putText(frame_to_show, f"Dist: {int(current_distance)}", (10, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                zoom_performed, zoom_direction = self.mouse_controller.handle_zoom(current_distance, zoom_gesture_active)
                if zoom_performed and zoom_direction:
                    cv2.putText(frame_to_show, f"Zoom {zoom_direction}", (10, 90), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                self.mouse_controller.last_zoom_distance = None
                self.mouse_controller.zoom_distances = []
            
            # cv2.imshow("Hand Mouse Control", frame_to_show) //DEBUG
            
            
            
            key = cv2.waitKey(1)
            if key == 27:
                set_running(False)
            
            if not get_running():
                break
        
        self.hand_tracker.stop()
    
    def terminate(self):
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
    app = AirMouseApp()
    if app.initialize():
        try:
            app.run()
        except Exception as e:
            print(f"Errore durante l'esecuzione: {e}")
        finally:
            app.terminate()
            cv2.setNumThreads(0)
    else:
        print("Impossibile inizializzare l'applicazione")


if __name__ == "__main__":
    main()
