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
    words = text.split()
    chunks = []

    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i+max_words]))

    return chunks


# ---------------------------------------
# GPT FUNCTIONS
# ---------------------------------------
def ask_gpt(prompt, model="gpt-4.1-mini"):
    try:
        response = client.responses.create(
            model=model,
            input=prompt
        )
        return response.output_text
    except Exception as e:
        return f"[GPT Error] {e}"


def extract_events_from_chunk(chunk, metadata):
    prompt = f"""
Extract factual events from the article chunk.

### Metadata
Title: {metadata['title']}
Publisher: {metadata['publisher']}
Published: {metadata['published']}
URL: {metadata['url']}

### Chunk:
{chunk}

### Output:
- [time or date if known] Event description (source: {metadata['publisher']})
"""
    return ask_gpt(prompt, "gpt-4.1-mini")


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
    return ask_gpt(prompt, "gpt-4.1")


def translate_timeline(timeline, target_lang):
    prompt = f"""
Translate the following timeline into **{target_lang}**.

### TIMELINE:
{timeline}
"""
    return ask_gpt(prompt, "gpt-4.1-mini")


def extract_key_highlights(timeline):
    prompt = f"""
Extract the **5 most important key events** from the following timeline.

### TIMELINE:
{timeline}

### Output:
## 🔑 Key Highlights
- Bullet points summarizing the most critical events
"""
    return ask_gpt(prompt, "gpt-4.1-mini")


def compare_sources(articles):
    formatted = ""
    for a in articles:
        content = a["content"][:1500] if a["content"] else ""
        formatted += f"""
### Source: {a['publisher']}
Title: {a['title']}
Content:
{content}
"""

    prompt = f"""
Compare the following news sources and highlight:

- Where the articles agree
- Where they disagree
- Unique details in each source
- Contradictions or vague claims

### ARTICLES:
{formatted}

### Output:
## 🆚 Differences Between Sources
- AGREEMENTS:
- DISAGREEMENTS:
- UNIQUE POINTS:
"""
    return ask_gpt(prompt, "gpt-4.1")


# ---------------------------------------
# STREAMLIT APP
# ---------------------------------------
st.title("📰 Multi-Article Incident Timeline Generator")
st.write("Enter a topic to fetch news, extract text, and build a chronological event timeline.")

query = st.text_input("Search topic", placeholder="ex: Bengaluru metro accident", key="query_input")

# ---------------------------------------
# SEARCH BUTTON
# ---------------------------------------
if st.button("Search", key="search_btn"):
    if not query.strip():
        st.error("Please enter a search term.")
        st.stop()

    with st.spinner("Fetching Google News results..."):
        entries = search_google_news(query)

    st.success(f"Found {len(entries)} articles.")

    articles_data = []

    for idx, entry in enumerate(entries[:10]):
        st.write(f"### Article {idx+1}")

        google_url = entry.link
        title = entry.title
        published = entry.get("published", "Unknown")
        publisher = entry.get("source", {}).get("title", "Unknown")

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

    timeline = merge_events_to_timeline("\n".join(all_events))

    st.session_state['timeline'] = timeline
    st.session_state['articles_data'] = articles_data
    st.session_state['translated_timeline'] = ""
    st.session_state['highlights'] = ""
    st.session_state['comparison'] = ""

    st.success("Timeline generated!")
    st.write("## 🧭 Final Chronological Timeline")
    st.write(timeline)
    st.write("---")


# ---------------------------------------------------------
# EXTRA FEATURES (Persisted with session_state)
# ---------------------------------------------------------
st.subheader("✨ Additional Analysis Options")

if "timeline" not in st.session_state:
    st.info("Run a search first to enable Translate / Highlights / Compare.")
    st.stop()


# 1. TRANSLATE
st.write("### 🌐 Translate Timeline")
target_lang = st.text_input("Target language (ex: Tamil, Hindi, Kannada)",
                           key="target_lang_input")

if st.button("Translate", key="translate_btn"):
    with st.spinner("Translating..."):
        result = translate_timeline(st.session_state["timeline"], target_lang)
        st.session_state["translated_timeline"] = result
    st.success("Translation complete!")

if st.session_state.get("translated_timeline"):
    st.write("## 🌐 Translated Timeline")
    st.write(st.session_state["translated_timeline"])
    st.write("---")


# 2. HIGHLIGHTS
st.write("### 🔎 Get Key Highlights")
if st.button("Show Key Highlights", key="highlights_btn"):
    with st.spinner("Extracting highlights..."):
        result = extract_key_highlights(st.session_state["timeline"])
        st.session_state["highlights"] = result
    st.success("Highlights extracted!")

if st.session_state.get("highlights"):
    st.write("## 🔑 Key Highlights")
    st.write(st.session_state["highlights"])
    st.write("---")


# 3. SOURCE COMPARISON
st.write("### 🆚 Compare Sources")
if st.button("Compare Articles", key="compare_btn"):
    with st.spinner("Comparing articles..."):
        result = compare_sources(st.session_state["articles_data"])
        st.session_state["comparison"] = result
    st.success("Comparison complete!")

if st.session_state.get("comparison"):
    st.write(st.session_state["comparison"])
    st.write("---")


# DOWNLOAD TIMELINE
st.download_button("Download Timeline",
                   st.session_state["timeline"],
                   file_name="timeline.txt")