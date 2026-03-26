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

from data.us_cities import get_states, get_cities, get_state_abbrev, get_regions, get_cities_by_region
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


@app.route("/api/regions")
def api_regions():
    state = request.args.get("state", "").strip()
    if not state:
        return jsonify({"error": "state parameter required"}), 400
    regions = get_regions(state)
    return jsonify(regions)


@app.route("/api/cities")
def api_cities():
    state = request.args.get("state", "").strip()
    region = request.args.get("region", "").strip()
    if not state:
        return jsonify({"error": "state parameter required"}), 400
    if region and region != "All Cities":
        cities = get_cities_by_region(state, region)
    else:
        cities = get_cities(state)
    if not cities:
        return jsonify({"error": f"No cities found for state: {state}"}), 404
    return jsonify(cities)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    body = request.get_json(silent=True) or {}
    state = body.get("state", "").strip()
    city = body.get("city", "").strip()
    # Allow the UI to supply an API key directly (stored in browser localStorage)
    request_eia_key = (body.get("eia_api_key") or "").strip()
    effective_eia_key = request_eia_key or EIA_API_KEY

    if not state or not city:
        return jsonify({"error": "Both 'state' and 'city' are required"}), 400

    state_abbrev = get_state_abbrev(state)
    if not state_abbrev:
        return jsonify({"error": f"Unknown state: {state}"}), 400

    logger.info(
        f"Analyzing grid for {city}, {state} ({state_abbrev}) | "
        f"EIA key: {'UI-supplied' if request_eia_key else 'env' if EIA_API_KEY else 'none (simulated)'}"
    )

    try:
        scraper = PowerGridScraper(
            eia_api_key=effective_eia_key,
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
            "city_stats": grid_data.get("city_stats"),
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
            "historical": grid_data.get("historical", []),
            "optimization": optimization,
        })
        return jsonify(payload)

    except PermissionError as e:
        # Invalid / missing API key — return 400 so the UI can show the message
        return jsonify({"error": str(e), "error_type": "invalid_key"}), 400
    except Exception as e:
        logger.exception(f"Analysis failed for {city}, {state}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    body = request.get_json(silent=True) or {}
    state = body.get("state", "").strip()
    city = body.get("city", "").strip()
    request_eia_key = (body.get("eia_api_key") or "").strip()
    effective_eia_key = request_eia_key or EIA_API_KEY
    savings_goal = max(1.0, float(body.get("savings_goal", 100.0) or 100.0))
    requested_sims = int(body.get("max_sims", 100) or 100)
    max_sims = min(requested_sims, 500)

    if not state or not city:
        return jsonify({"error": "Both 'state' and 'city' are required"}), 400

    state_abbrev = get_state_abbrev(state)
    if not state_abbrev:
        return jsonify({"error": f"Unknown state: {state}"}), 400

    try:
        scraper = PowerGridScraper(
            eia_api_key=effective_eia_key,
            openei_api_key=OPENEI_API_KEY,
        )
        grid_data = scraper.get_grid_data(state, city, state_abbrev)
        optimizer = PowerGridOptimizer()
        result = optimizer.run_goal_simulations(
            grid_data, savings_goal=savings_goal, max_sims=max_sims
        )
        return jsonify(_native(result))
    except PermissionError as e:
        return jsonify({"error": str(e), "error_type": "invalid_key"}), 400
    except Exception as e:
        logger.exception(f"Simulation failed for {city}, {state}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/test-key", methods=["POST"])
def api_test_key():
    """
    Validate an EIA API key by making a minimal live request.
    Body: { "eia_api_key": "..." }
    Returns: { "valid": true/false, "message": "..." }
    """
    body = request.get_json(silent=True) or {}
    key = (body.get("eia_api_key") or "").strip()
    if not key:
        return jsonify({"valid": False, "message": "No API key provided."})
    try:
        # Minimal probe: 1 row from retail-sales for CA
        probe_url = (
            "https://api.eia.gov/v2/electricity/retail-sales/data/"
            f"?api_key={key}&frequency=annual&data[0]=price"
            "&facets[stateid][]=CA&sort[0][column]=period"
            "&sort[0][direction]=desc&length=1"
        )
        result = PowerGridScraper._eia_get(probe_url)
        rows = result.get("response", {}).get("data", [])
        if rows:
            return jsonify({"valid": True, "message": "API key valid — live EIA data active."})
        return jsonify({"valid": True, "message": "Key accepted (probe returned 0 rows — try a full analysis)."})
    except PermissionError:
        return jsonify({"valid": False, "message": "Invalid API key (403 Forbidden). Check your key at eia.gov/opendata."})
    except Exception as e:
        return jsonify({"valid": False, "message": f"Test failed: {e}"})


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
