import os
import json
import yfinance as yf
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    ticker = data.get("ticker", "").upper().strip()

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


def get_stock_data(ticker):
    yf_ticker = BVC_TICKERS.get(ticker, f"{ticker}.CS")
    try:
        stock = yf.Ticker(yf_ticker)
        hist = stock.history(period="6mo")
        info = stock.info

        if hist.empty:
            return {"data_available": False}

        close = hist["Close"]
        current_price = close.iloc[-1]

        # Moving averages
        ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else None
        ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - 100 / (1 + rs)).iloc[-1] if len(close) >= 14 else None

        # Performance
        price_1mo = close.iloc[-22] if len(close) >= 22 else close.iloc[0]
        price_3mo = close.iloc[-66] if len(close) >= 66 else close.iloc[0]
        change_1mo = (current_price - price_1mo) / price_1mo * 100
        change_3mo = (current_price - price_3mo) / price_3mo * 100

        # Chart data (last 90 trading days)
        hist_90 = hist.tail(90)
        chart_data = {
            "dates": hist_90.index.strftime("%Y-%m-%d").tolist(),
            "prices": [round(p, 2) for p in hist_90["Close"].tolist()],
            "volumes": hist_90["Volume"].tolist(),
        }

        return {
            "data_available": True,
            "current_price": round(current_price, 2),
            "change_1mo": round(change_1mo, 2),
            "change_3mo": round(change_3mo, 2),
            "ma20": round(ma20, 2) if ma20 else None,
            "ma50": round(ma50, 2) if ma50 else None,
            "rsi": round(float(rsi), 2) if rsi else None,
            "high_52w": round(info.get("fiftyTwoWeekHigh", 0), 2),
            "low_52w": round(info.get("fiftyTwoWeekLow", 0), 2),
            "market_cap": info.get("marketCap"),
            "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else None,
            "dividend_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
            "chart_data": chart_data,
        }
    except Exception as e:
        print(f"Erreur pour {ticker}: {e}")
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

Génère exactement les 4 sections suivantes avec ces titres exacts :

## 📊 Résumé des Résultats Financiers
Analyse les performances financières récentes : chiffre d'affaires, résultat net, marges, endettement, dividendes.
Commente la trajectoire de croissance et les perspectives pour l'exercice en cours et le suivant.

## 📈 Signaux Momentum
Analyse technique détaillée :
- RSI : interprète le niveau (survente < 30, surachat > 70, zone neutre 30-70)
- Moyennes mobiles : relation prix / MM20 / MM50 (croisements, tendance)
- Momentum 1 mois et 3 mois
- Niveau de support et résistance clés
Pour chaque signal, indique clairement : 🟢 HAUSSIER | 🟡 NEUTRE | 🔴 BAISSIER

## 💡 Opinion d'Investissement
Recommandation parmi : ⭐ ACHAT FORT | ACHAT | NEUTRE | VENTE | VENTE FORTE
- Justification de la recommandation
- Prix cible estimé à 12 mois
- Principaux risques (réglementaire, macroéconomique, sectoriel)
- Profil d'investisseur cible (court terme / long terme / revenus)

## 🏭 Comparaison Sectorielle
Compare {ticker} avec ses pairs du secteur {sector} à la BVC :
- Valorisation relative (PER, Price/Book, rendement)
- Positionnement concurrentiel et parts de marché
- Catalyseurs sectoriels propres au Maroc
- Conclusion : {ticker} sur-performe ou sous-performe son secteur ?

Utilise des données chiffrées, sois factuel et professionnel. Réponds intégralement en français."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
