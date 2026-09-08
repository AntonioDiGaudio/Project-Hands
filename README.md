# AirMouse

Controllo del mouse tramite i gesti della mano rilevati da una webcam, con
MediaPipe e OpenCV.

## Installazione

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Serve Python 3.10 o superiore. Su Linux installa anche `python3-xlib`, che
viene tirato dentro automaticamente dal file dei requisiti.

## Avvio

```bash
python main.py
```

Opzioni:

| Flag | Effetto |
|---|---|
| `--no-window` | nessuna finestra webcam: e' la modalita' piu' leggera |
| `--no-overlay` | finestra webcam senza pannello diagnostico |
| `--benchmark` | misura le prestazioni della macchina e termina |
| `--profile` | attiva il profiler per modulo (rallenta l'esecuzione) |
| `--no-auto-perf` | disattiva la degradazione automatica della qualita' |

Prima di configurare a mano, conviene lanciare `python main.py --benchmark`:
misura backend webcam, costo del modello e costo del contorno su quella
specifica macchina e suggerisce i parametri di conseguenza.

## Gesture

Tutte a una mano. La mano non dominante serve solo a zoom e slide.

| Gesto | Azione |
|---|---|
| Indice non ripiegato | attiva il controllo; il cursore segue la punta dell'indice |
| Mano chiusa a pugno | tutto inerte, nessuna gesture possibile |
| Pollice + indice, tocco breve | click sinistro |
| Pollice + indice, tenuto | drag (premi, sposta, rilascia riaprendo) |
| Pollice + medio | click destro |
| Indice + medio estesi, su e giu' | scroll |
| Indici estesi su entrambe le mani | zoom |

Tasti nella finestra webcam: `ESC` esci, `D` scheletro, `O` pannello,
`H` nascondi la finestra.

### Perche' non partono click a caso

Il set di gesture e' costruito attorno a cinque regole, applicate a ogni gesto:

1. **Soglie normalizzate sulla dimensione della mano.** Nessuna soglia e' in
   pixel: tutte sono frazioni della distanza polso-nocca. La stessa gesture
   funziona identica a 30 cm e a 1 m dalla webcam. Con le soglie in pixel
   assoluti bastava avvicinarsi alla webcam perche' il click partisse da solo.
2. **Isteresi.** Chiudere un pinch e riaprirlo usano due soglie diverse. Fra le
   due non succede niente, quindi un valore che oscilla al confine non produce
   una raffica di eventi.
3. **Conferma temporale.** Un cambio di stato deve reggere per piu' fotogrammi
   consecutivi. Un singolo fotogramma sbagliato del modello non genera eventi.
4. **Fronte, non livello.** Ogni click e' emesso sulla transizione e va
   riarmato riaprendo la mano.
5. **Gating.** I click sono bloccati quando la mano si muove troppo veloce,
   subito dopo che rientra nell'inquadratura, e quando la mano e' chiusa a
   pugno.

La distinzione fra pugno e pinch merita una nota, perche' in entrambi pollice e
indice sono vicini. A separarli e' quanto e' disteso l'indice, misurato **dalla
nocca** e non dal polso:

    indice teso      ~1.3 - 1.5
    indice che pinza ~0.9 - 1.2
    pugno chiuso     ~0.4 - 0.6

Misurando dal polso, il pinch fa scendere la punta dell'indice sotto la
falange e la mano risulta "chiusa" proprio mentre stai cliccando: il gate
scatta e annulla click e drag.

In piu' il cursore si **congela** appena il pinch inizia a chiudersi: siccome il
cursore segue la punta dell'indice, che e' anche il dito che si muove per
pinzare, senza questo accorgimento ogni click cadrebbe qualche pixel sotto il
bersaglio.

### Taratura rapida

Il modo giusto di tarare non e' a occhio:

```bash
python calibrate.py
```

Apre una finestra che mostra i valori misurati dal vivo. Premi **SPAZIO una
volta sola**: la procedura ti guida attraverso tre pose (indice puntato, pinch,
pugno) con un conto alla rovescia per ciascuna e registra da sola, poi calcola
le soglie sulla tua mano e le salva con `S`. Se non muovi la mano o le pose
risultano indistinguibili te lo dice invece di produrre soglie inservibili.

Le soglie predefinite sono ragionevoli ma non sono misurate sulla tua mano.

| Sintomo | Rimedio |
|---|---|
| Click e drag non partono mai | *Soglia mano aperta/chiusa* troppo alta: pinzando l'indice si piega e il gate la scarta. Lancia `calibrate.py` |
| Il cursore scivola mentre clicchi | alza *Blocco cursore nel click* |
| Click da solo | abbassa *Chiusura pinch*, alza *Frame di conferma* |
| Click che non partono | alza *Chiusura pinch*, abbassa *Frame di conferma* |
| Drag che si stacca | alza *Frame di rilascio* e *Apertura pinch* |
| Cursore che trema da fermo | abbassa *Stabilita' da fermo*, alza *Zona morta* |
| Cursore in ritardo | alza *Reattivita' in movimento* |

## Prestazioni

Misure prese su questa macchina (Windows 11, webcam 640x480):

| Voce | Costo |
|---|---|
| Modello, nessuna mano inquadrata | 22-24 ms per fotogramma |
| Modello, complessita' 0 vs 1 | 23.9 ms contro 28.3 ms |
| Backend webcam MSMF contro DSHOW | 30.2 fps contro 17.0 fps |
| `cvtColor` con buffer riusato | 0.03 ms |
| Overlay a pannello contro overlay a frame intero | 0.02 ms contro 0.34 ms |

Due risultati hanno guidato le scelte di progetto:

**La risoluzione della webcam non influenza la velocita' del modello.**
MediaPipe ridimensiona comunque l'immagine a 192x192 al suo interno: 320x240
costa 37.9 ms e 640x480 ne costa 35.1. Abbassare la risoluzione peggiorava
quindi la precisione dei landmark senza far guadagnare nulla. Il default e'
640x480.

**Il costo scala con le mani effettivamente rilevate, non con il tetto
impostato.** Con nessuna mano inquadrata, `max_num_hands` a 1 o a 2 costa
uguale (22.7 contro 22.0 ms). Il tetto viene quindi impostato una volta sola, a
partire da `enable_zoom`, e lasciato stare: un meccanismo che lo alternava per
sondare la presenza di una seconda mano e' stato rimosso, perche' ricostruire
il grafo MediaPipe costa circa 25 ms e azzera lo stato di tracciamento,
producendo uno scatto visibile del cursore a ogni sondaggio.

### Risparmio a riposo

Senza mani inquadrate il modello spende comunque circa 22 ms per fotogramma
cercando un palmo che non c'e', ed e' la condizione in cui il programma passa
la maggior parte del tempo. Con `idle_throttle` il ritmo del rilevamento scende
a `idle_detect_fps` finche' non compare una mano:

```
senza throttling   30 fps x 24 ms  =  72% di un core
con throttling     misurato        =  17-18% di un core
```

Appena una mano compare si torna immediatamente a pieno ritmo.

### CPU deboli e Raspberry Pi

Con `auto_performance` attivo il programma misura il tempo reale di inferenza e
scala la qualita' da solo, in quattro livelli: prima smette di disegnare lo
scheletro, poi chiude la finestra di debug e passa a una mano sola, infine
forza il modello leggero e abbassa la risoluzione. Risale solo dopo un periodo
prolungato di margine, per non oscillare fra due livelli.

Il parametro che conta di piu' su hardware lento e' `idle_detect_fps`: siccome
la condizione "nessuna mano inquadrata" e' quella piu' frequente e costa
comunque un'inferenza intera, abbassarlo a 4 taglia il consumo a riposo piu' di
qualsiasi altra regolazione.

Impostazioni consigliate su hardware molto lento:

```bash
python main.py --no-window
```

più `camera_fourcc = "MJPG"` in `config.py`, che su USB 2.0 e su Raspberry Pi
e' spesso la differenza fra 10 e 30 fps.

## Configurazione

I parametri stanno in `config.py`, con i valori di ogni sessione salvati in
`Profiles/settings.txt`. La finestra delle impostazioni li espone tutti con una
spiegazione per ciascuno e li applica a caldo, senza riavviare.

Aggiungere un parametro si fa in `settings_schema.py`: GUI, salvataggio e
caricamento si generano da li'.

## Test

```bash
python test_gestures.py    # macchina a stati, senza webcam
python test_pipeline.py    # pipeline completa con webcam, senza toccare il mouse
python calibrate.py        # misura le soglie sulla tua mano
python test_calibrate.py   # procedura di calibrazione, senza webcam
```

`test_gestures.py` copre in particolare i casi che producevano falsi positivi,
fra cui il mignolo chiuso che generava un click destro al secondo.

## Struttura

| File | Ruolo |
|---|---|
| `main.py` | punto di ingresso, argomenti, lock a istanza singola |
| `app.py` | loop principale, throttling, tracciamento adattivo |
| `hand_tracker.py` | MediaPipe, landmark, stato delle dita con isteresi |
| `gesture_recognizer.py` | macchina a stati delle gesture |
| `mouse_controller.py` | filtro One Euro, movimento cursore, eventi |
| `webcam_manager.py` | selezione webcam, cattura in thread |
| `perf.py` | degradazione automatica della qualita' |
| `settings_schema.py` | schema dichiarativo dei parametri |
| `settings_gui.py` | finestra impostazioni generata dallo schema |
| `benchmark.py` | misura le prestazioni della macchina |
| `calibrate.py` | misura le soglie delle gesture sulla tua mano |
