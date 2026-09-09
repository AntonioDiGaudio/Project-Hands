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
# Ora il secondo click viene emesso al CONTATTO del secondo pinch: non si
# aspetta ne' la riapertura ne' la conferma su piu' fotogrammi. Al sistema
# arrivano due click normali alla stessa identica posizione, che e' esattamente
# quello che manda un mouse vero: e' Windows a interpretarli come doppio click.
# Il valore e' misurato dall'emissione del primo click al CONTATTO del secondo
# pinch, che e' anche l'istante in cui il secondo click viene emesso: quello che
# vede Windows e' esattamente questa finestra, senza sorprese. Prima il secondo
# click usciva `pinch_confirm_frames` piu' tardi (2 fotogrammi, da 70 a 130 ms a
# seconda del frame rate) e la finestra doveva stare abbondantemente sotto i
# 500 ms per assorbirli. All'avvio il valore viene comunque limitato al
# GetDoubleClickTime vero del sistema, che l'utente puo' aver abbassato.
double_click_time = 0.45         # s: 0 disattiva il doppio click

# Fra i due click il cursore resta fermo, altrimenti il secondo cade altrove e
# il doppio click non viene riconosciuto: Windows accoppia due click solo se
# cadono dentro pochi pixel l'uno dall'altro (SM_CXDOUBLECLK, di fabbrica 4).
# Il blocco cade se la mano si sposta piu' di questa frazione di inquadratura.
#
# La misura si fa sulla NOCCA dell'indice, non sulla punta. Sulla punta il
# blocco si liberava da solo durante il secondo pinch — piegare il dito sposta
# la punta di circa 0.07 di inquadratura, il doppio di questa soglia — e il
# doppio click non poteva funzionare per costruzione. La nocca invece resta
# ferma mentre le dita si chiudono, quindi qui si puo' tenere una soglia
# stretta: 0.025 di inquadratura sono meno di due centimetri di mano.
double_click_hold_radius = 0.025

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
# Il default e' un COMPROMESSO fra due mani vere, non un valore taratissimo su
# una sola. Seconda mano misurata:
#
#     posa                  indice   medio   poll-indice  poll-medio  ind-medio
#     indice puntato          0.89    1.06       1.05        1.44        0.46
#     pollice+indice uniti    0.38    0.80       0.07        0.87        0.83
#     pinch a tre dita        0.47    0.44       0.16        0.10        0.19
#     pugno chiuso            0.21    0.24       0.24        0.22        0.15
#     mano ben aperta         0.83    0.99       0.98        1.35        0.42
#
# Le due mani vogliono soglie diverse: la prima separa pugno 0.27 da pinch 0.46
# (soglia ideale ~0.36), la seconda pugno 0.21 da pinch 0.37 (ideale ~0.29).
# 0.32 e' l'unico valore che sta dentro entrambi gli intervalli. Con 0.38 —
# tarato sulla prima mano — la seconda aveva il gate ESATTAMENTE sopra il
# proprio pinch (0.37 al 5o percentile, 0.38 di mediana): il blocco 'mano
# chiusa' si accendeva in mezzo a ogni click, e non partivano ne' click, ne'
# doppio click, ne' click destro.
#
# Questa soglia e' la prima cosa da tarare su una mano nuova: `python
# calibrate.py` la misura, `python diagnose.py` dice se e' lei a bloccarti.
index_control_ratio = 0.32

# La soglia sopra e' un LIVELLO su un valore che oscilla, e fra le due pose che
# deve separare c'e' pochissimo spazio: pugno 0.27, indice che pinza 0.46 (5o
# percentile 0.45). Ogni tanto quindi il gate si accende DENTRO un gesto, e
# prima ogni accensione azzerava la macchina a stati: da li' il drag che si
# staccava da solo e i click che partivano a fatica.
#
# Il rimedio non e' allargare la soglia (allargarla fa passare il pugno, che
# geometricamente e' un pinch a tre dita) ma non farla piu' distruggere niente:
#
#   * il gate blocca l'INGRESSO di una gesture, non ne uccide una in corso;
#   * se il fronte di chiusura di un pinch cade proprio in un fotogramma
#     bloccato, lo si recupera entro questa grazia invece di perderlo.
#
# La grazia e' corta apposta: un pugno tenuto chiuso resta bloccato per tutta la
# sua durata e all'apertura e' fuori finestra da un pezzo, quindi non puo'
# trasformarsi in un gesto.
gesture_start_grace = 0.15

# Seconda via per la stessa domanda: la mano e' aperta abbastanza per agire?
# Basta che la superi UNO dei due diti, indice o medio.
#
# Serve perche' il solo indice non regge. Con due mani misurate, l'intervallo
# utile per `index_control_ratio` si e' ristretto a (0.30, 0.37): la coda alta
# del pugno di una mano contro la coda bassa del pinch dell'altra. Dentro sette
# centesimi deve starci anche il rumore del modello, e non ci sta — infatti
# nella diagnosi il gate cadeva in mezzo ai click.
#
# Il medio separa le stesse due pose molto meglio, e su entrambe le mani:
#
#     posa                    medio (mano A)   medio (mano B)
#     pugno chiuso                0.32             0.24
#     pinch pollice+indice        0.84             0.80
#     pinch a tre dita            0.47             0.44
#
# Quando pinzi l'indice il medio resta disteso; quando chiudi il pugno no.
# 0.40 sta sopra ogni pugno misurato (95o percentile 0.35) e sotto ogni pinch.
#
# ATTENZIONE a non confonderla con la vecchia soglia omonima, che era una
# condizione da soddisfare INSIEME all'indice (AND) e per il click destro: li'
# bloccava la posa giusta, perche' un medio che pinza col pollice (0.47) e' quasi
# identico a un medio ripiegato nel palmo (0.46). Qui e' un'alternativa (OR) e
# puo' solo lasciar passare di piu', mai bloccare.
middle_control_ratio = 0.40

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
# Misurato: pollice-indice vale 1.19 nella posa di puntamento, quindi 1.05
# lascia 0.14 di margine sopra il rumore (la posa ferma oscilla fra 1.18 e 1.22)
# e fa scattare il blocco molto prima. Con 0.95 il blocco arrivava a chiusura
# gia' iniziata per un quinto: quel quinto e' il puntatore che scende.
pinch_freeze_ratio = 1.05

# Quanto deve essere sceso il rapporto rispetto al suo massimo negli ultimi
# `pinch_approach_window` secondi perche' si consideri un avvicinamento vero.
#
# 0.10 e non 0.20: e' il livello (`pinch_freeze_ratio`) a difendere dai falsi
# positivi, non questa soglia. Nella posa di puntamento il rapporto sta a 1.19
# con un'escursione di 0.04, quindi non arriva mai sotto 1.05 per conto suo, e
# chiedere un calo grosso serviva solo a far partire il blocco in ritardo.
pinch_approach_drop = 0.10
pinch_approach_window = 0.5

# Il cursore sta sulla PUNTA dell'indice, ed e' la punta che si sposta quando
# pinzi: misurata su una mano vera, l'estensione punta-nocca passa da 0.93 a
# 0.46 chiudendo il pinch. La distanza pollice-indice se ne accorge piu' tardi,
# perche' all'inizio del gesto si muove soprattutto il pollice. Un calo di 0.06
# della piega dell'indice e' quattro volte il rumore della posa ferma (0.92 -
# 0.95) e anticipa il blocco di qualche fotogramma.
index_curl_drop = 0.06

# ...ma solo a mano quasi ferma. Durante una spazzata larga la prospettiva
# accorcia l'indice da sola, e li' bloccare il cursore vorrebbe dire piantarlo
# in mezzo a un movimento. Un click si fa da fermi, sotto questa velocita'.
click_pose_speed = 900.0         # px schermo/s

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

# La posa di scroll richiede che indice e medio siano DAVVERO distesi, oltre
# che contati come alzati. Non e' un dettaglio: riconoscere questa posa
# azzittisce i due rilevatori di pinch, quindi un falso positivo qui non
# produce solo uno scroll indesiderato, fa sparire il click e il click destro
# finche' dura. Misurato (estensione punta-nocca):
#
#     posa                    indice   medio
#     due dita tese (scroll)    0.79     0.94
#     puntamento                0.93     0.46
#     pinch pollice+indice      0.46     0.84
#
# Solo la posa di scroll ha entrambe le dita distese. 0.65 sta in mezzo con
# circa 0.15 di margine da tutte le altre.
scroll_extension_ratio = 0.65
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

# Per quanto si tollera di perdere la posa prima di dimenticare la distanza di
# riferimento. Non e' un dettaglio: con due mani in campo MediaPipe ne perde una
# di continuo (misurato: due mani viste nel 65% dei fotogrammi), e azzerare il
# riferimento a ogni buco vuol dire ricominciare a misurare la variazione da
# capo. Il 18% richiesto non veniva raggiunto mai, e lo zoom non partiva senza
# che niente segnalasse un problema.
zoom_lost_grace = 0.4

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
