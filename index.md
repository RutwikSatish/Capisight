<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Capisight &mdash; CAPEX project scoring</title>
<style>
  :root{
    --bg:#0f1311; --surface:#161b18; --line:#283330;
    --ink:#e8ede9; --muted:#9aa6a0; --faint:#6f7a75;
    --green:#1D9E75; --green-d:#0F6E56; --purple:#7F77DD; --coral:#D85A30;
    --radius:14px; --maxw:880px;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.65; font-size:17px;
  }
  a{color:var(--green); text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:var(--maxw); margin:0 auto; padding:0 22px}

  header{padding:84px 0 56px; border-bottom:1px solid var(--line)}
  .eyebrow{color:var(--green); font-size:13px; letter-spacing:.14em; text-transform:uppercase; margin:0 0 14px}
  h1{font-size:46px; line-height:1.08; margin:0 0 18px; font-weight:650; letter-spacing:-.02em}
  .lede{font-size:20px; color:var(--muted); max-width:640px; margin:0 0 30px}
  .cta{display:flex; gap:12px; flex-wrap:wrap}
  .btn{display:inline-block; padding:12px 20px; border-radius:10px; font-size:15px; font-weight:600; border:1px solid var(--line)}
  .btn.primary{background:var(--green); color:#06120d; border-color:var(--green)}
  .btn.primary:hover{background:#23b487; text-decoration:none}
  .btn.ghost{color:var(--ink)}
  .btn.ghost:hover{border-color:var(--green); text-decoration:none}

  section{padding:54px 0; border-bottom:1px solid var(--line)}
  h2{font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:var(--faint); margin:0 0 26px; font-weight:600}
  h3{font-size:21px; margin:0 0 8px; font-weight:600; letter-spacing:-.01em}
  p{margin:0 0 16px}
  .muted{color:var(--muted)}

  .steps{counter-reset:step; list-style:none; padding:0; margin:0; display:grid; gap:22px}
  .steps li{position:relative; padding-left:52px}
  .steps li::before{
    counter-increment:step; content:counter(step);
    position:absolute; left:0; top:-2px; width:34px; height:34px; border-radius:9px;
    background:var(--surface); border:1px solid var(--line); color:var(--green);
    display:flex; align-items:center; justify-content:center; font-weight:700; font-size:15px;
  }

  .grid{display:grid; grid-template-columns:1fr 1fr; gap:16px}
  .card{background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:22px}
  .card h3{font-size:18px}
  .card p{font-size:15px; color:var(--muted); margin:0}
  .tag{display:inline-block; font-size:12px; color:var(--green); border:1px solid var(--green-d); border-radius:999px; padding:2px 10px; margin-bottom:12px}

  .why{background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:26px 28px}
  .why p:last-child{margin-bottom:0}

  .note{font-size:14px; color:var(--faint); border-left:3px solid var(--line); padding:4px 0 4px 16px; margin:8px 0}

  ul.clean{margin:0; padding-left:20px}
  ul.clean li{margin-bottom:9px; color:var(--muted)}
  ul.clean li b{color:var(--ink); font-weight:600}

  .placeholder{background:#1a120c; border:1px dashed var(--coral); border-radius:10px; padding:14px 16px; font-size:14px; color:#e8a884}
  code{background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:1px 6px; font-size:14px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--ink)}

  footer{padding:40px 0 70px; color:var(--faint); font-size:14px}
  @media(max-width:640px){
    h1{font-size:34px} .lede{font-size:18px} .grid{grid-template-columns:1fr}
    header{padding:56px 0 40px}
  }
</style>
</head>
<body>

<header>
  <div class="wrap">
    <p class="eyebrow">CAPEX decision tool</p>
    <h1>Capisight</h1>
    <p class="lede">Score capital projects by what they&rsquo;re for, rank them within each aim, and allocate a budget across aims &mdash; with a method that stays honest about what it can and can&rsquo;t compare.</p>
    <div class="cta">
      <!-- Live Streamlit app -->
      <a class="btn primary" href="https://capisight.streamlit.app/" id="app-link">Try the live app</a>
      <!-- GitHub repository -->
      <a class="btn ghost" href="https://github.com/RutwikSatish/Capisight" id="repo-link">View the code</a>
    </div>
  </div>
</header>

<section>
  <div class="wrap">
    <h2>What it does</h2>
    <ol class="steps">
      <li><h3>Tags each project by its aim</h3><p class="muted">Regulatory / safety, business-as-usual, new growth, or improve performance.</p></li>
      <li><h3>Scores on aim-appropriate criteria</h3><p class="muted">Each aim has its own weight profile across seven criteria (NPV, ROI, payback, strategic, operational, risk, cost). Weights are sliders that auto-normalize to 100%.</p></li>
      <li><h3>Ranks projects within each aim</h3><p class="muted">Not in one pooled list &mdash; a mandatory safety project and a growth bet are never ranked against each other.</p></li>
      <li><h3>Allocates a budget across aims</h3><p class="muted">You set a total and a share per aim. If a share can&rsquo;t be fully used, the app shows how much is stranded and why, and asks you to rebalance.</p></li>
    </ol>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Why it works this way</h2>
    <div class="why">
      <p>The central choice is <b>grouping by aim instead of ranking everything together.</b> Different projects exist for different reasons: a safety project may have a poor return and still be mandatory, while a growth bet lives or dies on NPV. Scoring them on one shared scale produces a number that implies a comparability that doesn&rsquo;t exist.</p>
      <p>This follows McKinsey&rsquo;s argument (in <em>Managing a moonshot</em>) that capital projects are best grouped by aim, with evaluation criteria set per category.</p>
      <p>A direct consequence: there is <b>no single cross-aim ranking</b>, and budget shares are <b>hard targets</b> &mdash; money is never moved across aims automatically. Stranded money is surfaced as a signal to rebalance, not quietly spent elsewhere. The tool makes the trade-off visible and hands the decision back to you.</p>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>The visuals</h2>
    <div class="grid">
      <div class="card"><span class="tag">within an aim</span><h3>Per-aim ranking bars</h3><p>Each project&rsquo;s score as horizontal bars, one chart per aim. Valid because all bars share that aim&rsquo;s weights.</p></div>
      <div class="card"><span class="tag">transparent</span><h3>Criteria breakdown</h3><p>For a chosen project, how each criterion&rsquo;s weighted contribution builds its score. Contributions sum exactly to the score.</p></div>
      <div class="card"><span class="tag">within an aim</span><h3>Cost vs. score</h3><p>A scatter to spot cheap high-scorers versus expensive low-scorers, kept inside one aim so the score axis stays meaningful.</p></div>
      <div class="card"><span class="tag">across aims</span><h3>Budget: committed vs. unused</h3><p>Stacked bars per aim. Comparing dollars across aims <em>is</em> valid, so this makes the stranded-money story visual.</p></div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Honesty notes</h2>
    <ul class="clean">
      <li>The <b>four aims are from McKinsey.</b> The default weight profiles per aim are a starting hypothesis, not a sourced prescription &mdash; every weight is editable.</li>
      <li><b>Sample projects and their aim tags are illustrative examples,</b> not validated figures. Replace them with real data before drawing real conclusions.</li>
      <li>The tool imposes <b>structure and discipline, not opinions</b> about a firm&rsquo;s priorities. Weights, aims, and budget shares are all your inputs.</li>
      <li>Scores are comparable <b>only within an aim,</b> never across aims.</li>
    </ul>
    <p class="note">A causal &ldquo;back half&rdquo; (checking whether a funded project actually moved its target outcome) is scoped but deliberately not built here, because it is methodologically hard on real single-firm data and its honest output is often &ldquo;too early to tell.&rdquo;</p>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Run it yourself</h2>
    <p class="muted">Clone the repo, then:</p>
    <p><code>pip install -r requirements.txt</code> &nbsp;then&nbsp; <code>streamlit run capex_scoring_app.py</code></p>
    <p class="muted" style="font-size:15px">Full detail on the method and design choices is in <code>How_it_works.md</code>.</p>
  </div>
</section>

<footer>
  <div class="wrap">
    Capisight &mdash; a CAPEX project scoring engine. Built as a portfolio project. Grounded in McKinsey (group-by-aim), Graham &amp; Harvey (NPV/IRR as standard appraisal), and standard manufacturing-KPI references.
  </div>
</footer>

</body>
</html>
