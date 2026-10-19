"""Evidence-only review of actually observed product listings.

An actor's posted tariff != confirmed actual buyer or creator revenue.
All third-party prices are manually checked and date-stamped, NOT scraped
blindly from page snippets and NOT fed into main radar scoring/thresholds.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/sitemap/commercial_evidence.json"
QUEUE = ROOT / "data/sitemap/queue.json"
REPORT = ROOT / "reports/sitemap/commercial.md"


def matched_evidence(queue, evidence):
    links = {str(row.get("url")): row for row in queue}
    rows = []
    for item in evidence:
        if item["source_url"] in links:
            rows.append((item, links[item["source_url"]]))
    return rows


def render(queue, evidence, date):
    matched = matched_evidence(queue, evidence)
    lines = [
        "# Sitemap commercial-evidence review — " + date,
        "",
        "**Research shortlist only. Published listing prices do not establish actual payments,",
        "MRR, users willing to subscribe to a standalone site, search volume or keyword newness.**",
        "",
        f"- Existing Sitemap leads with dated external pricing checks: {len(matched)}",
        "- Verified independent paid customers / monthly revenue: **not established**",
        "- Semrush Volume/KD/CPC and SERP competitiveness: **not checked**",
        "- No external API costs incurred to build this research report.",
        "",
        "## Product feature leads for an independent website (NOT an Apify plugin)", "",
    ]
    if not matched:
        lines.append("- No reviewed pricing source still appears in the retained research queue.")
    for item, lead in matched:
        lines += [
            f"### {item['label']}",
            "",
            f"- Observed Sitemap source: [{lead['source_id']}]({lead['url']})",
            f"- Independently checked listing: [{item['listing_label']}]({item['pricing_url']})",
            f"- Listed tariff ({item['checked_on']}): **{item['tariff']}**",
            f"- What the product actually sells: {item['sold_function']}",
            f"- Standalone-website hypothesis: {item['web_version']}",
            f"- Single-developer cost/maintenance concern: {item['cost_warning']}",
            f"- Important weakness: {item['evidence_limit']}",
            f"- Next exact query to verify in Semrush/SERP: **{item['check_term']}**",
            "- Status: **commercial-offer observed; real revenue and SEO viability unverified**",
            "",
        ]
    lines += [
        "## Evidence hierarchy", "",
        "1. Dated public price and available functionality: a commercial offer, not a sale.",
        "2. Verified independent paid transactions/subscriptions: unavailable for these leads.",
        "3. Country-specific nonbrand searches, competing ranking pages, Volume/KD/CPC: not supplied.",
        "4. Zero-cost or client-side feasibility must be examined separately from competitor price.",
        "",
        "This report does not change keyword lists, time-window thresholds, formal rankings",
        "or original raw URL observations.", "",
    ]
    return "\n".join(lines)


def main():
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render(queue, evidence, day), encoding="utf-8")
    print(f"Commercial evidence reviewed: {len(matched_evidence(queue, evidence))} "
          "price-listed product leads (0 confirmed paying customers)")


if __name__ == "__main__":
    main()
