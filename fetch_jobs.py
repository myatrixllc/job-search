from jobspy import scrape_jobs
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import os

# ─────────────────────────────────────────────
# FILTER / PROFILE-AWARE SCREENING CONFIGURATION
# ─────────────────────────────────────────────

TITLE_INCLUDE = [
    "vice president", "vp", "managing director", "associate managing director",
    "senior director", "sr. director", "sr director", "head of",
    "executive director", "avp", "assistant vice president"
]

TITLE_EXCLUDE = [
    "sales", "marketing", "human resources", "recruiter", "account manager",
    "business development", "legal", "supply chain", "radiolog", "nursing",
    "physician", "claims adjuster", "customer success", "account executive",
    "channel partner", "alliances", "chief information security officer",
    "ciso", "penetration testing"
]

TARGET_BASE = 240000
BACKUP_MAX_FLOOR = 225000
MIN_SCREEN_SCORE = 45
HIGH_SCREEN_SCORE = 90

LEVEL_SCORES = {
    "associate managing director": 15, "managing director": 15,
    "vice president": 15, "vp": 15, "head of": 15,
    "senior director": 15, "sr. director": 15, "sr director": 15,
    "assistant vice president": 14, "avp": 14, "executive director": 13,
}

FUNCTION_GROUPS = {
    "Data Platform / Engineering": (25, [
        "data platform", "enterprise data platform", "data engineering",
        "data infrastructure", "cloud data platform", "lakehouse",
        "data architecture", "platform engineering"]),
    "Enterprise Data": (24, [
        "enterprise data strategy", "data strategy", "enterprise data",
        "data transformation", "data modernization", "data management",
        "data governance"]),
    "Software / Platform": (23, [
        "software engineering", "platform engineering", "software platform",
        "cloud platform", "api platform", "engineering organization"]),
    "Analytics": (20, [
        "analytics engineering", "data analytics", "business intelligence",
        "enterprise analytics", "reporting", "dashboard", "semantic layer",
        "semantic model"]),
    "AI Platform": (20, [
        "ai platform", "ai engineering", "ai enablement", "generative ai",
        "genai", "rag", "mlops", "llmops", "agentic ai", "responsible ai"]),
    "Enterprise Architecture": (23, [
        "enterprise architecture", "solution architecture", "platform architecture",
        "technology architecture", "architecture strategy", "reference architecture"]),
}

LEADERSHIP_KEYWORDS = [
    "lead team", "lead teams", "leading teams", "build and lead", "manage team",
    "manage teams", "organization", "organizational leadership", "global team",
    "distributed team", "executive leadership", "senior leadership",
    "develop leaders", "mentor leaders", "budget", "portfolio", "investment",
    "vendor", "strategic partner", "build-vs-buy", "build vs buy"
]

TECH_KEYWORDS = [
    "snowflake", "databricks", "spark", "aws", "gcp", "google cloud",
    "lakehouse", "hadoop", "cloudera", "kafka", "cdc", "etl", "elt", "api",
    "microservices", "data modeling", "semantic", "observability", "ci/cd",
    "devsecops", "data quality", "metadata", "lineage", "mdm", "data products"
]

HEALTHCARE_KEYWORDS = [
    "healthcare", "health plan", "health insurance", "payer", "claims", "member",
    "provider", "fhir", "hl7", "interoperability", "medicare", "medicaid",
    "revenue cycle", "835", "837", "270", "271", "ehr", "emr"
]

BUSINESS_KEYWORDS = [
    "business value", "business outcome", "executive stakeholder",
    "senior stakeholder", "strategic roadmap", "multi-year roadmap",
    "investment prioritization", "portfolio management", "business case",
    "cost-benefit", "roi", "operating model", "organizational change",
    "transformation"
]

PENALTY_GROUPS = {
    "Quantitative / Actuarial DS": (20, [
        "actuarial credential", "actuary", "probability engine",
        "advanced mathematical", "advanced statistical", "quantitative research",
        "statistical theory"]),
    "Security Leadership": (30, [
        "chief information security", "security officer", "penetration testing",
        "cybersecurity operations", "security operations center"]),
    "Sales / Origination": (35, [
        "sales quota", "revenue quota", "book of business", "sales pipeline",
        "business development quota", "quota carrying"]),
    "Manufacturing Engineering": (35, [
        "manufacturing engineering", "mechanical engineering",
        "facilities engineering", "plant engineering", "packaging engineering",
        "maintenance engineering"]),
    "Microsoft Stack Hard Requirement": (12, [
        "extensive experience with microsoft fabric",
        "deep expertise in microsoft fabric", "expertise in microsoft fabric",
        "fabric migration experience required", "azure data factory required",
        "power bi required"]),
    "ERP Hard Requirement": (12, [
        "5+ years of erp", "five years of erp",
        "extensive erp experience required", "jd edwards experience required",
        "sap experience required"]),
    "Individual Contributor": (18, [
        "individual contributor role", "no direct reports",
        "hands-on individual contributor", "principal engineer role",
        "staff engineer role"]),
}

APPLIED_ROLES = [
    {"company": "McDonald's", "title": "Senior Director, Enterprise Architecture"},
    {"company": "Vituity", "title": "Senior Director, Platform Engineering"},
    {"company": "Experian", "title": "Senior Director, Platform Architecture"},
    {"company": "Revecore", "title": "Senior Director, Enterprise Data Architecture"},
]

# ─────────────────────────────────────────────
# FILTER / SCORING FUNCTIONS
# ─────────────────────────────────────────────

def filter_by_title(title):
    if not title:
        return False
    t = title.lower()
    return any(k in t for k in TITLE_INCLUDE) and not any(k in t for k in TITLE_EXCLUDE)

def count_matches(text, keywords):
    return sum(1 for k in keywords if k in text)

def score_role(title, description, min_salary=None, max_salary=None):
    title = (title or "").lower()
    desc = description.lower() if isinstance(description, str) else ""
    text = f"{title} {desc}"
    c = {}

    c["seniority"] = max(
        [pts for level, pts in LEVEL_SCORES.items() if level in title] or [0]
    )

    fs = []
    for name, (weight, keywords) in FUNCTION_GROUPS.items():
        hits = count_matches(text, keywords)
        if hits:
            fs.append((name, round(weight * min(hits / 3.0, 1.0))))
    fs.sort(key=lambda x: x[1], reverse=True)
    if fs:
        c["function"] = min(25, round(fs[0][1] + (fs[1][1] * .20 if len(fs) > 1 else 0)))
        primary = fs[0][0]
    else:
        c["function"], primary = 0, "Other / Unknown"

    c["leadership"] = min(15, count_matches(text, LEADERSHIP_KEYWORDS) * 3)
    c["technical"] = min(15, round(count_matches(text, TECH_KEYWORDS) * 1.5))
    c["domain"] = min(10, count_matches(text, HEALTHCARE_KEYWORDS) * 2)
    c["business"] = min(10, count_matches(text, BUSINESS_KEYWORDS) * 2)

    comp = 5
    if pd.notna(max_salary):
        if max_salary >= 280000: comp = 10
        elif max_salary >= 260000: comp = 9
        elif max_salary >= 240000: comp = 8
        elif max_salary >= 225000: comp = 4
        else: comp = 0
    c["compensation"] = comp

    penalties, penalty_total = [], 0
    for name, (penalty, keywords) in PENALTY_GROUPS.items():
        if any(k in text for k in keywords):
            penalties.append(name)
            penalty_total += penalty

    return {
        "score": max(0, min(100, sum(c.values()) - penalty_total)),
        "primary_function": primary,
        "components": c,
        "penalties": penalties,
    }

def screening_tier(score):
    if score >= 95: return "A+ | REVIEW NOW"
    if score >= 90: return "A | STRONG REVIEW"
    if score >= 87: return "B | SELECTIVE"
    return "C | BACKUP"

def salary_str(row):
    mn, mx = row.get("min_amount"), row.get("max_amount")
    if pd.notna(mn) and pd.notna(mx): return f"${int(mn):,} – ${int(mx):,}"
    if pd.notna(mn): return f"${int(mn):,}+"
    if pd.notna(mx): return f"up to ${int(mx):,}"
    return "Not listed"

def salary_val(row):
    mx, mn = row.get("max_amount"), row.get("min_amount")
    if pd.notna(mx): return int(mx)
    if pd.notna(mn): return int(mn)
    return 0

def salary_passes(row):
    # Discovery should not eliminate an otherwise relevant role based on salary.
    # Compensation is already incorporated into the screening score and remains
    # visible in the report for the user to make the final decision.
    return True

def already_applied(company, title):
    company, title = (company or "").lower(), (title or "").lower()
    return any(r["company"].lower() in company and r["title"].lower() in title
               for r in APPLIED_ROLES)

def clean_location(loc):
    if not isinstance(loc, str) or loc.strip().lower() in ("nan", ""):
        return "Remote / Not listed"
    parts = loc.split(",")
    return f"{parts[0].strip()}, {parts[1].strip()}" if len(parts) >= 2 else loc.strip()


# ─────────────────────────────────────────────
# HTML REPORT
# ─────────────────────────────────────────────

def generate_html_report(jobs_data, date_str, total_raw):
    high       = sum(1 for j in jobs_data if j["score"] >= HIGH_SCREEN_SCORE)
    with_sal   = sum(1 for j in jobs_data if j["salval"] > 0)
    applied_js = json.dumps(APPLIED_ROLES)
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
        <div class="kpi"><span class="kpi-n">{high}</span><span class="kpi-l">90+ Screen</span></div>
        <div class="kpi"><span class="kpi-n">{with_sal}</span><span class="kpi-l">Salary Listed</span></div>
      </div>
    </div>
  </div>

  <div class="notice">Screening score combines functional mandate, leadership scope, technical alignment, healthcare/domain fit, executive/business alignment, compensation and mismatch penalties. It is an automated prioritization score, not an interview probability. Compensation affects ranking but does not remove an otherwise relevant role.</div>

  <div class="ctrls">
    <div class="sw">
      <svg class="si" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="text" id="q" placeholder="Search title or company…" oninput="render()">
    </div>
    <div class="pills">
      <button class="pill on" onclick="setF('all',this)">All</button>
      <button class="pill" onclick="setF('high',this)">90+ Screen</button>
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
          <th onclick="srt('score')">Screen ↕</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="tb"></tbody>
    </table>
    <div class="empty" id="em">No roles match this filter.</div>
  </div>

  <div class="footer">Generated {date_str} &nbsp;·&nbsp; {total_raw} raw listings scraped &nbsp;·&nbsp; {len(jobs_data)} relevant roles after filtering &nbsp;·&nbsp; Discovery floor: ${MIN_SCREEN_SCORE} screening points · Compensation used for ranking, not exclusion</div>
</div>
<script>
const APPLIED={applied_js};
const jobs={jobs_js};
let flt='all',sk='score',sd=-1;

function bc(s){{return s>=95?'b4':s>=90?'b3':s>=87?'b2':'b1';}}
function bcolor(s){{return s>=95?'#16a34a':s>=90?'#2563eb':s>=87?'#d97706':'#9ca3af';}}
function bw(s){{return Math.max(0,Math.min(s,100));}}

function setF(f,btn){{flt=f;document.querySelectorAll('.pill').forEach(p=>p.classList.remove('on'));btn.classList.add('on');render();}}
function srt(k){{sk===k?sd*=-1:(sk=k,sd=-1);render();}}

function render(){{
  const q=(document.getElementById('q').value||'').toLowerCase();
  let list=[...jobs];
  if(flt==='high') list=list.filter(j=>j.score>=90);
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
    const isAp=APPLIED.some(a=>j.company.toLowerCase().includes(a.company.toLowerCase())&&j.title.toLowerCase().includes(a.title.toLowerCase()));
    const tr=document.createElement('tr');
    if(isAp) tr.className='arow';
    tr.innerHTML=`
      <td class="rc"><div class="rt"><a href="${{j.url}}" target="_blank" rel="noopener">${{j.title}}</a></div><div class="co">${{j.company}}</div></td>
      <td class="lo">${{j.location}}</td>
      <td class="dt">${{j.date}}</td>
      <td class="sa ${{j.salval>0?'k':'u'}}">${{j.salary}}</td>
      <td><span class="badge ${{cl}}"><span class="bd"></span>${{j.score}}</span><span class="sbar"><span class="sfill" style="width:${{bwv}}%;background:${{bclr}}"></span></span></td>
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
        "Senior Director Data Engineering",
        "Senior Director Enterprise Data Platforms",
        "Senior Director Data Platform Engineering",
        "Senior Director Data Architecture",
        "Senior Director Platform Engineering",
        "Senior Director Software Engineering",
        "Senior Director Data Analytics",
        "Senior Director Data AI Engineering",
        "Senior Director Cloud Data Platforms",
        "Senior Director Enterprise Architecture",
        "Vice President Data Engineering",
        "Vice President Data Platforms",
        "Vice President Data Analytics",
        "Vice President Platform Engineering",
        "Vice President Software Engineering",
        "Vice President Data AI",
        "Head of Data Engineering",
        "Head of Data Platforms",
        "Head of Platform Engineering",
        "Managing Director Data Engineering",
        "Managing Director Data Platforms",
        "Managing Director Data Analytics",
        "AVP Data Engineering",
        "AVP Data Platforms",
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

    def evaluate_row(r):
        result = score_role(
            r.get("title", ""),
            r.get(desc_col, "") if desc_col else "",
            r.get("min_amount"),
            r.get("max_amount"),
        )
        return pd.Series({
            "screening_score": result["score"],
            "primary_function": result["primary_function"],
            "screening_tier": screening_tier(result["score"]),
            "score_components": json.dumps(result["components"]),
            "penalties": ", ".join(result["penalties"]),
        })

    scored = combined.apply(evaluate_row, axis=1)
    combined = pd.concat([combined, scored], axis=1)
    combined = combined[combined["screening_score"] >= MIN_SCREEN_SCORE]
    combined = combined.sort_values("screening_score", ascending=False)

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
            "score":    int(r["screening_score"]),
            "tier":     str(r.get("screening_tier", "")),
            "function": str(r.get("primary_function", "")),
            "penalties": str(r.get("penalties", "")),
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
                 "min_amount", "max_amount", "screening_score",
                 "screening_tier", "primary_function", "penalties",
                 "score_components"]
    keep_cols = [c for c in keep_cols if c in combined.columns]
    combined[keep_cols].to_csv(csv_file, index=False)

    print(f"\n{'='*52}")
    print(f"  {len(jobs_data)} relevant roles from {total_raw} raw listings")
    print(f"  HTML report : {html_file}")
    print(f"  CSV backup  : {csv_file}")
    print(f"{'='*52}")

    print("\nTop 10 screening results:")
    for j in jobs_data[:10]:
        print(f"  [{j['score']}] {j['tier']} | {j['title']} @ {j['company']} | {j['location']}")


if __name__ == "__main__":
    run_job_search()
