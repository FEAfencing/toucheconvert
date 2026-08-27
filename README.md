# Touché!Convert

Applicazione con interfaccia grafica per convertire i file nei **due
sensi**:

- **JSON (touche-export) → XML (FIE)** — genera il file di
  pubblicazione risultati ufficiale a partire dall'esportazione
  gestionale.
- **XML (FIE) → JSON (touche-export)** — ricostruisce un file
  touche-export a partire da un XML FIE (conversione "best effort":
  l'XML FIE non contiene tutti i dati gestionali originali, vedi i
  limiti descritti in cima a `fie2touche.py`).

Non serve installare Python: grazie a GitHub Actions, ogni volta che
carichi il codice su GitHub vengono generati automaticamente gli
eseguibili pronti per **Windows**, **macOS** e **Linux**.

## Contenuto del pacchetto

```
touche2fie.py                -> logica di conversione JSON -> XML
fie2touche.py                -> logica di conversione XML -> JSON
gui.py                       -> interfaccia grafica "Touché!Convert" (punto di ingresso)
requirements.txt             -> dipendenze per la build (solo PyInstaller)
assets/
  icon.ico                   -> icona per l'eseguibile Windows
  icon.icns                  -> icona per l'app macOS
  icon_256.png / icon_512.png-> icona per Linux e per la finestra dell'app
  fie_watermark.png          -> logo FIE con sfondo rimosso, usato come
                                 filigrana nell'intestazione dell'interfaccia
.github/workflows/build.yml  -> istruzioni per GitHub Actions (build automatica)
```

## Come ottenere gli eseguibili (nessuna installazione richiesta)

### 1. Crea un repository su GitHub
Vai su github.com, crea un account se non ne hai uno, poi crea un
nuovo repository (es. `touche-convert`), anche privato va bene.

### 2. Carica questi file
Dal browser, senza riga di comando:
- apri il repository -> "Add file" -> "Upload files"
- trascina dentro **tutti** i file/cartelle di questo pacchetto,
  **mantenendo la struttura** (in particolare `.github/workflows/` e
  `assets/`)
- conferma il commit ("Commit changes")

### 3. Attendi la compilazione automatica
- vai nella scheda **Actions**: vedrai il workflow "Build
  Touché!Convert (Windows / macOS / Linux)" già in esecuzione
  (di solito 2-5 minuti per tutte e tre le piattaforme)
- quando è completato, aprilo e in fondo trovi tre **Artifacts**:
  - `Touche-Convert-Windows` → contiene `Touché!Convert.exe`
  - `Touche-Convert-macOS` → contiene `Touche-Convert-macOS.zip`
    (dentro c'è l'app `Touché!Convert.app`)
  - `Touche-Convert-Linux` → contiene l'eseguibile `ToucheConvert`

### 4. (Opzionale) Creare una versione "ufficiale" sempre scaricabile
Gli artifact scadono dopo 90 giorni. Per un link permanente:
- scheda **Releases** -> "Draft a new release" -> Tag `v1.0.0` ->
  Publish
- il workflow si riattiva e allega automaticamente i tre eseguibili
  alla Release

## Come usare l'app una volta scaricata

**Windows**: doppio clic su `Touché!Convert.exe`. Al primo avvio
SmartScreen potrebbe avvisare che l'app non è firmata digitalmente
(normale per eseguibili senza certificato a pagamento): scegli
"Ulteriori informazioni" -> "Esegui comunque".

**macOS**: estrai lo zip, sposta `Touché!Convert.app` dove preferisci
(es. Applicazioni) e aprila con **tasto destro -> Apri** la prima
volta (Gatekeeper blocca le app scaricate da internet non firmate con
un account sviluppatore Apple a pagamento: aprendola così una volta,
le volte successive si aprirà normalmente con doppio clic).

**Linux**: rendi eseguibile il file scaricato e avvialo:
```
chmod +x ToucheConvert
./ToucheConvert
```

Una volta aperta, l'app mostra due schede: scegli quella che ti serve,
seleziona il file di origine e la cartella di destinazione, premi
"Converti".

## Cosa è cambiato rispetto alla prima versione
- Interfaccia ridisegnata (tema scuro, header con il logo FIE come
  filigrana, icona dedicata) invece della semplice finestra grigia
  di base
- Aggiunta la conversione inversa XML → JSON
- L'eseguibile ora si chiama **Touché!Convert** e usa il logo fornito
  come icona dell'app su tutte le piattaforme
- Build automatica per Windows, macOS e Linux invece del solo Windows

## Aggiornare il programma in futuro
Ogni volta che modifichi i file `.py` e carichi le modifiche su
GitHub (nuovo commit), i tre eseguibili vengono ricompilati
automaticamente: non devi ripetere alcuna configurazione.

## Sviluppo/compilazione in locale (facoltativo)
Se preferisci compilare da solo invece di usare GitHub Actions
(va comunque eseguito sul sistema operativo di destinazione: PyInstaller
non fa compilazione incrociata fra sistemi diversi):
```
pip install -r requirements.txt

# Windows
pyinstaller --noconfirm --onefile --windowed --name "Touché!Convert" --icon assets/icon.ico --add-data "assets;assets" gui.py

# macOS
pyinstaller --noconfirm --windowed --name "Touché!Convert" --icon assets/icon.icns --add-data "assets:assets" gui.py

# Linux
pyinstaller --noconfirm --onefile --windowed --name "ToucheConvert" --add-data "assets:assets" gui.py
```
L'eseguibile/app verrà creato nella cartella `dist/`.
