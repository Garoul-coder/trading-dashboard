import os
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)

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
        raise ValueError("Clé API Anthropic non configurée sur le serveur.")
    return anthropic.Anthropic(api_key=api_key)


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
        if not ticker:
            return jsonify({"error": "Veuillez entrer un ticker valide"}), 400
        if len(ticker) > 10:
            return jsonify({"error": "Ticker invalide"}), 400

        sector = SECTORS.get(ticker, "Secteur divers")
        analysis = generate_analysis(ticker, sector)

        return jsonify({
            "ticker": ticker,
            "sector": sector,
            "analysis": analysis,
        })

    except Exception as e:
        print(f"[ERROR] /analyze : {e}")
        return jsonify({"error": str(e)}), 500


def generate_analysis(ticker, sector):
    prompt = f"""Tu es un analyste financier expert des marchés émergents, spécialisé dans la Bourse de Casablanca (BVC).
Ta mission est de produire une analyse complète, claire et professionnelle, digne d'un rapport de société de gestion marocaine (asset management / broker).

Ticker analysé : **{ticker}** | Secteur : {sector}

Génère l'analyse complète en respectant EXACTEMENT cette structure :

## 🔎 1. Présentation de la société
- Nom complet et activité principale
- Positionnement sur le marché marocain
- Principaux concurrents locaux

## 📊 2. Analyse fondamentale

### a) Résultats financiers récents
- Chiffre d'affaires et évolution YoY
- Résultat net et évolution YoY
- Marges EBITDA et nette
- Éléments marquants

### b) Ratios clés
- PER, ROE, Dette/EBITDA
- Rendement du dividende
- Valorisation vs historique (sur/sous-valorisé ?)

### c) Analyse qualitative
- Forces et avantages concurrentiels
- Faiblesses
- Risques (macro, sectoriels, spécifiques Maroc)
- Perspectives de croissance

## 📈 3. Analyse technique

### a) Tendance
- Court terme, moyen terme, long terme

### b) Indicateurs techniques
- MM20 / MM50 / MM200 : signaux et croisements
- RSI : niveau et interprétation
- MACD : signal haussier ou baissier
- Volumes : accumulation ou distribution

### c) Niveaux clés
- Supports principaux
- Résistances principales
- Situation : breakout, consolidation ou retournement ?

## ⚡ 4. Signaux de momentum
- Accélération ou ralentissement de tendance
- Force relative vs indice MASI
- Signal global : 🟢 HAUSSIER | 🟡 NEUTRE | 🔴 BAISSIER

## 🏭 5. Comparaison sectorielle
- Comparer {ticker} avec 2-3 concurrents marocains du secteur {sector}
- Croissance, rentabilité, valorisation comparées
- Leadership ou retard sectoriel

## 🧾 6. Opinion d'investissement
- Recommandation : **ACHAT FORT** | **ACHAT** | **CONSERVER** | **ALLÉGER** | **VENTE**
- Horizon : court / moyen / long terme
- Prix cible estimé à 12 mois
- Niveau de risque : Faible | Moyen | Élevé
- Arguments principaux (3-5 points)

## 🧠 7. Résumé exécutif
Synthèse en 5-7 lignes maximum, orientée décision, comme dans un flash note de broker.

---
Contraintes : répondre uniquement en français · être synthétique et factuel · utiliser des bullet points · formuler des hypothèses réalistes si données manquantes."""

    client = get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
