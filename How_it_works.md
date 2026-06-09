# How Capisight works: method, choices, and why

This document explains the *what*, *how*, and *why* in more depth than the README. It is written so that someone can follow the reasoning behind every design choice, including the ones that were deliberately rejected.

---

## 1. The problem Capisight addresses

Organizations are generally rigorous about *approving* capital spending but weaker at the surrounding discipline: deciding consistently across very different kinds of projects, and later checking whether the spend did what it promised. Capisight focuses on the first part — making the *decision* of where capital goes structured, transparent, and defensible.

The appraisal methods involved (NPV, ROI, payback, multi-criteria scoring) are standard. Capisight's contribution is not new math; it is *structure*: how projects are grouped, how priorities are made explicit, and how budget trade-offs are surfaced honestly.

---

## 2. The core idea: group by aim

The most important design decision is to **group projects by their aim and score each aim on its own criteria**, rather than ranking everything on one universal scale.

**Why.** Different projects exist for different reasons. A regulatory or safety project may have a poor financial return and still be mandatory. A growth project lives or dies on NPV and strategic upside. Ranking those two against each other on a single weighted score produces a number that means nothing — it implies a comparability that does not exist. McKinsey's *Managing a moonshot* makes this argument directly: sort projects by aim, and set evaluation metrics per category.

**The four aims** (from McKinsey):

| Aim | What it is | What it tends to care about |
|---|---|---|
| Regulatory / safety | Compliance / safety obligations | Often mandatory; risk and operational integrity over ROI |
| Business-as-usual | Maintaining current operations | Cost control and low risk |
| New growth | Pursuing new capacity / revenue | NPV, ROI, strategic upside |
| Improve performance | Making existing operations better | Operational gains (throughput, efficiency, quality) |

> The aims are sourced. The *specific default weights* assigned to each aim in the app are a starting hypothesis, not a sourced prescription, and are fully editable.

---

## 3. The scoring method

Within a single aim, for each project:

1. **Normalize each criterion to 0–1.** Min-max scaling, respecting direction:
   - higher-is-better: `(value − min) / (max − min)`
   - lower-is-better: `(max − value) / (max − min)`
   - degenerate case (all equal, or one project): score `1.0` — the criterion can't discriminate, so it is neutral rather than undefined.
2. **Normalize the weights** so they sum to 1.0. The user sets *relative* importance with sliders; the app handles making them sum correctly. The user never has to do mental arithmetic to keep weights adding to 100%.
3. **Weighted sum.** `score = Σ (normalized_criterion × effective_weight)`. Result is in 0–1.
4. **Rank within the aim** by score.

**Why normalize within the aim, not globally?** Because a score is only a fair comparison among projects judged on the same weights. Normalizing across aims would smuggle back the cross-aim comparison we deliberately rejected.

**Why user-controlled weights?** There is no universal "correct" weight for NPV versus risk — real firms set these from their own strategy. So the honest design moves the judgment from the tool's author to the user, and shows both the raw slider input and the resulting effective percentage so nothing is hidden.

---

## 4. Budget allocation across aims

Because aims are not comparable on one scale, the budget step is a **process**, not a single optimization:

1. The user sets a **total budget** and a **percentage share per aim**.
2. Within each aim's share, projects are funded **greedily in rank order** — take each that fits, skip those that don't, keep going.
3. Any money a share cannot use is reported, with the reason.

**The stranded-money problem (and why it is surfaced, not solved).**
Splitting a budget by aim *before* seeing project costs can leave money unused: an aim's cheapest project may cost more than its entire share. Three ways to handle this were considered:

- **Spillover** (unused share flows to other aims): rejected. It spends more of the budget but quietly destroys the "aims are not comparable" principle — it lets one aim's money become another's.
- **Leave it silent** (just fund what fits): rejected as too passive. The user is left to notice the gap themselves.
- **Targets with the gap surfaced** (chosen): shares are hard targets; the app funds what fits and then says, per aim, exactly how much is stranded and why (e.g. "the cheapest unfunded project costs more than the leftover"), with a prompt to rebalance.

**Why the chosen option is best.** The stranded money is not a flaw to engineer away — it is a *signal* that the budget split doesn't match the real project costs. The right behavior is to amplify that signal and hand the decision back to the user, consistent with the principle that the human makes the trade-off and the tool makes it visible.

---

## 5. What Capisight deliberately does *not* do

- It does not produce a single cross-aim leaderboard.
- It does not move budget across aims automatically.
- It does not claim its sample data or default weights are validated.
- It does not (yet) attempt to verify whether a funded project delivered its promised outcome — that is the separate, harder, experimental "back half".

---

## 6. The intended back half (context, not built here)

The larger concept pairs this decision tool with a **post-investment feedback layer**: given a funded project's claimed target and its actual operational metric over time, attempt to detect whether — and *when* — the spend actually moved the outcome.

This is methodologically hard on real single-firm data: investment timing is not random, confounders are pervasive (co-occurring product launches, demand shifts), and there is rarely a clean control. The honest output is therefore often "too early to tell" or "can't identify". The intended approach is to validate the method on **synthetic data with a known injected lag** (proving it recovers the true effect, and correctly reports no effect on a null case) and to label the module clearly as experimental. It is described here for context; it is not part of this build.


---

## 7. Interface

The app uses portfolio-level KPI cards (counts and dollars only — never a cross-aim score), tabbed sections (Projects, Rankings, Why a score, Cost vs score, Budget), and Plotly charts. Chart heights scale with the number of items so axis labels never overlap, and every score chart is scoped to a single aim so the visuals cannot imply a cross-aim comparison the method rejects.
