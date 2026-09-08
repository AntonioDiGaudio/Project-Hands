"""
Configurazione di AirMouse.

Nota sulle unita' di misura:

* Le soglie delle gesture NON sono in pixel ma in **frazioni della dimensione
  della mano** (distanza polso -> nocca del medio). Cosi' una gesture funziona
  identica che la mano sia a 30 cm o a 1 m dalla webcam: e' la causa numero uno
  di falsi positivi nelle versioni precedenti.
* Le soglie del cursore (deadzone, travel) sono in pixel di schermo.
* I tempi sono in secondi.
"""

# ---------------------------------------------------------------------------
# Cursore
# ---------------------------------------------------------------------------
overscan_x = 1.6                 # quanto "allarga" l'area utile della camera
overscan_y = 1.6
cursor_speed_multiplier = 1.0
deadzone_threshold = 2.0         # px schermo: sotto questo delta il cursore non si muove

# Filtro One Euro: e' il filtro che decide fluidita' vs latenza.
#   min_cutoff piu' basso  -> piu' stabile da fermo, piu' molle in movimento
#   beta       piu' alto   -> segue meglio i movimenti veloci
one_euro_min_cutoff = 1.2
one_euro_beta = 0.02
one_euro_d_cutoff = 1.0

# Compatibilita' con la vecchia GUI (mappato su one_euro_min_cutoff).
alpha_smooth = 0.4

# ---------------------------------------------------------------------------
# Gesture: soglie normalizzate sulla dimensione della mano
# ---------------------------------------------------------------------------
# Pinch pollice+indice = click sinistro / drag.
pinch_close_ratio = 0.45         # sotto  -> pinch chiuso
pinch_open_ratio = 0.70          # sopra  -> pinch aperto (isteresi Schmitt)

# Pinch pollice+medio = click destro.
right_pinch_close_ratio = 0.45
right_pinch_open_ratio = 0.70

# Un pinch deve restare stabile per N frame prima di essere accettato / rilasciato.
pinch_confirm_frames = 2
pinch_release_frames = 3

# Distinzione click vs drag: sotto drag_hold_time e' un click, sopra e' un drag.
drag_hold_time = 0.35
click_max_travel = 45.0          # px schermo: se il cursore vaga di piu', non e' un click
click_cooldown = 0.25
right_click_cooldown = 0.45

# ---------------------------------------------------------------------------
# Anti falsi positivi
# ---------------------------------------------------------------------------
require_pointing_pose = True     # nessuna gesture se la mano non e' in posa di controllo

# Soglia della posa di controllo, misurata come distanza punta-nocca
# dell'indice divisa per la dimensione della mano.
#
#     indice teso      ~1.3 - 1.5
#     indice che pinza ~0.9 - 1.2
#     pugno chiuso     ~0.4 - 0.6
#
# La soglia va nel mezzo fra pinch e pugno: deve lasciar passare il pinch
# (altrimenti il click si annulla da solo mentre lo fai) e fermare il pugno.
# Usa `python calibrate.py` per leggere i valori reali della tua mano.
index_control_ratio = 0.75

# La stessa soglia per il medio, usata dal click destro. Il pinch pollice+medio
# viene proprio ignorato se il medio non e' disteso: da ripiegato nel palmo, col
# pollice appoggiato sopra, la distanza pollice-medio vale gia' circa 0.35 e
# sarebbe indistinguibile da un pinch fatto apposta.
middle_control_ratio = 0.75

# Il cursore si congela quando il pinch scende sotto questa soglia. Va tenuta
# piu' alta di pinch_open_ratio: cosi' il blocco scatta gia' durante
# l'avvicinamento delle dita, prima che la punta dell'indice (che e' il
# cursore) si sia spostata in modo percepibile.
#
# ATTENZIONE: da sola questa soglia non basta, ed e' stata la causa del
# "cursore che si pianta". E' un LIVELLO, e ci sono pose ferme che ci stanno
# sotto per sempre: nella normale posa di puntamento il medio e' ripiegato nel
# palmo col pollice appoggiato sopra, quindi il rapporto pollice-medio vale
# circa 0.35 e il cursore restava congelato al 100% dei fotogrammi. Per questo
# il congelamento richiede anche un AVVICINAMENTO in corso e ha una durata
# massima.
pinch_freeze_ratio = 0.95

# Quanto deve essere sceso il rapporto rispetto al suo massimo negli ultimi
# `pinch_approach_window` secondi perche' si consideri un avvicinamento vero.
pinch_approach_drop = 0.20
pinch_approach_window = 0.5

# Durata massima di un congelamento del cursore. Oltre questa, le dita sono
# semplicemente ferme a mezz'aria e il cursore torna libero.
pinch_freeze_max_time = 0.7
min_handedness_score = 0.70      # scarta le mani riconosciute con poca confidenza
hand_reacquire_grace = 0.25      # s di silenzio dopo che una mano ricompare
max_gesture_speed = 2500.0       # px schermo/s: sopra, i click sono ignorati
finger_extend_ratio = 1.12       # dito esteso se dist(tip,polso) > ratio * dist(pip,polso)
finger_retract_ratio = 1.02      # isteresi sulla stessa misura
finger_confirm_frames = 2
teleport_reset_ratio = 0.45      # salto > 45% del frame -> riaggancio, gesture inibite
cursor_engage_frames = 3         # fotogrammi consecutivi con la mano prima di muovere il cursore

# Quanti fotogrammi senza mano si tollerano prima di dichiararla persa. Il
# modello perde l'aggancio per un fotogramma di continuo; senza tolleranza ogni
# buco faceva scattare hand_lost, che azzera lo stato e apre 0.25 s di grazia:
# il cursore si inchiodava a intermittenza e un drag in corso veniva rilasciato.
hand_lost_frames = 3

# ---------------------------------------------------------------------------
# Scroll a due dita (indice + medio estesi, movimento verticale)
# ---------------------------------------------------------------------------
enable_scroll = True
scroll_deadzone = 0.012          # frazione di altezza frame prima di scrollare
# Scatti di rotellina per un'altezza intera di frame. L'unita' e' lo scatto
# (WHEEL_DELTA), non un numero arbitrario: vedi mouse_controller.scroll.
scroll_gain = 25.0
scroll_max_notches = 4           # tetto per evento, contro le sbandate
scroll_cooldown = 0.03

# ---------------------------------------------------------------------------
# Zoom a due mani (indici estesi su entrambe le mani)
# ---------------------------------------------------------------------------
enable_zoom = True
zoom_trigger_ratio = 0.18        # variazione relativa della distanza per far scattare uno zoom
zoom_cooldown_time = 0.35
zoom_smooth_factor = 5
zoom_notches = 1                 # scatti di ctrl+rotellina per passo di zoom

# ---------------------------------------------------------------------------
# Slide (palmo chiuso della mano non dominante -> frecce direzionali)
# ---------------------------------------------------------------------------
enable_slide = False             # off: e' la gesture piu' soggetta a falsi positivi
slide_cooldown_time = 0.40
slide_margin = 0.28              # frazione del frame che conta come bordo

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
# 640x480 e' il default: MediaPipe ridimensiona comunque a 192x192 internamente,
# quindi abbassare la risoluzione NON fa guadagnare fps ma peggiora la precisione
# dei landmark (misurato: 320x240 -> 37.9 ms/frame, 640x480 -> 35.1 ms/frame).
camera_width = 640
camera_height = 480
camera_backend = "auto"          # "auto" | "msmf" | "dshow" | "v4l2" | "any"
camera_fourcc = "MJPG"           # aiuta molto su USB 2.0 / Raspberry Pi
camera_buffer_size = 1           # niente frame vecchi in coda = niente latenza

# ---------------------------------------------------------------------------
# Modello
# ---------------------------------------------------------------------------
# 0 = lite, 1 = full. Misurato su questa macchina, con la webcam reale:
#
#     complessita' 0    14.9 ms per fotogramma
#     complessita' 1    17.5 ms per fotogramma   (+2.6 ms)
#
# Il default e' 1. Il tetto reale del loop e' la webcam, che consegna 30 fps
# cioe' un fotogramma ogni 33 ms: 2.6 ms in piu' non tolgono un solo
# fotogramma, e in cambio i landmark del pollice durante il pinch sono
# nettamente piu' stabili. E' il pollice che decide se un click parte, quindi
# quei 2.6 ms comprano precisione esattamente dove serve.
#
# Su una macchina che non regge, il governor delle prestazioni scende da solo
# a 0: e' la prima cosa che toglie, perche' e' anche la piu' redditizia.
model_complexity = 1
min_detection_confidence = 0.6
min_tracking_confidence = 0.5
preferred_hand = "Right"

# Il tetto di mani segue semplicemente enable_zoom: 2 se lo zoom serve, 1
# altrimenti. Non c'e' nessun sondaggio periodico, perche' ricostruire il grafo
# MediaPipe costa circa 25 ms e azzera il tracciamento (scatto visibile del
# cursore), e perche' il costo del modello scala con le mani effettivamente
# rilevate e non con questo tetto.

# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
target_fps = 60                  # tetto del loop; il collo di bottiglia reale e' il modello
auto_performance = True          # degrada da solo su CPU deboli

# Throttling in assenza di mani.
#
# Misurato: con nessuna mano inquadrata il modello costa comunque circa 22 ms
# per fotogramma, perche' il rilevatore di palmo gira a vuoto su tutta
# l'immagine. Quando invece una mano e' agganciata MediaPipe salta il
# rilevatore e usa solo il modello dei landmark, che e' piu' leggero.
#
# Siccome l'applicazione sta ferma senza mani per la maggior parte del tempo,
# rallentare il ritmo in quella fase e' il singolo risparmio piu' grosso: la
# CPU a riposo scende di circa 4 volte. Appena una mano compare si torna
# immediatamente a pieno ritmo, quindi il ritardo di aggancio resta impercettibile.
idle_throttle = True
idle_after_seconds = 1.0         # dopo quanto silenzio si entra in modalita' risparmio
idle_detect_fps = 8              # ritmo del rilevamento quando non c'e' nessuna mano
perf_min_detect_fps = 12         # sotto questa soglia riduce la qualita'
perf_target_headroom = 0.85      # frazione del budget frame da non superare
show_debug_window = True
draw_landmarks = True
overlay_enabled = True
enable_profiler = False          # sys.setprofile: solo per diagnosi, rallenta tutto

# ---------------------------------------------------------------------------
# Modalita'
# ---------------------------------------------------------------------------
drag_mode_enabled = True
enable_right_click = True
