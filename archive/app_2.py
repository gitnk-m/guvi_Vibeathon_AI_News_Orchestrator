import streamlit as st
import feedparser
import trafilatura
from dateutil import parser
from datetime import datetime

st.set_page_config(page_title="AI News Timeline", layout="wide")


# ------------------------------------------------------
# 1. Fetch Search Results from Google News RSS
# ------------------------------------------------------
def search_google_news(query):
    query=query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    return feed.entries


# ------------------------------------------------------
# 2. Extract REAL article URL (very important)
# ------------------------------------------------------
def get_real_url(entry):
    # Google RSS gives the real link in links[0]['href']
    try:
        return entry.links[0]['href']
    except:
        return entry.link  # fallback


# ------------------------------------------------------
# 3. Extract full article text using Trafilatura
# ------------------------------------------------------
def extract_text(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            return text
        return None
    except:
        return None


# ------------------------------------------------------
# 4. Summarize text (simple non-LLM summarizer)
# ------------------------------------------------------
def basic_summarize(text, max_sentences=3):
    if not text:
        return "No summary available."

    sentences = text.replace("\n", " ").split(". ")
    return ". ".join(sentences[:max_sentences]) + "."


# ------------------------------------------------------
# 5. Build chronological timeline
# ------------------------------------------------------
def build_timeline(entries):
    events = []

    for entry in entries:
        real_url = get_real_url(entry)

        text = extract_text(real_url)

        # fallback date from RSS
        try:
            pub = parser.parse(entry.published)
        except:
            pub = None

        if text:
            summary = basic_summarize(text)
            events.append({
                "title": entry.title,
                "url": real_url,
                "published": pub,
                "summary": summary
            })

    # Sort by publish date
    events.sort(key=lambda x: x["published"] or datetime.now())
    return events


# ------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------
st.title("🔍 AI News Search → Chronological Event Timeline")

query = st.text_input("Enter a topic to search", placeholder="Example: Chandrayaan, Budget 2025, Election India")


if query:
    entries = search_google_news(query)
    st.write(f"Found **{len(entries)}** news articles")

    if st.button("Generate Timeline"):
        with st.spinner("Fetching and summarizing articles…"):
            timeline = build_timeline(entries)

        st.write("## 🕒 Chronological Timeline of Events")

        if len(timeline) == 0:
            st.warning("Could not extract content for any articles. Try a different topic.")
        else:
            for event in timeline:
                st.markdown(f"""
                ### 🗓 {event['published'].strftime('%Y-%m-%d %H:%M') if event['published'] else 'Unknown date'}
                #### {event['title']}

                {event['summary']}

                🔗 [Read Full Article]({event['url']})
                ---
                """)
