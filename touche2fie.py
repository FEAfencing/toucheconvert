#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
touche2fie.py
=============
Convertitore dal formato "touche-export" (JSON) al formato XML FIE
(CompetitionIndividuelle / Fencing-Time style) usato per la
pubblicazione dei risultati di gara.

Uso:
    python3 touche2fie.py input.json [cartella_output]

Per ogni "gara" presente nel file JSON viene generato un file XML
separato (una CompetitionIndividuelle rappresenta sempre UNA sola
gara/arma/categoria), con nome nel formato:

    RESULTS_<Sesso><Arma>_<Anno>-<indice>.xml

----------------------------------------------------------------------
LOGICA DI MAPPATURA (semantizzazione dei campi)
----------------------------------------------------------------------

Livello Competizione (elemento <CompetitionIndividuelle>)
  Championnat    -> costante configurabile (default "FIS": non deducibile
                    dal JSON touche-export, non esiste un campo
                    equivalente esplicito)
  Annee          -> circuito.stagione (già in formato "AAAA/AAAA")
  Arme           -> gara.arma  (Spada->E, Fioretto->F, Sciabola->S)
  Sexe           -> gara.genere (Misto->X, Maschile->M, Femminile->F)
  Domaine        -> gara.tipologia (individuale->I, a squadre->T)
  Federation     -> nazionalità più frequente fra gli iscritti
  Organisateur   -> evento.autorita (l'ente organizzatore/federazione)
  Categorie      -> mappatura categoria FIE nota; "Open" non ha codice
                    FIE standard => stringa vuota
  Date           -> evento.data_inizio (YYYY-MM-DD -> DD.MM.YYYY)
  TitreLong      -> evento.titolo
  DateFichierXML -> esportato_il (istante di export, formattato)

  NB: nel file di riferimento fornito come esempio
  (RESULTS_XE_2026-0.xml) i valori di "Annee" e "Date" riportano l'anno
  2026 anziché il 2025 reale della gara (evento.data_inizio =
  "2025-03-12", circuito.stagione = "2024/2025"): si tratta di
  un'incoerenza del file di esempio (probabilmente generato usando la
  data di esportazione anziché quella della gara). Questo convertitore
  deriva i valori correttamente dai campi sorgente, non li ricopia
  ciecamente dall'esempio.

Tireurs (atleti)
  Elenco di tutti gli iscritti alla gara, deduplicati, ordinati per
  cognome (poi per numero di licenza a parità di cognome) e numerati
  con ID negativi progressivi (-1, -2, ...).
    Nom, Prenom     -> atleta.cognome, atleta.nome
    DateNaissance   -> atleta.data_nascita (DD/MM/AA -> DD.MM.AAAA)
    Sexe            -> atleta.genere
    Lateralite      -> non presente nel formato touche-export: viene
                        impostata di default a "D" (mancinismo non
                        rilevabile dai dati sorgente)
    Nation          -> atleta.nazionalita
    Club            -> atleta.societa_nome
    Ligue           -> non presente esplicitamente nella forma attesa
                        dal formato FIE (regione_societa non è un
                        codice federale) => stringa vuota
    Licence         -> atleta.licenza
    Classement      -> iscritto.classifica_finale (piazzamento finale
                        di gara)
    Statut          -> "N" di norma; "A" se l'atleta risulta essersi
                        ritirato ("ritiro") in almeno un assalto,
                        "E" se escluso/squalificato

Arbitres (giudici)
  Costruito raccogliendo tutti gli "arbitro" citati negli assalti
  (gironi e tabelloni). Se l'arbitro coincide con un atleta già
  presente fra i Tireurs (stesso cognome+nome) ne riusa lo stesso ID
  (comportamento verificato nel file di esempio: gli arbitri che sono
  anche atleti hanno lo stesso ID nei due elenchi). Altrimenti riceve
  un nuovo ID negativo progressivo.

Phases -> TourDePoules (gironi)
  Un elemento <TourDePoules> per ciascun turno_gironi.
    NbDePoules            -> numero di gironi nel turno
    NbQualifiesParIndice  -> numero di iscritti con stato="qualificato"
                              (qualificati agli scontri diretti)
    NbQualifiesParPoule   -> 0 (qualificazione per indice/ranking, non
                              per posizione fissa nel girone)
  Lista <Tireur> (classifica generale dopo i gironi):
    RangInitial -> ranking_gara (testa di serie iniziale)
    RangFinal   -> piazzamento globale calcolato sulla base delle
                    statistiche di girone, secondo l'algoritmo FIE
                    standard: (1) % vittorie decrescente,
                    (2) indice (stoccate date - subite) decrescente,
                    (3) stoccate date decrescenti.
                    Questo valore coincide, per gli iscritti già
                    qualificati, con il campo "classifica_girone"
                    presente nel JSON; per i non qualificati (per cui
                    "classifica_girone" è null) viene calcolato con lo
                    stesso algoritmo per completare la classifica.
    Statut      -> "Q" se il rango calcolato rientra nel numero di
                    qualificati, altrimenti "N"
  Per ciascun girone -> <Poule>:
    <Tireur>: NoDansLaPoule e RangPoule -> "posizione" (l'unico ordine
              disponibile nella fonte), NbVictoires -> vittorie,
              NbMatches -> vittorie+sconfitte, TD -> stoccate_date,
              TR -> stoccate_ricevute
    <Match>: ID -> "ordine"; i due <Tireur> figli hanno Score ->
              punteggio_a/punteggio_b e Statut V/D in base al vincitore

Phases -> PhaseDeTableaux (tabellone ad eliminazione diretta)
  Un elemento <PhaseDeTableaux> per ciascun turno_diretta.
  Lista <Tireur> (solo i qualificati agli scontri diretti):
    RangInitial -> rango calcolato dopo i gironi (= RangFinal della
                    TourDePoules)
    RangFinal   -> iscritto.classifica_finale (piazzamento definitivo)
    Statut      -> "A" se l'atleta si è ritirato durante il tabellone,
                    altrimenti "N"
  <SuiteDeTableaux>: un'unica sequenza di tabelloni, suddivisa per
      "round_numero" degli assalti di turni_diretta. La dimensione di
      ciascun tabellone è calcolata come
        taglia_round = NbQualifiesParIndice / 2^(round_numero-1)
      con titolo "Tableau of N", "Semi-finals" (N=4) o "Final" (N=2).
      <Match>: ID -> "posizione_tabellone" (coincide con la posizione
      del match nel tabellone del turno), Piste -> pedana (se
      presente), <Arbitre Role="P"> se un arbitro è indicato,
      punteggi/ritiri gestiti come per i gironi (ritiro -> Score="0",
      Statut "A" per chi si ritira e "V" per l'avversario).

Limiti noti / dati non deducibili dalla fonte:
  - "Lateralite" (mancinismo) non è presente nel formato touche-export
    e viene impostata di default a "D" per tutti gli atleti.
  - "Ligue" (codice di lega/comitato regionale) non viene valorizzato:
    il formato touche-export fornisce solo la denominazione della
    regione societaria, non un codice di lega FIE/federale.
  - L'orario esatto (attributo "Date" sui singoli <Match> del
    tabellone) viene riportato solo se "ora_appello" è valorizzato
    nella fonte; se assente (come nel file di esempio fornito) viene
    omesso anziché inventato.
  - Il repêchage non è gestito in questa versione (nell'esempio
    fornito "repechage_attivo" risulta 0, cioè disattivato).
"""

import json
import sys
import os
import re
from datetime import datetime
from collections import Counter, defaultdict
from xml.sax.saxutils import escape as xml_escape


# ----------------------------------------------------------------------
# Costanti di mappatura
# ----------------------------------------------------------------------

ARMA_MAP = {
    "spada": "E",
    "fioretto": "F",
    "sciabola": "S",
}

GENERE_MAP = {
    "misto": "X",
    "maschile": "M",
    "uomini": "M",
    "femminile": "F",
    "donne": "F",
}

DOMAINE_MAP = {
    "individuale": "I",
    "a squadre": "T",
    "squadra": "T",
    "squadre": "T",
}

# Codici categoria FIE noti; le categorie non presenti (es. "Open", che
# non è una categoria d'età ufficiale FIE) restano senza codice.
CATEGORIA_MAP = {
    "under 10": "U10",
    "giovanissimi": "U10",
    "giovanissimi/e": "U10",
    "under 12": "U12",
    "under 14": "U14",
    "ragazzi": "U14",
    "ragazzi/e": "U14",
    "allievi": "U17",
    "allievi/e": "U17",
    "cadetti": "U17",
    "cadetti/e": "U17",
    "giovani": "U20",
    "juniores": "U20",
    "seniores": "S",
    "senior": "S",
    "assoluti": "S",
    "veterani": "V",
    "veterans": "V",
}

STATI_RITIRO = {"ritiro", "abbandono"}
STATI_ESCLUSIONE = {"squalificato", "escluso", "esclusione"}

CHAMPIONNAT_DEFAULT = "FIS"


# ----------------------------------------------------------------------
# Funzioni di utilità
# ----------------------------------------------------------------------

def norm(s):
    return (s or "").strip().lower()


def map_or_default(mapping, key, default=""):
    return mapping.get(norm(key), default)


def convert_date_nascita(data_nascita):
    """DD/MM/AA -> DD.MM.AAAA (interpretazione anno a 2 cifre rispetto
    all'anno corrente)."""
    if not data_nascita:
        return ""
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", data_nascita.strip())
    if not m:
        return data_nascita
    gg, mm, aa = m.groups()
    if len(aa) == 2:
        current_yy = datetime.now().year % 100
        aa_int = int(aa)
        aa = str(2000 + aa_int) if aa_int <= current_yy else str(1900 + aa_int)
    return f"{int(gg):02d}.{int(mm):02d}.{aa}"


def convert_date_evento(data_iso):
    """YYYY-MM-DD (o YYYY-MM-DDTHH:MM) -> DD.MM.YYYY"""
    if not data_iso:
        return ""
    data_part = data_iso.split("T")[0]
    y, m, d = data_part.split("-")
    return f"{d}.{m}.{y}"


def convert_datetime_export(iso_dt):
    """ISO datetime -> 'DD.MM.YYYY HH:MM'"""
    if not iso_dt:
        return ""
    try:
        dt = datetime.fromisoformat(iso_dt)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return ""


def esc(v):
    if v is None:
        return ""
    return xml_escape(str(v), {'"': "&quot;"})


def attr(name, value, omit_if_empty=False):
    """Genera name="value" già escapato; se omit_if_empty e valore
    vuoto/None, ritorna stringa vuota (attributo omesso)."""
    if value is None or (omit_if_empty and value == ""):
        return ""
    return f' {name}="{esc(value)}"'


# ----------------------------------------------------------------------
# Costruzione elenco Tireurs (atleti) univoci per la gara
# ----------------------------------------------------------------------

def build_tireurs(gara):
    """Ritorna:
       - lista ordinata di dict atleta (con id assegnato, chiave 'id')
       - mappa iscritto_idx (indice nella lista 'iscritti' della gara) -> id tireur
    """
    iscritti = gara["iscritti"]

    # ordina per cognome, poi per licenza (chiave di parità osservata
    # nei casi di omonimia di cognome)
    ordinati = sorted(
        range(len(iscritti)),
        key=lambda i: (
            norm(iscritti[i]["atleta"]["cognome"]),
            iscritti[i]["atleta"].get("licenza") or "",
        ),
    )

    tireurs = []
    idx_to_id = {}
    for pos, i in enumerate(ordinati):
        tid = -(pos + 1)
        idx_to_id[i] = tid
        atl = iscritti[i]["atleta"]
        tireurs.append({
            "id": tid,
            "iscritto_idx": i,
            "cognome": atl.get("cognome", ""),
            "nome": atl.get("nome", ""),
            "data_nascita": convert_date_nascita(atl.get("data_nascita", "")),
            "sesso": atl.get("genere", ""),
            "nazionalita": atl.get("nazionalita", ""),
            "club": atl.get("societa_nome", ""),
            "licenza": atl.get("licenza", ""),
            "classifica_finale": iscritti[i].get("classifica_finale"),
        })
    return tireurs, idx_to_id


def rileva_statuto_ritiro(gara, idx_to_id):
    """Determina, per ciascun iscritto_idx, se compare in un assalto
    con stato di ritiro/abbandono o squalifica/esclusione, in
    qualunque fase (gironi o tabelloni)."""
    statuto = defaultdict(lambda: "N")

    def scan_assalti_gironi():
        for turno in gara.get("turni_gironi", []):
            for girone in turno.get("gironi", []):
                pos_to_idx = {a["posizione"]: a["iscritto_idx"] for a in girone["atleti"]}
                for assalto in girone.get("assalti", []):
                    stato = norm(assalto.get("stato"))
                    if stato in STATI_RITIRO or stato in STATI_ESCLUSIONE:
                        vinc = assalto.get("vincitore")
                        # solo il lato che NON ha vinto è quello che si è
                        # ritirato/escluso; l'altro riceve la vittoria a tavolino
                        for lato, lato_key in (("posizione_a", "a"), ("posizione_b", "b")):
                            if lato_key == vinc:
                                continue
                            idx = pos_to_idx.get(assalto[lato])
                            if idx is not None:
                                statuto[idx] = "A" if stato in STATI_RITIRO else "E"

    def scan_assalti_diretta():
        for turno in gara.get("turni_diretta", []):
            for assalto in turno.get("assalti", []):
                stato = norm(assalto.get("stato"))
                if stato in STATI_RITIRO or stato in STATI_ESCLUSIONE:
                    vinc_idx = assalto.get("vincitore_idx")
                    for lato in ("iscritto_a_idx", "iscritto_b_idx"):
                        idx = assalto.get(lato)
                        if idx is not None and idx != vinc_idx:
                            statuto[idx] = "A" if stato in STATI_RITIRO else "E"

    scan_assalti_gironi()
    scan_assalti_diretta()
    return statuto


# ----------------------------------------------------------------------
# Costruzione elenco Arbitres
# ----------------------------------------------------------------------

def build_arbitres(gara, tireurs):
    by_name = {(norm(t["cognome"]), norm(t["nome"])): t["id"] for t in tireurs}
    arbitri = {}  # (cognome,nome) -> dict
    next_id = -(len(tireurs) + 1)

    def registra(arb):
        if not arb:
            return
        cognome = arb.get("cognome", "")
        nome = arb.get("nome", "")
        key = (norm(cognome), norm(nome))
        if key in arbitri:
            return
        nonlocal_id = by_name.get(key)
        arbitri[key] = {
            "id": nonlocal_id,
            "cognome": cognome,
            "nome": nome,
            "is_tireur": nonlocal_id is not None,
        }

    for turno in gara.get("turni_gironi", []):
        for girone in turno.get("gironi", []):
            for assalto in girone.get("assalti", []):
                registra(assalto.get("arbitro"))
    for turno in gara.get("turni_diretta", []):
        for assalto in turno.get("assalti", []):
            registra(assalto.get("arbitro"))

    # assegna ID nuovi a chi non è già un tireur, in ordine di comparsa
    for key, arb in arbitri.items():
        if arb["id"] is None:
            arb["id"] = next_id
            next_id -= 1

    tireur_by_id = {t["id"]: t for t in tireurs}
    risultato = []
    for arb in arbitri.values():
        if arb["is_tireur"]:
            t = tireur_by_id[arb["id"]]
            risultato.append({
                "id": arb["id"],
                "cognome": t["cognome"],
                "nome": t["nome"],
                "sesso": t["sesso"],
                "nazionalita": t["nazionalita"],
                "club": t["club"],
                "licenza": t["licenza"],
                "data_nascita": t["data_nascita"],
            })
        else:
            risultato.append({
                "id": arb["id"],
                "cognome": arb["cognome"],
                "nome": arb["nome"],
                "sesso": "",
                "nazionalita": "",
                "club": "",
                "licenza": "",
                "data_nascita": "",
            })
    risultato.sort(key=lambda a: -a["id"])
    return risultato, {(norm(a["cognome"]), norm(a["nome"])): a["id"] for a in risultato}


# ----------------------------------------------------------------------
# Algoritmo di classifica di girone (rango globale post-gironi)
# ----------------------------------------------------------------------

def calcola_seeding_iniziale(gara):
    """Ritorna dict iscritto_idx -> rango ordinale 1..N calcolato
    ordinando gli iscritti della gara per ranking_gara crescente
    (a parità, punti_gara decrescenti). Il "ranking_gara" grezzo è un
    valore riferito all'intero circuito e non è contiguo 1..N per i
    soli iscritti di questa gara: la semina (RangInitial) del
    tabellone/gironi è invece l'ordinale relativo fra i soli
    partecipanti a questa gara."""
    iscritti = gara["iscritti"]
    ordine = sorted(
        range(len(iscritti)),
        key=lambda i: (
            iscritti[i].get("ranking_gara") if iscritti[i].get("ranking_gara") is not None else 9999,
            -(iscritti[i].get("punti_gara") or 0),
        ),
    )
    return {idx: pos + 1 for pos, idx in enumerate(ordine)}


def calcola_rango_gironi(gara, idx_to_id):
    """Ritorna dict iscritto_idx -> rango globale (1..N) calcolato
    secondo l'algoritmo standard: % vittorie desc, indice desc,
    stoccate_date desc."""
    stats = {}
    for turno in gara.get("turni_gironi", []):
        for girone in turno.get("gironi", []):
            for a in girone["atleti"]:
                idx = a["iscritto_idx"]
                vitt = a.get("vittorie", 0) or 0
                sconf = a.get("sconfitte", 0) or 0
                incontri = vitt + sconf
                td = a.get("stoccate_date", 0) or 0
                tr = a.get("stoccate_ricevute", 0) or 0
                ratio = (vitt / incontri) if incontri else 0.0
                stats[idx] = {
                    "ratio": ratio,
                    "indice": td - tr,
                    "td": td,
                    "classifica_girone": a.get("classifica_girone"),
                }
    ordine = sorted(
        stats.keys(),
        key=lambda i: (-stats[i]["ratio"], -stats[i]["indice"], -stats[i]["td"]),
    )
    rango = {}
    for pos, idx in enumerate(ordine, start=1):
        rango[idx] = pos
    return rango


# ----------------------------------------------------------------------
# Costruzione XML
# ----------------------------------------------------------------------

def costruisci_xml_gara(dati, gara, indice_gara):
    evento = dati["evento"]
    circuito = dati["circuito"]

    tireurs, idx_to_id = build_tireurs(gara)
    id_to_idx = {v: k for k, v in idx_to_id.items()}
    statuto_ritiro = rileva_statuto_ritiro(gara, idx_to_id)
    arbitri, arbitro_id_by_name = build_arbitres(gara, tireurs)

    for t in tireurs:
        t["statut"] = statuto_ritiro.get(t["iscritto_idx"], "N")

    tireur_by_id = {t["id"]: t for t in tireurs}

    # attributi di testata
    arma = map_or_default(ARMA_MAP, gara.get("arma"), "")
    sesso = map_or_default(GENERE_MAP, gara.get("genere"), "")
    dominio = map_or_default(DOMAINE_MAP, gara.get("tipologia"), "I")
    categoria = map_or_default(CATEGORIA_MAP, gara.get("categoria"), "")

    nazionalita_iscritti = [
        i["atleta"].get("nazionalita") for i in gara["iscritti"] if i["atleta"].get("nazionalita")
    ]
    federazione = Counter(nazionalita_iscritti).most_common(1)[0][0] if nazionalita_iscritti else ""

    righe = []
    righe.append('<?xml version="1.0" encoding="utf-8"?>')
    righe.append("<!DOCTYPE CompetitionIndividuelle>")
    righe.append("<!-- Generato da touche2fie.py (convertitore touche-export -> FIE XML) -->")

    header = (
        "<CompetitionIndividuelle"
        + attr("Championnat", CHAMPIONNAT_DEFAULT)
        + attr("ID", "")
        + attr("Annee", circuito.get("stagione", ""))
        + attr("Arme", arma)
        + attr("Sexe", sesso)
        + attr("Domaine", dominio)
        + attr("Federation", federazione)
        + attr("Organisateur", evento.get("autorita", ""))
        + attr("Categorie", categoria)
        + attr("Date", convert_date_evento(evento.get("data_inizio", "")))
        + attr("TitreLong", evento.get("titolo", ""))
        + attr("DateFichierXML", convert_datetime_export(dati.get("esportato_il", "")))
        + ">"
    )
    righe.append(header)

    # ---------------- Tireurs ----------------
    righe.append("    <Tireurs>")
    for t in tireurs:
        riga = (
            "        <Tireur"
            + attr("ID", t["id"])
            + attr("Nom", t["cognome"])
            + attr("Prenom", t["nome"])
            + attr("DateNaissance", t["data_nascita"])
            + attr("Sexe", t["sesso"])
            + attr("Lateralite", "D")
            + attr("Nation", t["nazionalita"])
            + attr("Club", t["club"])
            + attr("Ligue", "")
            + attr("Licence", t["licenza"])
            + attr("Classement", t["classifica_finale"])
            + attr("Statut", t["statut"])
            + " />"
        )
        righe.append(riga)
    righe.append("    </Tireurs>")

    # ---------------- Arbitres ----------------
    righe.append("    <Arbitres>")
    for a in arbitri:
        riga = (
            "        <Arbitre"
            + attr("ID", a["id"])
            + attr("Nom", a["cognome"])
            + attr("Prenom", a["nome"])
            + attr("Sexe", a["sesso"])
            + attr("Nation", a["nazionalita"])
            + attr("Club", a["club"])
            + attr("Ligue", "")
            + attr("Licence", a["licenza"])
            + attr("DateNaissance", a["data_nascita"])
            + attr("Categorie", "")
            + " />"
        )
        righe.append(riga)
    righe.append("    </Arbitres>")

    righe.append("    <Phases>")

    # ---------------- TourDePoules ----------------
    n_qualificati = sum(1 for i in gara["iscritti"] if norm(i.get("stato")) == "qualificato")
    rango_gironi = calcola_rango_gironi(gara, idx_to_id)
    seeding_iniziale = calcola_seeding_iniziale(gara)

    turni_gironi = gara.get("turni_gironi", [])
    n_phase_poules = len(turni_gironi)
    n_phase_diretta = len(gara.get("turni_diretta", []))

    for gi, turno in enumerate(turni_gironi, start=1):
        phase_id = f"TourPoules{gi}"
        successiva = "PhaseTableaux1" if n_phase_diretta > 0 else ""
        n_gironi = len(turno.get("gironi", []))

        apertura = (
            "        <TourDePoules"
            + attr("PhaseID", phase_id)
            + attr("ID", gi)
            + attr("PhaseSuivanteDesQualifies", successiva, omit_if_empty=True)
            + attr("NbDePoules", n_gironi)
            + attr("NbQualifiesParPoule", 0)
            + attr("NbQualifiesParIndice", n_qualificati)
            + ">"
        )
        righe.append(apertura)

        # classifica generale post-gironi, in ordine di ID Tireur
        for t in sorted(tireurs, key=lambda x: x["id"]):
            idx = t["iscritto_idx"]
            if idx not in rango_gironi:
                continue
            rang_final = rango_gironi[idx]
            rang_iniziale = seeding_iniziale[idx]
            statut = "Q" if rang_final <= n_qualificati else "N"
            righe.append(
                "            <Tireur"
                + attr("REF", t["id"])
                + attr("RangInitial", rang_iniziale)
                + attr("RangFinal", rang_final)
                + attr("Statut", statut)
                + " />"
            )

        for girone in turno.get("gironi", []):
            righe.append(f'            <Poule ID="{girone["numero"]}">')
            pos_to_idx = {}
            for a in girone["atleti"]:
                idx = a["iscritto_idx"]
                pos_to_idx[a["posizione"]] = idx
                tid = idx_to_id[idx]
                righe.append(
                    "                <Tireur"
                    + attr("REF", tid)
                    + attr("NoDansLaPoule", a["posizione"])
                    + attr("NbVictoires", a.get("vittorie", 0))
                    + attr("NbMatches", (a.get("vittorie", 0) or 0) + (a.get("sconfitte", 0) or 0))
                    + attr("TD", a.get("stoccate_date", 0))
                    + attr("TR", a.get("stoccate_ricevute", 0))
                    + attr("RangPoule", a["posizione"])
                    + " />"
                )
            for assalto in girone.get("assalti", []):
                match_id = assalto["ordine"]
                idx_a = pos_to_idx.get(assalto["posizione_a"])
                idx_b = pos_to_idx.get(assalto["posizione_b"])
                pa, pb = assalto.get("punteggio_a"), assalto.get("punteggio_b")
                vinc = assalto.get("vincitore")
                stato_assalto = norm(assalto.get("stato"))
                righe.append(f'                <Match ID="{match_id}">')
                for lato_idx, lato_pt, lato_key in ((idx_a, pa, "a"), (idx_b, pb, "b")):
                    tid = idx_to_id.get(lato_idx)
                    score = lato_pt if lato_pt is not None else 0
                    if stato_assalto in STATI_RITIRO and lato_pt is None:
                        statut_m = "A" if vinc != lato_key else "V"
                    else:
                        statut_m = "V" if vinc == lato_key else "D"
                    righe.append(
                        "                    <Tireur"
                        + attr("REF", tid)
                        + attr("Score", score)
                        + attr("Statut", statut_m)
                        + " />"
                    )
                righe.append("                </Match>")
            righe.append("            </Poule>")
        righe.append("        </TourDePoules>")

    # ---------------- PhaseDeTableaux ----------------
    for di, turno in enumerate(gara.get("turni_diretta", []), start=1):
        phase_id = f"PhaseTableaux{di}"
        righe.append(f'        <PhaseDeTableaux PhaseID="{phase_id}" ID="{di}">')

        for t in sorted(tireurs, key=lambda x: x["id"]):
            idx = t["iscritto_idx"]
            if idx not in rango_gironi or rango_gironi[idx] > n_qualificati:
                continue
            iscritto = gara["iscritti"][idx]
            righe.append(
                "            <Tireur"
                + attr("REF", t["id"])
                + attr("RangInitial", rango_gironi[idx])
                + attr("RangFinal", iscritto.get("classifica_finale"))
                + attr("Statut", t["statut"])
                + " />"
            )

        assalti = turno.get("assalti", [])
        round_numbers = sorted(set(a["round_numero"] for a in assalti))
        n_tableaux = len(round_numbers)
        taglia_iniziale = n_qualificati

        righe.append(
            f'            <SuiteDeTableaux ID="SuiteTab_{di}" NbDeTableaux="{n_tableaux}" '
            f'Titre="Main tableau of {taglia_iniziale}">'
        )

        for rn in round_numbers:
            taglia = max(2, taglia_iniziale // (2 ** (rn - 1)))
            if taglia == 2:
                titolo = "Final"
            elif taglia == 4:
                titolo = "Semi-finals"
            else:
                titolo = f"Tableau of {taglia}"
            tab_id = f"A{taglia}"
            righe.append(f'                <Tableau ID="{tab_id}" Titre="{esc(titolo)}" Taille="{taglia}">')

            assalti_round = sorted(
                (a for a in assalti if a["round_numero"] == rn),
                key=lambda a: a["posizione_tabellone"],
            )
            for assalto in assalti_round:
                match_id = assalto["posizione_tabellone"]
                pedana = assalto.get("pedana")
                ora = assalto.get("ora_appello")
                apertura_match = f'                    <Match ID="{match_id}"'
                if ora:
                    apertura_match += attr("Date", ora)
                if pedana:
                    apertura_match += attr("Piste", pedana)
                apertura_match += ">"
                righe.append(apertura_match)

                arbitro = assalto.get("arbitro")
                if arbitro:
                    key = (norm(arbitro.get("cognome")), norm(arbitro.get("nome")))
                    aid = arbitro_id_by_name.get(key)
                    if aid is not None:
                        righe.append(f'                        <Arbitre REF="{aid}" Role="P" />')

                idx_a = assalto.get("iscritto_a_idx")
                idx_b = assalto.get("iscritto_b_idx")
                pa, pb = assalto.get("punteggio_a"), assalto.get("punteggio_b")
                vinc_idx = assalto.get("vincitore_idx")
                stato_assalto = norm(assalto.get("stato"))

                for lato_idx, lato_pt in ((idx_a, pa), (idx_b, pb)):
                    tid = idx_to_id.get(lato_idx)
                    score = lato_pt if lato_pt is not None else 0
                    if stato_assalto in STATI_RITIRO and lato_pt is None:
                        statut_m = "A" if lato_idx != vinc_idx else "V"
                    elif stato_assalto in STATI_ESCLUSIONE and lato_pt is None:
                        statut_m = "E" if lato_idx != vinc_idx else "V"
                    else:
                        statut_m = "V" if lato_idx == vinc_idx else "D"
                    righe.append(
                        "                        <Tireur"
                        + attr("REF", tid)
                        + attr("Score", score)
                        + attr("Statut", statut_m)
                        + " />"
                    )
                righe.append("                    </Match>")
            righe.append("                </Tableau>")
        righe.append("            </SuiteDeTableaux>")
        righe.append("        </PhaseDeTableaux>")

    righe.append("    </Phases>")
    righe.append("</CompetitionIndividuelle>")

    return "\n".join(righe) + "\n"


def nome_file_output(dati, gara, indice_gara):
    sesso = map_or_default(GENERE_MAP, gara.get("genere"), "X")
    arma = map_or_default(ARMA_MAP, gara.get("arma"), "X")
    data_inizio = gara.get("data_inizio", "") or dati["evento"].get("data_inizio", "")
    anno = data_inizio.split("-")[0] if data_inizio else "0000"
    return f"RESULTS_{sesso}{arma}_{anno}-{indice_gara}.xml"


def converti(path_json, cartella_out):
    with open(path_json, "r", encoding="utf-8") as f:
        dati = json.load(f)

    if dati.get("formato") != "touche-export":
        print(f"Attenzione: campo 'formato' inatteso: {dati.get('formato')!r}", file=sys.stderr)

    os.makedirs(cartella_out, exist_ok=True)
    generati = []
    for indice_gara, gara in enumerate(dati.get("gare", [])):
        xml_str = costruisci_xml_gara(dati, gara, indice_gara)
        nome_file = nome_file_output(dati, gara, indice_gara)
        percorso = os.path.join(cartella_out, nome_file)
        with open(percorso, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write(xml_str)
        generati.append(percorso)
    return generati


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 touche2fie.py input.json [cartella_output]", file=sys.stderr)
        sys.exit(1)
    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    files = converti(input_path, output_dir)
    for f in files:
        print(f"Generato: {f}")
