"""
Power Grid Data Scraper & Optimizer — Flask Web Application
------------------------------------------------------------
Routes:
  GET  /                          → Main web interface
  GET  /api/states                → List of all US states
  GET  /api/cities?state=<name>   → Cities for a given state
  POST /api/analyze               → Scrape + optimize for {state, city}
"""

import os
import logging
import json
import numpy as np
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from data.us_cities import get_states, get_cities, get_state_abbrev
from scraper import PowerGridScraper
from optimizer import PowerGridOptimizer

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


def _native(obj):
    """Recursively convert numpy scalars/arrays to native Python types."""
    if isinstance(obj, dict):
        return {k: _native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_native(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [_native(v) for v in obj.tolist()]
    return obj

EIA_API_KEY = os.getenv("EIA_API_KEY")
OPENEI_API_KEY = os.getenv("OPENEI_API_KEY", "DEMO_KEY")

if not EIA_API_KEY:
    logger.warning(
        "EIA_API_KEY not set — using simulated state data. "
        "Get a free key at https://www.eia.gov/opendata/"
    )


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/states")
def api_states():
    return jsonify(get_states())


@app.route("/api/cities")
def api_cities():
    state = request.args.get("state", "").strip()
    if not state:
        return jsonify({"error": "state parameter required"}), 400
    cities = get_cities(state)
    if not cities:
        return jsonify({"error": f"No cities found for state: {state}"}), 404
    return jsonify(cities)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    body = request.get_json(silent=True) or {}
    state = body.get("state", "").strip()
    city = body.get("city", "").strip()

    if not state or not city:
        return jsonify({"error": "Both 'state' and 'city' are required"}), 400

    state_abbrev = get_state_abbrev(state)
    if not state_abbrev:
        return jsonify({"error": f"Unknown state: {state}"}), 400

    logger.info(f"Analyzing grid for {city}, {state} ({state_abbrev})")

    try:
        scraper = PowerGridScraper(
            eia_api_key=EIA_API_KEY,
            openei_api_key=OPENEI_API_KEY,
        )
        grid_data = scraper.get_grid_data(state, city, state_abbrev)

        optimizer = PowerGridOptimizer()
        optimization = optimizer.optimize(grid_data)

        payload = _native({
            "state": state,
            "city": city,
            "state_abbrev": state_abbrev,
            "provider": grid_data.get("provider"),
            "grid": {
                "generation_mix": grid_data.get("generation_mix"),
                "total_capacity_mw": grid_data.get("total_capacity_mw"),
                "peak_demand_mw": grid_data.get("peak_demand_mw"),
                "avg_demand_mw": grid_data.get("avg_demand_mw"),
                "retail_price_cents_kwh": grid_data.get("retail_price_cents_kwh"),
                "annual_sales_gwh": grid_data.get("annual_sales_gwh"),
                "data_source": grid_data.get("data_source"),
                "data_year": grid_data.get("data_year"),
            },
            "optimization": optimization,
        })
        return jsonify(payload)

    except Exception as e:
        logger.exception(f"Analysis failed for {city}, {state}")
        return jsonify({"error": str(e)}), 500


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
