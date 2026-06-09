"""
CAPEX Project Scoring Engine - Front Half with per-aim bucketing

A Streamlit app that scores and ranks capital-expenditure projects using a
weighted, normalized multi-criteria model, organized by PROJECT AIM.

WHY BUCKET BY AIM:
McKinsey ("Managing a moonshot") argues that capital projects should be grouped
by their aim, not lumped together, because different aims should be judged on
different criteria. A mandatory safety project and a growth bet do not belong on
the same ranked list. So this app:
  1. tags each project with one of four aims,
  2. scores each aim's projects on that aim's own weight profile,
  3. ranks projects WITHIN each aim, and
  4. allocates a budget ACROSS aims (the user sets each aim's share),
     because there is no single yardstick that compares across aims.

The four aims are from McKinsey. The specific default weights per aim are a
reasonable starting hypothesis, NOT a sourced prescription - every weight is
user-editable.

WHAT THIS IS NOT (yet):
- No causal "back half" (that is, the separate experimental module).

Sample projects are ILLUSTRATIVE examples, not validated figures.

Run locally:
    pip install streamlit pandas
    streamlit run capex_scoring_app.py
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="CAPEX Scoring Engine", layout="wide")

# ---------------------------------------------------------------------------
# Criteria. direction: "higher" = bigger raw value is better (NPV);
# "lower" = smaller is better (Risk, Cost, Payback). Matches the Excel model.
# ---------------------------------------------------------------------------
CRITERIA = [
    {"key": "npv",         "label": "NPV (USD)",                 "direction": "higher"},
    {"key": "roi",         "label": "ROI (%)",                   "direction": "higher"},
    {"key": "payback",     "label": "Payback period (years)",    "direction": "lower"},
    {"key": "strategic",   "label": "Strategic score (1-10)",    "direction": "higher"},
    {"key": "operational", "label": "Operational impact (1-10)", "direction": "higher"},
    {"key": "risk",        "label": "Risk score (1-10)",         "direction": "lower"},
    {"key": "cost",        "label": "Estimated cost (USD)",      "direction": "lower"},
]
CRIT_KEYS = [c["key"] for c in CRITERIA]

# ---------------------------------------------------------------------------
# The four aims (McKinsey). Each has a DEFAULT weight profile that reflects
# what that aim cares about. These defaults are a starting hypothesis only;
# the user can edit every value. Rationale per aim:
#   Regulatory/safety - mandatory; financial return matters little, so NPV/ROI
#       are down-weighted and the project is largely "must-do" (see note in UI).
#   Business-as-usual - keep the lights on; cost control and low risk dominate.
#   New growth - upside-seeking; NPV, ROI, strategic value dominate.
#   Improve performance - operational gains dominate (OEE/throughput proxy).
# ---------------------------------------------------------------------------
AIMS = ["Regulatory / safety", "Business-as-usual", "New growth", "Improve performance"]

DEFAULT_AIM_WEIGHTS = {
    "Regulatory / safety":   {"npv": 5,  "roi": 5,  "payback": 5,  "strategic": 20, "operational": 15, "risk": 35, "cost": 15},
    "Business-as-usual":     {"npv": 10, "roi": 10, "payback": 15, "strategic": 5,  "operational": 20, "risk": 20, "cost": 20},
    "New growth":            {"npv": 30, "roi": 20, "payback": 5,  "strategic": 25, "operational": 10, "risk": 5,  "cost": 5},
    "Improve performance":   {"npv": 15, "roi": 15, "payback": 10, "strategic": 10, "operational": 30, "risk": 10, "cost": 10},
}

# ---------------------------------------------------------------------------
# Illustrative sample data (from the author's original model), now tagged with
# an aim. Tags are illustrative guesses to demonstrate the feature.
# ---------------------------------------------------------------------------
SAMPLE_PROJECTS = pd.DataFrame([
    {"Project": "Automation Line A",         "Aim": "New growth",          "cost": 750000, "npv": 400000, "roi": 18.5, "strategic": 8, "operational": 7, "risk": 3, "payback": 4.2},
    {"Project": "Energy Efficiency Retrofit","Aim": "Improve performance", "cost": 300000, "npv": 150000, "roi": 20.0, "strategic": 7, "operational": 6, "risk": 4, "payback": 3.0},
    {"Project": "Assembly Jig Upgrade",      "Aim": "Improve performance", "cost": 120000, "npv": 60000,  "roi": 12.0, "strategic": 6, "operational": 5, "risk": 6, "payback": 2.5},
    {"Project": "Quality Inspection System", "Aim": "New growth",          "cost": 500000, "npv": 280000, "roi": 16.0, "strategic": 9, "operational": 8, "risk": 5, "payback": 3.5},
    {"Project": "Warehouse Conveyor",        "Aim": "Business-as-usual",   "cost": 400000, "npv": 120000, "roi": 10.0, "strategic": 5, "operational": 6, "risk": 7, "payback": 4.8},
    {"Project": "Robotic Palletizer",        "Aim": "New growth",          "cost": 650000, "npv": 320000, "roi": 22.0, "strategic": 8, "operational": 7, "risk": 3, "payback": 3.1},
    {"Project": "Boiler Replacement",        "Aim": "Regulatory / safety", "cost": 200000, "npv": 90000,  "roi": 14.0, "strategic": 4, "operational": 4, "risk": 6, "payback": 3.8},
    {"Project": "Lighting Retrofit",         "Aim": "Business-as-usual",   "cost": 80000,  "npv": 35000,  "roi": 9.0,  "strategic": 3, "operational": 3, "risk": 8, "payback": 5.0},
])


def normalize_column(series: pd.Series, direction: str) -> pd.Series:
    """Min-max normalize one criterion to 0-1, respecting direction.
    If all values equal (or only one project), everyone scores 1.0 for it."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series([1.0] * len(series), index=series.index)
    if direction == "higher":
        return (series - lo) / (hi - lo)
    return (hi - series) / (hi - lo)


def compute_scores(projects: pd.DataFrame, weights: dict):
    """Score a SET of projects (one bucket) on a weight profile.
    Normalization is done within this set, so ranks are within-bucket.
    Returns (scored_df_sorted, effective_weights)."""
    total_w = sum(weights.values())
    eff = {k: (w / total_w if total_w > 0 else 0) for k, w in weights.items()}
    out = projects.copy().reset_index(drop=True)
    weighted_total = pd.Series([0.0] * len(out), index=out.index)
    for c in CRITERIA:
        norm = normalize_column(out[c["key"]], c["direction"])
        weighted_total += norm * eff[c["key"]]
    out["Score"] = weighted_total
    out = out.sort_values("Score", ascending=False).reset_index(drop=True)
    out.insert(0, "Rank", out.index + 1)
    return out, eff


def greedy_select(scored: pd.DataFrame, budget: float):
    """Pick highest-scoring projects in rank order until the budget runs out.
    Skips a project that doesn't fit and keeps trying smaller ones below it."""
    chosen, spent = [], 0.0
    for _, row in scored.iterrows():
        if spent + row["cost"] <= budget:
            chosen.append(row["Project"])
            spent += row["cost"]
    return chosen, spent


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "projects" not in st.session_state:
    st.session_state.projects = SAMPLE_PROJECTS.copy()

st.title("CAPEX project scoring engine")
st.caption(
    "Projects are grouped by their aim and scored on criteria that fit that aim, "
    "because a mandatory safety project and a growth bet should not be ranked on "
    "the same yardstick. Sample projects and their aim tags are illustrative "
    "examples, not validated figures \u2014 edit them or add your own."
)

# ---------------------------------------------------------------------------
# Sidebar: choose an aim to edit its weight profile
# ---------------------------------------------------------------------------
st.sidebar.header("Weights by aim")
st.sidebar.caption(
    "Each aim has its own weight profile. Pick an aim to tune how its projects "
    "are scored. Values are relative \u2014 auto-normalized to 100% within the aim."
)

# Initialize per-aim weights in session state once.
for aim in AIMS:
    for k in CRIT_KEYS:
        skey = f"w_{aim}_{k}"
        if skey not in st.session_state:
            st.session_state[skey] = DEFAULT_AIM_WEIGHTS[aim][k]

active_aim = st.sidebar.selectbox("Aim to edit", AIMS, index=0)

if active_aim == "Regulatory / safety":
    st.sidebar.info(
        "Note: regulatory / safety projects are often mandatory rather than "
        "ROI-ranked. Scoring here helps prioritize among them, but in practice "
        "these are frequently 'must-do' regardless of score."
    )

for c in CRITERIA:
    arrow = "higher is better" if c["direction"] == "higher" else "lower is better"
    st.sidebar.slider(
        f"{c['label']}  ({arrow})",
        min_value=0, max_value=40, step=1,
        key=f"w_{active_aim}_{c['key']}",
    )

if st.sidebar.button("Reset this aim to defaults"):
    for k in CRIT_KEYS:
        st.session_state[f"w_{active_aim}_{k}"] = DEFAULT_AIM_WEIGHTS[active_aim][k]
    st.rerun()

# ---------------------------------------------------------------------------
# Main: editable projects (now with an Aim column as a dropdown)
# ---------------------------------------------------------------------------
st.subheader("Projects")
st.caption("Edit any cell, change a project's aim, add rows, or delete rows.")
edited = st.data_editor(
    st.session_state.projects,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Aim": st.column_config.SelectboxColumn("Aim", options=AIMS, required=True),
    },
    key="editor",
)
st.session_state.projects = edited

# Collect the active aim's weights for the transparency table.
def aim_weights(aim):
    return {k: st.session_state[f"w_{aim}_{k}"] for k in CRIT_KEYS}

# ---------------------------------------------------------------------------
# Per-bucket ranking
# ---------------------------------------------------------------------------
valid = edited.dropna(subset=["Aim"]) if "Aim" in edited.columns else edited
st.subheader("Ranked results, within each aim")

bucket_scores = {}  # aim -> scored df, reused by the budget step
for aim in AIMS:
    bucket = valid[valid["Aim"] == aim]
    if len(bucket) == 0:
        continue
    w = aim_weights(aim)
    if sum(w.values()) == 0:
        st.warning(f"**{aim}**: all weights are zero \u2014 set at least one to rank.")
        continue
    scored, eff = compute_scores(bucket, w)
    bucket_scores[aim] = scored

    st.markdown(f"**{aim}**  ({len(bucket)} project{'s' if len(bucket) != 1 else ''})")
    cols = ["Rank", "Project", "Score"] + CRIT_KEYS
    show = scored[cols].copy()
    show["Score"] = show["Score"].map(lambda x: f"{x:.3f}")
    st.dataframe(show, use_container_width=True, hide_index=True)

if not bucket_scores:
    st.info("Add projects and assign aims to see rankings.")

# ---------------------------------------------------------------------------
# Cross-bucket budget allocation
# Rather than one pooled ranking, the user sets how much budget each aim gets,
# and within each aim the highest-ranked projects are funded until that aim's
# share runs out. This mirrors McKinsey's process: cap the spend, fund the most
# valuable per category, defer the rest.
# ---------------------------------------------------------------------------
if bucket_scores:
    st.subheader("Budget allocation across aims")
    st.caption(
        "Set a total budget and how it splits across aims. Within each aim, the "
        "top-ranked projects are funded until that aim's share is used up. There "
        "is no single cross-aim ranking by design \u2014 aims are not comparable on "
        "one scale."
    )

    total_budget = st.number_input(
        "Total budget (USD)", min_value=0, value=1500000, step=50000,
    )

    present_aims = list(bucket_scores.keys())
    st.markdown("**Share of budget per aim (%)** \u2014 these are normalized to 100%.")
    share_cols = st.columns(len(present_aims))
    raw_shares = {}
    for i, aim in enumerate(present_aims):
        raw_shares[aim] = share_cols[i].number_input(
            aim, min_value=0, max_value=100,
            value=round(100 / len(present_aims)), step=5, key=f"share_{aim}",
        )

    share_total = sum(raw_shares.values())
    if share_total == 0:
        st.warning("Set at least one aim's share above zero.")
    else:
        st.markdown("**Funded projects per aim:**")
        grand_spent = 0.0
        for aim in present_aims:
            aim_budget = total_budget * raw_shares[aim] / share_total
            chosen, spent = greedy_select(bucket_scores[aim], aim_budget)
            grand_spent += spent
            if chosen:
                st.success(
                    f"**{aim}** \u2014 budget ${aim_budget:,.0f}, "
                    f"spent ${spent:,.0f}: {', '.join(chosen)}"
                )
            else:
                st.info(
                    f"**{aim}** \u2014 budget ${aim_budget:,.0f}: "
                    f"no project fits this share."
                )
        st.markdown(f"**Total committed across all aims: ${grand_spent:,.0f}** "
                    f"of ${total_budget:,.0f}")
