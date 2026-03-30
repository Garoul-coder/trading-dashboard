import os
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)

BVC_TICKERS = {
    "ATW": "ATW.CS", "IAM": "IAM.CS", "BCP": "BCP.CS", "CIH": "CIH.CS",
    "BOA": "BOA.CS", "CMR": "CMR.CS", "HPS": "HPS.CS", "SMI": "SMI.CS",
    "TMA": "TMA.CS", "GAZ": "GAZ.CS", "MNG": "MNG.CS", "WAA": "WAA.CS",
    "CDM": "CDM.CS", "SBM": "SBM.CS", "FBR": "FBR.CS", "ADH": "ADH.CS",
    "LHM": "LHM.CS", "ACM": "ACM.CS", "AGC": "AGC.CS", "DHO": "DHO.CS",
    "SAH": "SAH.CS", "CTM": "CTM.CS", "MSA": "MSA.CS", "TQM": "TQM.CS",
    "RIS": "RIS.CS", "OUL": "OUL.CS", "M2M": "M2M.CS", "ALM": "ALM.CS",
}

SECTORS = {
    "ATW": "Banques", "BCP": "Banques", "CIH": "Banques",
    "BOA": "Banques", "CDM": "Banques",
    "IAM": "Télécommunications", "M2M": "Technologies",
    "CMR": "Matériaux de construction", "LHM": "Matériaux de construction",
    "HPS": "Technologies", "TQM": "Services",
    "SAH": "Automobile", "ALM": "Automobile",
    "SMI": "Mines", "MNG": "Mines", "MSA": "Mines",
    "TMA": "Énergie", "GAZ": "Énergie",
    "WAA": "Assurances", "ACM": "Assurances", "RIS": "Assurances",
    "FBR": "Agroalimentaire", "SBM": "Agroalimentaire", "OUL": "Agroalimentaire",
    "DHO": "Distribution", "CTM": "Transport", "AGC": "Immobilier",
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


def get_weekly_data(ticker):
    yf_ticker = BVC_TICKERS.get(ticker, f"{ticker}.CS")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
        f"?interval=1wk&range=1y"
    )
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        result = payload["chart"]["result"]
        if not result:
            return {"data_available": False}

        r = result[0]
        timestamps = r.get("timestamp", [])
        quotes = r["indicators"]["quote"][0]
        closes_raw = quotes.get("close", [])
        volumes_raw = quotes.get("volume", [])

        # Filter nulls
        rows = [
            (t, c, v or 0)
            for t, c, v in zip(timestamps, closes_raw, volumes_raw)
            if c is not None
        ]
        if len(rows) < 4:
            return {"data_available": False}

        dates   = [datetime.utcfromtimestamp(t).strftime("%Y-%m-%d") for t, c, v in rows]
        closes  = [round(c, 2) for t, c, v in rows]
        volumes = [int(v) for t, c, v in rows]

        current = closes[-1]
        high_52w = round(max(closes), 2)
        low_52w  = round(min(closes), 2)

        change_1mo = round((current - closes[-4])  / closes[-4]  * 100, 2) if len(closes) >= 4  else None
        change_3mo = round((current - closes[-13]) / closes[-13] * 100, 2) if len(closes) >= 13 else None
        change_1y  = round((current - closes[0])   / closes[0]   * 100, 2)

        ma10 = moving_avg(closes, 10)
        ma20 = moving_avg(closes, 20)
        ma50 = moving_avg(closes, 50)
        rsi  = calc_rsi(closes)

        return {
            "data_available": True,
            "current_price": current,
            "change_1mo": change_1mo,
            "change_3mo": change_3mo,
            "change_1y": change_1y,
            "ma10": ma10,
            "ma20": ma20,
            "ma50": ma50,
            "rsi": rsi,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "chart_data": {"dates": dates, "prices": closes, "volumes": volumes},
        }
    except Exception as e:
        print(f"[ERROR] get_weekly_data({ticker}): {e}")
        return {"data_available": False}


def generate_analysis(ticker, sector, sd):
    if sd and sd.get("data_available"):
        data_context = f"""
Données de clôture hebdomadaires — 1 an (Yahoo Finance) :
- Prix de clôture actuel : {sd['current_price']} MAD
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
    else:
        data_context = "Données marché non disponibles. Formule des hypothèses réalistes basées sur le contexte du marché marocain."

    company_context = get_company_context(ticker)
    company_section = f"\n{company_context}\n" if company_context else ""

    prompt = f"""Tu es un analyste financier expert des marchés émergents, spécialisé dans la Bourse de Casablanca (BVC).
Ta mission est de produire une analyse complète, professionnelle et orientée décision, digne d'un rapport de broker marocain.

Ticker : **{ticker}** | Secteur : {sector}
{company_section}
{data_context}

Génère l'analyse complète avec EXACTEMENT cette structure :

## 🔎 1. Présentation de la société
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
            "ticker": ticker,
            "sector": sector,
            "stock_data": sd,
            "analysis": analysis,
        })
    except Exception as e:
        print(f"[ERROR] /analyze: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
