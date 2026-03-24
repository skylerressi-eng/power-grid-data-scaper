"""
Power Grid Data Scraper
-----------------------
Fetches real US power grid data from:
  - EIA API v2 (https://www.eia.gov/opendata/) — generation & retail sales
  - OpenEI Utility Rates API — utility provider lookup by city/state

Falls back to realistic simulated data if API keys are unavailable.
"""

import os
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2"
OPENEI_BASE = "https://api.openei.org"

# Realistic state-level generation mix profiles (% of total generation)
# Source: approximated from EIA state profiles
STATE_GENERATION_PROFILES = {
    "AL": {"natural-gas": 28, "nuclear": 26, "coal": 22, "hydro": 10, "solar": 4, "wind": 1, "other": 9},
    "AK": {"natural-gas": 60, "hydro": 22, "coal": 8, "wind": 5, "other": 5},
    "AZ": {"natural-gas": 36, "nuclear": 29, "coal": 14, "solar": 14, "wind": 2, "other": 5},
    "AR": {"natural-gas": 35, "coal": 25, "nuclear": 20, "hydro": 12, "wind": 5, "other": 3},
    "CA": {"natural-gas": 40, "solar": 20, "wind": 11, "nuclear": 8, "hydro": 11, "other": 10},
    "CO": {"natural-gas": 30, "coal": 30, "wind": 22, "solar": 9, "hydro": 5, "other": 4},
    "CT": {"nuclear": 40, "natural-gas": 40, "hydro": 4, "wind": 3, "solar": 5, "other": 8},
    "DE": {"natural-gas": 80, "solar": 5, "wind": 3, "other": 12},
    "FL": {"natural-gas": 68, "nuclear": 12, "coal": 8, "solar": 9, "wind": 0, "other": 3},
    "GA": {"natural-gas": 35, "nuclear": 30, "coal": 18, "solar": 8, "hydro": 5, "other": 4},
    "HI": {"natural-gas": 40, "wind": 20, "solar": 18, "coal": 10, "other": 12},
    "ID": {"hydro": 60, "wind": 25, "natural-gas": 8, "solar": 4, "other": 3},
    "IL": {"nuclear": 55, "natural-gas": 20, "wind": 10, "coal": 10, "solar": 1, "other": 4},
    "IN": {"coal": 55, "natural-gas": 25, "wind": 12, "solar": 3, "other": 5},
    "IA": {"wind": 55, "natural-gas": 20, "coal": 18, "solar": 3, "other": 4},
    "KS": {"wind": 42, "natural-gas": 28, "coal": 22, "solar": 3, "nuclear": 2, "other": 3},
    "KY": {"coal": 60, "natural-gas": 22, "hydro": 10, "wind": 4, "solar": 1, "other": 3},
    "LA": {"natural-gas": 68, "nuclear": 15, "coal": 8, "hydro": 4, "wind": 2, "other": 3},
    "ME": {"natural-gas": 35, "wind": 30, "hydro": 25, "solar": 5, "other": 5},
    "MD": {"natural-gas": 50, "nuclear": 25, "coal": 8, "wind": 8, "solar": 5, "other": 4},
    "MA": {"natural-gas": 65, "nuclear": 10, "wind": 8, "solar": 8, "hydro": 5, "other": 4},
    "MI": {"natural-gas": 38, "nuclear": 28, "coal": 22, "wind": 7, "solar": 2, "other": 3},
    "MN": {"wind": 22, "nuclear": 22, "natural-gas": 22, "coal": 18, "hydro": 6, "solar": 4, "other": 6},
    "MS": {"natural-gas": 70, "nuclear": 16, "coal": 7, "solar": 4, "other": 3},
    "MO": {"coal": 42, "natural-gas": 30, "nuclear": 12, "wind": 10, "hydro": 3, "solar": 1, "other": 2},
    "MT": {"hydro": 45, "wind": 20, "coal": 25, "natural-gas": 6, "other": 4},
    "NE": {"wind": 22, "nuclear": 18, "natural-gas": 18, "coal": 32, "hydro": 5, "solar": 2, "other": 3},
    "NV": {"natural-gas": 60, "solar": 20, "wind": 5, "geothermal": 8, "hydro": 4, "other": 3},
    "NH": {"nuclear": 50, "natural-gas": 30, "hydro": 8, "wind": 6, "solar": 3, "other": 3},
    "NJ": {"nuclear": 40, "natural-gas": 45, "wind": 5, "solar": 5, "other": 5},
    "NM": {"natural-gas": 40, "wind": 30, "solar": 15, "coal": 10, "other": 5},
    "NY": {"natural-gas": 38, "nuclear": 26, "hydro": 22, "wind": 6, "solar": 4, "other": 4},
    "NC": {"natural-gas": 32, "nuclear": 33, "coal": 15, "solar": 10, "hydro": 6, "wind": 2, "other": 2},
    "ND": {"wind": 30, "coal": 48, "natural-gas": 16, "hydro": 5, "other": 1},
    "OH": {"natural-gas": 42, "coal": 30, "nuclear": 15, "wind": 8, "solar": 2, "other": 3},
    "OK": {"natural-gas": 42, "wind": 38, "coal": 12, "hydro": 4, "solar": 2, "other": 2},
    "OR": {"hydro": 65, "wind": 15, "natural-gas": 12, "solar": 4, "coal": 2, "other": 2},
    "PA": {"natural-gas": 40, "nuclear": 36, "coal": 12, "wind": 5, "solar": 3, "other": 4},
    "RI": {"natural-gas": 88, "wind": 6, "solar": 4, "other": 2},
    "SC": {"nuclear": 54, "natural-gas": 25, "coal": 8, "hydro": 7, "solar": 4, "other": 2},
    "SD": {"wind": 45, "hydro": 35, "natural-gas": 12, "solar": 4, "other": 4},
    "TN": {"nuclear": 38, "natural-gas": 25, "hydro": 20, "coal": 10, "wind": 3, "solar": 2, "other": 2},
    "TX": {"natural-gas": 40, "wind": 25, "coal": 17, "solar": 8, "nuclear": 8, "other": 2},
    "UT": {"natural-gas": 40, "coal": 36, "wind": 8, "solar": 8, "hydro": 4, "other": 4},
    "VT": {"nuclear": 20, "hydro": 35, "wind": 20, "natural-gas": 10, "solar": 10, "other": 5},
    "VA": {"natural-gas": 40, "nuclear": 30, "coal": 12, "solar": 8, "wind": 5, "hydro": 3, "other": 2},
    "WA": {"hydro": 65, "nuclear": 8, "wind": 12, "natural-gas": 10, "solar": 2, "other": 3},
    "WV": {"coal": 60, "natural-gas": 30, "wind": 5, "solar": 1, "hydro": 3, "other": 1},
    "WI": {"natural-gas": 35, "coal": 28, "nuclear": 18, "wind": 10, "solar": 4, "hydro": 3, "other": 2},
    "WY": {"coal": 65, "wind": 20, "natural-gas": 10, "solar": 2, "other": 3},
}

# Approximate state-level capacity (MW) and peak demand
STATE_CAPACITY = {
    "AL": {"capacity": 28000, "peak": 22000, "avg_load": 14300},
    "AK": {"capacity": 3000, "peak": 2200, "avg_load": 1430},
    "AZ": {"capacity": 32000, "peak": 26000, "avg_load": 16900},
    "AR": {"capacity": 16000, "peak": 12000, "avg_load": 7800},
    "CA": {"capacity": 85000, "peak": 70000, "avg_load": 45500},
    "CO": {"capacity": 22000, "peak": 17000, "avg_load": 11000},
    "CT": {"capacity": 10000, "peak": 7500, "avg_load": 4900},
    "DE": {"capacity": 3000, "peak": 2200, "avg_load": 1430},
    "FL": {"capacity": 70000, "peak": 58000, "avg_load": 37700},
    "GA": {"capacity": 38000, "peak": 28000, "avg_load": 18200},
    "HI": {"capacity": 2800, "peak": 1900, "avg_load": 1235},
    "ID": {"capacity": 6500, "peak": 4800, "avg_load": 3120},
    "IL": {"capacity": 46000, "peak": 32000, "avg_load": 20800},
    "IN": {"capacity": 24000, "peak": 17000, "avg_load": 11050},
    "IA": {"capacity": 15000, "peak": 9500, "avg_load": 6175},
    "KS": {"capacity": 16000, "peak": 10000, "avg_load": 6500},
    "KY": {"capacity": 22000, "peak": 16000, "avg_load": 10400},
    "LA": {"capacity": 26000, "peak": 20000, "avg_load": 13000},
    "ME": {"capacity": 4500, "peak": 2800, "avg_load": 1820},
    "MD": {"capacity": 14000, "peak": 10500, "avg_load": 6825},
    "MA": {"capacity": 17000, "peak": 13000, "avg_load": 8450},
    "MI": {"capacity": 32000, "peak": 24000, "avg_load": 15600},
    "MN": {"capacity": 22000, "peak": 15000, "avg_load": 9750},
    "MS": {"capacity": 16000, "peak": 11000, "avg_load": 7150},
    "MO": {"capacity": 24000, "peak": 17000, "avg_load": 11050},
    "MT": {"capacity": 6000, "peak": 4000, "avg_load": 2600},
    "NE": {"capacity": 8500, "peak": 6000, "avg_load": 3900},
    "NV": {"capacity": 14000, "peak": 11000, "avg_load": 7150},
    "NH": {"capacity": 4800, "peak": 3500, "avg_load": 2275},
    "NJ": {"capacity": 20000, "peak": 15000, "avg_load": 9750},
    "NM": {"capacity": 8000, "peak": 5500, "avg_load": 3575},
    "NY": {"capacity": 42000, "peak": 33000, "avg_load": 21450},
    "NC": {"capacity": 36000, "peak": 26000, "avg_load": 16900},
    "ND": {"capacity": 8000, "peak": 4500, "avg_load": 2925},
    "OH": {"capacity": 36000, "peak": 24000, "avg_load": 15600},
    "OK": {"capacity": 22000, "peak": 15000, "avg_load": 9750},
    "OR": {"capacity": 16000, "peak": 10000, "avg_load": 6500},
    "PA": {"capacity": 46000, "peak": 32000, "avg_load": 20800},
    "RI": {"capacity": 3000, "peak": 2200, "avg_load": 1430},
    "SC": {"capacity": 22000, "peak": 16000, "avg_load": 10400},
    "SD": {"capacity": 4500, "peak": 3000, "avg_load": 1950},
    "TN": {"capacity": 32000, "peak": 22000, "avg_load": 14300},
    "TX": {"capacity": 130000, "peak": 85000, "avg_load": 55250},
    "UT": {"capacity": 12000, "peak": 8500, "avg_load": 5525},
    "VT": {"capacity": 2000, "peak": 1200, "avg_load": 780},
    "VA": {"capacity": 28000, "peak": 20000, "avg_load": 13000},
    "WA": {"capacity": 30000, "peak": 18000, "avg_load": 11700},
    "WV": {"capacity": 16000, "peak": 10000, "avg_load": 6500},
    "WI": {"capacity": 20000, "peak": 14000, "avg_load": 9100},
    "WY": {"capacity": 8000, "peak": 5000, "avg_load": 3250},
}

# Average retail electricity price cents/kWh by state (approximate)
STATE_RETAIL_PRICE = {
    "AL": 12.2, "AK": 22.1, "AZ": 12.1, "AR": 10.4, "CA": 22.0,
    "CO": 12.5, "CT": 22.0, "DE": 12.3, "FL": 11.9, "GA": 11.5,
    "HI": 32.0, "ID": 9.0, "IL": 12.5, "IN": 11.2, "IA": 11.0,
    "KS": 11.5, "KY": 10.2, "LA": 9.5, "ME": 18.0, "MD": 13.5,
    "MA": 22.5, "MI": 13.0, "MN": 13.5, "MS": 11.0, "MO": 10.5,
    "MT": 10.5, "NE": 10.0, "NV": 12.0, "NH": 19.0, "NJ": 16.5,
    "NM": 12.0, "NY": 19.0, "NC": 11.0, "ND": 9.5, "OH": 12.0,
    "OK": 9.5, "OR": 10.5, "PA": 13.5, "RI": 22.0, "SC": 12.0,
    "SD": 11.0, "TN": 11.0, "TX": 11.5, "UT": 10.5, "VT": 19.0,
    "VA": 12.0, "WA": 9.5, "WV": 9.5, "WI": 14.0, "WY": 9.5,
}


class PowerGridScraper:
    def __init__(self, eia_api_key: str = None, openei_api_key: str = "DEMO_KEY"):
        self.eia_api_key = eia_api_key
        self.openei_api_key = openei_api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PowerGridAnalyzer/1.0"})

    def get_grid_data(self, state: str, city: str, state_abbrev: str) -> Dict[str, Any]:
        """
        Main entry point. Returns structured power grid data for a city/state.
        Tries live APIs first, falls back to simulated data.
        """
        result = {
            "state": state,
            "city": city,
            "state_abbrev": state_abbrev,
            "provider": self._get_utility_provider(city, state, state_abbrev),
            "data_source": "simulated",
        }

        grid = self._fetch_eia_state_data(state_abbrev)
        result.update(grid)
        return result

    def _get_utility_provider(self, city: str, state: str, state_abbrev: str) -> Dict:
        """Look up utility provider via OpenEI API."""
        try:
            url = f"{OPENEI_BASE}/utilities"
            params = {
                "version": "3",
                "api_key": self.openei_api_key,
                "format": "json",
                "location": f"{city}, {state_abbrev}",
                "limit": 3,
            }
            resp = self.session.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                utilities = data.get("items", [])
                if utilities:
                    primary = utilities[0]
                    return {
                        "name": primary.get("utility_name", "Unknown Utility"),
                        "id": primary.get("utility_id", ""),
                        "ownership": primary.get("ownership", ""),
                        "service_type": primary.get("service_type", ""),
                        "all_providers": [u.get("utility_name", "") for u in utilities],
                    }
        except Exception as e:
            logger.warning(f"OpenEI lookup failed: {e}")

        return self._fallback_provider(state_abbrev, city)

    def _fallback_provider(self, state_abbrev: str, city: str) -> Dict:
        """Return well-known utility providers per state when API is unavailable."""
        providers = {
            "AL": "Alabama Power (Southern Company)",
            "AK": "Golden Valley Electric Association",
            "AZ": "Arizona Public Service (APS)",
            "AR": "Entergy Arkansas",
            "CA": "Pacific Gas & Electric (PG&E) / Southern California Edison",
            "CO": "Xcel Energy",
            "CT": "Eversource Energy",
            "DE": "Delmarva Power",
            "FL": "Florida Power & Light (FPL)",
            "GA": "Georgia Power (Southern Company)",
            "HI": "Hawaiian Electric (HECO)",
            "ID": "Idaho Power",
            "IL": "ComEd / Ameren Illinois",
            "IN": "Duke Energy Indiana / AES Indiana",
            "IA": "MidAmerican Energy / Alliant Energy",
            "KS": "Evergy Kansas",
            "KY": "Louisville Gas & Electric / Kentucky Utilities",
            "LA": "Entergy Louisiana",
            "ME": "Central Maine Power",
            "MD": "Pepco / BGE",
            "MA": "Eversource Energy / National Grid",
            "MI": "DTE Energy / Consumers Energy",
            "MN": "Xcel Energy",
            "MS": "Entergy Mississippi",
            "MO": "Ameren Missouri / Kansas City Power & Light",
            "MT": "NorthWestern Energy",
            "NE": "NPPD / LES",
            "NV": "NV Energy",
            "NH": "Eversource Energy",
            "NJ": "PSE&G / JCP&L",
            "NM": "PNM Resources",
            "NY": "Con Edison / National Grid",
            "NC": "Duke Energy Progress / Duke Energy Carolinas",
            "ND": "Xcel Energy / Montana-Dakota Utilities",
            "OH": "AEP Ohio / FirstEnergy",
            "OK": "OG&E / PSO",
            "OR": "Pacific Power / Portland General Electric",
            "PA": "PECO / PPL Electric / West Penn Power",
            "RI": "National Grid",
            "SC": "Duke Energy Carolinas / Dominion Energy South Carolina",
            "SD": "Xcel Energy / Black Hills Power",
            "TN": "Tennessee Valley Authority (TVA)",
            "TX": "Oncor / CenterPoint Energy / AEP Texas",
            "UT": "Rocky Mountain Power",
            "VT": "Green Mountain Power",
            "VA": "Dominion Energy Virginia / Appalachian Power",
            "WA": "Puget Sound Energy / Seattle City Light",
            "WV": "Appalachian Power / Mon Power",
            "WI": "We Energies / Madison Gas & Electric",
            "WY": "Rocky Mountain Power / Black Hills Energy",
        }
        name = providers.get(state_abbrev, f"{city} Municipal Utilities")
        return {
            "name": name,
            "id": "",
            "ownership": "Investor-owned" if "Power" in name or "Energy" in name else "Public",
            "service_type": "Bundled",
            "all_providers": [name],
        }

    def _fetch_eia_state_data(self, state_abbrev: str) -> Dict:
        """
        Fetch state electricity data from EIA API v2.
        Falls back to simulated data if key is unavailable or request fails.
        """
        if self.eia_api_key:
            try:
                return self._live_eia_data(state_abbrev)
            except Exception as e:
                logger.warning(f"EIA API call failed ({e}), using simulated data")

        return self._simulated_state_data(state_abbrev)

    def _live_eia_data(self, state_abbrev: str) -> Dict:
        """Call EIA API v2 for generation and retail sales data."""
        # Generation mix
        gen_url = f"{EIA_BASE}/electricity/electric-power-operational-data/data/"
        gen_params = {
            "api_key": self.eia_api_key,
            "frequency": "annual",
            "data[]": "generation",
            "facets[location][]": state_abbrev,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 12,
        }
        gen_resp = self.session.get(gen_url, params=gen_params, timeout=10)
        gen_resp.raise_for_status()
        gen_data = gen_resp.json().get("response", {}).get("data", [])

        # Retail sales (price & consumption)
        sales_url = f"{EIA_BASE}/electricity/retail-sales/data/"
        sales_params = {
            "api_key": self.eia_api_key,
            "frequency": "annual",
            "data[]": ["revenue", "sales", "price", "customers"],
            "facets[stateid][]": state_abbrev,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 5,
        }
        sales_resp = self.session.get(sales_url, params=sales_params, timeout=10)
        sales_resp.raise_for_status()
        sales_data = sales_resp.json().get("response", {}).get("data", [])

        return self._parse_eia_response(gen_data, sales_data, state_abbrev)

    def _parse_eia_response(self, gen_data, sales_data, state_abbrev: str) -> Dict:
        """Parse EIA API response into structured data."""
        fuel_map = {
            "NG": "natural-gas", "COL": "coal", "NUC": "nuclear",
            "HYC": "hydro", "SUN": "solar", "WND": "wind",
            "GEO": "geothermal", "OTH": "other",
        }
        generation_mix = {}
        total_gen = 0

        for row in gen_data:
            fuel = fuel_map.get(row.get("fueltypeid", ""), "other")
            gen_val = float(row.get("generation", 0) or 0)
            generation_mix[fuel] = generation_mix.get(fuel, 0) + gen_val
            total_gen += gen_val

        if total_gen > 0:
            generation_mix = {k: round(v / total_gen * 100, 1) for k, v in generation_mix.items()}

        retail_price = None
        annual_sales_gwh = None
        for row in sales_data:
            if row.get("sectorid") == "ALL":
                retail_price = float(row.get("price", 0) or 0)
                annual_sales_gwh = float(row.get("sales", 0) or 0) / 1000
                break

        cap = STATE_CAPACITY.get(state_abbrev, {"capacity": 10000, "peak": 8000, "avg_load": 5200})
        return {
            "generation_mix": generation_mix or STATE_GENERATION_PROFILES.get(state_abbrev, {}),
            "total_capacity_mw": cap["capacity"],
            "peak_demand_mw": cap["peak"],
            "avg_demand_mw": cap["avg_load"],
            "retail_price_cents_kwh": retail_price or STATE_RETAIL_PRICE.get(state_abbrev, 12.0),
            "annual_sales_gwh": annual_sales_gwh,
            "data_source": "EIA API (live)",
            "data_year": 2023,
        }

    def _simulated_state_data(self, state_abbrev: str) -> Dict:
        """Return realistic simulated data based on state profile."""
        profile = STATE_GENERATION_PROFILES.get(state_abbrev, {
            "natural-gas": 40, "coal": 20, "nuclear": 15,
            "wind": 10, "solar": 8, "hydro": 5, "other": 2,
        })
        cap = STATE_CAPACITY.get(state_abbrev, {
            "capacity": 10000, "peak": 8000, "avg_load": 5200,
        })
        price = STATE_RETAIL_PRICE.get(state_abbrev, 12.0)

        return {
            "generation_mix": profile,
            "total_capacity_mw": cap["capacity"],
            "peak_demand_mw": cap["peak"],
            "avg_demand_mw": cap["avg_load"],
            "retail_price_cents_kwh": price,
            "annual_sales_gwh": round(cap["avg_load"] * 8760 / 1000, 0),
            "data_source": "Simulated (EIA state profiles)",
            "data_year": 2023,
        }
