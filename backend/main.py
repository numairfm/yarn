import asyncio
import json
import os
import random
import re
import socket
import subprocess
import threading
import uuid
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

FRAME_RE = re.compile(r"Rendered (\d+)/(\d+), time remaining: (.+)")

app = FastAPI(title="Yarn")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)

JOBS: dict[str, dict] = {}
ACTIVE_TASKS: dict[str, asyncio.Task] = {}
ACTIVE_SUBPROCESSES: dict[str, list[subprocess.Popen]] = {}


class GenerateRequest(BaseModel):
    url: str = ""
    text: str = ""
    background: str = "minecraft"
    video_file: str = ""
    voice: str = "en-US-AndrewNeural"


class GenerateResponse(BaseModel):
    job_id: str


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def start_file_server(directory: str) -> tuple[ThreadingHTTPServer, int]:
    port = find_free_port()
    handler = partial(SimpleHTTPRequestHandler, directory=directory)
    httpd = ThreadingHTTPServer(("localhost", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, port


def get_audio_duration(filepath: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", filepath],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


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


def build_remotion() -> None:
    remotion_dir = ROOT / "remotion"
    if not (remotion_dir / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=remotion_dir, check=True)


def render_video(
    job_id: str,
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
    video_start_frame: int = 0,
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
            "videoStartFrame": video_start_frame,
        }

        p = subprocess.Popen(
            ["npx", "remotion", "render", "StoryVideo", output_path,
             f"--props={json.dumps(props_data)}",
             "--timeout=120000",
             "--image-format=jpeg",
             "--concurrency=4",
             "--crf=28"],
            cwd=remotion_dir,
            env={**os.environ, "NODE_ENV": "production"},
            stderr=subprocess.PIPE,
        )
        if job_id not in ACTIVE_SUBPROCESSES:
            ACTIVE_SUBPROCESSES[job_id] = []
        ACTIVE_SUBPROCESSES[job_id].append(p)

        def read_progress():
            for line in p.stderr:
                text = line.decode("utf-8", errors="replace").strip()
                m = FRAME_RE.search(text)
                if m:
                    rendered, total, remaining = m.group(1), m.group(2), m.group(3)
                    if job_id in JOBS:
                        JOBS[job_id]["renderedFrames"] = int(rendered)
                        JOBS[job_id]["totalFrames"] = int(total)
                        JOBS[job_id]["timeRemaining"] = remaining

        progress_thread = threading.Thread(target=read_progress, daemon=True)
        progress_thread.start()

        try:
            p.wait()
            if p.returncode != 0:
                raise subprocess.CalledProcessError(p.returncode, p.args)
        finally:
            if job_id in ACTIVE_SUBPROCESSES and p in ACTIVE_SUBPROCESSES[job_id]:
                ACTIVE_SUBPROCESSES[job_id].remove(p)
    finally:
        httpd.shutdown()


# ==================== Pipeline Steps ====================

async def scrape_reddit(url: str) -> dict:
    from firecrawl import FirecrawlApp

    fc = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])
    result = await asyncio.to_thread(
        fc.scrape_url, url,
        params={"formats": ["json"], "jsonOptions": {
            "prompt": "Extract the title and the full body text of this Reddit post.",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["title", "body"],
            },
        }},
    )
    return {"title": result.get("title") or "Untitled", "body": result.get("body") or ""}


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


def clean_script_sync(raw_title: str, raw_body: str, raw_text: str = "", url: str = "") -> dict:
    """Use LLM to clean and split the script into parts. Returns dict with title, subreddit, parts."""
    from openai import OpenAI

    subreddit = extract_subreddit(raw_text, url)

    client = OpenAI(
        api_key=os.environ["OPENCODE_API_KEY"],
        base_url="https://opencode.ai/zen/v1",
    )
    prompt = (
        'You are a narrator for short-form video. Casual, dry, 2am-friend telling a story. '
        'Short sentences. Contractions. Fragments. No elevated language, no poetic filler.\n\n'

        'STEP 1 — CLASSIFY the input into exactly one mode:\n'
        'A) REDDIT — title is non-empty AND body has ≥2 sentences describing events.\n'
        'B) ONE-OFF — body is empty OR ≤1 sentence AND the title reads as a message, question, or '
        'request addressed to you ("i did X", "what do i do", "hi narrator...").\n'
        'C) EDGE — body is empty OR ≤1 sentence AND the title is nonsense, a riddle, a lyric '
        'fragment, gibberish, OR a Reddit-style judgment question with no body to back it up '
        '(AITA/WIBTA/NTA/ESH as the whole title), OR both title and body are blank.\n\n'

        'STEP 2 — Apply the rules for the chosen mode ONLY. Do not apply any other mode\'s rules. '
        'If two modes\' rules would conflict, the chosen mode wins.\n\n'

        'MODE A — REDDIT\n'
        '- Open with the title exactly as written. Never paraphrase, summarize, or add commentary to it.\n'
        '- Narrate in first person (I, my, me, we). Preserve the poster\'s perspective — never switch '
        'to third person (she, he, her, him). The narrator IS the person who wrote the post.\n'
        '- Tell the story straight through in order. Do not summarize or skip to the point.\n'
        '- Target 225-270 words per part (~90s). If under 150 words, expand with concrete detail — '
        'scene, physical action, a second beat. Never pad with filler phrases.\n\n'

        'MODE B — ONE-OFF\n'
        '- Restate the input\'s situation as a story, not a reply. Don\'t address the sender, don\'t '
        'quote them, don\'t acknowledge that a request was made.\n'
        '- Narrate in the same perspective as the input. If the input uses first person (I, my, me), '
        'keep it first person. Never switch perspectives.\n'
        '- NEVER: acknowledge receiving a message, discuss what you\'re being asked to do, ask the '
        'user anything, or comment on the request itself.\n'
        '- Target 225-270 words (~90s). If short, expand with concrete detail, not commentary.\n\n'

        'MODE C — EDGE\n'
        'Shape: one flat deadpan acknowledgment of what the input actually is → force it into a tiny '
        'story anyway → stop. No moral, no explanation of the joke.\n'
        '- If it\'s a riddle or wordplay: don\'t solve it. Pick one image or phrase from it and build '
        'a 3-line scene around that image.\n'
        '- If it\'s a judgment-style title (AITA/WIBTA/etc.) with no body: don\'t invent the missing '
        'backstory. Riff on the dilemma implied by the question itself, pick one plausible detail, '
        'land it as a tiny scene. Don\'t answer the question.\n'
        '~75-100 words (~30-50s).\n\n'

        'GLOBAL RULES — apply regardless of mode:\n'
        '- EXPAND acronyms as they appear: AITA→"Am I the a-hole", YTA→"You\'re the a-hole", '
        'NTA→"Not the a-hole", ESH→"Everyone sucks here", OP→"the original poster", DH→"my husband", '
        'DW→"my wife", DS→"my son", DD→"my daughter", LC→"low contact", NC→"no contact".\n'
        '- Soften profanity, keep emotional intensity. Strip URLs, [removed], [deleted], bot/mod text.\n'
        '- Weave "Edit:" content in as "Update:" or "So later...". Keep dollar amounts, quotes, detail.\n'
        '- Never summarize. Preserve original voice and specifics — rewrite for flow only.\n'
        '- STRIP subreddit prefixes from the title before narrating (e.g. "r/relationship_advice", '
        'r/AITA, r/tifu). The subreddit is rendered separately on the video card — never speak it.\n'
        '- SPLITTING: if the title or body explicitly requests a number of parts (e.g. "split this '
        'into 2 parts", "make 3 clips"), produce exactly that many parts regardless of length, '
        'applying minimum duration to each. Otherwise split only if the cleaned body exceeds 300 '
        'words, at story beats (setup → conflict → resolution).\n'
        '- MINIMUM DURATION: every part ≥150 words. Expand short material with real detail — scene, '
        'physical action, a second beat. Never pad with filler.\n'
        '- VARIANCE: each output must feel specific to this exact input. If your draft could be '
        'reused unchanged on a different input, rewrite it.\n'
        '- NEVER SAY: "I\'ve seen it all" · "In this one" · "As Reddit stories go" · "This one takes '
        'the cake" · "It hits different" · "It\'s a reminder that" · "This is why we" · "Some people '
        'just" · "At the end of the day" · "Wild" · "Unbelievable" · "Can you believe it" · "What text '
        'are we splitting" · "It\'s like a loop" · any greeting-card metaphor or life lesson.\n'
        '- END ON INPUT: the last sentence of every part is the last event of the input\'s story, or '
        'a beat drawn directly from the input. Nothing follows it. No summary, moral, sign-off, '
        'question, or wrap-up remark.\n'
        '- PART MARKER: Part 1 opens with the title alone, no marker. Part 2+ MUST start with the '
        'title verbatim, immediately followed by the literal spoken words "Part 2" / "Part 3" etc., '
        'then a beat, then the narration. Format: "{title} Part N. {narration}". The "Part N" is '
        'spoken out loud — the viewer needs to know which part they\'re watching. Never skip the '
        'marker, even if it feels redundant.\n'
        '- NO META, ever: never mention that you are narrating, writing, following instructions, '
        'processing a request, or testing something.\n\n'

        'BAD (do not do this — summarizing and proceduralizing instead of narrating):\n'
        '"Alright, picture this. Yesterday evening, I\'m exhausted. I collapsed in bed. My stomach '
        'felt weird. I woke up and there it was, a stain on the sheets. Here\'s what I did: I stripped '
        'the sheets, threw them in the wash, sprayed vinegar on the mattress..."\n\n'

        f'TITLE: {raw_title}\n\nBODY: {raw_body}\n\n'
        'Return JSON: {"title": "post title", "subreddit": "' + subreddit + '", "parts": '
        '[{"partNumber": 1, "content": "narration text"}]}\n'
        'Valid JSON only. No commentary.'
    )
    response = client.chat.completions.create(
        model="mimo-v2.5-free",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
    )
    raw_response = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw_response.startswith("```"):
        raw_response = raw_response.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw_response)


async def generate_tts(text: str, output_path: str, voice: str = "en-US-AndrewNeural") -> None:
    import edge_tts

    rate = "+15%" if voice == "en-US-AvaNeural" else "+0%"
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(output_path)


def transcribe_audio_sync(audio_path: str, output_path: str) -> None:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words = [
        {"word": w["word"], "start": w["start"] * 1000, "end": w["end"] * 1000}
        for w in (transcription.words or [])
    ]
    with open(output_path, "w") as f:
        json.dump({"words": words, "text": transcription.text}, f, indent=2)


def pick_broll(background: str, video_file: str = "") -> str:
    pool = ASSETS / background
    if not pool.exists():
        raise HTTPException(400, f"Asset pool '{background}' not found at {pool}")
    if video_file:
        file_path = pool / video_file
        if file_path.exists():
            return str(file_path)
    clips = list(pool.glob("*.mp4")) + list(pool.glob("*.mov")) + list(pool.glob("*.webm"))
    if not clips:
        raise HTTPException(400, f"No video files in {pool}. Add .mp4/.mov/.webm files.")
    return str(random.choice(clips))


def combine_landscape(job_id: str, part_paths: list, output_path: str) -> None:
    """Concatenate portrait videos and create a landscape video with blurred backdrop."""
    if not part_paths:
        return
    if len(part_paths) == 1:
        part_paths_for_concat = part_paths
    else:
        # Create concat file
        concat_path = str(Path(output_path).parent / "concat.txt")
        with open(concat_path, "w") as f:
            for p in part_paths:
                f.write(f"file '{p}'\n")
        concat_video = str(Path(output_path).parent / "concat_portrait.mp4")
        
        p1 = subprocess.Popen(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
             "-c", "copy", concat_video]
        )
        if job_id not in ACTIVE_SUBPROCESSES:
            ACTIVE_SUBPROCESSES[job_id] = []
        ACTIVE_SUBPROCESSES[job_id].append(p1)
        try:
            p1.wait()
            if p1.returncode != 0:
                raise subprocess.CalledProcessError(p1.returncode, p1.args)
        finally:
            if job_id in ACTIVE_SUBPROCESSES and p1 in ACTIVE_SUBPROCESSES[job_id]:
                ACTIVE_SUBPROCESSES[job_id].remove(p1)
                
        part_paths_for_concat = [concat_video]

    # Create landscape with blurred backdrop
    input_video = part_paths_for_concat[0]
    p2 = subprocess.Popen(
        ["ffmpeg", "-y", "-i", input_video,
         "-filter_complex",
         "split[v1][v2];[v1]scale=1920:1080,boxblur=40,setsar=1[bg];[v2]scale=1080:1920,setsar=1[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1",
         "-aspect", "16:9",
         "-c:a", "copy", output_path]
    )
    if job_id not in ACTIVE_SUBPROCESSES:
        ACTIVE_SUBPROCESSES[job_id] = []
    ACTIVE_SUBPROCESSES[job_id].append(p2)
    try:
        p2.wait()
        if p2.returncode != 0:
            raise subprocess.CalledProcessError(p2.returncode, p2.args)
    finally:
        if job_id in ACTIVE_SUBPROCESSES and p2 in ACTIVE_SUBPROCESSES[job_id]:
            ACTIVE_SUBPROCESSES[job_id].remove(p2)


# ==================== Routes ====================

@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "processing", "progress": 0, "output": None}
    task = asyncio.create_task(_run_pipeline(job_id, req))
    ACTIVE_TASKS[job_id] = task
    return GenerateResponse(job_id=job_id)


@app.post("/api/jobs", response_model=GenerateResponse)
async def create_job(req: GenerateRequest):
    return await generate(req)


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
        script_data = await asyncio.to_thread(clean_script_sync, raw["title"], raw["body"], req.text, req.url)

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
            await generate_tts(content, narration_path, req.voice)

            JOBS[job_id]["stage"] = "transcribing"
            transcript_path = str(job_dir / f"part_{part_num}.json")
            await asyncio.to_thread(transcribe_audio_sync, narration_path, transcript_path)

            with open(transcript_path) as f:
                transcript_data = json.load(f)
            words = transcript_data.get("words", [])
            title_end_ms = find_title_end_ms(words, title)

            broll_clip = pick_broll(req.background, req.video_file)
            output_video = str(job_dir / f"part_{part_num}.mp4")
            JOBS[job_id]["stage"] = "rendering"
            JOBS[job_id]["progress"] = 25 + int(60 * (i + 1) / total_parts)

            duration = get_audio_duration(narration_path)
            broll_duration = get_audio_duration(broll_clip)
            max_start = max(0, int((broll_duration - duration) * 30))
            video_start_frame = random.randint(0, max_start) if max_start > 0 else 0
            render_video(
                job_id=job_id,
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
                video_start_frame=video_start_frame,
            )
            part_outputs.append(output_video)

        # FFmpeg combine into landscape
        JOBS[job_id]["stage"] = "combining"
        JOBS[job_id]["progress"] = 90
        combined_path = str(job_dir / "combined_landscape.mp4")
        await asyncio.to_thread(combine_landscape, job_id, part_outputs, combined_path)

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
    finally:
        if job_id in ACTIVE_TASKS:
            del ACTIVE_TASKS[job_id]


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found")
    return JOBS[job_id]


@app.get("/api/jobs")
async def list_jobs():
    return JOBS


@app.post("/api/cancel/{job_id}")
async def cancel_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found")

    # Cancel task
    if job_id in ACTIVE_TASKS:
        ACTIVE_TASKS[job_id].cancel()
        del ACTIVE_TASKS[job_id]

    # Terminate active subprocesses
    if job_id in ACTIVE_SUBPROCESSES:
        for p in ACTIVE_SUBPROCESSES[job_id]:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        del ACTIVE_SUBPROCESSES[job_id]

    JOBS[job_id]["status"] = "cancelled"
    JOBS[job_id]["stage"] = "cancelled"
    return {"status": "ok"}


@app.get("/api/video/{job_id}")
async def get_video(job_id: str):
    if job_id not in JOBS or JOBS[job_id].get("output") is None:
        raise HTTPException(404, "Video not ready")
    return FileResponse(JOBS[job_id]["output"], media_type="video/mp4")


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


@app.get("/api/assets")
async def list_assets():
    pools = {}
    for d in ASSETS.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            clips = [f.name for f in d.glob("*") if f.suffix in (".mp4", ".mov", ".webm")]
            pools[d.name] = clips
    return pools
