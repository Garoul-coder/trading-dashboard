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
    "SAH": "SAH.CS", "CTM": "CTM.CS",
}

SECTORS = {
    "ATW": "Banques", "BCP": "Banques", "CIH": "Banques",
    "BOA": "Banques", "CDM": "Banques",
    "IAM": "Télécommunications",
    "CMR": "Matériaux de construction", "LHM": "Matériaux de construction",
    "HPS": "Technologies", "SAH": "Automobile",
    "SMI": "Mines", "MNG": "Mines",
    "TMA": "Énergie", "GAZ": "Énergie",
    "WAA": "Assurances", "ACM": "Assurances",
    "FBR": "Agroalimentaire", "SBM": "Agroalimentaire",
    "DHO": "Distribution", "CTM": "Transport",
}


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

    prompt = f"""Tu es un analyste financier expert des marchés émergents, spécialisé dans la Bourse de Casablanca (BVC).
Ta mission est de produire une analyse complète, professionnelle et orientée décision, digne d'un rapport de broker marocain.

Ticker : **{ticker}** | Secteur : {sector}

{data_context}

Génère l'analyse complète avec EXACTEMENT cette structure :

## 🔎 1. Présentation de la société
- Nom complet et activité principale
- Positionnement sur le marché marocain
- Principaux concurrents locaux

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
