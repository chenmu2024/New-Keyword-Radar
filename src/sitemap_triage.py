"""Lossless quality triage for Sitemap URL leads.

Does not alter seeds, Trends thresholds, snapshots or the raw candidate queue.
A URL delta is never labelled as a verified new keyword or demand signal.
"""
from collections import Counter
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data/sitemap/queue.json"
LATEST = ROOT / "data/sitemap/latest.json"
REPORT = ROOT / "reports/sitemap/triage.md"

GAME_FEEDS = {"crazygames-en", "crazygames-br", "crazygames-es",
              "gamepix-en", "gamepix-pt", "minijuegos-es", "friv-en"}
DEPLOY_FEEDS = {"railway-templates"}
WORKFLOW_FEEDS = {"n8n-workflows", "apify-actors-a", "apify-actors-z"}
PRODUCT_FEEDS = {"producthunt-products", "futurepedia-tools", "vercel-product-watch",
                 "netlify-product-watch", "railway-changelog"}


def classify(lead):
    """Priority labels are research routing, NEVER search or revenue verification."""
    source = lead.get("source_id", "")
    query = lead.get("query", "").strip()
    if not query:
        return "ignore", "empty"
    # Public tenders / government registry leads are out of scope for this project.
    if re.search(r"\b(public tenders|public procurement|government tenders|gov tenders|government contracts|gov procurement|planning applications|companies house|medicare clinician)\b", query, re.I):
        return "low", "government-or-regulated-target"
    if source in DEPLOY_FEEDS and re.search(r"\s\d+$", query):
        return "low", "numbered-deploy-template"
    if re.fullmatch(r"[a-z]{8,}", query) and not re.search(r"[aeiou]", query):
        return "low", "unreadable-slug"
    if lead.get("tool_intent_hint"):
        return "review", "tool-intent-wording-not-verified"
    if source in GAME_FEEDS:
        return "watch", "game-title-not-search-demand"
    if source in DEPLOY_FEEDS:
        return "review", "deployment-topic-not-search-demand"
    if source in WORKFLOW_FEEDS:
        return "review", "workflow-problem-not-search-demand"
    if source in PRODUCT_FEEDS:
        return "review", "product-content-not-search-demand"
    return "watch", "generic-url-name-not-search-demand"


def build_report(latest, queue):
    classifications = [(lead, *classify(lead)) for lead in queue]
    tiers = Counter(tier for _, tier, _ in classifications)
    origins = Counter(lead.get("source_id", "unknown") for lead in queue)
    lines = [
        "# Sitemap lead triage — " + latest.get("date", "unknown"),
        "",
        "**Important:** These are *unverified URL leads*, not proven new keywords,",
        "not Google Trends validation, not Semrush Volume/KD/CPC, and not revenue evidence.",
        "Raw queue and all main radar settings remain unchanged.",
        "",
        f"- Sitemap feeds succeeded: {latest.get('success_count', 0)}/{latest.get('source_count', 0)}",
        f"- URLs newly observed in the latest scan: {latest.get('new_url_count', 0)}",
        f"- Candidate URL rows extracted in latest scan: {latest.get('new_candidate_count', 0)}",
        f"- First-time keyword/geo research leads: {latest.get('new_unique_research_lead_count', 'unknown')}",
        f"- Previously removed URLs resurfacing: {latest.get('reappeared_url_count', 'unknown')}",
        f"- Accumulated queue: {len(queue)}",
        f"- Human keyword/topic review: {tiers['review']}",
        f"- Game/general watchlist: {tiers['watch']}",
        f"- Low-quality page-name noise: {tiers['low']}",
        "- **Verified new keywords / search demand / business revenue: not established**",
        "",
        "## Queue composition (by Sitemap source)",
        "",
    ]
    for source, n in origins.most_common():
        lines.append(f"- {source}: {n}")
    lines += ["", "## Latest scan's leads (routing only)", ""]
    for lead in latest.get("candidates", []):
        tier, reason = classify(lead)
        q = lead.get("query", "")
        url = lead.get("url", "")
        if not url.startswith("https://"):
            continue
        lines.append(f"- [{q.replace(']', '')}]({url}) — {tier} / {reason}; "
                     f"source={lead.get('source_id', '')}")
    if not latest.get("candidates"):
        lines.append("- None: a successful baseline scan does not create new-word alerts.")
    lines += [
        "",
        "## Source interpretation",
        "",
        "- A localized path such as /pt/ is not proof of Portuguese-language search demand.",
        "- Deployment templates and product listing names are research leads, not keywords.",
        "- A numbered deploy slug is normally a template duplicate/variant, not evidence of a new term.",
        "- Review candidates against historical search interest, independent SERP, country",
        "  demand and a monetization pathway before recommending a site.",
        "- Apify is currently a two-shard sample, not complete actor coverage.",
        "",
    ]
    return "\n".join(lines)


def main():
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(latest, queue), encoding="utf-8")
    print("Sitemap triage complete:", len(queue), "raw leads (no verified keywords claimed)")


if __name__ == "__main__":
    main()
