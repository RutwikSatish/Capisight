# Capisight v3: CapEx prioritization prototype

Helps an analyst **screen and compare capital projects**, check that a business case's own numbers agree,
stress-test them, allocate a budget, and try AI-assisted extraction of figures from documents.

Built with AI-assisted development (Streamlit + Python). It is a **prototype and decision-support aid**, not a valuation
tool or a system of record.

## Quick start
```bash
pip install -r requirements.txt
streamlit run app.py
```
AI extraction is optional. To enable it, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add a key.
**Do not upload confidential documents**: text is sent to the AI provider you select.

## What changed from v2
| v2 problem | v3 |
|---|---|
| Sample data contradicted itself (e.g. stated NPV +$400K vs about -$73K implied by its own payback, rate and life) and the sensitivity tab hid it by anchoring to the stated NPV | **Consistency check** flags stated-vs-implied NPV gaps; stress tests run on the model, not the stated NPV |
| Docstring promised "source citations" but extraction returned none | Every extracted figure must come with a **verbatim quote**; the app checks the quote exists in the document and contains the number |
| AI guessed strategic/operational/risk scores that drove rankings | Prompt does not ask for them; you set them, and a "scores reviewed" flag is shown |
| `llama3-8b-8192` used for extraction | That model ID was shut down by Groq on 08/30/25, and its replacement `llama-3.1-8b-instant` is scheduled for shutdown 08/16/26. Model is now configurable; default `openai/gpt-oss-20b`; Anthropic also supported. **Check Groq's current model list.** |
| Silent 8,000-character cut-off | 30,000 characters, with an explicit warning showing how much was ignored |
| "[estimated]" marker conflicted with numeric JSON | Removed. Unknown means null |
| Missing numbers became 0 (a payback of 0 looks perfect) | Missing stays blank; incomplete projects are excluded and listed |
| One-project aims scored a perfect 1.0 | Neutral 0.5, plus a warning when an aim has fewer than 4 projects |
| Greedy budget selection | Exact 0/1 knapsack, compared with greedy; regulatory/safety can be funded first |
| UI said Word files work (they were not accepted) | `.docx` supported |
| No evidence the AI extraction works | **Extraction benchmark tab**: 10 synthetic documents with hand-labelled answers |
| Manufacturing-only | **Site deal tab**: tower/pole colocation cash flows and pole-to-macro break-even (placeholder inputs) |

## Demo data (all synthetic)
`data/demo_projects.csv`: 12 projects across the four aims. Stated NPVs are computed from each project's own payback, rate and
life, **except two planted inconsistencies** so the checker has something real to find:
- *Quality Inspection System*: stated NPV $280,000 vs about $41,500 implied (Inconsistent)
- *Warehouse Conveyor*: stated NPV $120,000 vs about $78,900 implied (Review)

`data/business_cases/`: 10 short business-case documents plus `ground_truth.csv` (the answer key).
Cases include different layouts, units ($0.38 million, 42 months, "2 years and 8 months"), distractor figures, a scenario
document, a table, negative NPVs (parentheses and minus sign), spelled-out numbers, and a document with almost no figures.

## Measuring extraction accuracy
Open the **Extraction benchmark** tab and run it with your configured model. Record the results here (they depend on the model):

| Date | Provider / model | Field accuracy | Invented figures | Missed | Wrong | Marked verified but wrong |
|---|---|---|---|---|---|---|
| (not yet run) | | | | | | |

The number to watch is **marked verified but wrong**: mistakes a hurried reviewer would trust.

## Tests
```bash
python -m unittest discover -s tests -v     # 34 tests of the calculation and verification logic
python tests/smoke_ui.py                     # UI smoke test using stand-ins for Streamlit/Plotly
```
**Test status when this was written:** the logic in `core.py` is unit-tested (including a brute-force check that the knapsack is optimal
and a check that every labelled number in the demo documents is actually readable from its document). The interface was only
smoke-tested with stand-ins and has not been run in a real Streamlit session. No live AI call has been made. Click through every
tab yourself and run the benchmark before relying on any of it.

## Method and sources
- Grouping by aim: McKinsey, "Managing a moonshot: Keeping large industrial projects on track" (four aims: regulatory/safety,
  business-as-usual, new growth, improve performance).
- Implied NPV uses uniform year-end cash flows: annual cash flow = cost / payback, discounted at the stated rate over the stated life.
- Consistency thresholds (gap as a share of capital cost): up to 10% Consistent, up to 25% Review, above that or a sign flip Inconsistent.
  These thresholds are judgment calls, not standards.
- Site-deal escalator context: older SBA Communications 10-K filings describe tenant escalators around 3-4% a year and ground-lease
  escalators around 2-3%; American Tower has described U.S. escalators averaging about 3%. Pull the latest filings and cite the year.
  All other site-deal defaults are **placeholders**.

## Known limits
- Uniform cash flows; no taxes, working capital, financing or terminal value (except an optional terminal multiple on the site tab).
- Scores are relative inside a small group and weights are editable hypotheses.
- "Verified" means the quote exists and contains the number, not that it is the right number for the project.
- Data lives in the browser session. Refreshing the page loses edits: use **Download portfolio (CSV)** and re-import.
- No user accounts, audit trail or database. Do not treat as a system of record.
