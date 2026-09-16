import os
import glob
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime


def find_todays_files():
    date_str = datetime.now().strftime("%Y-%m-%d")
    html_files = glob.glob(f"job_report_{date_str}.html")
    csv_files = glob.glob(f"leadership_jobs_{date_str}.csv")
    return html_files, csv_files


def build_email_body(html_file):
    """Read the HTML report and embed it as the email body."""
    if not html_file:
        return "<p>No report generated today.</p>"
    with open(html_file, "r", encoding="utf-8") as f:
        return f.read()


def count_matches(csv_file):
    """Quick summary stats for the email subject line."""
    if not csv_file:
        return 0, 0
    try:
        import pandas as pd
        df = pd.read_csv(csv_file)
        total = len(df)
        high = len(df[df.get("relevance_score", pd.Series()) >= 3]) if "relevance_score" in df.columns else 0
        return total, high
    except Exception:
        return 0, 0


def send_report():
    # ── Config from environment / GitHub Secrets ──
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    recipient = os.environ.get("RECIPIENT_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print("ERROR: SMTP credentials not set. Check GitHub Secrets.")
        return

    date_label = datetime.now().strftime("%B %d, %Y")
    html_files, csv_files = find_todays_files()

    html_file = html_files[0] if html_files else None
    csv_file  = csv_files[0]  if csv_files  else None

    total, high = count_matches(csv_file)

    # ── Build message ──
    msg = MIMEMultipart("mixed")
    msg["From"]    = smtp_user
    msg["To"]      = recipient
    msg["Subject"] = (
        f"[Job Report] {date_label} — "
        f"{total} matched roles, {high} high match"
    )

    # Email body = the full HTML report
    body_html = build_email_body(html_file)
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    # Attach CSV as a file
    if csv_file:
        with open(csv_file, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(csv_file)}"
        )
        msg.attach(part)

    # ── Send ──
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipient, msg.as_string())
        print(f"Report emailed to {recipient}")
    except Exception as e:
        print(f"Email failed: {e}")
        raise


if __name__ == "__main__":
    send_report()
