"""
Modulo principale dell'applicazione AirMouse con profiling integrato.
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

# Importa il profiler
from simple_profiler import profiler, ProfileSection

class AirMouseApp:
    def __init__(self):
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
        
        # Statistiche FPS
        self.frame_times = []
        self.max_frame_times = 30  # Numero di frame da considerare per le statistiche
    
    def initialize(self):
        try:
            # Selezione della webcam
            selected_cam = self.webcam_manager.select_camera_gui()
            
            # Dopo la selezione webcam, lancia la GUI delle impostazioni in un thread
            gui_thread = threading.Thread(target=create_settings_gui)
            gui_thread.daemon = True
            gui_thread.start()
            
            # Apertura della webcam selezionata
            self.cap = self.webcam_manager.open_camera(selected_cam)
            
            return True
        except Exception as e:
            print(f"Errore durante l'inizializzazione: {e}")
            return False
    
    def run(self):
        if self.cap is None:
            print("Webcam non inizializzata")
            return
        
        # Ciclo principale per il riconoscimento della mano e il movimento del cursore
        frame_count = 0
        start_time = time.time()
        last_stats_time = start_time
        
        while get_running():
            frame_start_time = time.time()
            
            # Profila l'intero frame
            with ProfileSection("Frame completo"):
                # Lettura frame
                with ProfileSection("Lettura frame"):
                    ret, frame = self.cap.read()
                    if not ret:
                        continue
                    frame = cv2.flip(frame, 1)
                
                # Rilevamento mani
                with ProfileSection("Rilevamento mani"):
                    frame, results = self.hand_tracker.find_hands(frame, draw=False)
                    h, w, _ = frame.shape
                    hands_data = self.hand_tracker.find_positions(frame, results)
                    right_hand_points = hands_data.get("Right")
                    left_hand_points = hands_data.get("Left")
                    right_finger_state = self.hand_tracker.fingers_up(right_hand_points)
                    left_finger_state = self.hand_tracker.fingers_up(left_hand_points)
                
                # Gestione della mano destra (controllo del mouse)
                with ProfileSection("Controllo mouse"):
                    if right_hand_points and right_finger_state and self.preferred_hand == "Right":
                        index_up, middle_up, ring_up, pinky_up = right_finger_state
                        ix, iy = right_hand_points[8]  # Indice
                        px, py = right_hand_points[4]  # Pollice
                        
                        # Controllo blocco cursore durante il gesto di click
                        if ring_up == 1:
                            self.mouse_controller.move_cursor(ix, iy, w, h)
                        
                        # Gestione del click
                        dist = self.hand_tracker.distance_between_points((ix, iy), (px, py))
                        self.mouse_controller.handle_click(dist, self.drag_mode_enabled, self.enable_right_click, pinky_up)
                
                # Gestione della mano sinistra (zoom e slide)
                with ProfileSection("Gestione slide"):
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
                with ProfileSection("Gestione zoom"):
                    if right_hand_points and left_hand_points and right_finger_state and left_finger_state:
                        # Verifica se è attiva la gesture per lo zoom (solo indici alzati)
                        zoom_gesture_active = self.hand_tracker.check_zoom_gesture(right_finger_state, left_finger_state)
                        
                        # Indici delle due mani
                        right_index = right_hand_points[8]
                        left_index = left_hand_points[8]
                        
                        # Gestione dello zoom
                        current_distance = self.hand_tracker.distance_between_points(right_index, left_index)
                        zoom_performed, zoom_direction = self.mouse_controller.handle_zoom(current_distance, zoom_gesture_active)
                    else:
                        # Reset delle variabili se non ci sono mani rilevate
                        self.mouse_controller.last_zoom_distance = None
                        self.mouse_controller.zoom_distances = []
                
                # Visualizzazione debug e statistiche
                with ProfileSection("Visualizzazione"):
                    # Calcola FPS
                    frame_count += 1
                    elapsed_time = time.time() - frame_start_time
                    self.frame_times.append(elapsed_time)
                    if len(self.frame_times) > self.max_frame_times:
                        self.frame_times.pop(0)
                    
                    avg_frame_time = sum(self.frame_times) / len(self.frame_times)
                    fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
                    
                    # Aggiungi un overlay con i valori di configurazione e statistiche
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (10, 10), (300, 250), (0, 0, 0), -1)
                    
                    # Aggiungi statistiche di profiling
                    stats = profiler.get_stats()
                    profiling_texts = [
                        f"FPS: {fps:.1f}",
                        f"Frame time: {avg_frame_time*1000:.1f} ms",
                    ]
                    
                    # Aggiungi i tempi delle sezioni principali
                    for section in ["Lettura frame", "Rilevamento mani", "Controllo mouse", "Gestione slide", "Gestione zoom", "Visualizzazione"]:
                        if section in stats:
                            profiling_texts.append(f"{section}: {stats[section]['avg']:.1f} ms")
                    
                    # Disegna i valori
                    for i, text in enumerate(profiling_texts):
                        cv2.putText(overlay, text, (15, 30 + i * 20), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    # Applica l'overlay con trasparenza
                    alpha = 0.7  # Trasparenza dell'overlay
                    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                    
                    # Mostra il frame
                    cv2.imshow("AirMouse Profiling", frame)
            
            # Stampa le statistiche ogni 5 secondi
            if time.time() - last_stats_time > 5:
                profiler.print_stats()
                last_stats_time = time.time()
            
            # Controllo chiusura con ESC
            key = cv2.waitKey(1)
            if key == 27:  # ESC key
                set_running(False)
            elif key == ord('p'):  # Premi 'p' per stampare statistiche dettagliate
                profiler.print_stats()
                # Non resettare le statistiche per mantenere i dati storici
            
            if not get_running():
                break
        
        # Stampa le statistiche finali
        print("\n=== STATISTICHE FINALI ===")
        total_time = time.time() - start_time
        print(f"Tempo totale di esecuzione: {total_time:.2f} secondi")
        print(f"Frame totali elaborati: {frame_count}")
        print(f"FPS medi: {frame_count / total_time:.2f}")
        profiler.print_stats()
    
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
    else:
        print("Impossibile inizializzare l'applicazione")


if __name__ == "__main__":
    main()
