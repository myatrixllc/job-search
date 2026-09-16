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
    "catastrophe", "real-world evidence", "radiolog", "nursing", "physician"
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

MIN_SCORE = 1          # Minimum domain keyword hits to include
MIN_SALARY = 180000    # Minimum base salary (skips roles below this when salary is available)

# ─────────────────────────────────────────────
# FILTER FUNCTIONS
# ─────────────────────────────────────────────

def filter_by_title(title):
    if not title:
        return False
    t = title.lower()
    has_level = any(kw in t for kw in TITLE_INCLUDE)
    is_excluded = any(kw in t for kw in TITLE_EXCLUDE)
    return has_level and not is_excluded

def score_role(title, description):
    t = (title or "").lower()
    d = ("" if not isinstance(description, str) else description).lower()
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


def salary_passes(row):
    """Return False only if salary is known AND below the minimum."""
    mn = row.get("min_amount")
    mx = row.get("max_amount")
    if pd.notna(mn) and mn < MIN_SALARY:
        return False
    if pd.notna(mx) and mx < MIN_SALARY:
        return False
    return True


def match_pct(score):
    return min(int(score / 3 * 100), 100)


# ─────────────────────────────────────────────
# HTML REPORT GENERATOR
# ─────────────────────────────────────────────

def generate_html_report(jobs_data, date_str, total_raw):
    high = sum(1 for j in jobs_data if j["match"] >= 90)
    with_salary = sum(1 for j in jobs_data if j["salary"] != "Not listed")

    jobs_json = json.dumps(jobs_data, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Match Report — {date_str}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  :root {{
    --bg:#F8F9FB;--surface:#FFFFFF;--border:#E4E7EC;
    --text-primary:#0F1C2E;--text-secondary:#5C6B7A;--text-muted:#9AA4B0;
    --accent:#1B4F8A;--accent-light:#E8F0FA;
    --high:#1A7A4A;--high-bg:#E8F5EE;
    --mid:#B45309;--mid-bg:#FEF3E2;
    --low:#5C6B7A;--low-bg:#F1F3F5;
  }}
  @media (prefers-color-scheme:dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0D1117;--surface:#161B22;--border:#30363D;
      --text-primary:#E6EDF3;--text-secondary:#8B949E;--text-muted:#6E7681;
      --accent:#58A6FF;--accent-light:#1B2A3D;
      --high:#3FB950;--high-bg:#0D2A1A;
      --mid:#D29922;--mid-bg:#2A1F00;
      --low:#8B949E;--low-bg:#21262D;
    }}
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text-primary);font-size:14px;line-height:1.5;padding:32px 24px}}
  .container{{max-width:980px;margin:0 auto}}
  .header{{margin-bottom:28px;padding-bottom:20px;border-bottom:2px solid var(--accent)}}
  .header h1{{font-size:22px;font-weight:700;color:var(--accent);letter-spacing:-0.3px}}
  .header .subtitle{{font-size:13px;color:var(--text-secondary);margin-top:4px}}
  .stats{{display:flex;gap:16px;margin-top:20px;flex-wrap:wrap}}
  .stat{{text-align:center;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 20px;min-width:90px}}
  .stat-num{{font-size:24px;font-weight:700;color:var(--accent);display:block}}
  .stat-label{{font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;margin-top:2px}}
  .note{{background:var(--accent-light);border-left:3px solid var(--accent);padding:10px 14px;border-radius:0 6px 6px 0;font-size:12px;color:var(--text-secondary);margin-bottom:16px}}
  .filters{{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}}
  .filter-btn{{padding:6px 14px;border-radius:20px;border:1px solid var(--border);background:var(--surface);color:var(--text-secondary);font-size:12px;font-weight:500;cursor:pointer;transition:all 0.15s;font-family:inherit}}
  .filter-btn:hover{{border-color:var(--accent);color:var(--accent)}}
  .filter-btn.active{{background:var(--accent);color:white;border-color:var(--accent)}}
  .table-wrap{{overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;background:var(--surface);border-radius:10px;overflow:hidden;border:1px solid var(--border)}}
  thead{{background:var(--accent);color:white}}
  th{{padding:12px 16px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.6px;white-space:nowrap}}
  td{{padding:13px 16px;border-bottom:1px solid var(--border);vertical-align:top}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:var(--accent-light)}}
  .job-title{{font-weight:600;font-size:13px;color:var(--text-primary);line-height:1.4;max-width:300px}}
  .job-title a{{color:inherit;text-decoration:none}}
  .job-title a:hover{{color:var(--accent);text-decoration:underline}}
  .company{{font-size:12px;color:var(--text-secondary);margin-top:3px}}
  .location,.date,.salary{{font-size:12px;color:var(--text-secondary);white-space:nowrap}}
  .match-badge{{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap}}
  .match-high{{background:var(--high-bg);color:var(--high)}}
  .match-mid{{background:var(--mid-bg);color:var(--mid)}}
  .match-low{{background:var(--low-bg);color:var(--low)}}
  .dot{{width:7px;height:7px;border-radius:50%}}
  .match-high .dot{{background:var(--high)}}
  .match-mid .dot{{background:var(--mid)}}
  .match-low .dot{{background:var(--low)}}
  .view-btn{{display:inline-block;padding:5px 12px;background:var(--accent-light);color:var(--accent);border-radius:6px;font-size:11px;font-weight:600;text-decoration:none;white-space:nowrap;transition:background 0.15s}}
  .view-btn:hover{{background:var(--accent);color:white}}
  .empty{{text-align:center;padding:40px;color:var(--text-muted);display:none}}
  .footer{{margin-top:20px;font-size:11px;color:var(--text-muted);text-align:center}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>Daily Job Match Report</h1>
      <div class="subtitle">Julary Yesudhas &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; VP / Sr. Director / Managing Director — Data, AI &amp; Platform Engineering</div>
    </div>
    <div class="stats">
      <div class="stat"><span class="stat-num">{total_raw}</span><span class="stat-label">Total Pulled</span></div>
      <div class="stat"><span class="stat-num" id="match-count">{len(jobs_data)}</span><span class="stat-label">Matched</span></div>
      <div class="stat"><span class="stat-num">{high}</span><span class="stat-label">High Match</span></div>
      <div class="stat"><span class="stat-num">{with_salary}</span><span class="stat-label">Salary Listed</span></div>
    </div>
  </div>

  <div class="note">
    Match score is based on title and description keyword relevance to your target profile (Data, AI, Platform Engineering leadership). Roles with known salary below ${MIN_SALARY:,} are excluded.
  </div>

  <div class="filters">
    <button class="filter-btn active" onclick="filterJobs('all',this)">All Roles</button>
    <button class="filter-btn" onclick="filterJobs('high',this)">High Match (90%+)</button>
    <button class="filter-btn" onclick="filterJobs('mid',this)">Mid Match (55–89%)</button>
    <button class="filter-btn" onclick="filterJobs('low',this)">Low Match (&lt;55%)</button>
    <button class="filter-btn" onclick="filterJobs('salary',this)">Salary Listed</button>
  </div>

  <div class="table-wrap">
    <table id="job-table">
      <thead>
        <tr>
          <th>Position</th>
          <th>Location</th>
          <th>Posted</th>
          <th>Base Salary</th>
          <th>Match</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="job-body"></tbody>
    </table>
    <div class="empty" id="empty-state">No roles match this filter.</div>
  </div>

  <div class="footer">
    Generated {date_str} &nbsp;·&nbsp; {total_raw} raw listings scraped &nbsp;·&nbsp; {len(jobs_data)} relevant roles after filtering &nbsp;·&nbsp; Min salary filter: ${MIN_SALARY:,}
  </div>
</div>

<script>
const jobs = {jobs_json};

function matchClass(p) {{
  if (p >= 90) return 'match-high';
  if (p >= 55) return 'match-mid';
  return 'match-low';
}}

function renderJobs(filter) {{
  const tbody = document.getElementById('job-body');
  const empty = document.getElementById('empty-state');
  const table = document.getElementById('job-table');
  tbody.innerHTML = '';

  const filtered = jobs.filter(j => {{
    if (filter === 'high') return j.match >= 90;
    if (filter === 'mid') return j.match >= 55 && j.match < 90;
    if (filter === 'low') return j.match < 55;
    if (filter === 'salary') return j.salary !== 'Not listed';
    return true;
  }});

  document.getElementById('match-count').textContent = filtered.length;

  if (filtered.length === 0) {{
    empty.style.display = 'block';
    table.style.display = 'none';
  }} else {{
    empty.style.display = 'none';
    table.style.display = 'table';
    filtered.forEach(j => {{
      const cls = matchClass(j.match);
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>
          <div class="job-title"><a href="${{j.url}}" target="_blank" rel="noopener">${{j.title}}</a></div>
          <div class="company">${{j.company}}</div>
        </td>
        <td class="location">${{j.location}}</td>
        <td class="date">${{j.date}}</td>
        <td class="salary">${{j.salary}}</td>
        <td><span class="match-badge ${{cls}}"><span class="dot"></span>${{j.match}}%</span></td>
        <td><a class="view-btn" href="${{j.url}}" target="_blank" rel="noopener">View →</a></td>
      `;
      tbody.appendChild(row);
    }});
  }}
}}

function filterJobs(filter, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderJobs(filter);
}}

renderJobs('all');
</script>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run_job_search():
    date_str = datetime.now().strftime("%B %d, %Y")
    file_date = datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now()}] Starting daily 24-hour leadership job pull...")

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
            print(f"  Error scraping '{query}': {e}")

    if not all_jobs:
        print("No jobs found.")
        return

    combined = pd.concat(all_jobs, ignore_index=True)
    total_raw = len(combined)

    # Deduplicate
    combined = combined.drop_duplicates(subset=["title", "company"])

    # Date filter
    if "date_posted" in combined.columns:
        combined["date_posted"] = pd.to_datetime(
            combined["date_posted"], utc=True, errors="coerce"
        )
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        combined = combined[
            (combined["date_posted"] >= cutoff) | (combined["date_posted"].isna())
        ]

    # Title filter
    combined = combined[combined["title"].apply(filter_by_title)]

    # Salary filter (only exclude when salary is known and too low)
    combined = combined[combined.apply(salary_passes, axis=1)]

    # Score
    desc_col = "description" if "description" in combined.columns else None
    combined["relevance_score"] = combined.apply(
        lambda r: score_role(r["title"], r.get(desc_col, "") if desc_col else ""),
        axis=1
    )
    combined = combined[combined["relevance_score"] >= MIN_SCORE]
    combined = combined.sort_values("relevance_score", ascending=False)

    # Build jobs list for report
    jobs_data = []
    for _, r in combined.iterrows():
        jobs_data.append({
            "title": str(r.get("title", "")),
            "company": str(r.get("company", "Unknown")),
            "location": str(r.get("location", "")) or "Remote / Not listed",
            "date": str(r.get("date_posted", "Today"))[:10] if pd.notna(r.get("date_posted")) else "Today",
            "salary": salary_str(r),
            "match": match_pct(r["relevance_score"]),
            "url": str(r.get("job_url", "#")),
        })

    # Save CSV
    csv_file = f"leadership_jobs_{file_date}.csv"
    keep_cols = ["title", "company", "location", "date_posted", "job_url",
                 "min_amount", "max_amount", "relevance_score", "description"]
    keep_cols = [c for c in keep_cols if c in combined.columns]
    combined[keep_cols].to_csv(csv_file, index=False)

    # Generate HTML report
    html = generate_html_report(jobs_data, date_str, total_raw)
    html_file = f"job_report_{file_date}.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n{'='*50}")
    print(f"  {len(jobs_data)} relevant roles from {total_raw} raw listings")
    print(f"  CSV:  {csv_file}")
    print(f"  HTML: {html_file}  ← open this in your browser")
    print(f"{'='*50}")

    print("\nTop 10 matches:")
    for j in jobs_data[:10]:
        print(f"  [{j['match']}%] {j['title']} at {j['company']} | {j['location']}")


if __name__ == "__main__":
    run_job_search()
