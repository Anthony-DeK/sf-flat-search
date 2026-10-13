"""ntfy push (one per strong match) and a Gmail digest (matches + maybes + broken sources)."""
import os
import smtplib
from email.mime.text import MIMEText
from html import escape

from . import http


PUSH_LIMIT = 8   # beyond this, one summary push points to the email (e.g. after widening the search)


def furnishing(l):
    return {True: "Furnished", False: "Unfurnished"}.get(l.get("furnished"), "Furnishing not stated")


def _line(l):
    bits = [f"${l['price']:,}" if l.get("price") else "$?",
            f"{l['beds']}BR" if l.get("beds") is not None else "?BR",
            l.get("hood") or "?"]
    if l.get("lease"):
        bits.append(l["lease"])
    bits.append({True: "furnished", False: "unfurnished"}.get(l.get("furnished"), "furnishing?"))
    return " · ".join(bits)


def _publish(msg, dry_run):
    topic = os.environ.get("NTFY_TOPIC")
    if dry_run or not topic:
        print(f"  [push] {msg['title']} | {msg.get('click', '')}")
        return False
    # JSON publish keeps emoji/UTF-8 intact (headers are latin-1 only).
    http.post("https://ntfy.sh/", json={"topic": topic, "tags": ["house"], **msg})
    return True


def push(listings, dry_run=False):
    """One push per listing (caller sorts deals/cheapest first), capped at PUSH_LIMIT plus a summary.
    Returns True if anything was actually delivered."""
    sent = False
    for l in listings[:PUSH_LIMIT]:
        body = l["title"][:200] + (f"\n+ {', '.join(l['bonus'])}" if l.get("bonus") else "") + f"\n{l['source']}"
        sent |= _publish({"title": ("🔥 " if l.get("deal") else "") + _line(l), "message": body,
                          "click": l["url"], "priority": 4 if l.get("deal") else 3}, dry_run)
    extra = len(listings) - PUSH_LIMIT
    if extra > 0:
        sent |= _publish({"title": f"+{extra} more new apartments",
                          "message": "Too many to push one by one; they're all in the email digest."}, dry_run)
    return sent


def _rows(items):
    return "".join(
        f'<tr><td><a href="{escape(l["url"])}">{escape(l["title"][:90])}</a><br>'
        f'<small>{escape(_line(l))} · {escape(l["source"])}'
        f'{" · " + escape(", ".join(l["bonus"])) if l.get("bonus") else ""}'
        f'{" · unknown: " + escape(", ".join(l["unknown"])) if l.get("unknown") else ""}</small></td></tr>'
        for l in items)


def email(matches, maybes, broken, dashboard_url="", dry_run=False):
    """Returns True if the email was actually sent."""
    if not (matches or maybes or broken):
        return False
    if matches or maybes:
        nf = sum(1 for l in matches if l.get("furnished") is True)
        subject = (f"🏠 {len(matches)} new match{'es' * (len(matches) != 1)}"
                   + (f" ({nf} furnished, {len(matches) - nf} unfurnished/unstated)" if matches else "")
                   + (f", {len(maybes)} maybe" if maybes else ""))
    else:
        subject = "⚠️ Apartment hunter: a source stopped working"
    html = ""
    for label in ("Furnished", "Unfurnished", "Furnishing not stated"):
        group = [l for l in matches if furnishing(l) == label]
        if group:
            html += f"<h3>{label} ({len(group)})</h3><table>{_rows(group)}</table>"
    if maybes:
        html += f"<h3>Maybe (missing info, worth a look)</h3><table>{_rows(maybes)}</table>"
    if broken:
        html += "<h3>⚠️ Sources returning nothing</h3><ul>" + "".join(f"<li>{escape(b)}</li>" for b in broken) + "</ul>"
    if dashboard_url:
        html += f'<p><a href="{escape(dashboard_url)}">Open dashboard</a></p>'
    user, pw, to = (os.environ.get(k) for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "ALERT_TO"))
    if dry_run or not (user and pw):
        print(f"  [email] {subject} ({len(matches)} matches, {len(maybes)} maybes, {len(broken)} broken)")
        return False
    msg = MIMEText(html, "html")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to or user
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
    return True
