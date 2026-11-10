"""
Smoke test for app.py WITHOUT real Streamlit or Plotly installed.

It replaces both with lightweight stand-ins and runs main() several times, including the
'Add to portfolio', 'Extract with AI' and 'Run extraction benchmark' flows with a fake AI model.
It catches crashes, typos and wrong function calls. It does NOT prove the page looks right:
run `streamlit run app.py` and click through every tab before you rely on it.

    python tests/smoke_ui.py
"""
import json
import os
import sys
import types
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CLICKED = set()          # button labels to treat as clicked on the next run
UPLOAD = {"file": None}  # what file_uploader returns for the document uploader


class SS(dict):
    def __getattr__(self, k):
        return self[k]

    def __setattr__(self, k, v):
        self[k] = v


class Fake:
    """Stand-in for the streamlit module, a column, a sidebar, or a container."""

    def __init__(self, session, root=True):
        self.session_state = session
        self.secrets = {}
        self.column_config = MagicMock()
        self.sidebar = Fake(session, root=False) if root else None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: MagicMock()

    # --- widgets that must return real values ---
    def selectbox(self, label, options, index=0, **k):
        options = list(options)
        return options[min(index, len(options) - 1)] if options else None

    def slider(self, label, *a, **k):
        key = k.get("key")
        if key and key in self.session_state:
            return self.session_state[key]
        if len(a) >= 3:
            return a[2]
        return k.get("value", a[0] if a else 0)

    def number_input(self, label, *a, **k):
        if len(a) >= 3:
            return a[2]
        return k.get("value", a[0] if a else 0)

    def text_input(self, label, value="", **k):
        return value

    def text_area(self, label, value="", **k):
        return value

    def checkbox(self, label, value=False, **k):
        return (label in CLICKED) or value

    toggle = checkbox

    def radio(self, label, options, **k):
        return list(options)[0]

    def button(self, label, *a, **k):
        return label in CLICKED

    def file_uploader(self, label, *a, **k):
        return UPLOAD["file"] if "Business case" in label else None

    def data_editor(self, df, **k):
        return df

    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [self for _ in range(n)]

    def tabs(self, labels):
        return [self for _ in labels]

    def expander(self, *a, **k):
        return self

    def spinner(self, *a, **k):
        return self

    def rerun(self):
        return None


def install_fakes():
    session = SS()
    sys.modules["streamlit"] = Fake(session)
    plotly = types.ModuleType("plotly")
    go = MagicMock()
    plotly.graph_objects = go
    sys.modules["plotly"] = plotly
    sys.modules["plotly.graph_objects"] = go
    return session


def fake_llm_factory(provider, key, model):
    def call(prompt):
        return json.dumps({
            "project_name": "Fake project", "suggested_aim": "New growth",
            "cost": {"value": 750000, "evidence": "Total capital cost: $750,000"},
            "npv": {"value": 500000, "evidence": "Net present value: $500,000"},
            "roi": {"value": None, "evidence": None},
            "payback": {"value": 3.2, "evidence": "Simple payback: 3.2 years"},
            "discount_rate_pct": {"value": 10, "evidence": "10% discount rate"},
            "useful_life_yrs": {"value": 8, "evidence": "8-year useful life"},
        })
    return call


def main():
    session = install_fakes()
    os.environ["GROQ_API_KEY"] = "test-key"
    import core
    core.make_llm_fn = fake_llm_factory
    import app

    # 1. default run on the demo portfolio
    app.main()
    assert len(session["projects"]) == 12, "demo portfolio should load"
    print("run 1 ok: demo portfolio renders on every tab")

    # 2. extraction -> review form -> add to portfolio
    class FakeUpload:
        name = "case.txt"

        def getvalue(self):
            return (b"Total capital cost: $750,000. Net present value: $500,000 at a 10% discount rate over an "
                    b"8-year useful life. Simple payback: 3.2 years.")
    UPLOAD["file"] = FakeUpload()
    CLICKED.add("Extract with AI")
    app.main()
    assert session["extraction"] and session["extraction"]["ok"], "extraction should have run"
    assert session["extraction"]["fields"]["cost"]["status"] == "verified"
    CLICKED.clear()
    UPLOAD["file"] = None
    CLICKED.add("Add to portfolio")
    app.main()
    assert len(session["projects"]) == 13, "extracted project should be added"
    assert session["projects"].iloc[-1]["scores_reviewed"] is False or not session["projects"].iloc[-1]["scores_reviewed"]
    CLICKED.clear()
    app.main()
    print("run 2 ok: extract -> review -> add to portfolio -> re-render")

    # 3. benchmark with the fake model
    CLICKED.add("Run extraction benchmark")
    app.main()
    assert session["bench_results"] and len(session["bench_results"]) == 10
    CLICKED.clear()
    app.main()
    print("run 3 ok: benchmark runs and scores")

    # 4. empty portfolio and a project with missing values must not crash
    app.clear_portfolio()
    app.main()
    import pandas as pd
    app.set_portfolio(pd.DataFrame([{"Project": "Half-filled", "Aim": "New growth", "cost": 100000}]))
    app.main()
    print("run 4 ok: empty and incomplete portfolios render")
    print("SMOKE OK")


if __name__ == "__main__":
    main()
