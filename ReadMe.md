# Capisight

**A CAPEX project scoring engine that ranks capital projects by their aim and allocates a budget across those aims, with an honest, transparent method.**

Capisight is the "front half" of a larger idea: it helps decide *where capital should go*. It groups capital-expenditure projects by what they are trying to achieve, scores each project on criteria that fit its aim, ranks projects within each aim, and then helps allocate a budget across aims.

> **Status:** working front half. The experimental causal "back half" (checking whether a funded project actually moved its target outcome) is a separate, deliberately-unbuilt module. See [Roadmap](#roadmap).

---

## Table of contents
- [What it does](#what-it-does)
- [Why it works this way](#why-it-works-this-way)
- [Quick start](#quick-start)
- [How to use it](#how-to-use-it)
- [How the scoring works](#how-the-scoring-works)
- [Visuals](#visuals)
- [Honesty notes](#honesty-notes-please-read)
- [Project structure](#project-structure)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [Grounding and sources](#grounding-and-sources)

---

## What it does

1. **Tags each project by aim.** Four aims: *regulatory / safety*, *business-as-usual*, *new growth*, *improve performance*.
2. **Scores projects on aim-appropriate criteria.** Each aim has its own weight profile across seven criteria (NPV, ROI, payback period, strategic score, operational impact, risk, cost). Weights are set with sliders and auto-normalize to 100%.
3. **Ranks projects within each aim** — not in one pooled list.
4. **Allocates a budget across aims.** You set a total budget and how it splits across aims. Within each aim, the highest-ranked projects are funded until that aim's share is used up. If a share cannot be fully used, the app explains why and prompts you to rebalance.
5. **Shows visuals** that respect the same rule: charts compare scores only *within* an aim, and compare money (cost, budget) across aims where that is genuinely valid. See [Visuals](#visuals).

## Why it works this way

The central design choice is **grouping by aim instead of ranking everything together.** A mandatory safety project and a speculative growth bet should not sit on the same ranked list, because they exist for different reasons and should be judged on different criteria. This follows McKinsey's argument (in *Managing a moonshot*) that capital projects are best grouped by aim, with evaluation metrics set per category.

A direct consequence: there is **no single cross-aim ranking**, and budget shares are **hard targets** — money does not move across aims automatically. If a 25% share for one aim cannot fund any of its projects, that money stays unallocated and the app tells you, rather than silently spending it on a different aim. This keeps the "aims are not comparable" principle intact and hands the trade-off back to you.

---

## Quick start

```bash
# 1. (optional) create a virtual environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. run
streamlit run app.py
```

The app opens in your browser (default `http://localhost:8501`).

---

## How to use it

1. **Edit the projects table.** Change any value, switch a project's aim via the dropdown, add rows, or delete rows. The sample projects are illustrative — replace them with your own.
2. **Tune the weights.** In the sidebar, pick an aim to edit, then set how much each criterion matters for that aim. Values are relative and auto-normalize to 100% within the aim. "Reset this aim to defaults" restores the starting profile.
3. **Read the within-aim rankings.** Each aim gets its own ranked table with a 0–1 score.
4. **Allocate the budget.** Set a total budget and the percentage share per aim. The app funds top-ranked projects within each share and clearly flags any unallocated money, with the reason, so you can rebalance.

---

## How the scoring works

Each criterion is **min-max normalized to 0–1 within an aim**, respecting its direction:

- *Higher is better* (NPV, ROI, strategic, operational): `(value − min) / (max − min)`
- *Lower is better* (payback, risk, cost): `(max − value) / (max − min)`
- If every project in an aim shares the same value for a criterion (or the aim has one project), that criterion scores `1.0` for everyone — it cannot discriminate, so it is treated as neutral rather than dividing by zero.

The **score** is the weighted sum of normalized criteria, using the aim's effective (normalized) weights. Because normalization happens *within* each aim, scores and ranks are only meaningful inside an aim — not across aims, by design.

Budget allocation uses a **greedy selection**: within each aim's share, projects are funded in rank order, taking each that fits and skipping ones that don't. Any leftover in a share is reported as *stranded* (the cheapest unfunded project costs more than the remainder) or *surplus* (the share more than covers every project in the aim).

---

## Visuals

Four charts, each built to respect the comparability rule (scores compare only within an aim; money compares across aims):

- **Per-aim ranking bars** — horizontal bars of each project's score, one chart per aim. Valid because all bars in a chart share that aim's weights.
- **Criteria breakdown** — for a project you pick, how each criterion's weighted contribution builds its score. The contributions sum exactly to the score, so the number is never a black box.
- **Cost vs. score (within an aim)** — a scatter to spot cheap high-scorers (top-left) versus expensive low-scorers. Kept within one aim so the score axis stays meaningful.
- **Budget: committed vs. unused per aim** — stacked bars showing how much of each aim's target was committed versus left unused. Comparing dollars across aims *is* valid, so this makes the stranded-money story visual.

Charts use Altair, which ships with Streamlit, so they add no meaningful deploy cost.

## Honesty notes (please read)

This project is built to be defensible, so its assumptions are stated openly rather than hidden:

- **The four aims are from McKinsey.** The *default weight profiles per aim* are a reasonable starting hypothesis, **not** a sourced prescription. Every weight is user-editable.
- **Sample projects and their aim tags are illustrative examples, not validated figures.** They demonstrate the mechanism. Replace them with real data before drawing any real conclusion.
- **The tool imposes structure and discipline, not opinions** about a firm's priorities. The weights, the aim of each project, and the budget shares are all your inputs.
- **Scores are comparable only within an aim,** never across aims. Cross-aim allocation is a *process* (set shares, fund the best per aim, rebalance), not a single formula.

---

## Project structure

```
capisight/
├── app.py              # the Streamlit application
├── requirements.txt    # Python dependencies
├── README.md           # this file
├── .gitignore          # excludes secrets and local cruft
├── .streamlit/
│   └── config.toml     # app theme/config
└── docs/
    └── HOW_IT_WORKS.md  # deeper explanation: method, design choices, and why
```

---

## Deployment

The app runs anywhere Streamlit runs. For a free hosted demo, Streamlit Community Cloud works (push this folder to a GitHub repo and deploy from it).

**One honest caveat about free hosting:** free tiers (Streamlit Community Cloud and similar) put apps to sleep after a period of inactivity, so a demo link may show a "waking up" screen to a first visitor. Options: accept the sleep, run a scheduled keep-alive that genuinely wakes the app (a simple HTTP ping returns a static shell and does *not* wake the Python process — you need a headless-browser visit), or use a paid always-on tier. Verify current free-tier and sleep policies before relying on them, as they change.

**Secrets (for the future back half):** if you later add an LLM layer, do **not** hard-code keys. Use Streamlit secrets — a local `.streamlit/secrets.toml` (git-ignored) and the host's secrets UI in production.

---

## Roadmap

- **Experimental causal back half.** Given time-series of a funded project's actual outcome metric (e.g. OEE, defect rate, throughput) versus its claimed target, attempt to detect whether and *when* the spend moved the outcome — with explicit uncertainty. This is methodologically hard on real single-firm data (confounders, non-random investment timing, short series), so its honest default output is often "too early to tell / can't identify." It is intended to be validated on synthetic data with a known injected lag before any real use, and to be clearly labeled experimental.

---

## Grounding and sources

- **Group by aim; evaluate each aim differently** — McKinsey, *Managing a moonshot: Keeping large industrial projects on track* (2019).
- **NPV / IRR / payback are standard appraisal methods** — Graham & Harvey, *The Theory and Practice of Corporate Finance* (2001); Graham, *Corporate Finance and Reality* (2022).
- **Operational outcome metrics (OEE, defect rate, throughput, etc.)** — standard manufacturing-KPI references (e.g. NetSuite's manufacturing KPI guide); used to inform the *menu* of outcome metrics for the future back half.
- **Post-investment review is a recognized but often-missing step** — McKinsey (above); PMI / APM capital-project KPI guidance; corporate-finance practitioner sources.

The original multi-criteria scoring approach (normalization, weighted sum, scenario weight profiles) is the author's own model; Capisight generalizes it with user-controlled weights and aim-based bucketing.
