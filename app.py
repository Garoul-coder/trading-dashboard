import os
import re
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import anthropic

try:
    from bs4 import BeautifulSoup
    _BS4_OK = True
except ImportError:
    _BS4_OK = False
    print("[WARN] beautifulsoup4 non disponible — scraping désactivé")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Mapping ticker BVC → slug boursenews.ma/action/{slug}
# Source : <select id="enreprisechoise"> sur boursenews.ma
# ---------------------------------------------------------------------------
BOURSENEWS_SLUGS = {
    # Banques
    "ATW":    "attijariwafa",
    "BCP":    "bcp",
    "CIH":    "cih",
    "BOA":    "boa",
    "CDM":    "cdm",
    "BMCI":   "bmci",
    "CFG":    "cfg",
    # Assurances & Financières
    "WAA":    "wafa",
    "ACM":    "atlanta",
    "SLF":    "salafin",
    "AFMA":   "afma",
    "EQD":    "eqdom",
    "MAL":    "maroc-leasing",
    # Télécoms & Technologies
    "IAM":    "maroc-telecom",
    "M2M":    "microdata",   # Microdata = M2M sur boursenews
    "HPS":    "hps",
    "DISWAY": "disway",
    "DISTY":  "disty",
    # Mines & Industrie minière
    "SMI":    "smi",
    "MNG":    "managem",
    "CMT":    "compagnie-miniere",
    # Ciment & BTP
    "CMR":    "ciments",
    "LHM":    "lafarge",
    "JET":    "jet",
    "TGCC":   "tgcc",
    "SGTM":   "sgtm",
    # Énergie
    "TMA":    "taqa",
    "GAZ":    "afriquia-gaz",
    "TQM":    "totalenergies",
    "MOX":    "mox",
    # Agroalimentaire & Boissons
    "SBM":    "boissons",
    "OUL":    "oulmes",
    "FNB":    "fenie",
    "LES":    "lesieur",
    "CSR":    "cosumar",
    "MUT":    "mutandis",
    "UNM":    "unimer",
    "COL":    "colorado",
    # Distribution & Commerce
    "LBV":    "labelevie",
    # Automobile
    "ADH":    "autohall",
    "ALM":    "alliances",
    # Immobilier
    "DHO":    "addoha",
    "RDS":    "residences",
    "IMM":    "immorente",
    "ARA":    "aradei",
    # Industrie & Chimie
    "SID":    "sonasid",
    "PRO":    "promopharm",
    "SNEP":   "snep",
    "SOT":    "sothema",
    "STK":    "stokvis",
    "AFI":    "afric-industries",
    "AKD":    "akdital",
    "DEL":    "delta",
    # Transport & Services
    "CTM":    "ctm",
    "RIS":    "risma",
    "MSA":    "marsa",
    # Autres
    "ENK":    "ennakl",
    "CMG":    "cmgp",
    "VIC":    "vicenne",
}

# Mapping ticker → secteur
SECTORS = {
    "ATW": "Banques", "BCP": "Banques", "CIH": "Banques",
    "BOA": "Banques", "CDM": "Banques", "BMCI": "Banques", "CFG": "Banques",
    "WAA": "Assurances", "ACM": "Assurances",
    "SLF": "Services financiers", "AFMA": "Services financiers",
    "EQD": "Crédit à la consommation", "MAL": "Crédit-bail",
    "IAM": "Télécommunications",
    "M2M": "Technologies", "HPS": "Technologies",
    "DISWAY": "Technologies", "DISTY": "Technologies",
    "SMI": "Mines", "MNG": "Mines", "CMT": "Mines",
    "CMR": "Matériaux de construction", "LHM": "Matériaux de construction",
    "JET": "BTP", "TGCC": "BTP", "SGTM": "BTP",
    "TMA": "Énergie", "GAZ": "Énergie", "TQM": "Énergie", "MOX": "Énergie",
    "SBM": "Agroalimentaire", "OUL": "Agroalimentaire", "FNB": "Agroalimentaire",
    "LES": "Agroalimentaire", "CSR": "Agroalimentaire",
    "MUT": "Agroalimentaire", "UNM": "Agroalimentaire", "COL": "Agroalimentaire",
    "LBV": "Distribution",
    "ADH": "Automobile", "ALM": "Immobilier",
    "DHO": "Immobilier", "RDS": "Immobilier",
    "IMM": "Immobilier", "ARA": "Immobilier",
    "SID": "Industrie sidérurgique", "PRO": "Pharmacie",
    "SNEP": "Industrie chimique", "SOT": "Pharmacie",
    "STK": "Distribution industrielle", "AFI": "Industrie",
    "AKD": "Santé", "DEL": "Industrie",
    "CTM": "Transport", "RIS": "Tourisme & Loisirs", "MSA": "Transport maritime",
    "ENK": "Automobile", "CMG": "Services", "VIC": "Services",
}

# Fiches sociétés — source : BVC + rapports publics
COMPANY_PROFILES = {
    "SMI": {
        "nom": "Société Métallurgique d'Imiter (SMI)",
        "groupe": "Groupe Managem (filiale)",
        "activite": "Exploitation de la mine d'argent d'Imiter, dans la région de Tinghir (Drâa-Tafilalet). Première mine d'argent d'Afrique. Produit également du zinc et du plomb en sous-produits.",
        "concurrents": "Managem (MNG), filiales minières du groupe OCP",
        "particularites": "Très sensible au cours international de l'argent (XAG/USD). Réserves prouvées importantes sur le gisement d'Imiter.",
    },
    "MNG": {
        "nom": "Managem",
        "groupe": "Groupe ONA / SNI",
        "activite": "Groupe minier marocain diversifié : or, argent, cobalt, cuivre, zinc, fluorine. Opère au Maroc et en Afrique subsaharienne.",
        "concurrents": "OCP (phosphates), SMI (filiale), sociétés minières africaines internationales",
        "particularites": "Leader minier marocain coté à la BVC. Stratégie d'expansion panafricaine.",
    },
    "ATW": {
        "nom": "Attijariwafa Bank",
        "groupe": "Groupe ONA / SNI",
        "activite": "Premier groupe bancaire et financier du Maroc. Banque universelle présente dans 27 pays africains.",
        "concurrents": "BCP, BMCE Bank of Africa (BOA), CIH Bank",
        "particularites": "Plus grande capitalisation boursière de la BVC. Leader du crédit au Maroc.",
    },
    "BCP": {
        "nom": "Banque Centrale Populaire (BCP)",
        "groupe": "Groupe Banque Populaire (Crédit Populaire du Maroc)",
        "activite": "Banque coopérative. Réseau de Banques Populaires Régionales. Banque des MRE, PME et particuliers.",
        "concurrents": "Attijariwafa Bank (ATW), BMCE Bank of Africa (BOA), CIH Bank",
        "particularites": "Deuxième groupe bancaire marocain. Fort ancrage régional. Part de marché solide sur les dépôts MRE.",
    },
    "IAM": {
        "nom": "Itissalat Al-Maghrib (Maroc Telecom)",
        "groupe": "Groupe e& (Émirats Télécommunications)",
        "activite": "Opérateur télécom historique du Maroc. Mobile, fixe, internet, data centers. Présent dans 8 pays africains.",
        "concurrents": "Orange Maroc, Inwi (groupe Al Mada)",
        "particularites": "Opérateur dominant au Maroc. Dividende généreux. Croissance portée par l'Afrique subsaharienne.",
    },
    "CIH": {
        "nom": "CIH Bank",
        "groupe": "Caisse de Dépôt et de Gestion (CDG)",
        "activite": "Banque de détail orientée crédit immobilier, consommation, TPE/PME. Digital banking.",
        "concurrents": "ATW, BCP, BOA, Société Générale Maroc",
        "particularites": "En forte transformation numérique. Profil de croissance dynamique.",
    },
    "BOA": {
        "nom": "BMCE Bank of Africa",
        "groupe": "Groupe FinanceCom (famille Othman Benjelloun)",
        "activite": "Banque universelle marocaine avec présence dans 20+ pays africains.",
        "concurrents": "Attijariwafa Bank (ATW), Banque Centrale Populaire (BCP)",
        "particularites": "Troisième groupe bancaire marocain. Pionnier de la bancarisation en Afrique subsaharienne.",
    },
    "HPS": {
        "nom": "Hightech Payment Systems (HPS)",
        "groupe": "Indépendant (fondateurs)",
        "activite": "Éditeur de logiciels de paiement électronique. Solution PowerCARD. Clients dans 90+ pays.",
        "concurrents": "Fiserv, FIS, Temenos (internationaux)",
        "particularites": "Champion marocain de la fintech à l'international. Revenus récurrents. Forte croissance export.",
    },
    "TMA": {
        "nom": "Taqa Morocco",
        "groupe": "Abu Dhabi National Energy Company (TAQA) — 72,6%",
        "activite": "Production d'électricité depuis la centrale thermique de Jorf Lasfar (2 760 MW). Vente exclusive à l'ONEE.",
        "concurrents": "ONEE, autres producteurs indépendants (IPP)",
        "particularites": "Contrat PPA long terme avec l'ONEE. Revenus stables. Fort rendement dividende.",
    },
    "CMR": {
        "nom": "Ciments du Maroc (CimMaroc)",
        "groupe": "Groupe Heidelberg Materials — majoritaire",
        "activite": "Production de ciment, béton, granulats et chaux. Deuxième cimentier du Maroc.",
        "concurrents": "LafargeHolcim Maroc (LHM), Asment de Témara, Cimat",
        "particularites": "Bénéficiaire potentiel du Mondial 2030 et reconstruction post-séisme.",
    },
    "LHM": {
        "nom": "LafargeHolcim Maroc",
        "groupe": "Holcim Group (Suisse) — majoritaire",
        "activite": "Premier cimentier du Maroc. Production de ciment, béton, granulats, mortiers.",
        "concurrents": "Ciments du Maroc (CMR), Asment de Témara, Cimat",
        "particularites": "Stratégie décarbonation. Fort levier sur les grands chantiers infrastructure.",
    },
    "GAZ": {
        "nom": "Afriquia Gaz",
        "groupe": "Groupe Akwa (famille Akhannouch)",
        "activite": "Distribution et commercialisation de GPL (butane, propane). Leader du marché gaz au Maroc.",
        "concurrents": "Maghreb Oxygène, Total Énergies Maroc",
        "particularites": "Monopole partiel sur le GPL. Prix butane subventionné par l'État. Fort dividende.",
    },
    "WAA": {
        "nom": "Wafa Assurance",
        "groupe": "Attijariwafa Bank (filiale)",
        "activite": "Compagnie d'assurance multibranche : vie, non-vie, assurance-crédit, santé.",
        "concurrents": "RMA (FinanceCom), Saham Assurance (Sanlam), AXA Assurance Maroc",
        "particularites": "Leader de l'assurance au Maroc. Forte synergie avec Attijariwafa Bank.",
    },
    "SBM": {
        "nom": "Société des Boissons du Maroc (SBM)",
        "groupe": "Castel Group (France) — actionnaire majoritaire",
        "activite": "Production et distribution de bières (Flag, Casablanca, Heineken sous licence), eaux minérales (Sidi Ali).",
        "concurrents": "CBGN, Coca-Cola Maroc, Pepsi",
        "particularites": "Secteur régulé. Fort pricing power. Dividende généreux.",
    },
    "DHO": {
        "nom": "Douja Promotion Groupe Addoha",
        "groupe": "Famille Anas Sefrioui",
        "activite": "Premier promoteur immobilier marocain. Logement social, économique et haut standing.",
        "concurrents": "Alliances Développement Immobilier, Résidences Dar Saada",
        "particularites": "Très sensible aux politiques de logement social. Restructuration de la dette en cours.",
    },
    "CTM": {
        "nom": "CTM (Compagnie de Transport au Maroc)",
        "groupe": "Groupe FinanceCom (actionnaire)",
        "activite": "Transport routier de voyageurs au Maroc et vers l'Europe.",
        "concurrents": "Supratours (ONCF), transporteurs privés, compagnies aériennes low-cost",
        "particularites": "Quasi-monopole sur les liaisons longue distance de qualité.",
    },
    "LES": {
        "nom": "Lesieur Cristal",
        "groupe": "Groupe OCP / Sofiprotéol",
        "activite": "Production et commercialisation d'huiles alimentaires (Lesieur, Huilor), savons, margarines.",
        "concurrents": "Aicha, producteurs régionaux, importations",
        "particularites": "Leader des huiles alimentaires au Maroc. Sensible aux cours des oléagineux.",
    },
    "CSR": {
        "nom": "Cosumar",
        "groupe": "Groupe Al Mada (ex-SNI)",
        "activite": "Principale sucrerie du Maroc. Extraction et raffinage du sucre. Marques : Nassim, Enmer, Farida.",
        "concurrents": "Importations, producteurs régionaux de sucre",
        "particularites": "Quasi-monopole sur le sucre raffiné au Maroc. Prix encadrés par l'État.",
    },
    "LBV": {
        "nom": "Label'Vie",
        "groupe": "Famille Zniber / Carrefour (partenariat franchise)",
        "activite": "Distribution alimentaire et non-alimentaire. Enseignes : Carrefour, Carrefour Market, Atacadão.",
        "concurrents": "Marjane (ONA), Aswak Assalam, BIM",
        "particularites": "Forte croissance du réseau. Concept Atacadão (Cash & Carry) en expansion.",
    },
    "SID": {
        "nom": "Sonasid",
        "groupe": "Groupe ArcelorMittal (majoritaire)",
        "activite": "Production d'acier long (ronds à béton, fil machine). Principal sidérurgiste marocain.",
        "concurrents": "Importations d'acier (Turquie, Chine, Europe), Maghreb Steel",
        "particularites": "Sensible aux cours mondiaux de l'acier et de la ferraille. Levier sur le BTP marocain.",
    },
    "PRO": {
        "nom": "Promopharm",
        "groupe": "Groupe Sanofi (filiale)",
        "activite": "Production et distribution de médicaments génériques et princeps. Usine à Casablanca.",
        "concurrents": "Sothema, Cooper Pharma, Laprophan",
        "particularites": "Filiale de Sanofi. Bénéficiaire de la politique de généricisation au Maroc.",
    },
    "RIS": {
        "nom": "Risma",
        "groupe": "Groupe Accor (actionnaire de référence)",
        "activite": "Gestion hôtelière au Maroc. Portefeuille d'hôtels Accor (Ibis, Novotel, Mercure, Sofitel).",
        "concurrents": "Hôtels indépendants, chaînes internationales (Marriott, Hilton)",
        "particularites": "Bénéficiaire direct du tourisme marocain. Levier sur le Mondial 2030.",
    },
    "OUL": {
        "nom": "Les Eaux Minérales d'Oulmès",
        "groupe": "Groupe Holmarcom",
        "activite": "Production et distribution d'eaux minérales (Sidi Ali, Oulmès) et de boissons gazeuses (Coca-Cola sous licence).",
        "concurrents": "SBM (Sidi Ali), Ain Saïss, importations",
        "particularites": "Leader des eaux minérales et boissons gazeuses. Franchise Coca-Cola au Maroc.",
    },
    "MUT": {
        "nom": "Mutandis",
        "groupe": "Management (fondateurs)",
        "activite": "Holding agroalimentaire. Marques : Carrefour (produits MDD), St Michel (biscuits), pêche, conserves.",
        "concurrents": "Divers selon segment",
        "particularites": "Conglomérat agroalimentaire en croissance. Modèle de consolidation de niches.",
    },
    "MOX": {
        "nom": "Maghreb Oxygène",
        "groupe": "Groupe Air Liquide (partenariat)",
        "activite": "Production et distribution de gaz industriels (oxygène, azote, acétylène, CO2) et médicaux.",
        "concurrents": "Linde Maroc, Air Products",
        "particularites": "Position de niche dans les gaz industriels. Clients : sidérurgie, santé, industrie.",
    },
    "ADH": {
        "nom": "Auto Hall",
        "groupe": "Groupe Holmarcom",
        "activite": "Distribution automobile : concessionnaire Ford, Mitsubishi, Volvo, Iveco au Maroc.",
        "concurrents": "Auto Nejma, Sopriam, SMEIA",
        "particularites": "Premier distributeur automobile au Maroc. Sensible au marché auto et au crédit.",
    },
}


def get_company_context(ticker):
    p = COMPANY_PROFILES.get(ticker)
    if not p:
        return ""
    lines = [
        f"- Nom complet    : {p['nom']}",
        f"- Groupe         : {p['groupe']}",
        f"- Activité       : {p['activite']}",
        f"- Concurrents    : {p['concurrents']}",
        f"- Particularités : {p['particularites']}",
    ]
    return "Fiche société (source : BVC / rapports publics) :\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Scraper boursenews.ma
# ---------------------------------------------------------------------------
_BN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://boursenews.ma/",
}


def _fr_num(s):
    """Convert French-formatted number string to float. '2 000,00' → 2000.0"""
    if s is None:
        return None
    s = str(s).strip().replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s) if s not in ("", ".") else None
    except ValueError:
        return None


def scrape_boursenews(slug):
    """
    Fetch boursenews.ma/action/{slug} and extract all financial data.
    Returns a dict ready to be serialised as JSON.
    Timeout: 20s. Uses html.parser (no lxml dependency).
    """
    if not _BS4_OK:
        raise RuntimeError("beautifulsoup4 non installé")

    url = f"https://boursenews.ma/action/{slug}"
    try:
        resp = requests.get(url, headers=_BN_HEADERS, timeout=(5, 10))
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Timeout scraping {url}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP {e.response.status_code} for {url}")

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {"source": "boursenews", "url": url, "scraped_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

    # ── 1. Prix et données de séance ──────────────────────────────────────
    # Page text lines — iterate to find labelled values
    lines = [ln.strip() for ln in soup.get_text(separator="\n").split("\n") if ln.strip()]

    def val_after(label, max_offset=4, exclude=None):
        label_l = label.lower()
        excl_l  = [e.lower() for e in (exclude or [])]
        for i, ln in enumerate(lines):
            ln_l = ln.lower()
            if label_l in ln_l and not any(e in ln_l for e in excl_l):
                for j in range(1, max_offset + 1):
                    if i + j < len(lines):
                        v = _fr_num(lines[i + j])
                        if v is not None:
                            return v
        return None

    result["cours"]      = val_after("Cours", exclude=["cible", "variation", "haut", "bas", "ouverture", "offre", "demande"])
    result["variation"]  = val_after("Var (%)")  or val_after("Var.")
    result["volume"]     = val_after("Volumes")  or val_after("Volume")
    result["haut"]       = val_after("+ Haut")   or val_after("Haut")
    result["bas"]        = val_after("+ Bas")    or val_after("Bas")
    result["ouverture"]  = val_after("Ouverture")
    result["meil_dem"]   = val_after("Meilleure demande") or val_after("Demande")
    result["meil_off"]   = val_after("Meilleure offre")   or val_after("Offre")

    # ── 2. Tableaux financiers annuels ────────────────────────────────────
    annees = []
    financials = {}
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"])
        header_texts = [c.get_text(strip=True) for c in header_cells]
        year_cols = [i for i, t in enumerate(header_texts) if re.match(r"^20\d{2}", t)]
        if not year_cols:
            continue
        if not annees:
            annees = [header_texts[i] for i in year_cols]
        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            label = cells[0].get_text(strip=True)
            if not label or label in ("", "-"):
                continue
            values = []
            for i in year_cols:
                v = _fr_num(cells[i].get_text(strip=True)) if i < len(cells) else None
                values.append(v)
            if any(v is not None for v in values):
                financials[label] = dict(zip(annees, values))

    result["annees"]     = annees
    result["financials"] = financials

    # ── 3. Données Chart.js (labels + data arrays dans les <script>) ──────
    chart_series = {}
    scripts = [s.string for s in soup.find_all("script") if s.string]
    for script in scripts:
        # Pattern: label: 'X', data: [1, 2, 3]  or  label: "X", data: [...]
        matches = re.findall(
            r'label\s*:\s*["\']([^"\']+)["\']\s*,\s*data\s*:\s*\[([^\]]+)\]',
            script
        )
        for lbl, data_str in matches:
            nums = re.findall(r"-?\d+(?:\.\d+)?", data_str)
            if nums:
                chart_series[lbl] = [float(n) for n in nums]
    if chart_series:
        result["chart_series"] = chart_series

    # ── 4. Scores radar (Fondamentaux, Momentum, Visibilité…) ─────────────
    radar_keys = {"Fondamentaux", "Momentum", "Visibilite", "Visibilité", "Consensus", "Valorisation"}
    radar = {}
    for script in scripts:
        for key in radar_keys:
            m = re.search(rf'["\']?{key}["\']?\s*:\s*(\d+(?:\.\d+)?)', script)
            if m:
                radar[key.replace("é", "e")] = float(m.group(1))
    # Fallback: search in data arrays labelled with these keywords
    if not radar:
        for script in scripts:
            m = re.search(
                r'labels\s*:\s*\[([^\]]+)\].*?data\s*:\s*\[([^\]]+)\]',
                script, re.DOTALL
            )
            if m:
                lbls = re.findall(r'["\']([^"\']+)["\']', m.group(1))
                vals = re.findall(r'-?\d+(?:\.\d+)?', m.group(2))
                for l, v in zip(lbls, vals):
                    if any(k.lower() in l.lower() for k in radar_keys):
                        radar[l] = float(v)
    if radar:
        result["scores"] = radar

    # ── 5. Signaux techniques (Acheter / Neutre / Vendre) ─────────────────
    signals = {}
    signal_map = {"Acheter": "acheter", "Neutre": "neutre", "Vendre": "vendre"}
    for i, ln in enumerate(lines):
        for fr_key, en_key in signal_map.items():
            if ln.strip() == fr_key:
                for j in range(1, 4):
                    if i + j < len(lines):
                        v = _fr_num(lines[i + j])
                        if v is not None:
                            signals[en_key] = int(v)
                            break
    if signals:
        result["signaux_techniques"] = signals

    # ── 6. Cours cible analyste ───────────────────────────────────────────
    for i, ln in enumerate(lines):
        if "cours cible" in ln.lower():
            for j in range(1, 5):
                if i + j < len(lines):
                    v = _fr_num(lines[i + j])
                    if v and v > 10:
                        result["cours_cible"] = v
                        break
            break

    # ── 7. Actionnaires ───────────────────────────────────────────────────
    shareholders = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) == 2:
                name = cells[0].get_text(strip=True)
                pct_text = cells[1].get_text(strip=True)
                if "%" in pct_text and name and name.upper() != "TOTAL":
                    pct = _fr_num(pct_text.replace("%", "").strip())
                    if pct is not None and 0 < pct <= 100:
                        shareholders.append({"nom": name, "pct": pct})
    if shareholders:
        result["actionnaires"] = shareholders

    # ── 8. Ratios (PER, PBR, DY) depuis les tableaux ─────────────────────
    for label, values in financials.items():
        l = label.upper()
        if "PER" in l:
            result["ratios_per"] = values
        elif "PBR" in l:
            result["ratios_pbr"] = values
        elif "DY" in l or "DIVIDENDE" in l:
            result["ratios_dy"] = values

    return result


def _format_scraped_for_claude(ticker, sd):
    """
    Format the scraped boursenews data into a rich text context for Claude.
    Returns a string to inject in the prompt.
    """
    if not sd or sd.get("source") != "boursenews":
        return "Données marché non disponibles. Formule des hypothèses réalistes basées sur le contexte du marché marocain."

    lines = [f"Données financières issues de boursenews.ma — scraped le {sd.get('scraped_at', 'N/A')} :\n"]

    # Cours actuel
    if sd.get("cours"):
        variation = sd.get("variation")
        var_str = f" ({variation:+.2f}%)" if variation is not None else ""
        lines.append(f"💰 **COURS ACTUEL : {sd['cours']:,.2f} MAD{var_str}**")
    if sd.get("haut"):
        lines.append(f"- Séance : Haut {sd['haut']:,.2f} / Bas {sd.get('bas', '—'):,.2f} MAD")
    if sd.get("ouverture"):
        lines.append(f"- Ouverture : {sd['ouverture']:,.2f} MAD")
    if sd.get("volume"):
        lines.append(f"- Volume échangé : {int(sd['volume']):,} titres")
    if sd.get("cours_cible"):
        lines.append(f"- Cours cible analyste : {sd['cours_cible']:,.2f} MAD")

    # Données financières annuelles
    fin = sd.get("financials", {})
    annees = sd.get("annees", [])
    if fin and annees:
        lines.append(f"\nDonnées financières annuelles (en MMAD) — années : {', '.join(annees)}")
        key_labels = [
            "Chiffre d'affaires", "CA", "Chiffre d affaires",
            "EBITDA",
            "Résultat d'exploitation", "Résultat exploitation",
            "Résultat net",
            "Marge d'exploitation", "Marge exploitation",
            "Marge nette",
            "BNA", "DPA",
        ]
        for label, values in fin.items():
            # Only show key financial metrics
            if any(k.lower() in label.lower() for k in key_labels):
                row_vals = " | ".join(
                    f"{v:,.1f}" if isinstance(v, float) and v is not None else "—"
                    for v in [values.get(y) for y in annees]
                )
                lines.append(f"  {label}: {row_vals}")

    # Scores radar
    scores = sd.get("scores", {})
    if scores:
        score_str = " | ".join(f"{k}: {v}/10" for k, v in scores.items())
        lines.append(f"\nScores qualitatifs : {score_str}")

    # Signaux techniques
    sig = sd.get("signaux_techniques", {})
    if sig:
        lines.append(
            f"Signaux techniques : Acheter={sig.get('acheter', '?')} | "
            f"Neutre={sig.get('neutre', '?')} | Vendre={sig.get('vendre', '?')}"
        )

    # Actionnaires
    act = sd.get("actionnaires", [])
    if act:
        lines.append("\nActionnariat :")
        for a in act[:5]:
            lines.append(f"  - {a['nom']}: {a['pct']}%")

    # Ratios
    if sd.get("ratios_per"):
        per_vals = " | ".join(
            f"{yr}: {sd['ratios_per'].get(yr, '—')}"
            for yr in annees[-4:] if yr in sd.get("ratios_per", {})
        )
        if per_vals:
            lines.append(f"PER historique : {per_vals}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------
def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Clé API Anthropic non configurée.")
    return anthropic.Anthropic(api_key=api_key)


def generate_analysis(ticker, sector, sd):
    """Build prompt from scraped data and call Claude Haiku."""
    data_context = _format_scraped_for_claude(ticker, sd)

    company_context = get_company_context(ticker)
    company_section = f"\n{company_context}\n" if company_context else ""

    # Price snapshot for section 1
    price_snapshot = ""
    if sd and sd.get("source") == "boursenews" and sd.get("cours"):
        cours = sd["cours"]
        variation = sd.get("variation")
        var_str = f"{variation:+.2f}%" if variation is not None else "—"
        haut = sd.get("haut", "—")
        bas = sd.get("bas", "—")
        vol = f"{int(sd['volume']):,}" if sd.get("volume") else "—"
        cible = f"{sd['cours_cible']:,.2f} MAD" if sd.get("cours_cible") else "—"
        price_snapshot = f"""
**💰 COURS ACTUEL : {cours:,.2f} MAD ({var_str})**
| Indicateur | Valeur |
|---|---|
| Cours actuel | **{cours:,.2f} MAD** |
| Variation séance | {var_str} |
| Haut du jour | {haut} MAD |
| Bas du jour | {bas} MAD |
| Volume échangé | {vol} titres |
| Cours cible analyste | {cible} |

"""

    prompt = f"""Analyste financier BVC expert. Analyse complète en français, style broker, bullet points concis.

Ticker : **{ticker}** | Secteur : {sector}
{company_section}
{data_context}

Structure OBLIGATOIRE (7 sections) :

## 🔎 1. Présentation
{price_snapshot}- Nom complet, groupe, activité principale
- Positionnement marché marocain, concurrents clés

## 📊 2. Analyse fondamentale
- CA, résultat net, marges EBITDA/nette (utilise données fournies, avec évolutions YoY)
- PER, ROE, rendement dividende (DPA/cours), valorisation vs historique
- Forces, faiblesses, risques macro/sectoriels, perspectives

## 📈 3. Analyse technique
- Tendances court/moyen/long terme
- Signaux Acheter/Neutre/Vendre fournis + scores radar (si disponibles)
- Supports et résistances clés (MAD), configuration actuelle

## ⚡ 4. Momentum
- Tendance de fond, force vs MASI
- Signal : 🟢 HAUSSIER | 🟡 NEUTRE | 🔴 BAISSIER

## 🏭 5. Comparaison sectorielle
| Critère | {ticker} | Pair 1 | Pair 2 |
|---|---|---|---|
| Croissance CA | | | |
| Marge nette | | | |
| PER | | | |

## 🧾 6. Opinion
- **ACHAT FORT** / **ACHAT** / **CONSERVER** / **ALLÉGER** / **VENTE**
- Prix cible 12 mois (MAD) · Risque : Faible/Moyen/Élevé
- 3 arguments clés

## 🧠 7. Résumé exécutif
4-5 lignes max, style flash note broker, orienté décision."""

    client = get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

# Garantit que toutes les erreurs Flask retournent du JSON (jamais du HTML)
@app.errorhandler(Exception)
def handle_any_exception(e):
    print(f"[ERROR] Unhandled: {e}")
    return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "Route non trouvée"}), 404


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))})


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Requête invalide"}), 400

        ticker = str(data.get("ticker", "")).upper().strip()
        if not ticker or len(ticker) > 10:
            return jsonify({"error": "Ticker invalide"}), 400

        sector = SECTORS.get(ticker, "Secteur divers")

        # Try boursenews first
        sd = None
        slug = BOURSENEWS_SLUGS.get(ticker)
        if slug:
            try:
                sd = scrape_boursenews(slug)
                print(f"[DATA] {ticker} → boursenews.ma/{slug} ✓")
            except Exception as e:
                print(f"[WARN] boursenews failed for {ticker} ({slug}): {e}")
                sd = {"source": "none", "data_available": False}
        else:
            print(f"[WARN] No boursenews slug for {ticker}")
            sd = {"source": "none", "data_available": False}

        analysis = generate_analysis(ticker, sector, sd)

        return jsonify({
            "ticker":      ticker,
            "sector":      sector,
            "stock_data":  sd,
            "analysis":    analysis,
            "data_source": sd.get("source", "none"),
        })

    except Exception as e:
        print(f"[ERROR] /analyze: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
