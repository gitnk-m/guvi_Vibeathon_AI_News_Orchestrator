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
import json

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------
# GOOGLE NEWS FUNCTIONS
# ---------------------------------------------------------
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
            return trafilatura.extract(downloaded)
    except:
        return None
    return None


# ---------------------------------------------------------
# TEXT CHUNKING
# ---------------------------------------------------------
def chunk_text(text, max_words=300):
    words = text.split()
    chunks = []

    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i + max_words]))

    return chunks


# ---------------------------------------------------------
# GPT WRAPPER
# ---------------------------------------------------------
def ask_gpt(prompt, model="gpt-4.1-mini"):
    try:
        response = client.responses.create(model=model, input=prompt)
        return response.output_text
    except Exception as e:
        return f"[GPT Error] {e}"


# ---------------------------------------------------------
# EVENT EXTRACTION
# ---------------------------------------------------------
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
4. Arrange in chronological order

### EVENTS:
{events_list}
"""
    return ask_gpt(prompt, "gpt-4.1")


# ---------------------------------------------------------
# NEW FEATURE: CREDIBILITY SCORING
# ---------------------------------------------------------
def get_credibility_score(article):
    prompt = f"""
Analyze the credibility of this news article and give a score (0-100).

### Criteria:
- Reputed publisher
- Specific details (names, dates, numbers)
- Direct quotes
- Neutral language
- Internal consistency
- Avoids vague claims
- Completeness

### Article:
Title: {article['title']}
Publisher: {article['publisher']}
Published: {article['published']}

Content:
{article['content'][:1200]}

### Output strictly in JSON:
{{
  "score": number,
  "reason": "short explanation"
}}
"""
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )
        return response.output_text
    except:
        return '{"score": 50, "reason": "Unable to calculate"}'


# ---------------------------------------------------------
# NEW FEATURE: BEAUTIFUL UI CARDS
# ---------------------------------------------------------
def render_article_card(article, credibility_json):
    try:
        data = json.loads(credibility_json)
    except:
        data = {"score": 50, "reason": "Invalid JSON"}

    score = int(data.get("score", 50))
    reason = data.get("reason", "No explanation given.")

    # Color coding
    if score >= 75:
        color = "#4CAF50"
    elif score >= 50:
        color = "#FFC107"
    else:
        color = "#F44336"

    st.markdown(f"""
    <div style="
        background-color: #ffffff;
        padding: 16px;
        border-radius: 14px;
        box-shadow: 0 3px 8px rgba(0,0,0,0.12);
        margin-bottom: 20px;
        border-left: 6px solid {color};
        color: #333333;
    ">
        <h4 style="margin-top: 0;">{article['title']}</h4>
        <p><b>Publisher:</b> {article['publisher']}<br>
        <b>Published:</b> {article['published']}<br>
        <b>Credibility Score:</b> 
        <span style="color:{color}; font-weight:600;">{score}/100</span>
        </p>
        <p style="word-wrap: break-word;">Credibility Analysis:<br>{reason}</p>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------
# TRANSLATE + HIGHLIGHTS + COMPARE
# ---------------------------------------------------------
def translate_timeline(timeline, target_lang):
    prompt = f"""
Translate the timeline into **{target_lang}**:

### TIMELINE:
{timeline}
"""
    return ask_gpt(prompt, "gpt-4.1-mini")


def extract_key_highlights(timeline):
    prompt = f"""
Extract the **5 most important events** from this timeline.

### TIMELINE:
{timeline}

### Output:
## 🔑 Key Highlights
- Bullet points
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
Compare these articles:

### ARTICLES:
{formatted}

### Output:
- AGREEMENTS:
- DIFFERENCES:
- UNIQUE DETAILS:
"""
    return ask_gpt(prompt, "gpt-4.1")


# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------
st.title("📰 AI News Orchestrator - Event Timeline Generator")

query = st.text_input("Search topic", placeholder="ex: Bengaluru metro accident", key="query_input")


# ---------------------------------------------------------
# SEARCH BUTTON
# ---------------------------------------------------------
if st.button("Search", key="search_btn"):

    if not query.strip():
        st.error("Enter a search term.")
        st.stop()

    with st.spinner("Fetching Google News..."):
        entries = search_google_news(query)

    st.success(f"Found {len(entries)} articles.")

    articles_data = []

    for idx, entry in enumerate(entries[:10]):
        st.write(f"### Article {idx + 1}")

        google_url = entry.link
        title = entry.title
        published = entry.get("published", "Unknown")
        publisher = entry.get("source", {}).get("title", "Unknown")

        st.write("Resolving URL...")
        real_url = resolve_real_url(google_url)

        st.write(real_url)

        st.write("Extracting text...")
        text = extract_text(real_url)

        if text is None:
            st.warning("Could not extract content.")
            continue

        # Build article object
        article_obj = {
            "title": title,
            "publisher": publisher,
            "published": published,
            "url": real_url,
            "content": text
        }

        # Get credibility
        st.write("Calculating credibility...")
        cred_json = get_credibility_score(article_obj)
        article_obj["credibility"] = cred_json

        # Save article
        articles_data.append(article_obj)

        # Render card
        render_article_card(article_obj, cred_json)

        st.success("Article processed.")

    # EVENT EXTRACTION
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

    st.session_state["timeline"] = timeline
    st.session_state["articles_data"] = articles_data
    st.session_state["translated_timeline"] = ""
    st.session_state["highlights"] = ""
    st.session_state["comparison"] = ""

    st.success("Timeline generated!")
    st.write("## 🧭 Final Chronological Timeline")
    st.write(timeline)
    st.write("---")


# ---------------------------------------------------------
# EXTRA FEATURES
# ---------------------------------------------------------
st.subheader("✨ Additional Analysis Options")

if "timeline" not in st.session_state:
    st.info("Search something first.")
    st.stop()

# TRANSLATION
st.write("### 🌐 Translate Timeline")
target_lang = st.text_input("Language (ex: Tamil, Hindi)", key="lang_input")

if st.button("Translate", key="translate_btn"):
    with st.spinner("Translating..."):
        out = translate_timeline(st.session_state["timeline"], target_lang)
        st.session_state["translated_timeline"] = out
    st.success("Done!")

if st.session_state.get("translated_timeline"):
    st.write("## 🌐 Translated Timeline")
    st.write(st.session_state["translated_timeline"])
    st.write("---")

# HIGHLIGHTS
st.write("### 🔎 Key Highlights")
if st.button("Show Key Highlights", key="highlight_btn"):
    with st.spinner("Extracting key events..."):
        out = extract_key_highlights(st.session_state["timeline"])
        st.session_state["highlights"] = out
    st.success("Done!")

if st.session_state.get("highlights"):
    st.write("## 🔑 Key Highlights")
    st.write(st.session_state["highlights"])
    st.write("---")

# COMPARE ARTICLES
st.write("### 🆚 Compare Sources")
if st.button("Compare Articles", key="compare_btn"):
    with st.spinner("Comparing..."):
        out = compare_sources(st.session_state["articles_data"])
        st.session_state["comparison"] = out
    st.success("Done!")

if st.session_state.get("comparison"):
    st.write(st.session_state["comparison"])
    st.write("---")


# DOWNLOAD
st.download_button("Download Timeline", st.session_state["timeline"], file_name="timeline.txt")
