# 📰 Multi-Article Incident Timeline Generator — *hooray! Edition* 🎉

This application fetches multiple news articles about a real-world incident, extracts factual events using LLMs, and produces a clean, chronological timeline.  
It also evaluates **article credibility**, displays **beautiful UI article cards**, and provides additional features like translation, highlights, and source comparison.

---

## 🚀 Features

### ✅ **1. Google News Powered Search**
Fetches real-time news from Google News RSS based on user-provided keywords.

### ✅ **2. Smart URL Resolution**
Uses Selenium to convert Google News redirect URLs into the real publisher URL.

### ✅ **3. Article Text Extraction**
Extracts full article text using Trafilatura.

### ✅ **4. Credibility Scoring (LLM-Based)**
Each article receives:
- A **score (0–100)**
- A **reason**
- Color-coded UI card  
(Green = Highly credible, Yellow = Medium, Red = Low)

### ✅ **5. Chunking for Accurate LLM Processing**
Splits long articles into safe 300-word chunks.

### ✅ **6. Event Extraction per Chunk**
LLM extracts key events with timestamps, actors, and details.

### ✅ **7. Timeline Merging**
A second LLM merges events chronologically by:
- Removing duplicates  
- Fixing conflicts  
- Normalizing inconsistent timestamps  

### ✅ **8. Additional Analysis Tools**
- 🌐 Translate timeline (any language)
- 🔎 Extract top 5 key highlights
- 🆚 Compare sources for differences

### ✅ **9. Download Output**
Export final timeline as a `.txt` file.

---

## 🧩 System Architecture

### **High-Level Pipeline**
