"""
Capisight core logic. No Streamlit imports here, so everything in this file
can be unit-tested (see tests/test_core.py).

Sections
  1. Constants and project table helpers
  2. Finance: cash-flow model, consistency check, stress tests
  3. Scoring and budget allocation (optimal 0/1 knapsack vs greedy)
  4. Site-deal economics (tower/pole colocation) and pole-to-macro break-even
  5. Document reading
  6. AI extraction with evidence verification, and an accuracy benchmark

Modeling assumptions are stated in the docstrings. The most important one:
the cash-flow model is UNIFORM year-end cash flows over the useful life,
with annual cash flow = cost / simple payback. Real projects are rarely this
tidy, so treat outputs as a screening aid, not a valuation.
"""
from __future__ import annotations

import io
import itertools  # noqa: F401  (used by tests via core.itertools if needed)
import json
import math
import re
from typing import Callable, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 1. Constants and project table helpers
# ---------------------------------------------------------------------------
AIMS = ["Regulatory / safety", "Business-as-usual", "New growth", "Improve performance"]
MANDATORY_AIM = "Regulatory / safety"

CRITERIA = [
    {"key": "npv", "label": "NPV (USD)", "direction": "higher"},
    {"key": "roi", "label": "ROI (%)", "direction": "higher"},
    {"key": "payback", "label": "Payback period (years)", "direction": "lower"},
    {"key": "strategic", "label": "Strategic score (1-10)", "direction": "higher"},
    {"key": "operational", "label": "Operational impact (1-10)", "direction": "higher"},
    {"key": "throughput", "label": "Throughput improvement (%)", "direction": "higher"},
    {"key": "risk", "label": "Risk score (1-10)", "direction": "lower"},
    {"key": "cost", "label": "Estimated cost (USD)", "direction": "lower"},
]
CRIT_KEYS = [c["key"] for c in CRITERIA]
LABEL = {c["key"]: c["label"] for c in CRITERIA}

# Starting hypotheses, NOT sourced prescriptions. Users are expected to edit them.
DEFAULT_AIM_WEIGHTS = {
    "Regulatory / safety": {"npv": 5, "roi": 5, "payback": 5, "strategic": 20, "operational": 10, "throughput": 5, "risk": 35, "cost": 15},
    "Business-as-usual": {"npv": 10, "roi": 10, "payback": 15, "strategic": 5, "operational": 15, "throughput": 10, "risk": 20, "cost": 15},
    "New growth": {"npv": 25, "roi": 20, "payback": 5, "strategic": 20, "operational": 10, "throughput": 10, "risk": 5, "cost": 5},
    "Improve performance": {"npv": 10, "roi": 10, "payback": 10, "strategic": 10, "operational": 20, "throughput": 20, "risk": 10, "cost": 10},
}

PROJECT_COLUMNS = [
    "Project", "Aim", "cost", "npv", "roi", "payback", "discount_rate_pct", "useful_life_yrs",
    "strategic", "operational", "throughput", "risk", "assumptions", "source", "scores_reviewed",
]
NUMERIC_COLS = ["cost", "npv", "roi", "payback", "discount_rate_pct", "useful_life_yrs",
                "strategic", "operational", "throughput", "risk"]


def parse_number(x) -> Optional[float]:
    """Best-effort float conversion. Returns None for blanks/NaN/garbage."""
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = x.replace(",", "").replace("$", "").replace("%", "").strip()
            if x == "":
                return None
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def normalize_projects(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee every expected column exists with a sensible dtype.

    Missing numeric values stay NaN (they are NOT silently turned into 0: a
    payback of 0 would look like the best possible project).
    """
    out = df.copy()
    for col in PROJECT_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan if col in NUMERIC_COLS else ("" if col != "scores_reviewed" else False)
    for col in NUMERIC_COLS:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")  # float so blanks (NaN) are allowed
    for col in ("Project", "Aim", "assumptions", "source"):
        out[col] = out[col].fillna("").astype(str)
    out["scores_reviewed"] = out["scores_reviewed"].fillna(False).astype(bool)
    return out[PROJECT_COLUMNS].reset_index(drop=True)


def load_demo_projects(path: str) -> pd.DataFrame:
    return normalize_projects(pd.read_csv(path))


# ---------------------------------------------------------------------------
# 2. Finance
# ---------------------------------------------------------------------------
def annuity_pv(cf: float, rate: float, n) -> float:
    """PV of n equal year-end cash flows. rate as a fraction (0.10 = 10%)."""
    n = int(round(n))
    if n <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return cf * n
    return cf * (1 - (1 + rate) ** (-n)) / rate


def npv_of_flows(rate: float, flows) -> float:
    """flows[0] occurs at t=0, flows[t] at end of year t."""
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))


def irr(flows, lo: float = -0.99, hi: float = 10.0, tol: float = 1e-9, max_iter: int = 300) -> Optional[float]:
    """IRR by bisection. Returns None if NPV does not change sign on [lo, hi]."""
    f_lo, f_hi = npv_of_flows(lo, flows), npv_of_flows(hi, flows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = npv_of_flows(mid, flows)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def discounted_payback(cost: float, cf: float, rate: float, life) -> Optional[float]:
    """Years until cumulative discounted inflows cover cost, or None if never within life."""
    cum = 0.0
    for t in range(1, int(round(life)) + 1):
        pv = cf / (1 + rate) ** t
        if cum + pv >= cost:
            return (t - 1) + (cost - cum) / pv
        cum += pv
    return None


def _metrics(cost: float, cf: float, rate: float, life) -> dict:
    n = int(round(life))
    flows = [-cost] + [cf] * n
    r = irr(flows)
    return {
        "npv": annuity_pv(cf, rate, n) - cost,
        "irr_pct": None if r is None else r * 100,
        "simple_payback": cost / cf if cf > 0 else float("inf"),
        "discounted_payback": discounted_payback(cost, cf, rate, n) if cf > 0 else None,
    }


CONSISTENT_PCT = 0.10   # gap up to 10% of capital cost: Consistent
REVIEW_PCT = 0.25       # gap up to 25%: Review; beyond (or sign flip): Inconsistent


def consistency_check(cost, stated_npv, payback, rate_pct, life_yrs) -> dict:
    """Compare a business case's STATED NPV with the NPV implied by its own payback,
    discount rate and useful life (uniform year-end cash flows, CF = cost / payback).

    Business cases quote NPV, payback and ROI separately, and they often disagree.
    Hiding that disagreement (for example by anchoring a sensitivity analysis to the
    stated NPV) lets bad numbers flow into rankings, so we surface it instead.

    gap = stated - implied (positive means the stated NPV is more optimistic).
    """
    c, s, p, r, life = (parse_number(v) for v in (cost, stated_npv, payback, rate_pct, life_yrs))
    if None in (c, s, p, r, life) or c <= 0 or p <= 0 or life <= 0 or r < 0:
        return {"status": "Not checkable", "implied_npv": None, "gap": None, "gap_pct_of_cost": None,
                "note": "Needs cost, stated NPV, payback, discount rate and useful life."}
    implied = annuity_pv(c / p, r / 100, life) - c
    gap = s - implied
    pct = abs(gap) / c
    tiny = 0.01 * c
    sign_flip = (implied > tiny and s < -tiny) or (implied < -tiny and s > tiny)
    if sign_flip or pct > REVIEW_PCT:
        status = "Inconsistent"
    elif pct > CONSISTENT_PCT:
        status = "Review"
    else:
        status = "Consistent"
    note = ""
    if p > life:
        note = "Payback is longer than the useful life, so the project never pays back."
    return {"status": status, "implied_npv": implied, "gap": gap, "gap_pct_of_cost": pct * 100, "note": note}


def add_consistency_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    res = [consistency_check(r.cost, r.npv, r.payback, r.discount_rate_pct, r.useful_life_yrs)
           for r in out.itertuples()]
    out["implied_npv"] = [x["implied_npv"] for x in res]
    out["npv_gap"] = [x["gap"] for x in res]
    out["check"] = [x["status"] for x in res]
    return out


def scenario_table(cost, payback, rate_pct, life, overrun_pct: float = 20.0, savings_cut_pct: float = 30.0) -> pd.DataFrame:
    """Stress scenarios on the uniform cash-flow model (NOT anchored to the stated NPV)."""
    cf0 = cost / payback
    r0 = rate_pct / 100
    over, cut = overrun_pct / 100, savings_cut_pct / 100
    scenarios = [
        ("Base case (model)", 1.0, 1.0, 0.0),
        ("Discount rate +2 pp", 1.0, 1.0, 0.02),
        ("Discount rate +5 pp", 1.0, 1.0, 0.05),
        (f"Savings down {savings_cut_pct:.0f}%", 1.0, 1 - cut, 0.0),
        (f"Cost overrun +{overrun_pct:.0f}%", 1 + over, 1.0, 0.0),
        ("Combined downside", 1 + over, 1 - cut, 0.02),
    ]
    rows = []
    for name, cm, fm, dr in scenarios:
        c, cf, r = cost * cm, cf0 * fm, r0 + dr
        m = _metrics(c, cf, r, life)
        rows.append({
            "Scenario": name, "Rate %": r * 100, "Capital cost": c, "Annual cash flow": cf,
            "NPV": m["npv"], "IRR %": m["irr_pct"], "Simple payback (yrs)": m["simple_payback"],
            "Discounted payback (yrs)": m["discounted_payback"], "NPV > 0": m["npv"] > 0,
        })
    return pd.DataFrame(rows)


def tornado_table(cost, payback, rate_pct, life, swing_pct: float = 20.0, rate_pp: float = 2.0, life_yrs: int = 1) -> pd.DataFrame:
    """One-at-a-time NPV swings, sorted by size, for a tornado chart."""
    cf0, r0, n0 = cost / payback, rate_pct / 100, int(round(life))
    base = annuity_pv(cf0, r0, n0) - cost
    s = swing_pct / 100

    def npv(c=cost, cf=cf0, r=r0, n=n0):
        return annuity_pv(cf, r, max(n, 1)) - c

    rows = [
        ("Discount rate", f"-{rate_pp:g} pp", f"+{rate_pp:g} pp", npv(r=r0 - rate_pp / 100), npv(r=r0 + rate_pp / 100)),
        ("Annual savings", f"-{swing_pct:g}%", f"+{swing_pct:g}%", npv(cf=cf0 * (1 - s)), npv(cf=cf0 * (1 + s))),
        ("Capital cost", f"+{swing_pct:g}%", f"-{swing_pct:g}%", npv(c=cost * (1 + s)), npv(c=cost * (1 - s))),
        ("Useful life", f"-{life_yrs} yr", f"+{life_yrs} yr", npv(n=n0 - life_yrs), npv(n=n0 + life_yrs)),
    ]
    df = pd.DataFrame(rows, columns=["Variable", "Low case", "High case", "NPV (low case)", "NPV (high case)"])
    df["Base NPV"] = base
    df["Swing"] = (df["NPV (high case)"] - df["NPV (low case)"]).abs()
    return df.sort_values("Swing", ascending=False).reset_index(drop=True)


def breakeven_savings_cut(cost, payback, rate_pct, life) -> float:
    """Percent drop in annual savings at which NPV hits zero (negative means NPV is already below zero)."""
    cf = cost / payback
    af = annuity_pv(1.0, rate_pct / 100, life)
    return (1 - cost / (cf * af)) * 100


# ---------------------------------------------------------------------------
# 3. Scoring and budget allocation
# ---------------------------------------------------------------------------
def normalize_column(series: pd.Series, direction: str) -> pd.Series:
    """Min-max within the group. If there is no spread, return 0.5 (no basis to compare),
    so a one-project aim does not automatically get a perfect score."""
    lo, hi = series.min(), series.max()
    if pd.isna(lo) or hi == lo:
        return pd.Series(0.5, index=series.index)
    if direction == "higher":
        return (series - lo) / (hi - lo)
    return (hi - series) / (hi - lo)


def split_complete(df: pd.DataFrame):
    """Rows with a valid aim and every scoring criterion present are rankable; the rest are
    returned separately instead of being scored as if the missing value were 0."""
    ok = df["Aim"].isin(AIMS) & df[CRIT_KEYS].notna().all(axis=1)
    return df[ok].copy(), df[~ok].copy()


def score_aim(bucket: pd.DataFrame, weights: dict):
    total = float(sum(weights.get(k, 0) for k in CRIT_KEYS))
    eff = {k: (weights.get(k, 0) / total if total > 0 else 0.0) for k in CRIT_KEYS}
    out = bucket.copy().reset_index(drop=True)
    score = pd.Series(0.0, index=out.index)
    for c in CRITERIA:
        score = score + normalize_column(out[c["key"]].astype(float), c["direction"]) * eff[c["key"]]
    out["Score"] = score
    out = out.sort_values("Score", ascending=False, kind="stable").reset_index(drop=True)
    out.insert(0, "Rank", range(1, len(out) + 1))
    return out, eff


def score_breakdown(scored: pd.DataFrame, project: str, eff: dict) -> pd.DataFrame:
    row_idx = scored.index[scored["Project"] == project][0]
    parts = []
    for c in CRITERIA:
        nv = float(normalize_column(scored[c["key"]].astype(float), c["direction"])[row_idx])
        parts.append({"Criterion": c["label"], "Raw value": scored.loc[row_idx, c["key"]],
                      "Normalized (0-1)": nv, "Weight": eff[c["key"]], "Contribution": nv * eff[c["key"]]})
    return pd.DataFrame(parts).sort_values("Contribution")


def greedy_select(costs, values, budget):
    """Take items in the given order if they fit. Returns (indices, total value)."""
    chosen, spent, total = [], 0.0, 0.0
    for i, (c, v) in enumerate(zip(costs, values)):
        if spent + c <= budget + 1e-9:
            chosen.append(i)
            spent += c
            total += v
    return chosen, total


def knapsack_select(costs, values, budget, unit: float = 1000.0):
    """Exact 0/1 knapsack by dynamic programming on cost units of `unit` dollars.
    Costs are rounded UP to whole units, so every selection is truly within budget
    (it may very slightly under-use the budget). Returns (indices, total value)."""
    w = [int(math.ceil(c / unit - 1e-9)) for c in costs]
    cap = int(budget // unit)
    n = len(w)
    if n == 0 or cap <= 0:
        return [], 0.0
    dp = np.zeros((n + 1, cap + 1))
    for i in range(1, n + 1):
        wi, vi = w[i - 1], float(values[i - 1])
        dp[i] = dp[i - 1]
        if wi <= cap:
            dp[i, wi:] = np.maximum(dp[i - 1, wi:], dp[i - 1, : cap + 1 - wi] + vi)
    chosen, b = [], cap
    for i in range(n, 0, -1):
        if dp[i, b] != dp[i - 1, b]:
            chosen.append(i - 1)
            b -= w[i - 1]
    return sorted(chosen), float(dp[n, cap])


def allocate_budget(scored_by_aim: dict, total_budget: float, shares: dict,
                    regulatory_mandatory: bool = True, method: str = "optimal", unit: float = 1000.0):
    """Split a budget across aims and pick projects within each aim.

    - If regulatory_mandatory, regulatory/safety projects are funded first (they are usually
      non-discretionary); the rest of the budget is split across the other aims by `shares`.
    - Within an aim we compare greedy-by-rank with the exact knapsack optimum on total score.
      Money never moves between aims automatically.
    """
    out, remaining = {}, float(total_budget)
    if regulatory_mandatory and MANDATORY_AIM in scored_by_aim:
        reg = scored_by_aim[MANDATORY_AIM]
        spend = float(reg["cost"].sum())
        names = list(reg["Project"])
        out[MANDATORY_AIM] = {"mode": "mandatory", "budget": spend, "funded": names, "unfunded": [], "spent": spend,
                              "unused": 0.0, "selected_score": float(reg["Score"].sum()),
                              "greedy_score": float(reg["Score"].sum()), "optimal_score": float(reg["Score"].sum()),
                              "greedy_funded": names, "optimal_funded": names}
        remaining -= spend
    shortfall = max(0.0, -remaining)
    remaining = max(0.0, remaining)
    flexible = [a for a in scored_by_aim if not (regulatory_mandatory and a == MANDATORY_AIM)]
    share_total = sum(shares.get(a, 0) for a in flexible)
    for a in flexible:
        df = scored_by_aim[a].reset_index(drop=True)
        bud = remaining * shares.get(a, 0) / share_total if share_total > 0 else 0.0
        costs, vals = df["cost"].tolist(), df["Score"].tolist()
        g_idx, g_score = greedy_select(costs, vals, bud)
        o_idx, o_score = knapsack_select(costs, vals, bud, unit)
        sel = o_idx if method == "optimal" else g_idx
        spent = float(sum(costs[i] for i in sel))
        out[a] = {"mode": method, "budget": bud, "funded": [df.loc[i, "Project"] for i in sel],
                  "unfunded": [df.loc[i, "Project"] for i in range(len(df)) if i not in sel],
                  "spent": spent, "unused": bud - spent,
                  "selected_score": float(sum(vals[i] for i in sel)),
                  "greedy_score": g_score, "optimal_score": o_score,
                  "greedy_funded": [df.loc[i, "Project"] for i in g_idx],
                  "optimal_funded": [df.loc[i, "Project"] for i in o_idx]}
    meta = {"remaining_after_mandatory": remaining, "mandatory_shortfall": shortfall}
    return out, meta


# ---------------------------------------------------------------------------
# 4. Site-deal economics (illustrative structure, user supplies sourced inputs)
# ---------------------------------------------------------------------------
def site_deal(capex, years, anchor_rent_month, tenant2_year, tenant3_year, coloc_factor,
              tenant_esc_pct, ground_rent_month, ground_esc_pct, opex_year1, opex_esc_pct,
              discount_rate_pct, terminal_multiple: float = 0.0):
    """Unlevered, pre-tax cash flows for one built site.

    - Anchor tenant pays `anchor_rent_month` in year 1, escalating annually.
    - Tenant 2 / 3 join in the given year (0 = never) and pay `coloc_factor` x the then-current
      anchor rent (assumes new tenants sign at the escalated market rent).
    - Ground lease and operating costs escalate at their own rates.
    - Optional terminal value = multiple x final-year NOI (0 = none, the conservative default).
    """
    years = int(years)
    rows = []
    for t in range(1, years + 1):
        extra = (1 if tenant2_year and t >= tenant2_year else 0) + (1 if tenant3_year and t >= tenant3_year else 0)
        anchor = anchor_rent_month * 12 * (1 + tenant_esc_pct / 100) ** (t - 1)
        revenue = anchor * (1 + coloc_factor * extra)
        ground = ground_rent_month * 12 * (1 + ground_esc_pct / 100) ** (t - 1)
        opex = opex_year1 * (1 + opex_esc_pct / 100) ** (t - 1)
        rows.append({"Year": t, "Tenants": 1 + extra, "Revenue": revenue, "Ground lease": ground,
                     "Opex": opex, "NOI": revenue - ground - opex})
    df = pd.DataFrame(rows)
    flows = [-capex] + df["NOI"].tolist()
    if terminal_multiple > 0 and len(df):
        flows[-1] += terminal_multiple * df["NOI"].iloc[-1]
    r = discount_rate_pct / 100
    df["Cumulative"] = np.cumsum(df["NOI"]) - capex
    irr_v = irr(flows)
    cum, simple_pb = -capex, None
    for t, noi in enumerate(df["NOI"], start=1):
        if cum + noi >= 0:
            simple_pb = (t - 1) + (-cum) / noi if noi > 0 else None
            break
        cum += noi
    metrics = {
        "npv": npv_of_flows(r, flows),
        "irr_pct": None if irr_v is None else irr_v * 100,
        "simple_payback": simple_pb,
        "year1_yield_pct": (df["NOI"].iloc[0] / capex * 100) if capex > 0 and len(df) else None,
        "peak_tenants": int(df["Tenants"].max()) if len(df) else 0,
    }
    return df, metrics


def pv_per_added_tenant(rent_month, esc_pct, rate_pct, term_years, opex_per_tenant_year: float = 0.0, opex_esc_pct: float = 0.0) -> float:
    """PV of the net cash one additional tenant adds over `term_years`."""
    r, e, o = rate_pct / 100, esc_pct / 100, opex_esc_pct / 100
    return sum((rent_month * 12 * (1 + e) ** (t - 1) - opex_per_tenant_year * (1 + o) ** (t - 1)) / (1 + r) ** t
               for t in range(1, int(term_years) + 1))


def breakeven_added_tenants(conversion_capex, rent_month, esc_pct, rate_pct, term_years, opex_per_tenant_year: float = 0.0):
    """Added tenants needed for a pole-to-macro conversion to reach NPV = 0 (fractional, and rounded up)."""
    pv = pv_per_added_tenant(rent_month, esc_pct, rate_pct, term_years, opex_per_tenant_year)
    if pv <= 0:
        return float("inf"), None
    exact = conversion_capex / pv
    return exact, int(math.ceil(exact - 1e-9))


def breakeven_rent(conversion_capex, n_tenants, esc_pct, rate_pct, term_years, opex_per_tenant_year: float = 0.0) -> float:
    """Monthly rent per added tenant needed for NPV = 0 given n_tenants added."""
    r, e = rate_pct / 100, esc_pct / 100
    factor = sum(12 * (1 + e) ** (t - 1) / (1 + r) ** t for t in range(1, int(term_years) + 1))
    pv_opex = sum(opex_per_tenant_year / (1 + r) ** t for t in range(1, int(term_years) + 1))
    return (conversion_capex / n_tenants + pv_opex) / factor


# ---------------------------------------------------------------------------
# 5. Document reading
# ---------------------------------------------------------------------------
def read_document(filename: str, data: bytes):
    """Return (text, warnings). Supports pdf, xlsx/xls, csv, docx, txt."""
    name, warnings = filename.lower(), []
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
            if len(text.strip()) < 50:
                warnings.append("This PDF has almost no extractable text. Scanned PDFs need OCR first.")
        elif name.endswith((".xlsx", ".xls")):
            sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
            text = "\n".join(f"Sheet: {n}\n{d.to_string(index=False, header=False)}" for n, d in sheets.items())
        elif name.endswith(".csv"):
            text = pd.read_csv(io.BytesIO(data), header=None).to_string(index=False, header=False)
        elif name.endswith(".docx"):
            from docx import Document
            doc = Document(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
            text = "\n".join(parts)
        else:
            text = data.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return "", [f"Could not read {filename}: {exc}"]
    if not text.strip():
        warnings.append("No text could be read from this file.")
    return text, warnings


# ---------------------------------------------------------------------------
# 6. AI extraction with evidence verification
# ---------------------------------------------------------------------------
NUMERIC_FIELDS = {
    "cost": "total capital cost of THIS project in US dollars (full dollars, not thousands or millions)",
    "npv": "net present value in US dollars; negative if the document shows it as negative, in parentheses or with a minus sign",
    "roi": "return on investment as a percentage number (46 for 46%)",
    "payback": "simple payback period in YEARS (convert months to years)",
    "discount_rate_pct": "discount rate or hurdle rate as a percentage number",
    "useful_life_yrs": "useful life or evaluation horizon in YEARS",
}
# Defaults for the two common providers. Model names get retired; both are overridable.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"     # Groq lists llama-3.1-8b-instant as shut down 08/16/26
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"


def build_prompt(doc_text: str) -> str:
    fields = "\n".join(f'  "{k}": {{"value": number or null, "evidence": "verbatim quote or null"}},  // {v}'
                       for k, v in NUMERIC_FIELDS.items())
    return f"""You extract figures from a capital expenditure (CapEx) business case.

Rules:
- Use ONLY what the document states. Never guess or compute a figure the document does not give. Use null when absent or marked not applicable.
- The document may mention other projects, budget caps, penalties, past costs, or scenarios. Extract the figures for THIS project's proposed investment and its BASE or recommended case.
- "evidence" must be copied VERBATIM from the document (max 200 characters) and must contain the number you report.
- Convert units: months to years for payback; thousands/millions to full dollars; percentages as plain numbers.
- suggested_aim must be one of: {", ".join(AIMS)} (or null if unclear). It is a suggestion for a human to confirm.
- Return ONLY valid JSON, no commentary, in exactly this shape:

{{
  "project_name": string or null,
  "suggested_aim": string or null,
{fields}
}}

DOCUMENT:
\"\"\"
{doc_text}
\"\"\""""


def parse_llm_json(raw: str) -> dict:
    """Pull the first JSON object out of a model reply (handles code fences and chatter)."""
    if not raw:
        raise ValueError("Empty response from the model.")
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in the model response.")
    return json.loads(raw[start:end + 1])


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


_NUM_RE = re.compile(
    r"(?:(?<![\w.])(?P<neg>[-\u2212\u2013]))?\s*\$?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<suf>million|billion|thousand|mm|bn|%|k(?![a-z])|m(?![a-z])|b(?![a-z]))?\s*"
    r"(?P<unit>months?|mos?(?![a-z])|years?|yrs?)?",
    re.I,
)
# Accounting-style negatives: ($48,000). Only a number wrapped entirely in parentheses is negative.
_PAREN_NEG_RE = re.compile(r"\(\s*\$?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<suf>million|billion|thousand|mm|bn|k|m|b)?\s*\)", re.I)
_YEARS_MONTHS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*(?:and\s*)?(\d+(?:\.\d+)?)\s*(?:months?|mos?)", re.I)
_SUFFIX = {"million": 1e6, "mm": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9, "thousand": 1e3, "k": 1e3}


def candidate_values(evidence: str) -> list:
    """All plausible numeric readings of a snippet, as signed values.
    A minus sign counts only when it stands alone before the number (not in ranges like 3-4),
    and parentheses count as negative only when they wrap the whole figure: ($48,000)."""
    text = evidence or ""
    cands, paren_spans = [], []
    for m in _PAREN_NEG_RE.finditer(text):
        base = float(m.group("num").replace(",", "")) * _SUFFIX.get((m.group("suf") or "").lower(), 1.0)
        cands.append(-base)
        paren_spans.append(m.span("num"))
    for m in _NUM_RE.finditer(text):
        a, b = m.span("num")
        if any(a >= s0 and b <= s1 for s0, s1 in paren_spans):
            continue
        base = float(m.group("num").replace(",", ""))
        suf = (m.group("suf") or "").lower()
        if suf in _SUFFIX:
            base *= _SUFFIX[suf]
        unit = (m.group("unit") or "").lower()
        vals = [base]
        if unit.startswith(("month", "mo")):
            vals.append(base / 12.0)
        sign = -1.0 if m.group("neg") else 1.0
        cands.extend(sign * v for v in vals)
    for m in _YEARS_MONTHS_RE.finditer(text):
        cands.append(float(m.group(1)) + float(m.group(2)) / 12.0)
    if re.search(r"\b(negative|deficit)\b", text, re.I):
        cands.extend([-abs(c) for c in cands])
    return cands


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0.005, abs_tol=0.01)


def verify_field(value, evidence, doc_text: str) -> str:
    """Check a model-reported figure against the document. Statuses:
    absent | no_evidence | quote_not_found | unverifiable | verified | sign_mismatch | number_mismatch
    'verified' means the quote really appears in the document AND contains the number (after unit
    conversion). It does NOT prove the number is the right one for this project, so humans still review."""
    v = parse_number(value)
    if v is None:
        return "absent"
    if not evidence or not str(evidence).strip():
        return "no_evidence"
    if _squash(str(evidence)) not in _squash(doc_text):
        return "quote_not_found"
    cands = candidate_values(str(evidence))
    if not cands:
        return "unverifiable"
    if any(_close(v, c) for c in cands):
        return "verified"
    if any(_close(abs(v), abs(c)) for c in cands):
        return "sign_mismatch"
    return "number_mismatch"


def normalize_extraction(obj: dict, doc_text: str) -> dict:
    fields = {}
    for key in NUMERIC_FIELDS:
        raw = obj.get(key)
        if isinstance(raw, dict):
            value, evidence = parse_number(raw.get("value")), raw.get("evidence")
        else:
            value, evidence = parse_number(raw), None
        fields[key] = {"value": value, "evidence": evidence, "status": verify_field(value, evidence, doc_text)}
    aim = obj.get("suggested_aim")
    return {"project_name": obj.get("project_name") or "", "suggested_aim": aim if aim in AIMS else None, "fields": fields}


def extract_project(doc_text: str, llm_fn: Callable[[str], str], max_chars: int = 30000) -> dict:
    """Run extraction. llm_fn(prompt) -> raw text. Never raises; errors come back in the result."""
    truncated = len(doc_text) > max_chars
    text = doc_text[:max_chars]
    try:
        raw = llm_fn(build_prompt(text))
        parsed = normalize_extraction(parse_llm_json(raw), text)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": friendly_llm_error(exc)}
    parsed.update({"ok": True, "truncated": truncated, "chars_read": len(text), "chars_total": len(doc_text)})
    return parsed


def friendly_llm_error(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if "decommission" in low or "model_not_found" in low or "does not exist" in low or "deprecat" in low:
        return (f"The model name appears to be retired or unavailable ({msg[:160]}). "
                "Set a current model in the sidebar. Providers retire model names regularly.")
    if "api key" in low or "401" in low or "authentication" in low:
        return "The API key was rejected. Check the key in Streamlit secrets."
    return f"Extraction failed: {msg[:300]}"


def make_llm_fn(provider: str, api_key: str, model: str) -> Callable[[str], str]:
    """Return a function prompt -> text for 'groq' or 'anthropic'. Imports are lazy."""
    if provider == "groq":
        from groq import Groq
        client = Groq(api_key=api_key)

        def call(prompt: str) -> str:
            resp = client.chat.completions.create(model=model, temperature=0, max_tokens=3000,
                                                  messages=[{"role": "user", "content": prompt}])
            return resp.choices[0].message.content or ""
        return call
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        def call(prompt: str) -> str:
            resp = client.messages.create(model=model, max_tokens=2000, temperature=0,
                                          messages=[{"role": "user", "content": prompt}])
            return "".join(getattr(b, "text", "") for b in resp.content)
        return call
    raise ValueError(f"Unknown provider: {provider}")


# ---- accuracy benchmark ----------------------------------------------------
BENCH_FIELDS = list(NUMERIC_FIELDS.keys())


def values_match(a, b) -> bool:
    return math.isclose(a, b, rel_tol=0.01, abs_tol=0.05)


def run_benchmark(cases: dict, llm_fn: Callable[[str], str]) -> dict:
    return {cid: extract_project(text, llm_fn) for cid, text in cases.items()}


def evaluate_extraction(results: dict, truth: pd.DataFrame):
    """Field-level scoring against hand-labelled ground truth.

    outcome: correct | hallucinated (truth absent, model gave a value) | missed | wrong
    The number that matters most is 'verified_wrong': figures our verifier marked 'verified'
    that were nevertheless wrong, because those are the ones a rushed reviewer would trust."""
    rows, aim_ok, aim_n, failed = [], 0, 0, []
    for _, t in truth.iterrows():
        cid = t["case_id"]
        res = results.get(cid)
        if not res or not res.get("ok"):
            failed.append(cid)
            continue
        aim_n += 1
        aim_ok += int(res.get("suggested_aim") == t["aim"])
        for f in BENCH_FIELDS:
            tv, ex = parse_number(t[f]), res["fields"][f]
            ev = ex["value"]
            if tv is None and ev is None:
                outcome = "correct"
            elif tv is None:
                outcome = "hallucinated"
            elif ev is None:
                outcome = "missed"
            else:
                outcome = "correct" if values_match(tv, ev) else "wrong"
            rows.append({"case_id": cid, "field": f, "truth": tv, "extracted": ev,
                         "verification": ex["status"], "outcome": outcome})
    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail, {"fields_scored": 0, "cases_failed": len(failed)}
    verified = detail[detail["verification"] == "verified"]
    summary = {
        "fields_scored": len(detail),
        "accuracy": float((detail["outcome"] == "correct").mean()),
        "hallucinated": int((detail["outcome"] == "hallucinated").sum()),
        "missed": int((detail["outcome"] == "missed").sum()),
        "wrong": int((detail["outcome"] == "wrong").sum()),
        "verified_total": len(verified),
        "verified_wrong": int(((verified["outcome"] == "wrong") | (verified["outcome"] == "hallucinated")).sum()),
        "verified_precision": float((verified["outcome"] == "correct").mean()) if len(verified) else None,
        "aim_accuracy": (aim_ok / aim_n) if aim_n else None,
        "cases_failed": len(failed),
    }
    return detail, summary
