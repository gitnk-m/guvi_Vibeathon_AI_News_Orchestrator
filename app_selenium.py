import streamlit as st
import feedparser
import trafilatura
from dateutil import parser
from datetime import datetime
import time

# Selenium imports (correct usage)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

st.set_page_config(page_title="AI News Timeline", layout="wide")

# ------------------------------------------------------
# 1. Selenium – Resolve REAL URL from Google News redirect
# ------------------------------------------------------
def resolve_real_url(google_url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    # Correct Selenium 4 syntax
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(google_url)
        time.sleep(2)  # Wait for redirect
        return driver.current_url
    except Exception as e:
        print("URL resolve error:", e)
        return google_url
    finally:
        driver.quit()

# ------------------------------------------------------
# 2. Fetch Search Results from Google News RSS
# ------------------------------------------------------
def search_google_news(query):
    query=query.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(rss_url)
    return feed.entries

# ------------------------------------------------------
# 3. Extract Article Content (Trafilatura)
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
# 4. Very Basic Text Summarizer
# ------------------------------------------------------
def summarize(text, max_sentences=3):
    if not text:
        return "No summary available."

    sentences = text.replace("\n", " ").split(". ")
    return ". ".join(sentences[:max_sentences]) + "."

# ------------------------------------------------------
# 5. Build Timeline (resolve URL → extract text → summarize)
# ------------------------------------------------------
def build_timeline(entries):
    events = []

    for entry in entries[:3]:
        st.write(f"🔗 Resolving source: **{entry.title}**")

        # Step 1: Real URL via Selenium
        real_url = resolve_real_url(entry.link)

        # Step 2: Extract readable text
        text = extract_text(real_url)

        # Step 3: Publication date fallback
        try:
            published = parser.parse(entry.published)
        except:
            published = None

        if text:
            summary = summarize(text)
            events.append({
                "title": entry.title,
                "url": real_url,
                "published": published,
                "summary": summary
            })

    # Sort chronologically
    events.sort(key=lambda x: x["published"] or datetime.now())
    return events

# ------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------
st.title("📰 AI News Search → Chronological Timeline (Selenium Powered)")

query = st.text_input("Search News", placeholder="Example: Budget 2025, Chandrayaan, India Elections")

if query:
    entries = search_google_news(query)
    st.write(f"Found **{len(entries)}** articles.")

    if st.button("Generate Timeline"):
        with st.spinner("Reading articles using Selenium + Trafilatura…"):
            timeline = build_timeline(entries)

        st.subheader("🕒 Chronological Timeline of Events")
        st.write("---")

        if len(timeline) == 0:
            st.warning("No extractable articles. Try another topic.")
        else:
            for event in timeline:
                st.markdown(f"""
                ### 🗓 {event['published'].strftime('%Y-%m-%d %H:%M') if event['published'] else 'Unknown Date'}
                #### {event['title']}

                {event['summary']}

                🔗 [Read Full Article]({event['url']})
                ---
                """)
