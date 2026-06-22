# How Capisight works: method, choices, and why

This document explains the *what*, *how*, and *why* in more depth than the README. It is written so that someone can follow the reasoning behind every design choice, including the ones that were deliberately rejected.

---

## 1. The problem Capisight addresses

Organizations are generally rigorous about *approving* capital spending but weaker at the surrounding discipline: deciding consistently across very different kinds of projects, stress-testing the assumptions those decisions rest on, and later checking whether the spend did what it promised.

Capisight focuses on the first two parts — making the *decision* of where capital goes structured, transparent, and defensible, and making the *assumptions* behind each project visible before commitment.

The origin of this tool: after interviewing for a manufacturing finance role, it became clear that teams were rigorous about capital approval processes but had no structured way to record what the business case promised, surface the assumptions underlying the NPV, or verify after the fact whether those assumptions held. Capisight was built to address that gap.

The appraisal methods involved (NPV, ROI, payback, DCF, multi-criteria scoring) are standard. Capisight's contribution is not new math — it is *structure*: how projects are grouped, how assumptions are captured, how priorities are made explicit, and how budget trade-offs are surfaced honestly.

---

## 2. The core idea: group by aim

The most important design decision is to **group projects by their aim and score each aim on its own criteria**, rather than ranking everything on one universal scale.

**Why.** Different projects exist for different reasons. A regulatory or safety project may have a poor financial return and still be mandatory. A growth project lives or dies on NPV and strategic upside. Ranking those two against each other on a single weighted score produces a number that means nothing — it implies a comparability that does not exist. McKinsey's *Managing a moonshot* makes this argument directly: sort projects by aim, and set evaluation metrics per category.

**The four aims** (from McKinsey):

| Aim | What it is | What it tends to care about |
|---|---|---|
| Regulatory / safety | Compliance and safety obligations | Often mandatory; risk and operational integrity over ROI |
| Business-as-usual | Maintaining current operations | Cost control and low risk |
| New growth | Pursuing new capacity or revenue | NPV, ROI, strategic upside |
| Improve performance | Making existing operations better | Operational gains: throughput, efficiency, quality |

> The aims are sourced. The *specific default weights* assigned to each aim in the app are a starting hypothesis, not a sourced prescription, and are fully editable.

---

## 3. AI document ingestion

In practice, CapEx business cases arrive as PDFs and Excel models — not as clean rows in a table. The highest friction point in any CapEx evaluation process is the manual re-keying of data from those documents into whatever scoring or tracking system the team uses.

v2 addresses this directly: the user uploads a business case document, and a language model (Groq, Llama 3, free API) reads the full text and extracts the relevant fields — capital cost, NPV, ROI, payback period, strategic alignment, operational impact, throughput improvement, risk score, discount rate, useful life, and up to three key assumptions. The extracted values are returned as structured JSON and presented to the user in editable fields before being added to the portfolio.

**Why this design matters.** The extraction step is a starting point, not a final answer. The human reviews and corrects before accepting. This is intentional: language models make extraction errors, especially on tables with unusual formatting, negative number conventions, or ambiguous units. The right workflow is AI handles the tedious first pass; the human makes the final call. The app badges AI-extracted projects distinctly from manually entered ones throughout the interface so provenance is always visible.

**What the extraction prompt asks for.** The prompt is structured to return only valid JSON with exactly the required fields. It asks the model to estimate values it cannot find directly (strategic alignment score, risk score) from context, and to mark estimated values explicitly. Confidence is returned as high, medium, or low. The prompt limits input to 8,000 characters to stay within token constraints while covering most business case documents.

---

## 4. The scoring method

Within a single aim, for each project:

1. **Normalize each criterion to 0–1.** Min-max scaling, respecting direction:
   - Higher-is-better: `(value − min) / (max − min)`
   - Lower-is-better: `(max − value) / (max − min)`
   - Degenerate case (all equal, or one project): score `1.0` — the criterion cannot discriminate, so it is treated as neutral rather than undefined.
2. **Normalize the weights** so they sum to 1.0. The user sets relative importance with sliders; the app handles normalization. The user never has to do mental arithmetic to keep weights summing to 100%.
3. **Weighted sum.** `score = Σ (normalized_criterion × effective_weight)`. Result is in 0–1.
4. **Rank within the aim** by score.

**Why normalize within the aim, not globally?** Because a score is only a fair comparison among projects judged on the same weights. Normalizing across aims would smuggle back the cross-aim comparison we deliberately rejected.

**Why user-controlled weights?** There is no universal correct weight for NPV versus risk — real firms set these from their own strategy. The honest design moves the judgment from the tool's author to the user, and shows both the raw slider input and the resulting effective percentage so nothing is hidden.

### The eight criteria

| Criterion | Direction | Rationale |
|---|---|---|
| NPV (USD) | Higher | Primary financial return measure (Graham & Harvey 2001) |
| ROI (%) | Higher | Return relative to capital invested |
| Payback period (years) | Lower | Liquidity and risk proxy; widely used by CFOs |
| Strategic score (1–10) | Higher | Alignment with organizational priorities |
| Operational impact (1–10) | Higher | Effect on day-to-day operations |
| Throughput improvement (%) | Higher | Manufacturing-specific KPI; added in v2 |
| Risk score (1–10) | Lower | Implementation and delivery risk |
| Estimated cost (USD) | Lower | Capital efficiency |

**Why throughput was added in v2.** The original seven criteria were primarily financial and strategic. Manufacturing operations teams make CapEx decisions primarily on operational outcomes — does this machine improve throughput, reduce cycle time, reduce defect rate? Throughput improvement as a percentage is a standard manufacturing KPI (ISO 22400-2, Nakajima TPM framework) and was the most significant gap in the v1 scoring model.

---

## 5. Assumption transparency

Every project in the portfolio stores the key assumptions its business case rests on: discount rate, useful life, demand growth, cost escalation, headcount changes, or whatever the proposer claimed. These assumptions are displayed in two places: the Score Breakdown tab (alongside the score) and the Sensitivity tab (alongside the stress tests).

**Why this matters.** Most CapEx processes record what was approved and how much was spent, but not what the business case promised operationally. When a post-investment review is attempted — and Finario's own research notes that most organizations talk about reviews but do not do them — the original assumptions have usually been lost. Recording them at the point of approval is the minimum required to make any future review possible.

---

## 6. DCF sensitivity analysis

The sensitivity tab recalculates NPV and payback from first principles under five scenarios using the standard discounted cash flow formula.

**Formula:**

```
NPV = Σ(CF_t / (1+r)^t  for t = 1 to n) − C0
```

Where:
- `CF_t` = annual cash inflow (derived from ROI × C0 ÷ n, assuming uniform cash flows)
- `r` = discount rate per period
- `n` = useful life in years
- `C0` = initial capital cost

Simple payback = C0 ÷ annual CF (undiscounted).

**The five scenarios:**
1. Base case — user's inputs as submitted
2. Discount rate +2pp — tests hurdle rate sensitivity
3. Discount rate +5pp — significant tightening scenario
4. Revenue or savings down X% — tests demand or price risk (user-set)
5. Capital cost overrun +X% — tests implementation risk (user-set)

**Source:** Brealey, Myers & Allen, *Principles of Corporate Finance* (13th ed.), Ch. 5.

**What was deliberately rejected: fabricated multipliers.** An earlier version of this module applied flat percentage multipliers to NPV and payback to simulate scenarios (for example, multiplying NPV by 0.82 to simulate a discount rate increase). This was rejected because the relationship between a discount rate change and NPV impact is not a fixed multiplier — it depends entirely on the project's cash flow timing, growth rate, and terminal value. Applying a flat multiplier to every project regardless of its financial structure is not sensitivity analysis; it is invented numbers. The current implementation derives NPV from the formula so the math is correct and traceable.

**Limitation stated explicitly:** uniform cash flows are a simplification. Projects with non-uniform cash flows require a full cash flow schedule. This limitation is disclosed in the UI and in the README.

---

## 7. Budget allocation across aims

Because aims are not comparable on one scale, the budget step is a **process**, not a single optimization:

1. The user sets a total budget and a percentage share per aim.
2. Within each aim's share, projects are funded greedily in rank order.
3. Any money a share cannot use is reported with the reason.

**The stranded-money problem and why it is surfaced, not solved.** Three options were considered:

- **Spillover** (unused share flows to other aims): rejected. It quietly destroys the "aims are not comparable" principle.
- **Leave it silent**: rejected as too passive. The user is left to notice the gap themselves.
- **Targets with the gap surfaced** (chosen): shares are hard targets; the app funds what fits and reports exactly how much is stranded and why, with a prompt to rebalance.

The stranded money is not a flaw to engineer away — it is a signal that the budget split does not match the real project costs. The right behavior is to amplify that signal and hand the decision back to the user.

---

## 8. What Capisight deliberately does not do

- Produce a single cross-aim leaderboard
- Move budget across aims automatically
- Claim its sample data or default weights are validated
- Make the sensitivity analysis look more precise than it is — the uniform cash flow limitation is disclosed everywhere it appears
- Verify whether a funded project delivered its promised outcome — that is the separate, harder, experimental back half described below

---

## 9. The intended back half (context, not yet built)

The larger concept pairs this decision tool with a **post-investment feedback layer**: given a funded project's claimed target and its actual operational metric over time, attempt to detect whether and when the spend actually moved the outcome.

This is methodologically hard on real single-firm data: investment timing is not random, confounders are pervasive (co-occurring product launches, demand shifts, seasonal effects), and there is rarely a clean control group. The honest output is therefore often "too early to tell" or "cannot identify."

The intended approach is to validate the method on synthetic data with a known injected lag — proving it recovers the true effect when one exists, and correctly reports no effect on a null case — before applying it to real data. It would be labeled clearly as experimental. It is described here for context; it is not part of this build.

---

## 10. Interface design choices

The app uses portfolio-level KPI cards (counts and dollars only, never a cross-aim score), tabbed sections (Ingest Document, Projects, Rankings, Score Breakdown, Sensitivity, Cost vs Score, Budget), and Plotly charts.

**Light theme in v2.** v1 used a dark terminal aesthetic. v2 switched to a clean light theme for one practical reason: finance teams evaluate this kind of tool in a work context alongside Excel and other tools that are predominantly light-themed. A tool that requires eye adjustment to use alongside a spreadsheet is harder to adopt.

**AI-extracted project badging.** Projects ingested from documents are visibly distinguished from manually entered ones throughout the interface. This keeps provenance visible and reminds reviewers which values came from AI extraction and which were entered directly.

**Chart heights scale with item count.** Horizontal bar charts scale their height based on the number of projects so axis labels never overlap regardless of portfolio size.

**Score charts scoped to a single aim.** Every score visualization is scoped to one aim so the interface cannot imply a cross-aim comparison the method deliberately rejects.

---

## Sources

- McKinsey, *Managing a moonshot: Keeping large industrial projects on track* (2019) — aim-based grouping
- Graham & Harvey, *The Theory and Practice of Corporate Finance*, Journal of Financial Economics 60(2-3): 187–243 (2001) — NPV and payback as dominant real-world methods
- Graham, *Corporate Finance and Reality* (2022) — updated survey on capital budgeting practice
- Brealey, Myers & Allen, *Principles of Corporate Finance* (13th ed.), Ch. 5 — DCF formula
- ISO 22400-2:2014 — manufacturing KPI definitions including throughput and OEE
- Nakajima, *Introduction to TPM* (1988) — throughput and OEE as operational benchmarks
- Finario, *FP&A from the Frontlines: Overcoming Obstacles to CapEx Post-Completion Reviews* (2023) — post-investment review as a recognized but rarely practiced step
- McKinsey, *Measuring the returns on capital allocation* (2021) — capital allocation frameworks
