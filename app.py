"""
Capisight v3 - CapEx prioritization prototype (Streamlit interface).

All calculations live in core.py (unit-tested). This file only draws the interface.

Run:   pip install -r requirements.txt
       streamlit run app.py

What this is: a decision-SUPPORT prototype for screening and comparing capital projects.
What it is not: a valuation model, or a system of record. Read the "About & limits" tab.
"""
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import core
from core import AIMS, CRIT_KEYS, CRITERIA, DEFAULT_AIM_WEIGHTS

BASE = os.path.dirname(os.path.abspath(__file__))
DEMO_PATH = os.path.join(BASE, "data", "demo_projects.csv")
CASES_DIR = os.path.join(BASE, "data", "business_cases")
MAX_CHARS = 30000

BLUE, GREEN, AMBER, RED, GREY = "#1B6EF3", "#16A34A", "#D97706", "#DC2626", "#9CA3AF"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _call(fn, *args, **kw):
    """Streamlit renamed use_container_width to width='stretch'. Try the new form, fall back."""
    try:
        return fn(*args, width="stretch", **kw)
    except Exception:  # noqa: BLE001
        return fn(*args, use_container_width=True, **kw)


def usd(x) -> str:
    return "n/a" if x is None or pd.isna(x) else f"${x:,.0f}"


def get_setting(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, None)
    except Exception:  # noqa: BLE001  (no secrets file)
        value = None
    return str(value or os.environ.get(name, default) or "")


def plot_layout(height: int) -> dict:
    return dict(height=height, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#FAFAFA", font=dict(size=12))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def init_state():
    ss = st.session_state
    if "projects" not in ss:
        demo = core.load_demo_projects(DEMO_PATH)
        ss["projects"], ss["projects_base"], ss["editor_version"] = demo, demo, 0
    ss.setdefault("extraction", None)
    ss.setdefault("extraction_id", 0)
    ss.setdefault("bench_results", None)
    for aim in AIMS:
        for k in CRIT_KEYS:
            ss.setdefault(f"w_{aim}_{k}", DEFAULT_AIM_WEIGHTS[aim][k])


def set_portfolio(df: pd.DataFrame):
    """Replace the portfolio and reset the table editor (new widget key = clean edit state)."""
    ss = st.session_state
    df = core.normalize_projects(df)
    ss["projects"], ss["projects_base"] = df, df
    ss["editor_version"] = ss.get("editor_version", 0) + 1


def load_demo():
    set_portfolio(core.load_demo_projects(DEMO_PATH))


def clear_portfolio():
    set_portfolio(pd.DataFrame(columns=core.PROJECT_COLUMNS))


def reset_weights(aim: str):
    for k in CRIT_KEYS:
        st.session_state[f"w_{aim}_{k}"] = DEFAULT_AIM_WEIGHTS[aim][k]


def aim_weights(aim: str) -> dict:
    return {k: st.session_state[f"w_{aim}_{k}"] for k in CRIT_KEYS}


# ---------------------------------------------------------------------------
# LLM configuration (sidebar)
# ---------------------------------------------------------------------------
def sidebar() -> tuple:
    """Draws the sidebar. Returns (llm_fn or None, status message)."""
    sb = st.sidebar
    sb.title("Capisight")
    sb.caption("CapEx prioritization prototype")
    sb.divider()
    sb.markdown("**Scoring weights by aim**")
    aim = sb.selectbox("Aim to configure", AIMS)
    if aim == core.MANDATORY_AIM:
        sb.info("Regulatory projects are usually mandatory. Scores help order them, not decide whether to fund them.")
    for c in CRITERIA:
        arrow = "higher is better" if c["direction"] == "higher" else "lower is better"
        sb.slider(f"{c['label']} ({arrow})", 0, 40, key=f"w_{aim}_{c['key']}")
    sb.button("Reset weights for this aim", on_click=reset_weights, args=(aim,))
    sb.caption("Default weights are a starting hypothesis, not a sourced prescription. Change them to match your policy.")
    sb.divider()

    sb.markdown("**AI extraction**")
    keys = {"groq": get_setting("GROQ_API_KEY"), "anthropic": get_setting("ANTHROPIC_API_KEY")}
    available = [p for p, k in keys.items() if k]
    if not available:
        sb.caption("No API key found. Add GROQ_API_KEY or ANTHROPIC_API_KEY to Streamlit secrets to enable it. Everything else works without one.")
        return None, "No API key configured."
    preferred = get_setting("LLM_PROVIDER").lower()
    default_idx = available.index(preferred) if preferred in available else 0
    provider = sb.selectbox("Provider", available, index=default_idx)
    default_model = (get_setting("GROQ_MODEL", core.DEFAULT_GROQ_MODEL) if provider == "groq"
                     else get_setting("ANTHROPIC_MODEL", core.DEFAULT_ANTHROPIC_MODEL))
    model = sb.text_input("Model", value=default_model, key=f"model_{provider}",
                          help="Providers retire model names. If extraction fails with a model error, update this.")
    sb.caption("Do not upload confidential documents. Text is sent to the provider you select.")
    try:
        return core.make_llm_fn(provider, keys[provider], model), f"{provider} / {model}"
    except Exception as exc:  # noqa: BLE001
        return None, f"Could not start {provider}: {exc}"


# ---------------------------------------------------------------------------
# Rankings (shared by several tabs)
# ---------------------------------------------------------------------------
def compute_rankings():
    projects = core.add_consistency_columns(st.session_state["projects"])
    complete, incomplete = core.split_complete(projects)
    scored_by_aim, eff_by_aim = {}, {}
    for aim in AIMS:
        bucket = complete[complete["Aim"] == aim]
        if bucket.empty:
            continue
        w = aim_weights(aim)
        scored_by_aim[aim], eff_by_aim[aim] = core.score_aim(bucket, w)
    return projects, scored_by_aim, eff_by_aim, incomplete


# ---------------------------------------------------------------------------
# Tab: Portfolio
# ---------------------------------------------------------------------------
def tab_portfolio():
    ss = st.session_state
    st.markdown("Edit any cell, add rows, or delete rows. **Blank numeric cells stay blank**: a project with a missing value is "
                "left out of rankings and listed as incomplete, instead of being scored as if the value were zero.")
    c1, c2, c3 = st.columns(3)
    c1.button("Load demo portfolio", on_click=load_demo, help="12 synthetic projects. Two are deliberately inconsistent.")
    c2.button("Start empty", on_click=clear_portfolio)
    up = c3.file_uploader("Import projects (CSV)", type=["csv"], key="csv_import")
    if up is not None and st.button("Replace portfolio with this CSV"):
        try:
            set_portfolio(pd.read_csv(up))
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not import: {exc}")

    cfg = {
        "Aim": st.column_config.SelectboxColumn("Aim", options=AIMS, required=True),
        "cost": st.column_config.NumberColumn("Cost (USD)", format="%.0f"),
        "npv": st.column_config.NumberColumn("Stated NPV (USD)", format="%.0f"),
        "roi": st.column_config.NumberColumn("ROI (%)", format="%.1f"),
        "payback": st.column_config.NumberColumn("Payback (yrs)", format="%.1f"),
        "discount_rate_pct": st.column_config.NumberColumn("Discount rate (%)", format="%.1f"),
        "useful_life_yrs": st.column_config.NumberColumn("Useful life (yrs)", format="%.0f"),
        "throughput": st.column_config.NumberColumn("Throughput (%)", format="%.0f"),
        "assumptions": st.column_config.TextColumn("Key assumptions", width="large"),
        "scores_reviewed": st.column_config.CheckboxColumn("Scores reviewed", help="Tick when a person has set strategic/operational/risk scores."),
    }
    edited = _call(st.data_editor, ss["projects_base"], num_rows="dynamic", column_config=cfg,
                   key=f"editor_{ss['editor_version']}")
    ss["projects"] = core.normalize_projects(edited)
    projects_checked = core.add_consistency_columns(ss["projects"])

    st.markdown("#### Consistency check")
    st.caption("Compares each stated NPV with the NPV implied by its own payback, discount rate and useful life "
               "(uniform year-end cash flows). Large gaps usually mean one of the figures is wrong or uses a different basis.")
    counts = projects_checked["check"].value_counts()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Consistent", int(counts.get("Consistent", 0)))
    k2.metric("Review", int(counts.get("Review", 0)))
    k3.metric("Inconsistent", int(counts.get("Inconsistent", 0)))
    k4.metric("Not checkable", int(counts.get("Not checkable", 0)))
    view = projects_checked[["Project", "Aim", "cost", "npv", "implied_npv", "npv_gap", "check"]].rename(columns={
        "cost": "Cost", "npv": "Stated NPV", "implied_npv": "Implied NPV", "npv_gap": "Stated minus implied", "check": "Check"})
    _call(st.dataframe, view.round(0), hide_index=True)
    st.download_button("Download portfolio (CSV)", ss["projects"].to_csv(index=False).encode("utf-8"), "capisight_portfolio.csv", "text/csv")


# ---------------------------------------------------------------------------
# Tab: Rankings
# ---------------------------------------------------------------------------
def tab_rankings(scored_by_aim: dict, eff_by_aim: dict, incomplete: pd.DataFrame):
    st.caption("Scores compare projects only within an aim, using min-max scaling inside that group. "
               "They are relative, so they cannot be compared across aims or across different portfolios.")
    if len(incomplete):
        st.warning(f"{len(incomplete)} project(s) are not ranked because an aim or a scoring value is missing: "
                   + ", ".join(incomplete["Project"].astype(str)))
    if not scored_by_aim:
        st.info("Add projects with an aim and all scoring values to see rankings.")
        return
    for aim, scored in scored_by_aim.items():
        n = len(scored)
        st.markdown(f"#### {aim}  ·  {n} project{'s' if n != 1 else ''}")
        if n < 4:
            st.warning(f"Only {n} project(s) in this aim. Min-max scoring exaggerates small differences with so few projects; "
                       "read the raw values, not just the score.")
        unreviewed = scored.loc[~scored["scores_reviewed"], "Project"].tolist()
        if unreviewed:
            st.warning("Strategic, operational and risk scores have not been reviewed by a person for: " + ", ".join(unreviewed))
        flagged = scored.loc[scored["check"].isin(["Inconsistent"]), "Project"].tolist()
        if flagged:
            st.error("Stated NPV conflicts with the project's own payback/rate/life for: " + ", ".join(flagged)
                     + ". Their NPV-driven scores may be unreliable.")
        s = scored.sort_values("Score")
        fig = go.Figure(go.Bar(x=s["Score"], y=s["Project"], orientation="h", marker_color=BLUE,
                               text=[f"{v:.3f}" for v in s["Score"]], textposition="outside"))
        fig.update_layout(**plot_layout(90 + 44 * n))
        fig.update_xaxes(range=[0, 1.12], title="Score (0-1, within this aim)")
        _call(st.plotly_chart, fig, key=f"rank_{aim}")
        show = scored[["Rank", "Project", "Score"] + CRIT_KEYS + ["check", "scores_reviewed"]].copy()
        show["Score"] = show["Score"].round(3)
        with st.expander(f"Table and score breakdown: {aim}"):
            _call(st.dataframe, show, hide_index=True)
            pick = st.selectbox("Explain the score for", scored["Project"].tolist(), key=f"bd_{aim}")
            bd = core.score_breakdown(scored, pick, eff_by_aim[aim])
            fig2 = go.Figure(go.Bar(x=bd["Contribution"], y=bd["Criterion"], orientation="h", marker_color=BLUE))
            fig2.update_layout(**plot_layout(60 + 40 * len(bd)))
            fig2.update_xaxes(title="Weighted contribution to score")
            _call(st.plotly_chart, fig2, key=f"bdchart_{aim}")


# ---------------------------------------------------------------------------
# Tab: Stress test
# ---------------------------------------------------------------------------
def tab_stress(projects_checked: pd.DataFrame):
    usable = projects_checked[(projects_checked["cost"] > 0) & (projects_checked["payback"] > 0)]
    if usable.empty:
        st.info("Add a project with cost and payback to stress-test it.")
        return
    name = st.selectbox("Project", usable["Project"].tolist(), key="stress_pick")
    row = usable[usable["Project"] == name].iloc[0]
    left, right = st.columns([1, 2])
    with left:
        rate_default = float(row["discount_rate_pct"]) if pd.notna(row["discount_rate_pct"]) else 10.0
        life_default = int(round(row["useful_life_yrs"])) if pd.notna(row["useful_life_yrs"]) else 5
        rate = st.number_input("Discount rate (%)", 0.1, 50.0, min(max(rate_default, 0.1), 50.0), 0.5, key=f"s_rate_{name}")
        life = st.number_input("Useful life (years)", 1, 40, min(max(life_default, 1), 40), key=f"s_life_{name}")
        over = st.slider("Cost overrun scenario (%)", 5, 60, 20, 5)
        cut = st.slider("Savings reduction scenario (%)", 5, 70, 30, 5)
        st.markdown(f"**Cost** {usd(row['cost'])}  \n**Stated payback** {row['payback']:.1f} yrs  \n**Annual cash flow (cost / payback)** {usd(row['cost'] / row['payback'])}")
    with right:
        chk = core.consistency_check(row["cost"], row["npv"], row["payback"], rate, life)
        if chk["status"] == "Consistent":
            st.success(f"Stated NPV {usd(row['npv'])} agrees with the model ({usd(chk['implied_npv'])}).")
        elif chk["status"] in ("Review", "Inconsistent"):
            (st.warning if chk["status"] == "Review" else st.error)(f"Stated NPV {usd(row['npv'])} vs model-implied {usd(chk['implied_npv'])} "
                     f"(gap {usd(chk['gap'])}, {chk['gap_pct_of_cost']:.0f}% of cost). Sensitivity below uses the MODEL, "
                     "not the stated NPV, so it shows what the project's own payback, rate and life support.")
        else:
            st.info(chk["note"])
        if chk.get("note") and chk["status"] != "Not checkable":
            st.warning(chk["note"])
        sc = core.scenario_table(row["cost"], row["payback"], rate, life, over, cut)
        show = sc.copy()
        for c in ("Capital cost", "Annual cash flow", "NPV"):
            show[c] = show[c].map(usd)
        for c in ("Rate %", "IRR %", "Simple payback (yrs)", "Discounted payback (yrs)"):
            show[c] = show[c].map(lambda v: "none" if v is None or pd.isna(v) else f"{v:.1f}")
        _call(st.dataframe, show, hide_index=True)
        be = core.breakeven_savings_cut(row["cost"], row["payback"], rate, life)
        if be > 0:
            st.metric("Break-even: savings can fall by", f"{be:.0f}%", help="Annual savings reduction at which NPV reaches zero.")
        else:
            st.metric("Break-even", "already below zero", help="NPV is negative under the model even with no savings reduction.")
        t = core.tornado_table(row["cost"], row["payback"], rate, life)
        base = t["Base NPV"].iloc[0]
        fig = go.Figure()
        fig.add_bar(y=t["Variable"], x=t["NPV (low case)"] - base, orientation="h", name="Low case", marker_color=RED)
        fig.add_bar(y=t["Variable"], x=t["NPV (high case)"] - base, orientation="h", name="High case", marker_color=GREEN)
        fig.update_layout(**plot_layout(260), barmode="overlay")
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title=f"Change in NPV vs base ({usd(base)})")
        _call(st.plotly_chart, fig, key="tornado")
        st.caption("Uniform year-end cash flows; annual cash flow = cost / payback. Tornado swings: rate +/-2 pp, savings +/-20%, cost +/-20%, life +/-1 year.")


# ---------------------------------------------------------------------------
# Tab: Budget
# ---------------------------------------------------------------------------
def tab_budget(scored_by_aim: dict):
    if not scored_by_aim:
        st.info("Add rankable projects first.")
        return
    c1, c2, c3 = st.columns(3)
    total = c1.number_input("Total budget (USD)", 0, 100_000_000, 1_500_000, 50_000)
    mandatory = c2.toggle("Fund regulatory / safety projects first", value=True,
                          help="Treats them as non-discretionary and funds them off the top.")
    method = c3.radio("Selection method", ["optimal", "greedy"], horizontal=True,
                      help="Optimal solves the 0/1 knapsack exactly. Greedy funds by rank until money runs out.")
    flexible = [a for a in scored_by_aim if not (mandatory and a == core.MANDATORY_AIM)]
    shares = {}
    if flexible:
        st.markdown("**Share of the remaining budget per aim (%)** (normalized to 100%)")
        cols = st.columns(len(flexible))
        for col, a in zip(cols, flexible):
            shares[a] = col.number_input(a, 0, 100, round(100 / len(flexible)), 5, key=f"share_{a}")
    out, meta = core.allocate_budget(scored_by_aim, total, shares, mandatory, method)
    if meta["mandatory_shortfall"] > 0:
        st.error(f"Mandatory projects cost {usd(meta['mandatory_shortfall'])} more than the total budget. Nothing is left for other aims.")
    rows = []
    for aim, v in out.items():
        rows.append({"Aim": aim, "Budget": v["budget"], "Spent": v["spent"], "Unused": v["unused"],
                     "Funded": ", ".join(v["funded"]) or "none",
                     "Score captured": round(v["selected_score"], 3),
                     "Greedy score": round(v["greedy_score"], 3), "Optimal score": round(v["optimal_score"], 3)})
    table = pd.DataFrame(rows)
    k1, k2, k3 = st.columns(3)
    k1.metric("Committed", usd(table["Spent"].sum()))
    k2.metric("Total budget", usd(total))
    k3.metric("Unallocated", usd(total - table["Spent"].sum()))
    fig = go.Figure()
    fig.add_bar(y=table["Aim"], x=table["Spent"], orientation="h", name="Spent", marker_color=BLUE)
    fig.add_bar(y=table["Aim"], x=table["Unused"], orientation="h", name="Unused", marker_color="#E5E7EB")
    fig.update_layout(**plot_layout(100 + 50 * len(table)), barmode="stack")
    _call(st.plotly_chart, fig, key="budget_chart")
    _call(st.dataframe, table.assign(Budget=table["Budget"].map(usd), Spent=table["Spent"].map(usd), Unused=table["Unused"].map(usd)), hide_index=True)
    gaps = [(a, v["optimal_score"] - v["greedy_score"]) for a, v in out.items() if v["mode"] != "mandatory"]
    better = [g for g in gaps if g[1] > 1e-9]
    if better:
        st.info("Exact optimization beats greedy-by-rank in: " + ", ".join(f"{a} (+{g:.3f} score)" for a, g in better))
    st.caption("Objective: maximize the sum of within-aim scores. Money never moves between aims automatically, because aims are scored on different criteria. "
               "Costs are rounded up to the next $1,000 inside the optimizer, so selections never exceed budget.")


# ---------------------------------------------------------------------------
# Tab: Ingest (AI)
# ---------------------------------------------------------------------------
STATUS_TEXT = {
    "verified": ("✅", "Quote found in the document and contains this number"),
    "absent": ("➖", "Not stated in the document"),
    "no_evidence": ("⚠️", "No supporting quote given. Check by hand"),
    "quote_not_found": ("❌", "The quote is NOT in the document. Likely invented. Check by hand"),
    "number_mismatch": ("❌", "The quote does not contain this number. Check by hand"),
    "sign_mismatch": ("⚠️", "Number matches but the sign differs. Check by hand"),
    "unverifiable": ("⚠️", "Quote has no digits (for example spelled-out numbers). Check by hand"),
}
FIELD_LABELS = {"cost": "Cost (USD)", "npv": "NPV (USD)", "roi": "ROI (%)", "payback": "Payback (years)",
                "discount_rate_pct": "Discount rate (%)", "useful_life_yrs": "Useful life (years)"}


def tab_ingest(llm_fn, llm_status: str):
    ss = st.session_state
    st.info("AI reads a business case and proposes figures, each with a quote from the document. A figure marked ✅ means the quote really "
            "appears in the file and contains the number. It does not prove the number is the right one. Review everything. "
            "Do not upload confidential documents: the text is sent to the AI provider.")
    st.caption(f"AI provider: {llm_status}")
    up = st.file_uploader("Business case (PDF, Excel, Word, CSV, TXT)", type=["pdf", "xlsx", "xls", "csv", "docx", "txt"], key="doc_upload")
    if up is not None:
        text, warns = core.read_document(up.name, up.getvalue())
        for w in warns:
            st.warning(w)
        if text.strip():
            st.caption(f"Read {len(text):,} characters from {up.name}.")
            if len(text) > MAX_CHARS:
                st.warning(f"The document is longer than the {MAX_CHARS:,}-character limit. Only the first {MAX_CHARS:,} characters "
                           f"will be read; {len(text) - MAX_CHARS:,} characters will be ignored.")
            with st.expander("Preview the text the AI will see"):
                st.code(text[:1500])
            if st.button("Extract with AI", type="primary"):
                if llm_fn is None:
                    st.error("AI extraction is not configured. Add an API key to Streamlit secrets (see the sidebar).")
                else:
                    with st.spinner("Reading the document..."):
                        ss["extraction"] = core.extract_project(text, llm_fn, MAX_CHARS)
                        ss["extraction_id"] += 1

    res = ss["extraction"]
    if not res:
        return
    if not res.get("ok"):
        st.error(res["error"])
        return
    if res.get("truncated"):
        st.warning(f"Only the first {res['chars_read']:,} of {res['chars_total']:,} characters were read.")
    eid = ss["extraction_id"]
    st.markdown("#### Review and confirm")
    name = st.text_input("Project name", value=res["project_name"], key=f"ex_name_{eid}")
    aim_idx = AIMS.index(res["suggested_aim"]) if res["suggested_aim"] in AIMS else 0
    aim = st.selectbox("Aim (AI suggestion, please confirm)", AIMS, index=aim_idx, key=f"ex_aim_{eid}")
    values = {}
    for key, label in FIELD_LABELS.items():
        f = res["fields"][key]
        icon, meaning = STATUS_TEXT.get(f["status"], ("⚠️", f["status"]))
        c1, c2 = st.columns([1, 3])
        shown = "" if f["value"] is None else f"{f['value']:g}"
        values[key] = c1.text_input(label, value=shown, key=f"ex_{key}_{eid}")
        c2.markdown(f"{icon} {meaning}")
        if f["evidence"]:
            c2.caption(f"Quote: \"{f['evidence']}\"")
    st.markdown("**Scores below are NOT extracted. Set them yourself.**")
    s1, s2, s3, s4 = st.columns(4)
    strategic = s1.slider("Strategic (1-10)", 1, 10, 5, key=f"ex_s_{eid}")
    operational = s2.slider("Operational (1-10)", 1, 10, 5, key=f"ex_o_{eid}")
    risk = s3.slider("Risk (1-10, 10 = riskiest)", 1, 10, 5, key=f"ex_r_{eid}")
    throughput = s4.number_input("Throughput (%)", 0.0, 500.0, 0.0, key=f"ex_t_{eid}")
    reviewed = st.checkbox("I have reviewed these figures and scores", key=f"ex_rev_{eid}")
    if st.button("Add to portfolio"):
        row = {"Project": name or "Unnamed project", "Aim": aim, "strategic": strategic, "operational": operational,
               "risk": risk, "throughput": throughput, "assumptions": "", "source": "AI-assisted (human reviewed)" if reviewed else "AI-assisted (NOT reviewed)",
               "scores_reviewed": reviewed}
        for key in FIELD_LABELS:
            row[key] = core.parse_number(values[key])
        new = core.normalize_projects(pd.DataFrame([row]))
        set_portfolio(pd.concat([ss["projects"], new], ignore_index=True))
        ss["extraction"] = None
        st.success("Added. Open the Portfolio tab to see it and its consistency check.")
        st.rerun()


# ---------------------------------------------------------------------------
# Tab: Extraction benchmark
# ---------------------------------------------------------------------------
def load_benchmark_files():
    truth = pd.read_csv(os.path.join(CASES_DIR, "ground_truth.csv"))
    cases = {}
    for fname in sorted(os.listdir(CASES_DIR)):
        if fname.endswith(".txt"):
            with open(os.path.join(CASES_DIR, fname), encoding="utf-8") as fh:
                cases[fname[:-4]] = fh.read()
    return truth, cases


def tab_benchmark(llm_fn, llm_status: str):
    ss = st.session_state
    truth, cases = load_benchmark_files()
    st.markdown("Ten synthetic business cases with hand-labelled answers: different layouts, units, distractor numbers, scenarios, "
                "negative NPVs, spelled-out numbers, and one document with almost no figures. Run your configured AI model on all ten "
                "and see how often it is right, how often it invents figures, and whether the ✅ check catches mistakes.")
    st.caption(f"AI provider: {llm_status}")
    if st.button("Run extraction benchmark", type="primary"):
        if llm_fn is None:
            st.error("AI extraction is not configured. Add an API key to Streamlit secrets.")
        else:
            with st.spinner("Running 10 documents..."):
                ss["bench_results"] = core.run_benchmark(cases, llm_fn)
    results = ss["bench_results"]
    if results:
        detail, s = core.evaluate_extraction(results, truth)
        if s.get("cases_failed"):
            st.warning(f"{s['cases_failed']} document(s) failed to run. Example error: "
                       + next((r["error"] for r in results.values() if not r.get("ok")), ""))
        if s.get("fields_scored"):
            k = st.columns(4)
            k[0].metric("Field accuracy", f"{s['accuracy']:.0%}")
            k[1].metric("Invented figures", s["hallucinated"], help="Model gave a number where the document has none.")
            k[2].metric("Missed figures", s["missed"])
            k[3].metric("Wrong figures", s["wrong"])
            k2 = st.columns(3)
            k2[0].metric("Marked ✅ but wrong", s["verified_wrong"], help="The mistakes a hurried reviewer would trust. Lower is better; this is the number to watch.")
            k2[1].metric("Precision when marked ✅", "n/a" if s["verified_precision"] is None else f"{s['verified_precision']:.0%}")
            k2[2].metric("Aim suggestion accuracy", "n/a" if s["aim_accuracy"] is None else f"{s['aim_accuracy']:.0%}")
            _call(st.dataframe, detail, hide_index=True)
            st.caption(f"Model: {llm_status}. Record these numbers, the model name and the date in your README: results change by model.")
    else:
        st.info("Not run yet.")
    with st.expander("See the test documents and answer key"):
        pick = st.selectbox("Document", list(cases.keys()), key="bench_pick")
        st.code(cases[pick])
        _call(st.dataframe, truth[truth["case_id"] == pick], hide_index=True)


# ---------------------------------------------------------------------------
# Tab: Site deal
# ---------------------------------------------------------------------------
def tab_site():
    st.warning("Illustrative structure only. Every default below is a PLACEHOLDER, not market data. "
               "Replace them with sourced assumptions before drawing any conclusion.")
    st.caption("Public tower-company filings give reference points for escalators and tenancy (for example, tenant lease escalators "
               "around 3-4% a year and ground lease escalators around 2-3% in an older SBA Communications 10-K; "
               "pull the latest filings and cite the year). Build cost and rent levels vary widely by market; source your own.")
    a, b, c = st.columns(3)
    capex = a.number_input("Build cost (USD) [placeholder]", 10_000, 5_000_000, 250_000, 10_000)
    years = a.number_input("Analysis horizon (years)", 5, 40, 20)
    rate = a.number_input("Discount rate (%)", 1.0, 30.0, 8.0, 0.5, key="site_rate")
    rent = b.number_input("Anchor tenant rent (USD/month) [placeholder]", 100, 20_000, 2_000, 100)
    esc = b.number_input("Tenant rent escalator (%/yr)", 0.0, 10.0, 3.0, 0.25)
    coloc = b.slider("Added tenant pays (% of anchor rent)", 20, 100, 80, 5) / 100
    t2 = c.number_input("Tenant 2 joins in year (0 = never)", 0, 40, 3)
    t3 = c.number_input("Tenant 3 joins in year (0 = never)", 0, 40, 0)
    ground = c.number_input("Ground lease (USD/month) [placeholder]", 0, 10_000, 600, 50)
    gesc = c.number_input("Ground lease escalator (%/yr)", 0.0, 10.0, 2.0, 0.25)
    opex = a.number_input("Opex year 1 (USD) [placeholder]", 0, 200_000, 12_000, 500)
    oesc = b.number_input("Opex escalator (%/yr)", 0.0, 10.0, 3.0, 0.25)
    tv = c.number_input("Terminal value (x final-year NOI, 0 = none)", 0.0, 30.0, 0.0, 0.5)
    df, m = core.site_deal(capex, years, rent, t2, t3, coloc, esc, ground, gesc, opex, oesc, rate, tv)
    k = st.columns(5)
    k[0].metric("NPV", usd(m["npv"]))
    k[1].metric("IRR", "n/a" if m["irr_pct"] is None else f"{m['irr_pct']:.1f}%")
    k[2].metric("Simple payback", "beyond horizon" if m["simple_payback"] is None else f"{m['simple_payback']:.1f} yrs")
    k[3].metric("Year-1 NOI yield", "n/a" if m["year1_yield_pct"] is None else f"{m['year1_yield_pct']:.1f}%")
    k[4].metric("Peak tenants", m["peak_tenants"])
    fig = go.Figure()
    fig.add_bar(x=df["Year"], y=df["NOI"], name="NOI", marker_color=BLUE)
    fig.add_scatter(x=df["Year"], y=df["Cumulative"], name="Cumulative cash", line=dict(color=AMBER))
    fig.update_layout(**plot_layout(320))
    _call(st.plotly_chart, fig, key="site_chart")
    st.markdown("**NPV sensitivity: anchor rent vs. when tenant 2 joins**")
    grid = {}
    for mult in (0.8, 1.0, 1.2):
        grid[f"Rent x{mult:.1f}"] = {("never" if y == 0 else f"year {y}"): core.site_deal(capex, years, rent * mult, y, t3, coloc, esc, ground, gesc, opex, oesc, rate, tv)[1]["npv"]
                                     for y in (0, 2, 4, 6)}
    _call(st.dataframe, pd.DataFrame(grid).T.map(usd) if hasattr(pd.DataFrame, "map") else pd.DataFrame(grid).T.applymap(usd))
    with st.expander("Year-by-year cash flows"):
        _call(st.dataframe, df.round(0), hide_index=True)

    st.divider()
    st.markdown("### Pole to macro conversion: how many added tenants does it take?")
    x, y, z = st.columns(3)
    ccap = x.number_input("Conversion capex (USD) [placeholder]", 10_000, 3_000_000, 180_000, 10_000)
    crent = y.number_input("Rent per added tenant (USD/month) [placeholder]", 100, 20_000, 1_800, 100)
    cterm = z.number_input("Term (years)", 5, 40, 15)
    copex = x.number_input("Added opex per tenant (USD/yr)", 0, 100_000, 1_000, 500)
    cesc = y.number_input("Escalator (%/yr)", 0.0, 10.0, 3.0, 0.25, key="c_esc")
    crate = z.number_input("Discount rate (%)", 1.0, 30.0, 8.0, 0.5, key="c_rate")
    exact, whole = core.breakeven_added_tenants(ccap, crent, cesc, crate, cterm, copex)
    if whole is None:
        st.error("At this rent and opex, an added tenant never covers its own costs. No tenant count breaks even.")
    else:
        st.metric("Break-even added tenants", f"{whole}", help=f"Exact: {exact:.2f}. NPV of the conversion alone reaches zero at this count.")
        st.caption("Break-even rent per month for 1, 2, 3 added tenants: " + ", ".join(
            f"{n} tenant(s): {usd(core.breakeven_rent(ccap, n, cesc, crate, cterm, copex))}" for n in (1, 2, 3)))


# ---------------------------------------------------------------------------
# Tab: About
# ---------------------------------------------------------------------------
def tab_about():
    st.markdown("""
### What this is
A prototype that helps a finance or operations analyst **screen and compare capital projects**, check whether a business case's own numbers agree,
stress-test them, and test an AI-assisted way to pull figures out of documents. It is built with AI-assisted development and is not a system of record.

### Method
- **Grouping by aim.** Projects are ranked only against others with the same aim (regulatory/safety, business-as-usual, new growth, improve performance),
  following McKinsey's advice to sort capex projects by aim to avoid apples-to-oranges comparisons ("Managing a moonshot", McKinsey).
- **Scoring.** Weighted sum of min-max-scaled criteria within each aim. Weights are editable starting hypotheses.
- **Consistency check.** Implied NPV = PV of (cost / payback) for the useful life at the stated discount rate, minus cost. Gap up to 10% of cost: Consistent; up to 25%: Review; beyond that or a sign flip: Inconsistent.
- **Stress tests.** Run on the same uniform cash-flow model, not anchored to the stated NPV, so a bad stated NPV cannot hide.
- **Budget.** Exact 0/1 knapsack per aim (costs rounded up to $1,000) compared with greedy-by-rank. Regulatory/safety can be funded first.
- **AI extraction.** The model must return a verbatim quote for every figure. The app checks the quote exists in the document and contains the number
  (with unit conversions such as months to years). Subjective scores are never extracted. Run the benchmark tab to measure accuracy for your chosen model.

### Limits you should know
- Uniform year-end cash flows; real projects have ramps, taxes, working capital and terminal values.
- Scores are relative within a small group. With few projects, small gaps look large.
- Verified means "quote found and contains the number", not "this is the right number".
- Demo data is synthetic. The site-deal and conversion inputs are placeholders.
- Model names change: AI providers retire models. Update the model name in the sidebar if extraction errors.
- Do not upload confidential documents to a third-party AI provider.
""")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Capisight | CapEx prioritization", page_icon="📊", layout="wide")
    init_state()
    llm_fn, llm_status = sidebar()

    st.title("Capisight")
    st.caption("CapEx prioritization prototype. Rank projects within aims, check the numbers agree, stress-test them, and allocate a budget.")

    tabs = st.tabs(["Portfolio", "Rankings", "Stress test", "Budget", "Ingest (AI)", "Extraction benchmark", "Site deal", "About & limits"])
    # The Portfolio tab edits the table first; compute everything else from its result.
    with tabs[0]:
        tab_portfolio()
    projects_checked, scored_by_aim, eff_by_aim, incomplete = compute_rankings()
    with tabs[1]:
        tab_rankings(scored_by_aim, eff_by_aim, incomplete)
    with tabs[2]:
        tab_stress(projects_checked)
    with tabs[3]:
        tab_budget(scored_by_aim)
    with tabs[4]:
        tab_ingest(llm_fn, llm_status)
    with tabs[5]:
        tab_benchmark(llm_fn, llm_status)
    with tabs[6]:
        tab_site()
    with tabs[7]:
        tab_about()
    st.divider()
    st.caption("Capisight is a prototype built by Rutwik Satish with AI-assisted development. Demo data is synthetic.")


if __name__ == "__main__":
    main()
