# AirMouse

AirMouse è un'applicazione che permette di controllare il cursore del mouse tramite i gesti delle mani rilevati da una webcam. Il progetto sfrutta MediaPipe e OpenCV per il tracciamento e include diversi moduli per riconoscere i gesti e inviare i comandi al sistema.

## Requisiti
- Python 3.10 o superiore
- Tutti i pacchetti indicati in `requirements.txt`

## Installazione
1. Clonare il repository e posizionarsi nella cartella del progetto.
2. Installare le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```

## Utilizzo
Eseguire il file `main.py` per avviare l'applicazione:
```bash
python main.py
```
Alla prima esecuzione viene chiesta la selezione della webcam e vengono mostrate le impostazioni principali in una finestra dedicata.

Durante l'esecuzione è possibile modificare alcune impostazioni (come risoluzione della camera e complessità del modello) tramite la finestra delle impostazioni. Il programma rileva le variazioni e aggiorna automaticamente la webcam e il tracker senza bisogno di riavviare l'applicazione.

## Configurazione
I parametri principali possono essere modificati nel file `config.py` oppure tramite il file `Profiles/settings.txt` generato dopo il primo avvio. Questi valori controllano sensibilità del cursore, overscan, soglie per click e zoom e altre preferenze.
In particolare il parametro `drag_release_frames` determina dopo quanti fotogrammi consecutivi con le dita separate viene rilasciata la modalità di trascinamento, rendendo la gesture più stabile.

## Stato del progetto
Il codice è in sviluppo e può essere utilizzato come base per ulteriori miglioramenti o integrazioni. Ogni contributo è benvenuto.

