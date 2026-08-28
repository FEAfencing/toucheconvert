# Touché!Convert

Applicazione con interfaccia grafica per convertire i risultati di gara
di scherma fra tre formati:

- **touche-export** (JSON) — l'esportazione gestionale completa
- **FIE XML** (`CompetitionIndividuelle`) — il formato di pubblicazione
  risultati internazionale
- **FisDotNet XML** (`dsLoadSave`, es. file "ExpAllGara_*.XML") — il
  formato del software federale italiano

## Le sei schede dell'applicazione

1. **JSON → FIE** — da un evento/gara touche-export a uno o più file
   FIE XML (uno per ciascuna gara contenuta, se l'evento ne ha più di
   una: stessa arma/genere/categoria diversi = file diversi).
2. **FIE → JSON** — da un file FIE XML a un touche-export di singola
   gara (conversione "best effort": l'XML FIE non contiene tutti i
   dati gestionali originali, vedi i limiti in cima a `fie2touche.py`).
3. **FisDotNet → JSON** — da un intero evento FisDotNet (anche con più
   armi/generi/categorie nello stesso file) a un touche-export con più
   gare. **Il torneo FisDotNet diventa il "circuito" del touche-export;
   se il torneo è assente, si usa il titolo dell'evento** (regola
   richiesta esplicitamente).
4. **JSON → FisDotNet** — conversione inversa, verso il formato
   federale.
5. **FisDotNet → FIE (tutte le gare)** — scorciatoia che incatena le
   conversioni 3 e 1: da un evento FisDotNet produce direttamente un
   file FIE per ciascuna gara contenuta.
6. **Componi evento** — prende più file touche-export di **singola
   gara** (uno per arma/genere/categoria) e li unisce in un unico
   evento con più gare, pronto per essere esportato in FIE o in
   FisDotNet.

## Un punto importante sul formato FisDotNet

Nel formato FisDotNet gli **"Incontri"** sono scontri **a squadre**
(un incontro = il punteggio complessivo fra due squadre), mentre gli
**"Assalti"** sono i singoli scontri **individuali** (anche quando
avvengono all'interno di un incontro a squadre). Il convertitore non
usa **mai** la tabella "Incontri" per ricostruire gli assalti di una
gara individuale — sarebbe un errore concettuale, dato che i due dati
vivono a livelli diversi. Le gare a squadre vengono riconosciute come
tali ma non ricostruite in dettaglio (formazioni, sostituzioni): è un
limite dichiarato, non un'approssimazione silenziosa.

Tutte le convenzioni dedotte dal formato FisDotNet (mappatura arma/
genere, codici categoria d'età, ecc. — non essendo disponibile una
documentazione ufficiale consultabile) sono descritte in dettaglio
nella testata di `fisdotnet.py`, insieme all'elenco completo dei
limiti noti della conversione.

## Contenuto del pacchetto

```
touche2fie.py                -> logica di conversione JSON touche -> XML FIE
fie2touche.py                -> logica di conversione XML FIE -> JSON touche
fisdotnet.py                 -> logica di conversione FisDotNet <-> touche
                                 (e scorciatoia FisDotNet -> FIE, e la
                                 composizione di più gare in un evento)
gui.py                       -> interfaccia grafica "Touché!Convert" (punto di ingresso)
requirements.txt             -> dipendenze per la build (solo PyInstaller)
assets/
  icon.ico / icon.icns / icon_256.png / icon_512.png -> icone app
  fie_watermark.png          -> logo FIE con sfondo rimosso, usato come
                                 filigrana nell'intestazione
  dsLoadSave_schema_template.xml -> intestazione/schema XML fisso del
                                 formato FisDotNet, riusato tale e quale
                                 per generare file compatibili
.github/workflows/build.yml  -> build automatica per Windows/macOS/Linux
```

## Come ottenere gli eseguibili (nessuna installazione richiesta)

### 1. Crea un repository su GitHub e carica questi file
Dal browser, senza riga di comando: apri il repository -> "Add file"
-> "Upload files" -> trascina dentro **tutti** i file/cartelle di
questo pacchetto, **mantenendo la struttura** (`.github/workflows/` e
`assets/` incluse) -> "Commit changes".

### 2. Attendi la compilazione automatica
Scheda **Actions**: dopo 2-5 minuti trovi tre **Artifacts**:
- `Touche-Convert-Windows` → `Touché!Convert.exe`
- `Touche-Convert-macOS` → `Touche-Convert-macOS.zip` (contiene
  `Touché!Convert.app`)
- `Touche-Convert-Linux` → eseguibile `ToucheConvert`

### 3. (Opzionale) Versione permanente
Scheda **Releases** -> "Draft a new release" -> Tag `v1.0.0` ->
Publish: il workflow allega automaticamente i tre eseguibili.

## Come usare l'app

**Windows**: doppio clic su `Touché!Convert.exe` (SmartScreen può
avvisare per app non firmate: "Ulteriori informazioni" -> "Esegui
comunque").

**macOS**: estrai lo zip, sposta `Touché!Convert.app` dove preferisci,
apri con **tasto destro -> Apri** la prima volta (Gatekeeper).

**Linux**:
```
chmod +x ToucheConvert
./ToucheConvert
```

Scegli la scheda che ti serve, seleziona il file (o i file, per
"Componi evento") e la cartella di destinazione, premi il pulsante di
conversione.

## Uso da riga di comando (facoltativo)
Ogni modulo funziona anche da solo, senza interfaccia grafica:
```
python3 touche2fie.py evento.json cartella_output
python3 fie2touche.py risultati_fie.xml cartella_output
python3 fisdotnet.py in ExpAllGara.XML cartella_output        # FisDotNet -> touche
python3 fisdotnet.py out evento.json cartella_output          # touche -> FisDotNet
python3 fisdotnet.py fie ExpAllGara.XML cartella_output       # FisDotNet -> FIE (tutte le gare)
python3 fisdotnet.py componi cartella_output gara1.json gara2.json ...
```

## Aggiornare il programma in futuro
Ogni commit su GitHub ricompila automaticamente i tre eseguibili:
non serve ripetere alcuna configurazione.

## Sviluppo/compilazione in locale (facoltativo)
PyInstaller compila solo per il sistema operativo su cui viene
eseguito (nessuna compilazione incrociata):
```
pip install -r requirements.txt

# Windows
pyinstaller --noconfirm --onefile --windowed --name "Touché!Convert" --icon assets/icon.ico --add-data "assets;assets" gui.py

# macOS
pyinstaller --noconfirm --windowed --name "Touché!Convert" --icon assets/icon.icns --add-data "assets:assets" gui.py

# Linux
pyinstaller --noconfirm --onefile --windowed --name "ToucheConvert" --add-data "assets:assets" gui.py
```
