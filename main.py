import asyncio
import os

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig

# --- FastAPI App ---
app = FastAPI(title="YouTube Tools API")

# --- Jinja2 Templates ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# --- Proxy Configuration ---
PROXY_USERNAME = os.environ.get("PROXY_USERNAME", "")
PROXY_PASSWORD = os.environ.get("PROXY_PASSWORD", "")


# --- Pydantic Models ---
class ExtractRequest(BaseModel):
    channel_name: str = Field(..., min_length=1, description="YouTube channel name")


class ExtractResponse(BaseModel):
    channel: str
    count: int
    urls: list[str]


class TranscriptSegment(BaseModel):
    text: str
    start: float
    dur: float


class TranscriptResponse(BaseModel):
    videoId: str
    lang: str
    content: list[TranscriptSegment]


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    error: str


# --- Core Functions ---

async def extract_video_urls(channel_name: str) -> list[str]:
    """Run yt-dlp as async subprocess, return list of video URLs."""
    channel_url = f"https://www.youtube.com/@{channel_name}"
    process = await asyncio.create_subprocess_exec(
        "yt-dlp", "--flat-playlist", "--get-url", channel_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise

    if process.returncode != 0:
        error_msg = stderr.decode().strip() or "Failed to extract URLs"
        raise RuntimeError(error_msg)

    urls = [
        line.strip()
        for line in stdout.decode().strip().splitlines()
        if line.strip()
    ]
    return urls


# --- Channel Extractor JSON Endpoint ---

@app.post("/api/extract", response_model=ExtractResponse, responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}})
async def api_extract(request: Request):
    body = await request.json()
    channel_name = body.get("channel_name")
    if not channel_name or not isinstance(channel_name, str) or not channel_name.strip():
        return JSONResponse(status_code=400, content={"error": "channel_name is required"})

    channel_name = channel_name.strip()
    try:
        urls = await extract_video_urls(channel_name)
    except asyncio.TimeoutError:
        return JSONResponse(status_code=504, content={"error": "Timed out extracting URLs"})
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})

    return ExtractResponse(channel=channel_name, count=len(urls), urls=urls)


# --- Transcript Scraper Endpoint ---

@app.get("/api/transcript", response_model=TranscriptResponse)
def get_transcript(videoId: str, lang: str = "en"):
    try:
        ytt = YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=PROXY_USERNAME,
                proxy_password=PROXY_PASSWORD,
            )
        )

        transcript_list = ytt.list(videoId)

        fallback_langs = ["en", "zh-TW", "zh-CN", "ja", "ko"]
        try:
            transcript = transcript_list.find_transcript([lang])
        except Exception:
            try:
                transcript = transcript_list.find_transcript(fallback_langs)
            except Exception:
                transcript = transcript_list.find_generated_transcript(fallback_langs)

        fetched = transcript.fetch()

        return TranscriptResponse(
            videoId=videoId,
            lang=transcript.language_code,
            content=[
                TranscriptSegment(text=item.text, start=item.start, dur=item.duration)
                for item in fetched
            ],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Web UI Routes ---

@app.get("/")
async def index_get(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"urls": [], "error": None, "channel_name": ""},
    )


@app.post("/")
async def index_post(request: Request, channel_name: str = Form("")):
    urls: list[str] = []
    error: str | None = None
    channel_name = channel_name.strip()

    if not channel_name:
        error = "Please enter a channel name."
    else:
        try:
            urls = await extract_video_urls(channel_name)
            if not urls:
                error = "No videos found for this channel."
        except RuntimeError as e:
            error = str(e)
        except asyncio.TimeoutError:
            error = "Request timed out. The channel may have too many videos."

    return templates.TemplateResponse(
        request,
        "index.html",
        {"urls": urls, "error": error, "channel_name": channel_name},
    )


# --- Health & Diagnostics Endpoints ---

@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    import subprocess

    result = subprocess.run(
        ["pip", "show", "youtube-transcript-api"], capture_output=True, text=True
    )
    return {"output": result.stdout}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
