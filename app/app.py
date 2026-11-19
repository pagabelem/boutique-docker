
import os
import time
import json
import psycopg
import redis

from flask import Flask, request, jsonify
from psycopg.rows import dict_row

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

cache = redis.from_url(REDIS_URL, decode_responses=True)


def get_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    for attempt in range(15):
        try:
            with get_db() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS produits (
                        id SERIAL PRIMARY KEY,
                        nom VARCHAR(150) NOT NULL,
                        prix NUMERIC(10,2) NOT NULL,
                        stock INTEGER NOT NULL DEFAULT 0
                    )
                """)
            print("Base PostgreSQL initialisee.")
            return
        except Exception as e:
            print(f"Attente PostgreSQL : {e}")
            time.sleep(2)

    raise RuntimeError("PostgreSQL indisponible")


@app.route("/")
def accueil():
    return jsonify({
        "message": "Bienvenue dans notre boutique Docker",
        "api": "Flask + PostgreSQL + Redis"
    })


@app.route("/health")
def health():
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        cache.ping()
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route("/produits", methods=["GET"])
def get_produits():
    cached = cache.get("produits")

    if cached:
        return jsonify({
            "source": "Redis",
            "produits": json.loads(cached)
        })

    with get_db() as conn:
        produits = conn.execute(
            "SELECT * FROM produits ORDER BY id"
        ).fetchall()

    result = [dict(p) for p in produits]

    for p in result:
        p["prix"] = float(p["prix"])

    cache.setex("produits", 60, json.dumps(result))

    return jsonify({
        "source": "PostgreSQL",
        "produits": result
    })


@app.route("/produits", methods=["POST"])
def ajouter_produit():
    data = request.get_json(silent=True) or {}

    if not all(k in data for k in ["nom", "prix", "stock"]):
        return jsonify({"erreur": "nom, prix et stock obligatoires"}), 400

    if not isinstance(data["nom"], str) or not data["nom"].strip():
        return jsonify({"erreur": "Nom invalide"}), 400

    try:
        prix = float(data["prix"])
        stock = int(data["stock"])
        if prix < 0 or stock < 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"erreur": "Prix ou stock invalide"}), 400

    with get_db() as conn:
        produit = conn.execute(
            """
            INSERT INTO produits (nom, prix, stock)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (data["nom"].strip(), prix, stock)
        ).fetchone()

    cache.delete("produits")

    result = dict(produit)
    result["prix"] = float(result["prix"])

    return jsonify(result), 201


@app.route("/produits/<int:produit_id>", methods=["GET"])
def detail_produit(produit_id):
    with get_db() as conn:
        produit = conn.execute(
            "SELECT * FROM produits WHERE id = %s",
            (produit_id,)
        ).fetchone()

    if not produit:
        return jsonify({"erreur": "Produit introuvable"}), 404

    result = dict(produit)
    result["prix"] = float(result["prix"])
    return jsonify(result)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
