import streamlit as st
import feedparser
import trafilatura
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from openai import OpenAI
from dotenv import load_dotenv
import os
import re

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# --------------------------
# GOOGLE NEWS FUNCTIONS
# --------------------------
def search_google_news(query, region="IN", lang="en-IN"):
    query = query.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={region}&ceid={region}:en"
    feed = feedparser.parse(rss_url)
    return feed.entries


def resolve_real_url(google_url, headless=True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(google_url)
        time.sleep(1.2)
        return driver.current_url
    except:
        return google_url
    finally:
        driver.quit()


def extract_text(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            return text
    except:
        return None
    return None


# ---------------------------------------
# CHUNKING FUNCTION
# ---------------------------------------
def chunk_text(text, max_words=300):
    sentences = re.split(r'(?<=[.?!])\s+', text)
    chunks, current = [], ""

    for s in sentences:
        if len((current + s).split()) < max_words:
            current += " " + s
        else:
            chunks.append(current.strip())
            current = s

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ---------------------------------------
# GPT EVENT EXTRACTION
# ---------------------------------------
def extract_events_from_chunk(chunk, metadata):
    prompt = f"""
Extract factual events from this article chunk.

### Metadata
Title: {metadata['title']}
Publisher: {metadata['publisher']}
Published Date: {metadata['published']}
URL: {metadata['url']}

### Chunk:
{chunk}

### Output format (strict):
- [time or date if known] Event description (source: {metadata['publisher']})
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text


def merge_events_to_timeline(events_list):
    prompt = f"""
The following events came from multiple articles about the same incident.

Your tasks:
1. Merge them
2. Remove duplicates
3. Resolve conflicts using published dates
4. Arrange them in chronological order
5. Output a clean timeline

### EVENTS:
{events_list}
"""

    response = client.responses.create(
        model="gpt-4.1",
        input=prompt
    )

    return response.output_text


# ---------------------------------------
# STREAMLIT APP
# ---------------------------------------
st.title("📰 Multi-Article Incident Timeline Generator")
st.write("Enter a topic, I will fetch news, extract article text, and create a chronological timeline of events.")

query = st.text_input("Search topic", placeholder="ex: Bengaluru metro accident")

if st.button("Search"):
    if not query.strip():
        st.error("Please enter a search term.")
        st.stop()

    with st.spinner("Fetching Google News results..."):
        entries = search_google_news(query)

    st.success(f"Found {len(entries)} articles.")

    articles_data = []

    for idx, entry in enumerate(entries[:10]):  # limit to 10 for speed
        st.write(f"### Article {idx+1}")

        google_url = entry.link
        title = entry.title
        published = entry.published if "published" in entry else "Unknown"
        publisher = entry.source.title if "source" in entry else "Unknown"

        st.write("Resolving article URL...")
        real_url = resolve_real_url(google_url)

        st.write(real_url)

        st.write("Extracting text...")
        text = extract_text(real_url)

        if text is None:
            st.warning("Could not extract content.")
            continue

        articles_data.append({
            "title": title,
            "publisher": publisher,
            "published": published,
            "url": real_url,
            "content": text
        })

        st.success("Content extracted.")

    st.subheader("⏳ Extracting events from all articles...")

    all_events = []

    for article in articles_data:
        chunks = chunk_text(article["content"])

        metadata = {
            "title": article["title"],
            "publisher": article["publisher"],
            "published": article["published"],
            "url": article["url"]
        }

        for chunk in chunks:
            events = extract_events_from_chunk(chunk, metadata)
            all_events.append(events)

    st.subheader("📅 Merging events into timeline")
    timeline = merge_events_to_timeline("\n".join(all_events))

    st.success("Timeline generated!")
    st.write("---")
    st.write("## 🧭 Final Chronological Timeline")
    st.write(timeline)
    st.write("---")
    st.download_button("Download Timeline", timeline, file_name="timeline.txt")
