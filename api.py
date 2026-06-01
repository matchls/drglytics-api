"""
DRG Dashboard — API Flask
==========================
Un seul endpoint : POST /api/parse
  - Reçoit un fichier .sav (multipart/form-data)
  - Reçoit le pseudo du joueur (form field "player_name")
  - Retourne le JSON du dashboard

Analogie : c'est un guichet. Le joueur dépose son fichier save sur le comptoir,
et le guichet lui remet une fiche résumé lisible. Rien n'est conservé.

Usage local :
    pip install flask
    python api.py
    → http://localhost:5000
"""

import tempfile
import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from parse_save import parse_gvas
from stats_builder import build_dashboard_data

# ── App Flask ─────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Derrière le reverse-proxy de l'hébergeur (Railway/Vercel), l'IP cliente réelle
# se trouve dans l'en-tête X-Forwarded-For, pas dans remote_addr (qui vaut l'IP
# interne du proxy, identique pour tous). ProxyFix la restaure pour que le rate
# limiting compte bien PAR visiteur. x_for=1 = on ne fait confiance qu'à UNE
# couche de proxy ; sinon X-Forwarded-For redeviendrait spoofable par le client.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# CORS : on n'autorise QUE les origines explicitement déclarées (plus de "*",
# qui laissait n'importe quel site appeler l'API). La liste vient d'une variable
# d'env ALLOWED_ORIGINS (séparée par des virgules). En local, défaut = front Next.
# Ex. prod : ALLOWED_ORIGINS="https://drg-dashboard.vercel.app"
allowed_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

# Rate limiting : plafonne les appels par IP pour éviter l'abus de ressources.
# ⚠️ Stockage en mémoire par défaut (suffisant pour un backend mono-process type
# Railway). Pour du multi-instance, brancher un storage_uri Redis.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["60 per hour"],
)

# ── Limites ───────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_MB = 5
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024


# ── Endpoint principal ────────────────────────────────────────────────────────

@app.route("/api/parse", methods=["POST"])
@limiter.limit("10 per minute")  # parsing = opération coûteuse → plafond serré
def parse_save_file():
    """
    Reçoit un fichier .sav et un pseudo, retourne les stats du dashboard.

    Form data :
        file        : le fichier .sav (required)
        player_name : le pseudo du joueur (required)

    Réponse 200 :
        { "ok": true, "data": { ... } }

    Réponse 4xx/5xx :
        { "ok": false, "error": "message d'erreur lisible" }
    """

    # 1. Vérifier la présence du fichier
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided"}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    if not file.filename.endswith(".sav"):
        return jsonify({"ok": False, "error": "File must be a .sav file"}), 400

    # 2. Vérifier le pseudo
    player_name = request.form.get("player_name", "").strip()
    if not player_name:
        return jsonify({"ok": False, "error": "player_name is required"}), 400
    if len(player_name) > 64:
        return jsonify({"ok": False, "error": "player_name too long (max 64 chars)"}), 400

    # 3. Parser le fichier .sav
    #    On écrit dans un fichier temporaire car parse_gvas attend un chemin
    #    Le fichier est automatiquement supprimé après le bloc "with"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".sav", delete=False) as tmp:
            tmp_path = tmp.name
            file.save(tmp_path)
        raw_save = parse_gvas(tmp_path)
    except Exception:
        # On logue le détail réel côté serveur (avec la stack trace)...
        app.logger.exception("parse_gvas a échoué")
        # ...mais on ne renvoie qu'un message générique au client (pas de fuite
        # d'internes du parseur, qui aideraient à forger un .sav malveillant).
        return jsonify({
            "ok": False,
            "error": "Could not parse the save file."
        }), 422
    finally:
        # Toujours supprimer le fichier temporaire, y compris si file.save() a
        # échoué après sa création (sinon il fuiterait sur le disque).
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # 4. Construire les données du dashboard
    try:
        dashboard_data = build_dashboard_data(raw_save, player_name)
    except Exception:
        app.logger.exception("build_dashboard_data a échoué")
        return jsonify({
            "ok": False,
            "error": "Could not build the dashboard."
        }), 500

    return jsonify({"ok": True, "data": dashboard_data})


# ── Health check (utile pour Vercel et les monitors) ─────────────────────────

@app.route("/api/health", methods=["GET"])
@limiter.exempt  # les monitors pingent souvent (>60/h) : ne pas les bloquer en 429
def health():
    return jsonify({"ok": True, "service": "drg-dashboard-api"})


# ── Gestion des erreurs globales ──────────────────────────────────────────────

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({
        "ok": False,
        "error": f"File too large (max {MAX_FILE_SIZE_MB}MB)"
    }), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({"ok": False, "error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"ok": False, "error": "Method not allowed"}), 405

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"ok": False, "error": "Too many requests. Slow down."}), 429


# ── Lancement local ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # debug=True ouvre la console Werkzeug (exécution de code à distance si exposée)
    # et fait fuiter les stack traces. On le pilote par env, désactivé par défaut.
    # En local : FLASK_DEBUG=1 python api.py
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    print("DRG Dashboard API — http://localhost:5000")
    print("Endpoint : POST /api/parse")
    print("           GET  /api/health")
    print(f"Debug : {'ON' if debug else 'OFF'}")
    app.run(debug=debug, port=5000)
