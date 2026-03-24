"""
Power Grid Optimization Algorithm
----------------------------------
Implements Economic Dispatch optimization for a power grid.

Economic Dispatch: given a set of generators and a total load demand,
find the output level for each generator that minimizes total operating cost
while satisfying:
  1. Power balance: sum(P_i) == Load
  2. Generator limits: P_i_min <= P_i <= P_i_max

Cost function per generator: C_i(P_i) = a_i * P_i^2 + b_i * P_i + c_i

Secondary objectives analyzed:
  - CO2 / emissions minimization
  - Renewable penetration maximization
  - Reserve margin adequacy
  - Demand response potential
"""

import numpy as np
from scipy.optimize import minimize
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Generator:
    name: str
    fuel_type: str
    capacity_mw: float
    min_output_mw: float
    # Quadratic cost curve coefficients ($/MWh)
    cost_a: float   # quadratic term
    cost_b: float   # linear term
    cost_c: float   # no-load cost ($/h)
    emissions_lbs_co2_per_mwh: float
    is_renewable: bool
    is_dispatchable: bool


# Cost curve parameters per fuel type
# (cost_a, cost_b, cost_c, emissions_lbs_co2/MWh)
FUEL_CONFIGS = {
    "natural-gas": {
        "cost_a": 0.0045, "cost_b": 18.0, "cost_c": 180,
        "emissions": 820, "renewable": False, "dispatchable": True,
    },
    "coal": {
        "cost_a": 0.0020, "cost_b": 11.5, "cost_c": 350,
        "emissions": 2100, "renewable": False, "dispatchable": True,
    },
    "nuclear": {
        "cost_a": 0.0008, "cost_b": 7.0, "cost_c": 600,
        "emissions": 12, "renewable": False, "dispatchable": False,
    },
    "hydro": {
        "cost_a": 0.0005, "cost_b": 4.5, "cost_c": 80,
        "emissions": 4, "renewable": True, "dispatchable": True,
    },
    "wind": {
        "cost_a": 0.0, "cost_b": 0.0, "cost_c": 0,
        "emissions": 0, "renewable": True, "dispatchable": False,
    },
    "solar": {
        "cost_a": 0.0, "cost_b": 0.0, "cost_c": 0,
        "emissions": 0, "renewable": True, "dispatchable": False,
    },
    "geothermal": {
        "cost_a": 0.0005, "cost_b": 3.5, "cost_c": 50,
        "emissions": 38, "renewable": True, "dispatchable": True,
    },
    "other": {
        "cost_a": 0.0030, "cost_b": 14.0, "cost_c": 120,
        "emissions": 600, "renewable": False, "dispatchable": True,
    },
}


class PowerGridOptimizer:
    """
    Optimizes the dispatch of a power grid's generator fleet.
    """

    def build_generators(self, grid_data: Dict) -> List[Generator]:
        """Construct generator objects from scraped grid data."""
        generators = []
        mix = grid_data.get("generation_mix", {})
        total_cap = grid_data.get("total_capacity_mw", 10000)

        for fuel, pct in mix.items():
            if pct <= 0:
                continue
            cfg = FUEL_CONFIGS.get(fuel, FUEL_CONFIGS["other"])
            cap = total_cap * (pct / 100.0)
            # Non-dispatchable (wind/solar/nuclear) have fixed min = their full share
            min_out = 0.0 if cfg["renewable"] and not cfg["dispatchable"] else cap * 0.10

            generators.append(Generator(
                name=f"{fuel.replace('-', ' ').title()} Fleet",
                fuel_type=fuel,
                capacity_mw=round(cap, 1),
                min_output_mw=round(min_out, 1),
                cost_a=cfg["cost_a"],
                cost_b=cfg["cost_b"],
                cost_c=cfg["cost_c"],
                emissions_lbs_co2_per_mwh=cfg["emissions"],
                is_renewable=cfg["renewable"],
                is_dispatchable=cfg["dispatchable"],
            ))

        return generators

    def economic_dispatch(self, generators: List[Generator], load_mw: float) -> Dict:
        """
        Solve the Economic Dispatch problem using Sequential Least Squares (SLSQP).
        Returns dispatch schedule and cost metrics.
        """
        n = len(generators)
        if n == 0:
            return {"success": False, "error": "No generators defined"}

        # Non-dispatchable units run at fixed output (wind/solar at capacity, nuclear at min)
        fixed_dispatch = {}
        dispatchable_idx = []
        fixed_total = 0.0

        for i, gen in enumerate(generators):
            if not gen.is_dispatchable:
                fixed_out = gen.capacity_mw  # run at full available output
                fixed_dispatch[i] = fixed_out
                fixed_total += fixed_out
            else:
                dispatchable_idx.append(i)

        # If non-dispatchable output exceeds load, curtail proportionally (surplus renewable/nuclear)
        if fixed_total > load_mw:
            scale = load_mw / fixed_total
            fixed_dispatch = {k: v * scale for k, v in fixed_dispatch.items()}
            fixed_total = load_mw

        net_load = max(0.0, load_mw - fixed_total)
        disp_gens = [generators[i] for i in dispatchable_idx]
        nd = len(disp_gens)

        if nd == 0:
            # All generation is non-dispatchable
            dispatch = [fixed_dispatch.get(i, 0) for i in range(n)]
            cost = sum(
                generators[i].cost_a * dispatch[i] ** 2
                + generators[i].cost_b * dispatch[i]
                + generators[i].cost_c
                for i in range(n) if dispatch[i] > 0
            )
            return {
                "success": True, "dispatch": dispatch,
                "total_cost_per_hour": cost, "net_load_served": sum(dispatch),
            }

        # If net_load is less than sum of dispatchable minimums, reduce minimums proportionally
        min_total = sum(g.min_output_mw for g in disp_gens)
        if net_load < min_total:
            min_scale = net_load / min_total if min_total > 0 else 0
            disp_gens = [
                Generator(
                    name=g.name, fuel_type=g.fuel_type,
                    capacity_mw=g.capacity_mw,
                    min_output_mw=g.min_output_mw * min_scale,
                    cost_a=g.cost_a, cost_b=g.cost_b, cost_c=g.cost_c,
                    emissions_lbs_co2_per_mwh=g.emissions_lbs_co2_per_mwh,
                    is_renewable=g.is_renewable, is_dispatchable=g.is_dispatchable,
                )
                for g in disp_gens
            ]

        # ── Lambda Iteration (Equal Incremental Cost Rule) ────────────────
        # For C_i(P) = a_i*P^2 + b_i*P + c_i, the optimality condition is:
        #   dC_i/dP = 2*a_i*P_i + b_i = lambda  →  P_i = (lambda - b_i)/(2*a_i)
        # For units with a_i=0 (linear): run at max if b_i < lambda, else at min.
        # Find lambda via bisection so that sum(P_i) = net_load.

        def dispatch_at_lambda(lam):
            P = []
            for g in disp_gens:
                if g.cost_a > 1e-12:
                    p = (lam - g.cost_b) / (2.0 * g.cost_a)
                else:
                    # Linear/constant cost — compare marginal cost to lambda
                    p = g.capacity_mw if g.cost_b <= lam else g.min_output_mw
                P.append(float(np.clip(p, g.min_output_mw, g.capacity_mw)))
            return P

        # Bracket lambda: find [lo, hi] such that sum crosses net_load
        lo, hi = -1000.0, 5000.0
        for _ in range(100):
            lam_mid = (lo + hi) / 2.0
            total = sum(dispatch_at_lambda(lam_mid))
            if abs(total - net_load) < 0.1:
                break
            if total < net_load:
                lo = lam_mid
            else:
                hi = lam_mid

        x_mw = np.array(dispatch_at_lambda(lam_mid))
        converged = abs(sum(x_mw) - net_load) < max(net_load * 0.001, 1.0)

        # Reconstruct full dispatch vector
        full_dispatch = [0.0] * n
        for i, idx in enumerate(dispatchable_idx):
            full_dispatch[idx] = max(0.0, x_mw[i])
        for i, val in fixed_dispatch.items():
            full_dispatch[i] = val

        total_cost = sum(
            g.cost_a * x_mw[k] ** 2 + g.cost_b * x_mw[k] + g.cost_c
            for k, g in enumerate(disp_gens) if x_mw[k] > 0
        ) + sum(
            generators[i].cost_a * fixed_dispatch[i] ** 2
            + generators[i].cost_b * fixed_dispatch[i]
            for i in fixed_dispatch
        )

        return {
            "success": converged,
            "dispatch": full_dispatch,
            "total_cost_per_hour": round(total_cost, 2),
            "net_load_served": round(sum(full_dispatch), 1),
            "solver_message": "Lambda iteration converged" if converged else "Lambda iteration did not converge",
        }

    def optimize(self, grid_data: Dict) -> Dict:
        """
        Run full grid optimization analysis:
          1. Economic dispatch at peak load
          2. Economic dispatch at average load
          3. Emissions analysis
          4. Recommendations
        """
        generators = self.build_generators(grid_data)
        if not generators:
            return {"status": "error", "message": "No generator data available"}

        peak_load = grid_data.get("peak_demand_mw", 5000)
        avg_load = grid_data.get("avg_demand_mw", peak_load * 0.65)
        price_cents_kwh = grid_data.get("retail_price_cents_kwh", 12.0)

        peak_result = self.economic_dispatch(generators, peak_load)
        avg_result = self.economic_dispatch(generators, avg_load)

        peak_dispatch = peak_result["dispatch"]
        avg_dispatch = avg_result["dispatch"]

        # ── Emissions ──────────────────────────────────────────────────────
        peak_co2 = sum(
            peak_dispatch[i] * generators[i].emissions_lbs_co2_per_mwh
            for i in range(len(generators))
        )
        avg_co2 = sum(
            avg_dispatch[i] * generators[i].emissions_lbs_co2_per_mwh
            for i in range(len(generators))
        )
        annual_co2_tons = round(avg_co2 * 8760 / 2000, 0)

        # ── Renewable metrics ──────────────────────────────────────────────
        renewable_peak = sum(
            peak_dispatch[i] for i in range(len(generators))
            if generators[i].is_renewable
        )
        renewable_avg = sum(
            avg_dispatch[i] for i in range(len(generators))
            if generators[i].is_renewable
        )
        renewable_pct_peak = round(renewable_peak / max(peak_load, 1) * 100, 1)
        renewable_pct_avg = round(renewable_avg / max(avg_load, 1) * 100, 1)

        # ── Costs ──────────────────────────────────────────────────────────
        annual_cost = round(avg_result["total_cost_per_hour"] * 8760, 0)
        annual_revenue = round(avg_load * price_cents_kwh / 100 * 8760, 0)

        # ── Reserve margin ─────────────────────────────────────────────────
        total_cap = grid_data.get("total_capacity_mw", sum(g.capacity_mw for g in generators))
        reserve_margin_pct = round((total_cap - peak_load) / max(peak_load, 1) * 100, 1)

        # ── Per-generator dispatch table ───────────────────────────────────
        dispatch_table = []
        for i, gen in enumerate(generators):
            pd = round(peak_dispatch[i], 1)
            ad = round(avg_dispatch[i], 1)
            dispatch_table.append({
                "name": gen.name,
                "fuel_type": gen.fuel_type,
                "capacity_mw": gen.capacity_mw,
                "peak_dispatch_mw": pd,
                "avg_dispatch_mw": ad,
                "peak_utilization_pct": round(pd / max(gen.capacity_mw, 1) * 100, 1),
                "is_renewable": gen.is_renewable,
                "emissions_lbs_per_mwh": gen.emissions_lbs_co2_per_mwh,
            })

        recommendations = self._recommendations(
            generators, grid_data, peak_result, avg_result,
            reserve_margin_pct, renewable_pct_peak, annual_co2_tons,
        )

        return {
            "status": "success",
            "optimization_converged": peak_result["success"] and avg_result["success"],
            # Load
            "peak_demand_mw": round(peak_load, 1),
            "avg_demand_mw": round(avg_load, 1),
            "total_capacity_mw": round(total_cap, 0),
            "reserve_margin_pct": reserve_margin_pct,
            # Costs
            "peak_hourly_cost_usd": peak_result["total_cost_per_hour"],
            "avg_hourly_cost_usd": avg_result["total_cost_per_hour"],
            "annual_operating_cost_usd": annual_cost,
            "annual_revenue_estimate_usd": annual_revenue,
            "retail_price_cents_kwh": price_cents_kwh,
            # Emissions
            "peak_co2_lbs_per_hour": round(peak_co2, 0),
            "avg_co2_lbs_per_hour": round(avg_co2, 0),
            "annual_co2_tons": annual_co2_tons,
            "grid_carbon_intensity_lbs_per_mwh": round(avg_co2 / max(avg_load, 1), 1),
            # Renewables
            "renewable_pct_peak": renewable_pct_peak,
            "renewable_pct_avg": renewable_pct_avg,
            # Dispatch
            "dispatch_table": dispatch_table,
            "recommendations": recommendations,
            "generators": [
                {
                    "name": g.name,
                    "fuel_type": g.fuel_type,
                    "capacity_mw": g.capacity_mw,
                    "is_renewable": g.is_renewable,
                }
                for g in generators
            ],
        }

    def _recommendations(
        self, generators, grid_data, peak_result, avg_result,
        reserve_margin, renewable_pct, annual_co2_tons,
    ) -> List[Dict]:
        recs = []
        peak_load = grid_data.get("peak_demand_mw", 5000)
        avg_load = grid_data.get("avg_demand_mw", peak_load * 0.65)
        price = grid_data.get("retail_price_cents_kwh", 12.0)
        peak_dispatch = peak_result["dispatch"]

        # 1. Reserve margin
        if reserve_margin < 15:
            recs.append({
                "priority": "critical",
                "category": "Grid Reliability",
                "title": "Low Reserve Margin",
                "detail": (
                    f"Reserve margin is {reserve_margin}% (below the 15% NERC standard). "
                    "Add peaking capacity or expand demand response programs to reduce risk of outages."
                ),
            })
        elif reserve_margin > 40:
            recs.append({
                "priority": "low",
                "category": "Asset Utilization",
                "title": "High Reserve Margin",
                "detail": (
                    f"Reserve margin is {reserve_margin}%, significantly above standard. "
                    "Consider retiring aging or expensive generating units to reduce fixed costs."
                ),
            })

        # 2. Renewable energy
        if renewable_pct < 25:
            recs.append({
                "priority": "high",
                "category": "Clean Energy Transition",
                "title": "Low Renewable Penetration",
                "detail": (
                    f"Renewable sources supply only {renewable_pct}% of peak demand. "
                    "Expanding wind and solar capacity could reduce emissions and long-term fuel costs. "
                    f"A 10% renewable capacity addition (~{peak_load * 0.10:.0f} MW) is recommended."
                ),
            })
        elif renewable_pct >= 50:
            recs.append({
                "priority": "low",
                "category": "Clean Energy",
                "title": "Strong Renewable Penetration",
                "detail": (
                    f"Renewables provide {renewable_pct}% of peak demand — excellent progress. "
                    "Consider battery storage (4-hour duration) to firm up variable generation "
                    f"and shift surplus off-peak energy to peak periods."
                ),
            })

        # 3. Overloaded units
        for i, gen in enumerate(generators):
            util = peak_dispatch[i] / max(gen.capacity_mw, 1) * 100
            if util > 95 and gen.is_dispatchable:
                recs.append({
                    "priority": "high",
                    "category": "Capacity",
                    "title": f"{gen.name} Near Capacity Limit",
                    "detail": (
                        f"{gen.name} is operating at {util:.0f}% during peak demand. "
                        "Prolonged operation above 90% accelerates wear and reduces reliability. "
                        f"Add {gen.capacity_mw * 0.15:.0f} MW of peaking capacity or demand response."
                    ),
                })

        # 4. Coal retirement
        coal_gens = [g for g in generators if g.fuel_type == "coal"]
        if coal_gens:
            coal_cap = sum(g.capacity_mw for g in coal_gens)
            annual_savings = coal_cap * 0.5 * 8760 * 0.02  # rough estimate
            recs.append({
                "priority": "medium",
                "category": "Emissions Reduction",
                "title": "Coal Fleet Transition Opportunity",
                "detail": (
                    f"{coal_cap:.0f} MW of coal capacity contributes {annual_co2_tons:,.0f} tons CO2/year. "
                    f"Replacing coal with combined-cycle natural gas could cut emissions ~60% and "
                    f"save an estimated ${annual_savings:,.0f}/year in operating costs."
                ),
            })

        # 5. Demand response
        dr_savings = avg_result["total_cost_per_hour"] * 0.05 * 8760
        recs.append({
            "priority": "medium",
            "category": "Demand Response",
            "title": "Demand Response Expansion",
            "detail": (
                f"A 5% peak demand reduction program (~{peak_load * 0.05:.0f} MW) could "
                f"avoid dispatching expensive peaking units and save "
                f"approximately ${dr_savings:,.0f}/year in system operating costs."
            ),
        })

        # 6. Energy storage
        if renewable_pct > 20:
            storage_mw = peak_load * 0.08
            recs.append({
                "priority": "medium",
                "category": "Energy Storage",
                "title": "Battery Storage Integration",
                "detail": (
                    f"With {renewable_pct}% renewable penetration, grid-scale battery storage "
                    f"({storage_mw:.0f} MW / {storage_mw * 4:.0f} MWh) would improve reliability, "
                    "reduce curtailment, and shift cheap off-peak energy to peak hours."
                ),
            })

        # 7. Rate optimization
        if price > 18:
            recs.append({
                "priority": "medium",
                "category": "Rate Design",
                "title": "High Retail Electricity Price",
                "detail": (
                    f"Retail price of {price}¢/kWh is above the national average (~12¢/kWh). "
                    "Time-of-use (TOU) rates and real-time pricing could shift load to off-peak "
                    "hours and reduce average customer bills by 8–15%."
                ),
            })

        return recs

    def run_goal_simulations(
        self, grid_data: Dict, savings_goal: float = 100.0, max_sims: int = 100
    ) -> Dict:
        """
        Monte Carlo simulation: vary demand-response % and renewable boost %
        to find configurations that achieve >= savings_goal in annual savings.
        Stops early once any scenario crosses the goal; always runs max_sims.
        Returns all simulation results plus the best scenario found.
        """
        import random

        # ── Baseline ──────────────────────────────────────────────────────────
        base_opt = self.optimize(grid_data)
        if base_opt["status"] != "success":
            return {"status": "error", "message": "Baseline optimization failed"}

        baseline_cost = base_opt["annual_operating_cost_usd"]

        simulations: list = []
        best_savings = 0.0
        best_scenario = None
        sims_to_reach_goal = None

        rng = random.Random(42)  # reproducible seed

        for i in range(max_sims):
            dr_pct = rng.uniform(0, 25)          # demand-response 0–25 %
            renew_boost = rng.uniform(0, 30)     # renewable capacity addition 0–30 %
            fuel_mult = rng.uniform(0.80, 1.20)  # fuel-price variability ±20 %

            # ── Apply demand response ─────────────────────────────────────────
            dr_factor = 1.0 - dr_pct / 100.0
            peak_base = grid_data.get("peak_demand_mw", 5000)
            avg_base = grid_data.get("avg_demand_mw", peak_base * 0.65)
            modified = dict(grid_data)
            modified["peak_demand_mw"] = peak_base * dr_factor
            modified["avg_demand_mw"] = avg_base * dr_factor

            # ── Apply renewable boost (shift fossil → solar) ──────────────────
            mix = dict(grid_data.get("generation_mix", {}))
            renewable_fuels = {"wind", "solar", "hydro", "geothermal"}
            fossil_fuels = ["natural-gas", "coal", "other"]
            fossil_total = sum(mix.get(f, 0) for f in fossil_fuels)
            if renew_boost > 0 and fossil_total > 0:
                transfer = min(renew_boost, fossil_total * 0.6)
                mix["solar"] = mix.get("solar", 0) + transfer
                scale = (fossil_total - transfer) / fossil_total
                for f in fossil_fuels:
                    mix[f] = mix.get(f, 0) * scale
                total = sum(v for v in mix.values() if v > 0)
                if total > 0:
                    mix = {k: round(v * 100 / total, 1) for k, v in mix.items() if v > 0}
            modified["generation_mix"] = mix

            # ── Run optimizer ─────────────────────────────────────────────────
            try:
                opt = self.optimize(modified)
                if opt["status"] != "success":
                    continue
                sim_cost = opt["annual_operating_cost_usd"] * fuel_mult
                annual_savings = baseline_cost - sim_cost
            except Exception:
                continue

            if annual_savings > best_savings:
                best_savings = annual_savings
                best_scenario = {
                    "demand_response_pct": round(dr_pct, 1),
                    "renewable_boost_pct": round(renew_boost, 1),
                    "fuel_cost_mult": round(fuel_mult, 3),
                    "annual_cost_usd": round(sim_cost, 0),
                    "annual_savings_usd": round(annual_savings, 0),
                    "renewable_pct_avg": opt["renewable_pct_avg"],
                    "annual_co2_tons": opt["annual_co2_tons"],
                    "reserve_margin_pct": opt["reserve_margin_pct"],
                }

            if sims_to_reach_goal is None and annual_savings >= savings_goal:
                sims_to_reach_goal = i + 1

            simulations.append({
                "sim_id": i + 1,
                "demand_response_pct": round(dr_pct, 1),
                "renewable_boost_pct": round(renew_boost, 1),
                "fuel_cost_mult": round(fuel_mult, 3),
                "annual_savings_usd": round(annual_savings, 2),
                "annual_cost_usd": round(sim_cost, 0),
                "reached_goal": annual_savings >= savings_goal,
            })

        return {
            "status": "success",
            "baseline_annual_cost_usd": round(baseline_cost, 0),
            "savings_goal_usd": savings_goal,
            "max_sims": max_sims,
            "simulations_run": len(simulations),
            "goal_reached": sims_to_reach_goal is not None,
            "sims_to_reach_goal": sims_to_reach_goal,
            "best_savings_usd": round(best_savings, 0),
            "best_scenario": best_scenario,
            "simulations": simulations,
        }
