# 🔬 Multi-Agent Research Assistant (MARA)

A powerful AI-powered research assistant that uses multiple specialized agents to search, analyze, synthesize, and generate research reports — all in real-time.

## ✨ Features

- 🤖 **Multi-agent pipeline** — Planner, Searcher, Critic, Synthesizer, Writer & Hypothesis agents
- 📄 **PDF upload & analysis** — Upload papers for deep per-paper analysis
- 🔍 **Hybrid search** — BM25 + semantic search with re-ranking
- 🧠 **Knowledge graph** — Visual graph of paper relationships and topics
- 📊 **Comparative analysis** — Cross-paper comparison and contradiction detection
- 💬 **Real-time streaming** — Live agent status updates via WebSocket

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, LangGraph, Groq (LLaMA 3.3) |
| Frontend | Next.js 14, TypeScript, TailwindCSS |
| Memory | ChromaDB (vector store), BM25, NetworkX (knowledge graph) |
| Search | arXiv, Semantic Scholar, CrossRef |

## ⚙️ Prerequisites

- Python 3.11+
- Node.js 18+
- A **Groq API key** → get one free at [console.groq.com](https://console.groq.com)

## 🚀 Setup & Run

### 1. Clone the repository

```bash
git clone https://github.com/suhruthsai/multi-agent-research-assistant.git
cd multi-agent-research-assistant
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
LANGCHAIN_API_KEY=your_langchain_key_here   # optional, for tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=mara-research-assistant
```

### 3. Set up the backend

```bash
# Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Set up the frontend

```bash
cd frontend
npm install
cd ..
```

### 5. Run the backend

From the **project root**:

```bash
source venv/bin/activate
bash run_server.sh
```

Backend will start at → **http://localhost:8000**

### 6. Run the frontend

Open a **new terminal**, then:

```bash
cd frontend
npm run dev
```

Frontend will start at → **http://localhost:3000**

---

Open your browser at **http://localhost:3000** and start researching! 🎉

## 📁 Project Structure

```
├── backend/
│   ├── agents/          # Multi-agent pipeline (planner, searcher, critic, etc.)
│   ├── api/             # FastAPI app + WebSocket endpoint
│   ├── memory/          # Vector store, knowledge graph, history
│   ├── tools/           # Academic search, PDF processing, query expansion
│   └── state.py         # Shared agent state
├── frontend/
│   ├── app/             # Next.js app router
│   └── components/      # UI components (report, graph, analyzer, etc.)
├── requirements.txt     # Python dependencies
├── run_server.sh        # Backend startup script
└── .env.example         # Environment variable template
```

## 🔑 API Keys Needed

| Key | Required | Where to get |
|-----|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | [console.groq.com](https://console.groq.com) — Free |
| `LANGCHAIN_API_KEY` | ❌ Optional | [smith.langchain.com](https://smith.langchain.com) — For tracing |
