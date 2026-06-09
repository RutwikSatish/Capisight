"""
Capisight - CAPEX project scoring engine (front half)

Capisight scores and ranks capital-expenditure projects, grouped by their AIM,
and allocates a budget across aims. It is the "front half" of a larger concept:
deciding where capital should go, with an honest, transparent method.

WHY GROUP BY AIM
McKinsey ("Managing a moonshot") argues capital projects should be grouped by
aim rather than lumped together, because different aims warrant different
evaluation criteria. A mandatory safety project and a growth bet do not belong
on the same ranked list. So Capisight:
  1. tags each project with one of four aims,
  2. scores each aim's projects on that aim's own weight profile,
  3. ranks projects WITHIN each aim, and
  4. allocates a budget ACROSS aims (the user sets each aim's share), because
     there is no single yardstick that compares across aims.

HONESTY NOTES (these matter)
  - The four aims are from McKinsey. The default weight profiles per aim are a
    reasonable starting hypothesis, NOT a sourced prescription. Every weight is
    user-editable.
  - Sample projects and their aim tags are ILLUSTRATIVE examples, not validated
    figures. Edit them or replace them with your own.
  - Per-aim budget shares are hard targets: money does NOT move across aims
    automatically. If a share strands money, the app says so and asks you to
    rebalance, rather than silently spending it elsewhere. This preserves the
    "aims are not comparable" principle.

NOT INCLUDED YET
  - The experimental causal "back half" (did the spend actually move the
    outcome?) is a separate module, deliberately not built here.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import altair as alt  # ships with Streamlit; no extra dependency to deploy

st.set_page_config(page_title="Capisight - CAPEX scoring", layout="wide")

# ---------------------------------------------------------------------------
# Criteria. direction: "higher" = bigger raw value is better (NPV);
# "lower" = smaller is better (Risk, Cost, Payback).
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

# Four aims (McKinsey). Default per-aim weight profiles are a starting
# hypothesis only; every value is user-editable in the sidebar.
AIMS = ["Regulatory / safety", "Business-as-usual", "New growth", "Improve performance"]

DEFAULT_AIM_WEIGHTS = {
    "Regulatory / safety":   {"npv": 5,  "roi": 5,  "payback": 5,  "strategic": 20, "operational": 15, "risk": 35, "cost": 15},
    "Business-as-usual":     {"npv": 10, "roi": 10, "payback": 15, "strategic": 5,  "operational": 20, "risk": 20, "cost": 20},
    "New growth":            {"npv": 30, "roi": 20, "payback": 5,  "strategic": 25, "operational": 10, "risk": 5,  "cost": 5},
    "Improve performance":   {"npv": 15, "roi": 15, "payback": 10, "strategic": 10, "operational": 30, "risk": 10, "cost": 10},
}

# Illustrative sample data (from the author's original model), tagged with an
# aim. Values and tags are illustrative, not validated.
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
    """Score a set of projects (one bucket) on a weight profile.
    Normalization is within this set, so ranks are within-bucket.
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
    """Fund highest-scoring projects in rank order until the budget runs out.
    Skips a project that doesn't fit and keeps trying lower-ranked ones."""
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

st.title("Capisight")
st.caption(
    "Score capital projects, grouped by their aim, then allocate a budget across "
    "aims. A mandatory safety project and a growth bet are not ranked on the same "
    "yardstick. Sample projects and aim tags are illustrative examples, not "
    "validated figures \u2014 edit them or add your own."
)

# ---------------------------------------------------------------------------
# Sidebar: per-aim weight profiles
# ---------------------------------------------------------------------------
st.sidebar.header("Weights by aim")
st.sidebar.caption(
    "Each aim has its own weight profile. Pick an aim to tune how its projects "
    "are scored. Values are relative \u2014 auto-normalized to 100% within the aim."
)

for aim in AIMS:
    for k in CRIT_KEYS:
        skey = f"w_{aim}_{k}"
        if skey not in st.session_state:
            st.session_state[skey] = DEFAULT_AIM_WEIGHTS[aim][k]

active_aim = st.sidebar.selectbox("Aim to edit", AIMS, index=0)

if active_aim == "Regulatory / safety":
    st.sidebar.info(
        "Regulatory / safety projects are often mandatory rather than ROI-ranked. "
        "Scoring helps prioritize among them, but in practice these are frequently "
        "'must-do' regardless of score."
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


def aim_weights(aim):
    return {k: st.session_state[f"w_{aim}_{k}"] for k in CRIT_KEYS}


# ---------------------------------------------------------------------------
# Editable projects
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

# ---------------------------------------------------------------------------
# Within-bucket ranking
# ---------------------------------------------------------------------------
valid = edited.dropna(subset=["Aim"]) if "Aim" in edited.columns else edited
st.subheader("Ranked results, within each aim")

bucket_scores = {}
bucket_effweights = {}  # aim -> effective (normalized) weights, for the breakdown visual
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
    bucket_effweights[aim] = eff

    st.markdown(f"**{aim}**  ({len(bucket)} project{'s' if len(bucket) != 1 else ''})")
    cols = ["Rank", "Project", "Score"] + CRIT_KEYS
    show = scored[cols].copy()
    show["Score"] = show["Score"].map(lambda x: f"{x:.3f}")
    st.dataframe(show, use_container_width=True, hide_index=True)

    # Visual 1: within-aim ranking bars (horizontal, sorted by score).
    # Comparison is valid here because all bars share this aim's weights.
    if len(scored) >= 1:
        rank_chart = (
            alt.Chart(scored)
            .mark_bar(color="#1D9E75")
            .encode(
                x=alt.X("Score:Q", title="Score (0-1, within this aim)",
                        scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("Project:N", sort="-x", title=None),
                tooltip=["Project", alt.Tooltip("Score:Q", format=".3f"),
                         "cost", "npv", "roi"],
            )
            .properties(height=max(80, 38 * len(scored)))
        )
        st.altair_chart(rank_chart, use_container_width=True)

if not bucket_scores:
    st.info("Add projects and assign aims to see rankings.")

# ---------------------------------------------------------------------------
# Visual 2: criteria breakdown for a selected project
# Shows how a project's score is built from each criterion's weighted
# contribution, so the score is transparent rather than a black box.
# ---------------------------------------------------------------------------
if bucket_scores:
    st.subheader("Why a project scored what it did")
    st.caption("Pick a project to see how each criterion contributed to its score.")
    pick_aim = st.selectbox("Aim", list(bucket_scores.keys()), key="bd_aim")
    aim_df = bucket_scores[pick_aim]
    pick_proj = st.selectbox("Project", aim_df["Project"].tolist(), key="bd_proj")

    eff = bucket_effweights[pick_aim]
    row = aim_df[aim_df["Project"] == pick_proj].iloc[0]
    # Re-derive each criterion's normalized value within this aim, then its
    # weighted contribution. Contributions sum to the project's score.
    parts = []
    for c in CRITERIA:
        norm = normalize_column(aim_df[c["key"]], c["direction"])
        nv = norm[aim_df.index[aim_df["Project"] == pick_proj][0]]
        parts.append({
            "Criterion": c["label"],
            "Contribution": nv * eff[c["key"]],
            "Normalized value": nv,
            "Weight": eff[c["key"]],
        })
    parts_df = pd.DataFrame(parts)
    breakdown = (
        alt.Chart(parts_df)
        .mark_bar(color="#534AB7")
        .encode(
            x=alt.X("Contribution:Q", title="Weighted contribution to score"),
            y=alt.Y("Criterion:N", sort="-x", title=None),
            tooltip=[
                "Criterion",
                alt.Tooltip("Normalized value:Q", format=".2f"),
                alt.Tooltip("Weight:Q", format=".0%"),
                alt.Tooltip("Contribution:Q", format=".3f"),
            ],
        )
        .properties(height=max(120, 30 * len(parts_df)))
    )
    st.altair_chart(breakdown, use_container_width=True)
    st.caption(
        f"Contributions sum to {pick_proj}'s score of {row['Score']:.3f}. "
        "A criterion contributes more when the project scores well on it *and* "
        "that criterion carries weight in this aim."
    )

# ---------------------------------------------------------------------------
# Visual 3: cost vs score, within a single aim
# A within-aim view to spot cheap high-scorers vs. expensive low-scorers.
# Kept within one aim so the score axis stays comparable.
# ---------------------------------------------------------------------------
if bucket_scores:
    st.subheader("Cost vs. score, within an aim")
    st.caption("Top-left is the sweet spot: high score, low cost. Stays within one "
               "aim so scores are comparable.")
    sc_aim = st.selectbox("Aim", list(bucket_scores.keys()), key="sc_aim")
    sc_df = bucket_scores[sc_aim]
    scatter = (
        alt.Chart(sc_df)
        .mark_circle(size=160, color="#D85A30", opacity=0.8)
        .encode(
            x=alt.X("cost:Q", title="Estimated cost (USD)"),
            y=alt.Y("Score:Q", title="Score (within this aim)",
                    scale=alt.Scale(domain=[0, 1])),
            tooltip=["Project", alt.Tooltip("Score:Q", format=".3f"), "cost",
                     "npv", "roi", "risk"],
        )
        .properties(height=320)
    )
    labels = scatter.mark_text(align="left", dx=8, fontSize=11).encode(
        text="Project:N", color=alt.value("#888780")
    )
    st.altair_chart(scatter + labels, use_container_width=True)

# ---------------------------------------------------------------------------
# Cross-bucket budget allocation (targets, with stranded money surfaced)
# Per-aim shares are hard targets. Money does not move across aims
# automatically. If a share strands money, the app explains why and prompts a
# rebalance, rather than silently spending it elsewhere.
# ---------------------------------------------------------------------------
if bucket_scores:
    st.subheader("Budget allocation across aims")
    st.caption(
        "Set a total budget and how it splits across aims. Within each aim, the "
        "top-ranked projects are funded until that aim's share is used up. Shares "
        "are hard targets \u2014 money does not move across aims automatically, by "
        "design (aims are not comparable on one scale). If a share cannot be fully "
        "used, the app tells you and asks you to rebalance."
    )

    total_budget = st.number_input(
        "Total budget (USD)", min_value=0, value=1500000, step=50000,
    )

    present_aims = list(bucket_scores.keys())
    st.markdown("**Share of budget per aim (%)** \u2014 normalized to 100%.")
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
        total_committed = 0.0
        total_stranded = 0.0
        needs_rebalance = []
        budget_rows = []  # for the allocation visual

        for aim in present_aims:
            aim_budget = total_budget * raw_shares[aim] / share_total
            scored = bucket_scores[aim]
            chosen, spent = greedy_select(scored, aim_budget)
            stranded = aim_budget - spent
            total_committed += spent
            total_stranded += stranded
            budget_rows.append({"Aim": aim, "Committed": spent, "Unused": stranded,
                                "Target": aim_budget})

            unfunded = scored[~scored["Project"].isin(set(chosen))]
            if chosen:
                line = (f"**{aim}** \u2014 target ${aim_budget:,.0f}, "
                        f"committed ${spent:,.0f}: {', '.join(chosen)}")
            else:
                line = f"**{aim}** \u2014 target ${aim_budget:,.0f}, committed $0"

            if stranded > 0.5 and len(unfunded) > 0:
                cheapest = unfunded["cost"].min()
                line += (f".  \n_Strands ${stranded:,.0f}: the cheapest unfunded "
                         f"project here costs ${cheapest:,.0f}, more than the "
                         f"${stranded:,.0f} left in this share._")
                needs_rebalance.append(aim)
                st.warning(line)
            elif stranded > 0.5 and len(unfunded) == 0:
                line += (f".  \n_Surplus ${stranded:,.0f}: this share more than "
                         f"covers every project in the aim. Consider lowering its "
                         f"share._")
                needs_rebalance.append(aim)
                st.info(line)
            else:
                st.success(line)

        total_unspent = total_budget - total_committed
        st.markdown(
            f"**Committed across all aims: ${total_committed:,.0f} of "
            f"${total_budget:,.0f}**  (unallocated: ${total_unspent:,.0f})"
        )

        if needs_rebalance and total_unspent > 0.5:
            st.warning(
                f"\u2248${total_unspent:,.0f} is unallocated because the per-aim "
                f"shares do not fit the project costs in: "
                f"{', '.join(needs_rebalance)}. Adjust the shares above to use more "
                f"of the budget. Money is not moved across aims automatically \u2014 "
                f"that is a deliberate choice, since aims are not comparable on one "
                f"scale."
            )

        # Visual 4: target vs committed vs unused per aim (stacked bars).
        # Comparing money across aims IS valid (dollars are dollars), unlike
        # comparing scores. This makes the stranded-money story visual.
        bud_df = pd.DataFrame(budget_rows)
        melted = bud_df.melt(
            id_vars="Aim", value_vars=["Committed", "Unused"],
            var_name="Status", value_name="USD",
        )
        budget_chart = (
            alt.Chart(melted)
            .mark_bar()
            .encode(
                x=alt.X("USD:Q", title="USD", stack="zero"),
                y=alt.Y("Aim:N", title=None),
                color=alt.Color(
                    "Status:N",
                    scale=alt.Scale(domain=["Committed", "Unused"],
                                    range=["#1D9E75", "#D3D1C7"]),
                    legend=alt.Legend(title=None, orient="top"),
                ),
                tooltip=["Aim", "Status", alt.Tooltip("USD:Q", format="$,.0f")],
            )
            .properties(height=max(120, 46 * len(bud_df)))
        )
        st.altair_chart(budget_chart, use_container_width=True)
