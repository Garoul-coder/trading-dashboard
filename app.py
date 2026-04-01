import os
import re
import json
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
# Mapping ticker BVC → slug fr.investing.com/equities/{slug}
# Slugs vérifiés depuis https://fr.investing.com/equities/morocco
# ---------------------------------------------------------------------------
INVESTING_SLUGS = {
    # Banques
    "ATW":    "attijariwafa-bk",
    "BCP":    "bcp",
    "CIH":    "cih",
    "BOA":    "bmce",
    "CDM":    "cdm",
    "BMCI":   "bmci",
    "CFG":    "cfg-bank",
    # Assurances & Financières
    "WAA":    "wafa-assurance",
    "ACM":    "atlanta",
    "SLF":    "salafin",
    "AFMA":   "afma-sa",
    "EQD":    "credit-eqdm",
    "MAL":    "maroc-leasing",
    # Télécoms & Tech
    "IAM":    "itissalat-al-maghrib",
    "M2M":    "m2m-group",
    "HPS":    "highteck-payment",
    "DISWAY": "disway",
    "DISTY":  "disty-tech",
    # Mines
    "SMI":    "smi",
    "MNG":    "managem",
    "CMT":    "miniere-touissit",
    # Ciment & BTP
    "CMR":    "ciments-du-maroc",
    "LHM":    "lafarge-ciments",
    "JET":    "jet-alu-maroc-sa",
    "TGCC":   "casablanca",
    # Énergie
    "TMA":    "jorf-lasfar",
    "GAZ":    "afriquia-gaz",
    "TQM":    "total-maroc-sa",
    "MOX":    "maghreb-oxygene",
    # Agroalimentaire
    "SBM":    "brasseries-maroc",
    "OUL":    "oulmes",
    "LES":    "lesieur",
    "CSR":    "cosumar",
    "MUT":    "mutandis",
    "UNM":    "unimer",
    "COL":    "colorado",
    # Distribution
    "LBV":    "label-vie",
    # Automobile
    "ADH":    "auto-hall",
    # Immobilier
    "ALM":    "alliances",
    "DHO":    "addoha",
    "RDS":    "res-dar-saada",
    "IMM":    "immorente-invest",
    "ARA":    "aradei-capital",
    # Industrie & Chimie
    "SID":    "sonasid",
    "PRO":    "promopharm-s.a",
    "SNEP":   "snep",
    "SOT":    "sothema",
    "STK":    "stokvis-nord",
    "AFI":    "afric-industries",
    "AKD":    "akdital",
    "DEL":    "delta-holding",
    # Transport & Services
    "CTM":    "ctm-ln",
    "RIS":    "risma",
    "MSA":    "marsa-maroc-sa",
    # Autres
    "S2M":    "s2m",
}

# ---------------------------------------------------------------------------
# Secteurs BVC
# ---------------------------------------------------------------------------
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
    "JET": "BTP", "TGCC": "BTP",
    "TMA": "Énergie", "GAZ": "Énergie", "TQM": "Énergie", "MOX": "Énergie",
    "SBM": "Agroalimentaire", "OUL": "Agroalimentaire",
    "LES": "Agroalimentaire", "CSR": "Agroalimentaire",
    "MUT": "Agroalimentaire", "UNM": "Agroalimentaire", "COL": "Agroalimentaire",
    "LBV": "Distribution",
    "ADH": "Automobile",
    "ALM": "Immobilier", "DHO": "Immobilier", "RDS": "Immobilier",
    "IMM": "Immobilier", "ARA": "Immobilier",
    "SID": "Industrie sidérurgique", "PRO": "Pharmacie",
    "SNEP": "Industrie chimique", "SOT": "Pharmacie",
    "STK": "Distribution industrielle", "AFI": "Industrie",
    "AKD": "Santé", "DEL": "Industrie",
    "CTM": "Transport", "RIS": "Tourisme & Loisirs", "MSA": "Transport maritime",
    "S2M": "Technologies",
}

# ---------------------------------------------------------------------------
# Fiches sociétés
# ---------------------------------------------------------------------------
COMPANY_PROFILES = {
    "SMI": {
        "nom": "Société Métallurgique d'Imiter (SMI)",
        "groupe": "Groupe Managem (filiale)",
        "activite": "Exploitation de la mine d'argent d'Imiter (Tinghir). Première mine d'argent d'Afrique.",
        "concurrents": "Managem (MNG), filiales minières OCP",
        "particularites": "Très sensible au cours international de l'argent (XAG/USD).",
    },
    "MNG": {
        "nom": "Managem",
        "groupe": "Groupe ONA / SNI",
        "activite": "Groupe minier diversifié : or, argent, cobalt, cuivre, zinc. Présent en Afrique.",
        "concurrents": "OCP, filiales minières africaines",
        "particularites": "Leader minier marocain coté BVC. Expansion panafricaine.",
    },
    "ATW": {
        "nom": "Attijariwafa Bank",
        "groupe": "Groupe ONA / SNI",
        "activite": "Premier groupe bancaire du Maroc, présent dans 27 pays africains.",
        "concurrents": "BCP, BOA, CIH Bank",
        "particularites": "Plus grande capitalisation boursière BVC. Leader crédit Maroc.",
    },
    "BCP": {
        "nom": "Banque Centrale Populaire (BCP)",
        "groupe": "Groupe Banque Populaire",
        "activite": "Banque coopérative, réseau BPR, banque MRE/PME/particuliers.",
        "concurrents": "ATW, BOA, CIH Bank",
        "particularites": "2e groupe bancaire marocain. Fort ancrage régional.",
    },
    "IAM": {
        "nom": "Itissalat Al-Maghrib (Maroc Telecom)",
        "groupe": "Groupe e& (Émirats)",
        "activite": "Opérateur télécom historique Maroc. Mobile, fixe, internet. 8 pays africains.",
        "concurrents": "Orange Maroc, Inwi",
        "particularites": "Dividende généreux. Croissance portée par l'Afrique.",
    },
    "CIH": {
        "nom": "CIH Bank",
        "groupe": "Caisse de Dépôt et de Gestion (CDG)",
        "activite": "Banque de détail, crédit immobilier, TPE/PME, digital banking.",
        "concurrents": "ATW, BCP, BOA",
        "particularites": "Forte transformation numérique. Profil de croissance dynamique.",
    },
    "BOA": {
        "nom": "BMCE Bank of Africa",
        "groupe": "Groupe FinanceCom (Benjelloun)",
        "activite": "Banque universelle marocaine, présente dans 20+ pays africains.",
        "concurrents": "ATW, BCP",
        "particularites": "3e groupe bancaire marocain. Pioneer bancaire en Afrique.",
    },
    "HPS": {
        "nom": "Hightech Payment Systems (HPS)",
        "groupe": "Indépendant",
        "activite": "Éditeur logiciels paiement électronique (PowerCARD). 90+ pays.",
        "concurrents": "Fiserv, FIS, Temenos",
        "particularites": "Champion marocain fintech international. Revenus récurrents.",
    },
    "TMA": {
        "nom": "Taqa Morocco",
        "groupe": "TAQA Abu Dhabi (72,6%)",
        "activite": "Production électricité centrale Jorf Lasfar (2 760 MW). Vente à l'ONEE.",
        "concurrents": "ONEE, autres IPP",
        "particularites": "Contrat PPA long terme. Revenus stables. Fort rendement dividende.",
    },
    "CMR": {
        "nom": "Ciments du Maroc",
        "groupe": "Heidelberg Materials",
        "activite": "Production ciment, béton, granulats. 2e cimentier Maroc.",
        "concurrents": "LafargeHolcim Maroc, Asment, Cimat",
        "particularites": "Bénéficiaire Mondial 2030 et reconstruction post-séisme.",
    },
    "LHM": {
        "nom": "LafargeHolcim Maroc",
        "groupe": "Holcim Group (Suisse)",
        "activite": "1er cimentier Maroc. Ciment, béton, granulats, mortiers.",
        "concurrents": "Ciments du Maroc, Asment, Cimat",
        "particularites": "Stratégie décarbonation. Levier grands chantiers infrastructure.",
    },
    "GAZ": {
        "nom": "Afriquia Gaz",
        "groupe": "Groupe Akwa (Akhannouch)",
        "activite": "Distribution GPL (butane, propane). Leader marché gaz Maroc.",
        "concurrents": "Maghreb Oxygène, TotalEnergies Maroc",
        "particularites": "Prix butane subventionné. Fort dividende.",
    },
    "WAA": {
        "nom": "Wafa Assurance",
        "groupe": "Attijariwafa Bank (filiale)",
        "activite": "Assurance multibranche : vie, non-vie, santé, crédit.",
        "concurrents": "RMA, Saham Assurance (Sanlam), AXA Maroc",
        "particularites": "Leader assurance Maroc. Synergie ATW.",
    },
    "SBM": {
        "nom": "Société des Boissons du Maroc",
        "groupe": "Castel Group (France)",
        "activite": "Bières (Flag, Casablanca, Heineken licence), eaux (Sidi Ali).",
        "concurrents": "CBGN, Coca-Cola Maroc",
        "particularites": "Fort pricing power. Dividende généreux.",
    },
    "DHO": {
        "nom": "Douja Promotion Groupe Addoha",
        "groupe": "Famille Anas Sefrioui",
        "activite": "1er promoteur immobilier Maroc. Logement social, économique, haut standing.",
        "concurrents": "Alliances, Résidences Dar Saada",
        "particularites": "Sensible politiques logement social. Restructuration dette en cours.",
    },
    "LES": {
        "nom": "Lesieur Cristal",
        "groupe": "OCP / Sofiprotéol",
        "activite": "Huiles alimentaires (Lesieur, Huilor), savons, margarines.",
        "concurrents": "Aicha, importations",
        "particularites": "Leader huiles alimentaires Maroc. Sensible cours oléagineux.",
    },
    "CSR": {
        "nom": "Cosumar",
        "groupe": "Groupe Al Mada",
        "activite": "Sucrerie du Maroc. Extraction et raffinage sucre.",
        "concurrents": "Importations",
        "particularites": "Quasi-monopole sucre raffiné. Prix encadrés État.",
    },
    "LBV": {
        "nom": "Label'Vie",
        "groupe": "Famille Zniber / Carrefour",
        "activite": "Distribution alimentaire. Carrefour, Carrefour Market, Atacadão.",
        "concurrents": "Marjane, Aswak Assalam, BIM",
        "particularites": "Forte croissance réseau. Concept Atacadão en expansion.",
    },
    "SID": {
        "nom": "Sonasid",
        "groupe": "ArcelorMittal",
        "activite": "Acier long (ronds à béton, fil machine). Principal sidérurgiste marocain.",
        "concurrents": "Importations acier, Maghreb Steel",
        "particularites": "Sensible cours mondiaux acier/ferraille.",
    },
    "ADH": {
        "nom": "Auto Hall",
        "groupe": "Groupe Holmarcom",
        "activite": "Distribution automobile : Ford, Mitsubishi, Volvo, Iveco.",
        "concurrents": "Auto Nejma, Sopriam, SMEIA",
        "particularites": "1er distributeur automobile Maroc.",
    },
    "MSA": {
        "nom": "Marsa Maroc",
        "groupe": "État marocain (actionnaire principal)",
        "activite": "Exploitation et développement des ports marocains.",
        "concurrents": "Opérateurs portuaires internationaux",
        "particularites": "Levier direct sur croissance commerce extérieur marocain.",
    },
    "RIS": {
        "nom": "Risma",
        "groupe": "Groupe Accor",
        "activite": "Gestion hôtelière Maroc. Ibis, Novotel, Mercure, Sofitel.",
        "concurrents": "Hôtels indépendants, Marriott, Hilton",
        "particularites": "Bénéficiaire tourisme marocain et Mondial 2030.",
    },
    "OUL": {
        "nom": "Les Eaux Minérales d'Oulmès",
        "groupe": "Groupe Holmarcom",
        "activite": "Eaux minérales (Sidi Ali, Oulmès), boissons gazeuses (Coca-Cola licence).",
        "concurrents": "SBM, Ain Saïss",
        "particularites": "Leader eaux minérales et boissons gazeuses. Franchise Coca-Cola.",
    },
    "AKD": {
        "nom": "Akdital",
        "groupe": "Fondateurs (Dr Rochdi Talib)",
        "activite": "Réseau de cliniques privées au Maroc. Leader hospitalier privé coté BVC.",
        "concurrents": "Clinimaroc, cliniques indépendantes",
        "particularites": "Forte croissance. Seul acteur santé privé coté BVC.",
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
    return "Fiche société :\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Scraper fr.investing.com
# ---------------------------------------------------------------------------
_INV_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://fr.investing.com/",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Cache-Control": "max-age=0",
}


def _inv_num(s):
    """
    Parse investing.com French-format numbers.
    '6.734,00' → 6734.0  |  '10,07B' → 10070000000  |  '+10,00%' → 10.0
    """
    if s is None:
        return None
    s = str(s).strip().replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    mult = 1
    su = s.upper()
    if su.endswith('B'):
        mult = 1_000_000_000
        s = s[:-1]
    elif su.endswith('M') and not su.endswith('MAD'):
        mult = 1_000_000
        s = s[:-1]
    # French: dots = thousands separator, comma = decimal → remove dots, comma→dot
    s = s.replace('.', '').replace(',', '.')
    s = re.sub(r'[^\d.\-]', '', s)
    try:
        return float(s) * mult if s not in ('', '.') else None
    except ValueError:
        return None


def scrape_investing(slug):
    """
    Scrape fr.investing.com/equities/{slug}.
    Extracts: cours, variation, haut, bas, volume, ouverture, clot_precedent,
              haut_52s, bas_52s, per, bpa, capitalisation, rendement, roe, roa,
              marge_brute, rsi, cours_cible.
    Returns a dict. Raises RuntimeError on failure.
    """
    if not _BS4_OK:
        raise RuntimeError("beautifulsoup4 non installé")

    url = f"https://fr.investing.com/equities/{slug}"
    try:
        resp = requests.get(url, headers=_INV_HEADERS, timeout=(5, 12))
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Timeout scraping {url}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP {e.response.status_code} scraping {url}")

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {
        "source":     "investing",
        "url":        url,
        "scraped_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

    # ── 1. Prix : essai via data-test (nouveau UI investing.com) ─────────────
    price_el = soup.find(attrs={"data-test": "instrument-price-last"})
    if price_el:
        result["cours"] = _inv_num(price_el.get_text(strip=True))

    var_el = soup.find(attrs={"data-test": "instrument-price-change-percent"})
    if var_el:
        result["variation"] = _inv_num(
            var_el.get_text(strip=True).strip("()%")
        )

    # ── 2. Essai via __NEXT_DATA__ JSON ──────────────────────────────────────
    if not result.get("cours"):
        nd = soup.find("script", {"id": "__NEXT_DATA__"})
        if nd and nd.string:
            try:
                data = json.loads(nd.string)
                props = data.get("props", {}).get("pageProps", {})
                for path in [
                    ["instrumentData", "last"],
                    ["priceData", "last"],
                    ["data", "last"],
                ]:
                    val = props
                    for key in path:
                        if isinstance(val, dict):
                            val = val.get(key)
                    if val is not None:
                        result["cours"] = _inv_num(str(val))
                        break
            except Exception:
                pass

    # ── 3. Parsing texte (fallback universel) ─────────────────────────────────
    lines = [ln.strip() for ln in soup.get_text(separator="\n").split("\n") if ln.strip()]

    def val_after(label, max_offset=3, exclude=None):
        label_l = label.lower()
        excl_l  = [e.lower() for e in (exclude or [])]
        for i, ln in enumerate(lines):
            ln_l = ln.lower()
            if label_l in ln_l and not any(e in ln_l for e in excl_l):
                for j in range(1, max_offset + 1):
                    if i + j < len(lines):
                        v = _inv_num(lines[i + j])
                        if v is not None and v > 0:
                            return v
        return None

    def range_val(label):
        """Parse 'X,XX - Y,YY' → (low, high)"""
        label_l = label.lower()
        for i, ln in enumerate(lines):
            if label_l in ln.lower():
                for j in range(1, 5):
                    if i + j < len(lines):
                        m = re.search(r'([\d.,]+)\s*[-–]\s*([\d.,]+)', lines[i + j])
                        if m:
                            return _inv_num(m.group(1)), _inv_num(m.group(2))
        return None, None

    # Prix depuis le texte si pas trouvé via data-test
    if not result.get("cours"):
        for ln in lines[:40]:
            v = _inv_num(ln)
            if v and v > 50:   # toutes les valeurs BVC sont > 50 MAD
                result["cours"] = v
                break

    # Variation depuis le texte
    if not result.get("variation"):
        for ln in lines[:40]:
            m = re.search(r'\(([+-]?\d+[.,]\d+)%\)', ln)
            if m:
                result["variation"] = _inv_num(m.group(1))
                break

    # Haut / Bas journalier
    bas, haut = range_val("Ecart journalier")
    if not (bas and haut):
        bas, haut = range_val("Fourchette journalière")
    if haut:
        result["haut"] = haut
    if bas:
        result["bas"] = bas

    # 52 semaines
    bas52, haut52 = range_val("Ecart 52")
    if not (bas52 and haut52):
        bas52, haut52 = range_val("52 sem")
    if haut52:
        result["haut_52s"] = haut52
    if bas52:
        result["bas_52s"] = bas52

    # Volume
    result["volume"]       = val_after("Volume", exclude=["moyen", "échangé moyen"])
    result["volume_moyen"] = val_after("Volume moyen")

    # Données séance
    result["ouverture"]      = val_after("Ouverture")
    result["clot_precedent"] = val_after("Clôture précédente") or val_after("Cloture précédente")

    # Métriques financières
    result["per"]          = val_after("P/E Ratio") or val_after("PER")
    result["bpa"]          = val_after("BPA")
    result["rendement"]    = val_after("Rendement")
    result["capitalisation"] = val_after("Capitalisation")
    result["roe"]          = val_after("ROE")
    result["roa"]          = val_after("ROA")
    result["marge_brute"]  = val_after("Marge brute")
    result["rsi"]          = val_after("RSI")
    result["cours_cible"]  = val_after("Objectif de cours") or val_after("Cours cible")

    print(
        f"[INV] {slug} → cours={result.get('cours')}, "
        f"var={result.get('variation')}, per={result.get('per')}, "
        f"rsi={result.get('rsi')}, cap={result.get('capitalisation')}"
    )
    return result


# ---------------------------------------------------------------------------
# Formatage données pour Claude
# ---------------------------------------------------------------------------
def _format_scraped_for_claude(ticker, sd):
    if not sd or sd.get("source") != "investing":
        return (
            "Données marché non disponibles. "
            "Formule des hypothèses réalistes basées sur le contexte du marché marocain."
        )

    lines = [f"Données financières — fr.investing.com — {sd.get('scraped_at', '')} :\n"]

    # Prix
    if sd.get("cours"):
        var_str = f" ({sd['variation']:+.2f}%)" if sd.get("variation") is not None else ""
        lines.append(f"💰 COURS : {sd['cours']:,.2f} MAD{var_str}")
    if sd.get("haut") and sd.get("bas"):
        lines.append(f"- Séance Haut/Bas : {sd['haut']:,.2f} / {sd['bas']:,.2f} MAD")
    if sd.get("ouverture"):
        lines.append(f"- Ouverture : {sd['ouverture']:,.2f} MAD")
    if sd.get("clot_precedent"):
        lines.append(f"- Clôture précédente : {sd['clot_precedent']:,.2f} MAD")
    if sd.get("volume"):
        lines.append(f"- Volume : {int(sd['volume']):,} titres")
    if sd.get("volume_moyen"):
        lines.append(f"- Volume moyen : {int(sd['volume_moyen']):,} titres")
    if sd.get("haut_52s") and sd.get("bas_52s"):
        lines.append(
            f"- Plage 52 semaines : {sd['bas_52s']:,.2f} → {sd['haut_52s']:,.2f} MAD"
        )

    lines.append("\nMétriques financières :")
    if sd.get("capitalisation"):
        lines.append(f"- Capitalisation : {sd['capitalisation']:,.0f} MAD")
    if sd.get("per"):
        lines.append(f"- PER : {sd['per']:.2f}x")
    if sd.get("bpa"):
        lines.append(f"- BPA (EPS) : {sd['bpa']:.2f} MAD")
    if sd.get("rendement"):
        lines.append(f"- Rendement dividende : {sd['rendement']:.2f}%")
    if sd.get("roe"):
        lines.append(f"- ROE : {sd['roe']:.1f}%")
    if sd.get("roa"):
        lines.append(f"- ROA : {sd['roa']:.1f}%")
    if sd.get("marge_brute"):
        lines.append(f"- Marge brute : {sd['marge_brute']:.1f}%")
    if sd.get("rsi"):
        lines.append(f"- RSI(14) : {sd['rsi']:.1f}")
    if sd.get("cours_cible"):
        lines.append(f"- Objectif de cours analyste : {sd['cours_cible']:,.2f} MAD")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude API — analyse 7 axes
# ---------------------------------------------------------------------------
def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Clé API Anthropic non configurée.")
    return anthropic.Anthropic(api_key=api_key)


def generate_analysis(ticker, sector, sd):
    data_context    = _format_scraped_for_claude(ticker, sd)
    company_context = get_company_context(ticker)
    company_section = f"\n{company_context}\n" if company_context else ""

    # Snapshot prix pour section 1
    price_snapshot = ""
    if sd and sd.get("cours"):
        cours   = sd["cours"]
        var_str = f"{sd['variation']:+.2f}%" if sd.get("variation") is not None else "—"
        haut    = f"{sd['haut']:,.2f}" if sd.get("haut") else "—"
        bas     = f"{sd['bas']:,.2f}" if sd.get("bas") else "—"
        vol     = f"{int(sd['volume']):,}" if sd.get("volume") else "—"
        cible   = f"{sd['cours_cible']:,.2f} MAD" if sd.get("cours_cible") else "—"
        price_snapshot = f"""
**💰 COURS : {cours:,.2f} MAD ({var_str})**
| Indicateur | Valeur |
|---|---|
| Cours actuel | **{cours:,.2f} MAD** |
| Variation séance | {var_str} |
| Haut du jour | {haut} MAD |
| Bas du jour | {bas} MAD |
| Volume | {vol} titres |
| Objectif analyste | {cible} |

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
- PER, ROE, ROA, BPA, rendement dividende (utilise données fournies)
- Capitalisation, valorisation vs secteur et historique
- Forces, faiblesses, risques macro/sectoriels, perspectives

## 📈 3. Analyse technique
- Plage 52 semaines comme support/résistance (données fournies)
- RSI(14) — zone surachat/survente
- Tendance court/moyen terme, supports et résistances clés (MAD)

## ⚡ 4. Momentum
- Tendance de fond, force relative vs MASI
- Signal : 🟢 HAUSSIER | 🟡 NEUTRE | 🔴 BAISSIER

## 🏭 5. Comparaison sectorielle
| Critère | {ticker} | Pair 1 | Pair 2 |
|---|---|---|---|
| PER | | | |
| ROE | | | |
| Rendement div. | | | |

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
    return jsonify({
        "status":      "ok",
        "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


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
        slug   = INVESTING_SLUGS.get(ticker)

        sd = {"source": "none"}
        if slug:
            try:
                sd = scrape_investing(slug)
            except Exception as e:
                print(f"[WARN] investing.com failed for {ticker} ({slug}): {e}")
                sd = {"source": "none", "error": str(e)}
        else:
            print(f"[WARN] No investing.com slug for {ticker}")

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
