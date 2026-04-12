# YouTube Tools API

Unified FastAPI service combining YouTube channel URL extraction (yt-dlp) and transcript scraping (youtube-transcript-api) into a single Railway deployment.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/extract` | Extract video URLs from a YouTube channel (JSON) |
| `GET` | `/api/transcript` | Fetch a YouTube video transcript (JSON) |
| `GET` | `/health` | Health check |
| `GET` | `/version` | Package version info |
| `GET` | `/` | Web UI form |
| `POST` | `/` | Web UI form submission |

## Setup

```bash
pip install -r requirements.txt
python main.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | Yes (Railway sets it) | Server bind port |
| `PROXY_USERNAME` | No | Webshare proxy username |
| `PROXY_PASSWORD` | No | Webshare proxy password |

## Tests

```bash
python -m pytest test/ -v
```

## Deploy to Railway

Push this repo to GitHub and connect it to Railway. The `nixpacks.toml` and `railway.json` handle the build and start config.
