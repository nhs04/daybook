#!/usr/bin/env python3
"""Fetch this week's AI advancement and cybersecurity news for Daybook.

Reads public RSS/Atom feeds, keeps stories from the last 7 days (newest first),
with the headline, a short summary from the feed, the source and a link to read
the full article. Also lists the week's trending topics from the headlines.

Usage:  python3 update_news.py --out news.json
No third-party packages needed.
"""

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS = {
    # Professional sources only: research journals, labs and serious tech journalism.
    # AI itself: new models, generative AI, research breakthroughs and the AI labs. No general tech.
    "ai": [
        ("The Decoder", "https://the-decoder.com/feed/"),
        ("OpenAI", "https://openai.com/news/rss.xml"),
        ("Google DeepMind", "https://deepmind.google/blog/rss.xml"),
        ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
        ("Import AI", "https://importai.substack.com/feed"),
        ("Berkeley AI Research", "https://bair.berkeley.edu/blog/feed.xml"),
        ("MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
        ("Google Research", "https://research.google/blog/rss/"),
        ("Microsoft Research", "https://www.microsoft.com/en-us/research/feed/"),
    ],
    "security": [
        ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
        ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
        ("Dark Reading", "https://www.darkreading.com/rss.xml"),
        ("SecurityWeek", "https://www.securityweek.com/feed/"),
    ],
}
PER_TOPIC = 40
PER_SOURCE = 8  # so no single source takes over the list
# Consumer pieces (gadget lists, deals, reviews, how-tos) are left out.
CONSUMER = re.compile(r"(?i)\b(gadgets?|deals?|gift(s| guide)?|discount|coupon|on sale|buy(ing)? guide|best .+ (to buy|for you)|review:|hands-on|headphones|earbuds|smart home|home office|how to)\b|^\d+\s+\w+")
MAX_AGE = 7 * 86400
# For the AI tab, a story has to be about AI itself (models, generative AI, agents, training, research, the labs)...
AI_CORE = re.compile(r"(?i)\b(a\.?i\.?|artificial intelligence|gen(erative)?[- ]?ai|llms?|(large )?language models?|models?|gpt[- ]?\d*|chatgpt|gemini|claude|llama|mistral|deepseek|qwen|grok|agents?|agentic|reasoning|diffusion|transformers?|neural|deep learning|machine learning|fine-?tun\w*|post-?training|pre-?training|training|benchmarks?|evals?|open[- ]?(source|weights?)|multimodal|agi|superintelligence|alignment|inference|tokens?|chatbots?|openai|anthropic|deepmind|frontier)\b")
# ...and not a side story where AI is only used for something else, or business, gadget and courtroom news.
AI_OFFTOPIC = re.compile(r"(?i)\b(wearables?|cardio\w*|kidney|patients?|hospital|clinical|smell|nose|quantum|astronom\w*|planets?|space|climate|pollution|air quality|data cent(er|re)s?|power grid|energy|gadgets?|smartphones?|homepage|search engine|teens?|cops?|police|school|lawsuits?|sues?|sued|scandal|privacy|stocks?|shares|earnings|valuation|layoffs?|hype index|ipo|chips?|shipments?|industry|partners?|partnership|join forces|adopt\w*|enterprise|customers?|health\w*|sales|marketing|nato|military|defen[cs]e|government|for (chile|countries|\w+ nations?))\b")

STOP = set("""a an the and or but of to in on for with at by from into over about after before as is are was were be been
being it its this that these those new how why what when who which your you we our their they he she his her not no
more most than up out off just now can could will would may might says say said report reports using use uses used
via vs amid get gets got make makes made one two first year years week day days time ai security cyber here there
all any some has have had do does did if into while under against between through also back still big top best
latest update updates news free help want wants need needs launch launches launched announces announced
critical flaw flaws bug bugs data hacker hackers attack attacks attacker attackers patch patches patched vulnerability
vulnerabilities exploit exploited exploits threat threats actors actor users user company companies people model models
tool tools app apps chatbot chatbots tech warns warn found finds million billion high severity fix fixes fixed
breach breaches breached code access remote execution account accounts systems system devices device allow allows let lets design designing building build builds frontier introducing introduces study studies research researchers researcher learning machine scientists scientist paper papers inside meet""".split())


def text(el, *names):
    for n in names:
        found = el.find(n)
        if found is not None:
            if found.text and found.text.strip():
                return found.text.strip()
            if found.get("href"):
                return found.get("href")
    return ""


def clean(s, limit):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    s = re.sub(r"\s+", " ", html.unescape(s)).strip()
    s = re.sub(r"The post .*? appeared first on .*$", "", s).strip()
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return s


def when(s):
    if not s:
        return 0
    try:
        return int(parsedate_to_datetime(s).timestamp())
    except (TypeError, ValueError):
        pass
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; daybook-news/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse(source, raw):
    root = ET.fromstring(raw)
    for el in root.iter():  # drop XML namespaces so RSS and Atom read the same
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    out = []
    for it in list(root.iter("item")) + list(root.iter("entry")):
        title = clean(text(it, "title"), 200)
        link = text(it, "link")
        if not link:
            l = it.find("link")
            link = l.get("href") if l is not None else ""
        if not title or not link.startswith("http"):
            continue
        out.append({
            "id": hashlib.sha1(link.encode()).hexdigest()[:16],
            "title": title,
            "url": link,
            "source": source,
            "published": when(text(it, "pubDate", "published", "updated")),
            "summary": clean(text(it, "description", "summary", "content"), 260),
        })
    return out


# Topics people in AI and security actually follow. A topic trends when this week's stories keep mentioning it.
TOPICS = {
    "ai": [
        ("New model releases", r"\b(introduc|launch|releas|unveil|announc)\w*\b.*\b(model|gpt|gemini|claude|llama|qwen|mistral)|\b(gpt-?\d|gemini \d|claude \w+ \d|llama \d)"),
        ("Generative AI", r"\b(generative|gen[- ]?ai|diffusion|text-to-(image|video|speech)|image generation|video generation|sora|veo|genie)\b"),
        ("AI agents", r"\bagent(s|ic)?\b"), ("Reasoning models", r"\breason(ing|s)?\b"),
        ("Open-weight models", r"\bopen[- ](source|weights?)\b"), ("Multimodal AI", r"\bmulti-?modal|vision[- ]language|speech|voice\b"),
        ("Training & fine-tuning", r"\b(fine-?tun|post-?training|pre-?training|training|rlhf|reinforcement learning|distill)\w*"),
        ("Benchmarks & evals", r"\b(benchmarks?|evals?|evaluations?|leaderboard)\b"), ("AI safety & alignment", r"\b(safety|alignment|interpretab\w+|red[- ]team\w*|guardrails?)\b"),
        ("AI for coding", r"\b(cod(e|ing)|programming|software engineer\w*|developers?)\b"),
        ("Efficiency & inference", r"\b(inference|efficien\w+|quantiz\w+|kernels?|latency|small models?)\b"),
        ("Robotics & embodied AI", r"\brobot(s|ic|ics)?|embodied\b"), ("AGI", r"\b(agi|superintelligence)\b"),
        ("OpenAI", r"\bopenai|chatgpt|gpt-?\d"), ("Google DeepMind & Gemini", r"\b(gemini|deepmind)\b"),
        ("Anthropic & Claude", r"\b(anthropic|claude)\b"), ("Meta AI & Llama", r"\b(meta ai|llama)\b"),
    ],
    "security": [
        ("Ransomware", r"\bransomware\b"), ("Zero-days", r"\bzero-?day"), ("Data breaches", r"\bbreach(es|ed)?\b|\bleak(s|ed)?\b"),
        ("Remote code execution", r"\b(rce|remote code)\b"), ("Critical patches", r"\b(patch(es|ed)?|update fixes|emergency fix)"),
        ("Phishing", r"\bphish"), ("Supply-chain attacks", r"supply[- ]chain|\bnpm\b|\bpypi\b|open-source package"),
        ("Malware", r"\b(malware|trojan|infostealer|stealer|botnet|backdoor|rat)\b"),
        ("State-backed hackers", r"\b(china|chinese|russia(n)?|north korea(n)?|iran(ian)?|apt\d*|state-sponsored|nation-state)\b"),
        ("AI-powered attacks", r"\bai[- ](assisted|powered|driven|generated)|deepfake|\bllm\b"),
        ("Cloud security", r"\b(cloud|aws|azure|kubernetes|saas)\b"), ("Identity & passwords", r"\b(password|credential|mfa|2fa|identity|okta|oauth)\w*"),
        ("Microsoft & Windows", r"\b(microsoft|windows|exchange|outlook)\b"), ("VMware", r"\bvmware|vcenter|esxi\b"),
        ("Linux", r"\blinux\b"), ("Outages", r"\boutage"), ("Healthcare attacks", r"\b(hospital|medical|health)\w*"),
    ],
}


def trends(items, topic):
    counts = Counter()
    for it in items:
        text = (it["title"] + " " + it.get("summary", "")).lower()
        for label, pattern in TOPICS[topic]:
            if re.search(pattern, text):
                counts[label] += 1
    return [{"term": label, "count": n} for label, n in counts.most_common(8) if n >= 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="news.json")
    args = ap.parse_args()
    now = time.time()
    topics, used, failed = {}, [], []
    for topic, feeds in FEEDS.items():
        items = []
        for source, url in feeds:
            try:
                items += parse(source, fetch(url))
                used.append(source)
            except Exception as e:  # one broken feed shouldn't stop the others
                failed.append(f"{source} ({e.__class__.__name__})")
        seen, keep, per = set(), [], Counter()
        for it in sorted(items, key=lambda x: x["published"], reverse=True):
            key = re.sub(r"\W+", "", it["title"].lower())[:60]
            if key in seen or not it["published"] or now - it["published"] > MAX_AGE:
                continue
            if CONSUMER.search(it["title"]) or per[it["source"]] >= PER_SOURCE:
                continue
            if topic == "ai" and (not AI_CORE.search(it["title"] + " " + it.get("summary", "")) or AI_OFFTOPIC.search(it["title"])):
                continue
            seen.add(key)
            per[it["source"]] += 1
            keep.append(it)
        topics[topic] = {"items": keep[:PER_TOPIC], "trends": trends(keep, topic)}
    if not any(t["items"] for t in topics.values()):
        print("No news could be fetched; keeping the previous file.", file=sys.stderr)
        sys.exit(1)
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": used, "topics": topics}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Saved {len(topics['ai']['items'])} AI and {len(topics['security']['items'])} cybersecurity stories to {args.out}"
          + (f" · could not read: {', '.join(failed)}" if failed else ""))


if __name__ == "__main__":
    main()
