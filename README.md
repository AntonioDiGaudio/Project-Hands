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
| Pollice + **medio disteso** | click destro (col medio ripiegato non conta: vedi sotto) |
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
   riarmato riaprendo la mano. Un rilevatore parte **disarmato**: finche' non
   ha visto le dita davvero separate non produce nessun fronte, quindi una mano
   che entra in scena gia' "chiusa" non clicca.
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

Lo stesso vale per il **medio**, ed e' la lezione piu' cara di questo progetto.
Il click destro e' "pollice + medio uniti", ma nella normale posa di puntamento
il medio e' ripiegato nel palmo e il pollice gli si appoggia sopra: la distanza
fra le due punte vale gia' circa `0.35` della mano, cioe' meno della soglia di
chiusura. Senza sapere se il medio e' **disteso**, la posa di puntamento e' un
pinch medio a tutti gli effetti, con due conseguenze misurate:

* il cursore restava congelato **120 fotogrammi su 120**, cioe' per sempre;
* il primo momento in cui aprivi la mano partiva un click destro non richiesto.

Per questo il pinch destro viene proprio ignorato finche' `middle_extension`
non supera `middle_control_ratio`.

In piu' il cursore si **congela** appena il pinch inizia a chiudersi: siccome il
cursore segue la punta dell'indice, che e' anche il dito che si muove per
pinzare, senza questo accorgimento ogni click cadrebbe qualche pixel sotto il
bersaglio. Il congelamento richiede pero' un **avvicinamento in corso**, non un
semplice "sotto soglia": e' un livello, e le pose ferme che ci stanno sotto
resterebbero congelate all'infinito. C'e' anche un tetto di durata
(`pinch_freeze_max_time`), perche' delle dita ferme a mezz'aria non devono
tenere il cursore in ostaggio.

### Unita' della rotellina

Scroll e zoom parlano in **scatti di rotellina**. Non e' un dettaglio: su
Windows `pyautogui.scroll(n)` passa `n` tale e quale a
`mouse_event(MOUSEEVENTF_WHEEL, ..., dwData=n)`, dove uno scatto vale
`WHEEL_DELTA = 120`. Lo zoom mandava `pyautogui.scroll(3)` con ctrl premuto,
cioe' il 2.5% di uno scatto: nessuna applicazione zooma per cosi' poco, ed era
tutta li' la ragione per cui lo zoom "non funzionava". Ora la rotellina passa
da `mouse_controller._wheel`, che moltiplica per `WHEEL_DELTA`.

### Taratura rapida

Il modo giusto di tarare non e' a occhio:

```bash
python calibrate.py
```

Apre una finestra che mostra i valori misurati dal vivo. Premi **SPAZIO una
volta sola**: la procedura ti guida attraverso quattro pose (indice puntato,
pollice+indice, pollice+medio, pugno) con un conto alla rovescia per ciascuna e
registra da sola, poi calcola le soglie sulla tua mano e le salva con `S`. Se
non muovi la mano o le pose risultano indistinguibili te lo dice invece di
produrre soglie inservibili.

Tre cose che la calibrazione ora fa e prima no, ognuna nata da un profilo
sbagliato realmente prodotto:

* **scarta i primi 0.8 s di ogni posa.** Registrava dal primo fotogramma dopo
  il conto alla rovescia, quando la mano e' ancora in viaggio verso la posa; con
  il 95o percentile quei fotogrammi finivano dritti nella soglia. Il profilo
  salvato aveva `pinch_close_ratio = 0.82`, cioe' il valore di una mano
  **aperta**: con quello caricato, un pugno chiuso emetteva `drag_start` e il
  tasto sinistro restava premuto invece di cliccare.
* **misura il pollice+medio con una posa sua.** Prima copiava le soglie
  dell'indice su quelle del medio, e le due geometrie non c'entrano niente
  l'una con l'altra. I campioni pollice-medio venivano peraltro gia' raccolti,
  e poi buttati.
* **rifiuta i valori implausibili** invece di scriverli su file, e all'avvio
  `settings_gui` ricontrolla il profilo e riporta ai valori di fabbrica le
  soglie che non stanno in piedi, dicendo quali e perche'.

Le soglie predefinite sono ragionevoli ma non sono misurate sulla tua mano.

| Sintomo | Rimedio |
|---|---|
| Il cursore si pianta | guarda la riga `cursore:` nell'overlay. Se dice BLOCCATO a mano ferma, alza *Sensibilita' blocco cursore* |
| Click destro a caso | il medio deve essere **disteso** perche' conti: alza *Soglia mano aperta/chiusa* del medio |
| Lo zoom non fa niente | alza *Scatti per passo di zoom*; verifica di avere gli **indici estesi su entrambe le mani** e il medio chiuso |
| Scroll troppo lento o troppo brusco | *Intensita' scroll* e' in scatti di rotellina per altezza di inquadratura |
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
| Modello, complessita' 0 vs 1 (webcam reale) | 14.4 ms contro 16.7 ms |
| Backend webcam MSMF contro DSHOW | 30.2 fps contro 17.0 fps |
| `cvtColor` con buffer riusato | 0.03 ms |
| Overlay a pannello contro overlay a frame intero | 0.02 ms contro 0.34 ms |
| `imshow` + `waitKey(1)` | **15.66 ms** per fotogramma |
| `imshow` + `pollKey()` | **0.37 ms** per fotogramma |

Tre risultati hanno guidato le scelte di progetto:

**`cv2.waitKey(1)` non aspetta 1 ms.** Su Windows entra nel ciclo di messaggi
Win32 e si allinea alla risoluzione del timer di sistema, che di default e'
15.6 ms. Misurato sopra: la finestra di debug costava **15.7 ms per
fotogramma**, cioe' piu' del modello (14 ms), e quei millisecondi erano latenza
pura fra il movimento della mano e quello del cursore. Era la causa principale
del "framelag". Con `cv2.pollKey()`, che non blocca, il costo dell'intero
`_render` (imshow + overlay + tastiera) misurato sul loop reale scende a
**0.99 ms mediani**.

**La risoluzione della webcam non influenza la velocita' del modello.**
MediaPipe ridimensiona comunque l'immagine a 192x192 al suo interno: 320x240
costa 37.9 ms e 640x480 ne costa 35.1. Abbassare la risoluzione peggiorava
quindi la precisione dei landmark senza far guadagnare nulla. Il default e'
640x480.

> Le misure del modello vanno prese con una avvertenza: costruire piu' grafi
> MediaPipe di fila nello stesso processo contamina i tempi, perche' i thread
> pool dei grafi gia' chiusi non spariscono subito e le configurazioni misurate
> per ultime pagano la contesa. Una passata sola su questo banco ha dato 35.4 ms
> per "2 mani, complessita' 0" contro 14.3 ms in un processo pulito — piu' della
> *stessa* configurazione a complessita' 1, il che rende l'errore evidente. Per
> questo `benchmark.py` ripete la griglia tre volte e tiene il minimo.

**Il default e' `model_complexity = 1`.** Costa 2.3 ms in piu' del modello
lite, ma il tetto reale del loop e' la webcam, che consegna un fotogramma ogni
33 ms: quei 2.3 ms non tolgono un solo fotogramma. In cambio i landmark del
pollice durante il pinch sono molto piu' stabili, ed e' il pollice a decidere
se un click parte. Su una macchina che non regge, il governor scende da solo a
0 — e' la prima cosa che toglie, perche' e' anche la piu' redditizia.

**Il governor riduce la qualita', non toglie funzioni.** Prima, scendendo di
livello, disattivava `enable_zoom`: lo zoom spariva senza spiegazione, e siccome
`max_num_hands` in `app` segue proprio `enable_zoom`, i due si rincorrevano
ricostruendo il grafo MediaPipe. L'ordine dei livelli e' stato anche rifatto
sulle misure: con `pollKey` la finestra di debug costa 1 ms e non e' piu' un
risparmio, mentre il modello vale 2.3 ms, quindi il modello viene prima.

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
python test_zoom.py        # zoom a due mani, senza webcam e senza mouse
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
