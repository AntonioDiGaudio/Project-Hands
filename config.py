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

# Quanto ci mette il cursore a riassorbire lo scarto accumulato durante un
# congelamento. Mentre e' congelato il cursore resta fermo ma la mano no: alla
# ripresa la posizione vera e' altrove, e senza questo il cursore ci SALTA.
# Si vedeva soprattutto all'inizio di un drag, dove il salto avviene a tasto
# gia' premuto e trascina quello che stai afferrando.
cursor_settle_time = 0.35

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

# Click destro = pinch a TRE DITA: pollice + indice + medio tutti insieme.
# La grandezza misurata e' max(pollice-indice, pollice-medio), cioe' "la piu'
# lontana delle due punte": va sotto soglia solo quando entrambe toccano.
#
# Prima era il solo pollice+medio, e su una mano vera non funziona. Misurato:
# nella posa di puntamento il pollice sta gia' appoggiato sul medio ripiegato a
# 0.22, contro lo 0.12 del pinch fatto apposta. Margine 0.06, dentro il rumore
# del tracciamento: qualunque soglia li' in mezzo o non scatta mai o scatta
# mentre punti. Con max() le pose che arrivano al riconoscitore stanno tutte
# sopra 0.65 e il pinch a tre dita sta intorno a 0.20: margine 0.45.
#
#     posa            max(poll-indice, poll-medio)
#     puntamento              1.18 - 1.22
#     mano aperta             1.27 - 1.31
#     pinch pollice+indice    0.96 - 1.00
#     pollice+medio           0.65 - 0.82
#     pinch a tre dita        ~0.20
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

# Doppio click: due pinch ravvicinati.
#
# Non era implementato affatto, e non bastava "cliccare due volte in fretta":
# `click_cooldown` scartava il secondo click, e ogni ciclo di pinch costa
# comunque pinch_confirm_frames + pinch_release_frames di sola conferma (5
# fotogrammi, circa 170 ms a 30 fps). Due cicli completi non stavano dentro i
# 500 ms che Windows concede (GetDoubleClickTime).
#
# Ora il secondo click viene emesso alla CHIUSURA del secondo pinch invece che
# alla riapertura: si risparmiano i fotogrammi di conferma del rilascio, e il
# cooldown non si applica dentro la finestra. Al sistema arrivano due click
# normali alla stessa posizione, che e' esattamente quello che manda un mouse
# vero: e' Windows a interpretarli come doppio click.
# Il valore e' 0.40, non 0.50, e il margine serve. La finestra viene misurata
# dall'emissione del primo click al CONTATTO del secondo pinch, mentre a
# Windows il secondo click arriva `pinch_confirm_frames` piu' tardi (2
# fotogrammi, circa 0.07 s a 30 fps). Con 0.45 il caso peggiore diventa 0.52 e
# sfora i 500 ms di GetDoubleClickTime; con 0.40 resta 0.47.
double_click_time = 0.40         # s: 0 disattiva il doppio click

# Fra i due click il cursore resta fermo, altrimenti il secondo cade altrove e
# il doppio click non viene riconosciuto. Il blocco cade subito se la mano si
# sposta piu' di questa frazione di inquadratura: cosi' un click singolo non
# lascia il cursore incollato.
double_click_hold_radius = 0.035

# ---------------------------------------------------------------------------
# Anti falsi positivi
# ---------------------------------------------------------------------------
require_pointing_pose = True     # nessuna gesture se la mano non e' in posa di controllo

# Soglia della posa di controllo, misurata come distanza punta-nocca
# dell'indice divisa per la dimensione della mano (polso -> nocca del medio).
#
# I valori qui sotto sono MISURATI su una mano vera con `diagnose.py`, non
# stimati. Mediane per posa:
#
#     posa                  indice   medio   poll-indice  poll-medio
#     indice puntato          0.93    0.46       1.19         0.22
#     pollice+indice uniti    0.46    0.84       0.14         0.98
#     pollice+medio uniti     0.73    0.47       0.74         0.12
#     pugno chiuso            0.27    0.32       0.20         0.28
#     mano ben aperta         0.79    0.94       0.96         1.29
#
# I commenti precedenti dichiaravano "indice teso ~1.3-1.5, pinch ~0.9-1.2,
# pugno ~0.4-0.6", e non erano mai stati verificati. La misura dice 0.93 / 0.46
# / 0.27: un fattore 1.6 di distanza, e soprattutto una scala diversa. Il
# rapporto e' lunghezza dell'indice diviso lunghezza del palmo, che
# anatomicamente sta intorno a 0.8-0.9 a dito teso — non poteva valere 1.4.
#
# Il default che ne discendeva, 0.75, coincideva col valore dell'indice TESO:
# passava solo a dito perfettamente dritto e falliva appena lo pieghi per
# pinzare, che e' esattamente il momento del click. Risultato: `gated_reason`
# diventava "mano chiusa" durante ogni click e non partiva mai niente, mentre
# il cursore continuava a muoversi perche' non passa da quel gate.
#
# La soglia va nel mezzo fra pinch (0.46) e pugno (0.27): deve lasciar passare
# il pinch e fermare il pugno. Usa `python calibrate.py` per i valori della tua
# mano, e `python diagnose.py` se una gesture non parte e non capisci perche'.
index_control_ratio = 0.38

# NOTA: `middle_control_ratio` e' stato rimosso. Era un tentativo di salvare il
# click destro pollice+medio chiedendo che il medio fosse DISTESO, ed era lo
# stesso errore appena corretto sull'indice, rifatto sul medio. Misurato su una
# mano vera: un medio che pinza col pollice sta a 0.47, un medio ripiegato nel
# palmo a 0.46. Non e' esecuzione sbagliata — un dito piegato per toccare il
# pollice e' geometricamente quasi identico a un dito piegato nel palmo, e
# infatti l'indice fa lo stesso (0.93 teso, 0.46 mentre pinza). Quella soglia
# non separava niente e bloccava anche la posa corretta. Il click destro ora e'
# un pinch a tre dita, che si separa da solo.

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
# 0 = lite, 1 = full. Misurato su questa macchina, con la webcam reale e ogni
# configurazione in un processo pulito (misurarle di fila nello stesso processo
# le contamina: vedi benchmark.py):
#
#     complessita' 0    14.4 ms per fotogramma
#     complessita' 1    16.7 ms per fotogramma   (+2.3 ms)
#
# Il default e' 1. Il tetto reale del loop e' la webcam, che consegna 30 fps
# cioe' un fotogramma ogni 33 ms: 2.3 ms in piu' non tolgono un solo
# fotogramma, e in cambio i landmark del pollice durante il pinch sono
# nettamente piu' stabili. E' il pollice che decide se un click parte, quindi
# quei 2.3 ms comprano precisione esattamente dove serve.
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
