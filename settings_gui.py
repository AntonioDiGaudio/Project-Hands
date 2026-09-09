"""
Finestra delle impostazioni.

Interamente generata da `settings_schema`: aggiungere o togliere un parametro
si fa in un posto solo. La versione precedente aveva un metodo `update_*`
scritto a mano per ogni slider piu' una lista separata per salvare e una per
caricare, e le tre liste erano finite fuori sincrono fra loro.

Ogni modifica agisce direttamente sul modulo `config`, che il loop principale
rilegge a ogni fotogramma: le modifiche sono quindi immediate senza riavviare.
"""

import os
import tkinter as tk
from tkinter import messagebox, ttk

import config
import settings_schema as schema
from gui_theme import (
    GUI_FONT, GUI_BG_COLOR, GUI_FG_COLOR,
    GUI_BUTTON_BG, GUI_BUTTON_FG, GUI_HIGHLIGHT_COLOR,
    GUI_FONT_BOLD_TITLE, GUI_FONT_BOLD_SUBTITLE,
)
from shared_state import set_running

PROFILE_DIR = "Profiles"
PROFILE_PATH = os.path.join(PROFILE_DIR, "settings.txt")

# Versione del formato. Si alza solo quando cambia il SIGNIFICATO di un
# parametro esistente, non quando se ne aggiunge uno: un valore vecchio letto
# con l'unita' nuova e' peggio di un valore mancante, perche' nessuno se ne
# accorge.
#   1 -> 2  scroll_gain passa da "unita' grezze x100" a "scatti di rotellina"
PROFILE_VERSION = 2

# Valori di fabbrica, catturati all'import prima che il file utente li sovrascriva.
_FACTORY = {key: getattr(config, key) for key in schema.persisted_keys()
            if hasattr(config, key)}


# ---------------------------------------------------------------------------
# Persistenza
# ---------------------------------------------------------------------------
def save_settings(path=PROFILE_PATH):
    """Scrive su file tutti i parametri dello schema."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lines = ["profile_version = %d" % PROFILE_VERSION]
    for key in schema.persisted_keys():
        if not hasattr(config, key):
            continue
        value = getattr(config, key)
        if isinstance(value, bool):
            value = int(value)
        lines.append("%s = %s" % (key, value))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def load_settings(path=PROFILE_PATH):
    """
    Legge il file di configurazione, se esiste.

    Le chiavi sconosciute vengono ignorate senza errore, cosi' un profilo
    scritto da una versione precedente resta caricabile.
    """
    if not os.path.isfile(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = {}
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                raw[key.strip()] = value.strip()
    except OSError as exc:
        print("Impossibile leggere %s: %s" % (path, exc))
        return False

    version = 1
    try:
        version = int(float(raw.pop("profile_version", 1)))
    except ValueError:
        pass

    for key, text in raw.items():
        if key not in _FACTORY:
            continue
        current = _FACTORY[key]
        try:
            if isinstance(current, bool):
                setattr(config, key, bool(int(float(text))))
            elif isinstance(current, int):
                setattr(config, key, int(float(text)))
            elif isinstance(current, float):
                setattr(config, key, float(text))
            else:
                setattr(config, key, text)
        except ValueError:
            print("Valore non valido per %s: %r (ignorato)" % (key, text))

    _migrate(version)
    validate_thresholds()
    return True


def _migrate(version):
    """Adegua un profilo scritto da una versione precedente."""
    if version < 2:
        # `scroll_gain` era moltiplicato per 100 e finiva in unita' grezze di
        # `mouse_event`, dove uno scatto di rotellina vale 120: il valore
        # vecchio, riletto in scatti, darebbe uno scroll quasi immobile.
        if config.scroll_gain != _FACTORY["scroll_gain"]:
            print("Profilo: scroll_gain (%.1f) e' in unita' vecchie -> %.1f scatti."
                  % (config.scroll_gain, _FACTORY["scroll_gain"]))
            config.scroll_gain = _FACTORY["scroll_gain"]


# ---------------------------------------------------------------------------
# Convalida del profilo
# ---------------------------------------------------------------------------
# Limiti di plausibilita' fisica, non preferenze. Un pinch e' "dita che si
# toccano": il rapporto pollice-punta diviso la dimensione della mano vale
# allora circa 0.1-0.3, e comunque mai piu' di mezza mano. Un profilo che dice
# 0.82 non descrive un pinch, descrive una mano aperta.
#
# Serve perche' calibrate.py ha prodotto davvero un profilo cosi', e con quello
# caricato due test della macchina a stati falliscono: un PUGNO CHIUSO emette
# drag_start, cioe' il tasto sinistro resta premuto invece di cliccare. E'
# esattamente il sintomo "il click sinistro non funziona".
# Nota sulla soglia di ESTENSIONE (index_control_ratio): il limite e'
# volutamente larghissimo. La prima versione lo teneva fra 0.55 e 1.30,
# copiando i valori di riferimento dei commenti del progetto, mai verificati su
# una mano vera; la prima calibrazione reale ha misurato 0.31 e si e' vista
# rifiutare un valore corretto, restando quindi su un default che blocca ogni
# gesture. Quelle soglie non hanno una scala assoluta prevedibile: dipendono
# dalle proporzioni della mano. Qui si scartano solo i valori impossibili.
_LIMITS = {
    "pinch_close_ratio": (0.10, 0.60),
    "pinch_open_ratio": (0.20, 1.20),
    "right_pinch_close_ratio": (0.10, 0.60),
    "right_pinch_open_ratio": (0.20, 1.20),
    "pinch_freeze_ratio": (0.25, 1.80),
    "index_control_ratio": (0.08, 1.60),
    "middle_control_ratio": (0.08, 1.60),
}


def _revert(keys, reason):
    names = [k for k in keys if getattr(config, k) != _FACTORY.get(k)]
    if not names:
        return
    print("Profilo: %s" % reason)
    for key in names:
        print("  %s = %s -> ripristinato a %s"
              % (key, getattr(config, key), _FACTORY[key]))
        setattr(config, key, _FACTORY[key])
    print("  Rilancia `python calibrate.py` per rifare la calibrazione.")


def validate_thresholds():
    """
    Riporta ai valori di fabbrica le soglie del profilo che non stanno in piedi.

    Un profilo sbagliato non da' errore: da' un'applicazione che si comporta
    male in un modo che sembra un bug del riconoscitore. Meglio accorgersene
    all'avvio, dicendo cosa e perche'.
    """
    fuori = [k for k, (lo, hi) in _LIMITS.items()
             if hasattr(config, k) and not (lo <= getattr(config, k) <= hi)]
    if fuori:
        _revert(fuori, "valori fuori dall'intervallo fisicamente sensato.")

    # L'ordine delle soglie e' quello che rende l'isteresi un'isteresi: se si
    # inverte, il rilevatore sfarfalla invece di stabilizzare.
    for close, open_ in (("pinch_close_ratio", "pinch_open_ratio"),
                         ("right_pinch_close_ratio", "right_pinch_open_ratio")):
        if getattr(config, close) >= getattr(config, open_) - 0.05:
            _revert([close, open_],
                    "isteresi troppo stretta o invertita fra %s e %s." % (close, open_))
    if config.pinch_freeze_ratio <= config.pinch_open_ratio:
        _revert(["pinch_freeze_ratio"],
                "il congelamento deve stare sopra la soglia di apertura.")


def reset_to_factory():
    for key, value in _FACTORY.items():
        setattr(config, key, value)


# Carica subito il profilo utente, cosi' il loop parte gia' con i valori giusti.
load_settings()


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class SettingsGUI:
    """Pannello di controllo con tutti i parametri in tempo reale."""

    def __init__(self):
        self.root = None
        self.widgets = {}     # key -> (tk.Variable, tipo)
        self.value_labels = {}
        self.info_window = None

    # -- costruzione -------------------------------------------------------
    def create_gui(self):
        self.root = tk.Tk()
        self.root.title("AirMouse - Impostazioni")
        self.root.geometry("680x820")
        self.root.configure(bg=GUI_BG_COLOR)
        self.root.minsize(560, 480)

        container = tk.Frame(self.root, bg=GUI_BG_COLOR)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=GUI_BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=GUI_BG_COLOR)

        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_wheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")

        # bind_all sul solo canvas: la rotella non viene rubata ad altre finestre.
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self._build_header(body)
        self._build_toggles(body)
        for title, params in schema.SECTIONS:
            self._build_section(body, title, params)
        self._build_choices(body)
        self._build_buttons(body)

        self.refresh_widgets()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _build_header(self, parent):
        tk.Label(parent, text="AirMouse", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT_BOLD_TITLE).pack(pady=(14, 2))
        tk.Button(parent, text="Come si usa: guida alle gesture",
                  command=self.show_help, font=GUI_FONT, bg=GUI_BUTTON_BG,
                  fg=GUI_BUTTON_FG, activebackground=GUI_HIGHLIGHT_COLOR,
                  relief="flat").pack(padx=24, pady=(4, 12), fill="x")

    def _section_title(self, parent, text):
        tk.Label(parent, text=text, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT_BOLD_SUBTITLE).pack(pady=(18, 6))

    def _build_toggles(self, parent):
        self._section_title(parent, "FUNZIONI ATTIVE")
        grid = tk.Frame(parent, bg=GUI_BG_COLOR)
        grid.pack(fill="x", padx=24)
        for i, (key, label) in enumerate(schema.TOGGLES):
            var = tk.IntVar(value=int(bool(getattr(config, key, False))))
            self.widgets[key] = (var, "bool")
            tk.Checkbutton(
                grid, text=label, variable=var, font=GUI_FONT,
                bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, selectcolor=GUI_BUTTON_BG,
                activebackground=GUI_BG_COLOR, activeforeground=GUI_FG_COLOR,
                anchor="w", command=lambda k=key: self._apply_bool(k),
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=1)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

    def _build_section(self, parent, title, params):
        self._section_title(parent, title)
        for param in params:
            self._build_param(parent, param)

    def _build_param(self, parent, param):
        row = tk.Frame(parent, bg=GUI_BG_COLOR)
        row.pack(fill="x", padx=24, pady=(6, 0))

        head = tk.Frame(row, bg=GUI_BG_COLOR)
        head.pack(fill="x")
        tk.Label(head, text=param.label, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=GUI_FONT, anchor="w").pack(side="left")
        value_label = tk.Label(head, text="", bg=GUI_BG_COLOR, fg=GUI_HIGHLIGHT_COLOR,
                               font=GUI_FONT, anchor="e")
        value_label.pack(side="right")
        self.value_labels[param.key] = value_label

        # Tkinter Scale lavora bene con gli interi: gli slider float usano
        # internamente dei passi interi e convertono in uscita.
        if param.kind == "float":
            steps = max(1, int(round((param.hi - param.lo) / param.step)))
            var = tk.IntVar()
            scale = tk.Scale(
                row, from_=0, to=steps, orient="horizontal", showvalue=False,
                variable=var, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                highlightbackground=GUI_BG_COLOR, troughcolor=GUI_BUTTON_BG,
                command=lambda v, p=param: self._apply_float(p, int(float(v))),
            )
        else:
            var = tk.IntVar()
            scale = tk.Scale(
                row, from_=param.lo, to=param.hi, orient="horizontal",
                showvalue=False, variable=var, resolution=param.step,
                bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                highlightbackground=GUI_BG_COLOR, troughcolor=GUI_BUTTON_BG,
                command=lambda v, p=param: self._apply_int(p, int(float(v))),
            )
        scale.pack(fill="x")
        self.widgets[param.key] = (var, param.kind)

        tk.Label(row, text=param.help, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                 font=("Times", 9), wraplength=600, justify="left",
                 anchor="w").pack(fill="x", pady=(0, 2))

    def _build_choices(self, parent):
        self._section_title(parent, "CAMERA E MODELLO")
        for choice in schema.CHOICES:
            row = tk.Frame(parent, bg=GUI_BG_COLOR)
            row.pack(fill="x", padx=24, pady=(6, 0))
            tk.Label(row, text=choice.label, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                     font=GUI_FONT, anchor="w").pack(fill="x")

            var = tk.StringVar()
            self.widgets[choice.key] = (var, "choice")
            box = tk.Frame(row, bg=GUI_BG_COLOR)
            box.pack(fill="x")
            for option in choice.options:
                tk.Radiobutton(
                    box, text=option, variable=var, value=option, font=GUI_FONT,
                    bg=GUI_BG_COLOR, fg=GUI_FG_COLOR, selectcolor=GUI_BUTTON_BG,
                    activebackground=GUI_BG_COLOR, activeforeground=GUI_FG_COLOR,
                    command=lambda c=choice: self._apply_choice(c),
                ).pack(side="left", padx=(0, 10))

            tk.Label(row, text=choice.help, bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                     font=("Times", 9), wraplength=600, justify="left",
                     anchor="w").pack(fill="x", pady=(0, 2))

    def _build_buttons(self, parent):
        box = tk.Frame(parent, bg=GUI_BG_COLOR)
        box.pack(fill="x", padx=24, pady=18)
        for text, command in (
            ("Salva profilo", self._on_save),
            ("Ricarica profilo", self._on_reload),
            ("Valori di fabbrica", self._on_reset),
            ("Chiudi AirMouse", self._on_close),
        ):
            tk.Button(box, text=text, command=command, font=GUI_FONT,
                      bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG,
                      activebackground=GUI_HIGHLIGHT_COLOR, relief="flat"
                      ).pack(side="left", expand=True, fill="x", padx=3)

    # -- applicazione dei valori -------------------------------------------
    def _apply_float(self, param, steps):
        value = param.lo + steps * param.step
        value = min(param.hi, max(param.lo, value))
        setattr(config, param.key, float(value))
        self._update_label(param.key, value)
        self._enforce_hysteresis(param.key)

    def _apply_int(self, param, value):
        value = int(min(param.hi, max(param.lo, value)))
        setattr(config, param.key, value)
        self._update_label(param.key, value)

    def _apply_bool(self, key):
        var, _ = self.widgets[key]
        setattr(config, key, bool(var.get()))

    def _apply_choice(self, choice):
        var, _ = self.widgets[choice.key]
        value = var.get()
        if choice.key == "camera_resolution":
            width, _, height = value.partition("x")
            config.camera_width = int(width)
            config.camera_height = int(height)
        elif choice.key == "model_complexity":
            config.model_complexity = int(value)
        else:
            setattr(config, choice.key, value)

    def _enforce_hysteresis(self, key):
        """
        L'isteresi si rompe se la soglia di apertura scende sotto quella di
        chiusura: il gesto inizierebbe a sfarfallare. Qui si mantiene sempre un
        margine minimo, correggendo l'altra soglia se serve.
        """
        margin = 0.05
        pairs = [("pinch_close_ratio", "pinch_open_ratio"),
                 ("right_pinch_close_ratio", "right_pinch_open_ratio")]
        for close_key, open_key in pairs:
            if key not in (close_key, open_key):
                continue
            close = getattr(config, close_key)
            open_ = getattr(config, open_key)
            if open_ < close + margin:
                if key == close_key:
                    setattr(config, open_key, close + margin)
                    self._sync_widget(open_key)
                else:
                    setattr(config, close_key, max(0.05, open_ - margin))
                    self._sync_widget(close_key)

        if key in ("finger_extend_ratio", "finger_retract_ratio"):
            if config.finger_retract_ratio >= config.finger_extend_ratio:
                if key == "finger_extend_ratio":
                    config.finger_retract_ratio = config.finger_extend_ratio - 0.05
                    self._sync_widget("finger_retract_ratio")
                else:
                    config.finger_extend_ratio = config.finger_retract_ratio + 0.05
                    self._sync_widget("finger_extend_ratio")

    def _update_label(self, key, value):
        label = self.value_labels.get(key)
        if label is None:
            return
        label.config(text=("%.3f" % value).rstrip("0").rstrip(".")
                     if isinstance(value, float) else str(value))

    # -- sincronizzazione widget <- config ---------------------------------
    def _param_by_key(self, key):
        for param in schema.all_params():
            if param.key == key:
                return param
        return None

    def _sync_widget(self, key):
        entry = self.widgets.get(key)
        if entry is None:
            return
        var, kind = entry
        value = getattr(config, key, None)
        if value is None:
            return
        if kind == "float":
            param = self._param_by_key(key)
            if param is None:
                return
            steps = int(round((float(value) - param.lo) / param.step))
            var.set(max(0, steps))
            self._update_label(key, float(value))
        elif kind == "int":
            var.set(int(value))
            self._update_label(key, int(value))
        elif kind == "bool":
            var.set(int(bool(value)))

    def refresh_widgets(self):
        """Riporta ogni widget al valore attuale di config."""
        for key in list(self.widgets):
            if key in ("camera_resolution", "model_complexity",
                       "preferred_hand", "camera_backend"):
                continue
            self._sync_widget(key)

        var, _ = self.widgets["camera_resolution"]
        var.set("%dx%d" % (config.camera_width, config.camera_height))
        self.widgets["model_complexity"][0].set(str(config.model_complexity))
        self.widgets["preferred_hand"][0].set(config.preferred_hand)
        self.widgets["camera_backend"][0].set(config.camera_backend)

    # -- azioni ------------------------------------------------------------
    def _on_save(self):
        try:
            save_settings()
            messagebox.showinfo("AirMouse", "Profilo salvato in %s" % PROFILE_PATH)
        except OSError as exc:
            messagebox.showerror("AirMouse", "Errore nel salvataggio: %s" % exc)

    def _on_reload(self):
        if load_settings():
            self.refresh_widgets()
            messagebox.showinfo("AirMouse", "Profilo ricaricato.")
        else:
            messagebox.showwarning("AirMouse", "Nessun profilo salvato da caricare.")

    def _on_reset(self):
        reset_to_factory()
        self.refresh_widgets()

    def _on_close(self):
        set_running(False)
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    # -- guida -------------------------------------------------------------
    def show_help(self):
        if self.info_window is not None and self.info_window.winfo_exists():
            self.info_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.info_window = win
        win.title("AirMouse - Guida alle gesture")
        win.geometry("620x640")
        win.configure(bg=GUI_BG_COLOR)

        text = tk.Text(win, wrap="word", bg=GUI_BG_COLOR, fg=GUI_FG_COLOR,
                       font=GUI_FONT, relief="flat", padx=16, pady=16)
        text.pack(fill="both", expand=True)
        text.insert("1.0", HELP_TEXT)
        text.config(state="disabled")

        tk.Button(win, text="Chiudi", command=win.destroy, font=GUI_FONT,
                  bg=GUI_BUTTON_BG, fg=GUI_BUTTON_FG,
                  activebackground=GUI_HIGHLIGHT_COLOR, relief="flat"
                  ).pack(fill="x", padx=16, pady=10)


HELP_TEXT = """GESTURE

Posa di controllo - indice esteso
  Il cursore si muove solo con l'indice esteso. Chiudi la mano e il sistema
  diventa completamente inerte: e' il modo piu' semplice per non far succedere
  niente mentre parli o gesticoli.

Movimento - punta dell'indice
  Il cursore segue la punta dell'indice. Non serve arrivare ai bordi
  dell'inquadratura: l'ampiezza si regola con i cursori "Ampiezza".

Doppio click - due pinch pollice + indice ravvicinati
  Ripeti il pinch entro la finestra del doppio click. Fra i due il cursore
  resta BLOCCATO, altrimenti il secondo click cadrebbe altrove e Windows non
  li accoppierebbe. Il blocco cade da solo appena sposti la mano.

Click sinistro - pollice + indice, tocco breve
  Avvicina pollice e indice e riaprili subito. Appena il pinch inizia a
  chiudersi il cursore si BLOCCA, cosi' il click cade esattamente dove stavi
  puntando invece che qualche pixel piu' in la'.

Drag - pollice + indice, tenuto
  Stesso gesto, ma tienilo chiuso. Superata la "Soglia click/drag" il tasto
  resta premuto e il cursore torna a seguire la mano. Riapri le dita per
  rilasciare.

Click destro - pollice + indice + medio, tutti e tre insieme
  Avvicina indice E medio al pollice contemporaneamente. L'evento parte quando
  RIAPRI le dita, una volta sola: non si ripete anche se tieni il gesto.

  Era il solo pollice + medio, e su una mano vera non funziona: nella normale
  posa di puntamento il pollice sta gia' appoggiato sul medio ripiegato, a una
  distanza di 0.22 contro lo 0.12 del pinch fatto apposta. Sei centesimi di
  margine sono dentro il rumore del tracciamento, quindi qualunque soglia li'
  in mezzo o non scattava mai o scattava mentre puntavi. Con tre dita la posa
  piu' vicina sta a 0.65: margine 0.45.

Scroll - indice + medio estesi, anulare e mignolo chiusi
  Muovi la mano su e giu' per scorrere. La posa e' incompatibile con il pinch,
  quindi non puo' essere confusa con un click.

Zoom - indici estesi su entrambe le mani
  Avvicina o allontana le mani. Di default il sistema traccia una mano sola
  (e' circa 2,5 volte piu' veloce) e cerca la seconda ogni secondo.


PERCHE' NON PARTONO CLICK A CASO

Tutte le soglie sono frazioni della dimensione della tua mano, non pixel: la
stessa gesture funziona identica da vicino e da lontano dalla webcam. Ogni
gesto ha due soglie diverse per aprirsi e chiudersi (isteresi), deve reggere
per piu' fotogrammi consecutivi, e viene emesso sulla transizione e non sullo
stato. In piu' i click sono bloccati quando la mano si muove troppo veloce e
subito dopo che la mano rientra nell'inquadratura.


TARATURA RAPIDA

Ti partono click da solo
  Abbassa "Chiusura pinch", alza "Frame di conferma", alza "Confidenza minima
  mano".

I click non partono
  Alza "Chiusura pinch", abbassa "Frame di conferma".

Il drag si stacca da solo
  Alza "Frame di rilascio" e "Apertura pinch".

Il cursore trema da fermo
  Abbassa "Stabilita' da fermo", alza un po' la "Zona morta".

Il cursore resta indietro
  Alza "Reattivita' in movimento".


TASTI (finestra webcam)

  ESC  chiudi         D  scheletro on/off
  O    pannello       H  nascondi la finestra
"""


def create_settings_gui():
    SettingsGUI().create_gui()
