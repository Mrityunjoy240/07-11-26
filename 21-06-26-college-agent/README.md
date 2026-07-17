# College Voice Agent

AI-powered multilingual chatbot + telephony voice agent for college admissions.

Built on:
- **RAG Backend**: FastAPI + Groq LLM + ChromaDB + BGE-M3 embeddings
- **Multilingual**: English, Hindi, Bengali — FastText detection + Sarvam AI TTS/STT
- **Telephony**: Dograh (white-labeled, open-source voice agent platform)
- **Web Chat**: React + TypeScript + Material-UI

## Architecture

```
Caller → [Phone] → Twilio → Dograh (STT → LLM → Tool Call → TTS)
                                │
                   POST /qa/query ← Our RAG Backend (ChromaDB + Groq)
                                │
                            College KB
```

## Quick Start (Web Chat Only)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # Add GROQ_API_KEY and SARVAM_API_KEY
uvicorn app.main:app --reload --port 8000
```

## Full Stack (Web Chat + Telephony)

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env: add Groq, Sarvam keys, and set OSS_JWT_SECRET

# 2. Start everything
docker compose up -d

# 3. Create Dograh account (first visit to http://localhost:3010)
# 4. Set up the voice agent:
python scripts/setup_agent.py --jwt <token_from_dograh_ui>
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `POST /qa/query` | Ask a question (text, returns answer) |
| `POST /qa/query-stream` | Streaming response (SSE) |
| `POST /qa/tts-direct` | Text to speech |
| `POST /qa/stt` | Speech to text |
| `GET /api/conversations` | Conversation history |
| `POST /admin/upload` | Upload KB documents |

## White-Labeling (Dograh → College Agent)

Dograh is BSD 2-Clause licensed. To remove all Dograh branding:

```bash
# Fork the repo, then run:
bash dograh/fork-and-brand.sh
```

See `dograh/fork-and-brand.sh` for detailed instructions.
