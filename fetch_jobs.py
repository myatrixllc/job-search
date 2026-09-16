from jobspy import scrape_jobs
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import os

# ─────────────────────────────────────────────
# FILTER CONFIGURATION
# ─────────────────────────────────────────────

TITLE_INCLUDE = [
    "vice president", "vp", "managing director", "senior director",
    "sr. director", "sr director", "head of", "executive director", "avp"
]

TITLE_EXCLUDE = [
    "sales", "marketing", "finance", "hr", "human resources",
    "product manager", "recruiter", "account manager", "operations manager",
    "business development", "clinical", "medical", "legal", "supply chain",
    "sap", "google coe", "delivery lead", "reinsurance", "retail media",
    "catastrophe", "real-world evidence", "radiolog", "nursing", "physician",
    "grc", "governance, risk", "risk and compliance", "security officer",
    "information security", "cybersecurity", "ciso", "penetration",
    "quant", "quantitative", "actuar", "underwr", "claims adjuster",
    "product management", "customer success", "account executive",
    "global systems integrator", "channel partner", "alliances"
]

DOMAIN_KEYWORDS = [
    "data platform", "data engineering", "enterprise data", "data architecture",
    "data strategy", "data governance", "ai", "genai", "generative ai",
    "machine learning", "mlops", "databricks", "snowflake", "lakehouse",
    "cloud data", "aws", "gcp", "platform engineering", "software engineering",
    "healthcare", "health plan", "payer", "fhir", "hl7", "interoperability",
    "data products", "analytics", "data science", "data infrastructure",
    "semantic", "rag", "llm", "agentic", "responsible ai",
    "data management", "data architect", "artificial intelligence",
    "data analytics", "intelligence", "telemetry"
]

MIN_SCORE   = 1
MIN_SALARY  = 180000

# Companies already applied to — shown with a checkmark in the report
APPLIED_COMPANIES = [
    "WEX", "TIAA", "Optum", "Vituity", "Devoted Health",
    "Abbott", "Experian", "SCA Health"
]

# ─────────────────────────────────────────────
# FILTER FUNCTIONS
# ─────────────────────────────────────────────

def filter_by_title(title):
    if not title:
        return False
    t = title.lower()
    has_level   = any(kw in t for kw in TITLE_INCLUDE)
    is_excluded = any(kw in t for kw in TITLE_EXCLUDE)
    return has_level and not is_excluded


def score_role(title, description):
    t = (title or "").lower()
    d = description.lower() if isinstance(description, str) else ""
    combined = t + " " + d
    return sum(1 for kw in DOMAIN_KEYWORDS if kw in combined)


def salary_str(row):
    mn = row.get("min_amount")
    mx = row.get("max_amount")
    if pd.notna(mn) and pd.notna(mx):
        return f"${int(mn):,} – ${int(mx):,}"
    elif pd.notna(mn):
        return f"${int(mn):,}+"
    elif pd.notna(mx):
        return f"up to ${int(mx):,}"
    return "Not listed"


def salary_val(row):
    mn = row.get("min_amount")
    return int(mn) if pd.notna(mn) else 0


def salary_passes(row):
    mn = row.get("min_amount")
    mx = row.get("max_amount")
    if pd.notna(mn) and mn < MIN_SALARY:
        return False
    if pd.notna(mx) and mx < MIN_SALARY:
        return False
    return True


def match_pct(score):
    return min(int(score / 8 * 100), 100)


def clean_location(loc):
    if not isinstance(loc, str) or loc.strip().lower() in ("nan", ""):
        return "Remote / Not listed"
    parts = loc.split(",")
    if len(parts) >= 2:
        return f"{parts[0].strip()}, {parts[1].strip()}"
    return loc.strip()


# ─────────────────────────────────────────────
# HTML REPORT
# ─────────────────────────────────────────────

def generate_html_report(jobs_data, date_str, total_raw):
    high       = sum(1 for j in jobs_data if j["score"] >= 5)
    with_sal   = sum(1 for j in jobs_data if j["salval"] > 0)
    applied_js = json.dumps(APPLIED_COMPANIES)
    jobs_js    = json.dumps(jobs_data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Job Match Report — {date_str}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
:root{{
  --bg:#F0F4F8;--surface:#FFF;--surface2:#F8FAFC;
  --border:#E2E8F0;--border2:#CBD5E1;
  --navy:#1E3A5F;--navy-l:#EEF3F9;
  --text:#0F172A;--text2:#475569;--text3:#94A3B8;
  --green:#166534;--green-bg:#DCFCE7;--green-b:#86EFAC;
  --amber:#92400E;--amber-bg:#FEF3C7;--amber-b:#FCD34D;
  --blue:#1D4ED8;--blue-bg:#DBEAFE;--blue-b:#93C5FD;
  --gray:#374151;--gray-bg:#F3F4F6;--gray-b:#D1D5DB;
  --sh:0 1px 3px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.06);
  --sh2:0 4px 6px -1px rgba(0,0,0,.08);
}}
@media(prefers-color-scheme:dark){{
  :root:not([data-theme="light"]){{
    --bg:#0A0F1E;--surface:#111827;--surface2:#1F2937;
    --border:#1F2937;--border2:#374151;
    --navy:#60A5FA;--navy-l:#1E3A5F;
    --text:#F1F5F9;--text2:#94A3B8;--text3:#64748B;
    --green:#4ADE80;--green-bg:#052E16;--green-b:#166534;
    --amber:#FCD34D;--amber-bg:#2D1B00;--amber-b:#92400E;
    --blue:#93C5FD;--blue-bg:#1E3A5F;--blue-b:#1D4ED8;
    --gray:#D1D5DB;--gray-bg:#1F2937;--gray-b:#374151;
  }}
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.6}}
.page{{max-width:1060px;margin:0 auto;padding:28px 20px}}
.hdr{{background:var(--navy);border-radius:14px;padding:24px 28px;margin-bottom:20px;color:#fff;box-shadow:var(--sh2)}}
.hdr-in{{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:14px}}
.hdr h1{{font-size:19px;font-weight:700;letter-spacing:-.3px;opacity:.95}}
.hdr p{{font-size:11.5px;opacity:.6;margin-top:3px}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap}}
.kpi{{text-align:center;background:rgba(255,255,255,.1);border-radius:9px;padding:10px 16px;min-width:74px;backdrop-filter:blur(4px)}}
.kpi-n{{font-size:24px;font-weight:700;display:block;line-height:1}}
.kpi-l{{font-size:10px;opacity:.65;text-transform:uppercase;letter-spacing:.5px;margin-top:3px;display:block}}
.notice{{background:var(--navy-l);border-left:3px solid var(--navy);border-radius:0 7px 7px 0;padding:9px 13px;font-size:12px;color:var(--text2);margin-bottom:14px}}
.ctrls{{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap;align-items:center}}
.sw{{flex:1;min-width:180px;position:relative}}
.sw input{{width:100%;padding:8px 13px 8px 34px;border:1px solid var(--border2);border-radius:7px;background:var(--surface);color:var(--text);font-family:inherit;font-size:13px;outline:none;transition:border .15s}}
.sw input:focus{{border-color:var(--navy)}}
.si{{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--text3);pointer-events:none}}
.pills{{display:flex;gap:5px;flex-wrap:wrap}}
.pill{{padding:5px 12px;border-radius:18px;border:1px solid var(--border2);background:var(--surface);color:var(--text2);font-size:11.5px;font-weight:500;cursor:pointer;transition:all .15s;font-family:inherit;white-space:nowrap}}
.pill:hover{{border-color:var(--navy);color:var(--navy)}}
.pill.on{{background:var(--navy);color:#fff;border-color:var(--navy)}}
.tw{{background:var(--surface);border-radius:11px;box-shadow:var(--sh);overflow:hidden;border:1px solid var(--border)}}
table{{width:100%;border-collapse:collapse}}
thead{{background:var(--surface2);border-bottom:2px solid var(--border2)}}
th{{padding:10px 15px;text-align:left;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.7px;color:var(--text2);white-space:nowrap;cursor:pointer;user-select:none}}
th:hover{{color:var(--navy)}}
td{{padding:13px 15px;border-bottom:1px solid var(--border);vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tbody tr{{transition:background .1s}}
tbody tr:hover{{background:var(--navy-l)}}
.rc{{max-width:290px}}
.rt{{font-weight:600;font-size:13px;line-height:1.35}}
.rt a{{color:var(--text);text-decoration:none}}
.rt a:hover{{color:var(--navy);text-decoration:underline}}
.co{{font-size:11.5px;color:var(--text2);margin-top:2px;font-weight:500}}
.lo{{font-size:12px;color:var(--text2);white-space:nowrap}}
.dt{{font-size:11.5px;color:var(--text3);white-space:nowrap}}
.sa{{font-size:12px;font-weight:500;white-space:nowrap}}
.sa.k{{color:var(--green)}}
.sa.u{{color:var(--text3)}}
.badge{{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:11px;font-size:11px;font-weight:600;white-space:nowrap}}
.b4{{background:var(--green-bg);color:var(--green);border:1px solid var(--green-b)}}
.b3{{background:var(--blue-bg);color:var(--blue);border:1px solid var(--blue-b)}}
.b2{{background:var(--amber-bg);color:var(--amber);border:1px solid var(--amber-b)}}
.b1{{background:var(--gray-bg);color:var(--gray);border:1px solid var(--gray-b)}}
.bd{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.b4 .bd{{background:var(--green)}}
.b3 .bd{{background:var(--blue)}}
.b2 .bd{{background:var(--amber)}}
.b1 .bd{{background:var(--gray)}}
.sbar{{width:48px;height:5px;background:var(--border2);border-radius:3px;overflow:hidden;display:inline-block;vertical-align:middle;margin-left:5px}}
.sfill{{height:100%;border-radius:3px}}
.abtn{{display:inline-block;padding:4px 11px;background:var(--navy-l);color:var(--navy);border-radius:5px;font-size:11px;font-weight:600;text-decoration:none;white-space:nowrap;transition:all .15s}}
.abtn:hover{{background:var(--navy);color:#fff}}
.empty{{text-align:center;padding:48px 20px;color:var(--text3);display:none}}
.footer{{margin-top:18px;font-size:11px;color:var(--text3);text-align:center}}
tr.arow .co::after{{content:" ✓ Applied";color:var(--green);font-size:10px;font-weight:600;margin-left:4px}}
</style>
</head>
<body>
<div class="page">
  <div class="hdr">
    <div class="hdr-in">
      <div>
        <h1>Daily Job Match Report</h1>
        <p>Julary Yesudhas &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; VP / Sr. Director / Managing Director — Data, AI &amp; Platform Engineering</p>
      </div>
      <div class="kpis">
        <div class="kpi"><span class="kpi-n">{total_raw}</span><span class="kpi-l">Pulled</span></div>
        <div class="kpi"><span class="kpi-n" id="kn">{len(jobs_data)}</span><span class="kpi-l">Showing</span></div>
        <div class="kpi"><span class="kpi-n">{high}</span><span class="kpi-l">High Match</span></div>
        <div class="kpi"><span class="kpi-n">{with_sal}</span><span class="kpi-l">Salary Listed</span></div>
      </div>
    </div>
  </div>

  <div class="notice">Match score is based on title + description keyword relevance to your target profile (Data, AI, Platform Engineering leadership). Roles with known salary below ${MIN_SALARY:,} are excluded.</div>

  <div class="ctrls">
    <div class="sw">
      <svg class="si" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="text" id="q" placeholder="Search title or company…" oninput="render()">
    </div>
    <div class="pills">
      <button class="pill on" onclick="setF('all',this)">All</button>
      <button class="pill" onclick="setF('high',this)">High Match</button>
      <button class="pill" onclick="setF('salary',this)">Salary Listed</button>
      <button class="pill" onclick="setF('remote',this)">Remote</button>
    </div>
  </div>

  <div class="tw">
    <table>
      <thead>
        <tr>
          <th onclick="srt('title')">Position ↕</th>
          <th onclick="srt('location')">Location ↕</th>
          <th onclick="srt('date')">Posted ↕</th>
          <th onclick="srt('salval')">Salary ↕</th>
          <th onclick="srt('score')">Match ↕</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="tb"></tbody>
    </table>
    <div class="empty" id="em">No roles match this filter.</div>
  </div>

  <div class="footer">Generated {date_str} &nbsp;·&nbsp; {total_raw} raw listings scraped &nbsp;·&nbsp; {len(jobs_data)} relevant roles after filtering &nbsp;·&nbsp; Min salary filter: ${MIN_SALARY:,}</div>
</div>
<script>
const APPLIED={applied_js};
const jobs={jobs_js};
let flt='all',sk='score',sd=-1;

function bc(s){{return s>=7?'b4':s>=5?'b3':s>=3?'b2':'b1';}}
function bcolor(s){{return s>=7?'#16a34a':s>=5?'#2563eb':s>=3?'#d97706':'#9ca3af';}}
function bw(s){{return Math.min(Math.round(s/8*100),100);}}

function setF(f,btn){{flt=f;document.querySelectorAll('.pill').forEach(p=>p.classList.remove('on'));btn.classList.add('on');render();}}
function srt(k){{sk===k?sd*=-1:(sk=k,sd=-1);render();}}

function render(){{
  const q=(document.getElementById('q').value||'').toLowerCase();
  let list=[...jobs];
  if(flt==='high') list=list.filter(j=>j.score>=5);
  else if(flt==='salary') list=list.filter(j=>j.salval>0);
  else if(flt==='remote') list=list.filter(j=>j.location.toLowerCase().includes('remote'));
  if(q) list=list.filter(j=>j.title.toLowerCase().includes(q)||j.company.toLowerCase().includes(q));
  list.sort((a,b)=>{{
    let av=a[sk],bv=b[sk];
    if(typeof av==='string'){{av=av.toLowerCase();bv=bv.toLowerCase();}}
    return av<bv?-sd:av>bv?sd:0;
  }});
  document.getElementById('kn').textContent=list.length;
  const tb=document.getElementById('tb');
  const em=document.getElementById('em');
  tb.innerHTML='';
  if(!list.length){{em.style.display='block';return;}}
  em.style.display='none';
  list.forEach(j=>{{
    const cl=bc(j.score),bwv=bw(j.score),bclr=bcolor(j.score);
    const isAp=APPLIED.some(a=>j.company.includes(a)||j.title.includes(a));
    const tr=document.createElement('tr');
    if(isAp) tr.className='arow';
    tr.innerHTML=`
      <td class="rc"><div class="rt"><a href="${{j.url}}" target="_blank" rel="noopener">${{j.title}}</a></div><div class="co">${{j.company}}</div></td>
      <td class="lo">${{j.location}}</td>
      <td class="dt">${{j.date}}</td>
      <td class="sa ${{j.salval>0?'k':'u'}}">${{j.salary}}</td>
      <td><span class="badge ${{cl}}"><span class="bd"></span>${{j.match}}%</span><span class="sbar"><span class="sfill" style="width:${{bwv}}%;background:${{bclr}}"></span></span></td>
      <td><a class="abtn" href="${{j.url}}" target="_blank" rel="noopener">Apply →</a></td>
    `;
    tb.appendChild(tr);
  }});
}}
render();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run_job_search():
    date_str  = datetime.now().strftime("%B %d, %Y")
    file_date = datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now()}] Starting daily leadership job pull...")

    queries = [
        "Vice President Data Engineering",
        "VP Data Analytics",
        "Senior Director Data Architecture",
        "Director Enterprise Data",
        "VP Software Engineering",
        "Director Software Engineering",
        "Head of Engineering",
        "Head of Data",
        "VP Data Analytics Engineering",
        "Senior Director Data Engineering",
        "Executive Director Analytics Engineering",
        "Vice President Artificial Intelligence",
        "Senior Director AI Platform",
        "VP Data Governance",
        "Managing Director Data Platforms",
    ]

    all_jobs = []
    for query in queries:
        try:
            print(f"  Searching: {query}")
            jobs = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=query,
                google_search_term=f"{query} jobs United States last 24 hours",
                location="United States",
                is_remote=True,
                results_wanted=20,
                hours_old=24,
                country_hosted="USA"
            )
            if not jobs.empty:
                all_jobs.append(jobs)
        except Exception as e:
            print(f"  Error: '{query}': {e}")

    if not all_jobs:
        print("No jobs found.")
        return

    combined  = pd.concat(all_jobs, ignore_index=True)
    total_raw = len(combined)
    combined  = combined.drop_duplicates(subset=["title", "company"])

    if "date_posted" in combined.columns:
        combined["date_posted"] = pd.to_datetime(combined["date_posted"], utc=True, errors="coerce")
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        combined = combined[
            (combined["date_posted"] >= cutoff) | (combined["date_posted"].isna())
        ]

    combined = combined[combined["title"].apply(filter_by_title)]
    combined = combined[combined.apply(salary_passes, axis=1)]

    desc_col = "description" if "description" in combined.columns else None
    combined["relevance_score"] = combined.apply(
        lambda r: score_role(r["title"], r.get(desc_col, "") if desc_col else ""),
        axis=1
    )
    combined = combined[combined["relevance_score"] >= MIN_SCORE]
    combined = combined.sort_values("relevance_score", ascending=False)

    # Build jobs list
    jobs_data = []
    for _, r in combined.iterrows():
        jobs_data.append({
            "title":    str(r.get("title", "")),
            "company":  str(r.get("company", "Unknown")),
            "location": clean_location(r.get("location", "")),
            "date":     str(r.get("date_posted", "Today"))[:10] if pd.notna(r.get("date_posted")) else "Today",
            "salary":   salary_str(r),
            "salval":   salary_val(r),
            "match":    match_pct(int(r["relevance_score"])),
            "score":    int(r["relevance_score"]),
            "url":      str(r.get("job_url", "#")),
        })

    # Save HTML report
    html      = generate_html_report(jobs_data, date_str, total_raw)
    html_file = f"job_report_{file_date}.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    # Save CSV (backup)
    csv_file  = f"leadership_jobs_{file_date}.csv"
    keep_cols = ["title", "company", "location", "date_posted", "job_url",
                 "min_amount", "max_amount", "relevance_score"]
    keep_cols = [c for c in keep_cols if c in combined.columns]
    combined[keep_cols].to_csv(csv_file, index=False)

    print(f"\n{'='*52}")
    print(f"  {len(jobs_data)} relevant roles from {total_raw} raw listings")
    print(f"  HTML report : {html_file}")
    print(f"  CSV backup  : {csv_file}")
    print(f"{'='*52}")

    print("\nTop 10 matches:")
    for j in jobs_data[:10]:
        print(f"  [{j['match']}%] {j['title']} @ {j['company']} | {j['location']}")


if __name__ == "__main__":
    run_job_search()
