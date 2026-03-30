import os
import math
import yfinance as yf
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)

# Mapping tickers BVC -> Yahoo Finance
BVC_TICKERS = {
    "ATW": "ATW.CS", "IAM": "IAM.CS", "BCP": "BCP.CS", "CIH": "CIH.CS",
    "BOA": "BOA.CS", "CMR": "CMR.CS", "HPS": "HPS.CS", "SMI": "SMI.CS",
    "TMA": "TMA.CS", "GAZ": "GAZ.CS", "MNG": "MNG.CS", "WAA": "WAA.CS",
    "CDM": "CDM.CS", "SBM": "SBM.CS", "FBR": "FBR.CS", "ADH": "ADH.CS",
    "LHM": "LHM.CS", "ACM": "ACM.CS", "AGC": "AGC.CS", "DHO": "DHO.CS",
    "SAH": "SAH.CS", "JET": "JET.CS", "RDS": "RDS.CS", "CTM": "CTM.CS",
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


def safe(val, decimals=2):
    """Convert numpy/pandas scalar to a JSON-safe Python type."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None


def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Clé API Anthropic non configurée sur le serveur.")
    return anthropic.Anthropic(api_key=api_key)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Requête invalide"}), 400

        ticker = str(data.get("ticker", "")).upper().strip()
        if not ticker:
            return jsonify({"error": "Veuillez entrer un ticker valide"}), 400
        if len(ticker) > 10:
            return jsonify({"error": "Ticker invalide"}), 400

        sector = SECTORS.get(ticker, "Secteur divers")
        stock_data = get_stock_data(ticker)
        analysis = generate_analysis(ticker, stock_data, sector)

        return jsonify({
            "ticker": ticker,
            "sector": sector,
            "stock_data": stock_data,
            "analysis": analysis,
        })

    except Exception as e:
        print(f"[ERROR] /analyze : {e}")
        return jsonify({"error": str(e)}), 500


def get_stock_data(ticker):
    yf_ticker = BVC_TICKERS.get(ticker, f"{ticker}.CS")
    try:
        stock = yf.Ticker(yf_ticker)
        hist = stock.history(period="6mo")

        if hist.empty:
            return {"data_available": False}

        info = {}
        try:
            info = stock.info or {}
        except Exception:
            pass

        close = hist["Close"]
        current_price = float(close.iloc[-1])

        ma20 = safe(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
        ma50 = safe(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None

        # RSI
        rsi = None
        if len(close) >= 14:
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            rsi = safe((100 - 100 / (1 + rs)).iloc[-1])

        price_1mo = float(close.iloc[-22]) if len(close) >= 22 else float(close.iloc[0])
        price_3mo = float(close.iloc[-66]) if len(close) >= 66 else float(close.iloc[0])
        change_1mo = safe((current_price - price_1mo) / price_1mo * 100)
        change_3mo = safe((current_price - price_3mo) / price_3mo * 100)

        # Chart — convert everything to plain Python types
        hist_90 = hist.tail(90)
        chart_data = {
            "dates": hist_90.index.strftime("%Y-%m-%d").tolist(),
            "prices": [safe(p) for p in hist_90["Close"].tolist()],
            "volumes": [int(v) if not math.isnan(float(v)) else 0
                        for v in hist_90["Volume"].tolist()],
        }

        return {
            "data_available": True,
            "current_price": safe(current_price),
            "change_1mo": change_1mo,
            "change_3mo": change_3mo,
            "ma20": ma20,
            "ma50": ma50,
            "rsi": rsi,
            "high_52w": safe(info.get("fiftyTwoWeekHigh")),
            "low_52w": safe(info.get("fiftyTwoWeekLow")),
            "market_cap": int(info["marketCap"]) if info.get("marketCap") else None,
            "pe_ratio": safe(info.get("trailingPE")),
            "dividend_yield": safe((info.get("dividendYield") or 0) * 100),
            "chart_data": chart_data,
        }

    except Exception as e:
        print(f"[ERROR] get_stock_data({ticker}): {e}")
        return {"data_available": False}


def generate_analysis(ticker, stock_data, sector):
    if stock_data and stock_data.get("data_available"):
        data_context = f"""
Données de marché en temps réel :
- Prix actuel      : {stock_data['current_price']} MAD
- Variation 1 mois : {stock_data['change_1mo']:+.2f}%
- Variation 3 mois : {stock_data['change_3mo']:+.2f}%
- MM20             : {stock_data['ma20']} MAD
- MM50             : {stock_data['ma50']} MAD
- RSI (14)         : {stock_data['rsi']}
- 52 sem. haut     : {stock_data['high_52w']} MAD
- 52 sem. bas      : {stock_data['low_52w']} MAD
- Capitalisation   : {stock_data['market_cap']} MAD
- PER              : {stock_data['pe_ratio']}
- Rendement div.   : {stock_data['dividend_yield']}%
"""
    else:
        data_context = "Données de marché en temps réel non disponibles. Basez-vous sur vos connaissances de cette société cotée à la BVC."

    prompt = f"""Tu es un analyste financier senior expert de la Bourse de Casablanca (BVC).
Fournis une analyse professionnelle et structurée en français pour le titre **{ticker}** (secteur : {sector}).

{data_context}

Génère exactement les 4 sections suivantes :

## 📊 Résumé des Résultats Financiers
Analyse les performances financières récentes : chiffre d'affaires, résultat net, marges, endettement, dividendes.
Commente la trajectoire de croissance et les perspectives.

## 📈 Signaux Momentum
Analyse technique : RSI, MM20/MM50, momentum 1 et 3 mois, supports/résistances.
Indique pour chaque signal : 🟢 HAUSSIER | 🟡 NEUTRE | 🔴 BAISSIER

## 💡 Opinion d'Investissement
Recommandation : ACHAT FORT | ACHAT | NEUTRE | VENTE | VENTE FORTE
Prix cible 12 mois, risques principaux, profil investisseur.

## 🏭 Comparaison Sectorielle
Compare {ticker} avec ses pairs BVC du secteur {sector} : valorisation, positionnement, catalyseurs.

Réponds intégralement en français."""

    client = get_client()
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
