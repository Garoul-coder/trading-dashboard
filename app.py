import os
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)

BVC_TICKERS = {
    # Banques
    "ATW": "ATW.CS", "BCP": "BCP.CS", "CIH": "CIH.CS", "BOA": "BOA.CS",
    "CDM": "CDM.CS", "BMCI": "BMCI.CS",
    # Assurances & Financières
    "WAA": "WAA.CS", "ACM": "ACM.CS", "SLF": "SLF.CS", "AFMA": "AFMA.CS",
    # Télécoms & Technologies
    "IAM": "IAM.CS", "M2M": "M2M.CS", "HPS": "HPS.CS",
    "DISWAY": "DIS.CS", "INVOLYS": "INVOL.CS",
    # Mines
    "SMI": "SMI.CS", "MNG": "MNG.CS", "MSA": "MSA.CS",
    # Ciment & BTP
    "CMR": "CMR.CS", "LHM": "LHM.CS", "CMA": "CMA.CS", "STROC": "STROC.CS",
    # Énergie
    "TMA": "TMA.CS", "GAZ": "GAZ.CS", "TQM": "TQM.CS", "MOX": "MOX.CS",
    # Agroalimentaire & Boissons
    "SBM": "SBM.CS", "OUL": "OUL.CS", "FBR": "FBR.CS",
    "LES": "LES.CS", "CSR": "CSR.CS", "MUT": "MUT.CS",
    # Distribution
    "LBV": "LBV.CS",
    # Automobile
    "SAH": "SAH.CS", "ALM": "ALM.CS", "ADH": "ADH.CS",
    # Immobilier
    "DHO": "DHO.CS", "AGC": "AGC.CS", "RDS": "RDS.CS",
    # Industrie
    "SID": "SID.CS", "CCAR": "CCAR.CS", "SNEP": "SNEP.CS", "PRO": "PRO.CS",
    # Transport & Services publics
    "CTM": "CTM.CS", "RIS": "RIS.CS", "LYDEC": "LYDEC.CS", "TIMAR": "TIMAR.CS",
}

# Mapping ticker BVC → ISIN (source : BVCscrap/Notation.py + BVC officiel)
BVC_ISIN = {
    # Banques
    "ATW":    "MA0000012445",  # Attijariwafa Bank
    "BCP":    "MA0000011884",  # Banque Centrale Populaire
    "CIH":    "MA0000011454",  # CIH Bank
    "BOA":    "MA0000012437",  # Bank of Africa (BMCE)
    "CDM":    "MA0000010381",  # Crédit du Maroc
    "BMCI":   "MA0000010811",  # BMCI (BNP Paribas Maroc)
    # Assurances & Financières
    "WAA":    "MA0000010928",  # Wafa Assurance
    "ACM":    "MA0000011710",  # Atlanta (ATLANTASANAD)
    "SLF":    "MA0000011744",  # Salafin
    "AFMA":   "MA0000012296",  # AFMA
    # Télécoms & Technologies
    "IAM":    "MA0000011488",  # Maroc Telecom
    "M2M":    "MA0000011678",  # M2M Group
    "HPS":    "MA0000011611",  # HPS
    "DISWAY": "MA0000011637",  # Disway
    "INVOLYS":"MA0000011579",  # Involys
    # Mines
    "SMI":    "MA0000010068",  # SMI
    "MNG":    "MA0000011058",  # Managem
    # Ciment & BTP
    "CMR":    "MA0000010506",  # Ciments du Maroc
    "LHM":    "MA0000012320",  # LafargeHolcim Maroc
    "STROC":  "MA0000012056",  # Stroc Industrie
    # Énergie
    "TMA":    "MA0000012205",  # TAQA Morocco
    "GAZ":    "MA0000010951",  # Afriquia Gaz
    "TQM":    "MA0000012262",  # Total Maroc
    "MOX":    "MA0000010985",  # Maghreb Oxygène
    # Agroalimentaire
    "SBM":    "MA0000010365",  # Ste Boissons du Maroc
    "OUL":    "MA0000010415",  # Oulmès
    "FBR":    "MA0000011421",  # Dari Couspate
    "LES":    "MA0000012031",  # Lesieur Cristal
    "CSR":    "MA0000012247",  # Cosumar
    "MUT":    "MA0000012395",  # Mutandis
    # Distribution
    "LBV":    "MA0000011801",  # Label Vie
    # Automobile
    "ALM":    "MA0000011009",  # Auto Nejma
    "ADH":    "MA0000010969",  # Auto Hall
    # Immobilier
    "DHO":    "MA0000011512",  # Addoha
    "AGC":    "MA0000011819",  # Alliances Développement
    "RDS":    "MA0000012239",  # Résidences Dar Saada
    # Industrie
    "SID":    "MA0000010019",  # Sonasid
    "CCAR":   "MA0000011868",  # Cartier Saada
    "PRO":    "MA0000011660",  # Promopharm
    "SNEP":   "MA0000011728",  # SNEP
    # Transport & Services
    "CTM":    "MA0000010340",  # CTM
    "RIS":    "MA0000011462",  # Risma
    "TIMAR":  "MA0000011686",  # Timar
}

SECTORS = {
    # Banques
    "ATW": "Banques", "BCP": "Banques", "CIH": "Banques",
    "BOA": "Banques", "CDM": "Banques", "BMCI": "Banques",
    # Assurances & Financières
    "WAA": "Assurances", "ACM": "Assurances", "SLF": "Services financiers", "AFMA": "Services financiers",
    # Télécoms & Technologies
    "IAM": "Télécommunications", "M2M": "Technologies",
    "HPS": "Technologies", "DISWAY": "Technologies", "INVOLYS": "Technologies",
    # Mines
    "SMI": "Mines", "MNG": "Mines", "MSA": "Mines",
    # Ciment & BTP
    "CMR": "Matériaux de construction", "LHM": "Matériaux de construction",
    "CMA": "Matériaux de construction", "STROC": "BTP",
    # Énergie
    "TMA": "Énergie", "GAZ": "Énergie", "TQM": "Énergie", "MOX": "Énergie",
    # Agroalimentaire
    "SBM": "Agroalimentaire", "OUL": "Agroalimentaire", "FBR": "Agroalimentaire",
    "LES": "Agroalimentaire", "CSR": "Agroalimentaire", "MUT": "Agroalimentaire",
    # Distribution
    "LBV": "Distribution",
    # Automobile
    "SAH": "Automobile", "ALM": "Automobile", "ADH": "Automobile",
    # Immobilier
    "DHO": "Immobilier", "AGC": "Immobilier", "RDS": "Immobilier",
    # Industrie
    "SID": "Industrie", "CCAR": "Industrie", "SNEP": "Industrie", "PRO": "Pharmacie",
    # Transport & Services
    "CTM": "Transport", "RIS": "Tourisme & Loisirs",
    "LYDEC": "Services publics", "TIMAR": "Logistique",
}

# Fiches sociétés — source : Bourse de Casablanca + rapports publics
COMPANY_PROFILES = {
    "SMI": {
        "nom": "Société Métallurgique d'Imiter (SMI)",
        "groupe": "Groupe Managem (filiale)",
        "activite": "Exploitation de la mine d'argent d'Imiter, dans la région de Tinghir (Drâa-Tafilalet). Première mine d'argent d'Afrique. Produit également du zinc et du plomb en sous-produits.",
        "concurrents": "Managem (MNG), LafargeHolcim Maroc (LHM), autres filiales minières du groupe OCP",
        "particularites": "SMI est l'actif minier d'argent le plus important du Maroc. Très sensible au cours international de l'argent (XAG/USD). Réserves prouvées et probables importantes sur le gisement d'Imiter.",
    },
    "MNG": {
        "nom": "Managem",
        "groupe": "Groupe ONA / SNI",
        "activite": "Groupe minier marocain diversifié : or, argent, cobalt, cuivre, zinc, fluorine. Opère au Maroc, en Afrique subsaharienne (Côte d'Ivoire, Gabon, Éthiopie, RDC, Soudan) et en Amérique latine.",
        "concurrents": "OCP (phosphates), SMI (filiale), sociétés minières africaines internationales",
        "particularites": "Leader minier marocain coté à la BVC. Fortement exposé aux cours des métaux (cobalt, or, argent). Stratégie d'expansion panafricaine.",
    },
    "ATW": {
        "nom": "Attijariwafa Bank",
        "groupe": "Groupe ONA / SNI",
        "activite": "Premier groupe bancaire et financier du Maroc. Banque universelle : banque de détail, corporate, marchés de capitaux, assurance (Wafa Assurance), immobilier. Présent dans 27 pays africains.",
        "concurrents": "Banque Centrale Populaire (BCP), BMCE Bank of Africa (BOA), CIH Bank, Société Générale Maroc",
        "particularites": "Plus grande capitalisation boursière de la BVC. Leader du crédit au Maroc. Forte expansion en Afrique subsaharienne et Afrique de l'Ouest.",
    },
    "BCP": {
        "nom": "Banque Centrale Populaire (BCP)",
        "groupe": "Groupe Banque Populaire (Crédit Populaire du Maroc)",
        "activite": "Banque coopérative de premier plan. Réseau de Banques Populaires Régionales. Banque des MRE (Marocains Résidant à l'Étranger), PME et particuliers. Présente en Afrique subsaharienne.",
        "concurrents": "Attijariwafa Bank (ATW), BMCE Bank of Africa (BOA), CIH Bank",
        "particularites": "Deuxième groupe bancaire marocain. Fort ancrage dans les régions. Part de marché solide sur les dépôts MRE.",
    },
    "IAM": {
        "nom": "Itissalat Al-Maghrib (Maroc Telecom)",
        "groupe": "Groupe Vivendi / Émirats Télécommunications (e&)",
        "activite": "Opérateur télécom historique du Maroc. Services mobiles, fixe, internet haut débit (Maroc Fibre), data centers, solutions IT pour entreprises. Présent dans 8 pays africains (Mauritanie, Mali, Burkina Faso, Gabon, Côte d'Ivoire, Bénin, Togo, Niger).",
        "concurrents": "Orange Maroc, Inwi (groupe Al Mada)",
        "particularites": "Opérateur dominant avec la plus grande part de marché mobile et fixe au Maroc. Dividende généreux historiquement. Croissance portée par l'Afrique subsaharienne.",
    },
    "CIH": {
        "nom": "CIH Bank",
        "groupe": "Caisse de Dépôt et de Gestion (CDG)",
        "activite": "Banque de détail orientée crédit immobilier, crédit à la consommation, TPE/PME. Développement du digital banking (CIH Online). Filiale de la CDG.",
        "concurrents": "Attijariwafa Bank, BCP, BMCE Bank of Africa, Société Générale Maroc",
        "particularites": "Positionnée sur le segment immobilier et digital. En forte transformation numérique. Profil de croissance dynamique parmi les banques de taille moyenne.",
    },
    "BOA": {
        "nom": "BMCE Bank of Africa",
        "groupe": "Groupe FinanceCom (famille Othman Benjelloun)",
        "activite": "Banque universelle marocaine avec forte présence panafricaine (20+ pays). Banque de détail, corporate, marchés, trade finance. Partenariat avec CIC (Crédit Mutuel) en France.",
        "concurrents": "Attijariwafa Bank (ATW), Banque Centrale Populaire (BCP)",
        "particularites": "Troisième groupe bancaire marocain. Pionnier de la bancarisation en Afrique subsaharienne via Bank of Africa.",
    },
    "HPS": {
        "nom": "Hightech Payment Systems (HPS)",
        "groupe": "Indépendant (fondateurs)",
        "activite": "Éditeur de logiciels de paiement électronique. Solution phare : PowerCARD (gestion de cartes bancaires, monétique, paiement mobile). Clients dans 90+ pays sur 5 continents.",
        "concurrents": "Sociétés internationales de fintech (Fiserv, FIS, Temenos), concurrents locaux",
        "particularites": "Champion marocain de la fintech à l'international. Revenus récurrents via licences et maintenance. Forte croissance à l'export.",
    },
    "TMA": {
        "nom": "Taqa Morocco (ex-ONE)",
        "groupe": "Abu Dhabi National Energy Company (TAQA) — 72,6%",
        "activite": "Production d'électricité à partir de la centrale thermique à charbon de Jorf Lasfar (2 760 MW installés). Vente exclusive à l'ONEE (Office National de l'Électricité).",
        "concurrents": "ONEE (monopole distribution), autres producteurs indépendants (IPP)",
        "particularites": "Contrat d'achat d'électricité (PPA) à long terme avec l'ONEE. Revenus prévisibles et stables. Fort rendement du dividende. Sensible au prix du charbon et au taux de change (USD).",
    },
    "CMR": {
        "nom": "Ciments du Maroc (CimMaroc)",
        "groupe": "Groupe Heidelberg Materials (ex-HeidelbergCement) — majoritaire",
        "activite": "Production et commercialisation de ciment, béton prêt à l'emploi, granulats et chaux. Deuxième cimentier du Maroc. Usines à Aït Baha, Marrakech et Safi.",
        "concurrents": "LafargeHolcim Maroc (LHM), Asment de Témara, Cimat",
        "particularites": "Très sensible à l'activité BTP et aux programmes d'infrastructure de l'État marocain. Bénéficiaire potentiel de la reconstruction post-séisme d'Al Haouz et du Mondial 2030.",
    },
    "LHM": {
        "nom": "LafargeHolcim Maroc",
        "groupe": "Holcim Group (Suisse) — majoritaire",
        "activite": "Leader du ciment au Maroc. Production de ciment, béton, granulats, mortiers et solutions de construction. Présent sur tout le territoire national.",
        "concurrents": "Ciments du Maroc (CMR), Asment de Témara, Cimat",
        "particularites": "Premier cimentier marocain. Stratégie de décarbonation (ciment bas carbone). Fort levier sur les grands chantiers d'infrastructure (autoroutes, logements, Coupe du Monde 2030).",
    },
    "GAZ": {
        "nom": "Afriquia Gaz",
        "groupe": "Groupe Akwa (famille Akhannouch)",
        "activite": "Distribution et commercialisation de gaz de pétrole liquéfié (GPL) : butane, propane. Leader du marché du gaz au Maroc. Conditionnement en bouteilles et vrac.",
        "concurrents": "Maghreb Oxygène, Total Énergies Maroc, Vivo Energy",
        "particularites": "Monopole partiel sur le GPL au Maroc. Prix subventionnés par l'État (butane). Fort dividende. Actionnaire principal : Groupe Akwa.",
    },
    "WAA": {
        "nom": "Wafa Assurance",
        "groupe": "Attijariwafa Bank (filiale)",
        "activite": "Compagnie d'assurance multibranche : vie, non-vie, assurance-crédit, santé. Distribution via le réseau Attijariwafa Bank (bancassurance) et courtiers.",
        "concurrents": "RMA (filiale FinanceCom), Saham Assurance (Sanlam), AXA Assurance Maroc",
        "particularites": "Leader de l'assurance au Maroc. Forte synergie avec Attijariwafa Bank. Croissance portée par l'assurance-vie et la bancassurance.",
    },
    "SBM": {
        "nom": "Société des Brasseries du Maroc (SBM)",
        "groupe": "Castel Group (France) — actionnaire majoritaire",
        "activite": "Production et distribution de boissons : bières (Flag, Casablanca, Heineken sous licence), eaux minérales (Sidi Ali), boissons gazeuses et jus. Leader des boissons alcoolisées au Maroc.",
        "concurrents": "CBGN (Compagnie des Boissons Gazeuses du Nord), Coca-Cola Maroc, Pepsi",
        "particularites": "Secteur régulé au Maroc (alcool soumis à taxes élevées). Fort pricing power. Dividende généreux.",
    },
    "FBR": {
        "nom": "Dari Couspate (ex-Farine de Blé Riche)",
        "groupe": "Indépendant",
        "activite": "Production et commercialisation de semoule, couscous, pâtes alimentaires et farine. Marques : Dari, Couspate. Distribution nationale et export.",
        "concurrents": "Meknès (groupe Zouiten), Sonasid (acier — différent secteur), minoteries régionales",
        "particularites": "Niche agroalimentaire marocaine avec forte marque locale. Sensible aux cours du blé dur importé.",
    },
    "CDM": {
        "nom": "Crédit du Maroc",
        "groupe": "Groupe Crédit Agricole (France) — majoritaire",
        "activite": "Banque de détail et corporate au Maroc. Réseau national d'agences. Services aux particuliers, professionnels et entreprises. Filiale de Crédit Agricole SA.",
        "concurrents": "Attijariwafa Bank, BCP, BMCE Bank of Africa, Société Générale Maroc",
        "particularites": "Banque de taille moyenne en transformation. Adossée à Crédit Agricole (expertise internationale). Profil défensif.",
    },
    "SAH": {
        "nom": "Société Automobile Haddioui (SAH Liwa)",
        "groupe": "Famille Haddioui",
        "activite": "Distribution automobile : concessionnaire de marques (Renault, Dacia). Vente de véhicules neufs et occasion, financement, après-vente et pièces de rechange.",
        "concurrents": "Auto Nejma, Sopriam (Peugeot-Citroën), SMEIA (BMW), Omar Zniber",
        "particularites": "Sensible au marché automobile marocain, aux taux d'intérêt (crédit auto) et à la politique d'importation.",
    },
    "DHO": {
        "nom": "Douja Promotion Groupe Addoha",
        "groupe": "Famille Anas Sefrioui",
        "activite": "Premier promoteur immobilier marocain. Logement social, économique, moyen et haut standing. Présence en Afrique subsaharienne (Côte d'Ivoire, Sénégal, Ghana, Cameroun).",
        "concurrents": "Alliances Développement Immobilier (ADI), Résidences Dar Saada",
        "particularites": "Très sensible aux politiques de logement social de l'État marocain. Restructuration de la dette en cours. Fort endettement historique.",
    },
    "CTM": {
        "nom": "CTM (Compagnie de Transport au Maroc)",
        "groupe": "Groupe FinanceCom (actionnaire)",
        "activite": "Transport routier de voyageurs au Maroc et vers l'Europe (Maroc-France-Espagne-Belgique). Réseau national de gares routières. Services premium et économiques.",
        "concurrents": "Supratours (ONCF), transporteurs privés régionaux, compagnies aériennes low-cost",
        "particularites": "Quasi-monopole sur les liaisons longue distance de qualité. Bénéficiaire de la croissance du tourisme et des MRE.",
    },
}


def get_company_context(ticker):
    """Return company profile string for the prompt."""
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
    return "Fiche société (source : Bourse de Casablanca / rapports publics) :\n" + "\n".join(lines)


def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Clé API Anthropic non configurée.")
    return anthropic.Anthropic(api_key=api_key)


def moving_avg(data, n):
    if len(data) < n:
        return None
    return round(sum(data[-n:]) / n, 2)


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


_M24_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://medias24.com/",
    "Accept":     "application/json, text/plain, */*",
}


def _build_weekly_result(dates, closes, volumes, source):
    """Build the standard weekly result dict from sorted daily arrays."""
    current  = closes[-1]
    n        = len(closes)
    return {
        "data_available": True,
        "source":         source,
        "current_price":  current,
        "change_1mo":  round((current - closes[-4])  / closes[-4]  * 100, 2) if n >= 4  else None,
        "change_3mo":  round((current - closes[-13]) / closes[-13] * 100, 2) if n >= 13 else None,
        "change_1y":   round((current - closes[0])   / closes[0]   * 100, 2),
        "ma10":  moving_avg(closes, 10),
        "ma20":  moving_avg(closes, 20),
        "ma50":  moving_avg(closes, 50),
        "rsi":   calc_rsi(closes),
        "high_52w": round(max(closes), 2),
        "low_52w":  round(min(closes), 2),
        "chart_data": {"dates": dates, "prices": closes, "volumes": volumes},
    }


def get_weekly_data_medias24(isin):
    """Fetch 1-year daily history from medias24.com and aggregate to weekly closes."""
    end_dt   = datetime.utcnow()
    start_dt = end_dt - timedelta(days=370)
    url = (
        "https://medias24.com/content/api?method=getPriceHistory"
        f"&ISIN={isin}&format=json"
        f"&from={start_dt.strftime('%Y-%m-%d')}"
        f"&to={end_dt.strftime('%Y-%m-%d')}"
    )
    resp = requests.get(url, headers=_M24_HEADERS, timeout=15)
    resp.raise_for_status()
    raw = resp.json()

    # Normalise: accept list or dict wrapping
    rows = raw if isinstance(raw, list) else None
    if rows is None and isinstance(raw, dict):
        for key in ("content", "data", "prices", "history", "result"):
            val = raw.get(key)
            if isinstance(val, list):
                rows = val
                break
            if isinstance(val, dict):
                for v2 in val.values():
                    if isinstance(v2, list):
                        rows = v2
                        break
    if not rows:
        return None

    # Parse each daily record (field names vary by API version)
    daily = []
    for row in rows:
        date_s  = (row.get("d") or row.get("Date") or row.get("date") or
                   row.get("Timestamp") or "")
        close_v = (row.get("v") or row.get("Value") or row.get("value") or
                   row.get("Close") or row.get("close"))
        vol_v   = (row.get("vol") or row.get("Vol") or row.get("Volume") or
                   row.get("volume") or 0)
        if not date_s or close_v is None:
            continue
        try:
            daily.append((str(date_s)[:10], round(float(close_v), 2), int(float(vol_v or 0))))
        except (ValueError, TypeError):
            continue

    if len(daily) < 4:
        return None

    daily.sort(key=lambda x: x[0])

    # Keep last close of each ISO week → weekly series
    weekly = {}
    for date_s, close_v, vol_i in daily:
        try:
            dt       = datetime.strptime(date_s, "%Y-%m-%d")
            week_key = dt.strftime("%G-W%V")        # ISO week
            weekly[week_key] = (date_s, close_v, vol_i)
        except ValueError:
            continue

    if len(weekly) < 4:
        return None

    sorted_w = sorted(weekly.items())
    dates   = [v[0] for _, v in sorted_w]
    closes  = [v[1] for _, v in sorted_w]
    volumes = [v[2] for _, v in sorted_w]
    return _build_weekly_result(dates, closes, volumes, "medias24")


def get_weekly_data_yahoo(ticker):
    """Fetch 1-year weekly data from Yahoo Finance (fallback)."""
    yf_ticker = BVC_TICKERS.get(ticker, f"{ticker}.CS")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
        f"?interval=1wk&range=1y"
    )
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    result = payload["chart"]["result"]
    if not result:
        return None

    r          = result[0]
    timestamps = r.get("timestamp", [])
    quotes     = r["indicators"]["quote"][0]
    closes_raw = quotes.get("close", [])
    volumes_raw= quotes.get("volume", [])

    rows = [(t, c, v or 0)
            for t, c, v in zip(timestamps, closes_raw, volumes_raw)
            if c is not None]
    if len(rows) < 4:
        return None

    dates   = [datetime.utcfromtimestamp(t).strftime("%Y-%m-%d") for t, c, v in rows]
    closes  = [round(c, 2) for t, c, v in rows]
    volumes = [int(v)      for t, c, v in rows]
    return _build_weekly_result(dates, closes, volumes, "yahoo")


def get_weekly_data(ticker):
    """Try medias24 first (données BVC réelles), fallback Yahoo Finance."""
    isin = BVC_ISIN.get(ticker)
    if isin:
        try:
            result = get_weekly_data_medias24(isin)
            if result:
                print(f"[DATA] {ticker} → medias24 ({len(result['chart_data']['prices'])} semaines)")
                return result
        except Exception as e:
            print(f"[WARN] medias24 failed for {ticker} ({isin}): {e}")

    try:
        result = get_weekly_data_yahoo(ticker)
        if result:
            print(f"[DATA] {ticker} → Yahoo Finance")
            return result
    except Exception as e:
        print(f"[ERROR] Yahoo Finance failed for {ticker}: {e}")

    return {"data_available": False}


def generate_analysis(ticker, sector, sd):
    if sd and sd.get("data_available"):
        source_label = "Bourse de Casablanca via medias24" if sd.get("source") == "medias24" else "Yahoo Finance"
        data_context = f"""
Données de clôture hebdomadaires — 1 an (source : {source_label}) :
- 💰 Prix de clôture actuel : **{sd['current_price']} MAD**
- Performance 1 mois    : {sd['change_1mo']:+.2f}%
- Performance 3 mois    : {sd['change_3mo']:+.2f}%
- Performance 1 an      : {sd['change_1y']:+.2f}%
- MM10 (hebdo)          : {sd['ma10']} MAD
- MM20 (hebdo)          : {sd['ma20']} MAD
- MM50 (hebdo)          : {sd['ma50']} MAD
- RSI hebdomadaire (14) : {sd['rsi']}
- Plus haut 52 semaines : {sd['high_52w']} MAD
- Plus bas  52 semaines : {sd['low_52w']} MAD
"""
        price_snapshot = f"""
**💰 COURS ACTUEL : {sd['current_price']} MAD**
| Indicateur | Valeur |
|---|---|
| Cours actuel | **{sd['current_price']} MAD** |
| Plus haut 52 sem. | {sd['high_52w']} MAD |
| Plus bas 52 sem. | {sd['low_52w']} MAD |
| Performance 1 mois | {sd['change_1mo']:+.2f}% |
| Performance 1 an | {sd['change_1y']:+.2f}% |
| RSI (14) | {sd['rsi']} |
| MM20 / MM50 | {sd['ma20']} / {sd['ma50']} MAD |

"""
    else:
        data_context = "Données marché non disponibles. Formule des hypothèses réalistes basées sur le contexte du marché marocain."
        price_snapshot = ""

    company_context = get_company_context(ticker)
    company_section = f"\n{company_context}\n" if company_context else ""

    prompt = f"""Tu es un analyste financier expert des marchés émergents, spécialisé dans la Bourse de Casablanca (BVC).
Ta mission est de produire une analyse complète, professionnelle et orientée décision, digne d'un rapport de broker marocain.

Ticker : **{ticker}** | Secteur : {sector}
{company_section}
{data_context}

Génère l'analyse complète avec EXACTEMENT cette structure :

## 🔎 1. Présentation de la société
{price_snapshot}
Utilise STRICTEMENT la fiche société fournie ci-dessus (si disponible) pour les informations suivantes :
- Nom complet et activité principale (respecte scrupuleusement la description fournie)
- Groupe d'appartenance et actionnariat
- Positionnement sur le marché marocain
- Principaux concurrents locaux
- Points de différenciation clés

## 📊 2. Analyse fondamentale

### a) Résultats financiers récents
- Chiffre d'affaires et évolution YoY
- Résultat net et évolution YoY
- Marges EBITDA et nette
- Éléments marquants de l'exercice

### b) Ratios clés
- PER, ROE, Dette/EBITDA
- Rendement du dividende
- Valorisation vs historique : sur-valorisé ou sous-valorisé ?

### c) Analyse qualitative
- Forces et avantages concurrentiels
- Faiblesses
- Risques (macro, sectoriels, spécifiques Maroc)
- Perspectives de croissance

## 📈 3. Analyse technique (basée sur les données hebdomadaires 1 an)

### a) Tendance
- Court terme (4-8 semaines)
- Moyen terme (3-6 mois)
- Long terme (12 mois)

### b) Indicateurs techniques
- MM10 / MM20 / MM50 hebdomadaires : croisements et signaux
- RSI hebdomadaire : niveau, zone (survente/surachat/neutre)
- MACD : configuration haussière ou baissière
- Volumes : accumulation ou distribution

### c) Niveaux clés
- Supports principaux (en MAD)
- Résistances principales (en MAD)
- Situation actuelle : breakout, consolidation ou retournement ?

## ⚡ 4. Signaux de momentum
- Tendance de fond : accélération ou ralentissement
- Force relative vs indice MASI
- Signal global : 🟢 HAUSSIER | 🟡 NEUTRE | 🔴 BAISSIER

## 🏭 5. Comparaison sectorielle
- Comparer {ticker} avec 2-3 pairs marocains du secteur {sector}
- Tableau comparatif : croissance, rentabilité, valorisation
- Conclusion : leader ou retardataire ?

## 🧾 6. Opinion d'investissement
- Recommandation : **ACHAT FORT** | **ACHAT** | **CONSERVER** | **ALLÉGER** | **VENTE**
- Horizon : court / moyen / long terme
- Prix cible à 12 mois (en MAD)
- Niveau de risque : Faible | Moyen | Élevé
- 3 à 5 arguments clés

## 🧠 7. Résumé exécutif
5 à 7 lignes maximum. Synthèse orientée décision, style flash note de broker.

---
Règles : français uniquement · bullet points · données chiffrées si disponibles · hypothèses réalistes sinon."""

    client = get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


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
        sd = get_weekly_data(ticker)
        analysis = generate_analysis(ticker, sector, sd)

        return jsonify({
            "ticker":     ticker,
            "sector":     sector,
            "stock_data": sd,
            "analysis":   analysis,
            "data_source": sd.get("source", "none") if sd else "none",
        })
    except Exception as e:
        print(f"[ERROR] /analyze: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
