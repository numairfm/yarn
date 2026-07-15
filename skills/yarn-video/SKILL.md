---
name: yarn-video
description: Generate autonomous Yarn story videos through its HTTP API. Use when asked to submit one or many video jobs, monitor their status, cancel a job, or retrieve completed video URLs from a running Yarn service.
---

# Yarn Video

Set `YARN_API_URL` to the service URL, defaulting to `http://localhost:8000`.

## Submit and monitor

Submit `POST $YARN_API_URL/api/jobs` with either `text` or `url`. Optional fields are `background`, `video_file`, and `voice`. The response contains `job_id`.

Set `background` to a specific pool name (e.g. `"minecraft"`, `"gta"`) to pick from that category, or `"*"` to randomly select a video from **all** asset categories on each render. When `background="*"`, the `video_file` field is ignored.

Use `GET /api/assets/random-video` to fetch a random video pick from all pools (returns `{filename, pool, path}`).

Poll `GET /api/jobs/{job_id}` until `status` is `done`, `error`, or `cancelled`. On success, return `parts` and `combinedOutput` as URLs relative to `YARN_API_URL`. Call `POST /api/cancel/{job_id}` to stop it.

For independent videos, submit them concurrently with `POST /api/jobs/batch` using `{ "jobs": [ ... ] }`. Do not poll more often than every five seconds. The service caps active jobs with `MAX_PARALLEL_JOBS`.

Use `GET /docs` for the live OpenAPI contract and `GET /api/health` before submitting work. Report API errors directly; do not retry cancelled jobs.
