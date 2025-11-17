# --------------------------------------------------------------
# news_timeline_app.py
# --------------------------------------------------------------
import os
import json
import httpx
import feedparser
import trafilatura
import dateparser
from datetime import datetime
from typing import List, Dict, Any, Optional

import streamlit as st
from dotenv import load_dotenv

# --------------------------------------------------------------
# Load environment variables (Groq API key)
# --------------------------------------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("❗ Groq API key not found. Please create a .env file with GROQ_API_KEY.")
    st.stop()

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

# --------------------------------------------------------------
# 1️⃣ Google‑News RSS search
# --------------------------------------------------------------
def google_news_rss(query: str, max_items: int = 20) -> List[Dict[str, Any]]:
    """Return a list of dicts: title, link, published (datetime), summary."""
    q = query.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)

    items = []
    for entry in feed.entries[:max_items]:
        pub_dt = datetime(*entry.published_parsed[:6])
        items.append({
            "title": entry.title,
            "link": entry.link,
            "published": pub_dt,
            "summary": entry.summary,
        })
    return items

# --------------------------------------------------------------
# 2️⃣ Full‑article extraction (trafilatura)
# --------------------------------------------------------------
def fetch_full_article(url: str) -> Optional[Dict[str, Any]]:
    """Return dict with title, text, publish_date (datetime or None)."""
    downloaded = trafilatura.fetch_url(url, timeout=10)
    if not downloaded:
        return None

    result = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        output_format="json",
    )
    if not result:
        return None

    data = json.loads(result)

    # Try to parse a date from the metadata (many sites store ISO strings)
    raw_date = data.get("date")
    publish_date = None
    if raw_date:
        try:
            publish_date = dateparser.parse(raw_date)
        except Exception:
            pass

    return {
        "title": data.get("title") or "",
        "text": data.get("content") or "",
        "publish_date": publish_date,
    }

# --------------------------------------------------------------
# 3️⃣ Summarise with Groq LLM
# --------------------------------------------------------------
def summarize_with_groq(text: str, max_tokens: int = 300) -> str:
    """Send `text` to Groq and receive a concise 2‑3‑sentence summary."""
    # Trim to a safe size for the model's context window
    trimmed = text[:4000]

    system_prompt = (
        "You are a neutral news summariser. Produce a short (2‑3 sentence) "
        "summary that captures the main facts, key dates, people and places. "
        "Do not add any opinion."
    )
    user_prompt = f"Summarise the following article:\n\n{trimmed}"

    payload = {
        "model": "llama3-8b-8192",          # change if you prefer another model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    response = httpx.post(GROQ_ENDPOINT, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()

# --------------------------------------------------------------
# 4️⃣ End‑to‑end pipeline (used by Streamlit)
# --------------------------------------------------------------
def build_timeline(query: str, max_articles: int = 7) -> List[Dict[str, Any]]:
    """
    Returns a list of dicts (title, url, published, summary) sorted
    from oldest to newest.
    """
    rss_items = google_news_rss(query, max_items=max_articles * 2)  # fetch a few extra

    timeline = []
    for item in rss_items:
        article = fetch_full_article(item["link"])
        if not article or not article["text"]:
            continue

        # Prefer article's own publish date; fallback to RSS date
        pub_date = article["publish_date"] or item["published"]

        # Summarise with Groq
        try:
            summary = summarize_with_groq(article["text"])
        except Exception as e:
            summary = f"⚠️ Summarisation failed: {e}"

        timeline.append({
            "title": article["title"] or item["title"],
            "url": item["link"],
            "published": pub_date,
            "summary": summary,
        })

        if len(timeline) >= max_articles:
            break

    # Chronological order (oldest → newest)
    timeline.sort(key=lambda x: x["published"])
    return timeline

# --------------------------------------------------------------
# 5️⃣ Streamlit UI
# --------------------------------------------------------------
st.set_page_config(page_title="News Timeline", layout="centered")
st.title("🗞️ News Timeline – Google News + Groq")
st.caption(
    "Enter a topic, the app fetches the latest Google‑News results, reads each article, "
    "summarises it with a Groq LLM and shows the events in chronological order."
)

# ----- Sidebar controls -----
with st.sidebar:
    st.header("⚙️ Settings")
    query = st.text_input("Search query", value="Apple iPhone launch")
    max_articles = st.slider(
        "Maximum articles to summarise", min_value=3, max_value=15, value=7, step=1
    )
    run_button = st.button("🔎 Get timeline")

# ----- Main logic -----
if run_button:
    if not query.strip():
        st.error("Please type a search query.")
    else:
        with st.spinner("Fetching news, extracting articles, summarising…"):
            try:
                timeline = build_timeline(query, max_articles=max_articles)
            except Exception as exc:
                st.error(f"❗ Unexpected error: {exc}")
                st.stop()

        if not timeline:
            st.warning("No articles could be processed. Try a different query.")
        else:
            st.success(f"✅ Found {len(timeline)} summarised articles")
            for entry in timeline:
                date_str = entry["published"].strftime("%Y-%m-%d %H:%M")
                st.markdown(
                    f"""
                    **{date_str}** – [{entry['title']}]({entry['url']})
                    
                    {entry['summary']}
                    """,
                    unsafe_allow_html=False,
                )
                st.divider()