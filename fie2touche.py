#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fie2touche.py
=============
Convertitore INVERSO: da XML FIE (CompetitionIndividuelle) al formato
"touche-export" (JSON).

Uso:
    python3 fie2touche.py input.xml [cartella_output]

----------------------------------------------------------------------
IMPORTANTE: conversione "best effort", non simmetrica al 100%
----------------------------------------------------------------------
Il formato XML FIE è un formato di **pubblicazione risultati**: non
contiene tutte le informazioni gestionali presenti nel formato
touche-export sorgente (che è invece un formato di **esportazione
gestionale completa**). Alcuni dati NON sono quindi recuperabili
dall'XML e vengono impostati a valori nulli/di default, con un elenco
completo qui sotto. Se converti A->B->A (JSON->XML->JSON) il risultato
finale NON sarà identico all'originale: è una limitazione strutturale
del formato XML di destinazione, non un bug del convertitore.

Dati NON presenti nell'XML FIE (quindi non ricostruibili):
  - indirizzo dell'impianto, pedane disponibili, direttori di gara,
    delegato GSA, commissione medica, fuso orario (evento.*)
  - "punti_gara"/"punti_ranking" e "regione_societa"/"presenza" degli
    atleti (iscritti[].*, atleta.*)
  - percentuali/parametri esatti della formula di gara (numero
    stoccate, tempo, modalità di qualificazione, ecc.): viene
    ricostruita una formula sintetica plausibile a partire dai dati
    presenti (numero di gironi, dimensione tabelloni), NON quella
    originale
  - mancinismo ("Lateralite") e codice di lega ("Ligue") non hanno
    equivalente nel formato touche-export e vengono scartati
  - "ranking_gara"/"punti_gara" originali: nell'XML è presente solo il
    rango ordinale relativo alla gara (RangInitial), che viene quindi
    riportato in "ranking_gara" come valore APPROSSIMATO (non è il
    ranking/punteggio di circuito originale)
  - orari esatti dei singoli assalti (solo se presente l'attributo
    Date sul Match)
  - gestione a squadre (config_squadre, formazioni, sostituzioni):
    non gestita da questo convertitore

Mappatura principale (simmetrica a touche2fie.py):
  Arme E/F/S            -> gara.arma Spada/Fioretto/Sciabola
  Sexe X/M/F            -> gara.genere Misto/Maschile/Femminile
  Domaine I/T           -> gara.tipologia individuale/a squadre
  Categorie             -> gara.categoria (mappatura nota; vuoto->"Open")
  Date, Annee           -> evento.data_inizio/data_fine, circuito.stagione
  TitreLong             -> evento.titolo
  Organisateur          -> evento.autorita e organizzatore.nome
  Tireur (Nom,Prenom,...) -> atleta.cognome/nome/... in iscritti[]
  Classement             -> iscritti[].classifica_finale
  TourDePoules/Poule/Match -> turni_gironi
  PhaseDeTableaux/SuiteDeTableaux/Tableau/Match -> turni_diretta
"""

import json
import os
import re
import sys
from datetime import datetime
from xml.etree import ElementTree as ET

# Riusa le tabelle di mappatura del convertitore diretto, invertendole,
# per garantire coerenza fra i due sensi di conversione.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import touche2fie as fwd  # noqa: E402


def inverti_mappa(mappa, default):
    """Da {chiave_normalizzata: codice} costruisce {codice: chiave_leggibile}.
    In caso di più chiavi con lo stesso codice, mantiene la prima
    incontrata (le mappe dirette sono definite in ordine "preferito")."""
    inversa = {}
    for chiave, codice in mappa.items():
        if codice not in inversa:
            inversa[codice] = chiave
    inversa.setdefault(default, default)
    return inversa


ARMA_INV = {"E": "Spada", "F": "Fioretto", "S": "Sciabola"}
GENERE_INV = {"X": "Misto", "M": "Maschile", "F": "Femminile"}
DOMAINE_INV = {"I": "individuale", "T": "a squadre"}
CATEGORIA_INV = inverti_mappa(fwd.CATEGORIA_MAP, "")


def cap(s):
    """Capitalizza in modo leggibile mantenendo acronimi corti (FIE ecc.)."""
    if not s:
        return s
    return " ".join(w.capitalize() for w in s.split())


def convert_date_naissance_back(d):
    """DD.MM.AAAA -> DD/MM/AA"""
    if not d:
        return ""
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", d.strip())
    if not m:
        return d
    gg, mm, aaaa = m.groups()
    return f"{int(gg):02d}/{int(mm):02d}/{aaaa[-2:]}"


def convert_date_back(d):
    """DD.MM.AAAA -> AAAA-MM-DD"""
    if not d:
        return ""
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", d.strip())
    if not m:
        return d
    gg, mm, aaaa = m.groups()
    return f"{aaaa}-{int(mm):02d}-{int(gg):02d}"


def gi(elem, nome, default=None, tipo=None):
    """Legge un attributo XML con cast opzionale."""
    if elem is None:
        return default
    v = elem.get(nome)
    if v is None or v == "":
        return default
    if tipo is int:
        try:
            return int(v)
        except ValueError:
            return default
    if tipo is float:
        try:
            return float(v)
        except ValueError:
            return default
    return v


# ----------------------------------------------------------------------
def costruisci_json(xml_root):
    ns_strip = lambda tag: tag.split("}")[-1]  # tollera eventuali namespace
    comp = xml_root
    if ns_strip(comp.tag) != "CompetitionIndividuelle":
        # potrebbe essere un wrapper: cerca il primo discendente giusto
        trovato = None
        for el in comp.iter():
            if ns_strip(el.tag) == "CompetitionIndividuelle":
                trovato = el
                break
        if trovato is not None:
            comp = trovato

    # -------- Tireurs --------
    tireurs_el = comp.find("Tireurs")
    tireurs = {}
    ordine_tireurs = []
    if tireurs_el is not None:
        for t in tireurs_el.findall("Tireur"):
            tid = gi(t, "ID", tipo=int)
            tireurs[tid] = {
                "id": tid,
                "cognome": gi(t, "Nom", ""),
                "nome": gi(t, "Prenom", ""),
                "data_nascita": convert_date_naissance_back(gi(t, "DateNaissance", "")),
                "genere": gi(t, "Sexe", ""),
                "nazionalita": gi(t, "Nation", ""),
                "club": gi(t, "Club", ""),
                "licenza": gi(t, "Licence", ""),
                "classifica_finale": gi(t, "Classement", tipo=int),
                "statut": gi(t, "Statut", "N"),
            }
            ordine_tireurs.append(tid)

    # -------- Arbitres --------
    arbitres_el = comp.find("Arbitres")
    arbitri = {}
    if arbitres_el is not None:
        for a in arbitres_el.findall("Arbitre"):
            aid = gi(a, "ID", tipo=int)
            arbitri[aid] = {
                "cognome": gi(a, "Nom", ""),
                "nome": gi(a, "Prenom", ""),
            }

    # assegna un indice progressivo (0..N-1) a ciascun Tireur: sarà
    # l'iscritto_idx nella lista "iscritti" del touche-export, nello
    # stesso ordine in cui compaiono nell'XML
    id_to_idx = {tid: i for i, tid in enumerate(ordine_tireurs)}

    # -------- attributi di testata --------
    arma = ARMA_INV.get(gi(comp, "Arme", ""), gi(comp, "Arme", ""))
    genere = GENERE_INV.get(gi(comp, "Sexe", ""), gi(comp, "Sexe", ""))
    dominio = DOMAINE_INV.get(gi(comp, "Domaine", "I"), "individuale")
    categoria_codice = gi(comp, "Categorie", "")
    categoria = CATEGORIA_INV.get(categoria_codice, categoria_codice) or "Open"
    data_gara = convert_date_back(gi(comp, "Date", ""))
    titolo = gi(comp, "TitreLong", "")
    organisateur = gi(comp, "Organisateur", "")
    annee = gi(comp, "Annee", "")
    federation = gi(comp, "Federation", "")

    # -------- ranking_gara approssimato + stato qualificazione --------
    # raccolto scandendo le liste <Tireur REF=.. RangInitial=.. /> delle
    # fasi; se un Tireur compare nella lista della PhaseDeTableaux è
    # considerato "qualificato", altrimenti "eliminato"
    rang_iniziale_by_ref = {}
    qualificati_ref = set()

    fasi = comp.find("Phases")
    turni_gironi_json = []
    turni_diretta_json = []

    if fasi is not None:
        for tp in fasi.findall("TourDePoules"):
            for tref in tp.findall("Tireur"):
                ref = gi(tref, "REF", tipo=int)
                ri = gi(tref, "RangInitial", tipo=int)
                if ref is not None and ri is not None:
                    rang_iniziale_by_ref[ref] = ri

            gironi_json = []
            for poule in tp.findall("Poule"):
                pos_to_ref = {}
                atleti_json = []
                for tref in poule.findall("Tireur"):
                    ref = gi(tref, "REF", tipo=int)
                    pos = gi(tref, "NoDansLaPoule", tipo=int)
                    pos_to_ref[pos] = ref
                    nb_v = gi(tref, "NbVictoires", 0, tipo=int)
                    nb_m = gi(tref, "NbMatches", 0, tipo=int)
                    td = gi(tref, "TD", 0, tipo=int)
                    tr = gi(tref, "TR", 0, tipo=int)
                    idx = id_to_idx.get(ref)
                    atleti_json.append({
                        "iscritto_idx": idx,
                        "posizione": pos,
                        "vittorie": nb_v,
                        "sconfitte": max(nb_m - nb_v, 0),
                        "stoccate_date": td,
                        "stoccate_ricevute": tr,
                        "classifica_girone": None,  # ricalcolabile, non riportato qui
                    })
                assalti_json = []
                for m in poule.findall("Match"):
                    match_id = gi(m, "ID", tipo=int)
                    figli = m.findall("Tireur")
                    if len(figli) != 2:
                        continue
                    t_a, t_b = figli[0], figli[1]
                    ref_a = gi(t_a, "REF", tipo=int)
                    ref_b = gi(t_b, "REF", tipo=int)
                    score_a = gi(t_a, "Score", 0, tipo=int)
                    score_b = gi(t_b, "Score", 0, tipo=int)
                    stat_a = gi(t_a, "Statut", "")
                    stat_b = gi(t_b, "Statut", "")
                    if stat_a == "V":
                        vincitore = "a"
                    elif stat_b == "V":
                        vincitore = "b"
                    else:
                        vincitore = None
                    stato = "completato"
                    if stat_a == "A" or stat_b == "A":
                        stato = "ritiro"
                    elif stat_a == "E" or stat_b == "E":
                        stato = "escluso"
                    pos_a = next((p for p, r in pos_to_ref.items() if r == ref_a), None)
                    pos_b = next((p for p, r in pos_to_ref.items() if r == ref_b), None)
                    assalti_json.append({
                        "ordine": match_id,
                        "posizione_a": pos_a,
                        "posizione_b": pos_b,
                        "punteggio_a": score_a,
                        "punteggio_b": score_b,
                        "vincitore": vincitore,
                        "stato": stato,
                        "arbitro": None,
                    })
                gironi_json.append({
                    "numero": gi(poule, "ID", tipo=int),
                    "atleti": atleti_json,
                    "assalti": assalti_json,
                })
            turni_gironi_json.append({
                "numero": gi(tp, "ID", tipo=int),
                "gironi": gironi_json,
            })

        for pdt in fasi.findall("PhaseDeTableaux"):
            for tref in pdt.findall("Tireur"):
                ref = gi(tref, "REF", tipo=int)
                if ref is not None:
                    qualificati_ref.add(ref)

            assalti_json = []
            suite = pdt.find("SuiteDeTableaux")
            round_numero = 0
            n_round_totali = 0
            tableaux = suite.findall("Tableau") if suite is not None else []
            n_round_totali = len(tableaux)
            for i, tab in enumerate(tableaux):
                round_numero = i + 1
                for m in tab.findall("Match"):
                    match_id = gi(m, "ID", tipo=int)
                    pedana = gi(m, "Piste", None)
                    ora = gi(m, "Date", None)
                    arb_el = m.find("Arbitre")
                    arbitro = None
                    if arb_el is not None:
                        aref = gi(arb_el, "REF", tipo=int)
                        info = arbitri.get(aref) or tireurs.get(aref)
                        if info:
                            arbitro = {"cognome": info["cognome"], "nome": info["nome"]}
                    figli = m.findall("Tireur")
                    if len(figli) != 2:
                        continue
                    t_a, t_b = figli[0], figli[1]
                    ref_a = gi(t_a, "REF", tipo=int)
                    ref_b = gi(t_b, "REF", tipo=int)
                    score_a = gi(t_a, "Score", 0, tipo=int)
                    score_b = gi(t_b, "Score", 0, tipo=int)
                    stat_a = gi(t_a, "Statut", "")
                    stat_b = gi(t_b, "Statut", "")
                    idx_a = id_to_idx.get(ref_a)
                    idx_b = id_to_idx.get(ref_b)
                    if stat_a == "V":
                        vincitore_idx = idx_a
                    elif stat_b == "V":
                        vincitore_idx = idx_b
                    else:
                        vincitore_idx = None
                    stato = "completato"
                    if stat_a == "A" or stat_b == "A":
                        stato = "ritiro"
                    elif stat_a == "E" or stat_b == "E":
                        stato = "escluso"
                    assalti_json.append({
                        "_id": match_id,
                        "iscritto_a_idx": idx_a,
                        "iscritto_b_idx": idx_b,
                        "posizione_tabellone": match_id,
                        "round_numero": round_numero,
                        "punteggio_a": score_a if stato == "completato" else (score_a or None),
                        "punteggio_b": score_b if stato == "completato" else (score_b or None),
                        "stato": stato,
                        "pedana": pedana,
                        "ora_appello": ora,
                        "vincitore_idx": vincitore_idx,
                        "arbitro": arbitro,
                    })
            turni_diretta_json.append({
                "numero": gi(pdt, "ID", tipo=int),
                "repechage_attivo": 0,
                "assalti": assalti_json,
                "_n_round": n_round_totali,
            })

    # -------- iscritti --------
    iscritti = []
    for tid in ordine_tireurs:
        t = tireurs[tid]
        idx = id_to_idx[tid]
        stato_iscritto = "qualificato" if (tid in qualificati_ref or not turni_diretta_json) else "eliminato"
        iscritti.append({
            "atleta": {
                "cognome": t["cognome"],
                "nome": t["nome"],
                "data_nascita": t["data_nascita"],
                "genere": t["genere"],
                "nazionalita": t["nazionalita"],
                "societa_nome": t["club"],
                "licenza": t["licenza"],
                # non recuperabili dall'XML:
                "ranking": None,
                "punti_ranking": None,
            },
            "ranking_gara": rang_iniziale_by_ref.get(tid),
            "punti_gara": None,
            "classifica_finale": t["classifica_finale"],
            "stato": stato_iscritto,
            "presenza": "confermato",
        })

    # rimuove il campo di servizio "_n_round" prima di esportare
    for tt in turni_diretta_json:
        tt.pop("_n_round", None)

    formula_testo = ""
    if turni_gironi_json:
        n_g = sum(len(t["gironi"]) for t in turni_gironi_json)
        formula_testo += f"Turno gironi. {n_g} girone/i.\n"
    if turni_diretta_json:
        n_qual = len(qualificati_ref) or len(iscritti)
        formula_testo += f"Tabellone ad eliminazione diretta da {n_qual} atleti."

    dati = {
        "formato": "touche-export",
        "versione": 2,
        "tipo": "gara",
        "esportato_il": datetime.now().isoformat(),
        "evento": {
            "titolo": titolo,
            "data_inizio": data_gara,
            "data_fine": data_gara,
            "luogo": "",
            "indirizzo": "",
            "autorita": organisateur,
            "organizzatore": "",
            "tipologia": "",
            "pedane": "",
            "dt_presidente": "",
            "dt_membro1": "",
            "dt_membro2": "",
            "dt_membro3": "",
            "dt_computerista": "",
            "semi": "",
            "gsa_delegato": "",
            "gsa_arbitri": "",
            "comm_medica": "",
            "note": "Generato da fie2touche.py: alcuni campi dell'evento "
                    "non sono presenti nell'XML FIE e sono stati lasciati vuoti.",
            "fuso_orario": None,
        },
        "circuito": {
            "titolo": "",
            "stagione": annee,
            "descrizione": "",
        },
        "organizzatore": {
            "nome": organisateur,
            "slug": re.sub(r"[^a-z0-9]+", "-", organisateur.lower()).strip("-"),
            "descrizione": "",
            "paese": federation or "",
        },
        "gare": [
            {
                "arma": arma,
                "genere": genere,
                "tipologia": dominio,
                "categoria": categoria,
                "data_inizio": data_gara,
                "data_fine": data_gara,
                "formula": formula_testo,
                "stato": "conclusa",
                "note": "",
                "iscritti": iscritti,
                "turni_gironi": turni_gironi_json,
                "turni_diretta": turni_diretta_json,
                "formula_classifica": None,
                "formula_strutturata": None,
                "classifiche_turno": [],
                "config_squadre": None,
                "frazioni_incontro": [],
                "formazioni_squadra": [],
                "sostituzioni_squadra": [],
            }
        ],
    }
    return dati


def converti(path_xml, cartella_out):
    tree = ET.parse(path_xml)
    root = tree.getroot()
    dati = costruisci_json(root)

    os.makedirs(cartella_out, exist_ok=True)
    base = os.path.splitext(os.path.basename(path_xml))[0]
    nome_file = f"{base}_touche-export.json"
    percorso = os.path.join(cartella_out, nome_file)
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    return [percorso]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 fie2touche.py input.xml [cartella_output]", file=sys.stderr)
        sys.exit(1)
    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    files = converti(input_path, output_dir)
    for f in files:
        print(f"Generato: {f}")
