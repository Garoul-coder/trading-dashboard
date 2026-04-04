import os
import json
import time

# Charge .env automatiquement en local (override=True : écrase les vars système vides)
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    # ── Fallback MCP si REST bloqué (Cloudflare) ─────────────────────────────
    if not result.get("cours"):
        print(f"[DRAHMI] REST sans cours pour {ticker} — tentative MCP fallback")
        mcp_result = fetch_via_mcp(ticker)
        if mcp_result and mcp_result.get("cours"):
            print(f"[MCP] ✅ {ticker} → {mcp_result['cours']} MAD via MCP")
            return mcp_result
        else:
            print(f"[MCP] ❌ MCP fallback aussi sans résultat pour {ticker}")

    return result


# ---------------------------------------------------------------------------
# Fetch données via MCP SSE (fallback si REST Cloudflare-bloqué)
# ---------------------------------------------------------------------------
def fetch_via_mcp(ticker):
    """
    Tente de récupérer les données via le endpoint MCP SSE de Drahmi.
    Protocol : GET /sse → event:endpoint → POST /messages → event:message
    Utilisé en fallback si api.drahmi.app est bloqué par Cloudflare.
    """
    key = os.environ.get("DRAHMI_API_KEY") or os.environ.get("trading_dashboard") or ""
    if not key:
        return None

    mcp_base  = "https://mcp.drahmi.app"
    sse_url   = f"{mcp_base}/sse"
    req_hdrs  = {
        "Authorization": f"Bearer {key}",
        "Accept":        "text/event-stream",
        "Cache-Control": "no-cache",
    }

    # ── Étape 1 : connexion SSE, récupère l'URL /messages?sessionId=... ──────
    messages_url = None
    sse_queue    = queue.Queue()

    def _sse_reader(sess, url):
        """Lit le stream SSE dans un thread séparé."""
        try:
            with sess.get(url, headers=req_hdrs, params={"api_key": key},
                          stream=True, timeout=12) as r:
                if r.status_code != 200:
                    sse_queue.put(("status_error", r.status_code, r.text[:200]))
                    return
                event_name = None
                for raw in r.iter_lines(decode_unicode=True):
                    sse_queue.put(("line", raw))
                    # Signal d'arrêt posé par le thread principal
                    if not sse_queue.empty():
                        item = sse_queue.queue[0]
                        if isinstance(item, tuple) and item[0] == "stop":
                            return
        except Exception as e:
            sse_queue.put(("error", str(e)))

    session = http.Session()
    t = threading.Thread(target=_sse_reader, args=(session, sse_url), daemon=True)
    t.start()

    # Attend l'événement endpoint (max 8 s)
    current_event = None
    deadline = 8
    start = time.time()
    while time.time() - start < deadline:
        try:
            item = sse_queue.get(timeout=1)
        except queue.Empty:
            continue

        if item[0] in ("status_error", "error"):
            print(f"[MCP] SSE error: {item[1:]}")
            return None

        line = item[1]
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_str = line.split(":", 1)[1].strip()
            if current_event == "endpoint" or messages_url is None:
                # L'URL peut être relative (/messages?sessionId=...) ou complète
                if data_str.startswith("/"):
                    messages_url = mcp_base + data_str
                elif data_str.startswith("http"):
                    messages_url = data_str
                elif data_str.startswith("{"):
                    try:
                        d = json.loads(data_str)
                        ep = d.get("endpoint") or d.get("url") or d.get("uri")
                        if ep:
                            messages_url = mcp_base + ep if ep.startswith("/") else ep
                    except Exception:
                        pass
                if messages_url:
                    break

    if not messages_url:
        print(f"[MCP] Impossible d'obtenir l'URL messages")
        return None

    print(f"[MCP] messages_url = {messages_url}")
    post_hdrs = {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Accept":        "application/json, text/event-stream",
    }

    # ── Étape 2 : initialize ─────────────────────────────────────────────────
    try:
        init_payload = {
            "jsonrpc": "2.0", "id": 1,
            "method":  "initialize",
            "params":  {
                "protocolVersion": "2024-11-05",
                "capabilities":    {},
                "clientInfo":      {"name": "trading-dashboard", "version": "1.0"},
            },
        }
        ri = session.post(messages_url, json=init_payload, headers=post_hdrs, timeout=8)
        print(f"[MCP] initialize → {ri.status_code}")
    except Exception as e:
        print(f"[MCP] initialize error: {e}")
        return None

    # ── Étape 3 : tools/call ─────────────────────────────────────────────────
    # Essaie plusieurs noms de tools courants Drahmi
    tool_candidates = [
        ("get_stock_data",   {"ticker": ticker}),
        ("getStock",         {"ticker": ticker}),
        ("stock_info",       {"symbol": ticker}),
        ("get_stock",        {"ticker": ticker}),
        ("get_ticker_info",  {"ticker": ticker}),
    ]

    for tool_name, tool_args in tool_candidates:
        try:
            call_payload = {
                "jsonrpc": "2.0", "id": 2,
                "method":  "tools/call",
                "params":  {"name": tool_name, "arguments": tool_args},
            }
            rc = session.post(messages_url, json=call_payload, headers=post_hdrs, timeout=10)
            print(f"[MCP] tools/call {tool_name} → {rc.status_code}")

            if rc.status_code == 200:
                try:
                    body = rc.json()
                    # Cherche le résultat dans la réponse JSON-RPC
                    result_data = body.get("result") or body
                    content = result_data.get("content") if isinstance(result_data, dict) else None
                    if content:
                        # Parfois retourné comme liste de {type, text}
                        if isinstance(content, list):
                            for c in content:
                                if c.get("type") == "text":
                                    try:
                                        parsed = json.loads(c["text"])
                                        return _normalize_mcp_stock(parsed, ticker)
                                    except Exception:
                                        pass
                        elif isinstance(content, dict):
                            return _normalize_mcp_stock(content, ticker)
                    # Parfois la donnée est directement dans result
                    if isinstance(result_data, dict) and (
                        result_data.get("price") or result_data.get("cours") or result_data.get("close")
                    ):
                        return _normalize_mcp_stock(result_data, ticker)
                except Exception as e:
                    print(f"[MCP] parse error: {e}")
        except Exception as e:
            print(f"[MCP] tools/call {tool_name} error: {e}")

    # ── Étape 4 : si tools/call n'a rien donné, essaie tools/list ────────────
    try:
        list_payload = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        rl = session.post(messages_url, json=list_payload, headers=post_hdrs, timeout=8)
        if rl.status_code == 200:
            tools_body = rl.json()
            tools = (tools_body.get("result") or {}).get("tools", [])
            tool_names = [t.get("name") for t in tools]
            print(f"[MCP] tools disponibles: {tool_names}")
            # Persiste dans les logs pour debugging
    except Exception as e:
        print(f"[MCP] tools/list error: {e}")

    return None


def _normalize_mcp_stock(d, ticker):
    """Normalise la réponse MCP en format attendu par _format_data_for_claude."""
    if not d:
        return None
    # Champs possibles selon l'implémentation Drahmi
    cours = (d.get("price") or d.get("cours") or d.get("close")
             or d.get("lastPrice") or d.get("last_price"))
    if not cours:
        return None
    return {
        "source":        "drahmi_mcp",
        "ticker":        ticker,
        "fetched_at":    datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "cours":         float(cours),
        "variation":     d.get("change") or d.get("variation") or d.get("changePercent"),
        "volume":        d.get("volume") or d.get("volume24h"),
        "capitalisation":d.get("marketCap") or d.get("capitalisation"),
        "per":           d.get("peRatio") or d.get("per"),
        "beta":          d.get("beta"),
        "div_yield":     d.get("dividendYield") or d.get("div_yield"),
        "week52_high":   d.get("week52High") or d.get("high52"),
        "week52_low":    d.get("week52Low")  or d.get("low52"),
        "name":          d.get("name") or d.get("companyName"),
        "signals":       d.get("signals", []),
    }


# ---------------------------------------------------------------------------
# Formatage données pour Claude
# ---------------------------------------------------------------------------
def _format_data_for_claude(ticker, sd):
    if not sd or not sd.get("cours"):
        return (
            "⚠️ Données de marché temps réel indisponibles (blocage réseau côté serveur).\n"
            "NE PAS inventer de cours, prix ou chiffres financiers.\n"
            "Produire uniquement une analyse qualitative : activité, secteur, positionnement, "
            "risques et opportunités connus — sans aucun chiffre inventé."
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

    prompt = f"""Analyste financier BVC expert. Analyse complète en français, style broker, bullet points et numérotation concis.

RÈGLE ABSOLUE : N'invente JAMAIS un cours ou un prix. Si le cours n'est pas fourni dans les données ci-dessous, indique explicitement "cours non disponible" et ne cite aucun chiffre de prix.

Ticker : **{ticker}** | Secteur : {sector}
{company_section}
{data_context}

Structure OBLIGATOIRE (7 sections, utilise puces "- " et numérotation "1. 2. 3." pour toutes les listes) :

## 🔎 1. Présentation
{price_snapshot}- Nom complet, groupe, activité principale
- Positionnement marché marocain
- Concurrents clés

## 📊 2. Analyse fondamentale
- PER, rendement dividende, beta (données fournies uniquement)
- Capitalisation et valorisation vs secteur
- **Forces :**
  1. [force 1]
  2. [force 2]
- **Risques :**
  1. [risque 1]
  2. [risque 2]

## 📈 3. Analyse technique
- Tendance court terme (basée sur signaux fournis)
- Tendance moyen terme
- Supports / Résistances clés (MAD) déduits du cours et 52S
- Configuration graphique actuelle

## ⚡ 4. Momentum
- Tendance de fond vs MASI
- Force relative sectorielle
- Signal global : 🟢 HAUSSIER | 🟡 NEUTRE | 🔴 BAISSIER

## 🏭 5. Comparaison sectorielle
| Critère | {ticker} | Pair 1 | Pair 2 |
|---|---|---|---|
| PER | | | |
| Rendement div. | | | |
| Beta | | | |
| Tendance | | | |

## 🧾 6. Opinion

⭐ **RECOMMANDATION : ACHAT FORT / ACHAT / CONSERVER / ALLÉGER / VENTE** _(choisis une seule)_

| Paramètre | Détail |
|---|---|
| **Prix cible 12M** | XXX MAD (+XX% potentiel) |
| **Prix entrée actuel** | XXX MAD |
| **Potentiel haussier** | +XX% — Risque baissier : -XX% (XXX MAD) |
| **Profil risque** | Faible / Moyen / Élevé |

**Arguments principaux :**
1. [argument 1]
2. [argument 2]
3. [argument 3]

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


@app.route("/debug-drahmi")
def debug_drahmi():
    key = os.environ.get("DRAHMI_API_KEY") or os.environ.get("trading_dashboard") or ""
    out = {"key_prefix": (key[:20] + "...") if key else "VIDE", "key_len": len(key)}

    # ── Test 1 : REST API ────────────────────────────────────────────────────
    rest_hdrs = {
        "X-API-Key": key, "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    try:
        r = http.get("https://api.drahmi.app/api/v1/stocks/SMI",
                     headers=rest_hdrs, timeout=8)
        out["rest_api"] = {
            "status_code": r.status_code,
            "response": r.json() if r.status_code == 200 else r.text[:300],
        }
    except Exception as e:
        out["rest_api"] = {"error": str(e)}

    # ── Test 2 : MCP SSE (juste l'accessibilité + premier event) ────────────
    mcp_url = "https://mcp.drahmi.app/sse"
    mcp_hdrs = {
        "Authorization": f"Bearer {key}",
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
    }
    try:
        r2 = http.get(mcp_url, headers=mcp_hdrs, params={"api_key": key},
                      stream=True, timeout=8)
        lines = []
        for raw in r2.iter_lines(decode_unicode=True):
            lines.append(raw)
            if len(lines) >= 10:
                break
        r2.close()
        out["mcp_sse"] = {
            "status_code": r2.status_code,
            "response_headers": dict(r2.headers),
            "first_lines": lines,
        }
    except Exception as e:
        out["mcp_sse"] = {"error": str(e)}

    # ── Test 3 : MCP full fetch SMI ──────────────────────────────────────────
    try:
        mcp_data = fetch_via_mcp("SMI")
        out["mcp_fetch_SMI"] = mcp_data if mcp_data else "null (aucune donnée)"
    except Exception as e:
        out["mcp_fetch_SMI"] = {"error": str(e)}

    return jsonify(out)


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

        # Si Drahmi a échoué, on génère quand même une analyse sans données temps réel
        if not sd.get("cours"):
            sd["source"] = "none"

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


# ---------------------------------------------------------------------------
# Scan sectoriel — opportunités hors banques
# ---------------------------------------------------------------------------

# Tickers éligibles au scan (hors secteur bancaire)
SCAN_TICKERS = [
    # Télécommunications
    "IAM",
    # Technologies
    "M2M", "HPS", "DISWAY", "S2M",
    # Mines
    "SMI", "MNG", "CMT",
    # Énergie
    "TMA", "GAZ", "TQM", "MOX",
    # Agroalimentaire
    "SBM", "LES", "CSR", "MUT", "OUL", "COL",
    # Assurances
    "WAA", "ACM",
    # Services financiers
    "SLF", "AFMA", "EQD", "MAL",
    # Immobilier
    "DHO", "RDS", "ALM", "IMM", "ARA",
    # Matériaux de construction
    "CMR", "LHM",
    # BTP
    "TGCC", "JET",
    # Distribution
    "LBV", "STK",
    # Industrie
    "SID", "SNEP", "ADH", "DEL",
    # Santé
    "AKD", "PRO", "SOT",
    # Transport & maritime
    "CTM", "MSA",
    # Tourisme
    "RIS",
]

# Cache en mémoire (TTL 30 min — préserve le quota 100 req/jour Drahmi)
_scan_cache: dict = {"data": None, "ts": 0.0}
_SCAN_TTL = 1800


# ── Indicateurs techniques ──────────────────────────────────────────────────

def _parse_rsi_from_signals(signals: list) -> float | None:
    """Extrait la valeur RSI numérique depuis les champs 'why'/'name' des signaux."""
    import re
    for s in signals:
        for field in ("why", "name", "description", "detail"):
            txt = str(s.get(field) or "")
            m = re.search(r'rsi[^0-9]*?(\d{1,2}(?:\.\d+)?)', txt, re.IGNORECASE)
            if m:
                v = float(m.group(1))
                if 5 < v < 95:
                    return round(v, 1)
        # Numerical value field
        if s.get("indicator") in ("RSI", "rsi"):
            v = s.get("value") or s.get("current_value")
            if v and 5 < float(v) < 95:
                return round(float(v), 1)
    return None


def _parse_ma_signal(signals: list) -> str:
    """Retourne 'bullish' | 'bearish' | 'neutral' selon les signaux MA."""
    for s in signals:
        if not s.get("triggered"):
            continue
        name = str(s.get("name") or "").lower()
        why  = str(s.get("why")  or "").lower()
        is_ma = any(k in name + why for k in ("mm", "ma", "moy", "average", "cross"))
        if is_ma:
            is_bull = any(k in why for k in ("haussier", "bullish", "dessus", "above", "↗", "hausse"))
            is_bear = any(k in why for k in ("baissier", "bearish", "dessous", "below", "↘", "baisse"))
            if is_bull:
                return "bullish"
            if is_bear:
                return "bearish"
    return "neutral"


def _approx_rsi(pos_in_range: float, var: float) -> float:
    """RSI approché depuis la position 52S + variation séance (fallback)."""
    base = 30 + pos_in_range * 40          # 30–70
    base += min(8, max(-8, var * 2))        # momentum ajustement
    return round(max(15, min(85, base)), 1)


def _rsi_label(rsi: float) -> str:
    if rsi < 30:  return "Survente"
    if rsi < 40:  return "Bas"
    if rsi <= 60: return "Neutre"
    if rsi <= 70: return "Haut"
    return "Surachat"


# ── Fetch complet ticker (2 appels : prix + signaux) ─────────────────────────

_quota_exceeded = False   # flag global : stoppe le scan si 429 détecté


def _fetch_ticker_full(ticker: str) -> dict | None:
    """Fetch données de marché + signaux techniques pour le scan avancé."""
    global _quota_exceeded
    if _quota_exceeded:
        return None

    headers = _drahmi_headers()
    result: dict = {
        "ticker":  ticker,
        "sector":  SECTORS.get(ticker, "Divers"),
        "signals": [],
    }

    # ── Appel 1 : prix / fondamentaux ─────────────────────────────────────
    try:
        r = http.get(f"{DRAHMI_BASE}/stocks/{ticker}", headers=headers, timeout=8)
        if r.status_code == 429:
            _quota_exceeded = True
            print(f"[SCAN] 429 quota épuisé sur {ticker}")
            return None
        if r.status_code != 200:
            return None
        d = r.json()
        cours = d.get("price")
        if not cours:
            return None
        result.update({
            "name":          d.get("name") or ticker,
            "cours":         float(cours),
            "variation":     float(d.get("change") or 0),
            "volume":        d.get("volume24h") or 0,
            "capitalisation":d.get("marketCap") or 0,
            "per":           d.get("peRatio"),
            "div_yield":     float(d.get("dividendYield") or 0),
            "week52_high":   d.get("week52High"),
            "week52_low":    d.get("week52Low"),
            "beta":          d.get("beta"),
        })
    except Exception as e:
        print(f"[SCAN] {ticker} prix: {e}")
        return None

    # ── Appel 2 : signaux techniques ──────────────────────────────────────
    try:
        r2 = http.get(
            f"{DRAHMI_BASE}/intelligence/stocks/{ticker}/signals",
            headers=headers, params={"range": "3M"}, timeout=8
        )
        if r2.status_code == 200:
            result["signals"] = r2.json().get("data", {}).get("signals", [])
    except Exception as e:
        print(f"[SCAN] {ticker} signals: {e}")

    return result


# ── Scoring opportunité v2 ────────────────────────────────────────────────────

def compute_opportunity_score(sd: dict, sector_sentiment: float = 0) -> tuple:
    """
    Score 0–100 multi-critères weekly :
      Position 52S / support    → 25 pts
      RSI (extrait ou approché) → 20 pts
      Signaux MA / momentum     → 20 pts
      Momentum séance           → 15 pts
      Dividende + PER           → 10 pts
      Sentiment sectoriel       → 10 pts
    Retourne (score, reasons, rsi_value, ma_signal_str)
    """
    score   = 0
    reasons = []
    cours   = float(sd.get("cours") or 0)
    high52  = sd.get("week52_high")
    low52   = sd.get("week52_low")
    var     = float(sd.get("variation") or 0)
    dy      = float(sd.get("div_yield") or 0)
    per     = sd.get("per")
    signals = sd.get("signals", [])

    # Position dans le range 52 semaines
    pos_52 = 0.5
    if high52 and low52 and float(high52) > float(low52):
        rng   = float(high52) - float(low52)
        pos_52 = (cours - float(low52)) / rng
        upside = (float(high52) - cours) / cours * 100

        if pos_52 <= 0.18:
            score += 20
            reasons.append(f"Au support annuel ({float(low52):,.0f} MAD) ✓")
        elif pos_52 <= 0.35:
            score += 25
            reasons.append(f"Zone d'achat — proche bas 52S ({float(low52):,.0f} MAD)")
        elif pos_52 <= 0.52:
            score += 15
            reasons.append("Cours sous la médiane annuelle")
        elif pos_52 <= 0.70:
            score += 7
        else:
            score += 2

        if upside >= 35:
            reasons.append(f"Potentiel +{upside:.0f}% vers résistance 52S")
        elif upside >= 18:
            reasons.append(f"Rebond possible +{upside:.0f}% vers 52S haut")

    # RSI
    rsi = _parse_rsi_from_signals(signals) or _approx_rsi(pos_52, var)
    ma_sig = _parse_ma_signal(signals)

    if 40 <= rsi <= 60:
        if var > 0:
            score += 20
            reasons.append(f"RSI {rsi:.0f} neutre↗ — configuration d'entrée idéale")
        else:
            score += 13
            reasons.append(f"RSI {rsi:.0f} — zone neutre opportuniste")
    elif 30 <= rsi < 40:
        score += 16
        reasons.append(f"RSI {rsi:.0f} — approche survente, rebond probable")
    elif rsi < 30:
        score += 9
        reasons.append(f"RSI {rsi:.0f} — survente (attendre confirmation)")
    elif 60 < rsi <= 70:
        score += 7
    else:
        score += 1   # >70 overbought

    # Signaux MA + déclenchés
    triggered = [s for s in signals if s.get("triggered")]
    if ma_sig == "bullish":
        score += 20
        reasons.append("Croisement MA haussier déclenché ✓")
    elif len(triggered) >= 2:
        score += 15
        reasons.append(f"{len(triggered)} signaux techniques actifs")
    elif len(triggered) == 1:
        score += 8
        reasons.append(f"Signal actif : {triggered[0].get('name','')}")

    # Momentum séance
    if -1.5 <= var < 0:
        score += 14
        reasons.append(f"Légère correction ({var:+.1f}%) = point d'entrée")
    elif 0 <= var <= 2.5:
        score += 15
        reasons.append(f"Momentum positif ({var:+.1f}%)")
    elif 2.5 < var <= 5:
        score += 8
    elif var < -3:
        score += 1
    else:
        score += 5

    # Dividende
    if dy >= 6:
        score += 7
        reasons.append(f"Dividende exceptionnel : {dy:.1f}%")
    elif dy >= 4:
        score += 5
        reasons.append(f"Dividende attractif : {dy:.1f}%")
    elif dy >= 2:
        score += 2

    # PER
    if per:
        p = float(per)
        if 5 < p < 15:
            score += 3
            reasons.append(f"PER attractif : {p:.1f}x")

    # Sentiment sectoriel
    if sector_sentiment >= 30:
        score += 10
        reasons.append(f"Secteur 🔥 haussier (sentiment {sector_sentiment:+.0f})")
    elif sector_sentiment >= 5:
        score += 5
    elif sector_sentiment < -20:
        score -= 5

    return min(score, 100), reasons, round(rsi, 1), ma_sig


# ── Sentiment sectoriel −100 → +100 ──────────────────────────────────────────

def compute_sector_sentiment(stocks: list) -> dict:
    """
    Score de sentiment sectoriel de −100 à +100.
    Basé sur : momentum moyen, RSI moyen, signaux MA, position 52S.
    """
    if not stocks:
        return {"score": 0, "label": "⚖️ Neutre", "color": "#ffd600", "perf_avg": 0}

    mom_scores, rsi_vals, pos_vals = [], [], []
    bull_cross = 0

    for sd in stocks:
        var   = float(sd.get("variation") or 0)
        sigs  = sd.get("signals", [])
        cours = float(sd.get("cours") or 0)
        h52   = sd.get("week52_high")
        l52   = sd.get("week52_low")

        # Momentum contribution (−40 → +40)
        if var > 3:    mom_scores.append(40)
        elif var > 1:  mom_scores.append(20)
        elif var > 0:  mom_scores.append(10)
        elif var > -1: mom_scores.append(-5)
        elif var > -3: mom_scores.append(-20)
        else:          mom_scores.append(-40)

        # RSI
        pos_52 = 0.5
        if h52 and l52 and float(h52) > float(l52):
            pos_52 = (cours - float(l52)) / (float(h52) - float(l52))
            pos_vals.append(pos_52)
        rsi = _parse_rsi_from_signals(sigs) or _approx_rsi(pos_52, var)
        rsi_vals.append(rsi)

        # MA
        if _parse_ma_signal(sigs) == "bullish":
            bull_cross += 1

    n = len(stocks)
    sentiment = 0.0

    # Momentum (poids 45 %)
    if mom_scores:
        sentiment += (sum(mom_scores) / len(mom_scores)) * 0.45

    # RSI vs 50 (poids 30 %) : RSI 50 = neutre, écart amplifié ×0.8
    if rsi_vals:
        rsi_mean = sum(rsi_vals) / len(rsi_vals)
        sentiment += (rsi_mean - 50) * 0.8

    # MA croisements (poids 25 %)
    if n:
        sentiment += (bull_cross / n - 0.5) * 50

    # Position 52S (bonus/malus léger)
    if pos_vals:
        pos_mean = sum(pos_vals) / len(pos_vals)
        sentiment += (pos_mean - 0.5) * 10

    sentiment = round(max(-100, min(100, sentiment)), 1)
    perf_avg  = round(sum(float(s.get("variation") or 0) for s in stocks) / n, 2)

    if sentiment >= 25:
        label, color = "🔥 Haussier", "#00e676"
    elif sentiment >= -10:
        label, color = "⚖️ Neutre",  "#ffd600"
    else:
        label, color = "❄️ Baissier", "#ef5350"

    return {
        "score":    sentiment,
        "label":    label,
        "color":    color,
        "perf_avg": perf_avg,
        "rsi_avg":  round(sum(rsi_vals) / len(rsi_vals), 1) if rsi_vals else None,
        "bull_pct": round(bull_cross / n * 100, 0) if n else 0,
        "n":        n,
    }


def _compute_entry_and_target(sd: dict, score: int) -> tuple:
    """Prix d'entrée + objectif 6M + % upside."""
    cours  = float(sd.get("cours") or 0)
    high52 = float(sd.get("week52_high") or cours * 1.20)
    low52  = float(sd.get("week52_low")  or cours * 0.80)

    if score >= 72:
        entry = round(cours * 0.987, 1)
    elif score >= 58:
        entry = round(cours * 0.972, 1)
    elif score >= 44:
        entry = round(cours * 0.952, 1)
    else:
        entry = round(max(cours * 0.90, low52 * 1.04), 1)

    gap    = high52 - entry
    target = round(entry + gap * 0.60, 1)
    upside = round((target - entry) / entry * 100, 1) if entry else 0
    return entry, target, upside


@app.route("/opportunites")
def opportunites_page():
    return render_template("opportunites.html")


@app.route("/api/scan-secteurs", methods=["POST"])
def scan_secteurs():
    global _scan_cache
    force = (request.get_json(silent=True) or {}).get("force", False)

    # ── Cache ────────────────────────────────────────────────────────────────
    if (not force and _scan_cache["data"]
            and time.time() - _scan_cache["ts"] < _SCAN_TTL):
        resp = dict(_scan_cache["data"])
        resp["cached"]    = True
        resp["cache_age"] = int(time.time() - _scan_cache["ts"])
        return jsonify(resp)

    global _quota_exceeded
    _quota_exceeded = False   # reset au début de chaque scan forcé
    t0 = time.time()

    # ── Phase 1 : fetch parallèle (prix + signaux) pour tous les tickers ────
    raw: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_ticker_full, t): t for t in SCAN_TICKERS}
        try:
            for f in as_completed(futures, timeout=24):
                r = f.result()
                if r and r.get("cours"):
                    raw.append(r)
        except Exception as e:
            print(f"[SCAN] fetch timeout: {e}")

    if not raw:
        msg = ("Quota API Drahmi épuisé (100 req/jour). "
               "Réessayez demain ou utilisez les données en cache.")  \
              if _quota_exceeded else "Aucune donnée Drahmi disponible"
        return jsonify({"error": msg, "quota_exceeded": _quota_exceeded}), 503

    print(f"[SCAN] {len(raw)} tickers en {time.time()-t0:.1f}s")

    # ── Phase 2 : sentiment sectoriel (agrège par secteur d'abord) ──────────
    sectors_stocks: dict[str, list] = {}
    for r in raw:
        sectors_stocks.setdefault(r["sector"], []).append(r)

    sector_sentiments: dict[str, dict] = {
        sec: compute_sector_sentiment(stocks)
        for sec, stocks in sectors_stocks.items()
    }

    # ── Phase 3 : scoring final avec sentiment sectoriel ────────────────────
    for r in raw:
        sec_sent = sector_sentiments.get(r["sector"], {}).get("score", 0)
        score, reasons, rsi, ma_sig = compute_opportunity_score(r, sec_sent)
        entry, target, upside = _compute_entry_and_target(r, score)
        r.update({
            "score":      score,
            "reasons":    reasons,
            "rsi":        rsi,
            "rsi_label":  _rsi_label(rsi),
            "ma_signal":  ma_sig,
            "entry":      entry,
            "target":     target,
            "upside_pct": upside,
            "signal":     ("ACHAT"      if score >= 68
                           else "SURVEILLER" if score >= 48
                           else "NEUTRE"),
        })

    raw.sort(key=lambda x: x["score"], reverse=True)

    # ── Grouper secteurs triés par sentiment décroissant ────────────────────
    by_sector: dict = {}
    for r in raw:
        by_sector.setdefault(r["sector"], []).append(r)

    by_sector_full = {}
    for sec in sorted(by_sector, key=lambda s: sector_sentiments.get(s, {}).get("score", 0), reverse=True):
        by_sector_full[sec] = {
            "stocks":    by_sector[sec],
            "sentiment": sector_sentiments[sec],
        }

    # Top 3 secteurs par sentiment
    top3_sectors = [
        {"sector": sec, **data}
        for sec, data in list(by_sector_full.items())[:3]
    ]

    payload = {
        "cached":        False,
        "fetched_at":    datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "scan_duration": round(time.time() - t0, 1),
        "total":         len(raw),
        "top_picks":     raw[:12],
        "by_sector":     by_sector_full,
        "top3_sectors":  top3_sectors,
        "buy_count":     sum(1 for r in raw if r["signal"] == "ACHAT"),
        "watch_count":   sum(1 for r in raw if r["signal"] == "SURVEILLER"),
        "neutral_count": sum(1 for r in raw if r["signal"] == "NEUTRE"),
        "api_calls":     len(raw) * 2,
        "quota_warning": _quota_exceeded,
    }
    _scan_cache["data"] = payload
    _scan_cache["ts"]   = time.time()
    return jsonify(payload)


@app.route("/api/analyse-opportunites", methods=["POST"])
def analyse_opportunites():
    """Analyse IA narrative des opportunités sectorielles."""
    body      = request.get_json(force=True, silent=True) or {}
    top_picks = body.get("top_picks", [])
    top3_sec  = body.get("top3_sectors", [])
    if not top_picks:
        return jsonify({"error": "Aucun pick fourni"}), 400

    # Contexte tickers
    ticker_lines = []
    for r in top_picks[:10]:
        h = r.get("week52_high") or "—"
        l = r.get("week52_low")  or "—"
        ticker_lines.append(
            f"- **{r['ticker']}** ({r['sector']}) : {r['cours']:,.1f} MAD "
            f"({r.get('variation', 0):+.1f}%) | Score={r['score']}/100 | "
            f"RSI={r.get('rsi','—')} ({r.get('rsi_label','')}) | "
            f"MA={r.get('ma_signal','neutral')} | "
            f"Entrée={r.get('entry','—')} MAD | Objectif={r.get('target','—')} MAD (+{r.get('upside_pct','—')}%) | "
            f"Div={r.get('div_yield', 0):.1f}% | PER={r.get('per') or '—'} | "
            f"52S [{l}–{h}] | [{'; '.join(r.get('reasons', [])[:2])}]"
        )

    # Contexte secteurs
    sec_lines = []
    for s in top3_sec[:5]:
        sent = s.get("sentiment", {})
        stocks = s.get("stocks", [])
        top_v = stocks[0].get("ticker") if stocks else "—"
        sec_lines.append(
            f"- **{s['sector']}** : sentiment={sent.get('score',0):+.0f} ({sent.get('label','')}) | "
            f"perf_moy={sent.get('perf_avg',0):+.1f}% | RSI_moy={sent.get('rsi_avg','—')} | "
            f"MA_haussier={sent.get('bull_pct',0):.0f}% valeurs | top_valeur={top_v}"
        )

    ctx = "**Top Opportunités :**\n" + "\n".join(ticker_lines)
    if sec_lines:
        ctx += "\n\n**Secteurs leaders :**\n" + "\n".join(sec_lines)

    prompt = f"""Tu es analyste financier senior spécialisé BVC (Bourse de Casablanca).
Analyse basée sur un scan sectoriel HEBDOMADAIRE (hors banques) :

{ctx}

Rédige en français, style flash note broker, avec puces et numérotation :

## 🎯 1. Top 3 Opportunités Prioritaires
Pour chacune :
1. **[TICKER]** — [Secteur] | RSI [X] | Signal MA : [haussier/neutre/baissier]
   - Thèse : (configuration technique + contexte fondamental en 2 lignes)
   - Entrée : [X MAD] | Objectif 6M : [Y MAD] (+Z%) | Stop-loss : [W MAD]
   - Catalyseur BVC à surveiller

## 📊 2. Sentiment Sectoriel (weekly)
| Secteur | Tendance | RSI moy. | Top valeur | Commentaire |
|---|---|---|---|---|
(5 secteurs, couleur via emoji 🔥⚖️❄️)

## ⚠️ 3. Risques du moment
1. [risque macro/BVC global]
2. [risque sectoriel/idiosyncratique]

## 🧠 4. Stratégie d'Allocation
- Répartition suggérée inter-secteurs (%)
- Timing d'entrée et conditions (weekly close > support, RSI > 40…)
- Diversification et gestion du risque"""

    client = get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
        timeout=25,
    )
    return jsonify({"analysis": response.content[0].text})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
