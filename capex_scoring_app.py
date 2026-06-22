"""
Capisight v2 - CAPEX Decision Intelligence Platform
=====================================================
Built by Rutwik Satish | MS Engineering Management, Northeastern University

WHAT'S NEW IN V2
  - AI document ingestion: upload a PDF or Excel business case and Claude/Groq
    extracts the financial data automatically, with source citations
  - Operational KPIs: throughput impact, cycle time, headcount, floor space
  - Assumption transparency: every extracted project shows the key assumptions
    the business case rests on
  - Sensitivity analysis: see what happens to NPV and payback if key assumptions
    shift (discount rate, demand growth, cost overrun)
  - Cleaner UI: lighter theme, better typography, clearer information hierarchy

WHY GROUP BY AIM
  McKinsey argues capital projects should be grouped by aim because different
  aims warrant different evaluation criteria. A mandatory safety project and a
  growth bet do not belong on the same ranked list.

HONESTY NOTES
  - Default weight profiles are a starting hypothesis, not a sourced prescription
  - AI extraction is a starting point; always verify extracted numbers
  - Sensitivity analysis uses standard DCF (Brealey, Myers & Allen Ch.5)
  - Assumes uniform cash flows across useful life — a simplification clearly disclosed
  - Sample data is illustrative, not validated

Run locally:
    pip install streamlit pandas plotly groq pypdf2 openpyxl anthropic
    streamlit run capisight_v2.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import io

st.set_page_config(
    page_title="Capisight | CapEx Decision Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Design tokens — clean light theme, professional finance tool aesthetic
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* Base */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"] {
    background-color: #F8F9FB !important;
    color: #1A1D23 !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E8EAF0 !important;
}
[data-testid="stSidebar"] * { color: #1A1D23 !important; }
[data-testid="stSidebar"] .stSelectbox label { color: #6B7280 !important; font-size: 12px !important; }

/* Headers */
h1,h2,h3,h4 { font-family: 'Inter', sans-serif !important; color: #1A1D23 !important; font-weight: 600 !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #E8EAF0 !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
[data-testid="stMetricValue"]  { color: #1A1D23 !important; font-weight: 600 !important; font-size: 1.5rem !important; font-family: 'IBM Plex Mono', monospace !important; }
[data-testid="stMetricLabel"]  { color: #6B7280 !important; font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.06em; }

/* Tabs */
[data-testid="stTabs"] button { color: #6B7280 !important; font-size: 0.85rem !important; font-weight: 500 !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #1B6EF3 !important; border-bottom: 2px solid #1B6EF3 !important; }

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #E8EAF0 !important; border-radius: 8px !important; background: #FFFFFF !important; }

/* Buttons */
[data-testid="stButton"] button {
    background: #1B6EF3 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    padding: 8px 18px !important;
}
[data-testid="stButton"] button:hover { background: #1558C0 !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: #FFFFFF !important;
    border: 2px dashed #CBD5E1 !important;
    border-radius: 10px !important;
    padding: 16px !important;
}

/* Expander */
[data-testid="stExpander"] { background: #FFFFFF !important; border: 1px solid #E8EAF0 !important; border-radius: 8px !important; }

/* Alerts */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* Sliders */
[data-testid="stSlider"] { padding: 4px 0 !important; }

hr { border-color: #E8EAF0 !important; }

/* Custom card */
.capex-card {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.capex-card-blue {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 12px;
}
.capex-card-green {
    background: #F0FDF4;
    border: 1px solid #BBF7D0;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.capex-card-amber {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.section-eyebrow {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6B7280;
    margin-bottom: 6px;
}
.assumption-pill {
    display: inline-block;
    background: #EFF6FF;
    color: #1D4ED8;
    border: 1px solid #BFDBFE;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 12px;
    margin: 2px 3px 2px 0;
}
.extracted-badge {
    display: inline-block;
    background: #F0FDF4;
    color: #166534;
    border: 1px solid #BBF7D0;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 500;
    margin-left: 8px;
    vertical-align: middle;
}
.manual-badge {
    display: inline-block;
    background: #F9FAFB;
    color: #6B7280;
    border: 1px solid #E5E7EB;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 500;
    margin-left: 8px;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Plotly theme — clean light
# ---------------------------------------------------------------------------
BLUE    = "#1B6EF3"
GREEN   = "#16A34A"
AMBER   = "#D97706"
RED     = "#DC2626"
PURPLE  = "#7C3AED"
GREY    = "#9CA3AF"
SLATE   = "#64748B"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#FAFAFA",
    font=dict(color="#374151", size=12, family="Inter"),
    margin=dict(l=10, r=10, t=16, b=10),
    xaxis=dict(gridcolor="#F3F4F6", linecolor="#E5E7EB", tickfont=dict(color="#6B7280")),
    yaxis=dict(gridcolor="#F3F4F6", linecolor="#E5E7EB", tickfont=dict(color="#6B7280")),
)

# ---------------------------------------------------------------------------
# Criteria, aims, weights
# ---------------------------------------------------------------------------
CRITERIA = [
    {"key": "npv",          "label": "NPV (USD)",                  "direction": "higher"},
    {"key": "roi",          "label": "ROI (%)",                    "direction": "higher"},
    {"key": "payback",      "label": "Payback period (years)",     "direction": "lower"},
    {"key": "strategic",    "label": "Strategic score (1-10)",     "direction": "higher"},
    {"key": "operational",  "label": "Operational impact (1-10)",  "direction": "higher"},
    {"key": "throughput",   "label": "Throughput improvement (%)", "direction": "higher"},
    {"key": "risk",         "label": "Risk score (1-10)",          "direction": "lower"},
    {"key": "cost",         "label": "Estimated cost (USD)",       "direction": "lower"},
]
CRIT_KEYS = [c["key"] for c in CRITERIA]
LABEL     = {c["key"]: c["label"] for c in CRITERIA}

AIMS = ["Regulatory / safety", "Business-as-usual", "New growth", "Improve performance"]

DEFAULT_AIM_WEIGHTS = {
    "Regulatory / safety":  {"npv": 5,  "roi": 5,  "payback": 5,  "strategic": 20, "operational": 10, "throughput": 5,  "risk": 35, "cost": 15},
    "Business-as-usual":    {"npv": 10, "roi": 10, "payback": 15, "strategic": 5,  "operational": 15, "throughput": 10, "risk": 20, "cost": 15},
    "New growth":           {"npv": 25, "roi": 20, "payback": 5,  "strategic": 20, "operational": 10, "throughput": 10, "risk": 5,  "cost": 5},
    "Improve performance":  {"npv": 10, "roi": 10, "payback": 10, "strategic": 10, "operational": 20, "throughput": 20, "risk": 10, "cost": 10},
}

SAMPLE_PROJECTS = pd.DataFrame([
    {"Project": "Automation Line A",          "Aim": "New growth",          "cost": 750000,  "npv": 400000, "roi": 18.5, "strategic": 8, "operational": 7, "throughput": 15, "risk": 3, "payback": 4.2,
     "assumptions": "Discount rate 10%, 5-year useful life, 8% annual volume growth, installation Q2 2025",
     "source": "Manual"},
    {"Project": "Energy Efficiency Retrofit", "Aim": "Improve performance", "cost": 300000,  "npv": 150000, "roi": 20.0, "strategic": 7, "operational": 6, "throughput": 0,  "risk": 4, "payback": 3.0,
     "assumptions": "Discount rate 8%, energy cost savings $50k/yr, 6-year useful life",
     "source": "Manual"},
    {"Project": "Assembly Jig Upgrade",       "Aim": "Improve performance", "cost": 120000,  "npv": 60000,  "roi": 12.0, "strategic": 6, "operational": 5, "throughput": 8,  "risk": 6, "payback": 2.5,
     "assumptions": "Discount rate 10%, cycle time reduction 8%, no headcount change",
     "source": "Manual"},
    {"Project": "Quality Inspection System",  "Aim": "New growth",          "cost": 500000,  "npv": 280000, "roi": 16.0, "strategic": 9, "operational": 8, "throughput": 12, "risk": 5, "payback": 3.5,
     "assumptions": "Discount rate 10%, defect reduction from 3.2% to 0.8%, 5-year life",
     "source": "Manual"},
    {"Project": "Warehouse Conveyor",         "Aim": "Business-as-usual",   "cost": 400000,  "npv": 120000, "roi": 10.0, "strategic": 5, "operational": 6, "throughput": 5,  "risk": 7, "payback": 4.8,
     "assumptions": "Discount rate 8%, labor savings 2 FTE, 8-year useful life",
     "source": "Manual"},
    {"Project": "Robotic Palletizer",         "Aim": "New growth",          "cost": 650000,  "npv": 320000, "roi": 22.0, "strategic": 8, "operational": 7, "throughput": 22, "risk": 3, "payback": 3.1,
     "assumptions": "Discount rate 10%, throughput +22%, replaces 3 FTE, 7-year life",
     "source": "Manual"},
    {"Project": "Boiler Replacement",         "Aim": "Regulatory / safety", "cost": 200000,  "npv": 90000,  "roi": 14.0, "strategic": 4, "operational": 4, "throughput": 0,  "risk": 6, "payback": 3.8,
     "assumptions": "Mandatory compliance, EPA deadline Q4 2025, 15-year useful life",
     "source": "Manual"},
    {"Project": "Lighting Retrofit",          "Aim": "Business-as-usual",   "cost": 80000,   "npv": 35000,  "roi": 9.0,  "strategic": 3, "operational": 3, "throughput": 0,  "risk": 8, "payback": 5.0,
     "assumptions": "Discount rate 8%, energy savings $16k/yr, 5-year payback target",
     "source": "Manual"},
])

# ---------------------------------------------------------------------------
# Groq extraction
# ---------------------------------------------------------------------------
@st.cache_resource
def get_groq_client():
    try:
        from groq import Groq
        key = st.secrets.get("GROQ_API_KEY", "")
        if key:
            return Groq(api_key=key)
    except Exception:
        pass
    return None


def extract_from_document(text: str) -> dict:
    """Use Groq to extract CapEx fields from a business case document."""
    client = get_groq_client()
    if not client:
        return {"error": "Add GROQ_API_KEY to Streamlit secrets to enable AI extraction."}

    prompt = f"""You are a financial analyst extracting data from a capital expenditure (CapEx) business case document.

Extract the following fields from the document. If a field is not explicitly stated, make your best estimate based on context and mark it with [estimated]. If it truly cannot be determined, use null.

Return ONLY valid JSON with exactly these fields:

{{
  "project_name": "string — name or title of the project",
  "aim": "one of: Regulatory / safety, Business-as-usual, New growth, Improve performance",
  "cost": number — total capital cost in USD (convert if in other currencies),
  "npv": number — net present value in USD (null if not stated),
  "roi": number — return on investment as percentage (e.g. 15.5 for 15.5%),
  "payback": number — payback period in years,
  "strategic": number — strategic alignment score 1-10 (estimate from context),
  "operational": number — operational impact score 1-10 (estimate from context),
  "throughput": number — throughput improvement as percentage (0 if not applicable),
  "risk": number — risk score 1-10 where 10 is highest risk (estimate from context),
  "discount_rate": "string — discount rate used e.g. '10%' or null",
  "useful_life": "string — asset useful life e.g. '5 years' or null",
  "key_assumption_1": "string — most important financial assumption",
  "key_assumption_2": "string — second most important assumption or null",
  "key_assumption_3": "string — third assumption or null",
  "confidence": "high | medium | low — your confidence in the extraction overall"
}}

Document:
{text[:8000]}"""

    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        return {"error": f"Could not parse AI response as JSON: {e}"}
    except Exception as e:
        return {"error": f"Extraction failed: {e}"}


def read_uploaded_file(uploaded_file) -> str:
    """Extract text from PDF or Excel file."""
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(uploaded_file.read()), sheet_name=None)
            parts = []
            for sheet_name, sheet_df in df.items():
                parts.append(f"Sheet: {sheet_name}")
                parts.append(sheet_df.to_string())
            return "\n".join(parts)
        elif name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(uploaded_file.read()))
            return df.to_string()
        else:
            return uploaded_file.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Could not read file: {e}"


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------
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


def dcf_sensitivity(base_cost: float, base_roi: float,
                    discount_rate_pct: float, useful_life_yrs: float,
                    cost_overrun_pct: float, revenue_cut_pct: float) -> pd.DataFrame:
    """
    Recalculates NPV and payback from first principles using user-provided inputs.

    Formula: NPV = sum(CF_t / (1+r)^t for t=1..n) - C0
    where CF_t = constant annual cash inflow (simplified uniform cash flow),
          r    = discount rate per period,
          n    = useful life in years,
          C0   = initial capital cost.

    Payback = C0 / annual_CF (simple, undiscounted).

    Assumption: cash flows are uniform across the project life. This is a
    simplification — real projects have non-uniform cash flows. For those,
    users should supply their own DCF model. This analysis is directional.

    Sources:
      Brealey, Myers & Allen, Principles of Corporate Finance (13th ed.), Ch. 5
      Graham & Harvey (2001), The theory and practice of corporate finance,
        Journal of Financial Economics 60(2-3): 187-243
    """
    if useful_life_yrs <= 0 or base_cost <= 0 or discount_rate_pct <= 0:
        return pd.DataFrame()

    # Annual cash inflow: derived from ROI and cost
    # ROI = net_return / C0, so net_return = ROI * C0
    # Assuming net_return spread evenly: annual_CF = net_return / n
    annual_cf = base_cost * (base_roi / 100) / useful_life_yrs if base_roi > 0 else 0.0

    if annual_cf <= 0:
        return pd.DataFrame()

    def calc_npv(cost, cf, rate, n):
        return sum(cf / (1 + rate) ** t for t in range(1, int(n) + 1)) - cost

    def calc_payback(cost, cf):
        return cost / cf if cf > 0 else float("inf")

    r_base = discount_rate_pct / 100
    adj_cost = base_cost * (1 + cost_overrun_pct / 100)
    adj_cf   = annual_cf * (1 - revenue_cut_pct / 100)

    rows = []
    scenarios = [
        ("Base case",
         base_cost, annual_cf, r_base,
         f"Discount rate {discount_rate_pct:.1f}%, life {int(useful_life_yrs)} yrs, uniform CF"),
        ("Discount rate +2pp",
         base_cost, annual_cf, r_base + 0.02,
         f"Rate rises to {discount_rate_pct+2:.1f}% — tests hurdle rate sensitivity"),
        ("Discount rate +5pp",
         base_cost, annual_cf, r_base + 0.05,
         f"Rate rises to {discount_rate_pct+5:.1f}% — significant tightening scenario"),
        (f"Revenue / savings down {int(revenue_cut_pct)}%",
         base_cost, adj_cf, r_base,
         f"Annual cash inflow reduced by {int(revenue_cut_pct)}% — demand or price risk"),
        (f"Capital cost overrun +{int(cost_overrun_pct)}%",
         adj_cost, annual_cf, r_base,
         f"Capital cost rises to ${adj_cost:,.0f} — implementation risk"),
    ]

    for label, c0, cf, r, note in scenarios:
        npv = calc_npv(c0, cf, r, useful_life_yrs)
        pb  = calc_payback(c0, cf)
        rows.append({
            "Scenario":       label,
            "Rate":           f"{r*100:.1f}%",
            "Adj. NPV":       npv,
            "Adj. Payback":   pb,
            "NPV display":    f"${npv:,.0f}",
            "Payback display":f"{pb:.1f} yrs" if pb < 99 else "N/A",
            "Note":           note,
            "Positive NPV":   npv > 0,
        })

    return pd.DataFrame(rows)


def kpi_card(col, label, value, sub=None, color="#1B6EF3"):
    sub_html = f'<div style="color:#6B7280;font-size:12px;margin-top:4px">{sub}</div>' if sub else ""
    col.markdown(
        f'''<div style="background:#FFFFFF;border:1px solid #E8EAF0;border-radius:10px;
        padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
        <div style="color:#6B7280;font-size:11px;letter-spacing:.06em;text-transform:uppercase;font-weight:500">{label}</div>
        <div style="color:{color};font-size:24px;font-weight:600;margin-top:4px;font-family:\'IBM Plex Mono\',monospace">{value}</div>
        {sub_html}</div>''',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "projects" not in st.session_state:
    st.session_state.projects = SAMPLE_PROJECTS.copy()
if "extracted_project" not in st.session_state:
    st.session_state.extracted_project = None

for aim in AIMS:
    for k in CRIT_KEYS:
        sk = f"w_{aim}_{k}"
        if sk not in st.session_state:
            st.session_state[sk] = DEFAULT_AIM_WEIGHTS[aim][k]


def aim_weights(aim):
    return {k: st.session_state[f"w_{aim}_{k}"] for k in CRIT_KEYS}


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.markdown("""
<div style="padding:8px 0 16px">
  <div style="font-size:20px;font-weight:700;color:#1A1D23">📊 Capisight</div>
  <div style="font-size:12px;color:#6B7280;margin-top:2px">CapEx Decision Intelligence</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.markdown('<div style="font-size:11px;font-weight:600;color:#6B7280;letter-spacing:.08em;text-transform:uppercase;margin-bottom:8px">Scoring weights by aim</div>', unsafe_allow_html=True)

active_aim = st.sidebar.selectbox("Aim to configure", AIMS)

if active_aim == "Regulatory / safety":
    st.sidebar.info("Regulatory projects are often mandatory. Scoring helps prioritize among them, not whether to fund them.")

for c in CRITERIA:
    arrow = "higher better" if c["direction"] == "higher" else "lower better"
    st.sidebar.slider(
        f"{c['label']} ({arrow})",
        0, 40, step=1,
        key=f"w_{active_aim}_{c['key']}"
    )

if st.sidebar.button("Reset to defaults"):
    for k in CRIT_KEYS:
        st.session_state[f"w_{active_aim}_{k}"] = DEFAULT_AIM_WEIGHTS[active_aim][k]
    st.rerun()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div style="padding:4px 0 20px">
  <div style="font-size:11px;font-weight:600;color:#6B7280;letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px">CAPITAL EXPENDITURE PLATFORM</div>
  <h1 style="font-size:28px;font-weight:700;margin:0;color:#1A1D23">CapEx Decision Intelligence</h1>
  <p style="color:#6B7280;font-size:14px;margin-top:4px;max-width:640px">
    Upload a business case document and let AI extract the numbers. Score, compare, and allocate capital across strategic aims. Stress-test assumptions before you commit.
  </p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Compute scores
# ---------------------------------------------------------------------------
projects_df = st.session_state.projects
valid = projects_df.dropna(subset=["Aim"]) if "Aim" in projects_df.columns else projects_df

# Ensure numeric columns exist
for k in CRIT_KEYS:
    if k not in valid.columns:
        valid[k] = 0
    valid[k] = pd.to_numeric(valid[k], errors="coerce").fillna(0)

if "assumptions" not in valid.columns:
    valid["assumptions"] = ""
if "source" not in valid.columns:
    valid["source"] = "Manual"

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
    bucket_eff[aim]    = eff

# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------
n_projects  = len(valid)
total_cost  = float(valid["cost"].sum()) if n_projects else 0.0
n_aims_used = valid["Aim"].nunique() if n_projects else 0
ai_count    = int((valid["source"] == "AI extracted").sum()) if "source" in valid.columns else 0

c1, c2, c3, c4, c5 = st.columns(5)
kpi_card(c1, "Projects",          f"{n_projects}")
kpi_card(c2, "Aims in use",       f"{n_aims_used} / {len(AIMS)}")
kpi_card(c3, "Total portfolio",   f"${total_cost:,.0f}")
kpi_card(c4, "Criteria scored",   f"{len(CRITERIA)}")
kpi_card(c5, "AI extracted",      f"{ai_count}", sub="projects ingested from docs", color=GREEN)

st.markdown('<div style="color:#9CA3AF;font-size:12px;margin:12px 0 4px">Scores compare projects <strong>only within an aim</strong>. Sample data is illustrative. Upload real business cases below or edit the table directly.</div>', unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_ingest, tab_proj, tab_rank, tab_break, tab_sensitivity, tab_scatter, tab_budget = st.tabs([
    "📄  Ingest Document",
    "📋  Projects",
    "📊  Rankings",
    "🔍  Score Breakdown",
    "📉  Sensitivity",
    "💰  Cost vs Score",
    "🏦  Budget",
])

# ============================================================
# TAB: INGEST DOCUMENT
# ============================================================
with tab_ingest:
    st.markdown("""
<div class="capex-card-blue">
  <div class="section-eyebrow">AI Document Ingestion</div>
  <div style="font-size:16px;font-weight:600;color:#1E40AF;margin-bottom:6px">Upload a business case — AI extracts the numbers</div>
  <div style="font-size:13px;color:#3730A3">
    Drop in a CapEx business case as PDF, Excel, or Word. The AI reads the document and populates the scoring fields automatically.
    Always review and correct the extracted values before accepting — AI extraction is a starting point, not a final answer.
  </div>
</div>
""", unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload business case (PDF, Excel, CSV)",
        type=["pdf", "xlsx", "xls", "csv", "txt"],
        help="Accepts PDF business cases, Excel financial models, or CSV data"
    )

    if uploaded:
        with st.spinner(f"Reading {uploaded.name}..."):
            doc_text = read_uploaded_file(uploaded)

        if doc_text.startswith("Could not read"):
            st.error(doc_text)
        else:
            st.success(f"Read {len(doc_text):,} characters from {uploaded.name}")

            with st.expander("Preview extracted text (first 1,000 characters)"):
                st.code(doc_text[:1000])

            if st.button("Extract CapEx data with AI", type="primary"):
                with st.spinner("Analyzing document and extracting financial data..."):
                    result = extract_from_document(doc_text)

                if "error" in result:
                    st.error(result["error"])
                    st.info("You can still add the project manually in the Projects tab.")
                else:
                    st.session_state.extracted_project = result
                    st.success("Extraction complete. Review and confirm below.")

    if st.session_state.extracted_project:
        ext = st.session_state.extracted_project
        conf = ext.get("confidence", "medium")
        conf_color = {"high": GREEN, "medium": AMBER, "low": RED}.get(conf, GREY)

        st.markdown(f"""
<div class="capex-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <div class="section-eyebrow">Extracted project</div>
      <div style="font-size:18px;font-weight:600;color:#1A1D23">{ext.get('project_name', 'Unnamed Project')}</div>
      <div style="font-size:13px;color:#6B7280;margin-top:2px">AI confidence: <span style="color:{conf_color};font-weight:500">{conf.upper()}</span> — review all values before accepting</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            proj_name = st.text_input("Project name", value=ext.get("project_name", ""))
            proj_aim  = st.selectbox("Strategic aim", AIMS,
                                     index=AIMS.index(ext.get("aim", AIMS[0])) if ext.get("aim") in AIMS else 0)
            proj_cost = st.number_input("Total cost (USD)", value=float(ext.get("cost") or 0), min_value=0.0, step=1000.0)
            proj_npv  = st.number_input("NPV (USD)", value=float(ext.get("npv") or 0), step=1000.0)

        with col2:
            proj_roi      = st.number_input("ROI (%)", value=float(ext.get("roi") or 0), min_value=0.0)
            proj_payback  = st.number_input("Payback (years)", value=float(ext.get("payback") or 0), min_value=0.0)
            proj_strategic = st.slider("Strategic score (1-10)", 1, 10, int(ext.get("strategic") or 5))
            proj_operational = st.slider("Operational impact (1-10)", 1, 10, int(ext.get("operational") or 5))

        with col3:
            proj_throughput = st.number_input("Throughput improvement (%)", value=float(ext.get("throughput") or 0), min_value=0.0)
            proj_risk = st.slider("Risk score (1-10, 10=highest)", 1, 10, int(ext.get("risk") or 5))

            # Build assumptions string
            a1 = ext.get("discount_rate") or ""
            a2 = ext.get("useful_life") or ""
            a3 = ext.get("key_assumption_1") or ""
            a4 = ext.get("key_assumption_2") or ""
            a5 = ext.get("key_assumption_3") or ""
            auto_assumptions = ", ".join(x for x in [
                f"Discount rate {a1}" if a1 else "",
                f"Useful life {a2}" if a2 else "",
                a3, a4, a5
            ] if x)
            proj_assumptions = st.text_area("Key assumptions (edit as needed)", value=auto_assumptions, height=100)

        if st.button("Add to portfolio", type="primary"):
            new_row = {
                "Project":     proj_name,
                "Aim":         proj_aim,
                "cost":        proj_cost,
                "npv":         proj_npv,
                "roi":         proj_roi,
                "payback":     proj_payback,
                "strategic":   proj_strategic,
                "operational": proj_operational,
                "throughput":  proj_throughput,
                "risk":        proj_risk,
                "assumptions": proj_assumptions,
                "source":      "AI extracted",
            }
            new_df = pd.DataFrame([new_row])
            st.session_state.projects = pd.concat(
                [st.session_state.projects, new_df], ignore_index=True
            )
            st.session_state.extracted_project = None
            st.success(f"Added '{proj_name}' to your portfolio. Switch to the Rankings tab to see it scored.")
            st.rerun()

        if st.button("Discard extraction"):
            st.session_state.extracted_project = None
            st.rerun()

    if not uploaded and not st.session_state.extracted_project:
        st.markdown("""
<div class="capex-card" style="text-align:center;padding:40px">
  <div style="font-size:32px;margin-bottom:12px">📄</div>
  <div style="font-size:15px;font-weight:500;color:#374151">Upload a business case document to get started</div>
  <div style="font-size:13px;color:#9CA3AF;margin-top:6px">Supports PDF business cases, Excel financial models, and CSV files</div>
  <div style="font-size:12px;color:#9CA3AF;margin-top:12px">Or skip this step and add projects manually in the Projects tab</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# TAB: PROJECTS
# ============================================================
with tab_proj:
    st.markdown('<div style="font-size:13px;color:#6B7280;margin-bottom:12px">Edit any cell, change an aim, add rows, or delete rows. The <strong>assumptions</strong> column records the key business case promises for later review.</div>', unsafe_allow_html=True)

    display_cols = ["Project", "Aim", "cost", "npv", "roi", "payback",
                    "strategic", "operational", "throughput", "risk", "assumptions", "source"]

    for col in display_cols:
        if col not in st.session_state.projects.columns:
            st.session_state.projects[col] = "" if col in ("assumptions", "source") else 0

    edited = st.data_editor(
        st.session_state.projects[display_cols],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Aim": st.column_config.SelectboxColumn("Aim", options=AIMS, required=True),
            "cost":        st.column_config.NumberColumn("Cost (USD)",    format="$%,.0f"),
            "npv":         st.column_config.NumberColumn("NPV (USD)",     format="$%,.0f"),
            "roi":         st.column_config.NumberColumn("ROI (%)",       format="%.1f%%"),
            "payback":     st.column_config.NumberColumn("Payback (yrs)", format="%.1f"),
            "throughput":  st.column_config.NumberColumn("Throughput (%)",format="%.0f%%"),
            "assumptions": st.column_config.TextColumn("Key assumptions", width="large"),
            "source":      st.column_config.TextColumn("Source",          width="small"),
        },
        key="editor",
    )
    st.session_state.projects = edited
    st.caption("Changes flow through to all tabs. Source = 'AI extracted' for documents ingested above; 'Manual' for hand-entered rows.")

# ============================================================
# TAB: RANKINGS
# ============================================================
with tab_rank:
    if not bucket_scores:
        st.info("Add projects and assign aims to see rankings.")
    else:
        for aim in AIMS:
            if aim not in bucket_scores:
                continue
            scored = bucket_scores[aim]
            n = len(scored)

            st.markdown(f"#### {aim}  ·  {n} project{'s' if n != 1 else ''}")
            s = scored.sort_values("Score")

            fig = go.Figure(go.Bar(
                x=s["Score"], y=s["Project"], orientation="h",
                marker_color=BLUE,
                marker_line_width=0,
                text=[f"{v:.3f}" for v in s["Score"]],
                textposition="outside",
                hovertemplate="%{y}<br>Score %{x:.3f}<extra></extra>",
            ))
            fig.update_layout(
                **PLOTLY_LAYOUT,
                height=80 + 48 * n,
            )
            fig.update_xaxes(range=[0, 1.12], title="Score (0-1, within this aim)")
            fig.update_yaxes(automargin=True, title=None)
            st.plotly_chart(fig, use_container_width=True, key=f"rank_{aim}")

            with st.expander(f"Table — {aim}"):
                cols = ["Rank", "Project", "Score"] + CRIT_KEYS + ["assumptions", "source"]
                show_cols = [c for c in cols if c in scored.columns]
                show = scored[show_cols].copy()
                show["Score"] = show["Score"].map(lambda x: f"{x:.3f}")

                def color_source(val):
                    if val == "AI extracted":
                        return "background-color:#F0FDF4;color:#166534"
                    return ""

                if "source" in show.columns:
                    st.dataframe(
                        show.style.applymap(color_source, subset=["source"]),
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.dataframe(show, use_container_width=True, hide_index=True)

            st.markdown("")

# ============================================================
# TAB: SCORE BREAKDOWN
# ============================================================
with tab_break:
    if not bucket_scores:
        st.info("Add projects and assign aims first.")
    else:
        c1, c2 = st.columns(2)
        sel_aim  = c1.selectbox("Aim", list(bucket_scores.keys()), key="bd_aim")
        adf      = bucket_scores[sel_aim]
        sel_proj = c2.selectbox("Project", adf["Project"].tolist(), key="bd_proj")

        eff = bucket_eff[sel_aim]
        idx = adf.index[adf["Project"] == sel_proj][0]

        parts = []
        for c in CRITERIA:
            nv = normalize_column(adf[c["key"]], c["direction"])[idx]
            parts.append({
                "Criterion":    c["label"],
                "Contribution": nv * eff[c["key"]],
                "Normalized":   nv,
                "Weight":       eff[c["key"]],
                "Raw value":    adf.loc[idx, c["key"]],
            })
        pdf = pd.DataFrame(parts).sort_values("Contribution")

        col_chart, col_detail = st.columns([2, 1])
        with col_chart:
            colors = [BLUE if x > 0.05 else GREY for x in pdf["Contribution"]]
            fig = go.Figure(go.Bar(
                x=pdf["Contribution"], y=pdf["Criterion"], orientation="h",
                marker_color=colors,
                marker_line_width=0,
                customdata=pdf[["Normalized", "Weight", "Raw value"]].values,
                hovertemplate="%{y}<br>Contribution: %{x:.3f}<br>Normalized: %{customdata[0]:.2f}<br>Weight: %{customdata[1]:.0%}<br>Raw value: %{customdata[2]}<extra></extra>",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=80 + 44 * len(pdf))
            fig.update_xaxes(title="Weighted contribution to score")
            fig.update_yaxes(automargin=True)
            st.plotly_chart(fig, use_container_width=True, key="breakdown_chart")

        with col_detail:
            score = adf.loc[idx, "Score"]
            st.markdown(f"""
<div class="capex-card">
  <div class="section-eyebrow">Final score</div>
  <div style="font-size:32px;font-weight:700;color:{BLUE};font-family:'IBM Plex Mono',monospace">{score:.3f}</div>
  <div style="font-size:12px;color:#6B7280;margin-top:4px">Rank {int(adf.loc[idx,'Rank'])} of {len(adf)} in {sel_aim}</div>
</div>
""", unsafe_allow_html=True)

            # Assumptions panel
            row_assumptions = ""
            if "assumptions" in adf.columns:
                row_assumptions = str(adf.loc[idx, "assumptions"] or "")

            if row_assumptions and row_assumptions != "nan":
                st.markdown('<div class="section-eyebrow" style="margin-top:12px">Key assumptions</div>', unsafe_allow_html=True)
                for assumption in row_assumptions.split(","):
                    assumption = assumption.strip()
                    if assumption:
                        st.markdown(f'<span class="assumption-pill">{assumption}</span>', unsafe_allow_html=True)
                st.markdown('<div style="font-size:11px;color:#9CA3AF;margin-top:8px">These are the promises the business case rests on. Challenge them before approving.</div>', unsafe_allow_html=True)

# ============================================================
# TAB: SENSITIVITY ANALYSIS
# ============================================================
with tab_sensitivity:
    if not bucket_scores:
        st.info("Add projects first.")
    else:
        st.markdown("""
<div class="capex-card-amber">
  <div class="section-eyebrow">Sensitivity analysis</div>
  <div style="font-size:14px;font-weight:500;color:#92400E">What happens to NPV and payback if key assumptions shift?</div>
  <div style="font-size:12px;color:#B45309;margin-top:4px">
    Every business case is built on assumptions. This tab stress-tests the most common ones:
    a higher discount rate, lower demand growth, and cost overruns.
    A project that is viable only under optimistic assumptions deserves more scrutiny.
  </div>
</div>
""", unsafe_allow_html=True)

        all_projects = valid["Project"].tolist()
        if all_projects:
            sel_sens = st.selectbox("Select project to stress-test", all_projects)
            row = valid[valid["Project"] == sel_sens].iloc[0]

            base_cost = float(row.get("cost", 0) or 0)
            base_roi  = float(row.get("roi", 0) or 0)

            if base_cost <= 0 or base_roi <= 0:
                st.warning("This project needs Cost and ROI values to run sensitivity analysis. Add them in the Projects tab.")
            else:
                st.markdown("""
<div class="capex-card-amber">
  <div style="font-size:12px;color:#92400E;margin-bottom:4px">
    <strong>How this works:</strong> Enter the discount rate and useful life from the original business case.
    The tool calculates NPV using a standard DCF formula (Brealey, Myers & Allen) and shows how it changes
    under five scenarios. Cash flows are assumed uniform across the project life — a simplification.
    For projects with non-uniform cash flows, use your own DCF model.
  </div>
</div>
""", unsafe_allow_html=True)

                col_inputs, col_results = st.columns([1, 2])

                with col_inputs:
                    st.markdown('<div class="section-eyebrow">Enter business case assumptions</div>', unsafe_allow_html=True)

                    discount_rate = st.number_input(
                        "Discount rate / hurdle rate (%)",
                        min_value=0.1, max_value=50.0, value=10.0, step=0.5,
                        help="The rate used in the original business case. Often WACC or a company hurdle rate."
                    )
                    useful_life = st.number_input(
                        "Useful life (years)",
                        min_value=1, max_value=30, value=5,
                        help="How many years the asset is expected to generate returns."
                    )
                    cost_overrun = st.slider(
                        "Cost overrun scenario (%)",
                        min_value=5, max_value=50, value=20, step=5,
                        help="How much capital cost could increase. 20% is a common contingency in manufacturing."
                    )
                    revenue_cut = st.slider(
                        "Revenue / savings reduction scenario (%)",
                        min_value=5, max_value=70, value=30, step=5,
                        help="How much the projected cash inflows could fall. Tests demand or price risk."
                    )

                    st.markdown(f"""
<div class="capex-card" style="margin-top:12px">
  <div class="section-eyebrow">Project inputs</div>
  <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #F3F4F6">
    <span style="color:#6B7280;font-size:12px">Capital cost</span>
    <span style="font-weight:600;font-size:12px;font-family:'IBM Plex Mono',monospace">${base_cost:,.0f}</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #F3F4F6">
    <span style="color:#6B7280;font-size:12px">ROI</span>
    <span style="font-weight:600;font-size:12px;font-family:'IBM Plex Mono',monospace">{base_roi:.1f}%</span>
  </div>
  <div style="display:flex;justify-content:space-between;padding:4px 0">
    <span style="color:#6B7280;font-size:12px">Implied annual CF</span>
    <span style="font-weight:600;font-size:12px;font-family:'IBM Plex Mono',monospace">${base_cost * (base_roi/100) / useful_life:,.0f}/yr</span>
  </div>
</div>
""", unsafe_allow_html=True)

                    # Assumptions on record
                    assumptions_text = str(row.get("assumptions", "") or "")
                    if assumptions_text and assumptions_text != "nan":
                        st.markdown('<div class="section-eyebrow" style="margin-top:12px">Assumptions on record</div>', unsafe_allow_html=True)
                        for a in assumptions_text.split(","):
                            a = a.strip()
                            if a:
                                st.markdown(f'<span class="assumption-pill">{a}</span>', unsafe_allow_html=True)

                with col_results:
                    sens_df = dcf_sensitivity(
                        base_cost, base_roi,
                        discount_rate, useful_life,
                        cost_overrun, revenue_cut
                    )

                    if sens_df.empty:
                        st.warning("Could not compute DCF. Check that Cost, ROI, discount rate, and useful life are all positive.")
                    else:
                        for _, srow in sens_df.iterrows():
                            positive = srow["Positive NPV"]
                            card_class = "capex-card-green" if positive else "capex-card-amber"
                            npv_color = GREEN if positive else AMBER
                            st.markdown(f"""
<div class="{card_class}" style="margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div style="flex:1;margin-right:12px">
      <div style="font-size:13px;font-weight:600;color:#1A1D23">{srow["Scenario"]}</div>
      <div style="font-size:11px;color:#6B7280;margin-top:2px">{srow["Note"]}</div>
      <div style="font-size:11px;color:#9CA3AF;margin-top:2px">Rate: {srow["Rate"]}</div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-size:15px;font-weight:700;font-family:'IBM Plex Mono',monospace;color:{npv_color}">{srow["NPV display"]}</div>
      <div style="font-size:12px;color:#6B7280">Payback: {srow["Payback display"]}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

                        st.markdown("""
<div style="font-size:11px;color:#9CA3AF;margin-top:8px;padding:10px;background:#F9FAFB;border-radius:6px">
  <strong>Methodology:</strong> Standard DCF — NPV = Σ(CF/(1+r)^t) − C0, where CF is derived from
  ROI × cost ÷ useful life (uniform cash flow assumption). Payback = cost ÷ annual CF (undiscounted).
  Source: Brealey, Myers & Allen, <em>Principles of Corporate Finance</em>, Ch. 5.
  Graham & Harvey (2001, JFE) found NPV and payback are the two most widely used methods by CFOs.
  <br><br>Limitation: uniform cash flows are a simplification. Non-uniform projects require a full cash flow schedule.
</div>
""", unsafe_allow_html=True)

# ============================================================
# TAB: COST VS SCORE
# ============================================================
with tab_scatter:
    if not bucket_scores:
        st.info("Add projects first.")
    else:
        st.caption("Top-left quadrant is the sweet spot: high score, low cost. Scores are within-aim only.")
        sel_aim_sc = st.selectbox("Aim", list(bucket_scores.keys()), key="sc_aim")
        sdf = bucket_scores[sel_aim_sc]

        colors = [BLUE if s == "AI extracted" else SLATE
                  for s in (sdf["source"].tolist() if "source" in sdf.columns else ["Manual"] * len(sdf))]

        fig = go.Figure(go.Scatter(
            x=sdf["cost"], y=sdf["Score"], mode="markers+text",
            marker=dict(size=18, color=colors, line=dict(width=1.5, color="#FFFFFF")),
            text=sdf["Project"], textposition="top center",
            textfont=dict(size=11, color="#374151"),
            hovertemplate="%{text}<br>Cost: $%{x:,.0f}<br>Score: %{y:.3f}<extra></extra>",
        ))
        fig.update_layout(**PLOTLY_LAYOUT, height=440)
        fig.update_xaxes(title="Estimated cost (USD)")
        fig.update_yaxes(title="Score (within aim)", range=[0, 1.12])
        st.plotly_chart(fig, use_container_width=True, key="scatter_chart")
        st.caption("Blue = AI-extracted from document. Grey = manually entered.")

# ============================================================
# TAB: BUDGET
# ============================================================
with tab_budget:
    if not bucket_scores:
        st.info("Add projects first.")
    else:
        st.caption("Set a total budget and allocate it across aims. Shares are hard targets — money does not move across aims automatically.")

        total_budget = st.number_input("Total budget (USD)", min_value=0, value=1500000, step=50000)
        present = list(bucket_scores.keys())

        st.markdown("**Budget share per aim (%)** — auto-normalized to 100%")
        scol = st.columns(len(present))
        raw_shares = {
            a: scol[i].number_input(a, 0, 100, round(100/len(present)), 5, key=f"share_{a}")
            for i, a in enumerate(present)
        }
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
                    msg = f"**{a}** — target ${ab:,.0f}, committed ${spent:,.0f}: {', '.join(chosen)}"
                else:
                    msg = f"**{a}** — target ${ab:,.0f}, committed $0"

                if strand > 0.5 and len(unfunded) > 0:
                    msg += f"\n\n_Strands ${strand:,.0f}: cheapest unfunded project costs ${unfunded['cost'].min():,.0f}_"
                    rebalance.append(a)
                    st.warning(msg)
                elif strand > 0.5:
                    msg += f"\n\n_Surplus ${strand:,.0f}: all projects funded. Consider reallocating._"
                    rebalance.append(a)
                    st.info(msg)
                else:
                    st.success(msg)

            unspent = total_budget - committed_total
            k1, k2, k3 = st.columns(3)
            kpi_card(k1, "Committed",       f"${committed_total:,.0f}", color=GREEN)
            kpi_card(k2, "Total budget",    f"${total_budget:,.0f}")
            kpi_card(k3, "Unallocated",     f"${unspent:,.0f}",
                     sub="rebalance shares" if unspent > 0.5 else "fully allocated",
                     color=AMBER if unspent > 0.5 else GREEN)

            st.markdown("")
            bud = pd.DataFrame(rows)
            fig = go.Figure()
            fig.add_bar(y=bud["Aim"], x=bud["Committed"], name="Committed",
                        orientation="h", marker_color=BLUE, marker_line_width=0,
                        hovertemplate="%{y}<br>Committed $%{x:,.0f}<extra></extra>")
            fig.add_bar(y=bud["Aim"], x=bud["Unused"], name="Unused",
                        orientation="h", marker_color="#E5E7EB", marker_line_width=0,
                        hovertemplate="%{y}<br>Unused $%{x:,.0f}<extra></extra>")
            fig.update_layout(
                **PLOTLY_LAYOUT,
                barmode="stack",
                height=90 + 52 * len(bud),
                legend=dict(orientation="h", y=1.12, x=0, font=dict(color="#374151")),
            )
            fig.update_xaxes(title="USD")
            fig.update_yaxes(automargin=True)
            st.plotly_chart(fig, use_container_width=True, key="budget_chart")

            if rebalance and unspent > 0.5:
                st.warning(
                    f"~${unspent:,.0f} is unallocated because per-aim shares do not fit project costs "
                    f"in: {', '.join(rebalance)}. Money does not move across aims automatically — "
                    f"this is deliberate, since aims are not comparable on one scale."
                )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.markdown(
    '<div style="font-size:11px;color:#9CA3AF;text-align:center">'
    'Capisight v2 · CapEx Decision Intelligence · '
    'Frameworks: McKinsey Capital Allocation, Graham & Harvey (2001) · '
    'AI extraction by Groq (Llama 3, free) · '
    'Built by Rutwik Satish · MS Engineering Management, Northeastern University · '
    '© 2026'
    '</div>',
    unsafe_allow_html=True,
)
