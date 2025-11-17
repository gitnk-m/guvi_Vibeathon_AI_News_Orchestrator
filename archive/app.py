import streamlit as st
import feedparser
from newspaper import Article
from dateutil import parser
import time

st.set_page_config(page_title="AI News Timeline", layout="wide")

# -----------------------------
# Fetch RSS search results
# -----------------------------
def search_google_news(query):
    query=query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    return feed.entries

# -----------------------------
# Extract content from each article
# -----------------------------
def extract_article(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        article.nlp()
        return article.title, article.summary, article.published
    except:
        return None, None, None

# -----------------------------
# Build timeline from multiple articles
# -----------------------------
def build_timeline(entries):
    timeline = []

    for item in entries:
        title, summary, pub = extract_article(item.link)

        # fallback if no publish date from newspaper3k
        if not pub:
            try:
                pub = parser.parse(item.published)
            except:
                pub = None

        if title and summary:
            timeline.append({
                "title": title,
                "summary": summary,
                "published": pub,
                "url": item.link
            })

        time.sleep(0.2)  # avoid rate limits

    # sort by published date
    timeline.sort(key=lambda x: x["published"] or 0)
    return timeline

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("🔍 AI News Search → Timeline Summary")

query = st.text_input("Enter a topic to search", placeholder="Example: Indian Budget 2025")

if query:
    st.write("### Searching news…")
    entries = search_google_news(query)
    st.write(f"Found **{len(entries)}** news articles")

    if st.button("Generate Timeline"):
        with st.spinner("Reading articles and building timeline…"):
            timeline = build_timeline(entries)

        st.write("## 🕒 Chronological Event Timeline")

        for event in timeline:
            st.markdown(f"""
            **🗓 {event['published'].strftime('%Y-%m-%d %H:%M') if event['published'] else 'Unknown time'}**

            ### {event['title']}
            {event['summary']}

            🔗 [Read Full Article]({event['url']})
            ---
            """)

        if len(timeline) == 0:
            st.warning("Could not extract meaningful events. Try another topic.")
