# Yarn security and architecture review

Date: 2026-07-13  
Scope: FastAPI backend, Next.js dashboard, Remotion renderer, local job API, and repository configuration. This was a source review; it did not include authenticated deployment testing, a dependency CVE scan, or inspection of secret values.

## Executive summary

Yarn is a capable local video-generation prototype, but it currently treats a privileged render worker as if it were a trusted local UI. The API can create expensive jobs, inspect every job and log, cancel work, enumerate assets, and download videos without authentication. If the backend is exposed beyond a single trusted machine, this is the first issue to solve.

The next reliability issue is capacity control. The job semaphore limits active pipelines, but not queued tasks, request size, on-disk output, or the nested Remotion concurrency. Two active jobs can still start up to eight part renders, each requesting eight Remotion workers. The application also keeps all job state and logs in process memory, making a restart destructive and a busy dashboard progressively more expensive.

## Risk ranking

| Priority | Finding | Impact | Evidence |
| --- | --- | --- | --- |
| P0 | No authentication or authorization | Anyone with network access can consume compute, read data, cancel jobs, and fetch outputs | `backend/main.py:30-35`, `477-490`, `632-653`, `749-805` |
| P0 | No rate, queue, input, or storage limits | Easy CPU/GPU, API-credit, memory, and disk denial of service | `backend/main.py:50-75`, `459-499`, `530-608` |
| P1 | Temporary HTTP server exposes repository root | Local processes can request source, `.env`, and generated artifacts during every render | `backend/main.py:129-135`, `188-192`, `666-668` |
| P1 | Renderer and preview work have weak timeout/cancellation control | Hung child processes and blocking cancellation can exhaust workers | `backend/main.py:138-144`, `207-245`, `417-454`, `689-730`, `749-770` |
| P1 | In-memory state is shared across async tasks and threads | Races, lost progress, restart data loss, and non-repeatable operations | `backend/main.py:42-46`, `86-120`, `459-629` |
| P1 | User-supplied source URLs and prompts cross trust boundaries without policy | SSRF-like scraper exposure, excessive third-party cost, and prompt-injection/output-integrity risk | `backend/main.py:50-61`, `250-268`, `284-344` |
| P2 | Dashboard polls the complete job collection, including logs | Response size and browser work grow with every retained job | `frontend/src/app/page.tsx:71-82`, `353-438`; `backend/main.py:644-653` |
| P2 | One backend module owns API, workflow, external clients, processes, storage, and telemetry | Hard to test, change safely, or operate | `backend/main.py:1-815` |
| P2 | Runtime dependency installation and unpinned/uneven dependency policy | Slow startup and avoidable software-supply-chain variance | `backend/main.py:164-168`, `backend/requirements.txt`, `remotion/package.json` |

## Detailed findings

### P0-1: Every privileged API operation is unauthenticated

**Evidence.** CORS accepts every origin (`allow_origins=["*"]`) at `backend/main.py:30-35`. The routes for job creation, batch creation, status, complete job enumeration, logs, cancellation, asset listing, test renders, and video download have no identity check at `477-490`, `632-653`, `656-815`.

**Impact.** A caller can submit jobs that use third-party LLM, TTS, transcription, CPU/GPU, and disk; read other users' job titles, URLs, debug output, and finished videos; or terminate another caller's render. Wildcard CORS makes browser-driven abuse especially simple when the server is reachable from a browser. The 48-bit-looking job ID is an identifier, not authorization: `GET /api/jobs` exposes all IDs directly.

**Recommendation.** Decide the deployment mode explicitly.

1. For a strictly local tool, bind Uvicorn to `127.0.0.1`, set a fixed CORS allowlist or remove CORS, and document that the API must not be reverse-proxied publicly.
2. For shared or public use, add authentication before every `/api/*` route, attach an owner to each job, and enforce ownership for read, logs, cancellation, and download endpoints. Use a server-side session/JWT validation or an API-key layer with hashed stored keys; do not use the job ID as a credential.
3. Add per-principal quotas and an audit identity to job events.

### P0-2: Work is bounded only after unbounded task allocation

**Evidence.** `submit_job()` creates an `asyncio` task for every accepted request before waiting on `JOB_SLOTS` (`backend/main.py:459-499`). The only batch limit is 20 items (`68-75`), and callers can issue unlimited batches or individual POSTs. `text`, `url`, and rendering inputs have no length or size limits (`50-83`). Per job, up to four part renders are submitted (`592-603`) and each Remotion command asks for eight workers (`207-214`). Outputs are retained in `output/` without expiry (`503-608`).

**Impact.** A small number of requests can create unbounded Python tasks and job/log dictionaries. Two pipeline slots can create up to eight concurrent Remotion commands and request up to 64 rendering workers, before ffmpeg, Chromium, TTS, transcription, and file servers are counted. Long source text can increase LLM/TTS cost and generate many parts. Output files accumulate indefinitely.

**Recommendation.** Introduce admission control before task creation:

- Set maximum body size, source character count, URL length, batch size, parts per job, and audio/video duration.
- Maintain a bounded queue with a clear `429`/`503` response once full; do not create an unbounded task merely to wait on a semaphore.
- Treat render concurrency as one budget. For example, have a global render semaphore and choose `max_parallel_jobs × max_parallel_parts × remotion_concurrency` from actual hardware capacity. Defaulting Remotion to lower concurrency is safer than multiplying defaults.
- Enforce per-user/IP request and concurrent-job quotas.
- Add retention: delete intermediates after successful delivery, expire completed jobs and logs, and measure output disk usage before accepting new work.

### P1-1: Each renderer temporarily serves the entire repository

**Evidence.** `render_video()` and `test_frame()` call `start_file_server(str(ROOT))` (`188`, `666`). That helper starts `SimpleHTTPRequestHandler` over the repository root on a randomly selected localhost port (`123-135`). The root contains `.env`, source, `output/`, and other local artifacts.

**Impact.** Although it is bound to localhost, any process on the machine can retrieve files while the server is running. A malicious or compromised renderer/browser context could also request paths beyond the intended narration and B-roll assets. The server additionally has a time-of-check/time-of-use port race: `find_free_port()` releases a port before `ThreadingHTTPServer` binds it (`123-132`).

**Recommendation.** Serve only a per-job staging directory containing the exact audio and B-roll files required, or avoid HTTP entirely by using supported local/static asset paths in the render bundle. Bind an already-open socket rather than probing then reopening a port. Never place `.env` or repository root behind a generic static file handler.

### P1-2: External and child-process execution lacks a consistent timeout policy

**Evidence.** `ffprobe` has no timeout (`138-144`). Firecrawl, the OpenAI-compatible script call, and Groq transcription have no explicit client timeout (`250-268`, `284-344`, `365-383`). Remotion relies on a CLI timeout argument but `p.wait()` itself has no Python deadline (`207-245`). ffmpeg uses unbounded `p.wait()` calls (`417-454`). Preview renders use `communicate()` with no deadline (`689-730`). The async cancellation route performs blocking `p.wait(timeout=2)` directly in the event loop (`749-770`).

**Impact.** Network stalls and broken media can consume the limited job slots forever. A cancellation request can block the FastAPI event loop for two seconds per child process. Failed ffmpeg commands discard stderr, delaying diagnosis and leaving users with a generic `CalledProcessError`.

**Recommendation.** Define deadlines per phase and enforce them in the owning adapter:

- Configure explicit connect/read/write timeouts and retry policy for each external client.
- Use `subprocess.Popen(..., start_new_session=True)` and a shared async-safe process supervisor that terminates the entire process group on timeout/cancellation.
- Await process completion through a thread or asyncio subprocess API; never block an async route with `wait()`.
- Capture bounded stderr (for example, final 64 KiB) and store it in protected diagnostic logs.
- Validate ffprobe return codes and include a phase-specific error message.

### P1-3: Job state is not durable or concurrency-safe

**Evidence.** `JOBS`, `ACTIVE_TASKS`, and `ACTIVE_SUBPROCESSES` are module-global dictionaries (`42-46`). Async code and renderer progress threads mutate nested job dictionaries and log lists concurrently (`86-120`, `223-234`, `459-629`). Job state is not written to disk or a database. The dashboard fetches the same mutable structures via `GET /api/jobs` (`644-646`).

**Impact.** A restart loses jobs, output association, logs, and cancellation handles. Multiple Uvicorn workers would each see a different job universe. Concurrent list append/update/serialization can yield inconsistent progress or race-sensitive behaviour. A task is removed from `ACTIVE_TASKS` when its coroutine exits even if a child process is still finishing, which weakens cancellation accounting.

**Recommendation.** For a single-host production path, use a transactional job store (SQLite is sufficient initially) for job metadata, events, ownership, and terminal state, plus a single worker process. Use a real queue only when multiple workers/hosts or durable retries are needed. Keep active process handles in the worker, protect in-memory progress with a lock or deliver events through one event loop, and make terminal-state transitions idempotent.

### P1-4: Untrusted URL and prompt handling needs explicit policy

**Evidence.** Any non-empty `url` is forwarded to Firecrawl (`50-61`, `250-268`). The title and body are interpolated directly into a long LLM instruction string (`284-344`). There is no source-domain allowlist, private-address policy, URL canonicalization, text size cap, model-output schema validation beyond `json.loads`, or content moderation policy.

**Impact.** Depending on Firecrawl's fetch policy, arbitrary URL submission can be used to reach internal or non-public targets, consume scraping quota, or fetch sensitive content into third-party processing. Source text can attempt to override the narration instruction; malformed model output can break the job. The application sends the source, narration, and audio to multiple external processors, which needs a deliberate data-handling policy.

**Recommendation.** Allow only the intended public domains (for example, canonical Reddit hosts) when URL ingestion is a feature. Reject private, loopback, link-local, and credential-bearing URLs before the scraper call; re-check after DNS resolution if the scraper is self-hosted. Put untrusted source in a separately delimited data field/message, validate the returned JSON with a Pydantic model (including max parts and content length), and document/obtain consent for each external processor.

### P1-5: User-controlled asset pool is not constrained to `assets/`

**Evidence.** `video_file` is resolved and checked as a child of its selected pool (`386-399`), but `background` itself is simply joined to `ASSETS` without resolving and validating containment (`387`). A caller can supply path segments such as `..` as `background`.

**Impact.** The fallback clip selection can enumerate and select media from directories outside the intended asset pool when a caller supplies traversal segments. This is a restricted file-read route, not arbitrary command injection, because extension filtering remains in place; it still violates the asset isolation model.

**Recommendation.** Resolve `pool = (ASSETS / background).resolve()` and reject it unless `pool.parent == ASSETS.resolve()` (or validate `background` against the names returned by the controlled asset registry). Allow only a short safe-name pattern.

### P2-1: Observability implementation makes the dashboard an amplification path

**Evidence.** Every rendered-frame update appends a log event (`111-120`), up to 1,000 events per job (`86-96`). `GET /api/jobs` returns all jobs, including their logs (`644-646`), and the frontend fetches the entire response every two seconds (`frontend/src/app/page.tsx:71-82`) before rendering the entire list (`353-438`).

**Impact.** As history grows, each browser poll transfers and parses a larger response. A multi-part render can spend a material amount of CPU serializing logs and repainting the dashboard, exactly when rendering needs resources. Debug detail is valuable, but it should not be the default list payload.

**Recommendation.** Make the job list a compact paginated summary. Fetch one selected job plus a cursor-based log endpoint, or stream events over Server-Sent Events/WebSocket with backpressure. Coalesce frame events (for example, once per second or every N frames) while retaining exact current counters. Store diagnostic logs separately from public status and redact before display.

### P2-2: The backend has no meaningful module seams

**Evidence.** `backend/main.py` contains HTTP routing, request models, authentication-adjacent policy, state management, scraping, LLM prompting, TTS, transcription, asset selection, ffprobe, Remotion invocation, ffmpeg composition, telemetry, and cancellation in one 815-line module.

**Impact.** The module interface is shallow: a change to a workflow detail requires understanding server state, external providers, filesystem convention, and process lifecycle together. This inhibits focused tests and makes fault isolation difficult.

**Recommendation.** Deepen the workflow module around one interface such as `run_job(job_id, request)`, then move external effects behind small adapters only where there are real seams:

- `JobStore`: state/events/ownership/retention.
- `NarrationPipeline`: source extraction, script validation, TTS, transcription.
- `RenderWorker`: staging files, Remotion, ffmpeg, process supervision.
- API routes: validation, identity, job submission, and response shaping.

Do not introduce factories or interfaces with a single speculative implementation. First separate the job lifecycle from the transport layer, then extract the renderer because it already has two subprocess technologies and a distinct failure model.

### P2-3: Runtime installation and dependency management are operationally fragile

**Evidence.** A request can execute `npm install` if `remotion/node_modules` is missing (`164-168`). Python dependencies are manually pinned in `backend/requirements.txt`, while frontend and Remotion dependencies use separate lockfiles and a mix of exact and range versions. The frontend production build reports multiple lockfiles and an ambiguous workspace root.

**Impact.** The first render can unexpectedly require network access, mutate the deployment, and produce a different dependency tree from the tested image. Multiple package roots make CI and vulnerability scanning harder to reason about.

**Recommendation.** Build a reproducible image or deployment artifact that installs dependencies once with `npm ci`/locked Python requirements. Fail health checks clearly if render prerequisites are absent; never install during request handling. Pin the intended package-manager/workspace structure, set `turbopack.root` if the current layout remains, and run scheduled lockfile vulnerability scans in CI.

### P2-4: Error handling exposes internals and loses diagnostics

**Evidence.** Pipeline exceptions are copied directly into job status and logs (`621-626`), and preview endpoint errors include the first 500 bytes of renderer stderr in the HTTP response (`699-721`). ffmpeg errors are not captured (`417-454`).

**Impact.** API users can learn local paths, command details, or provider error text; operators lack enough preserved ffmpeg diagnostics to debug failures safely.

**Recommendation.** Return a stable public error code and request ID. Keep sanitized, access-controlled diagnostic detail in the job event store. Capture bounded stderr for every child process and classify known failures (missing asset, missing binary, timeout, provider failure, render failure).

### P2-5: Test coverage is absent at the risk-bearing seams

**Evidence.** No project test files or test configuration were found. The project contains only ad hoc execution scripts and manual frontend checks.

**Impact.** Input validation, authorization, cancellation races, process cleanup, job terminal state, path containment, and API response contracts can regress without detection.

**Recommendation.** Add a small set of high-value tests before a broad suite:

1. API authorization/ownership and rate-limit rejection.
2. URL and asset-path containment validation.
3. Bounded queue behaviour and terminal state transitions under cancellation.
4. A fake renderer/transcriber integration test verifying cleanup and event order.
5. Frontend rendering of queued, running, error, cancelled, and completed job payloads.

## Efficiency and correctness opportunities

| Area | Current behaviour | Optimization |
| --- | --- | --- |
| Render startup | Starts one local static server per rendered part | Stage assets once per job and reuse one controlled server or native asset path |
| Render capacity | Nested parallelism: jobs × parts × Remotion workers | Set one global render budget based on CPU, RAM, GPU, and encoder throughput |
| Logs | Appends a log per progress line and returns all logs in job list | Coalesce progress; page/stream logs separately |
| TTS/transcription | Parts are prepared sequentially | After explicit provider quotas and global budgets, parallelize independent preparation with a small semaphore |
| Asset scanning | Globs the selected pool on every job | Cache a validated asset manifest and invalidate on explicit refresh or filesystem watcher |
| Video concatenation | Writes a concat file and intermediate portrait video | Retain this simple path until profiling proves it costly; then use a direct filter graph or delete intermediates immediately |
| UI | One large client component owns composer, previews, monitor, history, and results | Split only into `Composer`, `JobList`, and `JobInspector` when the next UI change makes locality painful |

## Recommended remediation sequence

1. **Before any non-local exposure:** bind locally by default, remove wildcard CORS, add authentication/ownership, and protect all job/output/log routes.
2. **Before accepting untrusted traffic:** cap request and queue size, add per-principal quotas, validate URL and asset paths, and set phase/process timeouts.
3. **Before relying on it operationally:** replace process-global job state with durable state plus a supervised worker; add retention and cleanup.
4. **Then improve observability:** split summary, detail, and log APIs; stream or page events instead of polling all history.
5. **Then make it maintainable:** extract the job lifecycle and renderer seams, add the focused tests above, and make builds reproducible.

## Positive controls already present

- Secrets and generated media are ignored by Git (`.gitignore`); no `.env` file was tracked by the repository scan.
- Process invocations use argument arrays rather than shell strings, reducing direct shell-injection risk.
- `video_file` is resolved and checked against the chosen pool, which is a good containment pattern; apply the same control to `background`.
- The current job semaphore, job IDs, cancellation path, and detailed telemetry are useful foundations once admission control and authorization are added.

## Assessment limits

- Dependency manifests were inspected, but no current CVE/advisory lookup was performed.
- No live endpoint was exposed or fuzzed, and no secret values were read.
- The final severity depends on deployment. If Uvicorn is strictly loopback-only on a single-user computer, remote attack likelihood drops substantially; local privilege and denial-of-service risks remain.
