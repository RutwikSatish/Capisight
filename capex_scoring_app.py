"""
Capisight - CAPEX project scoring engine (front half)

Scores capital-expenditure projects grouped by their AIM, ranks them within each
aim, and allocates a budget across aims. Polished UI: header, KPI cards, tabs,
and Plotly charts.

WHY GROUP BY AIM
McKinsey ("Managing a moonshot") argues capital projects should be grouped by
aim rather than lumped together, because different aims warrant different
evaluation criteria. A mandatory safety project and a growth bet do not belong
on the same ranked list. So Capisight scores each aim on its own weight profile,
ranks WITHIN each aim, and allocates a budget ACROSS aims (shares are hard
targets; money is never moved across aims automatically).

HONESTY NOTES
  - The four aims are from McKinsey. The default per-aim weight profiles are a
    starting hypothesis, NOT a sourced prescription. Every weight is editable.
  - Sample projects and aim tags are ILLUSTRATIVE examples, not validated figures.
  - All "score" visuals stay WITHIN one aim. Only money (cost, budget) is shown
    across aims, because dollars are comparable where scores are not.

NOT INCLUDED: the experimental causal "back half".

Run locally:
    pip install -r requirements.txt
    streamlit run capex_scoring_app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Capisight - CAPEX scoring", page_icon="📊", layout="wide")

# ---------------------------------------------------------------------------
# Palette (matches the dark-green theme)
# ---------------------------------------------------------------------------
GREEN = "#1D9E75"
GREEN_D = "#0F6E56"
PURPLE = "#7F77DD"
CORAL = "#D85A30"
GREY = "#D3D1C7"
INK = "#e8ede9"
MUTED = "#9aa6a0"
SURFACE = "#161b18"
LINE = "#283330"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=INK, size=13),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor=LINE, zerolinecolor=LINE),
    yaxis=dict(gridcolor=LINE, zerolinecolor=LINE),
)

# ---------------------------------------------------------------------------
# Criteria & aims
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
LABEL = {c["key"]: c["label"] for c in CRITERIA}

AIMS = ["Regulatory / safety", "Business-as-usual", "New growth", "Improve performance"]

DEFAULT_AIM_WEIGHTS = {
    "Regulatory / safety":   {"npv": 5,  "roi": 5,  "payback": 5,  "strategic": 20, "operational": 15, "risk": 35, "cost": 15},
    "Business-as-usual":     {"npv": 10, "roi": 10, "payback": 15, "strategic": 5,  "operational": 20, "risk": 20, "cost": 20},
    "New growth":            {"npv": 30, "roi": 20, "payback": 5,  "strategic": 25, "operational": 10, "risk": 5,  "cost": 5},
    "Improve performance":   {"npv": 15, "roi": 15, "payback": 10, "strategic": 10, "operational": 30, "risk": 10, "cost": 10},
}

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
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series([1.0] * len(series), index=series.index)
    if direction == "higher":
        return (series - lo) / (hi - lo)
    return (hi - series) / (hi - lo)


def compute_scores(projects: pd.DataFrame, weights: dict):
    total_w = sum(weights.values())
    eff = {k: (w / total_w if total_w > 0 else 0) for k, w in weights.items()}
    out = projects.copy().reset_index(drop=True)
    weighted_total = pd.Series([0.0] * len(out), index=out.index)
    for c in CRITERIA:
        weighted_total += normalize_column(out[c["key"]], c["direction"]) * eff[c["key"]]
    out["Score"] = weighted_total
    out = out.sort_values("Score", ascending=False).reset_index(drop=True)
    out.insert(0, "Rank", out.index + 1)
    return out, eff


def greedy_select(scored: pd.DataFrame, budget: float):
    chosen, spent = [], 0.0
    for _, row in scored.iterrows():
        if spent + row["cost"] <= budget:
            chosen.append(row["Project"])
            spent += row["cost"]
    return chosen, spent


def kpi_card(col, label, value, sub=None, sub_color=MUTED):
    sub_html = f'<div style="color:{sub_color};font-size:12px;margin-top:4px">{sub}</div>' if sub else ""
    col.markdown(
        f'''<div style="background:{SURFACE};border:1px solid {LINE};border-radius:12px;padding:16px 18px">
        <div style="color:{MUTED};font-size:12px;letter-spacing:.06em;text-transform:uppercase">{label}</div>
        <div style="color:{INK};font-size:26px;font-weight:650;margin-top:6px">{value}</div>
        {sub_html}</div>''',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
if "projects" not in st.session_state:
    st.session_state.projects = SAMPLE_PROJECTS.copy()

for aim in AIMS:
    for k in CRIT_KEYS:
        sk = f"w_{aim}_{k}"
        if sk not in st.session_state:
            st.session_state[sk] = DEFAULT_AIM_WEIGHTS[aim][k]


def aim_weights(aim):
    return {k: st.session_state[f"w_{aim}_{k}"] for k in CRIT_KEYS}


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    f'''<div style="padding:8px 0 4px">
    <span style="font-size:30px;font-weight:700;color:{INK}">📊 Capisight</span>
    <div style="color:{MUTED};font-size:15px;margin-top:2px">
    CAPEX project scoring &mdash; grouped by aim, ranked within aim, budgeted across aims</div>
    </div>''',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar: per-aim weights
# ---------------------------------------------------------------------------
st.sidebar.header("Weights by aim")
st.sidebar.caption(
    "Each aim has its own weight profile. Pick an aim to tune it. Values are "
    "relative \u2014 auto-normalized to 100% within the aim."
)
active_aim = st.sidebar.selectbox("Aim to edit", AIMS, index=0)
if active_aim == "Regulatory / safety":
    st.sidebar.info(
        "Regulatory / safety projects are often mandatory rather than ROI-ranked. "
        "Scoring helps prioritize among them, but these are frequently 'must-do'."
    )
for c in CRITERIA:
    arrow = "higher is better" if c["direction"] == "higher" else "lower is better"
    st.sidebar.slider(f"{c['label']}  ({arrow})", 0, 40, step=1, key=f"w_{active_aim}_{c['key']}")
if st.sidebar.button("Reset this aim to defaults"):
    for k in CRIT_KEYS:
        st.session_state[f"w_{active_aim}_{k}"] = DEFAULT_AIM_WEIGHTS[active_aim][k]
    st.rerun()

# ---------------------------------------------------------------------------
# Compute everything up front (so KPI cards can summarize)
# ---------------------------------------------------------------------------
projects_df = st.session_state.projects
valid = projects_df.dropna(subset=["Aim"]) if "Aim" in projects_df.columns else projects_df

bucket_scores, bucket_eff = {}, {}
for aim in AIMS:
    bucket = valid[valid["Aim"] == aim]
    if len(bucket) == 0:
        continue
    w = aim_weights(aim)
    if sum(w.values()) == 0:
        continue
    scored, eff = compute_scores(bucket, w)
    bucket_scores[aim] = scored
    bucket_eff[aim] = eff

# ---------------------------------------------------------------------------
# KPI cards (portfolio-level facts only; never a cross-aim score)
# ---------------------------------------------------------------------------
n_projects = len(valid)
total_cost = float(valid["cost"].sum()) if n_projects else 0.0
n_aims_used = valid["Aim"].nunique() if n_projects else 0
c1, c2, c3, c4 = st.columns(4)
kpi_card(c1, "Projects", f"{n_projects}")
kpi_card(c2, "Aims in use", f"{n_aims_used} / {len(AIMS)}")
kpi_card(c3, "Total cost of all projects", f"${total_cost:,.0f}")
kpi_card(c4, "Criteria per project", f"{len(CRITERIA)}")

st.markdown(
    f'<div style="color:{MUTED};font-size:13px;margin:14px 0 4px">'
    f'Scores compare projects <b>only within an aim</b>. Sample data is illustrative, '
    f'not validated. Edit projects and weights to fit your portfolio.</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_proj, tab_rank, tab_break, tab_scatter, tab_budget = st.tabs(
    ["Projects", "Rankings", "Why a score", "Cost vs score", "Budget"]
)

# ---- Tab: Projects ----
with tab_proj:
    st.caption("Edit any cell, change a project's aim, add rows, or delete rows.")
    edited = st.data_editor(
        st.session_state.projects,
        num_rows="dynamic",
        use_container_width=True,
        column_config={"Aim": st.column_config.SelectboxColumn("Aim", options=AIMS, required=True)},
        key="editor",
    )
    st.session_state.projects = edited
    st.caption("Switch tabs to see rankings, score breakdowns, and budget allocation. "
               "Changes here flow through to every tab.")

# ---- Tab: Rankings ----
with tab_rank:
    if not bucket_scores:
        st.info("Add projects and assign aims to see rankings.")
    for aim in AIMS:
        if aim not in bucket_scores:
            continue
        scored = bucket_scores[aim]
        st.markdown(f"#### {aim}  \u00b7  {len(scored)} project{'s' if len(scored) != 1 else ''}")
        # Horizontal bar, sorted ascending so highest sits at top in Plotly.
        s = scored.sort_values("Score")
        fig = go.Figure(go.Bar(
            x=s["Score"], y=s["Project"], orientation="h",
            marker_color=GREEN,
            text=[f"{v:.3f}" for v in s["Score"]], textposition="outside",
            hovertemplate="%{y}<br>Score %{x:.3f}<extra></extra>",
        ))
        fig.update_layout(
            **PLOTLY_LAYOUT,
            height=90 + 46 * len(s),  # guarantees a label row per bar (fixes overlap)
        )
        fig.update_xaxes(range=[0, 1.08], title="Score (0-1, within this aim)")
        fig.update_yaxes(automargin=True, title=None)
        st.plotly_chart(fig, use_container_width=True, key=f"rank_{aim}")
        with st.expander(f"Table \u2014 {aim}"):
            cols = ["Rank", "Project", "Score"] + CRIT_KEYS
            show = scored[cols].copy()
            show["Score"] = show["Score"].map(lambda x: f"{x:.3f}")
            st.dataframe(show, use_container_width=True, hide_index=True)

# ---- Tab: Why a score (criteria breakdown) ----
with tab_break:
    if not bucket_scores:
        st.info("Add projects and assign aims first.")
    else:
        st.caption("How each criterion contributed to a project's score.")
        a = st.selectbox("Aim", list(bucket_scores.keys()), key="bd_aim")
        adf = bucket_scores[a]
        p = st.selectbox("Project", adf["Project"].tolist(), key="bd_proj")
        eff = bucket_eff[a]
        idx = adf.index[adf["Project"] == p][0]
        parts = []
        for c in CRITERIA:
            nv = normalize_column(adf[c["key"]], c["direction"])[idx]
            parts.append({"Criterion": c["label"], "Contribution": nv * eff[c["key"]],
                          "Normalized": nv, "Weight": eff[c["key"]]})
        pdf = pd.DataFrame(parts).sort_values("Contribution")
        fig = go.Figure(go.Bar(
            x=pdf["Contribution"], y=pdf["Criterion"], orientation="h",
            marker_color=PURPLE,
            customdata=pdf[["Normalized", "Weight"]].values,
            hovertemplate="%{y}<br>contribution %{x:.3f}"
                          "<br>normalized %{customdata[0]:.2f} \u00d7 weight %{customdata[1]:.0%}<extra></extra>",
        ))
        fig.update_layout(**PLOTLY_LAYOUT, height=90 + 42 * len(pdf))
        fig.update_xaxes(title="Weighted contribution to score")
        fig.update_yaxes(automargin=True, title=None)
        st.plotly_chart(fig, use_container_width=True, key="breakdown")
        score = adf.loc[idx, "Score"]
        st.caption(f"Contributions sum to {p}'s score of {score:.3f}. A criterion "
                   "contributes more when the project scores well on it and that "
                   "criterion carries weight in this aim.")

# ---- Tab: Cost vs score ----
with tab_scatter:
    if not bucket_scores:
        st.info("Add projects and assign aims first.")
    else:
        st.caption("Top-left is the sweet spot: high score, low cost. Within one aim "
                   "so scores stay comparable.")
        a = st.selectbox("Aim", list(bucket_scores.keys()), key="sc_aim")
        sdf = bucket_scores[a]
        fig = go.Figure(go.Scatter(
            x=sdf["cost"], y=sdf["Score"], mode="markers+text",
            marker=dict(size=16, color=CORAL, line=dict(width=1, color=GREEN_D)),
            text=sdf["Project"], textposition="top center", textfont=dict(size=11, color=MUTED),
            hovertemplate="%{text}<br>cost $%{x:,.0f}<br>score %{y:.3f}<extra></extra>",
        ))
        fig.update_layout(**PLOTLY_LAYOUT, height=420)
        fig.update_xaxes(title="Estimated cost (USD)")
        fig.update_yaxes(title="Score (within this aim)", range=[0, 1.08])
        st.plotly_chart(fig, use_container_width=True, key="scatter")

# ---- Tab: Budget ----
with tab_budget:
    if not bucket_scores:
        st.info("Add projects and assign aims first.")
    else:
        st.caption("Set a total budget and how it splits across aims. Shares are hard "
                   "targets \u2014 money does not move across aims automatically (aims are "
                   "not comparable). Unused money is flagged so you can rebalance.")
        total_budget = st.number_input("Total budget (USD)", min_value=0, value=1500000, step=50000)
        present = list(bucket_scores.keys())
        st.markdown("**Share per aim (%)** \u2014 normalized to 100%.")
        scol = st.columns(len(present))
        raw_shares = {a: scol[i].number_input(a, 0, 100, round(100/len(present)), 5, key=f"share_{a}")
                      for i, a in enumerate(present)}
        stot = sum(raw_shares.values())

        if stot == 0:
            st.warning("Set at least one aim's share above zero.")
        else:
            rows, committed_total, rebalance = [], 0.0, []
            for a in present:
                ab = total_budget * raw_shares[a] / stot
                chosen, spent = greedy_select(bucket_scores[a], ab)
                strand = ab - spent
                committed_total += spent
                rows.append({"Aim": a, "Committed": spent, "Unused": strand})
                unfunded = bucket_scores[a][~bucket_scores[a]["Project"].isin(set(chosen))]
                if chosen:
                    msg = f"**{a}** \u2014 target ${ab:,.0f}, committed ${spent:,.0f}: {', '.join(chosen)}"
                else:
                    msg = f"**{a}** \u2014 target ${ab:,.0f}, committed $0"
                if strand > 0.5 and len(unfunded) > 0:
                    msg += (f".  \n_Strands ${strand:,.0f}: cheapest unfunded project here "
                            f"costs ${unfunded['cost'].min():,.0f}, more than the ${strand:,.0f} left._")
                    rebalance.append(a); st.warning(msg)
                elif strand > 0.5:
                    msg += f".  \n_Surplus ${strand:,.0f}: share covers every project here. Consider lowering it._"
                    rebalance.append(a); st.info(msg)
                else:
                    st.success(msg)

            unspent = total_budget - committed_total
            kc1, kc2, kc3 = st.columns(3)
            kpi_card(kc1, "Committed", f"${committed_total:,.0f}")
            kpi_card(kc2, "Total budget", f"${total_budget:,.0f}")
            kpi_card(kc3, "Unallocated", f"${unspent:,.0f}",
                     sub=("shares don't fit costs" if unspent > 0.5 else "fully allocated"),
                     sub_color=(CORAL if unspent > 0.5 else GREEN))

            bud = pd.DataFrame(rows)
            fig = go.Figure()
            fig.add_bar(y=bud["Aim"], x=bud["Committed"], name="Committed",
                        orientation="h", marker_color=GREEN,
                        hovertemplate="%{y}<br>committed $%{x:,.0f}<extra></extra>")
            fig.add_bar(y=bud["Aim"], x=bud["Unused"], name="Unused",
                        orientation="h", marker_color=GREY,
                        hovertemplate="%{y}<br>unused $%{x:,.0f}<extra></extra>")
            fig.update_layout(**PLOTLY_LAYOUT, barmode="stack",
                              height=90 + 50 * len(bud),
                              legend=dict(orientation="h", y=1.12, x=0))
            fig.update_xaxes(title="USD")
            fig.update_yaxes(automargin=True, title=None)
            st.plotly_chart(fig, use_container_width=True, key="budget")

            if rebalance and unspent > 0.5:
                st.warning(
                    f"\u2248${unspent:,.0f} is unallocated because per-aim shares don't fit "
                    f"project costs in: {', '.join(rebalance)}. Adjust shares to use more of "
                    f"the budget. Money is not moved across aims automatically \u2014 a "
                    f"deliberate choice, since aims are not comparable on one scale."
                )
