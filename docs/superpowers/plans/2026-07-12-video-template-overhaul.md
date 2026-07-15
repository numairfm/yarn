# Video Template Overhaul & Multi-Part Splitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the Remotion video template (karaoke subtitles, Reddit card, multi-part splitting) and add landscape combining via FFmpeg.

**Architecture:** Backend LLM returns JSON with title, subreddit, and parts array. Each part goes through TTS → transcribe → Remotion render. FFmpeg concatenates parts into a landscape video with blurred backdrop. Frontend shows stage-by-stage progress.

**Tech Stack:** Remotion (React/TypeScript), Python FastAPI, edge-tts, Groq Whisper, OpenAI-compatible LLM, FFmpeg, Next.js

## Global Constraints

- Python venv at `backend/.venv/bin/python`
- Remotion invoked as subprocess: `npx remotion render StoryVideo <output> --props=<json> --timeout=120000`
- Files served to Remotion via local `ThreadingHTTPServer` on random port
- LLM: OpenCode Zen API at `https://opencode.ai/zen/v1`, model `mimo-v2.5-free`, key `OPENCODE_API_KEY`
- TTS: `edge-tts` v7.2.8, voice `en-US-JennyNeural`
- Transcription: Groq Whisper `whisper-large-v3`, key `GROQ_API_KEY`
- Frontend proxies `/api/proxy/:path*` to `http://localhost:8000/api/:path*`
- No test framework — use inline assertions / manual verification

---

## File Structure

| File | Responsibility |
|------|---------------|
| `remotion/src/types.ts` | TypeScript interfaces for Remotion props |
| `remotion/src/components/KaraokeSubtitles.tsx` | Windowed karaoke subtitles with borders |
| `remotion/src/components/StoryTop.tsx` | White Reddit card with logo, subreddit, part badge, fade-out |
| `remotion/src/StoryVideo.tsx` | Main composition, passes new props to children |
| `backend/main.py` | Pipeline orchestration: LLM prompt, subreddit extraction, per-part render, FFmpeg combine, new endpoints |
| `frontend/src/app/page.tsx` | Stage labels, multi-part progress, combined video display |

---

### Task 1: Update Remotion Types

**Files:**
- Modify: `remotion/src/types.ts`

**Interfaces:**
- Produces: `InputProps` with new optional fields `subreddit`, `partNumber`, `titleEndMs`

- [ ] **Step 1: Update types.ts**

```typescript
export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

export interface InputProps {
  narrationPath: string;
  words: WordTimestamp[];
  storyTitle: string;
  storyBody: string;
  brollClip: string;
  durationFrames?: number;
  subreddit?: string;
  partNumber?: number;
  titleEndMs?: number;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd remotion && node_modules/.bin/tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add remotion/src/types.ts
git commit -m "feat: add subreddit, partNumber, titleEndMs to InputProps"
```

---

### Task 2: Karaoke Subtitles — Windowed Display, Borders, Bigger Text

**Files:**
- Modify: `remotion/src/components/KaraokeSubtitles.tsx`

**Interfaces:**
- Consumes: `WordTimestamp[]` from props (unchanged)
- Produces: Windowed karaoke subtitles component

- [ ] **Step 1: Rewrite KaraokeSubtitles.tsx**

```tsx
import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import type { WordTimestamp } from "../types";

interface Props {
  words: WordTimestamp[];
}

const COLORS = {
  inactive: "rgba(255,255,255,0.4)",
  active: "#FFD700",
  passed: "rgba(255,255,255,0.9)",
};

const WINDOW = 3;

export const KaraokeSubtitles = ({ words }: Props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;

  if (!words.length) return null;

  const activeIdx = words.findIndex(
    (w) => currentMs >= w.start && currentMs <= w.end
  );
  const currentIdx = activeIdx === -1 ? 0 : activeIdx;

  const start = Math.max(0, currentIdx - WINDOW);
  const end = Math.min(words.length, currentIdx + WINDOW + 1);
  const visibleWords = words.slice(start, end);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 120,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        flexWrap: "wrap",
        padding: "20px 40px",
        gap: 10,
        zIndex: 100,
      }}
    >
      {visibleWords.map((w, i) => {
        const globalIdx = start + i;
        const isActive = globalIdx === activeIdx;
        const isPassed = currentMs > w.end;

        const scale = isActive
          ? spring({
              frame: frame - (w.start / 1000) * fps,
              fps,
              config: { damping: 12, stiffness: 200 },
            }) * 0.15 + 1
          : 1;

        const color = isActive
          ? COLORS.active
          : isPassed
          ? COLORS.passed
          : COLORS.inactive;

        return (
          <span
            key={globalIdx}
            style={{
              fontSize: 56,
              fontWeight: isActive ? 800 : 600,
              fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
              color,
              display: "inline-block",
              transform: `scale(${scale})`,
              WebkitTextStroke: isActive ? "3px black" : "2px black",
              WebkitTextFillColor: color,
              lineHeight: 1.2,
            }}
          >
            {w.word}
          </span>
        );
      })}
    </div>
  );
};
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd remotion && node_modules/.bin/tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add remotion/src/components/KaraokeSubtitles.tsx
git commit -m "feat: windowed karaoke subtitles with borders and bigger text"
```

---

### Task 3: StoryTop — White Reddit Card with Logo, Subreddit, Fade-Out

**Files:**
- Modify: `remotion/src/components/StoryTop.tsx`

**Interfaces:**
- Consumes: `title: string`, `subreddit?: string`, `partNumber?: number`, `titleEndMs?: number`
- Produces: White card component that fades out after title narration

- [ ] **Step 1: Rewrite StoryTop.tsx**

```tsx
import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

interface Props {
  title: string;
  subreddit?: string;
  partNumber?: number;
  titleEndMs?: number;
}

const RedditLogo = () => (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
    <circle cx="16" cy="16" r="16" fill="#FF4500" />
    <path
      d="M26 16c0-1.1-.9-2-2-2-.5 0-1 .2-1.3.5-1.3-.9-3-1.4-4.9-1.5l.8-3.8 2.6.6c0 .7.6 1.3 1.3 1.3.7 0 1.3-.6 1.3-1.3 0-.7-.6-1.3-1.3-1.3-.5 0-.9.3-1.1.7l-3-.7c-.1 0-.3.1-.3.2l-.9 4.3c-1.9.1-3.6.6-4.9 1.5-.3-.3-.8-.5-1.3-.5-1.1 0-2 .9-2 2 0 .8.4 1.4 1.1 1.7 0 .2-.1.4-.1.6 0 2.5 2.9 4.5 6.5 4.5s6.5-2 6.5-4.5c0-.2 0-.4-.1-.6.7-.3 1.1-.9 1.1-1.7zM11.5 17c0-.7.6-1.3 1.3-1.3.7 0 1.3.6 1.3 1.3 0 .7-.6 1.3-1.3 1.3-.7 0-1.3-.6-1.3-1.3zm7.4 3.2c-.9.9-2.6 1-2.9 1s-2-.1-2.9-1c-.1-.1-.1-.3 0-.4.1-.1.3-.1.4 0 .6.6 1.8.8 2.5.8s1.9-.2 2.5-.8c.1-.1.3-.1.4 0 .1.1.1.3 0 .4zm.3-1.9c-.7 0-1.3-.6-1.3-1.3 0-.7.6-1.3 1.3-1.3.7 0 1.3.6 1.3 1.3 0 .7-.6 1.3-1.3 1.3z"
      fill="#fff"
    />
  </svg>
);

export const StoryTop = ({ title, subreddit, partNumber, titleEndMs }: Props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;

  const fadeIn = spring({ frame, fps, config: { damping: 20 } });

  const fadeOutStart = titleEndMs ? (titleEndMs / 1000) * fps : 30 * fps;
  const opacity = interpolate(
    frame,
    [0, 10, fadeOutStart, fadeOutStart + fps],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const translateY = interpolate(
    frame,
    [fadeOutStart, fadeOutStart + fps],
    [0, -30],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const showPart = partNumber && partNumber > 1;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "40px 30px",
        background: "rgba(0,0,0,0.3)",
        opacity: fadeIn * opacity,
        transform: `translateY(${translateY}px)`,
      }}
    >
      <div
        style={{
          width: "85%",
          maxWidth: 920,
          background: "#fff",
          borderRadius: 16,
          padding: "32px 28px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          position: "relative",
        }}
      >
        {/* Reddit logo + subreddit */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <RedditLogo />
          {subreddit && (
            <span
              style={{
                fontSize: 16,
                fontWeight: 600,
                color: "#FF4500",
                fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
              }}
            >
              r/{subreddit}
            </span>
          )}
        </div>

        {/* Title */}
        <h1
          style={{
            fontSize: 32,
            fontWeight: 700,
            color: "#1a1a1b",
            textAlign: "left",
            margin: 0,
            lineHeight: 1.3,
            fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
          }}
        >
          {title}
        </h1>

        {/* Part badge */}
        {showPart && (
          <div
            style={{
              position: "absolute",
              top: 16,
              right: 16,
              padding: "4px 12px",
              borderRadius: 12,
              background: "#FF4500",
              color: "#fff",
              fontSize: 14,
              fontWeight: 700,
              fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
            }}
          >
            Part {partNumber}
          </div>
        )}
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd remotion && node_modules/.bin/tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add remotion/src/components/StoryTop.tsx
git commit -m "feat: white Reddit card with logo, dynamic subreddit, part badge, fade-out"
```

---

### Task 4: StoryVideo — Pass New Props

**Files:**
- Modify: `remotion/src/StoryVideo.tsx`

**Interfaces:**
- Consumes: `InputProps` with new fields from Task 1
- Produces: Updated composition passing `subreddit`, `partNumber`, `titleEndMs` to StoryTop

- [ ] **Step 1: Update StoryVideo.tsx**

```tsx
import { AbsoluteFill, Audio, OffthreadVideo } from "remotion";
import { StoryTop } from "./components/StoryTop";
import { KaraokeSubtitles } from "./components/KaraokeSubtitles";
import type { InputProps } from "./types";

export const StoryVideo = (props: InputProps) => {
  const { narrationPath, words, storyTitle, brollClip, subreddit, partNumber, titleEndMs } = props;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <div style={{ position: "absolute", top: "50%", left: 0, width: "100%", height: "50%" }}>
        {brollClip ? (
          <OffthreadVideo
            src={brollClip}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            muted
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              background: "linear-gradient(135deg, #1a1a2e, #16213e)",
            }}
          />
        )}
      </div>

      <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "50%" }}>
        <StoryTop
          title={storyTitle}
          subreddit={subreddit}
          partNumber={partNumber}
          titleEndMs={titleEndMs}
        />
      </div>

      <KaraokeSubtitles words={words} />
      <Audio src={narrationPath} />
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd remotion && node_modules/.bin/tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add remotion/src/StoryVideo.tsx
git commit -m "feat: pass subreddit, partNumber, titleEndMs to StoryTop"
```

---

### Task 5: Backend — LLM Prompt Change & Subreddit Extraction

**Files:**
- Modify: `backend/main.py` (the `clean_script` function and add `extract_subreddit`)

**Interfaces:**
- Produces: `clean_script` returns `dict` with `title`, `subreddit`, `parts` instead of `str`
- Produces: `extract_subreddit(text, url)` returns `str`

- [ ] **Step 1: Replace `clean_script` function**

Find the existing `clean_script` function and replace it with:

```python
import re

def extract_subreddit(text: str, url: str = "") -> str:
    """Extract subreddit from pasted text or URL."""
    if url:
        m = re.search(r"/r/([A-Za-z0-9_]+)", url)
        if m:
            return m.group(1)
    for line in text.strip().split("\n")[:5]:
        m = re.search(r"r/([A-Za-z0-9_]+)", line)
        if m:
            return m.group(1)
    return ""


async def clean_script(raw_title: str, raw_body: str, raw_text: str = "", url: str = "") -> dict:
    """Use LLM to clean and split the script into parts. Returns dict with title, subreddit, parts."""
    from openai import OpenAI

    subreddit = extract_subreddit(raw_text, url)

    client = OpenAI(
        api_key=os.environ["OPENCODE_API_KEY"],
        base_url="https://opencode.ai/zen/v1",
    )
    prompt = (
        'You are a script editor for viral short-form videos. '
        'Clean the following Reddit post into narration scripts for vertical videos. '
        'Return JSON in this exact format: '
        '{"title": "the post title", "subreddit": "' + subreddit + '", "parts": [{"partNumber": 1, "content": "narration text for this part"}]} '
        'Rules:\n'
        '- Title: the post title, to be read as the opening hook for every part\n'
        '- Parts: split the story into natural segments at story beats\n'
        '- Each part\'s content MUST start with the title text so the narrator reads it as a hook first\n'
        '- For part > 1, prepend "Part N. " to the content so the narrator announces it\n'
        '- No duration limit — let the story length determine the number of parts\n'
        '- Each part should be a self-contained narrative segment (30-90 seconds preferred, but not enforced)\n'
        '- Remove all non-narrative elements: "Edit:", links, timestamps, meta-commentary, TL;DRs\n'
        '- Keep the story compelling\n\n'
        f'TITLE: {raw_title}\n\nBODY: {raw_body}'
    )
    response = client.chat.completions.create(
        model="mimo-v2.5-free",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    raw_response = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw_response.startswith("```"):
        raw_response = raw_response.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw_response)
```

- [ ] **Step 2: Verify backend imports**

Run: `cd backend && .venv/bin/python -c "from main import app; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: LLM returns JSON with title, subreddit, parts array"
```

---

### Task 6: Backend — Per-Part Pipeline & titleEndMs Calculation

**Files:**
- Modify: `backend/main.py` (the `_run_pipeline` function and `render_video` signature)

**Interfaces:**
- Consumes: `clean_script` dict from Task 5
- Produces: Per-part MP4 files, updated `JOBS` dict with stage/part tracking

- [ ] **Step 1: Add `find_title_end_ms` helper function**

Add after the `get_audio_duration` function:

```python
def find_title_end_ms(words: list, title: str) -> int:
    """Find the end timestamp of the title narration by matching title words."""
    title_words = title.lower().split()
    if not title_words or not words:
        return 3000  # default 3s

    matched = 0
    for w in words:
        if matched >= len(title_words):
            break
        if title_words[matched] in w["word"].lower():
            matched += 1
    if matched > 0:
        return int(words[min(matched - 1, len(words) - 1)]["end"])
    return 3000
```

- [ ] **Step 2: Update `render_video` signature to accept new props**

Replace the `render_video` function with:

```python
def render_video(
    narration_path: str,
    words: list,
    story_title: str,
    story_body: str,
    broll_clip: str,
    output_path: str,
    duration_seconds: float,
    subreddit: str = "",
    part_number: int = 1,
    title_end_ms: int = 3000,
) -> None:
    build_remotion()
    remotion_dir = ROOT / "remotion"

    httpd, port = start_file_server(str(ROOT))

    try:
        broll_url = f"http://localhost:{port}/{quote(str(Path(broll_clip).relative_to(ROOT)))}"
        narration_url = f"http://localhost:{port}/{quote(str(Path(narration_path).relative_to(ROOT)))}"

        props_data = {
            "narrationPath": narration_url,
            "words": words,
            "storyTitle": story_title,
            "storyBody": story_body,
            "brollClip": broll_url,
            "durationFrames": int(duration_seconds * 30) + 30,
            "subreddit": subreddit,
            "partNumber": part_number,
            "titleEndMs": title_end_ms,
        }

        subprocess.run(
            ["npx", "remotion", "render", "StoryVideo", output_path,
             f"--props={json.dumps(props_data)}", "--timeout=120000"],
            cwd=remotion_dir, check=True,
            env={**os.environ, "NODE_ENV": "production"},
        )
    finally:
        httpd.shutdown()
```

- [ ] **Step 3: Replace `_run_pipeline` with per-part logic**

```python
async def _run_pipeline(job_id: str, req: GenerateRequest):
    job_dir = OUTPUT / job_id
    job_dir.mkdir(exist_ok=True)
    try:
        JOBS[job_id]["progress"] = 5
        JOBS[job_id]["stage"] = "script"
        if req.text:
            lines = req.text.strip().split("\n", 1)
            raw = {"title": lines[0].strip(), "body": lines[1].strip() if len(lines) > 1 else ""}
        else:
            JOBS[job_id]["stage"] = "scraping"
            raw = await scrape_reddit(req.url)

        JOBS[job_id]["progress"] = 15
        JOBS[job_id]["stage"] = "script"
        script_data = await clean_script(raw["title"], raw["body"], req.text, req.url)

        title = script_data.get("title", raw["title"])
        subreddit = script_data.get("subreddit", "")
        parts = script_data.get("parts", [])

        if not parts:
            parts = [{"partNumber": 1, "content": raw["body"]}]

        total_parts = len(parts)
        part_outputs = []

        for i, part in enumerate(parts):
            part_num = part.get("partNumber", i + 1)
            content = part.get("content", "")

            JOBS[job_id]["stage"] = "tts"
            JOBS[job_id]["currentPart"] = i + 1
            JOBS[job_id]["totalParts"] = total_parts
            JOBS[job_id]["progress"] = 20 + int(60 * i / total_parts)

            narration_path = str(job_dir / f"part_{part_num}.mp3")
            await generate_tts(content, narration_path)

            JOBS[job_id]["stage"] = "transcribing"
            transcript_path = str(job_dir / f"part_{part_num}.json")
            await transcribe_audio(narration_path, transcript_path)

            with open(transcript_path) as f:
                transcript_data = json.load(f)
            words = transcript_data.get("words", [])
            title_end_ms = find_title_end_ms(words, title)

            broll_clip = pick_broll(req.background)
            output_video = str(job_dir / f"part_{part_num}.mp4")
            JOBS[job_id]["stage"] = "rendering"
            JOBS[job_id]["progress"] = 25 + int(60 * (i + 1) / total_parts)

            duration = get_audio_duration(narration_path)
            render_video(
                narration_path=narration_path,
                words=words,
                story_title=title,
                story_body=content,
                broll_clip=broll_clip,
                output_path=output_video,
                duration_seconds=duration,
                subreddit=subreddit,
                part_number=part_num,
                title_end_ms=title_end_ms,
            )
            part_outputs.append(output_video)

        # FFmpeg combine into landscape
        JOBS[job_id]["stage"] = "combining"
        JOBS[job_id]["progress"] = 90
        combined_path = str(job_dir / "combined_landscape.mp4")
        combine_landscape(part_outputs, combined_path)

        JOBS[job_id] = {
            "status": "done",
            "stage": "done",
            "progress": 100,
            "parts": [f"/api/video/{job_id}/part/{i+1}" for i in range(total_parts)],
            "combinedOutput": f"/api/video/{job_id}/combined",
            "partPaths": part_outputs,
            "combinedPath": combined_path,
        }
    except Exception as e:
        JOBS[job_id] = {"status": "error", "stage": "error", "progress": 0, "error": str(e)}
```

- [ ] **Step 4: Verify backend imports**

Run: `cd backend && .venv/bin/python -c "from main import app; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: per-part pipeline with titleEndMs, subreddit, part tracking"
```

---

### Task 7: Backend — FFmpeg Landscape Combine

**Files:**
- Modify: `backend/main.py` (add `combine_landscape` function)

**Interfaces:**
- Consumes: list of portrait MP4 paths
- Produces: `combined_landscape.mp4` at the given output path

- [ ] **Step 1: Add `combine_landscape` function**

Add before the routes section:

```python
def combine_landscape(part_paths: list, output_path: str) -> None:
    """Concatenate portrait videos and create a landscape video with blurred backdrop."""
    if not part_paths:
        return
    if len(part_paths) == 1:
        # Single part — still create landscape version
        part_paths_for_concat = part_paths
    else:
        # Create concat file
        concat_path = str(Path(output_path).parent / "concat.txt")
        with open(concat_path, "w") as f:
            for p in part_paths:
                f.write(f"file '{p}'\n")
        concat_video = str(Path(output_path).parent / "concat_portrait.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
             "-c", "copy", concat_video],
            check=True,
        )
        part_paths_for_concat = [concat_video]

    # Create landscape with blurred backdrop
    input_video = part_paths_for_concat[0]
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_video,
         "-filter_complex",
         "split[v1][v2];[v1]scale=1920:1080,boxblur=40[bg];[v2]scale=1080:1920[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2",
         "-c:a", "copy", output_path],
        check=True,
    )
```

- [ ] **Step 2: Verify backend imports**

Run: `cd backend && .venv/bin/python -c "from main import app; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: FFmpeg landscape combine with blurred backdrop"
```

---

### Task 8: Backend — New Video Serving Endpoints

**Files:**
- Modify: `backend/main.py` (add part and combined video endpoints)

**Interfaces:**
- Produces: `GET /api/video/{job_id}/part/{n}` and `GET /api/video/{job_id}/combined`

- [ ] **Step 1: Add new endpoints**

Add after the existing `get_video` endpoint:

```python
@app.get("/api/video/{job_id}/part/{part_num}")
async def get_part_video(job_id: str, part_num: int):
    if job_id not in JOBS or JOBS[job_id].get("status") != "done":
        raise HTTPException(404, "Video not ready")
    part_path = str(OUTPUT / job_id / f"part_{part_num}.mp4")
    if not Path(part_path).exists():
        raise HTTPException(404, f"Part {part_num} not found")
    return FileResponse(part_path, media_type="video/mp4")


@app.get("/api/video/{job_id}/combined")
async def get_combined_video(job_id: str):
    if job_id not in JOBS or JOBS[job_id].get("status") != "done":
        raise HTTPException(404, "Video not ready")
    combined_path = JOBS[job_id].get("combinedPath")
    if not combined_path or not Path(combined_path).exists():
        raise HTTPException(404, "Combined video not found")
    return FileResponse(combined_path, media_type="video/mp4")
```

- [ ] **Step 2: Verify backend imports**

Run: `cd backend && .venv/bin/python -c "from main import app; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: endpoints for per-part and combined landscape videos"
```

---

### Task 9: Frontend — Stage Labels, Multi-Part Progress, Combined Video

**Files:**
- Modify: `frontend/src/app/page.tsx`

**Interfaces:**
- Consumes: Updated job status with `stage`, `currentPart`, `totalParts`, `parts`, `combinedOutput`
- Produces: Progress bar with stage labels, multi-part display, combined landscape video

- [ ] **Step 1: Rewrite page.tsx**

```tsx
"use client";

import { useState, useEffect } from "react";

interface Assets {
  [pool: string]: string[];
}

interface JobStatus {
  status: string;
  stage?: string;
  currentPart?: number;
  totalParts?: number;
  progress: number;
  error?: string;
  output?: string;
  parts?: string[];
  combinedOutput?: string;
}

const STAGE_LABELS: Record<string, string> = {
  scraping: "Scraping Reddit",
  script: "Cleaning Script",
  tts: "Generating Voice",
  transcribing: "Transcribing Audio",
  rendering: "Rendering Video",
  combining: "Combining Landscape",
  done: "Done",
  error: "Error",
};

export default function Home() {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"url" | "text">("url");
  const [background, setBackground] = useState("minecraft");
  const [assets, setAssets] = useState<Assets>({});
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);

  useEffect(() => {
    fetch("/api/proxy/assets")
      .then((r) => r.json())
      .then(setAssets)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!jobId || status?.status === "done" || status?.status === "error") return;
    const interval = setInterval(() => {
      fetch(`/api/proxy/status/${jobId}`)
        .then((r) => r.json())
        .then(setStatus);
    }, 1000);
    return () => clearInterval(interval);
  }, [jobId, status?.status]);

  const handleGenerate = async () => {
    const hasContent = mode === "url" ? url : text;
    if (!hasContent) return;
    setStatus(null);
    try {
      const body = mode === "url"
        ? JSON.stringify({ url, background })
        : JSON.stringify({ text, background });
      const res = await fetch("/api/proxy/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      const data = await res.json();
      setJobId(data.job_id);
    } catch {
      setStatus({ status: "error", progress: 0, error: "Failed to connect to backend." });
    }
  };

  const stageLabel = status?.stage ? STAGE_LABELS[status.stage] || status.stage : "Processing";
  const partLabel = status?.totalParts && status?.totalParts > 1
    ? `Part ${status.currentPart} of ${status.totalParts}`
    : "";

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8">
      <div className="w-full max-w-lg space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Story Factory</h1>
          <p className="text-sm text-zinc-400">Zero-cost Reddit story video generator</p>
        </div>

        <div className="space-y-4 bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
          <div className="flex gap-1 bg-zinc-800 rounded-lg p-1">
            <button
              onClick={() => setMode("url")}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                mode === "url" ? "bg-zinc-700 text-white" : "text-zinc-400"
              }`}
            >
              Reddit URL
            </button>
            <button
              onClick={() => setMode("text")}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                mode === "text" ? "bg-zinc-700 text-white" : "text-zinc-400"
              }`}
            >
              Paste Text
            </button>
          </div>

          {mode === "url" ? (
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-300">Reddit URL</label>
              <input
                type="url"
                placeholder="https://www.reddit.com/r/AskReddit/comments/..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-4 py-2.5 text-sm
                           placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-orange-500/50"
              />
            </div>
          ) : (
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-zinc-300">Story Text</label>
              <textarea
                placeholder="Paste the full Reddit post here. First line = title, rest = body."
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={8}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-4 py-2.5 text-sm
                           placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-orange-500/50 resize-y"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-zinc-300">Background Pool</label>
            <select
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-4 py-2.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-orange-500/50"
            >
              {Object.keys(assets).map((pool) => (
                <option key={pool} value={pool}>
                  {pool} ({assets[pool].length} clips)
                </option>
              ))}
              {Object.keys(assets).length === 0 && (
                <option value="minecraft">minecraft (add .mp4 files to assets/minecraft/)</option>
              )}
            </select>
          </div>

          <button
            onClick={handleGenerate}
            disabled={status?.status === "processing"}
            className="w-full rounded-lg bg-orange-600 py-2.5 text-sm font-semibold text-white
                       hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed
                       transition-colors"
          >
            {status?.status === "processing" ? "Processing..." : "Generate Video"}
          </button>
        </div>

        {status?.status === "processing" && (
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-zinc-300 font-medium">
                {stageLabel}{partLabel && ` — ${partLabel}`}
              </span>
              <span className="text-zinc-500">{status.progress}%</span>
            </div>
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-orange-500 rounded-full transition-all duration-500"
                style={{ width: `${status.progress}%` }}
              />
            </div>
            {status.totalParts && status.totalParts > 1 && (
              <div className="flex gap-1">
                {Array.from({ length: status.totalParts }, (_, i) => (
                  <div
                    key={i}
                    className={`flex-1 h-1 rounded-full ${
                      i < (status.currentPart || 0) ? "bg-orange-500" : "bg-zinc-800"
                    }`}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {status?.status === "done" && (
          <div className="space-y-4">
            {status.parts && status.parts.length > 1 && (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 space-y-4">
                <p className="text-sm font-medium text-zinc-300">
                  Parts ({status.parts.length})
                </p>
                {status.parts.map((partUrl, i) => (
                  <div key={i} className="space-y-1">
                    <p className="text-xs text-zinc-500">Part {i + 1}</p>
                    <video
                      controls
                      className="w-full rounded-lg"
                      src={partUrl.replace("/api/", "/api/proxy/")}
                    />
                  </div>
                ))}
              </div>
            )}
            {status.combinedOutput && (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 space-y-4">
                <p className="text-green-400 text-sm font-medium">Combined Landscape Video</p>
                <video
                  controls
                  className="w-full rounded-lg"
                  src={status.combinedOutput.replace("/api/", "/api/proxy/")}
                />
              </div>
            )}
            {status.parts && status.parts.length === 1 && status.parts[0] && (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 text-center space-y-4">
                <p className="text-green-400 text-sm font-medium">Video ready!</p>
                <video
                  controls
                  className="w-full rounded-lg"
                  src={status.parts[0].replace("/api/", "/api/proxy/")}
                />
              </div>
            )}
          </div>
        )}

        {status?.status === "error" && (
          <div className="bg-red-950/50 border border-red-800 rounded-xl p-4 text-sm text-red-300">
            {status.error}
          </div>
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Verify Next.js builds**

Run: `cd frontend && npx next build`
Expected: Errors: 0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: stage labels, multi-part progress, combined video display"
```

---

### Task 10: End-to-End Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Verify all TypeScript compiles**

Run: `cd remotion && node_modules/.bin/tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Verify backend imports**

Run: `cd backend && .venv/bin/python -c "from main import app; print('OK')"`
Expected: OK

- [ ] **Step 3: Verify Next.js builds**

Run: `cd frontend && npx next build`
Expected: Errors: 0

- [ ] **Step 4: Manual test**

Start servers: `npm run dev`
Paste a Reddit story, select background, click Generate.
Verify:
- Progress bar shows stage labels
- If multi-part: part indicators show
- Video renders with new template (white card, borders on subtitles, windowed display)
- Combined landscape video appears in results

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes"
```
