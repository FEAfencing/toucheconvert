#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fisdotnet.py
============
Convertitore fra il formato "FisDotNet" (l'XML "dsLoadSave" prodotto/
importato dal software federale, es. file "ExpAllGara_*.XML") e il
formato "touche-export" (JSON), nei due sensi, con supporto ad eventi
composti da PIÙ gare (più armi/generi/categorie in un solo file).

----------------------------------------------------------------------
MODELLO DEI DATI FisDotNet (dedotto per analisi diretta del file,
non da documentazione ufficiale: alcuni dettagli marginali possono
differire da installazione a installazione)
----------------------------------------------------------------------
Il file è un dataset ADO.NET "piatto": dopo il blocco <xs:schema>
(che descrive solo la struttura e viene ignorato in lettura) seguono
righe ripetute, una per record, per varie "tabelle":

  Tornei            -> UN torneo/circuito (CodTorneo, Descrizione...).
                       Corrisponde al "circuito" del formato touche.
  Gare              -> UN evento (un file = un evento). "IdGara" è
                       l'identificativo dell'EVENTO, non di una singola
                       gara: "Categoria1..6" elenca le categorie d'età
                       incluse. La singola gara (arma+genere+categoria)
                       è invece identificata dalla combinazione dei
                       campi (Categoria/CatAtleti, Flags=arma,
                       MaschioFemmina=genere) che ricorre nelle altre
                       tabelle.
  FormulaGara       -> una riga per ciascuna gara (combinazione
                       arma/genere) con i parametri di formula.
  PartecipantiGara  -> iscritti all'evento (atleti E staff, distinti
                       dai flag FlgDirettore/FlgComputerista/FlgArbitro/
                       FlgFioretto/FlgSpada/FlgSciabola). Un atleta è
                       iscritto una riga per ciascuna arma praticata.
  Tesserati / TesseratiFIS -> anagrafica atleti (NumFIS -> dati
                       personali), condivisa fra tutte le gare/eventi.
  Societa           -> anagrafica società/club (CodSoc -> nome).
  Gironi            -> UNA riga per ATLETA per GIRONE (statistiche di
                       girone: vittorie, stoccate, ecc. — non i singoli
                       assalti). Numerazione Girone a partire da 0.
  Assalti           -> i singoli incontri INDIVIDUALI. Il campo
                       "EliminDirect" li distingue:
                         EliminDirect == 0  -> assalto di girone
                                               (il numero di girone è
                                               nel campo "Girone")
                         EliminDirect != 0  -> assalto ad eliminazione
                                               diretta, e il suo valore
                                               è la dimensione del
                                               tabellone di quel turno
                                               (128, 64, 32, ... 2)
  AssaltiRipesc     -> come Assalti, ma per il tabellone di ripescaggio
                       (se presente).
  Incontri / IncontriRipesc -> INCONTRI A SQUADRE (una riga = uno
                       scontro fra due squadre, con il punteggio
                       complessivo). *** IMPORTANTE: NON sono mai
                       usati per popolare gli assalti individuali.
                       Servono solo a rilevare che una gara è "a
                       squadre"; la ricostruzione dettagliata delle
                       formazioni di squadra non è implementata (vedi
                       limiti più sotto) — in ogni caso i singoli
                       assalti che compongono un incontro a squadre
                       restano comunque righe della tabella "Assalti"
                       e vengono trattati come tali. ***

Convenzioni dedotte dal file di esempio (documentate perché non
standardizzate/non verificabili al 100% senza la documentazione
ufficiale FIS):
  - Flags (bitmask arma) su Gironi/Assalti/FormulaGara:
        8 = Fioretto, 16 = Spada, 32 = Sciabola
    (dedotto incrociando il nome del file, che indica "FIO-SC", con
    il fatto che le righe FormulaGara con Flags=16 hanno "Passanti"=0
    in entrambi i generi, cioè quella gara non si è svolta).
  - MaschioFemmina numerico (Gironi/Assalti/FormulaGara): 0=Maschile,
    1=Femminile. Booleano (Tesserati.MaschioFemmina, PartecipantiGara/
    Tesserati "MF"): false=Maschile, true=Femminile.
  - Non esiste un codice età (CatAtleti/Categoria) standard
    documentato qui: viene mappato con una tabella best-effort
    (CATEGORIA_ETA_MAP) e, se il codice non è in tabella, viene
    riportato come stringa "Categoria N" anziché essere inventato.

----------------------------------------------------------------------
LIMITI NOTI
----------------------------------------------------------------------
  - Le gare A SQUADRE non vengono ricostruite in dettaglio (formazioni,
    incontri, sostituzioni): vengono segnalate come tali
    (gara.tipologia = "a squadre") con una nota, ma "turni_gironi"/
    "turni_diretta" restano quelli dei soli assalti individuali che
    le compongono (comunque corretti in sé, mai mescolati con gli
    "Incontri").
  - Il ripescaggio (AssaltiRipesc), se presente, viene riportato come
    fase aggiuntiva di turni_diretta con "repechage_attivo": 1, in
    forma semplificata.
  - "classifica_girone" non è quasi mai presente nei file FisDotNet
    osservati (il campo "ClasGir" risulta quasi sempre assente): viene
    lasciato a null, così come già avviene nel formato touche-export
    per gli atleti non tra i primi qualificati — la classifica di
    girone completa viene comunque ricalcolata correttamente a valle,
    ad esempio da touche2fie.py, con lo stesso algoritmo standard
    (percentuale vittorie, indice, stoccate fatte).
  - "ranking_gara" nel formato touche è un rango ordinale 1..N; qui
    viene ricalcolato ordinando gli iscritti per il campo "Ranking"
    di PartecipantiGara (punteggio di circuito) decrescente.
  - Non tutti i campi cosmetici del formato FisDotNet (loghi, colori
    di stampa, testi di intestazione, ecc.) vengono letti o scritti:
    nella conversione inversa (touche -> FisDotNet) vengono impostati
    a valori neutri/di default.
"""

import os
import re
import sys
import json
from datetime import datetime
from collections import defaultdict, Counter
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touche2fie as fwd  # noqa: E402  (riuso costanti/algoritmi già validati)

NS = "{http://www.tempuri.org/dsLoadSave.xsd}"

FLAG_ARMA = {8: "Fioretto", 16: "Spada", 32: "Sciabola"}
ARMA_FLAG = {v: k for k, v in FLAG_ARMA.items()}

GENERE_NUM = {"0": "Maschile", "1": "Femminile"}
GENERE_NUM_INV = {"Maschile": "0", "Femminile": "1"}
GENERE_BOOL = {"false": "Maschile", "true": "Femminile"}
GENERE_BOOL_INV = {"Maschile": "false", "Femminile": "true"}

# Best-effort: nessuna fonte ufficiale consultabile per la tabella
# completa dei codici "CatAtleti"/"Categoria"; codici non elencati
# restano come "Categoria N".
CATEGORIA_ETA_MAP = {
    1: "Giovanissimi/e",
    2: "Under 14",
    3: "Ragazzi/e",
    4: "Allievi/e",
    5: "Under 17",
    6: "Cadetti/e",
    7: "Under 20",
    8: "Giovani",
    9: "Assoluti",
    10: "Veterani",
}
CATEGORIA_ETA_INV = {v.lower(): k for k, v in CATEGORIA_ETA_MAP.items()}


def _bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() == "true"


def _int(v, default=None):
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except ValueError:
        return default


def _float(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


# ----------------------------------------------------------------------
# Lettura generica del dataset "piatto"
# ----------------------------------------------------------------------

def parse_dsloadsave(path):
    """Ritorna dict {nome_tabella: [ {campo: valore_stringa}, ... ]}."""
    tree = ET.parse(path)
    root = tree.getroot()
    tabelle = defaultdict(list)
    for el in root:
        tag = el.tag
        if tag.startswith("{http://www.w3.org/2001/XMLSchema}"):
            continue  # blocco di schema, non è un dato
        nome = tag.replace(NS, "")
        riga = {}
        for c in el:
            campo = c.tag.replace(NS, "")
            riga[campo] = c.text
        tabelle[nome].append(riga)
    return tabelle


def categoria_eta_nome(codice):
    if codice is None:
        return ""
    return CATEGORIA_ETA_MAP.get(_int(codice), f"Categoria {codice}")


def categoria_eta_codice(nome):
    if not nome:
        return None
    return CATEGORIA_ETA_INV.get(str(nome).strip().lower())


# ----------------------------------------------------------------------
# FisDotNet -> touche-export
# ----------------------------------------------------------------------

def fisdotnet_to_touche(path):
    t = parse_dsloadsave(path)

    tornei = t.get("Tornei", [])
    gare_evento = t.get("Gare", [])
    formula_rows = t.get("FormulaGara", [])
    partecipanti_rows = t.get("PartecipantiGara", [])
    tesserati_rows = t.get("Tesserati", []) + t.get("TesseratiFIS", [])
    societa_rows = t.get("Societa", [])
    gironi_rows = t.get("Gironi", [])
    assalti_rows = t.get("Assalti", [])
    assalti_ripesc_rows = t.get("AssaltiRipesc", [])
    incontri_rows = t.get("Incontri", []) + t.get("IncontriRipesc", [])

    gara_evento = gare_evento[0] if gare_evento else {}
    torneo = tornei[0] if tornei else {}

    evento_titolo = gara_evento.get("LuogoGara", "") or ""
    circuito_titolo = (torneo.get("Descrizione") or "").strip()
    # regola richiesta: se assente il circuito si usa il titolo dell'evento
    if not circuito_titolo:
        circuito_titolo = evento_titolo

    tesserati_idx = {}
    for r in tesserati_rows:
        num = r.get("NumFIS") or r.get("NumFis")
        if num:
            tesserati_idx[num] = r

    societa_idx = {r.get("CodSoc"): r for r in societa_rows if r.get("CodSoc") is not None}

    def nome_societa(cod_soc):
        r = societa_idx.get(cod_soc)
        if not r:
            return ""
        return (r.get("Denominazione") or "").strip()

    def dati_atleta(num_fis):
        r = tesserati_idx.get(num_fis)
        if not r:
            return {
                "cognome": "", "nome": "", "data_nascita": "",
                "genere": "", "nazionalita": "",
            }
        data_nasc = r.get("DataNascita") or ""
        if data_nasc:
            data_nasc = data_nasc.split("T")[0]
            try:
                y, m, d = data_nasc.split("-")
                data_nasc = f"{d}/{m}/{y[-2:]}"
            except ValueError:
                pass
        return {
            "cognome": (r.get("Cognome") or "").strip(),
            "nome": (r.get("Nome") or "").strip(),
            "data_nascita": data_nasc,
            "genere": "F" if _bool(r.get("MaschioFemmina")) else "M",
            "nazionalita": (r.get("Nazionalità") or "ITA").strip(),
        }

    def nome_arbitro(num_fis):
        if not num_fis or num_fis == "0":
            return None
        r = tesserati_idx.get(num_fis)
        if not r:
            return None
        return {"cognome": (r.get("Cognome") or "").strip(), "nome": (r.get("Nome") or "").strip()}

    # -------- individuazione delle singole gare (combinazioni) --------
    combos = []
    visti = set()
    for r in formula_rows:
        combo = (_int(r.get("CatAtleti")), _int(r.get("Flags")), r.get("MaschioFemmina"))
        if combo not in visti:
            visti.add(combo)
            combos.append(combo)
    if not combos:
        # fallback: deduce dalle altre tabelle se FormulaGara è assente
        for r in gironi_rows + assalti_rows + partecipanti_rows:
            cat = _int(r.get("Categoria") or r.get("CatAtleti"))
            flags = _int(r.get("Flags"))
            mf = r.get("MaschioFemmina")
            if flags in FLAG_ARMA and mf in ("0", "1"):
                combo = (cat, flags, mf)
                if combo not in visti:
                    visti.add(combo)
                    combos.append(combo)

    formula_by_combo = {}
    for r in formula_rows:
        combo = (_int(r.get("CatAtleti")), _int(r.get("Flags")), r.get("MaschioFemmina"))
        formula_by_combo[combo] = r

    incontri_combos = set()
    for r in incontri_rows:
        incontri_combos.add((_int(r.get("Categoria")), _int(r.get("Flags")), r.get("MaschioFemmina")))

    gare_json = []
    for combo in combos:
        cat_codice, flag_arma, mf = combo
        arma = FLAG_ARMA.get(flag_arma, str(flag_arma))
        genere = GENERE_NUM.get(mf, mf)
        categoria_nome = categoria_eta_nome(cat_codice)
        e_squadre = combo in incontri_combos

        flg_arma_attr = {"Fioretto": "FlgFioretto", "Spada": "FlgSpada", "Sciabola": "FlgSciabola"}.get(arma)

        # -------- iscritti --------
        iscritti_json = []
        idx_by_numfis = {}
        for r in partecipanti_rows:
            if flg_arma_attr and not _bool(r.get(flg_arma_attr)):
                continue
            riga_cat = _int(r.get("CatAtleti"))
            if riga_cat is not None and riga_cat != cat_codice:
                continue
            riga_mf = r.get("MF")
            if riga_mf is not None:
                genere_riga = "Femminile" if _bool(riga_mf) else "Maschile"
                if genere_riga != genere:
                    continue
            num_fis = r.get("NumFis")
            if not num_fis:
                continue
            atl = dati_atleta(num_fis)
            cod_soc = None
            for g in gironi_rows:
                if (g.get("NumFis") == num_fis and _int(g.get("Categoria")) == cat_codice
                        and _int(g.get("Flags")) == flag_arma and g.get("MaschioFemmina") == mf):
                    cod_soc = g.get("CodSoc")
                    break
            if cod_soc is None:
                for a in assalti_rows:
                    if _int(a.get("Categoria")) == cat_codice and _int(a.get("Flags")) == flag_arma and a.get("MaschioFemmina") == mf:
                        if a.get("NumFis1") == num_fis:
                            cod_soc = a.get("CodSoc1")
                            break
                        if a.get("NumFis2") == num_fis:
                            cod_soc = a.get("CodSoc2")
                            break

            presenza = "confermato" if _bool(r.get("Presenza", "true")) else "assente"
            idx_by_numfis[num_fis] = len(iscritti_json)
            iscritti_json.append({
                "atleta": {
                    "cognome": atl["cognome"],
                    "nome": atl["nome"],
                    "data_nascita": atl["data_nascita"],
                    "genere": atl["genere"] or ("F" if genere == "Femminile" else "M"),
                    "nazionalita": atl["nazionalita"],
                    "licenza": num_fis,
                    "categoria": categoria_nome,
                    "societa_nome": nome_societa(cod_soc),
                },
                "ranking_gara": None,  # calcolato sotto
                "punti_gara": _float(r.get("Ranking")),
                "classifica_finale": _int(r.get("Classifica")),
                "stato": "eliminato",  # aggiornato sotto se qualificato in ED
                "presenza": presenza,
                "_ed_passato": _int(r.get("EDPassato")),
            })

        # seeding: ordina per punti_gara decrescente (migliore=più punti)
        ordine_seed = sorted(
            range(len(iscritti_json)),
            key=lambda i: -(iscritti_json[i]["punti_gara"] or 0),
        )
        for pos, i in enumerate(ordine_seed, start=1):
            iscritti_json[i]["ranking_gara"] = pos

        # -------- turni_gironi --------
        gironi_di_questa_gara = defaultdict(list)
        for g in gironi_rows:
            if (_int(g.get("Categoria")) == cat_codice and _int(g.get("Flags")) == flag_arma
                    and g.get("MaschioFemmina") == mf):
                gironi_di_questa_gara[_int(g.get("Girone"))].append(g)

        gironi_json = []
        for numero_girone_0based in sorted(gironi_di_questa_gara.keys()):
            righe = gironi_di_questa_gara[numero_girone_0based]
            atleti_json = []
            pos_by_numfis = {}
            for r in righe:
                num_fis = r.get("NumFis")
                idx = idx_by_numfis.get(num_fis)
                posizione = _int(r.get("NumAtl"))
                pos_by_numfis[num_fis] = posizione
                vinti = _int(r.get("Vinti"), 0)
                totali = _int(r.get("Assalti"), 0)
                atleti_json.append({
                    "iscritto_idx": idx,
                    "posizione": posizione,
                    "vittorie": vinti,
                    "sconfitte": max(totali - vinti, 0),
                    "stoccate_date": _int(r.get("Stoccate"), 0),
                    "stoccate_ricevute": _int(r.get("Ricevute"), 0),
                    "classifica_girone": _int(r.get("ClasGir")),
                })

            assalti_json = []
            for a in assalti_rows:
                if not (_int(a.get("Categoria")) == cat_codice and _int(a.get("Flags")) == flag_arma
                        and a.get("MaschioFemmina") == mf):
                    continue
                if _int(a.get("EliminDirect"), 0) != 0:
                    continue
                if _int(a.get("Girone")) != numero_girone_0based:
                    continue
                num1, num2 = a.get("NumFis1"), a.get("NumFis2")
                vitt1 = _bool(a.get("Vittoria1"))
                assalti_json.append({
                    "ordine": _int(a.get("Ordine")),
                    "posizione_a": pos_by_numfis.get(num1, _int(a.get("NumAtl1"))),
                    "posizione_b": pos_by_numfis.get(num2, _int(a.get("NumAtl2"))),
                    "punteggio_a": _int(a.get("Stoccate1"), 0),
                    "punteggio_b": _int(a.get("Stoccate2"), 0),
                    "vincitore": "a" if vitt1 else "b",
                    "stato": "completato",
                    "arbitro": nome_arbitro(a.get("Arbitro")),
                })
            assalti_json.sort(key=lambda x: (x["ordine"] is None, x["ordine"]))

            gironi_json.append({
                "numero": numero_girone_0based + 1,  # convenzione touche: 1-based
                "atleti": atleti_json,
                "assalti": assalti_json,
            })

        turni_gironi_json = [{"numero": 1, "gironi": gironi_json}] if gironi_json else []

        # -------- turni_diretta --------
        assalti_ed = [
            a for a in assalti_rows
            if _int(a.get("Categoria")) == cat_codice and _int(a.get("Flags")) == flag_arma
            and a.get("MaschioFemmina") == mf and _int(a.get("EliminDirect"), 0) != 0
        ]
        taglie = sorted({_int(a.get("EliminDirect")) for a in assalti_ed}, reverse=True)
        round_di_taglia = {taglia: i + 1 for i, taglia in enumerate(taglie)}

        assalti_diretta_json = []
        for a in assalti_ed:
            num1, num2 = a.get("NumFis1"), a.get("NumFis2")
            idx1 = idx_by_numfis.get(num1)
            idx2 = idx_by_numfis.get(num2)
            vitt1 = _bool(a.get("Vittoria1"))
            data_ora = a.get("Data")
            ora = None
            if data_ora and "T" in data_ora:
                ora = data_ora.split("T")[1][:5]
            assalti_diretta_json.append({
                "iscritto_a_idx": idx1,
                "iscritto_b_idx": idx2,
                "posizione_tabellone": _int(a.get("Ordine")),
                "round_numero": round_di_taglia.get(_int(a.get("EliminDirect"))),
                "punteggio_a": _int(a.get("Stoccate1"), 0),
                "punteggio_b": _int(a.get("Stoccate2"), 0),
                "stato": "completato",
                "pedana": a.get("Pedana"),
                "ora_appello": ora,
                "vincitore_idx": idx1 if vitt1 else idx2,
                "arbitro": nome_arbitro(a.get("Arbitro")),
            })
            if idx1 is not None and vitt1:
                iscritti_json[idx1]["stato"] = "qualificato"
            if idx2 is not None and not vitt1:
                pass
            if idx1 is not None:
                iscritti_json[idx1]["stato"] = "qualificato"
            if idx2 is not None:
                iscritti_json[idx2]["stato"] = "qualificato"

        turni_diretta_json = []
        if assalti_diretta_json:
            turni_diretta_json.append({
                "numero": 1,
                "repechage_attivo": 1 if assalti_ripesc_rows else 0,
                "assalti": assalti_diretta_json,
            })

        # ripescaggio: fase aggiuntiva semplificata, mai unita al tabellone principale
        assalti_ripesc_combo = [
            a for a in assalti_ripesc_rows
            if _int(a.get("Categoria")) == cat_codice and _int(a.get("Flags")) == flag_arma
            and a.get("MaschioFemmina") == mf
        ]
        if assalti_ripesc_combo:
            ripesc_json = []
            for a in assalti_ripesc_combo:
                num1, num2 = a.get("NumFis1"), a.get("NumFis2")
                vitt1 = _bool(a.get("Vittoria1"))
                ripesc_json.append({
                    "iscritto_a_idx": idx_by_numfis.get(num1),
                    "iscritto_b_idx": idx_by_numfis.get(num2),
                    "posizione_tabellone": _int(a.get("Ordine")),
                    "round_numero": 1,
                    "punteggio_a": _int(a.get("Stoccate1"), 0),
                    "punteggio_b": _int(a.get("Stoccate2"), 0),
                    "stato": "completato",
                    "pedana": a.get("Pedana"),
                    "ora_appello": None,
                    "vincitore_idx": idx_by_numfis.get(num1) if vitt1 else idx_by_numfis.get(num2),
                    "arbitro": nome_arbitro(a.get("Arbitro")),
                })
            turni_diretta_json.append({
                "numero": 2,
                "repechage_attivo": 1,
                "assalti": ripesc_json,
            })

        for i in iscritti_json:
            i.pop("_ed_passato", None)

        formula = formula_by_combo.get(combo, {})
        formula_testo = ""
        if formula:
            formula_testo = (
                f"Turno gironi — {formula.get('StoccateGironi', '?')} stoccate, "
                f"tempo max. {formula.get('TempoGironi', '?')} min. "
                f"Passano all'E.D. n. {formula.get('Passanti', '?')} atleti. "
                f"Tabellone E.D. a {formula.get('StoccateED', '?')} stoccate."
            )

        gare_json.append({
            "arma": arma,
            "genere": genere,
            "tipologia": "a squadre" if e_squadre else "individuale",
            "categoria": categoria_nome,
            "data_inizio": (gara_evento.get("PrimaData") or "").split("T")[0],
            "data_fine": (gara_evento.get("UltimaData") or "").split("T")[0],
            "formula": formula_testo,
            "stato": "conclusa",
            "note": (
                "Gara a squadre: struttura non ricostruita in dettaglio "
                "(vedi limiti in fisdotnet.py); gli assalti individuali "
                "riportati sono comunque corretti." if e_squadre else ""
            ),
            "iscritti": iscritti_json,
            "turni_gironi": turni_gironi_json,
            "turni_diretta": turni_diretta_json,
            "formula_classifica": None,
            "formula_strutturata": None,
            "classifiche_turno": [],
            "config_squadre": None,
            "frazioni_incontro": [],
            "formazioni_squadra": [],
            "sostituzioni_squadra": [],
        })

    dati = {
        "formato": "touche-export",
        "versione": 2,
        "tipo": "evento",
        "esportato_il": datetime.now().isoformat(),
        "evento": {
            "titolo": evento_titolo,
            "data_inizio": (gara_evento.get("PrimaData") or "").split("T")[0],
            "data_fine": (gara_evento.get("UltimaData") or "").split("T")[0],
            "luogo": evento_titolo,
            "indirizzo": gara_evento.get("IndirizzoGara", "") or "",
            "autorita": circuito_titolo,
            "organizzatore": circuito_titolo,
            "tipologia": "",
            "pedane": "",
            "note": "Generato da fisdotnet.py.",
        },
        "circuito": {
            "titolo": circuito_titolo,
            "stagione": "",
            "descrizione": "",
        },
        "organizzatore": {
            "nome": circuito_titolo,
            "slug": re.sub(r"[^a-z0-9]+", "-", circuito_titolo.lower()).strip("-"),
            "descrizione": "",
            "paese": "ITA",
        },
        "gare": gare_json,
    }
    return dati


def converti_fisdotnet_a_touche(path_xml, cartella_out):
    dati = fisdotnet_to_touche(path_xml)
    os.makedirs(cartella_out, exist_ok=True)
    base = os.path.splitext(os.path.basename(path_xml))[0]
    percorso = os.path.join(cartella_out, f"{base}_touche-export.json")
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    return [percorso]


# ----------------------------------------------------------------------
# touche-export -> FisDotNet
# ----------------------------------------------------------------------

def _esc(v):
    return xml_escape(str(v)) if v is not None else ""


def _riga(tag, campi, indent="  "):
    parti = [f"{indent}<{tag}>"]
    for nome, valore in campi:
        if valore is None:
            continue
        parti.append(f"{indent}  <{nome}>{_esc(valore)}</{nome}>")
    parti.append(f"{indent}</{tag}>")
    return "\n".join(parti)


def touche_to_fisdotnet(dati, output_path):
    evento = dati.get("evento", {})
    circuito = dati.get("circuito", {})
    gare = dati.get("gare", [])

    righe = []

    # -------- Tornei (1 riga: il circuito) --------
    circuito_titolo = (circuito.get("titolo") or "").strip() or (evento.get("titolo") or "")
    righe.append(_riga("Tornei", [
        ("CodTorneo", 1),
        ("Descrizione", circuito_titolo),
        ("CategInsieme", "true"),
    ]))

    # -------- Gare (1 riga: l'evento) --------
    prima_data = evento.get("data_inizio", "") or ""
    ultima_data = evento.get("data_fine", "") or prima_data
    righe.append(_riga("Gare", [
        ("IdGara", 1),
        ("Torneo", 1),
        ("Livello", 2),
        ("LuogoGara", evento.get("titolo", "")),
        ("PrimaData", f"{prima_data}T00:00:00" if prima_data else None),
        ("UltimaData", f"{ultima_data}T00:00:00" if ultima_data else None),
        ("IndirizzoGara", evento.get("indirizzo", "")),
        ("MgtArbitri", "true"),
        ("MgtAssess", "false"),
        ("MgtPedOra", "false"),
        ("MgtIncontro", "false"),
    ]))

    tesserati_scritti = set()
    societa_scritte = set()
    next_cod_soc = {}
    next_cod_soc_counter = [1]

    def cod_soc_per(nome_societa):
        nome_societa = nome_societa or "SVINCOLATO"
        if nome_societa not in next_cod_soc:
            next_cod_soc[nome_societa] = next_cod_soc_counter[0]
            next_cod_soc_counter[0] += 1
            societa_scritte.add(nome_societa)
        return next_cod_soc[nome_societa]

    def num_fis_per(atleta):
        licenza = atleta.get("licenza")
        if licenza:
            return str(licenza)
        # nessuna licenza nota: genera un identificativo posizionale stabile
        chiave = f"{atleta.get('cognome','')}|{atleta.get('nome','')}|{atleta.get('data_nascita','')}"
        return str(abs(hash(chiave)) % 900000 + 100000)

    for gara in gare:
        arma = gara.get("arma", "")
        flag_arma = ARMA_FLAG.get(arma)
        genere = gara.get("genere", "")
        mf = GENERE_NUM_INV.get(genere, "0")
        cat_codice = categoria_eta_codice(gara.get("categoria")) or 0

        idx_by_iscritto = {}
        for idx, iscritto in enumerate(gara.get("iscritti", [])):
            atl = iscritto.get("atleta", {})
            num_fis = num_fis_per(atl)
            idx_by_iscritto[idx] = num_fis
            cod_soc = cod_soc_per(atl.get("societa_nome"))

            if num_fis not in tesserati_scritti:
                tesserati_scritti.add(num_fis)
                data_nasc_iso = None
                dn = atl.get("data_nascita")
                if dn:
                    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", dn)
                    if m:
                        gg, mm, aa = m.groups()
                        aaaa = aa if len(aa) == 4 else str(2000 + int(aa) if int(aa) < 50 else 1900 + int(aa))
                        data_nasc_iso = f"{aaaa}-{int(mm):02d}-{int(gg):02d}T00:00:00"
                righe.append(_riga("Tesserati", [
                    ("NumFIS", num_fis),
                    ("CodSoc", cod_soc),
                    ("Cognome", atl.get("cognome", "")),
                    ("Nome", atl.get("nome", "")),
                    ("MaschioFemmina", GENERE_BOOL_INV.get(
                        "Femminile" if atl.get("genere") == "F" else "Maschile")),
                    ("DataNascita", data_nasc_iso),
                    ("Nazionalità", atl.get("nazionalita", "ITA")),
                    ("CatAtleti", cat_codice),
                ]))

            righe.append(_riga("PartecipantiGara", [
                ("IdGara", 1),
                ("NumFis", num_fis),
                ("Flags", flag_arma),
                ("FlgDirettore", "false"),
                ("FlgComputerista", "false"),
                ("FlgArbitro", "false"),
                ("FlgFioretto", "true" if arma == "Fioretto" else "false"),
                ("FlgSpada", "true" if arma == "Spada" else "false"),
                ("FlgSciabola", "true" if arma == "Sciabola" else "false"),
                ("Punteggio", iscritto.get("punti_gara", 0) or 0),
                ("Ranking", iscritto.get("punti_gara", 0) or 0),
                ("Presenza", "true" if iscritto.get("presenza") != "assente" else "false"),
                ("CatAtleti", cat_codice),
                ("Classifica", iscritto.get("classifica_finale")),
                ("MF", GENERE_BOOL_INV.get("Femminile" if genere == "Femminile" else "Maschile")),
            ]))

        for nome_soc, cod in list(next_cod_soc.items()):
            if nome_soc in societa_scritte:
                societa_scritte.discard(nome_soc)
                righe.append(_riga("Societa", [
                    ("CodSoc", cod),
                    ("Sigla", (nome_soc or "")[:10]),
                    ("Denominazione", nome_soc),
                    ("Categoria", 0),
                ]))

        # -------- FormulaGara --------
        righe.append(_riga("FormulaGara", [
            ("IdGara", 1),
            ("Torneo", 1),
            ("Flags", flag_arma),
            ("MaschioFemmina", mf),
            ("CatAtleti", cat_codice),
            ("Gironi", 1),
        ]))

        # -------- Gironi + Assalti (fase a gironi) --------
        for turno in gara.get("turni_gironi", []):
            for girone in turno.get("gironi", []):
                numero_0based = (girone.get("numero") or 1) - 1
                for a in girone.get("atleti", []):
                    idx = a.get("iscritto_idx")
                    num_fis = idx_by_iscritto.get(idx)
                    if num_fis is None:
                        continue
                    iscritto = gara["iscritti"][idx]
                    cod_soc = cod_soc_per(iscritto["atleta"].get("societa_nome"))
                    righe.append(_riga("Gironi", [
                        ("Torneo", 1),
                        ("Gara", 1),
                        ("Categoria", cat_codice),
                        ("Flags", flag_arma),
                        ("MaschioFemmina", mf),
                        ("Girone", numero_0based),
                        ("NumAtl", a.get("posizione")),
                        ("NumFis", num_fis),
                        ("CodSoc", cod_soc),
                        ("Assalti", (a.get("vittorie", 0) or 0) + (a.get("sconfitte", 0) or 0)),
                        ("Vinti", a.get("vittorie", 0)),
                        ("Stoccate", a.get("stoccate_date", 0)),
                        ("Ricevute", a.get("stoccate_ricevute", 0)),
                        ("Punteggio", 0),
                        ("ClasGir", a.get("classifica_girone")),
                    ]))

                pos_to_idx = {a["posizione"]: a["iscritto_idx"] for a in girone.get("atleti", [])}
                for m in girone.get("assalti", []):
                    idx_a = pos_to_idx.get(m.get("posizione_a"))
                    idx_b = pos_to_idx.get(m.get("posizione_b"))
                    num1 = idx_by_iscritto.get(idx_a)
                    num2 = idx_by_iscritto.get(idx_b)
                    if num1 is None or num2 is None:
                        continue
                    vinc = m.get("vincitore")
                    righe.append(_riga("Assalti", [
                        ("Torneo", 1),
                        ("Gara", 1),
                        ("Categoria", cat_codice),
                        ("Flags", flag_arma),
                        ("MaschioFemmina", mf),
                        ("Fase", 0),
                        ("EliminDirect", 0),
                        ("Girone", numero_0based),
                        ("Ordine", m.get("ordine")),
                        ("NumAtl1", m.get("posizione_a")),
                        ("NumAtl2", m.get("posizione_b")),
                        ("NumFis1", num1),
                        ("NumFis2", num2),
                        ("Stoccate1", m.get("punteggio_a", 0)),
                        ("Stoccate2", m.get("punteggio_b", 0)),
                        ("Vittoria1", "true" if vinc == "a" else "false"),
                        ("Vittoria2", "true" if vinc == "b" else "false"),
                    ]))

        # -------- Assalti (fase ad eliminazione diretta) --------
        for turno in gara.get("turni_diretta", []):
            if turno.get("repechage_attivo") and turno.get("numero", 1) != 1:
                continue  # il ripescaggio va in AssaltiRipesc, gestito sotto
            assalti = turno.get("assalti", [])
            if not assalti:
                continue
            rounds = sorted(set(a.get("round_numero") for a in assalti if a.get("round_numero")))
            n_round = len(rounds)
            taglia_iniziale = 2 ** n_round if n_round else 2
            taglia_per_round = {rn: taglia_iniziale // (2 ** (rn - 1)) for rn in rounds}
            for a in assalti:
                num1 = idx_by_iscritto.get(a.get("iscritto_a_idx"))
                num2 = idx_by_iscritto.get(a.get("iscritto_b_idx"))
                if num1 is None or num2 is None:
                    continue
                taglia = taglia_per_round.get(a.get("round_numero"), 2)
                vinc_idx = a.get("vincitore_idx")
                ora = a.get("ora_appello")
                data_completa = None
                if ora:
                    gg = gara.get("data_inizio", "") or ""
                    data_completa = f"{gg}T{ora}:00" if gg else None
                righe.append(_riga("Assalti", [
                    ("Torneo", 1),
                    ("Gara", 1),
                    ("Categoria", cat_codice),
                    ("Flags", flag_arma),
                    ("MaschioFemmina", mf),
                    ("Fase", 0),
                    ("EliminDirect", taglia),
                    ("Girone", 0),
                    ("Ordine", a.get("posizione_tabellone")),
                    ("NumAtl1", a.get("posizione_tabellone")),
                    ("NumAtl2", a.get("posizione_tabellone")),
                    ("NumFis1", num1),
                    ("NumFis2", num2),
                    ("Stoccate1", a.get("punteggio_a", 0)),
                    ("Stoccate2", a.get("punteggio_b", 0)),
                    ("Vittoria1", "true" if a.get("iscritto_a_idx") == vinc_idx else "false"),
                    ("Vittoria2", "true" if a.get("iscritto_b_idx") == vinc_idx else "false"),
                    ("Pedana", a.get("pedana")),
                    ("Data", data_completa),
                ]))

        for turno in gara.get("turni_diretta", []):
            if not turno.get("repechage_attivo") or turno.get("numero", 1) == 1:
                continue
            for a in turno.get("assalti", []):
                num1 = idx_by_iscritto.get(a.get("iscritto_a_idx"))
                num2 = idx_by_iscritto.get(a.get("iscritto_b_idx"))
                if num1 is None or num2 is None:
                    continue
                vinc_idx = a.get("vincitore_idx")
                righe.append(_riga("AssaltiRipesc", [
                    ("Torneo", 1),
                    ("Gara", 1),
                    ("Categoria", cat_codice),
                    ("Flags", flag_arma),
                    ("MaschioFemmina", mf),
                    ("Fase", 0),
                    ("EliminDirect", 2),
                    ("Girone", 0),
                    ("Ordine", a.get("posizione_tabellone")),
                    ("NumFis1", num1),
                    ("NumFis2", num2),
                    ("Stoccate1", a.get("punteggio_a", 0)),
                    ("Stoccate2", a.get("punteggio_b", 0)),
                    ("Vittoria1", "true" if a.get("iscritto_a_idx") == vinc_idx else "false"),
                    ("Vittoria2", "true" if a.get("iscritto_b_idx") == vinc_idx else "false"),
                ]))

    corpo_dati = "\n".join(righe)

    template_path = _percorso_risorsa("assets", "dsLoadSave_schema_template.xml")
    with open(template_path, "r", encoding="utf-8") as f:
        intestazione = f.read().rstrip("\n").rstrip("\r")

    contenuto = intestazione + "\r\n" + corpo_dati.replace("\n", "\r\n") + "\r\n</dsLoadSave>\r\n"

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write(contenuto)


def _percorso_risorsa(*parti):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parti)


def converti_touche_a_fisdotnet(path_json, cartella_out):
    with open(path_json, "r", encoding="utf-8") as f:
        dati = json.load(f)
    os.makedirs(cartella_out, exist_ok=True)
    base = os.path.splitext(os.path.basename(path_json))[0]
    percorso = os.path.join(cartella_out, f"{base}_FisDotNet.XML")
    touche_to_fisdotnet(dati, percorso)
    return [percorso]


# ----------------------------------------------------------------------
# Composizione di più export touche di singola gara in un unico evento
# ----------------------------------------------------------------------

def combina_gare_in_evento(percorsi_json):
    """Prende una lista di file touche-export (ciascuno con tipo="gara",
    UNA gara in "gare") e li unisce in un unico evento con più gare.

    Regola per circuito/evento: se i file hanno un "circuito" valorizzato
    lo si usa (dando priorità al primo file che lo definisce); altrimenti
    si usa il titolo dell'evento (evento.titolo) del primo file, secondo
    la stessa regola "torneo assente -> titolo evento" richiesta per la
    conversione FisDotNet."""
    if not percorsi_json:
        raise ValueError("Nessun file fornito da comporre.")

    dati_letti = []
    for p in percorsi_json:
        with open(p, "r", encoding="utf-8") as f:
            dati_letti.append(json.load(f))

    primo = dati_letti[0]
    evento = dict(primo.get("evento", {}))
    circuito = dict(primo.get("circuito", {}))
    organizzatore = dict(primo.get("organizzatore", {}))

    if not (circuito.get("titolo") or "").strip():
        circuito["titolo"] = evento.get("titolo", "")

    gare_combinate = []
    for d in dati_letti:
        gare_combinate.extend(d.get("gare", []))

    evento_combinato = {
        "formato": "touche-export",
        "versione": primo.get("versione", 2),
        "tipo": "evento",
        "esportato_il": datetime.now().isoformat(),
        "evento": evento,
        "circuito": circuito,
        "organizzatore": organizzatore,
        "gare": gare_combinate,
    }
    return evento_combinato


def converti_componi_evento(percorsi_json, cartella_out):
    dati = combina_gare_in_evento(percorsi_json)
    os.makedirs(cartella_out, exist_ok=True)
    nome_base = re.sub(r"[^a-z0-9]+", "-", (dati["evento"].get("titolo") or "evento").lower()).strip("-") or "evento"
    percorso = os.path.join(cartella_out, f"{nome_base}_touche-export.json")
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    return [percorso]


# ----------------------------------------------------------------------
# Scorciatoia: da un evento FisDotNet esporta tutte le gare in altrettanti
# file FIE XML (riusa touche2fie.py dopo la conversione intermedia)
# ----------------------------------------------------------------------

def converti_fisdotnet_a_fie(path_xml, cartella_out):
    dati = fisdotnet_to_touche(path_xml)
    os.makedirs(cartella_out, exist_ok=True)
    generati = []
    for indice_gara, gara in enumerate(dati.get("gare", [])):
        xml_str = fwd.costruisci_xml_gara(dati, gara, indice_gara)
        nome_file = fwd.nome_file_output(dati, gara, indice_gara)
        percorso = os.path.join(cartella_out, nome_file)
        with open(percorso, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write(xml_str)
        generati.append(percorso)
    return generati


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Uso:\n"
            "  python3 fisdotnet.py in input.xml cartella_output       (FisDotNet -> touche)\n"
            "  python3 fisdotnet.py out input.json cartella_output     (touche -> FisDotNet)\n"
            "  python3 fisdotnet.py fie input.xml cartella_output      (FisDotNet -> FIE, tutte le gare)\n"
            "  python3 fisdotnet.py componi cartella_output f1.json f2.json ...\n",
            file=sys.stderr,
        )
        sys.exit(1)

    comando = sys.argv[1]
    if comando == "in":
        files = converti_fisdotnet_a_touche(sys.argv[2], sys.argv[3])
    elif comando == "out":
        files = converti_touche_a_fisdotnet(sys.argv[2], sys.argv[3])
    elif comando == "fie":
        files = converti_fisdotnet_a_fie(sys.argv[2], sys.argv[3])
    elif comando == "componi":
        files = converti_componi_evento(sys.argv[3:], sys.argv[2])
    else:
        print("Comando sconosciuto:", comando, file=sys.stderr)
        sys.exit(1)

    for f in files:
        print(f"Generato: {f}")
