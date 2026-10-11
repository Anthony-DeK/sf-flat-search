"""ntfy push (one per strong match) and a Gmail digest (matches + maybes + broken sources)."""
import os
import smtplib
from email.mime.text import MIMEText
from html import escape

from . import http


def _line(l):
    bits = [f"${l['price']:,}" if l.get("price") else "$?",
            f"{l['beds']}BR" if l.get("beds") is not None else "?BR",
            l.get("hood") or "?"]
    if l.get("lease"):
        bits.append(l["lease"])
    return " · ".join(bits)


def push(listings, dry_run=False):
    topic = os.environ.get("NTFY_TOPIC")
    for l in listings:
        title = ("🔥 " if l.get("deal") else "") + _line(l)
        body = l["title"][:200] + (f"\n+ {', '.join(l['bonus'])}" if l.get("bonus") else "") + f"\n{l['source']}"
        if dry_run or not topic:
            print(f"  [push] {title} | {l['url']}")
            continue
        # JSON publish keeps emoji/UTF-8 intact (headers are latin-1 only).
        http.post("https://ntfy.sh/", json={
            "topic": topic, "title": title, "message": body, "click": l["url"],
            "priority": 4 if l.get("deal") else 3, "tags": ["house"],
        })


def _rows(items):
    return "".join(
        f'<tr><td><a href="{escape(l["url"])}">{escape(l["title"][:90])}</a><br>'
        f'<small>{escape(_line(l))} · {escape(l["source"])}'
        f'{" · " + escape(", ".join(l["bonus"])) if l.get("bonus") else ""}'
        f'{" · unknown: " + escape(", ".join(l["unknown"])) if l.get("unknown") else ""}</small></td></tr>'
        for l in items)


def email(matches, maybes, broken, dashboard_url="", dry_run=False):
    if not (matches or maybes or broken):
        return
    if matches or maybes:
        subject = f"🏠 {len(matches)} new match{'es' * (len(matches) != 1)}" + (f", {len(maybes)} maybe" if maybes else "")
    else:
        subject = "⚠️ Apartment hunter: a source stopped working"
    html = ""
    if matches:
        html += f"<h3>New matches</h3><table>{_rows(matches)}</table>"
    if maybes:
        html += f"<h3>Maybe (missing info, worth a look)</h3><table>{_rows(maybes)}</table>"
    if broken:
        html += "<h3>⚠️ Sources returning nothing</h3><ul>" + "".join(f"<li>{escape(b)}</li>" for b in broken) + "</ul>"
    if dashboard_url:
        html += f'<p><a href="{escape(dashboard_url)}">Open dashboard</a></p>'
    user, pw, to = (os.environ.get(k) for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "ALERT_TO"))
    if dry_run or not (user and pw):
        print(f"  [email] {subject} ({len(matches)} matches, {len(maybes)} maybes, {len(broken)} broken)")
        return
    msg = MIMEText(html, "html")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to or user
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
