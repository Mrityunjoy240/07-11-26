# Current Dependencies

---

## Python Dependencies (requirements.txt)

| Package | Version | Purpose | Production Critical |
|---|---|---|---|
| **fastapi** | latest | Web framework for API endpoints | YES |
| **uvicorn[standard]** | latest | ASGI server | YES |
| **groq** | latest | Groq LLM API client (Llama 3.3, Mixtral) | YES |
| **python-dotenv** | latest | Load .env files | YES |
| **pydantic** | latest | Request/response validation, Settings management | YES |
| **pydantic-settings** | latest | Environment variable → Settings class | YES |
| **numpy** | latest | Audio processing, array operations | YES |
| **requests** | latest | HTTP client for external APIs | YES |
| **python-multipart** | latest | File upload handling | YES |
| **python-jose[cryptography]** | latest | JWT token creation and validation | YES |
| **passlib[bcrypt]** | latest | Password hashing and verification | YES |
| **slowapi** | latest | Rate limiting (10 req/min default) | YES |
| **httpx** | latest | Async HTTP client | YES |
| **websockets** | latest | WebSocket support for voice/telephony | YES |
| **pydub** | latest | Audio format conversion | YES |
| **sarvamai** | latest | Sarvam AI TTS/STT API client | YES |
| **aiofiles** | latest | Async file operations | YES |
| **pypdf** | latest | PDF file parsing for KB ingestion | YES |
| **pandas** | latest | Excel/CSV data parsing | YES |
| **openpyxl** | latest | Excel file support | YES |
| **cachetools** | latest | LRU cache for LLM responses | YES |
| **fasttext-wheel** | latest | Language detection model (Windows-compatible) | YES |

---

## Implicit Dependencies (not in requirements.txt)

| Package | Version | Used By | Purpose |
|---|---|---|---|
| **langchain-chroma** | latest | `vector_store.py` | ChromaDB vector store integration |
| **langchain-huggingface** | latest | `vector_store.py` | HuggingFace embedding models |
| **langchain-core** | latest | `vector_store.py`, `knowledge_base.py` | Document type, base classes |
| **chromadb** | latest | `vector_store.py` | Vector database (via langchain-chroma) |
| **sentence-transformers** | latest | `vector_store.py` | Embedding model (via langchain-huggingface) |
| **livekit** | latest | `livekit_session.py`, `voice.py` | LiveKit real-time audio transport |
| **twilio** | latest | `twilio_service.py` | Twilio telephony API |
| **inflect** | latest | `voice_utils.py` | Number-to-words conversion |
| **audioop-lts** | optional | `voice.py` | Audio format conversion (fallback) |
| **transformers** | latest | `intent_classifier.py` | Embedding model for intent classification |
| **torch** | latest | `intent_classifier.py` | PyTorch backend for embeddings |

---

## External Services

| Service | Dependency | Stage | Cost | Credentials In |
|---|---|---|---|---|
| **Groq API** | LLM responses | Production | Pay-per-token | `GROQ_API_KEY` env |
| **Sarvam AI API** | TTS + STT | Production | Pay-per-character | `SARVAM_API_KEY` env |
| **LiveKit Cloud/Self-host** | Real-time audio transport | Experimental | Free tier / self-host | `LIVEKIT_*` env vars |
| **Twilio** | Telephony (outbound calls) | Experimental | Pay-per-minute | `TWILIO_*` env vars |
| **FastText Model** | Language detection | Production | Free (meta) | Download at startup |
| **HuggingFace (all-MiniLM-L6-v2)** | Embeddings | Production | Free (download once) | Download at startup |

---

## Frontend Dependencies (package.json — inferred)

| Package | Purpose |
|---|---|
| **react** | UI framework |
| **react-dom** | DOM rendering |
| **react-router-dom** | Client-side routing |
| **@mui/material** | Material UI component library |
| **@mui/icons-material** | Material UI icons |
| **@emotion/react** | CSS-in-JS (MUI dependency) |
| **@emotion/styled** | Styled components (MUI dependency) |
| **vite** | Build tool and dev server |
| **typescript** | Type checking |

---

## Database

| Database | Purpose | Data |
|---|---|---|
| **SQLite** (via built-in `sqlite3`) | Conversation persistence | `conversations`, `messages` tables |
| **ChromaDB** (via `langchain-chroma`) | Vector storage | Document embeddings for RAG |

---

## Infrastructure Dependencies

| Tool | Purpose |
|---|---|
| **Python 3.11+** | Runtime |
| **Node.js 18+** | Frontend build |
| **Docker** (optional) | Containerized deployment via Dockerfile |
| **Railway / Fly.io / VPS** | Hosting (no CI/CD configured yet) |
