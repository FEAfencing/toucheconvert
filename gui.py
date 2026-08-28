#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gui.py — Interfaccia grafica di "Touché!Convert"

Interfaccia unica con due schede:
  - JSON (touche-export) -> XML (FIE)
  - XML (FIE) -> JSON (touche-export)

Usa solo librerie incluse in Python (Tkinter): nessuna dipendenza
esterna a runtime. Le uniche dipendenze servono per la BUILD
dell'eseguibile (PyInstaller) e sono elencate in requirements.txt.
"""

import os
import sys
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touche2fie  # noqa: E402
import fie2touche  # noqa: E402
import fisdotnet  # noqa: E402

APP_TITLE = "Touché!Convert"
APP_SUBTITLE = "touche-export ⇄ FIE XML ⇄ FisDotNet XML"

COLORE_SFONDO = "#0b1220"
COLORE_PANNELLO = "#111a2e"
COLORE_ACCENTO = "#29b6f6"
COLORE_TESTO = "#e8f1fb"
COLORE_TESTO_ATTENUATO = "#9fb3c8"


def risorsa(*parti):
    """Risolve il percorso di una risorsa sia in sviluppo sia una volta
    impacchettato con PyInstaller (--onefile usa una cartella temporanea
    indicata da sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parti)


class SchedaConversione(ttk.Frame):
    """Scheda generica: file di input -> cartella di output -> converti."""

    def __init__(self, parent, titolo, sottotitolo, estensioni_input, funzione_converti, style_prefix):
        super().__init__(parent, style=f"{style_prefix}.TFrame", padding=18)
        self.funzione_converti = funzione_converti
        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar()

        ttk.Label(self, text=titolo, style=f"{style_prefix}Titolo.TLabel").pack(
            anchor="w", pady=(0, 2)
        )
        ttk.Label(self, text=sottotitolo, style=f"{style_prefix}Sottotitolo.TLabel").pack(
            anchor="w", pady=(0, 14)
        )

        blocco_in = ttk.Frame(self, style=f"{style_prefix}.TFrame")
        blocco_in.pack(fill="x", pady=6)
        ttk.Label(blocco_in, text="File di origine:", style=f"{style_prefix}Etichetta.TLabel").pack(
            anchor="w"
        )
        riga_in = ttk.Frame(blocco_in, style=f"{style_prefix}.TFrame")
        riga_in.pack(fill="x", pady=(4, 0))
        ttk.Entry(riga_in, textvariable=self.input_path).pack(side="left", fill="x", expand=True)
        ttk.Button(
            riga_in, text="Sfoglia…", command=lambda: self._scegli_input(estensioni_input)
        ).pack(side="left", padx=(8, 0))

        blocco_out = ttk.Frame(self, style=f"{style_prefix}.TFrame")
        blocco_out.pack(fill="x", pady=6)
        ttk.Label(blocco_out, text="Cartella di destinazione:", style=f"{style_prefix}Etichetta.TLabel").pack(
            anchor="w"
        )
        riga_out = ttk.Frame(blocco_out, style=f"{style_prefix}.TFrame")
        riga_out.pack(fill="x", pady=(4, 0))
        ttk.Entry(riga_out, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(riga_out, text="Sfoglia…", command=self._scegli_output).pack(
            side="left", padx=(8, 0)
        )

        self.btn_converti = ttk.Button(
            self, text="Converti", style="Accento.TButton", command=self._avvia_conversione
        )
        self.btn_converti.pack(fill="x", pady=(16, 10), ipady=6)

        ttk.Label(self, text="Registro attività:", style=f"{style_prefix}Etichetta.TLabel").pack(
            anchor="w"
        )
        self.log = scrolledtext.ScrolledText(
            self, height=10, state="disabled", bg="#0d1526", fg=COLORE_TESTO,
            insertbackground=COLORE_TESTO, relief="flat", borderwidth=0,
        )
        self.log.pack(fill="both", expand=True, pady=(4, 0))

    def _scegli_input(self, estensioni):
        percorso = filedialog.askopenfilename(title="Seleziona il file di origine", filetypes=estensioni)
        if percorso:
            self.input_path.set(percorso)
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(percorso))

    def _scegli_output(self):
        cartella = filedialog.askdirectory(title="Seleziona la cartella di destinazione")
        if cartella:
            self.output_dir.set(cartella)

    def _scrivi_log(self, testo):
        self.log.configure(state="normal")
        self.log.insert("end", testo + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _avvia_conversione(self):
        input_path = self.input_path.get().strip()
        output_dir = self.output_dir.get().strip()
        if not input_path or not os.path.isfile(input_path):
            messagebox.showerror(APP_TITLE, "Seleziona un file di origine valido.")
            return
        if not output_dir:
            messagebox.showerror(APP_TITLE, "Seleziona una cartella di destinazione.")
            return
        self.btn_converti.configure(state="disabled", text="Conversione in corso…")
        self._scrivi_log(f"Avvio conversione di: {input_path}")
        threading.Thread(
            target=self._esegui, args=(input_path, output_dir), daemon=True
        ).start()

    def _esegui(self, input_path, output_dir):
        try:
            file_generati = self.funzione_converti(input_path, output_dir)
            for f in file_generati:
                self._scrivi_log(f"  → generato: {f}")
            self._scrivi_log("Conversione completata con successo.")
            self.after(
                0,
                lambda: messagebox.showinfo(
                    APP_TITLE,
                    f"Conversione completata.\n{len(file_generati)} file generato/i in:\n{output_dir}",
                ),
            )
        except Exception as e:  # noqa: BLE001
            dettaglio = traceback.format_exc()
            self._scrivi_log("ERRORE: " + str(e))
            self._scrivi_log(dettaglio)
            self.after(0, lambda: messagebox.showerror(APP_TITLE, f"Errore durante la conversione:\n{e}"))
        finally:
            self.after(0, lambda: self.btn_converti.configure(state="normal", text="Converti"))


class SchedaComponiEvento(ttk.Frame):
    """Scheda per comporre più export touche di singola gara in un unico
    evento con più gare (selezione di più file JSON)."""

    def __init__(self, parent, style_prefix):
        super().__init__(parent, style=f"{style_prefix}.TFrame", padding=18)
        self.output_dir = tk.StringVar()
        self.percorsi = []

        ttk.Label(
            self, text="Componi più gare in un unico evento", style=f"{style_prefix}Titolo.TLabel"
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            self,
            text="Seleziona più file JSON touche-export di singola gara: verranno "
                 "uniti in un unico evento con più gare (il circuito, se assente, "
                 "userà il titolo dell'evento del primo file).",
            style=f"{style_prefix}Sottotitolo.TLabel", wraplength=680, justify="left",
        ).pack(anchor="w", pady=(0, 14))

        blocco_lista = ttk.Frame(self, style=f"{style_prefix}.TFrame")
        blocco_lista.pack(fill="both", expand=False, pady=6)
        ttk.Label(blocco_lista, text="File selezionati:", style=f"{style_prefix}Etichetta.TLabel").pack(
            anchor="w"
        )
        riga_lista = ttk.Frame(blocco_lista, style=f"{style_prefix}.TFrame")
        riga_lista.pack(fill="x", pady=(4, 0))
        self.lista = tk.Listbox(
            riga_lista, height=6, bg="#0d1526", fg=COLORE_TESTO,
            selectbackground=COLORE_ACCENTO, relief="flat", borderwidth=0,
        )
        self.lista.pack(side="left", fill="both", expand=True)
        colonna_bottoni = ttk.Frame(riga_lista, style=f"{style_prefix}.TFrame")
        colonna_bottoni.pack(side="left", padx=(8, 0), fill="y")
        ttk.Button(colonna_bottoni, text="Aggiungi…", command=self._aggiungi_file).pack(fill="x", pady=(0, 4))
        ttk.Button(colonna_bottoni, text="Rimuovi selezionato", command=self._rimuovi_selezionato).pack(
            fill="x", pady=(0, 4)
        )
        ttk.Button(colonna_bottoni, text="Svuota lista", command=self._svuota_lista).pack(fill="x")

        blocco_out = ttk.Frame(self, style=f"{style_prefix}.TFrame")
        blocco_out.pack(fill="x", pady=6)
        ttk.Label(blocco_out, text="Cartella di destinazione:", style=f"{style_prefix}Etichetta.TLabel").pack(
            anchor="w"
        )
        riga_out = ttk.Frame(blocco_out, style=f"{style_prefix}.TFrame")
        riga_out.pack(fill="x", pady=(4, 0))
        ttk.Entry(riga_out, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(riga_out, text="Sfoglia…", command=self._scegli_output).pack(side="left", padx=(8, 0))

        self.btn_converti = ttk.Button(
            self, text="Componi evento", style="Accento.TButton", command=self._avvia_composizione
        )
        self.btn_converti.pack(fill="x", pady=(16, 10), ipady=6)

        ttk.Label(self, text="Registro attività:", style=f"{style_prefix}Etichetta.TLabel").pack(anchor="w")
        self.log = scrolledtext.ScrolledText(
            self, height=8, state="disabled", bg="#0d1526", fg=COLORE_TESTO,
            insertbackground=COLORE_TESTO, relief="flat", borderwidth=0,
        )
        self.log.pack(fill="both", expand=True, pady=(4, 0))

    def _aggiungi_file(self):
        percorsi = filedialog.askopenfilenames(
            title="Seleziona uno o più file JSON touche-export di singola gara",
            filetypes=[("File JSON", "*.json"), ("Tutti i file", "*.*")],
        )
        for p in percorsi:
            if p not in self.percorsi:
                self.percorsi.append(p)
                self.lista.insert("end", os.path.basename(p))
                if not self.output_dir.get():
                    self.output_dir.set(os.path.dirname(p))

    def _rimuovi_selezionato(self):
        sel = list(self.lista.curselection())
        for i in reversed(sel):
            self.lista.delete(i)
            del self.percorsi[i]

    def _svuota_lista(self):
        self.lista.delete(0, "end")
        self.percorsi = []

    def _scegli_output(self):
        cartella = filedialog.askdirectory(title="Seleziona la cartella di destinazione")
        if cartella:
            self.output_dir.set(cartella)

    def _scrivi_log(self, testo):
        self.log.configure(state="normal")
        self.log.insert("end", testo + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _avvia_composizione(self):
        if len(self.percorsi) < 2:
            messagebox.showerror(APP_TITLE, "Seleziona almeno due file JSON da comporre.")
            return
        output_dir = self.output_dir.get().strip()
        if not output_dir:
            messagebox.showerror(APP_TITLE, "Seleziona una cartella di destinazione.")
            return
        self.btn_converti.configure(state="disabled", text="Composizione in corso…")
        self._scrivi_log(f"Composizione di {len(self.percorsi)} file…")
        threading.Thread(target=self._esegui, args=(list(self.percorsi), output_dir), daemon=True).start()

    def _esegui(self, percorsi, output_dir):
        try:
            file_generati = fisdotnet.converti_componi_evento(percorsi, output_dir)
            for f in file_generati:
                self._scrivi_log(f"  → generato: {f}")
            self._scrivi_log("Composizione completata con successo.")
            self.after(
                0,
                lambda: messagebox.showinfo(
                    APP_TITLE, f"Evento composto correttamente in:\n{output_dir}"
                ),
            )
        except Exception as e:  # noqa: BLE001
            dettaglio = traceback.format_exc()
            self._scrivi_log("ERRORE: " + str(e))
            self._scrivi_log(dettaglio)
            self.after(0, lambda: messagebox.showerror(APP_TITLE, f"Errore durante la composizione:\n{e}"))
        finally:
            self.after(0, lambda: self.btn_converti.configure(state="normal", text="Componi evento"))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x680")
        self.minsize(760, 560)
        self.configure(bg=COLORE_SFONDO)

        self._imposta_icona()
        self._imposta_stile()
        self._costruisci_intestazione()
        self._costruisci_corpo()

    # ------------------------------------------------------------------
    def _imposta_icona(self):
        try:
            if sys.platform.startswith("win"):
                self.iconbitmap(risorsa("assets", "icon.ico"))
            else:
                icona = tk.PhotoImage(file=risorsa("assets", "icon_256.png"))
                self.iconphoto(True, icona)
                self._icona_ref = icona  # evita garbage collection
        except Exception:
            pass  # l'icona è puramente estetica: se manca, l'app funziona comunque

    def _imposta_stile(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        for prefix in ("TabA", "TabB", "TabC", "TabD", "TabE", "TabF"):
            style.configure(f"{prefix}.TFrame", background=COLORE_PANNELLO)
            style.configure(
                f"{prefix}Titolo.TLabel",
                background=COLORE_PANNELLO,
                foreground=COLORE_TESTO,
                font=("Helvetica", 15, "bold"),
            )
            style.configure(
                f"{prefix}Sottotitolo.TLabel",
                background=COLORE_PANNELLO,
                foreground=COLORE_TESTO_ATTENUATO,
                font=("Helvetica", 10),
            )
            style.configure(
                f"{prefix}Etichetta.TLabel",
                background=COLORE_PANNELLO,
                foreground=COLORE_TESTO,
                font=("Helvetica", 10, "bold"),
            )

        style.configure("TNotebook", background=COLORE_SFONDO, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=COLORE_SFONDO,
            foreground=COLORE_TESTO_ATTENUATO,
            padding=(16, 10),
            font=("Helvetica", 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORE_PANNELLO)],
            foreground=[("selected", COLORE_TESTO)],
        )

        style.configure("TEntry", fieldbackground="#0d1526", foreground=COLORE_TESTO, insertcolor=COLORE_TESTO)
        style.configure("TButton", padding=6)
        style.configure(
            "Accento.TButton",
            background=COLORE_ACCENTO,
            foreground="#04121c",
            font=("Helvetica", 11, "bold"),
        )
        style.map("Accento.TButton", background=[("active", "#5cd0ff")])

    # ------------------------------------------------------------------
    def _costruisci_intestazione(self):
        """Banner superiore con il logo FIE sfumato come filigrana e il
        titolo dell'app in primo piano."""
        altezza = 120
        canvas = tk.Canvas(
            self, height=altezza, bg=COLORE_PANNELLO, highlightthickness=0, bd=0
        )
        canvas.pack(fill="x", side="top")

        self._logo_watermark = None
        try:
            self._logo_watermark = tk.PhotoImage(file=risorsa("assets", "fie_watermark.png"))
        except Exception:
            pass

        def disegna(event=None):
            canvas.delete("all")
            larghezza = canvas.winfo_width() or 760
            canvas.create_rectangle(0, 0, larghezza, altezza, fill=COLORE_PANNELLO, outline="")
            if self._logo_watermark is not None:
                canvas.create_image(
                    larghezza - 20, altezza // 2, anchor="e", image=self._logo_watermark
                )
            canvas.create_text(
                24, altezza // 2 - 12, anchor="w", text=APP_TITLE,
                fill=COLORE_TESTO, font=("Helvetica", 22, "bold"),
            )
            canvas.create_text(
                24, altezza // 2 + 16, anchor="w", text=APP_SUBTITLE,
                fill=COLORE_ACCENTO, font=("Helvetica", 11),
            )

        canvas.bind("<Configure>", disegna)
        self._disegna_intestazione = disegna

    def _costruisci_corpo(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=14, pady=14)

        scheda_json_xml = SchedaConversione(
            notebook,
            titolo="JSON touche-export  →  XML FIE",
            sottotitolo="Genera il file di pubblicazione risultati in formato FIE a partire "
                        "dall'esportazione gestionale. Se il JSON è un evento con più gare, "
                        "viene generato un file FIE per ciascuna gara.",
            estensioni_input=[("File JSON", "*.json"), ("Tutti i file", "*.*")],
            funzione_converti=touche2fie.converti,
            style_prefix="TabA",
        )
        scheda_xml_json = SchedaConversione(
            notebook,
            titolo="XML FIE  →  JSON touche-export",
            sottotitolo="Ricostruisce un file touche-export a partire da un XML di "
                        "pubblicazione risultati FIE (conversione best-effort, vedi README).",
            estensioni_input=[("File XML", "*.xml"), ("Tutti i file", "*.*")],
            funzione_converti=fie2touche.converti,
            style_prefix="TabB",
        )
        scheda_fisdotnet_touche = SchedaConversione(
            notebook,
            titolo="XML FisDotNet  →  JSON touche-export",
            sottotitolo="Converte un intero evento FisDotNet (anche con più gare/armi/generi) "
                        "in un evento touche-export. Il torneo FisDotNet diventa il circuito; "
                        "se assente si usa il titolo dell'evento. Gli incontri a squadre non "
                        "vengono mai usati per ricostruire gli assalti individuali.",
            estensioni_input=[("File XML FisDotNet", "*.xml *.XML"), ("Tutti i file", "*.*")],
            funzione_converti=fisdotnet.converti_fisdotnet_a_touche,
            style_prefix="TabC",
        )
        scheda_touche_fisdotnet = SchedaConversione(
            notebook,
            titolo="JSON touche-export  →  XML FisDotNet",
            sottotitolo="Converte un evento touche-export (anche con più gare) in un file "
                        "XML in formato FisDotNet.",
            estensioni_input=[("File JSON", "*.json"), ("Tutti i file", "*.*")],
            funzione_converti=fisdotnet.converti_touche_a_fisdotnet,
            style_prefix="TabD",
        )
        scheda_fisdotnet_fie = SchedaConversione(
            notebook,
            titolo="XML FisDotNet  →  XML FIE (tutte le gare)",
            sottotitolo="Scorciatoia: converte direttamente un evento FisDotNet in tanti "
                        "file FIE quante sono le gare contenute nell'evento.",
            estensioni_input=[("File XML FisDotNet", "*.xml *.XML"), ("Tutti i file", "*.*")],
            funzione_converti=fisdotnet.converti_fisdotnet_a_fie,
            style_prefix="TabE",
        )
        scheda_componi = SchedaComponiEvento(notebook, style_prefix="TabF")

        notebook.add(scheda_json_xml, text="  JSON → FIE  ")
        notebook.add(scheda_xml_json, text="  FIE → JSON  ")
        notebook.add(scheda_fisdotnet_touche, text="  FisDotNet → JSON  ")
        notebook.add(scheda_touche_fisdotnet, text="  JSON → FisDotNet  ")
        notebook.add(scheda_fisdotnet_fie, text="  FisDotNet → FIE  ")
        notebook.add(scheda_componi, text="  Componi evento  ")


if __name__ == "__main__":
    app = App()
    app.mainloop()
