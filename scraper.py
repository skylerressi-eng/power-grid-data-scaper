"""
Power Grid Data Scraper
-----------------------
Fetches real US power grid data from:
  - EIA API v2 (https://www.eia.gov/opendata/) — generation & retail sales
  - OpenEI Utility Rates API — utility provider lookup by city/state

Falls back to realistic simulated data if API keys are unavailable.
"""

import os
import json as _json
import requests
import logging
from typing import Dict, Any
from urllib.request import urlopen as _urlopen, Request as _URequest
from urllib.error import HTTPError as _HTTPError

logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2"
OPENEI_BASE = "https://api.openei.org"

# Realistic state-level generation mix profiles (% of total generation)
# Source: approximated from EIA state profiles
STATE_GENERATION_PROFILES = {
    "DC": {"natural-gas": 72, "solar": 10, "wind": 5, "hydro": 2, "other": 11},
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

# City-specific generation mix overrides — used when city's grid differs from state average.
# Reflects local utility, climate zone, and known renewable/fossil mix differences.
CITY_GENERATION_PROFILES = {
    # ── California: Bay Area PG&E territory ──────────────────────────────────
    # Palo Alto: City of Palo Alto Utilities (CPAU) — 100% carbon-free portfolio
    "Palo Alto":      {"hydro": 45, "nuclear": 25, "solar": 15, "wind": 10, "geothermal": 5},
    # San Francisco: PG&E + CleanPowerSF — high renewables, some gas peakers
    "San Francisco":  {"natural-gas": 30, "hydro": 18, "solar": 22, "wind": 15, "nuclear": 8, "other": 7},
    # Oakland / Berkeley / East Bay: PG&E + East Bay Community Energy
    "Oakland":        {"natural-gas": 35, "hydro": 12, "solar": 20, "wind": 12, "nuclear": 8, "other": 13},
    "Berkeley":       {"natural-gas": 32, "hydro": 12, "solar": 22, "wind": 14, "nuclear": 8, "other": 12},
    "Richmond":       {"natural-gas": 45, "hydro": 10, "solar": 15, "wind": 10, "nuclear": 8, "other": 12},
    # Bay Area South (PG&E / Silicon Valley Clean Energy)
    "San Jose":       {"natural-gas": 38, "hydro": 10, "solar": 22, "wind": 11, "nuclear": 8, "other": 11},
    "Los Altos":      {"natural-gas": 37, "hydro": 10, "solar": 23, "wind": 12, "nuclear": 9, "other": 9},
    "Mountain View":  {"natural-gas": 36, "hydro": 10, "solar": 24, "wind": 12, "nuclear": 9, "other": 9},
    "Sunnyvale":      {"natural-gas": 36, "hydro": 10, "solar": 24, "wind": 12, "nuclear": 9, "other": 9},
    "Cupertino":      {"natural-gas": 36, "hydro": 10, "solar": 24, "wind": 12, "nuclear": 9, "other": 9},
    "Santa Clara":    {"natural-gas": 36, "hydro": 10, "solar": 24, "wind": 12, "nuclear": 9, "other": 9},
    "Fremont":        {"natural-gas": 38, "hydro": 10, "solar": 22, "wind": 12, "nuclear": 8, "other": 10},
    "Menlo Park":     {"natural-gas": 36, "hydro": 10, "solar": 24, "wind": 12, "nuclear": 9, "other": 9},
    "Redwood City":   {"natural-gas": 37, "hydro": 10, "solar": 23, "wind": 12, "nuclear": 9, "other": 9},
    "San Mateo":      {"natural-gas": 38, "hydro": 10, "solar": 22, "wind": 12, "nuclear": 9, "other": 9},
    "Burlingame":     {"natural-gas": 38, "hydro": 10, "solar": 22, "wind": 12, "nuclear": 9, "other": 9},
    "Daly City":      {"natural-gas": 39, "hydro": 10, "solar": 21, "wind": 12, "nuclear": 8, "other": 10},
    "South San Francisco": {"natural-gas": 39, "hydro": 10, "solar": 21, "wind": 12, "nuclear": 8, "other": 10},
    "East Palo Alto": {"natural-gas": 38, "hydro": 10, "solar": 22, "wind": 12, "nuclear": 9, "other": 9},
    # Bay Area East (PG&E, hotter/inland)
    "Hayward":        {"natural-gas": 40, "hydro": 10, "solar": 20, "wind": 11, "nuclear": 8, "other": 11},
    "Fremont":        {"natural-gas": 38, "hydro": 10, "solar": 22, "wind": 12, "nuclear": 8, "other": 10},
    "Pleasanton":     {"natural-gas": 40, "hydro": 10, "solar": 20, "wind": 11, "nuclear": 8, "other": 11},
    "Livermore":      {"natural-gas": 42, "hydro": 9, "solar": 19, "wind": 11, "nuclear": 8, "other": 11},
    "Concord":        {"natural-gas": 42, "hydro": 9, "solar": 18, "wind": 11, "nuclear": 8, "other": 12},
    "Walnut Creek":   {"natural-gas": 41, "hydro": 9, "solar": 19, "wind": 11, "nuclear": 8, "other": 12},
    "San Ramon":      {"natural-gas": 40, "hydro": 10, "solar": 20, "wind": 11, "nuclear": 8, "other": 11},
    "Antioch":        {"natural-gas": 46, "hydro": 8, "solar": 16, "wind": 10, "nuclear": 7, "other": 13},
    # North Bay (PG&E)
    "Vallejo":        {"natural-gas": 40, "hydro": 11, "solar": 19, "wind": 12, "nuclear": 8, "other": 10},
    "Napa":           {"natural-gas": 38, "hydro": 12, "solar": 20, "wind": 12, "nuclear": 8, "other": 10},
    "Santa Rosa":     {"natural-gas": 38, "hydro": 12, "solar": 20, "wind": 12, "nuclear": 8, "other": 10},
    "Petaluma":       {"natural-gas": 38, "hydro": 12, "solar": 20, "wind": 12, "nuclear": 8, "other": 10},
    "Novato":         {"natural-gas": 38, "hydro": 12, "solar": 20, "wind": 12, "nuclear": 8, "other": 10},
    "San Rafael":     {"natural-gas": 37, "hydro": 12, "solar": 21, "wind": 12, "nuclear": 8, "other": 10},
    "Fairfield":      {"natural-gas": 40, "hydro": 11, "solar": 19, "wind": 12, "nuclear": 8, "other": 10},
    "Vacaville":      {"natural-gas": 40, "hydro": 11, "solar": 19, "wind": 12, "nuclear": 8, "other": 10},
    # ── California: Central Valley (PG&E, natural-gas heavy) ─────────────────
    "Stockton":       {"natural-gas": 52, "hydro": 8, "solar": 15, "wind": 7, "nuclear": 7, "other": 11},
    "Modesto":        {"natural-gas": 50, "hydro": 8, "solar": 16, "wind": 8, "nuclear": 7, "other": 11},
    "Fresno":         {"natural-gas": 50, "hydro": 8, "solar": 17, "wind": 7, "nuclear": 8, "other": 10},
    "Visalia":        {"natural-gas": 50, "hydro": 7, "solar": 17, "wind": 7, "nuclear": 8, "other": 11},
    "Bakersfield":    {"natural-gas": 58, "hydro": 5, "solar": 14, "wind": 5, "nuclear": 6, "other": 12},
    "Turlock":        {"natural-gas": 50, "hydro": 8, "solar": 16, "wind": 8, "nuclear": 7, "other": 11},
    "Merced":         {"natural-gas": 50, "hydro": 8, "solar": 16, "wind": 8, "nuclear": 7, "other": 11},
    "Chico":          {"natural-gas": 47, "hydro": 11, "solar": 17, "wind": 7, "nuclear": 7, "other": 11},
    "Redding":        {"natural-gas": 44, "hydro": 14, "solar": 18, "wind": 7, "nuclear": 7, "other": 10},
    "Salinas":        {"natural-gas": 44, "hydro": 10, "solar": 17, "wind": 12, "nuclear": 7, "other": 10},
    "Hanford":        {"natural-gas": 50, "hydro": 7, "solar": 17, "wind": 7, "nuclear": 8, "other": 11},
    # ── California: Sacramento area (SMUD — public utility, more nuclear/hydro) ──
    "Sacramento":     {"natural-gas": 25, "nuclear": 25, "hydro": 20, "solar": 20, "wind": 8, "other": 2},
    "Elk Grove":      {"natural-gas": 25, "nuclear": 25, "hydro": 20, "solar": 20, "wind": 8, "other": 2},
    "Folsom":         {"natural-gas": 25, "nuclear": 25, "hydro": 20, "solar": 20, "wind": 8, "other": 2},
    "Davis":          {"natural-gas": 25, "nuclear": 25, "hydro": 20, "solar": 20, "wind": 8, "other": 2},
    "Roseville":      {"natural-gas": 28, "nuclear": 20, "hydro": 20, "solar": 22, "wind": 8, "other": 2},
    "Rocklin":        {"natural-gas": 28, "nuclear": 20, "hydro": 20, "solar": 22, "wind": 8, "other": 2},
    "Woodland":       {"natural-gas": 38, "hydro": 12, "solar": 19, "wind": 11, "nuclear": 8, "other": 12},
    # ── California: Los Angeles area (LADWP + SCE) ───────────────────────────
    "Los Angeles":    {"natural-gas": 42, "hydro": 12, "solar": 20, "wind": 8, "nuclear": 8, "other": 10},
    "Long Beach":     {"natural-gas": 45, "hydro": 10, "solar": 18, "wind": 7, "nuclear": 8, "other": 12},
    "Glendale":       {"natural-gas": 40, "hydro": 12, "solar": 20, "wind": 8, "nuclear": 10, "other": 10},
    "Burbank":        {"natural-gas": 40, "hydro": 12, "solar": 20, "wind": 8, "nuclear": 10, "other": 10},
    "Pasadena":       {"natural-gas": 38, "hydro": 12, "solar": 22, "wind": 8, "nuclear": 10, "other": 10},
    "Beverly Hills":  {"natural-gas": 42, "hydro": 10, "solar": 20, "wind": 8, "nuclear": 8, "other": 12},
    "Santa Monica":   {"natural-gas": 38, "hydro": 10, "solar": 25, "wind": 8, "nuclear": 8, "other": 11},
    "Torrance":       {"natural-gas": 44, "hydro": 10, "solar": 18, "wind": 7, "nuclear": 8, "other": 13},
    "El Monte":       {"natural-gas": 45, "hydro": 9, "solar": 17, "wind": 7, "nuclear": 8, "other": 14},
    "Pomona":         {"natural-gas": 46, "hydro": 8, "solar": 17, "wind": 7, "nuclear": 8, "other": 14},
    # ── California: Inland SoCal (SCE, hotter, drier) ────────────────────────
    "Anaheim":        {"natural-gas": 44, "hydro": 8, "solar": 18, "wind": 8, "nuclear": 10, "other": 12},
    "Riverside":      {"natural-gas": 46, "hydro": 6, "solar": 20, "wind": 8, "nuclear": 8, "other": 12},
    "San Bernardino": {"natural-gas": 48, "hydro": 6, "solar": 18, "wind": 8, "nuclear": 8, "other": 12},
    "Fontana":        {"natural-gas": 48, "hydro": 6, "solar": 18, "wind": 8, "nuclear": 8, "other": 12},
    "Rancho Cucamonga": {"natural-gas": 46, "hydro": 7, "solar": 19, "wind": 8, "nuclear": 8, "other": 12},
    "Victorville":    {"natural-gas": 44, "hydro": 6, "solar": 22, "wind": 10, "nuclear": 8, "other": 10},
    "Irvine":         {"natural-gas": 44, "hydro": 8, "solar": 20, "wind": 8, "nuclear": 10, "other": 10},
    "Santa Ana":      {"natural-gas": 44, "hydro": 8, "solar": 18, "wind": 8, "nuclear": 10, "other": 12},
    "Orange":         {"natural-gas": 44, "hydro": 8, "solar": 18, "wind": 8, "nuclear": 10, "other": 12},
    "Fullerton":      {"natural-gas": 44, "hydro": 8, "solar": 18, "wind": 8, "nuclear": 10, "other": 12},
    "Garden Grove":   {"natural-gas": 44, "hydro": 8, "solar": 18, "wind": 8, "nuclear": 10, "other": 12},
    "Anaheim":        {"natural-gas": 44, "hydro": 8, "solar": 18, "wind": 8, "nuclear": 10, "other": 12},
    "Murrieta":       {"natural-gas": 44, "hydro": 7, "solar": 21, "wind": 9, "nuclear": 8, "other": 11},
    "Temecula":       {"natural-gas": 44, "hydro": 7, "solar": 21, "wind": 9, "nuclear": 8, "other": 11},
    "Mission Viejo":  {"natural-gas": 44, "hydro": 8, "solar": 20, "wind": 8, "nuclear": 10, "other": 10},
    "Lake Forest":    {"natural-gas": 44, "hydro": 8, "solar": 20, "wind": 8, "nuclear": 10, "other": 10},
    "Tustin":         {"natural-gas": 44, "hydro": 8, "solar": 20, "wind": 8, "nuclear": 10, "other": 10},
    # ── California: Ventura / Santa Barbara (SCE) ────────────────────────────
    "Oxnard":         {"natural-gas": 42, "hydro": 8, "solar": 18, "wind": 10, "nuclear": 10, "other": 12},
    "Ventura":        {"natural-gas": 40, "hydro": 8, "solar": 20, "wind": 10, "nuclear": 10, "other": 12},
    "Thousand Oaks":  {"natural-gas": 40, "hydro": 8, "solar": 20, "wind": 10, "nuclear": 10, "other": 12},
    "Simi Valley":    {"natural-gas": 40, "hydro": 8, "solar": 20, "wind": 10, "nuclear": 10, "other": 12},
    "Santa Barbara":  {"natural-gas": 38, "hydro": 8, "solar": 22, "wind": 12, "nuclear": 10, "other": 10},
    # ── California: San Diego (SDG&E — highest solar penetration in CA) ──────
    "San Diego":      {"natural-gas": 35, "hydro": 8, "solar": 30, "wind": 10, "nuclear": 5, "other": 12},
    "Chula Vista":    {"natural-gas": 35, "hydro": 8, "solar": 30, "wind": 10, "nuclear": 5, "other": 12},
    "Oceanside":      {"natural-gas": 34, "hydro": 7, "solar": 30, "wind": 10, "nuclear": 5, "other": 14},
    "Carlsbad":       {"natural-gas": 33, "hydro": 7, "solar": 31, "wind": 10, "nuclear": 5, "other": 14},
    "Escondido":      {"natural-gas": 35, "hydro": 7, "solar": 28, "wind": 9, "nuclear": 5, "other": 16},
    "El Cajon":       {"natural-gas": 36, "hydro": 7, "solar": 28, "wind": 9, "nuclear": 5, "other": 15},
    "Vista":          {"natural-gas": 34, "hydro": 7, "solar": 30, "wind": 10, "nuclear": 5, "other": 14},
    "San Marcos":     {"natural-gas": 34, "hydro": 7, "solar": 30, "wind": 10, "nuclear": 5, "other": 14},
}

# Approximate state-level capacity (MW) and peak demand
STATE_CAPACITY = {
    "DC": {"capacity": 2500, "peak": 1800, "avg_load": 1100},
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

# National generation trend adjustment factors vs. 2023 baseline
# Approximated from EIA Electric Power Annual data
HISTORICAL_TREND_FACTORS = {
    2023: {"solar": 1.000, "wind": 1.000, "coal": 1.000, "natural-gas": 1.000,
           "nuclear": 1.000, "hydro": 1.000, "geothermal": 1.000, "other": 1.000,
           "price_mult": 1.000, "capacity_mult": 1.000},
    2022: {"solar": 0.790, "wind": 0.912, "coal": 1.074, "natural-gas": 1.026,
           "nuclear": 1.010, "hydro": 0.978, "geothermal": 1.000, "other": 1.010,
           "price_mult": 1.017, "capacity_mult": 0.966},
    2021: {"solar": 0.622, "wind": 0.821, "coal": 1.153, "natural-gas": 1.051,
           "nuclear": 1.017, "hydro": 1.022, "geothermal": 1.000, "other": 1.022,
           "price_mult": 0.858, "capacity_mult": 0.933},
}

RENEWABLE_FUELS = {"solar", "wind", "hydro", "geothermal"}

# Approximate city proper populations (thousands) — used to scale state data to city level
CITY_POPULATIONS = {
    # Alabama
    "Birmingham": 212, "Montgomery": 200, "Huntsville": 215, "Mobile": 187,
    "Tuscaloosa": 105, "Hoover": 92, "Dothan": 71, "Auburn": 76,
    "Decatur": 54, "Madison": 48,
    # Alaska
    "Anchorage": 291, "Fairbanks": 32, "Juneau": 32, "Sitka": 9,
    "Ketchikan": 8, "Wasilla": 10, "Kenai": 8, "Kodiak": 6,
    # Arizona
    "Phoenix": 1608, "Tucson": 548, "Mesa": 504, "Chandler": 261,
    "Scottsdale": 241, "Glendale": 248, "Gilbert": 254, "Tempe": 185,
    "Peoria": 175, "Surprise": 143, "Yuma": 99, "Avondale": 89,
    "Flagstaff": 75, "Goodyear": 93, "Lake Havasu City": 58,
    # Arkansas
    "Little Rock": 202, "Fort Smith": 89, "Fayetteville": 93,
    "Springdale": 85, "Jonesboro": 77, "North Little Rock": 67,
    "Conway": 67, "Rogers": 70, "Pine Bluff": 41, "Bentonville": 52,
    # California
    "Los Angeles": 3898, "San Diego": 1386, "San Jose": 1037,
    "San Francisco": 874, "Fresno": 542, "Sacramento": 524,
    "Long Beach": 466, "Oakland": 440, "Bakersfield": 383,
    "Anaheim": 346, "Santa Ana": 310, "Riverside": 314,
    "Stockton": 320, "Irvine": 307, "Chula Vista": 275,
    "Fremont": 230, "San Bernardino": 222, "Modesto": 218,
    "Fontana": 213, "Oxnard": 202,
    # California — Bay Area Peninsula & South Bay
    "Palo Alto": 68, "Los Altos": 30, "Mountain View": 82, "Sunnyvale": 156,
    "Cupertino": 60, "Los Gatos": 34, "Saratoga": 31, "Campbell": 43,
    "Menlo Park": 35, "Redwood City": 83, "San Mateo": 105, "Burlingame": 30,
    "San Carlos": 30, "Belmont": 26, "East Palo Alto": 29, "Atherton": 7,
    "Foster City": 32, "Millbrae": 23, "San Bruno": 44, "South San Francisco": 66,
    # California — Bay Area East & North Bay
    "Daly City": 104, "Hayward": 162, "Concord": 131, "Antioch": 119,
    "Richmond": 116, "Berkeley": 124, "Walnut Creek": 70, "Pleasanton": 79,
    "Livermore": 90, "San Ramon": 84, "Union City": 72, "Newark": 48,
    "Alameda": 77, "El Cerrito": 25, "Novato": 54, "San Rafael": 59,
    "Petaluma": 59, "Santa Rosa": 178, "Napa": 80, "Vallejo": 122,
    "Fairfield": 120, "Vacaville": 108,
    # California — Central Valley & Coast
    "Davis": 67, "Woodland": 59, "Chico": 101, "Redding": 93,
    "Roseville": 148, "Elk Grove": 176, "Folsom": 79, "Rocklin": 66,
    "Turlock": 73, "Merced": 86, "Visalia": 136, "Hanford": 56,
    "Santa Cruz": 62, "Capitola": 10, "Scotts Valley": 12,
    "Monterey": 30, "Salinas": 163, "San Luis Obispo": 47,
    "Paso Robles": 32, "Santa Maria": 109,
    # California — Southern California extras
    "Santa Barbara": 88, "Ventura": 106, "Thousand Oaks": 126,
    "Simi Valley": 126, "Glendale": 196, "Pasadena": 141, "Torrance": 147,
    "Santa Monica": 92, "Beverly Hills": 34, "Burbank": 105, "El Monte": 116,
    "Pomona": 151, "Rancho Cucamonga": 174, "Victorville": 134,
    "Garden Grove": 174, "Fullerton": 140, "Orange": 136, "Tustin": 81,
    "Mission Viejo": 93, "Lake Forest": 84, "El Cajon": 104,
    "Escondido": 151, "Oceanside": 174, "Carlsbad": 113,
    "Vista": 100, "San Marcos": 96, "Murrieta": 116, "Temecula": 113,
    # Colorado
    "Denver": 715, "Colorado Springs": 478, "Aurora": 366,
    "Fort Collins": 164, "Lakewood": 155, "Thornton": 136,
    "Arvada": 118, "Westminster": 113, "Pueblo": 111,
    "Boulder": 105, "Highlands Ranch": 105, "Greeley": 103,
    "Longmont": 92, "Loveland": 78, "Grand Junction": 63,
    # Connecticut
    "Bridgeport": 148, "New Haven": 130, "Stamford": 136,
    "Hartford": 121, "Waterbury": 114, "Norwalk": 92,
    "Danbury": 84, "New Britain": 72, "West Hartford": 64,
    "Greenwich": 63,
    # Delaware
    "Wilmington": 70, "Dover": 38, "Newark": 33, "Middletown": 23,
    "Smyrna": 12,
    # Florida
    "Jacksonville": 949, "Miami": 467, "Tampa": 399, "Orlando": 309,
    "St. Petersburg": 258, "Hialeah": 212, "Port St. Lucie": 201,
    "Tallahassee": 196, "Cape Coral": 194, "Fort Lauderdale": 182,
    "Pembroke Pines": 171, "Hollywood": 148, "Gainesville": 141,
    "Miramar": 130,
    # Georgia
    "Atlanta": 498, "Columbus": 206, "Augusta": 202, "Macon": 153,
    "Savannah": 147, "Athens": 127, "Sandy Springs": 108,
    "Roswell": 94, "Albany": 73, "Warner Robins": 80,
    # Hawaii
    "Honolulu": 345, "Pearl City": 47, "Hilo": 45, "Kailua": 51,
    "Waipahu": 38,
    # Idaho
    "Boise": 235, "Meridian": 114, "Nampa": 100, "Idaho Falls": 64,
    "Pocatello": 55, "Caldwell": 58, "Coeur d'Alene": 51,
    # Illinois
    "Chicago": 2696, "Aurora": 197, "Joliet": 147, "Naperville": 148,
    "Rockford": 148, "Elgin": 113, "Springfield": 114,
    "Peoria": 112, "Champaign": 88, "Waukegan": 87,
    # Indiana
    "Indianapolis": 887, "Fort Wayne": 263, "Evansville": 117,
    "South Bend": 103, "Carmel": 99, "Fishers": 100,
    "Hammond": 78, "Gary": 70, "Bloomington": 84,
    # Iowa
    "Des Moines": 214, "Cedar Rapids": 133, "Davenport": 102,
    "Sioux City": 82, "Iowa City": 74, "Waterloo": 67,
    # Kansas
    "Wichita": 397, "Overland Park": 197, "Kansas City": 152,
    "Topeka": 126, "Olathe": 140, "Lawrence": 95,
    # Kentucky
    "Louisville": 633, "Lexington": 322, "Bowling Green": 72,
    "Owensboro": 60, "Covington": 41,
    # Louisiana
    "New Orleans": 383, "Baton Rouge": 228, "Shreveport": 188,
    "Metairie": 138, "Lafayette": 130,
    # Maine
    "Portland": 68, "Lewiston": 36, "Bangor": 32,
    "South Portland": 26, "Auburn": 23,
    # Maryland
    "Baltimore": 585, "Frederick": 72, "Rockville": 68,
    "Gaithersburg": 68, "Bowie": 58,
    # Massachusetts
    "Boston": 675, "Worcester": 185, "Springfield": 155,
    "Cambridge": 118, "Lowell": 115, "Brockton": 105,
    "New Bedford": 95, "Quincy": 94, "Lynn": 93,
    # Michigan
    "Detroit": 639, "Grand Rapids": 197, "Warren": 139,
    "Sterling Heights": 131, "Ann Arbor": 121, "Lansing": 112,
    "Flint": 81, "Dearborn": 87,
    # Minnesota
    "Minneapolis": 429, "St. Paul": 308, "Rochester": 121,
    "Duluth": 90, "Bloomington": 89, "Brooklyn Park": 86,
    "Plymouth": 80, "Maple Grove": 68,
    # Mississippi
    "Jackson": 153, "Gulfport": 72, "Southaven": 55,
    "Hattiesburg": 47, "Biloxi": 46,
    # Missouri
    "Kansas City": 508, "St. Louis": 293, "Springfield": 167,
    "Columbia": 122, "Independence": 119,
    # Montana
    "Billings": 117, "Missoula": 73, "Great Falls": 60,
    "Bozeman": 53, "Butte": 35,
    # Nebraska
    "Omaha": 486, "Lincoln": 291, "Bellevue": 64,
    "Grand Island": 52, "Kearney": 33,
    # Nevada
    "Las Vegas": 641, "Henderson": 320, "Reno": 264,
    "North Las Vegas": 241, "Sparks": 102,
    # New Hampshire
    "Manchester": 115, "Nashua": 90, "Concord": 44,
    "Derry": 33, "Dover": 31,
    # New Jersey
    "Newark": 311, "Jersey City": 292, "Paterson": 159,
    "Elizabeth": 135, "Lakewood": 135, "Edison": 100,
    "Woodbridge": 99, "Toms River": 91,
    # New Mexico
    "Albuquerque": 564, "Las Cruces": 111, "Rio Rancho": 100,
    "Santa Fe": 84, "Roswell": 48,
    # New York
    "New York City": 8336, "Buffalo": 276, "Rochester": 210,
    "Yonkers": 211, "Syracuse": 148, "Albany": 97, "New Rochelle": 79,
    # North Carolina
    "Charlotte": 874, "Raleigh": 467, "Greensboro": 296,
    "Durham": 278, "Winston-Salem": 249, "Fayetteville": 211,
    "Cary": 174, "Wilmington": 115, "High Point": 114,
    # North Dakota
    "Fargo": 125, "Bismarck": 73, "Grand Forks": 57,
    "Minot": 48, "West Fargo": 36,
    # Ohio
    "Columbus": 905, "Cleveland": 372, "Cincinnati": 309,
    "Toledo": 270, "Akron": 188, "Dayton": 137,
    "Parma": 79, "Canton": 69,
    # Oklahoma
    "Oklahoma City": 681, "Tulsa": 413, "Norman": 128,
    "Broken Arrow": 113, "Edmond": 92,
    # Oregon
    "Portland": 652, "Salem": 175, "Eugene": 176,
    "Gresham": 109, "Hillsboro": 100, "Bend": 99,
    # Pennsylvania
    "Philadelphia": 1603, "Pittsburgh": 302, "Allentown": 125,
    "Erie": 94, "Reading": 95, "Scranton": 76,
    "Bethlehem": 75, "Lancaster": 59,
    # Rhode Island
    "Providence": 190, "Cranston": 81, "Warwick": 83,
    "Pawtucket": 71, "East Providence": 47,
    # South Carolina
    "Columbia": 136, "Charleston": 150, "North Charleston": 114,
    "Mount Pleasant": 89, "Rock Hill": 75,
    # South Dakota
    "Sioux Falls": 192, "Rapid City": 74, "Aberdeen": 28,
    # Tennessee
    "Nashville": 689, "Memphis": 633, "Knoxville": 190,
    "Chattanooga": 181, "Clarksville": 156,
    # Texas
    "Houston": 2304, "San Antonio": 1434, "Dallas": 1288,
    "Austin": 961, "Fort Worth": 918, "El Paso": 678,
    "Arlington": 394, "Corpus Christi": 317, "Plano": 285,
    "Laredo": 261, "Lubbock": 258, "Garland": 236,
    "Irving": 239, "Amarillo": 200, "Grand Prairie": 193,
    "Brownsville": 186, "Pasadena": 152, "McKinney": 195,
    "Frisco": 200, "Mesquite": 140,
    # Utah
    "Salt Lake City": 200, "West Valley City": 140, "Provo": 115,
    "West Jordan": 114, "Orem": 98,
    # Vermont
    "Burlington": 45, "South Burlington": 20, "Rutland": 15,
    # Virginia
    "Virginia Beach": 457, "Norfolk": 242, "Chesapeake": 249,
    "Richmond": 226, "Newport News": 186, "Alexandria": 159,
    "Hampton": 137, "Roanoke": 100,
    # Washington
    "Seattle": 737, "Spokane": 222, "Tacoma": 213,
    "Vancouver": 183, "Bellevue": 148, "Kent": 130, "Everett": 112,
    # West Virginia
    "Charleston": 49, "Huntington": 46, "Morgantown": 30,
    "Parkersburg": 30, "Wheeling": 27,
    # Wisconsin
    "Milwaukee": 577, "Madison": 269, "Green Bay": 107,
    "Kenosha": 100, "Racine": 78,
    # Wyoming
    "Cheyenne": 64, "Casper": 57, "Laramie": 32,
    # ── Additional cities (all states) ─────────────────────────────────────
    # Alaska
    "Bethel": 6, "Palmer": 7,
    # Delaware
    "Milford": 11, "Seaford": 8, "Elsmere": 6, "New Castle": 6,
    # Florida extras (original list)
    "Coral Springs": 133, "Palm Bay": 119, "West Palm Beach": 117,
    "Clearwater": 115, "Lakeland": 112, "Pompano Beach": 108,
    # Florida extras (new cities added)
    "Boca Raton": 99, "Davie": 105, "Miami Gardens": 113,
    "Deerfield Beach": 80, "Deltona": 92, "Palm Coast": 90,
    "Plantation": 93, "Sunrise": 94, "Lauderhill": 74, "Homestead": 75,
    "Kissimmee": 72, "Sanford": 62, "Ocala": 63, "Daytona Beach": 69,
    "Melbourne": 84, "Sarasota": 57, "Bradenton": 58, "Fort Myers": 86,
    "Naples": 22, "Bonita Springs": 56, "Pensacola": 54,
    "Panama City": 37, "St. Cloud": 57, "Apopka": 54,
    # Georgia extras
    "Johns Creek": 82, "Alpharetta": 65, "Marietta": 60,
    "Valdosta": 57, "Smyrna": 54, "Alpharetta": 65,
    # Hawaii extras
    "Kaneohe": 35, "Mililani Town": 28, "Kahului": 27,
    "Ewa Gentry": 22, "Kihei": 22,
    # Idaho extras
    "Twin Falls": 51, "Lewiston": 33, "Post Falls": 35,
    # Illinois extras
    "Decatur": 70, "Bolingbrook": 73, "Bloomington": 78,
    # Indiana extras
    "Lafayette": 72, "Terre Haute": 59, "Kokomo": 58,
    "Anderson": 55, "Noblesville": 71, "Muncie": 67,
    # Iowa extras
    "Council Bluffs": 62, "Ames": 66, "West Des Moines": 66, "Dubuque": 59,
    # Kansas extras
    "Shawnee": 64, "Manhattan": 52, "Lenexa": 54, "Salina": 46,
    # Kentucky extras
    "Hopkinsville": 32, "Richmond": 33, "Florence": 33,
    "Georgetown": 36, "Henderson": 28,
    # Louisiana extras
    "Lake Charles": 78, "Kenner": 67, "Bossier City": 68,
    "Monroe": 48, "Alexandria": 48, "Houma": 33,
    # Maine extras
    "Biddeford": 22, "Sanford": 20, "Augusta": 19, "Saco": 20, "Westbrook": 19,
    # Maryland extras
    "Hagerstown": 43, "Annapolis": 41, "College Park": 32,
    "Salisbury": 33, "Laurel": 26,
    # Massachusetts extras
    "Newton": 88, "Somerville": 81, "Framingham": 73,
    "Haverhill": 67, "Fall River": 94,
    # Michigan extras
    "Livonia": 95, "Westland": 84, "Troy": 82, "Farmington Hills": 81,
    "Kalamazoo": 72, "Wyoming": 74, "Southfield": 73,
    # Minnesota extras — fix "Saint Paul" spelling used in city dropdown
    "Saint Paul": 308, "Saint Cloud": 67, "Eagan": 67, "Woodbury": 73,
    "Coon Rapids": 63, "Burnsville": 61, "Blaine": 65, "Lakeville": 67,
    # Mississippi extras
    "Meridian": 39, "Tupelo": 37, "Olive Branch": 40,
    "Horn Lake": 28, "Pearl": 26,
    # Missouri extras — fix "Saint Louis" spelling
    "Saint Louis": 293, "Lee's Summit": 102, "O'Fallon": 91,
    "Saint Joseph": 77, "Saint Charles": 74, "Blue Springs": 56,
    # Montana extras
    "Helena": 33, "Kalispell": 25, "Havre": 9, "Anaconda": 9, "Miles City": 8,
    # Nebraska extras
    "Fremont": 26, "Hastings": 24, "North Platte": 24, "Norfolk": 24,
    # Nevada extras
    "Carson City": 57, "Fernley": 22, "Elko": 21, "Mesquite": 21,
    "Boulder City": 16,
    # New Hampshire extras
    "Derry": 33, "Dover": 31, "Rochester": 32, "Salem": 30,
    "Merrimack": 26, "Hudson": 25, "Londonderry": 26,
    # New Jersey extras
    "Clifton": 85, "Camden": 73, "Brick": 74, "Cherry Hill": 71,
    "Passaic": 70, "Hamilton": 92, "Trenton": 90,
    # New Mexico extras
    "Farmington": 45, "Clovis": 39, "Hobbs": 38,
    "Alamogordo": 31, "Carlsbad": 30,
    # New York extras
    "Brooklyn": 2600, "Queens": 2300, "Bronx": 1420,
    "Staten Island": 480, "Manhattan": 1630,
    "Ithaca": 31, "Poughkeepsie": 32, "Newburgh": 28,
    "Middletown": 29, "Kingston": 24, "Saratoga Springs": 29,
    "Plattsburgh": 20, "Watertown": 26, "Rome": 32, "Oswego": 18,
    "Binghamton": 47, "Hempstead": 55, "Mount Vernon": 73,
    "Niagara Falls": 49, "Schenectady": 65, "Utica": 60, "White Plains": 58,
    # North Carolina extras
    "Concord": 105, "Asheville": 94, "Gastonia": 82,
    "Chapel Hill": 61, "Greenville": 92, "Rocky Mount": 55,
    # North Dakota extras
    "Williston": 28, "Dickinson": 24, "Mandan": 24,
    "Jamestown": 15, "Wahpeton": 8,
    # Ohio extras
    "Hamilton": 63, "Springfield": 58, "Kettering": 56,
    "Elyria": 54, "Lakewood": 51,
    # Oklahoma extras
    "Lawton": 92, "Moore": 60, "Midwest City": 58,
    "Enid": 50, "Stillwater": 48,
    # Oregon extras
    "Medford": 84, "Corvallis": 59,
    # Pennsylvania extras
    "Harrisburg": 50, "York": 44, "Altoona": 44,
    "Wilkes-Barre": 41, "Chester": 34, "Norristown": 34, "State College": 41,
    # Rhode Island extras
    "Coventry": 35, "Cumberland": 35, "North Providence": 32, "West Warwick": 29,
    # South Carolina extras
    "Greenville": 72, "Summerville": 50, "Sumter": 41,
    "Goose Creek": 43, "Hilton Head Island": 41,
    # South Dakota extras
    "Brookings": 24, "Watertown": 22, "Mitchell": 15,
    "Yankton": 15, "Pierre": 14, "Huron": 13, "Vermillion": 11,
    # Tennessee extras
    "Jackson": 68, "Johnson City": 68, "Bartlett": 58,
    "Hendersonville": 57, "Kingsport": 53, "Collierville": 51,
    "Smyrna": 49, "Cleveland": 45,
    # Texas extras
    "Carrollton": 135, "Killeen": 153, "Midland": 132, "Waco": 139,
    "Denton": 139, "Abilene": 125, "Beaumont": 113, "Round Rock": 133,
    "Sugar Land": 118, "League City": 106, "Richardson": 119,
    "Wichita Falls": 103, "Tyler": 105, "College Station": 120,
    "Allen": 105, "Pearland": 125, "Odessa": 117, "Lewisville": 106,
    "San Angelo": 99, "Edinburg": 101, "Flower Mound": 78,
    "Longview": 82, "McAllen": 143, "Cedar Park": 77, "Georgetown": 75,
    "Baytown": 78, "North Richland Hills": 70, "Mission": 84,
    "Harlingen": 65, "Rowlett": 66,
    # Utah extras
    "Sandy": 96, "Ogden": 87, "St. George": 90, "Layton": 78, "Millcreek": 62,
    # Vermont extras
    "Essex Junction": 24, "Barre": 8, "Montpelier": 8,
    "Winooski": 8, "St. Albans": 7, "Newport": 5, "Vergennes": 2,
    # Virginia extras
    "Lynchburg": 82, "Harrisonburg": 54, "Charlottesville": 46,
    "Danville": 42, "Manassas": 41, "Suffolk": 93, "Portsmouth": 95,
    # Washington extras
    "Kennewick": 82, "Federal Way": 96, "Yakima": 96,
    "Redmond": 68, "Marysville": 67,
    # West Virginia extras
    "Fairmont": 18, "Martinsburg": 20, "Beckley": 17,
    "Clarksburg": 16, "Weirton": 19,
    # Wisconsin extras
    "Appleton": 76, "Waukesha": 72, "Oshkosh": 66, "Eau Claire": 69,
    "Janesville": 65, "West Allis": 60, "La Crosse": 51,
    "Sheboygan": 50, "Wauwatosa": 47, "Fond du Lac": 43,
    # Wyoming extras
    "Rock Springs": 23, "Sheridan": 18, "Green River": 12,
    "Evanston": 12, "Riverton": 11, "Jackson": 10, "Gillette": 33,
    "Lander": 8, "Cody": 10, "Worland": 5, "Rawlins": 9, "Douglas": 7,
    # DC
    "Washington": 689,
    "Georgetown": 30, "Capitol Hill": 35, "Adams Morgan": 20,
    "Dupont Circle": 18, "Foggy Bottom": 15, "Navy Yard": 12,
    "Columbia Heights": 25, "Anacostia": 22, "Petworth": 20,
    # Alabama extras
    "Gadsden": 37, "Florence": 40, "Phenix City": 33, "Opelika": 30,
    "Bessemer": 26, "Homewood": 25, "Vestavia Hills": 37,
    "Trussville": 24, "Northport": 27, "Prattville": 40,
    # Arizona extras
    "Casa Grande": 56, "Sierra Vista": 44, "Prescott": 45,
    "Apache Junction": 42, "Maricopa": 52, "Queen Creek": 62,
    "Buckeye": 79, "El Mirage": 33, "Prescott Valley": 48, "Oro Valley": 47,
    # Arkansas extras
    "Texarkana": 37, "Russellville": 29, "Benton": 36,
    "Hot Springs": 37, "Sherwood": 31, "Bryant": 25,
    "Paragould": 28, "Cabot": 26, "Searcy": 23,
    # Connecticut extras
    "Meriden": 60, "Middletown": 47, "New London": 27,
    "Torrington": 35, "Shelton": 42, "Milford": 55,
    "Bristol": 60, "Naugatuck": 31, "Stratford": 52, "East Hartford": 51,
    # Georgia extras
    "Gainesville": 42, "Peachtree City": 35, "Dalton": 34,
    "Douglasville": 35, "Lawrenceville": 31, "Kennesaw": 34,
    "Woodstock": 33, "Rome": 37, "Dunwoody": 49, "Brookhaven": 54,
    # Illinois extras
    "Cicero": 84, "Orland Park": 57, "Arlington Heights": 76,
    "Schaumburg": 73, "Normal": 54, "Palatine": 69,
    "Oak Park": 52, "Berwyn": 54, "Downers Grove": 47,
    "Tinley Park": 55, "Skokie": 65,
    # Iowa extras
    "Cedar Falls": 40, "Mason City": 27, "Ottumwa": 24,
    "Burlington": 25, "Bettendorf": 39, "Clinton": 26,
    "Marshalltown": 27, "Fort Dodge": 25, "Ankeny": 67,
    # Kansas extras
    "Hutchinson": 41, "Garden City": 26, "Junction City": 23,
    "Emporia": 24, "Derby": 23, "Liberal": 21,
    "Dodge City": 28, "Leawood": 34, "Prairie Village": 22, "Merriam": 11,
    # Kentucky extras
    "Paducah": 27, "Elizabethtown": 31, "Frankfort": 27,
    "Murray": 18, "Ashland": 20, "Nicholasville": 32,
    "Madisonville": 19, "Danville": 17, "Erlanger": 19, "Independence": 27,
    # Louisiana extras
    "Slidell": 29, "Metairie": 138, "New Iberia": 30,
    "Thibodaux": 15, "Ruston": 22, "Opelousas": 16,
    "Hammond": 21, "Natchitoches": 18, "Mandeville": 13, "Covington": 12,
    # Maine extras
    "Brunswick": 22, "Rockland": 8, "Presque Isle": 9,
    "Bath": 8, "Waterville": 16,
    # Maryland extras
    "Silver Spring": 80, "Bethesda": 65, "Greenbelt": 24,
    "Towson": 58, "Columbia": 103, "Germantown": 90,
    "Waldorf": 79, "Ellicott City": 75, "Dundalk": 63, "Catonsville": 42,
    # Mississippi extras
    "Vicksburg": 23, "Starkville": 24, "Natchez": 15,
    "Corinth": 14, "Greenville": 31, "Clinton": 26,
    "Ridgeland": 24, "Brandon": 23, "Flowood": 9,
    # Missouri extras
    "Joplin": 52, "Sedalia": 22, "Cape Girardeau": 40,
    "Jefferson City": 43, "Florissant": 52, "Chesterfield": 47,
    "Wentzville": 39, "Ballwin": 30, "Kirkwood": 27, "Wildwood": 35,
    # Nebraska extras
    "Scottsbluff": 15, "Beatrice": 12, "Lexington": 10,
    "Papillion": 24, "La Vista": 17,
    # Nevada extras
    "Pahrump": 36, "Sun Valley": 20, "Enterprise": 108,
    "Winchester": 36, "Paradise": 193, "Spring Valley": 178,
    "Summerlin South": 26, "Whitney": 38, "Sunrise Manor": 189,
    "East Las Vegas": 41,
    # New Mexico extras
    "Gallup": 22, "Artesia": 12, "Deming": 14,
    "Silver City": 9, "Portales": 12, "Lovington": 12,
    "Ruidoso": 8, "Taos": 6, "Los Lunas": 17, "Española": 10,
    # Oklahoma extras
    "Muskogee": 37, "Shawnee": 30, "Ponca City": 25,
    "Bartlesville": 36, "Yukon": 25, "Bixby": 27,
    "Owasso": 36, "Sapulpa": 21, "Ardmore": 24, "Duncan": 23,
    # Oregon extras
    "Albany": 54, "Lake Oswego": 41, "Grants Pass": 39,
    "Klamath Falls": 21, "Tigard": 54, "Tualatin": 29,
    "West Linn": 27, "Ashland": 21, "Roseburg": 23,
    # Iowa extras 2
    "Iowa Falls": 5,
    # South Carolina extras
    "Myrtle Beach": 35, "Spartanburg": 38, "Anderson": 28,
    "Conway": 24, "Aiken": 31, "Greer": 29,
    "Greenwood": 23, "Bluffton": 26, "Beaufort": 13,
    # Utah extras
    "Lehi": 80, "Draper": 48, "Herriman": 44,
    "Taylorsville": 59, "Murray": 48, "South Jordan": 75,
    "Logan": 52, "Cedar City": 35, "Springville": 38, "Spanish Fork": 41,
    # West Virginia extras
    "Bluefield": 10, "St. Albans": 11, "Vienna": 11,
    "South Charleston": 13,
    # Ohio extras
    "Lorain": 63, "Youngstown": 60,
    # Oregon extras
    "Beaverton": 100,
    # Rhode Island extras
    "Woonsocket": 43,
    # Tennessee extras
    "Franklin": 83, "Murfreesboro": 152,
    # Washington extras
    "Bellingham": 92, "Kirkland": 92, "Renton": 106,
    # California — Bay Area & Peninsula
    "Palo Alto": 67, "Los Altos": 31, "Mountain View": 82, "Sunnyvale": 155,
    "Cupertino": 60, "Los Gatos": 32, "Saratoga": 31, "Campbell": 42,
    "Menlo Park": 33, "Redwood City": 85, "San Mateo": 104,
    "Burlingame": 31, "San Carlos": 29, "Belmont": 27, "East Palo Alto": 29,
    "Atherton": 7, "Foster City": 33, "Millbrae": 22, "San Bruno": 44,
    "South San Francisco": 66,
    # California — East & North Bay
    "Daly City": 107, "Hayward": 159, "Concord": 129, "Antioch": 116,
    "Richmond": 116, "Berkeley": 124, "Walnut Creek": 70, "Pleasanton": 82,
    "Livermore": 90, "San Ramon": 84, "Union City": 75, "Newark": 47,
    "Alameda": 78, "El Cerrito": 25, "Novato": 54, "San Rafael": 60,
    "Petaluma": 60, "Santa Rosa": 178, "Napa": 80, "Vallejo": 121,
    "Fairfield": 122, "Vacaville": 102,
    # California — Central Valley & Central Coast
    "Davis": 67, "Woodland": 60, "Chico": 103, "Redding": 93,
    "Roseville": 147, "Elk Grove": 176, "Folsom": 82, "Rocklin": 68,
    "Turlock": 72, "Merced": 84, "Visalia": 136, "Hanford": 56,
    "Santa Cruz": 65, "Capitola": 10, "Scotts Valley": 12,
    "Monterey": 30, "Salinas": 163, "San Luis Obispo": 46,
    "Paso Robles": 32, "Santa Maria": 107,
    # California — Southern California extras
    "Santa Barbara": 88, "Ventura": 112, "Thousand Oaks": 127,
    "Simi Valley": 124, "Glendale": 196, "Pasadena": 141,
    "Torrance": 144, "Santa Monica": 94, "Beverly Hills": 33,
    "Burbank": 103, "El Monte": 116, "Pomona": 151,
    "Rancho Cucamonga": 177, "Victorville": 134, "Garden Grove": 174,
    "Fullerton": 143, "Orange": 139, "Tustin": 81, "Mission Viejo": 95,
    "Lake Forest": 83, "El Cajon": 100, "Escondido": 152,
    "Oceanside": 175, "Carlsbad": 114, "Vista": 101,
    "San Marcos": 98, "Murrieta": 115, "Temecula": 113,
}

# Approximate state populations (thousands) — 2023 estimates
STATE_POPULATIONS = {
    "DC": 689,
    "AL": 5100, "AK": 740, "AZ": 7400, "AR": 3050, "CA": 39500,
    "CO": 5800, "CT": 3610, "DE": 1000, "FL": 22600, "GA": 10900,
    "HI": 1440, "ID": 1900, "IL": 12800, "IN": 6800, "IA": 3200,
    "KS": 2940, "KY": 4500, "LA": 4700, "ME": 1395, "MD": 6200,
    "MA": 7030, "MI": 10000, "MN": 5720, "MS": 2980, "MO": 6200,
    "MT": 1120, "NE": 1960, "NV": 3200, "NH": 1400, "NJ": 9290,
    "NM": 2120, "NY": 20200, "NC": 10600, "ND": 780, "OH": 11800,
    "OK": 4000, "OR": 4300, "PA": 13000, "RI": 1100, "SC": 5300,
    "SD": 900, "TN": 7100, "TX": 30000, "UT": 3400, "VT": 650,
    "VA": 8700, "WA": 7800, "WV": 1800, "WI": 5900, "WY": 580,
}

# Simple climate zone tag per state (for city context)
# City-specific climate zone overrides (where significantly different from state average)
CITY_CLIMATE_ZONES = {
    # California — Central Valley (hot-dry, not marine)
    "Stockton": "hot-dry", "Fresno": "hot-dry", "Bakersfield": "hot-dry",
    "Modesto": "hot-dry", "Turlock": "hot-dry", "Merced": "hot-dry",
    "Visalia": "hot-dry", "Hanford": "hot-dry", "Chico": "hot-dry",
    "Redding": "hot-dry", "Sacramento": "hot-dry", "Elk Grove": "hot-dry",
    "Roseville": "hot-dry", "Folsom": "hot-dry", "Rocklin": "hot-dry",
    "Davis": "hot-dry", "Woodland": "hot-dry", "Fairfield": "warm-dry",
    "Vacaville": "warm-dry",
    # California — Bay Area (marine)
    "San Francisco": "marine", "Oakland": "marine", "Berkeley": "marine",
    "Richmond": "marine", "Fremont": "marine", "San Jose": "marine",
    "Palo Alto": "marine", "Los Altos": "marine", "Mountain View": "marine",
    "Sunnyvale": "marine", "Cupertino": "marine", "Menlo Park": "marine",
    "Redwood City": "marine", "San Mateo": "marine", "Burlingame": "marine",
    "Daly City": "marine", "South San Francisco": "marine", "San Bruno": "marine",
    "Millbrae": "marine", "Foster City": "marine", "San Carlos": "marine",
    "Belmont": "marine", "East Palo Alto": "marine", "Atherton": "marine",
    "Hayward": "marine", "Union City": "marine", "Newark": "marine",
    "Alameda": "marine", "El Cerrito": "marine", "Petaluma": "marine",
    "San Rafael": "marine", "Novato": "marine", "Vallejo": "marine",
    "Napa": "warm-dry", "Santa Rosa": "warm-dry",
    "Concord": "warm-dry", "Walnut Creek": "warm-dry", "Pleasanton": "warm-dry",
    "Livermore": "warm-dry", "San Ramon": "warm-dry", "Antioch": "hot-dry",
    # California — Southern California coastal (Mediterranean)
    "Los Angeles": "Mediterranean", "Long Beach": "Mediterranean",
    "Santa Monica": "Mediterranean", "Torrance": "Mediterranean",
    "Chula Vista": "Mediterranean", "Oceanside": "Mediterranean",
    "Carlsbad": "Mediterranean", "San Diego": "Mediterranean",
    "Ventura": "Mediterranean", "Oxnard": "Mediterranean",
    "Thousand Oaks": "Mediterranean", "Santa Barbara": "Mediterranean",
    "Irvine": "Mediterranean", "Mission Viejo": "Mediterranean",
    "Lake Forest": "Mediterranean", "Beverly Hills": "Mediterranean",
    # California — Inland SoCal (hot-dry)
    "Riverside": "hot-dry", "San Bernardino": "hot-dry", "Fontana": "hot-dry",
    "Rancho Cucamonga": "hot-dry", "Victorville": "hot-dry",
    "Santa Ana": "hot-dry", "Anaheim": "hot-dry", "Orange": "hot-dry",
    "Fullerton": "hot-dry", "Garden Grove": "hot-dry", "El Cajon": "hot-dry",
    "Escondido": "hot-dry", "Vista": "hot-dry", "San Marcos": "hot-dry",
    "Murrieta": "hot-dry", "Temecula": "hot-dry", "Tustin": "hot-dry",
    "El Monte": "hot-dry", "Pomona": "hot-dry", "Pasadena": "hot-dry",
    "Burbank": "hot-dry", "Glendale": "Mediterranean", "Simi Valley": "hot-dry",
}

# City-specific retail electricity prices (cents/kWh) — significant variation within states
CITY_RETAIL_PRICES = {
    # California — major utility/rate differences within the state
    "Palo Alto": 19.8,          # CPAU (City of Palo Alto Utilities) — municipal
    "Sacramento": 15.5,         # SMUD — public municipal utility, lower than PG&E
    "Elk Grove": 15.5,          # SMUD territory
    "Folsom": 15.5,             # SMUD territory
    "Davis": 15.5,              # SMUD territory
    "Roseville": 15.2,          # Roseville Electric — municipal, lower rates
    "Rocklin": 15.2,            # Roseville Electric service area
    "Los Angeles": 18.5,        # LADWP — public utility, lower than PG&E
    "Long Beach": 18.5,         # Long Beach Power (municipal) + SCE blend
    "Glendale": 17.5,           # Glendale Water & Power — municipal
    "Burbank": 16.5,            # Burbank Water and Power — municipal
    "Pasadena": 16.8,           # Pasadena Water and Power — municipal
    "Anaheim": 17.0,            # Anaheim Public Utilities — municipal
    "Riverside": 15.8,          # Riverside Public Utilities — municipal
    "San Diego": 34.0,          # SDG&E — highest retail rates in California
    "Chula Vista": 34.0,        # SDG&E
    "El Cajon": 34.0,           # SDG&E
    "Escondido": 34.0,          # SDG&E
    "Oceanside": 34.0,          # SDG&E
    "Carlsbad": 34.0,           # SDG&E
    "Vista": 34.0,              # SDG&E
    "San Marcos": 34.0,         # SDG&E
    "Murrieta": 34.0,           # SDG&E
    "Temecula": 34.0,           # SDG&E
}

# City-specific utility provider overrides (fallback when OpenEI API is unavailable)
CITY_UTILITY_PROVIDERS = {
    # California — Bay Area
    "Palo Alto":          "City of Palo Alto Utilities (CPAU)",
    "Los Altos":          "Pacific Gas & Electric (PG&E)",
    "Mountain View":      "Pacific Gas & Electric (PG&E) / Silicon Valley Clean Energy",
    "Sunnyvale":          "Pacific Gas & Electric (PG&E) / Silicon Valley Clean Energy",
    "Cupertino":          "Pacific Gas & Electric (PG&E) / Silicon Valley Clean Energy",
    "San Jose":           "Pacific Gas & Electric (PG&E) / Silicon Valley Clean Energy",
    "Santa Clara":        "Silicon Valley Power (City of Santa Clara)",
    "Fremont":            "Pacific Gas & Electric (PG&E)",
    "San Francisco":      "Pacific Gas & Electric (PG&E) / CleanPowerSF",
    "Oakland":            "Pacific Gas & Electric (PG&E) / East Bay Community Energy",
    "Berkeley":           "Pacific Gas & Electric (PG&E) / East Bay Community Energy",
    "Hayward":            "Pacific Gas & Electric (PG&E) / East Bay Community Energy",
    "Richmond":           "Pacific Gas & Electric (PG&E)",
    "Concord":            "Pacific Gas & Electric (PG&E)",
    "Walnut Creek":       "Pacific Gas & Electric (PG&E)",
    "Pleasanton":         "Pacific Gas & Electric (PG&E)",
    "Livermore":          "Pacific Gas & Electric (PG&E)",
    "San Ramon":          "Pacific Gas & Electric (PG&E)",
    "Antioch":            "Pacific Gas & Electric (PG&E)",
    "Santa Rosa":         "Pacific Gas & Electric (PG&E)",
    "Napa":               "Pacific Gas & Electric (PG&E) / Napa Green Energy",
    "Vallejo":            "Pacific Gas & Electric (PG&E)",
    "Fairfield":          "Pacific Gas & Electric (PG&E)",
    "Vacaville":          "Pacific Gas & Electric (PG&E)",
    "Menlo Park":         "Pacific Gas & Electric (PG&E) / Peninsula Clean Energy",
    "Redwood City":       "Pacific Gas & Electric (PG&E) / Peninsula Clean Energy",
    "San Mateo":          "Pacific Gas & Electric (PG&E) / Peninsula Clean Energy",
    # California — Central Valley
    "Stockton":           "Pacific Gas & Electric (PG&E)",
    "Fresno":             "Pacific Gas & Electric (PG&E)",
    "Bakersfield":        "Pacific Gas & Electric (PG&E)",
    "Modesto":            "Pacific Gas & Electric (PG&E)",
    "Turlock":            "Turlock Irrigation District (TID)",
    "Merced":             "Pacific Gas & Electric (PG&E)",
    "Visalia":            "Pacific Gas & Electric (PG&E)",
    "Chico":              "Pacific Gas & Electric (PG&E)",
    "Redding":            "Pacific Gas & Electric (PG&E) / Redding Electric Utility",
    # California — Sacramento area
    "Sacramento":         "Sacramento Municipal Utility District (SMUD)",
    "Elk Grove":          "Sacramento Municipal Utility District (SMUD)",
    "Folsom":             "Sacramento Municipal Utility District (SMUD)",
    "Davis":              "Sacramento Municipal Utility District (SMUD)",
    "Roseville":          "Roseville Electric Utility (City of Roseville)",
    "Rocklin":            "Roseville Electric Utility / Pacific Gas & Electric (PG&E)",
    "Woodland":           "Pacific Gas & Electric (PG&E)",
    # California — Los Angeles area
    "Los Angeles":        "Los Angeles Dept. of Water & Power (LADWP)",
    "Long Beach":         "Southern California Edison (SCE) / Long Beach Power",
    "Glendale":           "Glendale Water & Power",
    "Burbank":            "Burbank Water and Power",
    "Pasadena":           "Pasadena Water and Power",
    "Beverly Hills":      "Southern California Edison (SCE)",
    "Santa Monica":       "Southern California Edison (SCE)",
    "Torrance":           "Southern California Edison (SCE)",
    "El Monte":           "Southern California Edison (SCE)",
    "Pomona":             "Southern California Edison (SCE)",
    # California — Inland SoCal
    "Anaheim":            "Anaheim Public Utilities",
    "Riverside":          "Riverside Public Utilities",
    "San Bernardino":     "Southern California Edison (SCE)",
    "Fontana":            "Southern California Edison (SCE)",
    "Rancho Cucamonga":   "Southern California Edison (SCE)",
    "Victorville":        "Southern California Edison (SCE)",
    "Irvine":             "Southern California Edison (SCE)",
    "Santa Ana":          "Southern California Edison (SCE)",
    "Orange":             "Southern California Edison (SCE)",
    "Fullerton":          "Southern California Edison (SCE)",
    "Garden Grove":       "Southern California Edison (SCE)",
    "Murrieta":           "Southern California Edison (SCE)",
    "Temecula":           "Southern California Edison (SCE)",
    "Mission Viejo":      "Southern California Edison (SCE)",
    "Lake Forest":        "Southern California Edison (SCE)",
    "Tustin":             "Southern California Edison (SCE)",
    "Oxnard":             "Southern California Edison (SCE)",
    "Ventura":            "Southern California Edison (SCE)",
    "Thousand Oaks":      "Southern California Edison (SCE)",
    "Simi Valley":        "Southern California Edison (SCE)",
    "Santa Barbara":      "Southern California Edison (SCE)",
    # California — San Diego (SDG&E)
    "San Diego":          "San Diego Gas & Electric (SDG&E)",
    "Chula Vista":        "San Diego Gas & Electric (SDG&E)",
    "Oceanside":          "San Diego Gas & Electric (SDG&E)",
    "Carlsbad":           "San Diego Gas & Electric (SDG&E)",
    "El Cajon":           "San Diego Gas & Electric (SDG&E)",
    "Escondido":          "San Diego Gas & Electric (SDG&E)",
    "Vista":              "San Diego Gas & Electric (SDG&E)",
    "San Marcos":         "San Diego Gas & Electric (SDG&E)",
}

STATE_CLIMATE = {
    "DC": "mixed-humid",
    "AK": "subarctic", "HI": "tropical",
    "FL": "hot-humid", "LA": "hot-humid", "MS": "hot-humid",
    "AL": "hot-humid", "GA": "hot-humid", "SC": "mixed-humid",
    "TX": "hot-mixed", "AZ": "hot-dry", "NM": "hot-dry",
    "NV": "hot-dry", "CA": "marine/semi-arid",
    "OR": "marine", "WA": "marine",
    "ID": "cold", "MT": "cold", "WY": "cold",
    "ND": "very-cold", "SD": "cold", "MN": "very-cold",
    "WI": "cold", "MI": "cold", "ME": "very-cold",
    "VT": "very-cold", "NH": "cold",
    "NY": "mixed-humid", "PA": "mixed-humid", "OH": "mixed-humid",
    "IN": "mixed-humid", "IL": "cold",
    "CO": "cold", "UT": "cold",
    "KS": "mixed-dry", "NE": "mixed-dry",
    "MO": "mixed-humid", "AR": "mixed-humid", "TN": "mixed-humid",
    "KY": "mixed-humid", "VA": "mixed-humid", "NC": "mixed-humid",
    "WV": "mixed-humid", "MD": "mixed-humid", "DE": "mixed-humid",
    "NJ": "mixed-humid", "CT": "mixed-humid", "RI": "mixed-humid",
    "MA": "cold", "IA": "cold", "OK": "mixed-dry",
}

# Average retail electricity price cents/kWh by state (approximate)
STATE_RETAIL_PRICE = {
    "DC": 13.8,
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
            "historical": self._build_historical_data(state_abbrev),
        }

        grid = self._fetch_eia_state_data(state_abbrev)
        result.update(grid)

        # Override state-level generation mix with city-specific profile when available
        city_profile = CITY_GENERATION_PROFILES.get(city)
        if city_profile:
            result["generation_mix"] = city_profile
            result["data_source"] = result.get("data_source", "simulated") + " (city-specific mix)"

        result["city_stats"] = self._get_city_stats(city, state_abbrev, result)
        return result

    def _get_city_stats(self, city: str, state_abbrev: str, grid_data: Dict) -> Dict:
        """
        Estimate city-level grid metrics by scaling state data proportionally
        to the city's share of the state population.
        """
        city_pop_k = CITY_POPULATIONS.get(city, 150)
        state_pop_k = STATE_POPULATIONS.get(state_abbrev, 5000)
        share = city_pop_k / max(state_pop_k, 1)
        share_pct = round(share * 100, 2)

        peak = grid_data.get("peak_demand_mw", 0)
        avg = grid_data.get("avg_demand_mw", 0)
        cap = grid_data.get("total_capacity_mw", 0)
        sales = grid_data.get("annual_sales_gwh") or 0
        price = grid_data.get("retail_price_cents_kwh")

        # Use city-specific retail price and climate zone when available
        city_price = CITY_RETAIL_PRICES.get(city)
        if city_price:
            price = city_price
        climate = CITY_CLIMATE_ZONES.get(city) or STATE_CLIMATE.get(state_abbrev, "mixed")

        return {
            "city_population_k": city_pop_k,
            "state_population_k": state_pop_k,
            "city_share_pct": share_pct,
            "estimated_capacity_mw": round(cap * share),
            "estimated_peak_demand_mw": round(peak * share),
            "estimated_avg_demand_mw": round(avg * share),
            "estimated_annual_sales_gwh": round(sales * share) if sales else None,
            "retail_price_cents_kwh": price,
            "climate_zone": climate,
            "note": (
                f"City estimates scaled from state EIA data "
                f"({city_pop_k:,}K / {state_pop_k:,}K state pop = {share_pct}% share)"
            ),
        }

    def _build_historical_data(self, state_abbrev: str) -> list:
        """
        Generate 3-year historical data (2021–2023) based on known EIA state profiles
        and national year-over-year trend factors. Available without an API key.
        """
        profile = STATE_GENERATION_PROFILES.get(state_abbrev, {
            "natural-gas": 40, "coal": 20, "nuclear": 15,
            "wind": 10, "solar": 8, "hydro": 5, "other": 2,
        })
        cap = STATE_CAPACITY.get(state_abbrev, {
            "capacity": 10000, "peak": 8000, "avg_load": 5200,
        })
        base_price = STATE_RETAIL_PRICE.get(state_abbrev, 12.0)

        historical = []
        for year in [2021, 2022, 2023]:
            f = HISTORICAL_TREND_FACTORS[year]

            # Scale each fuel type by its trend factor and renormalize to 100 %
            raw_mix = {fuel: pct * f.get(fuel, 1.0) for fuel, pct in profile.items()}
            total = sum(raw_mix.values())
            adj_mix = (
                {k: round(v / total * 100, 1) for k, v in raw_mix.items()}
                if total > 0 else dict(profile)
            )

            cm = f["capacity_mult"]
            adj_cap = round(cap["capacity"] * cm)
            adj_peak = round(cap["peak"] * cm)
            adj_avg = round(cap["avg_load"] * cm)
            adj_price = round(base_price * f["price_mult"], 2)
            adj_sales = round(adj_avg * 8760 / 1000)
            renew_pct = round(
                sum(v for k, v in adj_mix.items() if k in RENEWABLE_FUELS), 1
            )

            historical.append({
                "year": year,
                "generation_mix": adj_mix,
                "total_capacity_mw": adj_cap,
                "peak_demand_mw": adj_peak,
                "avg_demand_mw": adj_avg,
                "retail_price_cents_kwh": adj_price,
                "annual_sales_gwh": adj_sales,
                "renewable_pct": renew_pct,
            })

        return historical

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
        """Return well-known utility providers per state/city when API is unavailable."""
        # Check for a city-specific provider first
        city_provider = CITY_UTILITY_PROVIDERS.get(city)
        if city_provider:
            return {
                "name": city_provider,
                "id": "",
                "ownership": "Public" if any(w in city_provider for w in ("Municipal", "SMUD", "LADWP", "Utilities (City", "Dept.", "District", "Roseville Electric", "CPAU")) else "Investor-owned",
                "service_type": "Bundled",
                "all_providers": [city_provider],
            }
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

    # ── EIA HTTP helper ────────────────────────────────────────────────────
    @staticmethod
    def _eia_get(url: str) -> dict:
        """
        Fetch an EIA API v2 URL without percent-encoding bracket characters.

        Python's requests library re-encodes brackets in any URL it receives
        ([ → %5B, ] → %5D) via PreparedRequest.prepare_url(), even when the
        URL is already a pre-built string.  Python's urllib.request does NOT
        re-encode characters that are already in the URL string; it sends the
        query string byte-for-byte as written, so data[0]=generation reaches
        the EIA server unmodified.
        """
        req = _URequest(url, headers={"Accept": "application/json"})
        try:
            with _urlopen(req, timeout=12) as resp:
                return _json.loads(resp.read().decode("utf-8"))
        except _HTTPError as exc:
            if exc.code == 403:
                raise PermissionError(
                    "EIA API key invalid or missing (HTTP 403 Forbidden). "
                    "Get a free key at https://www.eia.gov/opendata/ and enter "
                    "it in the API Key field above."
                ) from exc
            if exc.code == 400:
                body = exc.read().decode("utf-8", errors="replace")
                raise ValueError(f"EIA API bad request (HTTP 400): {body[:200]}") from exc
            raise

    def _fetch_eia_state_data(self, state_abbrev: str) -> Dict:
        """
        Fetch state electricity data from EIA API v2.
        Raises PermissionError for bad keys (so the UI can show a clear message).
        Falls back to simulated data only on network/parse errors.
        """
        if not self.eia_api_key:
            return self._simulated_state_data(state_abbrev)
        try:
            return self._live_eia_data(state_abbrev)
        except PermissionError:
            raise   # propagate 403 as a clear error to the caller
        except Exception as e:
            logger.warning(f"EIA API call failed ({e}), falling back to simulated data")
            return self._simulated_state_data(state_abbrev)

    def _live_eia_data(self, state_abbrev: str) -> Dict:
        """Call EIA API v2 for generation and retail sales data via urllib."""
        k = self.eia_api_key

        # Annual electric-power operations by fuel type — last 5 years
        gen_url = (
            f"{EIA_BASE}/electricity/electric-power-operational-data/data/"
            f"?api_key={k}&frequency=annual&data[0]=generation"
            f"&facets[location][]={state_abbrev}"
            f"&sort[0][column]=period&sort[0][direction]=desc&length=60"
        )
        gen_body = self._eia_get(gen_url)
        gen_data = gen_body.get("response", {}).get("data", [])
        logger.info(f"EIA gen rows for {state_abbrev}: {len(gen_data)}")

        # Retail sales — price, consumption — last 5 years
        sales_url = (
            f"{EIA_BASE}/electricity/retail-sales/data/"
            f"?api_key={k}&frequency=annual"
            f"&data[0]=revenue&data[1]=sales&data[2]=price&data[3]=customers"
            f"&facets[stateid][]={state_abbrev}"
            f"&sort[0][column]=period&sort[0][direction]=desc&length=20"
        )
        sales_body = self._eia_get(sales_url)
        sales_data = sales_body.get("response", {}).get("data", [])
        logger.info(f"EIA sales rows for {state_abbrev}: {len(sales_data)}")

        return self._parse_eia_response(gen_data, sales_data, state_abbrev)

    def _parse_eia_response(self, gen_data, sales_data, state_abbrev: str) -> Dict:
        """Parse EIA API response into structured data, including 3-year live historical."""
        fuel_map = {
            "NG": "natural-gas", "COL": "coal", "NUC": "nuclear",
            "HYC": "hydro", "SUN": "solar", "WND": "wind",
            "GEO": "geothermal", "OTH": "other",
            "PEL": "other", "PC": "other", "OOG": "other",
            "WWW": "other", "WAS": "other", "HPS": "hydro",
        }

        # Group generation by year then fuel (summing across all sectors)
        by_year: Dict[str, Dict[str, float]] = {}
        for row in gen_data:
            year = str(row.get("period", ""))[:4]
            if not year.isdigit():
                continue
            fuel = fuel_map.get(row.get("fueltypeid", ""), "other")
            val = float(row.get("generation", 0) or 0)
            by_year.setdefault(year, {})
            by_year[year][fuel] = by_year[year].get(fuel, 0) + val

        # Build generation mix for most-recent year
        current_year = max(by_year.keys()) if by_year else "2023"
        current_gen = by_year.get(current_year, {})
        total_gen = sum(current_gen.values())
        generation_mix = (
            {k: round(v / total_gen * 100, 1) for k, v in current_gen.items()}
            if total_gen > 0 else STATE_GENERATION_PROFILES.get(state_abbrev, {})
        )

        # Build price lookup by year from sales data (prefer sectorid ALL or first match)
        price_by_year: Dict[str, float] = {}
        sales_by_year: Dict[str, float] = {}
        for row in sales_data:
            yr = str(row.get("period", ""))[:4]
            if not yr.isdigit() or yr in price_by_year:
                continue
            price_val = float(row.get("price", 0) or 0)
            sales_val = float(row.get("sales", 0) or 0)
            if price_val:
                price_by_year[yr] = price_val
            if sales_val:
                sales_by_year[yr] = sales_val / 1000  # million kWh → GWh

        retail_price = price_by_year.get(current_year) or STATE_RETAIL_PRICE.get(state_abbrev, 12.0)
        annual_sales_gwh = sales_by_year.get(current_year)

        cap = STATE_CAPACITY.get(state_abbrev, {"capacity": 10000, "peak": 8000, "avg_load": 5200})

        # Build live historical for 2021-2023
        historical = []
        for yr_str in ["2021", "2022", "2023"]:
            yr_gen = by_year.get(yr_str, {})
            yr_total = sum(yr_gen.values())
            if yr_total > 0:
                yr_mix = {k: round(v / yr_total * 100, 1) for k, v in yr_gen.items()}
                src = "EIA API (live)"
            else:
                # Fall back to trend-adjusted profile for missing years
                profile = STATE_GENERATION_PROFILES.get(state_abbrev, {})
                f = HISTORICAL_TREND_FACTORS.get(int(yr_str), HISTORICAL_TREND_FACTORS[2023])
                raw = {fuel: pct * f.get(fuel, 1.0) for fuel, pct in profile.items()}
                t = sum(raw.values())
                yr_mix = {k: round(v / t * 100, 1) for k, v in raw.items()} if t > 0 else profile
                src = "simulated"

            f = HISTORICAL_TREND_FACTORS.get(int(yr_str), HISTORICAL_TREND_FACTORS[2023])
            cm = f["capacity_mult"]
            yr_price = (
                price_by_year.get(yr_str)
                or round(STATE_RETAIL_PRICE.get(state_abbrev, 12.0) * f["price_mult"], 2)
            )
            renew_pct = round(sum(v for k, v in yr_mix.items() if k in RENEWABLE_FUELS), 1)

            historical.append({
                "year": int(yr_str),
                "generation_mix": yr_mix,
                "total_capacity_mw": round(cap["capacity"] * cm),
                "peak_demand_mw": round(cap["peak"] * cm),
                "avg_demand_mw": round(cap["avg_load"] * cm),
                "retail_price_cents_kwh": yr_price,
                "annual_sales_gwh": sales_by_year.get(yr_str) or round(cap["avg_load"] * cm * 8760 / 1000),
                "renewable_pct": renew_pct,
                "data_source": src,
            })

        return {
            "generation_mix": generation_mix,
            "total_capacity_mw": cap["capacity"],
            "peak_demand_mw": cap["peak"],
            "avg_demand_mw": cap["avg_load"],
            "retail_price_cents_kwh": retail_price,
            "annual_sales_gwh": annual_sales_gwh,
            "data_source": "EIA API (live)",
            "data_year": int(current_year),
            "historical": historical,
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
