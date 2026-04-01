import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import anthropic

from bvcscrap.tech import getCours, getKeyIndicators
_BVCSCRAP_OK = True

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Mapping ticker BVC → nom BVCscrap (notation exacte requise)
# Source : bvc.notation()  — 74 valeurs supportées
# ---------------------------------------------------------------------------
BVC_NAMES = {
    # Banques
    "ATW":    "Attijariwafa",
    "BCP":    "BCP",
    "CIH":    "CIH",
    "BOA":    "BOA",
    "CDM":    "CDM",
    "BMCI":   "BMCI",
    # Assurances & Financières
    "WAA":    "Wafa Assur",
    "ACM":    "ATLANTASANAD",
    "SLF":    "SALAFIN",
    "AFMA":   "AFMA",
    "EQD":    "EQDOM",
    "MAL":    "Maroc Leasing",
    # Télécoms & Tech
    "IAM":    "Maroc Telecom",
    "M2M":    "M2M Group",
    "HPS":    "HPS",
    "DISWAY": "DISWAY",
    "DISTY":  "Disty Technolog",
    # Mines
    "SMI":    "SMI",
    "MNG":    "Managem",
    "CMT":    "CMT",
    # Ciment & BTP
    "CMR":    "Ciments Maroc",
    "LHM":    "LafargeHolcim",
    "JET":    "Jet Contractors",
    "TGCC":   "TGCC",
    # Énergie
    "TMA":    "TAQA Morocco",
    "GAZ":    "Afriquia Gaz",
    "TQM":    "Total Maroc",
    "MOX":    "Maghreb Oxygene",
    # Agroalimentaire
    "SBM":    "Ste Boissons",
    "OUL":    "Oulmes",
    "LES":    "Lesieur Cristal",
    "CSR":    "COSUMAR",
    "MUT":    "Mutandis",
    "UNM":    "Unimer",
    "COL":    "Colorado",
    # Distribution
    "LBV":    "LABEL VIE",
    # Automobile
    "ADH":    "Auto Hall",
    # Immobilier
    "ALM":    "Alliances",
    "DHO":    "Addoha",
    "RDS":    "Res.Dar Saada",
    "IMM":    "Immr Invest",
    "ARA":    "Aradei Capital",
    # Industrie & Chimie
    "SID":    "Sonasid",
    "PRO":    "PROMOPHARM",
    "SNEP":   "SNEP",
    "SOT":    "SOTHEMA",
    "STK":    "Stokvis Nord Afr",
    "AKD":    "Akdital",
    "DEL":    "Delta Holding",
    # Transport & Services
    "CTM":    "CTM",
    "RIS":    "Risma",
    "MSA":    "SODEP",
    # Autres
    "S2M":    "S2M",
}

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
# Parsing des valeurs retournées par BVCscrap (format français variable)
# ---------------------------------------------------------------------------
def _bvc_num(s):
    """
    Parse une valeur retournée par BVCscrap.
    Gère : float/int natif, "6 734,00", "6.734,00", "+2,35%", "N/A", None.
    """
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if s in ("", "N/A", "—", "-", "n/a"):
        return None
    # Supprimer unités et espaces spéciaux
    s = s.replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    s = re.sub(r"[MADmad%]", "", s)
    # Format français : point = séparateur milliers, virgule = décimale
    s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s) if s not in ("", ".") else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Fetch données BVC via BVCscrap
# ---------------------------------------------------------------------------
def fetch_bvc_data(name):
    """
    Appelle getCours() + getKeyIndicators() en PARALLÈLE avec timeout strict.
    Budget : 12s max pour les deux appels BVCscrap combinés.
    """
    if not _BVCSCRAP_OK:
        raise RuntimeError("BVCscrap non installé")

    result = {"source": "bvcscrap", "name": name,
               "scraped_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

    # ── Exécution parallèle avec timeout ─────────────────────────────────────
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_cours = pool.submit(getCours, name)
        fut_ind   = pool.submit(getKeyIndicators, name)

        # getCours — timeout 12s
        try:
            raw    = fut_cours.result(timeout=12)
            seance = raw.get("Données_Seance", {})
            result["cours"]          = _bvc_num(seance.get("Cours"))
            result["variation"]      = _bvc_num(seance.get("Variation"))
            result["ouverture"]      = _bvc_num(seance.get("Ouverture"))
            result["haut"]           = _bvc_num(seance.get("Plus haut"))
            result["bas"]            = _bvc_num(seance.get("Plus bas"))
            result["clot_precedent"] = _bvc_num(seance.get("Cours de cloture veille"))
            result["volume"]         = _bvc_num(seance.get("Volume en titres"))
            result["capitalisation"] = _bvc_num(seance.get("Capitalisation"))
            sp = raw.get("Seance_prec", {})
            if sp:
                result["seance_prec"] = sp
            print(f"[BVC] getCours({name}) → cours={result.get('cours')}, vol={result.get('volume')}")
        except FutureTimeout:
            print(f"[BVC] getCours({name}) TIMEOUT")
        except Exception as e:
            print(f"[BVC] getCours({name}) ERROR: {e}")

        # getKeyIndicators — timeout 12s
        try:
            ind = fut_ind.result(timeout=12)
            result["chiffres_cles"] = ind.get("Chiffres_cles", {})
            result["ratios"]        = ind.get("Ratio", {})
            result["actionnaires"]  = ind.get("Actionnaires", {})
            result["info_societe"]  = ind.get("Info_Societe", {})
            print(f"[BVC] getKeyIndicators({name}) → OK")
        except FutureTimeout:
            print(f"[BVC] getKeyIndicators({name}) TIMEOUT")
        except Exception as e:
            print(f"[BVC] getKeyIndicators({name}) ERROR: {e}")

    return result


# ---------------------------------------------------------------------------
# Formatage données pour Claude
# ---------------------------------------------------------------------------
def _format_scraped_for_claude(ticker, sd):
    if not sd or sd.get("source") != "bvcscrap":
        return (
            "Données marché non disponibles. "
            "Formule des hypothèses réalistes basées sur le contexte du marché marocain."
        )

    lines = [f"Données BVC officielles — casablanca-bourse.com — {sd.get('scraped_at', '')} :\n"]

    # Cours
    if sd.get("cours"):
        var = sd.get("variation")
        var_str = f" ({var:+.2f}%)" if var is not None else ""
        lines.append(f"💰 COURS : {sd['cours']:,.2f} MAD{var_str}")
    if sd.get("haut") and sd.get("bas"):
        lines.append(f"- Séance Haut/Bas : {sd['haut']:,.2f} / {sd['bas']:,.2f} MAD")
    if sd.get("ouverture"):
        lines.append(f"- Ouverture : {sd['ouverture']:,.2f} MAD")
    if sd.get("clot_precedent"):
        lines.append(f"- Clôture préc. : {sd['clot_precedent']:,.2f} MAD")
    if sd.get("volume"):
        lines.append(f"- Volume : {int(sd['volume']):,} titres")
    if sd.get("capitalisation"):
        lines.append(f"- Capitalisation : {sd['capitalisation']:,.0f} MAD")

    # Chiffres clés (3 ans)
    ck = sd.get("chiffres_cles", {})
    annees = ck.get("Annee", [])
    if annees:
        lines.append(f"\nChiffres clés — années : {', '.join(str(a) for a in annees)}")
        for label, key in [
            ("Chiffre d'affaires", "Chiffre_Affaires"),
            ("Résultat exploitation", "Resultat_exploitation"),
            ("Résultat net", "Resultat_net"),
            ("Capitaux propres", "Capitaux_propres"),
        ]:
            vals = ck.get(key, [])
            if any(v is not None for v in vals):
                row = " | ".join(
                    f"{_bvc_num(v):,.1f}" if _bvc_num(v) is not None else "—"
                    for v in vals
                )
                lines.append(f"  {label} : {row}")

    # Ratios (3 ans)
    rat = sd.get("ratios", {})
    rat_annees = rat.get("Annee", [])
    if rat_annees:
        lines.append(f"\nRatios boursiers — années : {', '.join(str(a) for a in rat_annees)}")
        for label, key in [
            ("PER", "PER"), ("BPA (MAD)", "BPA"),
            ("ROE (%)", "ROE"), ("PBR", "PBR"),
            ("Rendement div. (%)", "Dividend_yield"),
            ("Payout (%)", "Payout"),
        ]:
            vals = rat.get(key, [])
            if any(v is not None for v in vals):
                row = " | ".join(
                    f"{_bvc_num(v):.2f}" if _bvc_num(v) is not None else "—"
                    for v in vals
                )
                lines.append(f"  {label} : {row}")

    # Actionnaires
    act = sd.get("actionnaires", {})
    if act:
        lines.append("\nActionnariat :")
        for nom, pct in list(act.items())[:5]:
            lines.append(f"  - {nom} : {pct}")

    # Dernières séances
    sp = sd.get("seance_prec", {})
    dates = sp.get("Date", [])
    clots = sp.get("Cloture", [])
    if dates and clots:
        lines.append("\nDernières séances :")
        for d, c in zip(dates[-5:], clots[-5:]):
            lines.append(f"  {d} → {c} MAD")

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
    data_context    = _format_scraped_for_claude(ticker, sd)
    company_context = get_company_context(ticker)
    company_section = f"\n{company_context}\n" if company_context else ""

    # Snapshot prix section 1
    price_snapshot = ""
    if sd and sd.get("cours"):
        cours   = sd["cours"]
        var     = sd.get("variation")
        var_str = f"{var:+.2f}%" if var is not None else "—"
        haut    = f"{sd['haut']:,.2f}" if sd.get("haut") else "—"
        bas     = f"{sd['bas']:,.2f}" if sd.get("bas") else "—"
        vol     = f"{int(sd['volume']):,}" if sd.get("volume") else "—"

        # Calcul cours cible depuis ratios BPA × PER moyen si dispo
        rat   = sd.get("ratios", {})
        bpas  = [_bvc_num(v) for v in rat.get("BPA", []) if _bvc_num(v)]
        pers  = [_bvc_num(v) for v in rat.get("PER", []) if _bvc_num(v)]
        cible_str = "—"
        if bpas and pers:
            cible = bpas[-1] * pers[-1]
            cible_str = f"{cible:,.2f} MAD (BPA×PER)"

        price_snapshot = f"""
**💰 COURS BVC : {cours:,.2f} MAD ({var_str})**
| Indicateur | Valeur |
|---|---|
| Cours actuel | **{cours:,.2f} MAD** |
| Variation séance | {var_str} |
| Haut du jour | {haut} MAD |
| Bas du jour | {bas} MAD |
| Volume | {vol} titres |
| Cours cible estimé | {cible_str} |

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
- CA, résultat net, marges (utilise les 3 années fournies, calcule les évolutions YoY)
- PER, BPA, ROE, PBR, rendement dividende (données fournies)
- Capitalisation, valorisation vs secteur et historique
- Forces, faiblesses, risques macro/sectoriels, perspectives

## 📈 3. Analyse technique
- Tendances court/moyen/long terme basées sur les dernières séances fournies
- Supports et résistances clés (MAD) déduits du cours actuel et historique
- Configuration graphique actuelle

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
        timeout=15,   # 15s max pour Claude — budget total Render < 30s
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
        "status":        "ok",
        "bvcscrap":      _BVCSCRAP_OK,
        "api_key_set":   bool(os.environ.get("ANTHROPIC_API_KEY")),
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
        name   = BVC_NAMES.get(ticker)

        sd = {"source": "none"}
        if name:
            try:
                sd = fetch_bvc_data(name)
            except Exception as e:
                print(f"[WARN] BVCscrap failed for {ticker} ({name}): {e}")
                sd = {"source": "none", "error": str(e)}
        else:
            print(f"[WARN] No BVCscrap name for {ticker}")

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
