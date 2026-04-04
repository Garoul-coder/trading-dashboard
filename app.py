import os
import requests as http
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)

DRAHMI_BASE = "https://api.drahmi.app/api/v1"

# ---------------------------------------------------------------------------
# Secteurs BVC
# ---------------------------------------------------------------------------
SECTORS = {
    "ATW": "Banques", "BCP": "Banques", "CIH": "Banques",
    "BOA": "Banques", "CDM": "Banques", "BMCI": "Banques",
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
    "STK": "Distribution industrielle",
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
        "activite": "Exploitation mine d'argent d'Imiter (Tinghir). 1ère mine d'argent d'Afrique.",
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
        "activite": "1er groupe bancaire du Maroc, présent dans 27 pays africains.",
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
        "particularites": "3e groupe bancaire marocain.",
    },
    "HPS": {
        "nom": "Hightech Payment Systems (HPS)",
        "groupe": "Indépendant",
        "activite": "Éditeur logiciels paiement électronique (PowerCARD). 90+ pays.",
        "concurrents": "Fiserv, FIS, Temenos",
        "particularites": "Champion marocain fintech international.",
    },
    "TMA": {
        "nom": "Taqa Morocco",
        "groupe": "TAQA Abu Dhabi (72,6%)",
        "activite": "Production électricité centrale Jorf Lasfar (2 760 MW). Vente à l'ONEE.",
        "concurrents": "ONEE, autres IPP",
        "particularites": "Contrat PPA long terme. Fort rendement dividende.",
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
        "concurrents": "RMA, Saham Assurance, AXA Maroc",
        "particularites": "Leader assurance Maroc. Synergie ATW.",
    },
    "LBV": {
        "nom": "Label'Vie",
        "groupe": "Famille Zniber / Carrefour",
        "activite": "Distribution alimentaire. Carrefour, Carrefour Market, Atacadão.",
        "concurrents": "Marjane, Aswak Assalam, BIM",
        "particularites": "Forte croissance réseau. Concept Atacadão en expansion.",
    },
    "CSR": {
        "nom": "Cosumar",
        "groupe": "Groupe Al Mada",
        "activite": "Sucrerie du Maroc. Extraction et raffinage sucre.",
        "concurrents": "Importations",
        "particularites": "Quasi-monopole sucre raffiné. Prix encadrés État.",
    },
    "DHO": {
        "nom": "Douja Promotion Groupe Addoha",
        "groupe": "Famille Anas Sefrioui",
        "activite": "1er promoteur immobilier Maroc. Logement social, économique, haut standing.",
        "concurrents": "Alliances, Résidences Dar Saada",
        "particularites": "Sensible politiques logement social.",
    },
    "AKD": {
        "nom": "Akdital",
        "groupe": "Fondateurs (Dr Rochdi Talib)",
        "activite": "Réseau de cliniques privées au Maroc. Leader hospitalier privé coté BVC.",
        "concurrents": "Clinimaroc, cliniques indépendantes",
        "particularites": "Forte croissance. Seul acteur santé privé coté BVC.",
    },
    "MSA": {
        "nom": "Marsa Maroc (SODEP)",
        "groupe": "État marocain",
        "activite": "Exploitation et développement des ports marocains.",
        "concurrents": "Opérateurs portuaires internationaux",
        "particularites": "Levier direct sur croissance commerce extérieur marocain.",
    },
}


def get_company_context(ticker):
    p = COMPANY_PROFILES.get(ticker)
    if not p:
        return ""
    return (
        "Fiche société :\n"
        f"- Nom          : {p['nom']}\n"
        f"- Groupe       : {p['groupe']}\n"
        f"- Activité     : {p['activite']}\n"
        f"- Concurrents  : {p['concurrents']}\n"
        f"- Particularités: {p['particularites']}"
    )


# ---------------------------------------------------------------------------
# Fetch données via API Drahmi
# ---------------------------------------------------------------------------
def _drahmi_headers():
    key = os.environ.get("DRAHMI_API_KEY") or os.environ.get("trading_dashboard")
    if not key:
        raise ValueError("DRAHMI_API_KEY non configurée")
    return {
        "X-API-Key": key,
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://www.drahmi.app",
        "Referer": "https://www.drahmi.app/",
    }


def fetch_drahmi_data(ticker):
    """
    2 appels API Drahmi en parallèle :
      1. /stocks/{ticker}         — cours, variation, PER, beta, volume, capitalisation
      2. /intelligence/stocks/{ticker}/signals — signaux RSI / MA crossover
    Budget : 2 requêtes par analyse (~50 analyses/jour sur plan gratuit).
    """
    headers = _drahmi_headers()
    result = {
        "source": "drahmi",
        "ticker": ticker,
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

    # ── Appel 1 : données de marché ──────────────────────────────────────────
    try:
        r = http.get(f"{DRAHMI_BASE}/stocks/{ticker}", headers=headers, timeout=8)
        if r.status_code == 200:
            d = r.json()
            result["name"]          = d.get("name")
            result["cours"]         = d.get("price")
            result["variation"]     = d.get("change")
            result["volume"]        = d.get("volume24h")
            result["capitalisation"]= d.get("marketCap")
            result["per"]           = d.get("peRatio")
            result["beta"]          = d.get("beta")
            result["div_yield"]     = d.get("dividendYield")
            result["week52_high"]   = d.get("week52High")
            result["week52_low"]    = d.get("week52Low")
            result["isin"]          = d.get("isin")
            result["sector_drahmi"] = d.get("sector")
            print(f"[DRAHMI] {ticker} → {result['cours']} MAD ({result['variation']:+.2f}%)")
        elif r.status_code == 404:
            result["error"] = "Ticker non trouvé dans Drahmi"
            print(f"[DRAHMI] {ticker} → 404 not found")
        else:
            result["error"] = f"HTTP {r.status_code}"
            print(f"[DRAHMI] {ticker} → HTTP {r.status_code}")
    except Exception as e:
        result["error"] = str(e)
        print(f"[DRAHMI] {ticker} stocks ERROR: {e}")

    # ── Appel 2 : signaux techniques ─────────────────────────────────────────
    try:
        r2 = http.get(
            f"{DRAHMI_BASE}/intelligence/stocks/{ticker}/signals",
            headers=headers,
            params={"range": "3M"},
            timeout=8,
        )
        if r2.status_code == 200:
            data2 = r2.json()
            signals = data2.get("data", {}).get("signals", [])
            result["signals"] = signals
            print(f"[DRAHMI] {ticker} signals → {len(signals)} signaux")
    except Exception as e:
        print(f"[DRAHMI] {ticker} signals ERROR: {e}")

    return result


# ---------------------------------------------------------------------------
# Formatage données pour Claude
# ---------------------------------------------------------------------------
def _format_data_for_claude(ticker, sd):
    if not sd or sd.get("source") != "drahmi" or not sd.get("cours"):
        return (
            "Données marché non disponibles. "
            "Formule des hypothèses réalistes basées sur le contexte du marché marocain."
        )

    lines = [f"Données marché — API Drahmi — {sd.get('fetched_at', '')} :\n"]

    # Cours
    cours = sd["cours"]
    var   = sd.get("variation")
    var_str = f"{var:+.2f}%" if var is not None else "—"
    lines.append(f"💰 COURS : {cours:,.2f} MAD ({var_str})")

    if sd.get("volume"):
        lines.append(f"- Volume séance   : {sd['volume']:,.0f} MAD")
    if sd.get("capitalisation"):
        lines.append(f"- Capitalisation  : {sd['capitalisation']:,.0f} MAD")
    if sd.get("week52_high") and sd.get("week52_low"):
        lines.append(f"- 52S Haut/Bas    : {sd['week52_high']:,.2f} / {sd['week52_low']:,.2f} MAD")

    lines.append("\nRatios :")
    if sd.get("per"):
        lines.append(f"  PER             : {sd['per']:.2f}x")
    if sd.get("beta"):
        lines.append(f"  Bêta            : {sd['beta']:.2f}")
    if sd.get("div_yield"):
        lines.append(f"  Rendement div.  : {sd['div_yield']:.2f}%")

    # Signaux techniques
    signals = sd.get("signals", [])
    if signals:
        lines.append("\nSignaux techniques (3M) :")
        for s in signals:
            status = "✅ DÉCLENCHÉ" if s.get("triggered") else "⬜ non déclenché"
            lines.append(f"  [{status}] {s.get('name')} — {s.get('why', '')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude API — analyse 7 axes
# ---------------------------------------------------------------------------
def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Clé API Anthropic non configurée.")
    return anthropic.Anthropic(api_key=api_key, max_retries=0)


def generate_analysis(ticker, sector, sd):
    data_context    = _format_data_for_claude(ticker, sd)
    company_context = get_company_context(ticker)
    company_section = f"\n{company_context}\n" if company_context else ""

    # Snapshot prix section 1
    price_snapshot = ""
    if sd and sd.get("cours"):
        cours   = sd["cours"]
        var     = sd.get("variation")
        var_str = f"{var:+.2f}%" if var is not None else "—"
        vol     = f"{sd['volume']:,.0f}" if sd.get("volume") else "—"
        h52     = f"{sd['week52_high']:,.2f}" if sd.get("week52_high") else "—"
        l52     = f"{sd['week52_low']:,.2f}" if sd.get("week52_low") else "—"
        per     = f"{sd['per']:.2f}x" if sd.get("per") else "—"
        dy      = f"{sd['div_yield']:.2f}%" if sd.get("div_yield") else "—"

        price_snapshot = f"""
**💰 COURS BVC : {cours:,.2f} MAD ({var_str})**
| Indicateur | Valeur |
|---|---|
| Cours actuel | **{cours:,.2f} MAD** |
| Variation séance | {var_str} |
| Volume séance | {vol} MAD |
| 52S Haut / Bas | {h52} / {l52} MAD |
| PER | {per} |
| Rendement dividende | {dy} |

"""

    prompt = f"""Analyste financier BVC expert. Analyse complète en français, style broker, bullet points concis.

RÈGLE ABSOLUE : N'invente JAMAIS un cours ou un prix. Si le cours n'est pas fourni dans les données ci-dessous, indique explicitement "cours non disponible" et ne cite aucun chiffre de prix.

Ticker : **{ticker}** | Secteur : {sector}
{company_section}
{data_context}

Structure OBLIGATOIRE (7 sections) :

## 🔎 1. Présentation
{price_snapshot}- Nom complet, groupe, activité principale
- Positionnement marché marocain, concurrents clés

## 📊 2. Analyse fondamentale
- PER, rendement dividende, beta (données fournies)
- Capitalisation, valorisation vs secteur et historique
- Forces, faiblesses, risques macro/sectoriels, perspectives

## 📈 3. Analyse technique
- Tendances court/moyen terme basées sur les signaux fournis
- Supports et résistances clés (MAD) déduits du cours actuel et du 52S
- Configuration graphique actuelle

## ⚡ 4. Momentum
- Tendance de fond, force relative vs MASI
- Signal : 🟢 HAUSSIER | 🟡 NEUTRE | 🔴 BAISSIER

## 🏭 5. Comparaison sectorielle
| Critère | {ticker} | Pair 1 | Pair 2 |
|---|---|---|---|
| PER | | | |
| Rendement div. | | | |
| Beta | | | |

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
        timeout=25,
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
        "drahmi":      bool(os.environ.get("DRAHMI_API_KEY") or os.environ.get("trading_dashboard")),
        "anthropic":   bool(os.environ.get("ANTHROPIC_API_KEY")),
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

        try:
            sd = fetch_drahmi_data(ticker)
        except Exception as e:
            print(f"[WARN] Drahmi failed for {ticker}: {e}")
            sd = {"source": "none", "error": str(e)}

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
