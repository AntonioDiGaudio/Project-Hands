"""
Schema dichiarativo dei parametri configurabili.

Un solo posto descrive nome, tipo, intervallo e spiegazione di ogni parametro.
La GUI e il salvataggio su file si generano da qui, quindi aggiungere un
parametro non richiede di toccare tre file e di tenerli allineati a mano (che e'
il motivo per cui la GUI precedente era scivolata fuori sincrono con config).
"""

from collections import namedtuple

Param = namedtuple("Param", "key label kind lo hi step help")

# kind: "float" | "int" | "bool" | "choice"
Choice = namedtuple("Choice", "key label kind options help")

SECTIONS = [
    ("CURSORE", [
        Param("overscan_x", "Ampiezza orizzontale", "float", 1.0, 3.0, 0.05,
              "Quanto poco devi muovere la mano per attraversare lo schermo in "
              "orizzontale. Piu' alto = meno movimento richiesto, ma anche meno "
              "precisione."),
        Param("overscan_y", "Ampiezza verticale", "float", 1.0, 3.0, 0.05,
              "Come sopra, in verticale."),
        Param("cursor_speed_multiplier", "Velocita' cursore", "float", 0.5, 2.0, 0.05,
              "Moltiplicatore finale della posizione. Lascialo a 1.00 salvo casi "
              "particolari con piu' monitor."),
        Param("one_euro_min_cutoff", "Stabilita' da fermo", "float", 0.2, 5.0, 0.1,
              "Piu' BASSO = cursore piu' fermo quando la mano e' immobile, ma "
              "leggermente piu' molle. Se il cursore trema da fermo, abbassa."),
        Param("one_euro_beta", "Reattivita' in movimento", "float", 0.0, 0.5, 0.005,
              "Piu' ALTO = il cursore insegue meglio i movimenti rapidi. Se ti "
              "sembra che il cursore resti indietro, alza."),
        Param("deadzone_threshold", "Zona morta (px)", "float", 0.0, 15.0, 0.5,
              "Spostamenti sullo schermo piu' piccoli di questo valore vengono "
              "ignorati. Utile contro il micro-tremolio."),
    ]),
    ("GESTURE - CLICK E DRAG", [
        Param("pinch_close_ratio", "Chiusura pinch (click sx)", "float", 0.20, 0.80, 0.01,
              "Quanto devi avvicinare pollice e indice perche' valga come pinch. "
              "E' una FRAZIONE della dimensione della tua mano, quindi funziona "
              "uguale da vicino e da lontano. Se ti clicca da solo, ABBASSA."),
        Param("pinch_open_ratio", "Apertura pinch (click sx)", "float", 0.30, 1.20, 0.01,
              "Quanto devi riaprire le dita per chiudere il gesto. Deve restare "
              "piu' alto della chiusura: la distanza fra i due valori e' quello "
              "che impedisce lo sfarfallio."),
        Param("right_pinch_close_ratio", "Chiusura pinch a tre dita", "float", 0.20, 0.80, 0.01,
              "Come sopra ma per pollice+medio, che fa il click destro."),
        Param("right_pinch_open_ratio", "Apertura pinch a tre dita", "float", 0.30, 1.20, 0.01,
              "Apertura del pinch del click destro."),
        Param("pinch_approach_drop", "Sensibilita' blocco cursore", "float", 0.05, 0.60, 0.01,
              "Di quanto devono essersi avvicinate le dita perche' il cursore si "
              "blocchi. Il blocco richiede un avvicinamento IN CORSO: senza "
              "questa condizione una posa ferma sotto soglia (indice puntato, "
              "medio ripiegato col pollice sopra) lo bloccherebbe per sempre."),
        Param("pinch_freeze_max_time", "Durata max blocco (s)", "float", 0.2, 2.0, 0.05,
              "Oltre questo tempo il cursore torna libero anche se le dita "
              "restano vicine. Rete di sicurezza contro il cursore piantato."),
        Param("pinch_freeze_ratio", "Blocco cursore nel click", "float", 0.40, 1.60, 0.05,
              "Sotto questa distanza fra pollice e indice il cursore si blocca, "
              "cosi' il click cade dove stavi puntando invece che qualche pixel "
              "piu' in la'. Deve restare PIU' ALTA della chiusura del pinch: e' "
              "il margine in cui il cursore si ferma mentre le dita si stanno "
              "ancora avvicinando. Se il cursore ti scivola mentre clicchi, alza."),
        Param("index_control_ratio", "Soglia mano aperta/chiusa", "float", 0.10, 1.60, 0.01,
              "Quanto deve essere disteso l'indice perche' la mano conti come "
              "attiva, misurato dalla nocca. Sotto questo valore la mano e' "
              "considerata chiusa e nulla puo' succedere. ATTENZIONE: pinzare "
              "piega l'indice, quindi una soglia troppo alta annulla i click "
              "mentre li fai. Usa `python calibrate.py` per misurarla sulla tua "
              "mano invece di indovinarla."),
        Param("pinch_confirm_frames", "Frame di conferma", "int", 1, 6, 1,
              "Quanti fotogrammi consecutivi deve durare un pinch prima di "
              "contare. Alzalo se ti partono click fantasma, abbassalo se i "
              "click ti sembrano lenti."),
        Param("pinch_release_frames", "Frame di rilascio", "int", 1, 8, 1,
              "Quanti fotogrammi consecutivi con le dita aperte servono per "
              "chiudere il gesto. Alzalo se il drag si interrompe da solo."),
        Param("drag_hold_time", "Soglia click/drag (s)", "float", 0.15, 1.20, 0.05,
              "Pinch piu' breve di cosi' = click. Piu' lungo = inizia il drag."),
        Param("click_max_travel", "Movimento max nel click (px)", "float", 10.0, 200.0, 5.0,
              "Se durante il pinch il cursore vaga piu' di cosi', non viene "
              "considerato un click. Protegge dai click involontari mentre la "
              "mano si sposta."),
        Param("click_cooldown", "Pausa fra click (s)", "float", 0.05, 1.0, 0.05,
              "Tempo minimo fra due click sinistri."),
        Param("right_click_cooldown", "Pausa fra click destri (s)", "float", 0.1, 2.0, 0.05,
              "Tempo minimo fra due click destri."),
    ]),
    ("ANTI FALSI POSITIVI", [
        Param("min_handedness_score", "Confidenza minima mano", "float", 0.5, 0.99, 0.01,
              "Le mani riconosciute con meno certezza di cosi' vengono ignorate. "
              "Alzalo se oggetti o volti vengono scambiati per mani."),
        Param("hand_reacquire_grace", "Silenzio dopo riaggancio (s)", "float", 0.0, 1.0, 0.05,
              "Quando la mano ricompare, per questo tempo nessuna gesture puo' "
              "partire. Evita il click all'ingresso della mano nell'inquadratura."),
        Param("max_gesture_speed", "Velocita' max per click (px/s)", "float", 500.0, 6000.0, 100.0,
              "Se la mano si muove piu' veloce di cosi', i click vengono "
              "ignorati: un click a mano lanciata e' quasi sempre un artefatto."),
        Param("finger_extend_ratio", "Soglia dito esteso", "float", 1.0, 1.5, 0.01,
              "Quanto deve essere allungato un dito per contare come esteso. "
              "Alzalo se il sistema crede che le dita siano alzate quando non lo "
              "sono."),
        Param("finger_retract_ratio", "Soglia dito chiuso", "float", 0.8, 1.4, 0.01,
              "Deve restare sotto la soglia di estensione: la differenza fra le "
              "due e' l'isteresi che evita lo sfarfallio."),
        Param("teleport_reset_ratio", "Soglia salto mano", "float", 0.1, 1.0, 0.05,
              "Se la mano si sposta di piu' di questa frazione di inquadratura in "
              "un solo fotogramma, viene trattata come un riaggancio e le "
              "gesture sono inibite."),
    ]),
    ("SCROLL E ZOOM", [
        Param("scroll_deadzone", "Zona morta scroll", "float", 0.002, 0.08, 0.002,
              "Quanto devi muovere la mano prima che parta lo scroll."),
        Param("scroll_gain", "Intensita' scroll", "float", 2.0, 80.0, 1.0,
              "Scatti di rotellina per un'altezza intera di inquadratura. E' la "
              "stessa unita' della rotellina fisica: 3 scatti = 3 scatti."),
        Param("scroll_max_notches", "Scatti max per evento", "int", 1, 10, 1,
              "Tetto di scatti emessi in una volta sola. Basso = scroll piu' "
              "controllato, alto = piu' veloce ma piu' facile da sbandare."),
        Param("zoom_trigger_ratio", "Soglia zoom", "float", 0.05, 0.60, 0.01,
              "Variazione relativa della distanza fra le mani necessaria per uno "
              "scatto di zoom."),
        Param("zoom_cooldown_time", "Pausa fra zoom (s)", "float", 0.1, 2.0, 0.05,
              "Tempo minimo fra due scatti di zoom."),
        Param("zoom_smooth_factor", "Smoothing zoom", "int", 1, 15, 1,
              "Su quanti fotogrammi viene mediata la distanza fra le mani."),
        Param("zoom_notches", "Scatti per passo di zoom", "int", 1, 5, 1,
              "Quanti scatti di ctrl+rotellina manda un singolo passo di zoom."),
        Param("slide_cooldown_time", "Pausa fra slide (s)", "float", 0.05, 2.0, 0.05,
              "Tempo minimo fra due pressioni delle frecce con la gesture slide."),
    ]),
    ("PRESTAZIONI", [
        Param("target_fps", "Tetto FPS", "int", 15, 120, 5,
              "Limite superiore del ciclo. Abbassalo per consumare meno CPU e "
              "batteria; il collo di bottiglia reale resta il modello."),
        Param("perf_min_detect_fps", "FPS minimi accettabili", "int", 5, 40, 1,
              "Sotto questa soglia la qualita' viene ridotta automaticamente."),
        Param("idle_detect_fps", "Ritmo a riposo (fps)", "int", 2, 30, 1,
              "Quanto spesso si cerca una mano quando non ce n'e' nessuna. "
              "Senza mani il modello costa comunque circa 22 ms per "
              "fotogramma, ed e' la condizione piu' frequente: abbassare "
              "questo valore e' il modo piu' efficace di ridurre il consumo. "
              "Piu' basso = meno CPU, ma la mano viene agganciata con un po' "
              "piu' di ritardo."),
        Param("idle_after_seconds", "Attesa prima del riposo (s)", "float", 0.2, 5.0, 0.1,
              "Dopo quanti secondi senza mani si entra in modalita' risparmio."),
        Param("hand_lost_frames", "Buchi di rilevamento tollerati", "int", 0, 10, 1,
              "Quanti fotogrammi senza mano si ignorano prima di considerarla "
              "persa. A 0 ogni singolo buco del modello azzera lo stato e "
              "spezza i trascinamenti."),
        Param("cursor_engage_frames", "Fotogrammi prima di agganciare", "int", 1, 8, 1,
              "Quanti fotogrammi consecutivi con la mano visibile servono prima "
              "che il cursore inizi a muoversi. Evita che una rilevazione "
              "isolata teletrasporti il cursore."),
    ]),
]

TOGGLES = [
    ("drag_mode_enabled", "Abilita drag (pinch tenuto)"),
    ("enable_right_click", "Abilita click destro (pollice+medio)"),
    ("enable_scroll", "Abilita scroll a due dita"),
    ("enable_zoom", "Abilita zoom a due mani"),
    ("enable_slide", "Abilita slide con pugno (frecce)"),
    ("require_pointing_pose", "Richiedi indice esteso per agire"),
    ("auto_performance", "Riduci qualita' automaticamente se rallenta"),
    ("idle_throttle", "Risparmia CPU quando non ci sono mani"),
    ("show_debug_window", "Mostra finestra webcam"),
    ("draw_landmarks", "Disegna scheletro della mano"),
    ("overlay_enabled", "Mostra pannello diagnostico"),
]

CHOICES = [
    Choice("camera_resolution", "Risoluzione webcam", "choice",
           ["424x240", "640x480", "800x600", "1280x720"],
           "MediaPipe ridimensiona comunque l'immagine a 192x192 al suo interno, "
           "quindi alzare la risoluzione NON rallenta il riconoscimento in modo "
           "significativo, ma migliora la precisione dei punti. 640x480 e' il "
           "compromesso consigliato."),
    Choice("model_complexity", "Complessita' modello", "choice", ["0", "1"],
           "0 = modello leggero (misurato circa 35 ms per fotogramma). "
           "1 = modello completo (circa 56 ms), piu' preciso ma quasi il doppio "
           "piu' lento. Su CPU deboli tieni 0."),
    Choice("preferred_hand", "Mano che muove il cursore", "choice", ["Right", "Left"],
           "Quale mano controlla il cursore. L'altra resta libera per zoom e "
           "slide."),
    Choice("camera_backend", "Backend webcam", "choice",
           ["auto", "msmf", "dshow", "v4l2", "any"],
           "Come OpenCV parla con la webcam. 'auto' prova in ordine il migliore "
           "per il tuo sistema. Su Windows MSMF e' di solito molto piu' veloce "
           "di DSHOW."),
]


def all_params():
    for _, params in SECTIONS:
        for p in params:
            yield p


def persisted_keys():
    """Tutte le chiavi salvate su disco."""
    keys = [p.key for p in all_params()]
    keys += [k for k, _ in TOGGLES]
    keys += ["camera_width", "camera_height", "model_complexity",
             "preferred_hand", "camera_backend",
             "min_detection_confidence", "min_tracking_confidence"]
    return keys
