# TradeCore FastAPI

Local-first personal portfolio intelligence API.

## Setup

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

From the repository root:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\server\.venv\Scripts\uvicorn.exe server.main:app --host 127.0.0.1 --port 5080 --reload
```

Optional keys in `server/.env`:

- `GEMINI_API_KEY` / `GEMINI_MODEL` for portfolio analysis
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_USER_EMAIL` for the bot

Next.js continues to proxy to `http://localhost:5080`.
