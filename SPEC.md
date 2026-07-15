This product specification outlines the requirements for the **"Zero-Cost Story Factory,"** a local-first web application designed to automate the production of high-retention "Reddit story" style videos with "addicting" split-screen layouts for TikTok, YouTube Shorts, and Instagram Reels.

# SPEC.md: Zero-Cost Story Factory

## 1. Product Overview
The software creates a "zero-marginal-cost content factory" by automating the conversion of text-based stories (Reddit, custom text) into vertical videos. It eliminates the need for expensive SaaS subscriptions by leveraging free AI API tiers and local hardware for video rendering. The signature output is a **Vertical Stack** layout featuring story content on the top half and "addicting" gameplay (Minecraft parkour, satisfying clips) on the bottom half, overlaid with word-by-word karaoke subtitles.

## 2. User Stories
*   **The Content Repurposer:** "I want to paste a Reddit URL and get a ready-to-post vertical video in minutes without manually editing frames".
*   **The Viral Strategist:** "I want to use 'addicting' background footage to stretch watch time and maximize retention through word-by-word highlighted captions".
*   **The Budget-Conscious Creator:** "I want to generate 15+ videos a day for $0 in cloud or subscription fees".

## 3. Functional Requirements

### A. Ingestion & Narrative Cleaning
*   **Reddit Scraper:** Extract title and body text from a provided URL.
*   **Script Optimization:** Use **Google Gemma 31b** (free tier) to clean the text, removing non-narrative elements (e.g., "Edit:", links, timestamps) to ensure smooth narration.
*   **Asset Management:** A dashboard to manage local folders of "addicting" B-roll (e.g., `/assets/minecraft/`, `/assets/satisfying/`).

### B. Audio Engine
*   **Narration (TTS):** Integrate **edge-tts** for high-quality, natural-sounding voiceovers that require no API keys or costs.
*   **Word-Level Transcription:** Use the **Groq Whisper API** to process the generated narration and return a JSON transcript with millisecond-accurate word-level timestamps.

### C. Visual Assembly (Programmatic Rendering)
*   **Vertical Stack Layout:**
    *   **Top 50%:** A blurred or dimmed frame featuring the story's Reddit UI element or a generated thumbnail.
    *   **Bottom 50%:** A randomly selected 9:16 clip from the user's "addicting" B-roll pool.
*   **Karaoke Subtitles:** Convert JSON timestamps into **SubStation Alpha (.ass)** files to render word-by-word highlighted text with "Alex Hormozi" style animations (bounces, scale steps).
*   **Audio Engineering:** Implement **sidechain ducking** to automatically lower background music (BGM) volume when the narrator is speaking.

## 4. Technical Architecture (Tech Stack)

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | **Next.js 15 + Shadcn UI** | Professional dashboard for asset management and job tracking. |
| **Backend** | **Python (FastAPI)** | Orchestrates scraping, TTS generation, and transcription calls. |
| **Video Engine** | **Remotion** | React-based framework for treating video layers and CSS animations as code. |
| **Compute** | **Local Workstation** | Utilizes local GPU (NVENC/VideoToolbox) to keep rendering costs at **absolute zero**. |
| **AI (LLM)** | **Google Gemini 1.5 Flash** | Free-tier (1,500 req/day) for script cleaning and metadata generation. |

## 5. System Pipeline Workflow
1.  **Input:** User pastes Reddit URL + Selects "Minecraft" or "Satisfying" background pool.
2.  **Curation:** Python backend scrapes text and Gemma cleans the script for a 60–90 second narrative.
3.  **Voice:** `edge-tts` generates the `narration.mp3` file.
4.  **Sync:** Groq Whisper transcribes the MP3 into word-level JSON.
5.  **Render:** **Remotion** picks a random B-roll clip, layers it with the story UI and `.ass` subtitles, then renders the final MP4 using local hardware acceleration.

## 6. Profitability & Growth Strategy
*   **High Volume Output:** Deliver **15+ high-quality Shorts** per day, which statistically leads to 20–30% faster subscriber growth.
*   **Originality:** The use of fresh AI voiceovers and unique background gameplay helps bypass "reused content" flags that affect simple streamer clipping channels.
*   **SEO Automation:** The system will automatically generate optimized titles (<70 chars) and keyword-rich descriptions for YouTube.

## 7. Development Roadmap
*   **v1.0:** Core local-first pipeline (Reddit -> edge-tts -> Groq -> Remotion).
*   **v1.1:** Shadcn-based "Asset Manager" for B-roll pool management.
*   **v1.2:** "Story Clip Mode" to allow users to manually edit/correct transcripts before the final render.
