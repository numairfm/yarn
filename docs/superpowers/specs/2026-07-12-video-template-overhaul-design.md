# Design: Video Template Overhaul & Multi-Part Splitting

## Date: 2026-07-12

## Overview

Five changes to the Story Factory video pipeline:
1. Karaoke subtitles: bigger text, borders, windowed display (5-7 words)
2. StoryTop: white Reddit card with logo, dynamic subreddit, title-only, fade-out after title narration
3. Backend: LLM-driven script splitting into parts, subreddit extraction, per-part render
4. FFmpeg: combine portrait parts into landscape video with blurred backdrop
5. Frontend: progress bar with stage labels, remaining tasks, multi-part video results

## 1. Karaoke Subtitles (`KaraokeSubtitles.tsx`)

### Windowed Display
- Show only 5-7 words centered on the active word
- Slice `words` array to `activeIdx - 3` through `activeIdx + 3`
- Words entering/leaving the window get a subtle slide-in/fade-out

### Visual Changes
- `fontSize`: 42px -> 56px
- Text border: `WebkitTextStroke: "2px black"` on all words
- Active word: thicker gold stroke (`3px #FFD700`), keep spring bounce
- Position: `bottom: 120px` (moved down to accommodate bigger text)
- `WebkitTextFillColor` to ensure border renders properly with fill color

### No Backend Changes
Subtitle windowing is purely client-side (Remotion). The `words` prop already contains full word timestamps. The component slices internally.

## 2. StoryTop (`StoryTop.tsx`)

### Reddit Card Layout
- White card (`#fff` background), centered in the top half
- Card width: ~85% of top half, rounded corners (`borderRadius: 16px`), subtle shadow
- Left-aligned text inside card
- Reddit snoo SVG logo at top of card (small, ~32px)

### Dynamic Subreddit
- Backend extracts subreddit name and passes as `subreddit` prop
- If `subreddit` is empty/null, omit the subreddit badge entirely
- Badge format: "r/AskReddit" in Reddit orange (#FF4500)

### Title-Only Display
- Card shows only the post title (the hook)
- No body text on the card

### Fade-Out
- New prop: `titleEndMs` (milliseconds into the video when title narration ends)
- Card fades out over ~1 second using `interpolate` after `titleEndMs`
- After fade, the top half becomes transparent/dark, letting the B-roll show through

### Part Badge
- New prop: `partNumber` (integer, default 1)
- If `partNumber > 1`, show "Part N" badge on card (top-right corner)
- Narrator announces "Part N" after reading the title (handled by LLM prompt)

## 3. Backend Pipeline (`main.py`)

### LLM Prompt Change

Current prompt asks for a single 60-90s script. New prompt asks for JSON:

```
You are a script editor for viral short-form videos.
Clean the following Reddit post into narration scripts for vertical videos.

Return JSON in this exact format:
{"title": "the post title", "subreddit": "extracted subreddit or empty string", "parts": [{"partNumber": 1, "content": "narration text for this part"}]}

Rules:
- Title: the post title, to be read as the opening hook for every part
- Parts: split the story into natural segments at story beats
- Each part's content MUST start with the title text so the narrator reads it as a hook first
- For part > 1, prepend "Part N. " to the content so the narrator announces it
- No duration limit — let the story length determine the number of parts
- Each part should be a self-contained narrative segment (30-90 seconds preferred, but not enforced)
- Remove all non-narrative elements: 'Edit:', links, timestamps, meta-commentary, TL;DRs
- Keep the story compelling

TITLE: {raw_title}
BODY: {raw_body}
```

### Subreddit Extraction
- From pasted text: regex `r/([A-Za-z0-9_]+)` in first 3 lines
- From URL path: extract `/r/{subreddit}/` segment
- Pass to Remotion as `subreddit` prop

### Per-Part Pipeline
For each part returned by LLM:
1. TTS: `edge-tts` generates narration MP3 for part content
2. Transcribe: Groq Whisper returns word-level timestamps
3. Find `titleEndMs`: scan words array for the end of the title text
   - Match title words against the first N words of the transcript
   - `titleEndMs` = end timestamp of the last matched title word
4. Render: Remotion renders the portrait MP4 with props:
   - `narrationPath`: HTTP URL to narration MP3
   - `words`: word timestamps array
   - `storyTitle`: post title
   - `subreddit`: extracted subreddit
   - `partNumber`: part number
   - `titleEndMs`: calculated end time
   - `brollClip`: random B-roll HTTP URL
   - `durationFrames`: calculated from audio duration

### FFmpeg Landscape Combine
After all parts render:
1. Concatenate all portrait MP4s into one file
2. Apply FFmpeg filter to create landscape (1920x1080) with blurred backdrop:
   ```
   ffmpeg -i combined_portrait.mp4 -filter_complex \
   "split[v1][v2];[v1]scale=1920:1080,boxblur=40[bg];[v2]scale=1080:1920[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2" \
   -c:a copy combined_landscape.mp4
   ```
3. Output: `combined_landscape.mp4` alongside the portrait parts

### Job Status Shape
```json
{
  "status": "processing",
  "stage": "scraping|script|tts|transcribing|rendering|combining|done|error",
  "currentPart": 2,
  "totalParts": 4,
  "progress": 65,
  "output": null,
  "parts": [],
  "combinedOutput": null
}
```

When done:
```json
{
  "status": "done",
  "stage": "done",
  "progress": 100,
  "parts": ["/api/video/{job_id}/part/1", "/api/video/{job_id}/part/2"],
  "combinedOutput": "/api/video/{job_id}/combined"
}
```

## 4. Frontend UI (`page.tsx`)

### Progress Bar
- Visual progress bar (already exists, keep it)
- Stage label above bar: "Scraping" -> "Script Cleaning" -> "TTS" -> "Transcribing" -> "Rendering Part 2/4" -> "Combining Landscape"
- If multi-part: show "Part X of Y" next to stage label
- Remaining tasks derived from stage (e.g., if rendering part 2/4, remaining = parts 3, 4, combining)

### Results Display
When job is done:
- List all portrait part videos with thumbnails
- Show combined landscape video
- Download links for each

## 5. Remotion Props (`types.ts`)

```typescript
export interface InputProps {
  narrationPath: string;
  words: WordTimestamp[];
  storyTitle: string;
  storyBody: string;      // kept for backwards compat, unused in new card design
  brollClip: string;
  durationFrames?: number;
  subreddit?: string;     // new: dynamic subreddit name
  partNumber?: number;    // new: part number for multi-part videos
  titleEndMs?: number;    // new: when title narration ends (for card fade-out)
}
```

## 6. New Backend Endpoint

```
GET /api/video/{job_id}/part/{part_number}  -> serves individual part MP4
GET /api/video/{job_id}/combined            -> serves combined landscape MP4
```

## File Changes Summary

| File | Changes |
|------|---------|
| `remotion/src/components/KaraokeSubtitles.tsx` | Windowed display, bigger text, borders |
| `remotion/src/components/StoryTop.tsx` | White card, Reddit logo, dynamic subreddit, title-only, fade-out, part badge |
| `remotion/src/StoryVideo.tsx` | Pass new props (subreddit, partNumber, titleEndMs) to StoryTop |
| `remotion/src/types.ts` | Add subreddit, partNumber, titleEndMs to InputProps |
| `backend/main.py` | LLM prompt change, subreddit extraction, per-part pipeline, FFmpeg combine, new endpoints, updated job status |
| `frontend/src/app/page.tsx` | Stage labels, multi-part progress, combined video display |
