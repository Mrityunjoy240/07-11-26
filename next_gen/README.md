# BCREC AI Receptionist — Next-Gen Architecture

> Omnichannel AI College Receptionist | Free Tools Only | Demo-First

---

## Quick Start

### 1. Backend

```bash
cd next_gen

# Install dependencies
pip install -r requirements.txt

# Set API key
export GROQ_API_KEY=your_key_here

# Start server
python scripts/start_server.py
```

### 2. Frontend

```bash
cd next_gen/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### 3. Open

- Frontend: http://localhost:5173
- API: http://localhost:8000/api/health

---

## Architecture

```
Channel Adapters (REST, WebSocket, Twilio)
        ↓
Conversation Pipeline (single path)
        ↓
┌───────┴───────┐
│ Structured    │  RAG + LLM
│ Handlers      │  (Groq/Ollama)
│ (JSON lookup) │
└───────┬───────┘
        ↓
Post-Processor (validate + format)
        ↓
Response
```

**80% of queries answered without any LLM call.**

---

## Features

- **Text Chat** — Type questions in English, Hindi, or Bengali
- **Voice Input** — Click microphone, speak naturally
- **Voice Output** — Click speaker to hear answers
- **Follow-up Memory** — System remembers conversation context
- **Instant Answers** — Fee lookups, contacts, placement in <10ms
- **RAG Answers** — Complex questions handled by LLM
- **Hallucination Guard** — Validates answers against knowledge base

---

## Cost

| Item | Cost |
|------|------|
| LLM (Groq free tier) | $0 |
| Vector DB (ChromaDB local) | $0 |
| TTS (edge-tts) | $0 |
| STT (Web Speech API) | $0 |
| Hosting (localhost) | $0 |
| **Total** | **$0** |

---

## Knowledge Updates

Edit `data/knowledge_base.json` — restart server. No code changes needed.

---

## Production Path

After demo succeeds:
1. Add SQLite session persistence
2. Add Twilio telephone adapter
3. Add admin dashboard
4. Add observability
5. Add CI/CD

Each phase is deployable and reversible.
