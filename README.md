# AcmeAssist — Enterprise AI Agent 🚀

AcmeAssist is a **production-grade, cloud-native enterprise AI assistant** built on a fully decoupled, secure architecture. It answers employee questions using RAG (Retrieval-Augmented Generation) over internal company documents — with real-time streaming, persistent chat history, and self-service document uploads.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-black?logo=vercel)](https://enterprise-ai-agent-murex.vercel.app/)
[![Backend](https://img.shields.io/badge/Backend-AWS%20Elastic%20Beanstalk-orange?logo=amazon-aws)](https://aws.amazon.com/)
[![Database](https://img.shields.io/badge/Vector%20DB-Supabase-green?logo=supabase)](https://supabase.com/)

---

## 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        User / Web Browser                           │
│           (Zero keys · Zero SDK · Plain fetch() calls)             │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
             POST /auth/login · /stream · /upload · /sessions
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Vercel Edge (Frontend Proxy + Static SPA)             │
│        Rewrites all API calls → AWS Elastic Beanstalk               │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (AWS Elastic Beanstalk)            │
│                                                                     │
│  ┌─────────────────────┐   ┌──────────────────────────────────────┐ │
│  │   /auth/* Router    │   │        Agent Core Loop               │ │
│  │                     │   │                                      │ │
│  │ • POST /auth/login  │   │  Phase 1 — Tool Call (non-streaming) │ │
│  │ • POST /auth/signup │   │  1. Load session memory              │ │
│  │ • POST /auth/logout │   │  2. Call Groq API (Llama 3)         │ │
│  │ • GET  /auth/me     │   │  3. Detect TOOL_CALL instruction     │ │
│  │                     │   │  4. Embed query → pgvector search    │ │
│  │ Proxies to Supabase │   │  5. Inject context into messages     │ │
│  │ Auth API server-side│   │                                      │ │
│  └─────────────────────┘   │  Phase 2 — SSE Stream (visible)     │ │
│                            │  6. Stream clean answer token-by-    │ │
│  ┌─────────────────────┐   │     token via StreamingResponse      │ │
│  │  /upload Endpoint   │   │  7. Persist to Supabase chat_sessions│ │
│  │                     │   └──────────────────────────────────────┘ │
│  │ PDF/TXT → Extract   │                                            │
│  │ → Chunk → Embed     │                                            │
│  │ → Push to Supabase  │                                            │
│  └─────────────────────┘                                            │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Supabase Cloud (PostgreSQL)                    │
│                                                                     │
│   ┌────────────────────┐        ┌────────────────────────────────┐  │
│   │  documents table   │        │    chat_sessions table         │  │
│   │  (pgvector store)  │        │  (persistent chat history)     │  │
│   │                    │        │                                │  │
│   │  id · content      │        │  session_id · user_id          │  │
│   │  embedding (1536d) │        │  role · content · sources      │  │
│   │  metadata          │        │  created_at                    │  │
│   └────────────────────┘        └────────────────────────────────┘  │
│                                                                     │
│   Auth: Supabase Auth (proxied through FastAPI — no keys exposed)   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Enterprise Features

| Feature | Description |
| :--- | :--- |
| 🔐 **Secure Authentication** | Supabase JWT Auth fully proxied through FastAPI. Zero API keys in the frontend code or GitHub repo. |
| ⚡ **SSE Streaming Responses** | Two-phase streaming: RAG tool call runs first (silent), then the clean answer streams token-by-token like ChatGPT. |
| 💾 **Persistent Chat History** | Every conversation is saved to Supabase `chat_sessions`. Chat survives page refreshes and logouts. |
| 📋 **Session Sidebar** | Browse and reload any past conversation from the sidebar. |
| 📂 **Self-Service Document Upload** | Drag-and-drop `.pdf` or `.txt` from the UI → auto-chunked, embedded, and indexed into Supabase instantly. No redeploy needed. |
| 🌐 **Zero-Key Frontend** | The browser code has no Supabase SDK, no keys, no hardcoded credentials — just plain `fetch()` calls to our own API. |
| 🐳 **Dockerized & Scalable** | Full Docker setup on AWS EB. Stateless backend means horizontal scaling with zero data loss. |

---

## 🛠️ Technology Stack

| Layer | Component | Technology |
| :--- | :--- | :--- |
| **Logic** | API Framework | FastAPI (Python 3.11) |
| **Auth** | Authentication | Supabase Auth (server-side proxy) |
| **AI** | LLM Reasoning | Groq API · Llama 3 (via OpenAI SDK) |
| **AI** | Embeddings | `all-MiniLM-L6-v2` (local, free) |
| **Data** | Vector Store | Supabase `pgvector` |
| **Data** | Chat History | Supabase `chat_sessions` table |
| **Cloud** | Backend Hosting | AWS Elastic Beanstalk (Docker) |
| **Edge** | Frontend Hosting | Vercel (SPA + API Proxy) |
| **UI** | Styling | Vanilla CSS (glassmorphism) |

---

## 📂 Project Structure

```text
agent/
├── .ebextensions/           # AWS Infrastructure-as-Code (Swap & Disk expansion)
├── app/
│   ├── agent/               # LLM loop, memory, tools, prompts
│   ├── api/
│   │   ├── auth.py          # Auth proxy router (/auth/login, /signup, /logout, /me)
│   │   │                    # + get_current_user dependency for protected routes
│   │   └── routes.py        # /stream, /upload, /history, /sessions endpoints
│   ├── services/
│   │   ├── supabase_client.py  # Shared async HTTPX Supabase helper
│   │   └── chat_history.py     # Save & fetch chat messages
│   ├── rag/                 # Embedding, chunking, retrieval engine
│   ├── models/schemas.py    # Pydantic request/response models
│   └── main.py              # App entry point & lifespan
├── documents/               # Enterprise knowledge base (.txt files)
├── scripts/
│   └── index_documents.py   # One-time bulk indexing script
├── static/                  # SPA Frontend (HTML + CSS + JS)
│   ├── index.html           # Auth screen + sidebar + upload modal
│   ├── style.css            # Full glassmorphic design system
│   └── app.js               # Zero-key auth + SSE streaming + session sidebar
├── Dockerfile               # Production Docker image
├── requirements.txt         # Python dependencies
└── vercel.json              # Frontend deployment & API proxy config
```

---

## 🚀 Setup & Deployment

### 1. Prerequisites

- Python 3.11+
- [Supabase](https://supabase.com) project with `pgvector` enabled
- [Groq](https://console.groq.com) API key
- [AWS CLI](https://aws.amazon.com/cli/) + [EB CLI](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3.html)
- [Vercel CLI](https://vercel.com/docs/cli)

### 2. Clone & Configure

```bash
git clone https://github.com/mayank123hangsh00/Enterprise-AI-Agent.git
cd Enterprise-AI-Agent
cp .env.example .env
# Fill in your keys in .env
```

### 3. Supabase Setup

Run the following SQL in your **Supabase SQL Editor**:

```sql
-- Enable pgvector (already done if you set up the documents table before)
create extension if not exists vector;

-- Chat history persistence table
CREATE TABLE chat_sessions (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id text NOT NULL,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  content text NOT NULL,
  sources text[] DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX idx_chat_sessions_user_id    ON chat_sessions(user_id);
```

Also go to **Authentication → URL Configuration** and set your **Site URL** to your Vercel domain.

### 4. Initial Document Indexing

```bash
pip install -r requirements.txt
python scripts/index_documents.py
```

> After this, use the **Upload Doc** button in the UI for all future documents — no script needed.

### 5. Local Development

```bash
uvicorn app.main:app --reload
# Open http://localhost:8000
```

### 6. Deploy to AWS

```bash
eb deploy
```

### 7. Deploy to Vercel

```bash
vercel --prod
```

Vercel auto-deploys on every `git push` to `main`.

---

## 🔐 Security Architecture

| Concern | How It's Handled |
| :--- | :--- |
| **No keys in frontend** | All Supabase auth calls are proxied through FastAPI backend; browser code has no credentials |
| **No keys in GitHub** | `.env` is in `.gitignore`; only `.env.example` (no real values) is committed |
| **Token storage** | JWT stored in memory only — never `localStorage` (prevents XSS theft) |
| **Protected endpoints** | All `/stream`, `/upload`, `/history`, `/sessions` require valid Bearer token via `get_current_user` dependency |
| **Local embeddings** | Document text is never sent to third-party embedding APIs; all embeddings generated on-server |
| **Stateless backend** | No local files; AWS instance can crash/restart with zero data loss |

---

## 🎥 Live Demos

### 1. Real-Time Streaming Response
![AcmeAssist Demo](assets/demo_recording.webp)

### 2. RAG Document Retrieval
![Remote Work RAG Demo](assets/agent_demo_remote_work.webp)

---

## 📬 API Reference

| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | ❌ | Login with email + password |
| `POST` | `/auth/signup` | ❌ | Create new account |
| `POST` | `/auth/logout` | ✅ | Invalidate session |
| `GET` | `/auth/me` | ✅ | Get current user info |
| `POST` | `/stream` | ✅ | SSE streaming RAG response |
| `POST` | `/upload` | ✅ | Upload & index a PDF or TXT |
| `GET` | `/sessions` | ✅ | List user's past sessions |
| `GET` | `/history/{session_id}` | ✅ | Load messages for a session |
| `GET` | `/health` | ❌ | AWS health check |

---

*Built Production, enterprise grade AI Agent*
