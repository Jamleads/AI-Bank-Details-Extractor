## Extraction flow: concurrency and optimisation plan

### Current bottlenecks
- **Sequential per-file processing**: `/api/extract` awaits each file (and ZIP entries) serially.
- **CPU-bound work on event loop**: PDF parsing (PyPDF2), image decoding (Pillow), base64 encoding block the loop.
- **New HTTP client per call**: A new `httpx.AsyncClient` is created for each Gemini call; no pooling/HTTP2.
- **ZIP handling**: Entries are accumulated then processed; no streaming or overlap.
- **Synchronous DB writes in async path**: `db_adapter` is sync and called from async context.
- **No retries/backoff**: Transient Gemini failures cause hard failures; single 60s timeout isn’t tuned.
- **Heavy logging**: Logging full JSON payloads increases CPU/memory and log volume.

### Concurrent Request Capacity Analysis

#### Current Limits
- **Per-Lambda concurrency**: 6 documents (hardcoded `MAX_CONCURRENCY`)
- **HTTPX connections**: 20 max connections to Gemini
- **Lambda specs**: 1024MB memory, 30s timeout
- **AWS Lambda**: Up to 1000 concurrent instances (default)
- **Theoretical max**: ~6,000 concurrent document operations

#### Real-World Constraints
1. **Gemini API rate limits**: ~60 requests/minute (free tier), ~1500/day
2. **Lambda timeout**: 30s may be insufficient for large files
3. **Memory pressure**: 1024MB tight for large files + base64 encoding
4. **No retry logic**: Transient failures cause hard failures

#### Realistic Capacity Estimates
- **Conservative**: 10-30 concurrent users, ~60-180 docs/minute
- **Optimized**: 50-100 concurrent users, ~300-600 docs/minute
- **Primary bottleneck**: External Gemini API quotas

#### Scaling Recommendations
1. **Make concurrency configurable**: `MAX_CONCURRENCY` via environment variable
2. **Increase Lambda resources**: 2048MB memory, 60s timeout
3. **Implement rate limiting**: Per-user request throttling
4. **Add retry logic**: Exponential backoff for API failures
5. **Monitor quotas**: Track Gemini API usage and implement queuing
6. **Consider async processing**: Queue jobs for background processing

### Checklist
- [x] Introduce bounded concurrency (Semaphore/TaskGroup) in `/api/extract` for files and ZIP entries
- [x] Reuse a single `httpx.AsyncClient` with HTTP/2, tuned limits and timeouts in `GeminiService`
- [x] Offload CPU-bound steps (PDF validation, image open, base64) to threads via `anyio.to_thread`
- [x] Stream ZIP entries and schedule processing tasks as each entry is ready (respecting the same concurrency cap)
- [ ] Wrap synchronous DB adapter calls with `to_thread.run_sync` or migrate to async DB access
- [ ] Implement retries with exponential backoff and jitter on Gemini calls; split connect/read/write timeouts
- [x] Reduce logging payloads (log filenames/sizes; avoid raw JSON)
- [ ] Add per-file timing/metrics and concurrency cap configuration (env-based)
- [ ] Consider frontend batching (optional) if backend limits require spreading load
- [ ] Operational tuning: uvloop, worker counts, threadpool size, rate limiting per user/app

### Implementation sketches

- **Bounded concurrency in `/api/extract`**
```python
# app/api/routes.py
from asyncio import Semaphore, gather

MAX_CONCURRENCY = 6  # tune via config

async def _process_one_blob(filename, data, ext, header_config, gemini_service, user_id, sem):
    async with sem:
        json_data = await gemini_service.extract_bank_details_async(data, ext, header_config)
        await save_raw_extraction(user_id, filename, json_data)
        return {"source_pdf": filename, "raw_data": json_data}

@router.post("/extract", response_model=ProcessResponse)
async def extract_bank_details(...):
    sem = Semaphore(MAX_CONCURRENCY)
    tasks = []

    for file in files:
        content = await file.read()
        ext = os.path.splitext(file.filename.lower())[-1]

        if ext == ".zip":
            extracted_files = await extract_zip_files_async(content)
            for entry in extracted_files:
                name = secure_filename(entry['filename'])
                data = entry['data']
                eext = entry['ext']
                if len(data) > 100:
                    tasks.append(_process_one_blob(name, data, eext, header_config, gemini_service, get_user_id(current_user), sem))
        else:
            name = secure_filename(os.path.splitext(file.filename)[0])
            tasks.append(_process_one_blob(name, content, ext, header_config, gemini_service, get_user_id(current_user), sem))

    results, errors = [], []
    if tasks:
        for res in await gather(*tasks, return_exceptions=True):
            if isinstance(res, Exception):
                errors.append({"filename": "unknown", "error": f"Processing error: {res}"})
            else:
                results.append(res)

    if not results and errors:
        raise HTTPException(status_code=400, detail="Failed to process files: one or more errors")

    return ProcessResponse(success=True, results=results, errors=errors)
```

- **Reuse `httpx.AsyncClient`, offload CPU work, add retries**
```python
# app/services/gemini_service.py
import anyio, httpx, base64

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.API_KEY)
        self.api_key = settings.API_KEY
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        self.client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(connect=5, read=55, write=30, pool=60),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
            headers={"Content-Type": "application/json"},
        )

    async def _validate_pdf_async(self, data: bytes) -> bool:
        return await anyio.to_thread.run_sync(self._validate_pdf, data)

    async def _validate_image_async(self, data: bytes) -> bool:
        return await anyio.to_thread.run_sync(self._validate_image, data)

    async def _b64encode_async(self, data: bytes) -> str:
        return await anyio.to_thread.run_sync(lambda: base64.b64encode(data).decode("utf-8"))

    async def extract_bank_details_async(self, file_data: bytes, file_ext: str = '.pdf', header_config=None) -> Dict[str, Any]:
        if file_ext.lower() == '.pdf':
            if not await self._validate_pdf_async(file_data):
                raise HTTPException(status_code=400, detail="Invalid PDF")
            mime_type = "application/pdf"
        elif file_ext.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
            if not await self._validate_image_async(file_data):
                raise HTTPException(status_code=400, detail="Invalid image")
            mime_type = {'.png': 'image/png', '.webp': 'image/webp'}.get(file_ext.lower(), 'image/jpeg')
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_ext}")

        prompt_text = self._create_prompt(header_config)
        encoded_file = await self._b64encode_async(file_data)
        payload = {"contents": [{"parts": [{"inlineData": {"mimeType": mime_type, "data": encoded_file}}, {"text": prompt_text}]}]}

        # retries with backoff
        delay = 0.5
        for attempt in range(3):
            try:
                resp = await self.client.post(f"{self.api_url}?key={self.api_key}", json=payload)
                resp.raise_for_status()
                break
            except httpx.HTTPError as e:
                if attempt == 2:
                    raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")
                await anyio.sleep(delay)
                delay *= 2

        data = resp.json()
        # ... parse to JSON dict (existing _parse_response flow)
        # return parsed dict
```

- **Make DB adapter calls async-safe**
```python
# app/db/operations.py
import anyio

async def save_raw_extraction(user_id, filename, extraction_data, db=None):
    def _create():
        return db_adapter.create_raw_extraction({"user_id": user_id, "source_pdf": filename, "raw_json": extraction_data})
    try:
        result = await anyio.to_thread.run_sync(_create)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### Tuning & operations
- **Caps**: Start with 4–6 concurrent Gemini calls per worker; adjust via metrics (QPS, latency, error rates).
- **Timeouts**: Separate connect/read/write; fail fast on connect, leave generous read for larger files.
- **Workers**: Use uvicorn with uvloop; multiple workers and adequate threadpool size for validation/base64.
- **Rate limits**: Enforce per-user/app concurrency caps to protect quotas.
- **Metrics**: Record per-file timings, task queue depth, retries; use to right-size `MAX_CONCURRENCY` and HTTPX limits.

### Optional UX enhancements
- **Incremental results**: Stream results (SSE/WebSocket) or queue background jobs and poll `/api/session-status`.
- **Client-side batching**: If necessary, split large uploads into batches and send a few parallel requests with a cap.

### Acceptance criteria
- Concurrent processing of multiple documents and ZIP entries without overwhelming the service or Gemini.
- Event loop remains responsive (CPU tasks moved off-thread).
- Stable throughput under load with bounded memory and clear backpressure.
- Meaningful metrics for capacity tuning and error handling.
