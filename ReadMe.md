# Capisight v2

**An AI-powered CapEx decision intelligence platform that ingests business case documents, scores capital projects by strategic aim, stress-tests assumptions with real DCF analysis, and allocates a budget transparently.**

Capisight helps manufacturing and operations finance teams answer one question: *given a pile of inconsistent business case documents, which projects should we fund, in what order, and why?*

> **Status:** v2 is live at [capisight.streamlit.app](https://capisight.streamlit.app). Built after observing firsthand in a manufacturing finance interview that teams are rigorous about approving capital spend but lack structured tools to verify whether assumptions are sound before committing.

---

## Table of contents
- [What's new in v2](#whats-new-in-v2)
- [What it does](#what-it-does)
- [Why it works this way](#why-it-works-this-way)
- [Quick start](#quick-start)
- [How to use it](#how-to-use-it)
- [How the scoring works](#how-the-scoring-works)
- [How the DCF sensitivity works](#how-the-dcf-sensitivity-works)
- [Honesty notes](#honesty-notes-please-read)
- [Project structure](#project-structure)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [Grounding and sources](#grounding-and-sources)

---

## What's new in v2

| Feature | v1 | v2 |
|---|---|---|
| Data entry | Manual table only | Upload PDF or Excel business case — AI extracts the numbers |
| Criteria | 7 (financial + strategic + risk) | 8 — adds **throughput improvement (%)** as an operational KPI |
| Assumption tracking | None | Every project stores its key assumptions; surfaced in review |
| Sensitivity analysis | None | Real DCF — NPV recalculated from first principles under 5 scenarios |
| UI theme | Dark terminal aesthetic | Clean light theme — easier to read in a work context |
| Data provenance | All manual | AI-extracted projects are badged and distinguishable from manual entries |

---

## What it does

1. **Ingests business case documents.** Upload a PDF, Excel, or CSV business case. Groq (Llama 3, free) reads the document and extracts capital cost, NPV, ROI, payback period, strategic alignment, operational impact, throughput improvement, risk, and key assumptions. You review and correct before accepting.

2. **Tags each project by aim.** Four aims: *regulatory / safety*, *business-as-usual*, *new growth*, *improve performance*.

3. **Scores projects on aim-appropriate criteria.** Each aim has its own weight profile across eight criteria. Weights are set with sliders and auto-normalize to 100%.

4. **Ranks projects within each aim** — not in one pooled list. A mandatory safety project and a growth bet are not on the same ranked list because they exist for different reasons.

5. **Shows exactly why each project scored the way it did.** The Score Breakdown tab shows each criterion's weighted contribution. The contributions sum to the score, so the number is never a black box.

6. **Surfaces the assumptions the business case rests on.** Before you approve anything, you can see what discount rate, useful life, and demand assumptions the NPV was built on.

7. **Stress-tests those assumptions with real DCF.** The Sensitivity tab recalculates NPV and payback under five scenarios using the standard DCF formula. You enter the assumptions from the original business case; the tool shows what happens if they are wrong.

8. **Allocates a budget across aims.** Set a total budget and percentage share per aim. Within each aim, highest-ranked projects are funded until that share is used. Unallocated money is flagged with the reason.

---

## Why it works this way

**Grouping by aim instead of ranking everything together** is the central design choice. A mandatory safety project and a speculative growth bet should not sit on the same ranked list, because they exist for different reasons and should be judged on different criteria. This follows McKinsey's argument in *Managing a moonshot* that capital projects are best grouped by aim, with evaluation metrics set per category.

**Assumption transparency** exists because most CapEx business cases are built on projections that are optimistic by default. Recording what the business case promised, and making those promises visible before approval, is the thing most CapEx processes skip. Finario's own research notes that post-investment reviews are "talked about but rarely done" — the reason is that nobody captured the original promise in a form that survives the approval meeting.

**DCF sensitivity uses the standard formula, not invented multipliers.** NPV = Σ(CF/(1+r)^t) − C0. The user enters the discount rate and useful life from their actual business case. The tool derives uniform annual cash flows from ROI and cost, recalculates NPV and payback for five scenarios, and shows the math. No black box. The uniform cash flow assumption is a simplification that is explicitly disclosed.

**Budget shares are hard targets** — money does not move across aims automatically. This keeps the "aims are not comparable" principle intact and hands the trade-off back to the user.

---

## Quick start

```bash
# 1. create a virtual environment (optional but recommended)
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. add your Groq API key (free at console.groq.com)
mkdir -p .streamlit
echo '[secrets]\nGROQ_API_KEY = "your_key_here"' > .streamlit/secrets.toml

# 4. run
streamlit run capex_scoring_app.py
```

The app opens at `http://localhost:8501`. Without a Groq key the document ingestion tab will still load but AI extraction will be disabled — you can still use all other features manually.

---

## How to use it

1. **Ingest a document (optional).** Upload a CapEx business case as PDF or Excel. Review the AI-extracted values, correct anything wrong, and click Add to portfolio. Or skip this and add projects manually.

2. **Edit the projects table.** Change any value, switch a project's aim via the dropdown, add rows, or delete rows. Sample projects are illustrative — replace them with your own.

3. **Tune the weights.** In the sidebar, pick an aim and set how much each criterion matters for that aim. Values are relative and auto-normalize to 100%. Reset restores the default profile.

4. **Read the within-aim rankings.** Each aim gets its own ranked chart and table. AI-extracted projects are highlighted in green.

5. **Inspect any project's score.** The Score Breakdown tab shows how each criterion contributed, down to the weighted contribution. The Assumptions panel shows what the business case was built on.

6. **Stress-test assumptions.** In the Sensitivity tab, enter the discount rate and useful life from the original business case. The tool runs five DCF scenarios and shows adjusted NPV and payback for each.

7. **Allocate the budget.** Set a total budget and percentage share per aim. The app funds top-ranked projects within each share and flags any unallocated money.

---

## How the scoring works

Each criterion is **min-max normalized to 0–1 within an aim**, respecting its direction:

- *Higher is better* (NPV, ROI, strategic, operational, throughput): `(value − min) / (max − min)`
- *Lower is better* (payback, risk, cost): `(max − value) / (max − min)`
- If every project in an aim shares the same value for a criterion, that criterion scores `1.0` for all — it cannot discriminate, so it is treated as neutral rather than dividing by zero.

The **score** is the weighted sum of normalized criteria, using the aim's effective (normalized) weights. Scores are only meaningful inside an aim, not across aims.

Budget allocation uses a **greedy selection**: within each aim's share, projects are funded in rank order. Any leftover is reported as stranded or surplus with the reason.

### The eight criteria

| Criterion | Direction | Why it's included |
|---|---|---|
| NPV (USD) | Higher | Primary financial return measure |
| ROI (%) | Higher | Return relative to capital invested |
| Payback period (years) | Lower | Liquidity and risk proxy |
| Strategic score (1–10) | Higher | Alignment with organizational priorities |
| Operational impact (1–10) | Higher | Effect on day-to-day operations |
| Throughput improvement (%) | Higher | Manufacturing-specific operational KPI |
| Risk score (1–10) | Lower | Implementation and delivery risk |
| Estimated cost (USD) | Lower | Capital efficiency |

---

## How the DCF sensitivity works

**Formula:** NPV = Σ(CF / (1+r)^t for t = 1 to n) − C0

Where CF is the annual cash flow (derived from ROI × cost ÷ useful life, assuming uniform cash flows), r is the discount rate, n is the useful life in years, and C0 is the initial capital cost.

**Simple payback** = C0 ÷ annual CF (undiscounted).

**Five scenarios run:**
1. Base case — your inputs as submitted
2. Discount rate +2pp — tests hurdle rate sensitivity
3. Discount rate +5pp — significant tightening scenario
4. Revenue or savings down X% — tests demand or price risk (user-set)
5. Capital cost overrun +X% — tests implementation risk (user-set)

**Limitation:** uniform cash flows are a simplification. Projects with non-uniform cash flows (front-loaded savings, step-function revenues) require a full cash flow schedule. This limitation is disclosed in the UI.

**Sources:** Brealey, Myers & Allen, *Principles of Corporate Finance* (13th ed.), Ch. 5. Graham & Harvey (2001), *The Theory and Practice of Corporate Finance*, Journal of Financial Economics 60(2-3): 187–243.

---

## Honesty notes (please read)

- **The four aims are from McKinsey.** The default weight profiles per aim are a reasonable starting hypothesis, not a sourced prescription. Every weight is user-editable.
- **AI extraction is a starting point, not a final answer.** Always review extracted values before accepting. The confidence level shown (high / medium / low) reflects the AI's assessment of how clearly the document stated each figure.
- **Sample projects are illustrative.** Replace them with real data before drawing any real conclusion.
- **DCF sensitivity assumes uniform cash flows.** This is a simplification. The limitation is stated in the UI and in this README.
- **Scores are comparable only within an aim.** Never across aims. Cross-aim allocation is a process, not a formula.
- **The tool imposes structure and discipline, not opinions** about a firm's priorities. Weights, aim tags, and budget shares are all user inputs.

---

## Project structure

```
Capisight/
├── capex_scoring_app.py   # the Streamlit application (v2)
├── requirements.txt       # Python dependencies
├── README.md              # this file
└── .streamlit/
    └── secrets.toml       # GROQ_API_KEY — git-ignored, never committed
```

---

## Deployment

Live demo: **https://capisight.streamlit.app**

To deploy your own:
1. Push this folder to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo
3. Add `GROQ_API_KEY` in the Streamlit Cloud secrets UI
4. Deploy — Streamlit Cloud installs dependencies from `requirements.txt` automatically

**Note on free tier sleep:** Streamlit Community Cloud puts apps to sleep after inactivity. A first visitor may see a "waking up" screen. This is normal for free-tier hosting.

---

## Roadmap

**Near term**
- CSV template download so users know exactly what format to upload
- Persistent storage — save a portfolio across sessions
- Export scored portfolio as PDF report

**Experimental back half (post-investment review)**
Given time-series of a funded project's actual outcome metric versus its claimed target, attempt to detect whether and when the spend moved the outcome — with explicit uncertainty. This is methodologically hard on real single-firm data (confounders, non-random investment timing, short series). It is intended to be validated on synthetic data with a known injected lag before any real use, and clearly labeled experimental when built.

---

## Grounding and sources

- **Group by aim; evaluate each aim differently** — McKinsey, *Managing a moonshot: Keeping large industrial projects on track* (2019)
- **NPV / IRR / payback are the dominant real-world appraisal methods** — Graham & Harvey, *The Theory and Practice of Corporate Finance* (2001); Graham, *Corporate Finance and Reality* (2022)
- **DCF formula** — Brealey, Myers & Allen, *Principles of Corporate Finance* (13th ed.), Ch. 5
- **Throughput and OEE as manufacturing operational KPIs** — ISO 22400-2:2014; Nakajima, *Introduction to TPM* (1988)
- **Post-investment review as a recognized but often-missing step** — McKinsey (above); Finario, *FP&A from the Frontlines: Overcoming Obstacles to CapEx Post-Completion Reviews* (2023)
- **Capital allocation frameworks** — McKinsey, *Measuring the returns on capital allocation* (2021)

The multi-criteria scoring approach (min-max normalization, weighted sum, aim-based bucketing) is the author's own model built on these frameworks. Default weight profiles are a starting hypothesis, not a sourced prescription.

---

*Built by Rutwik Satish · MS Engineering Management, Northeastern University · © 2026*
