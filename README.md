# 🤖 Aria - AI Customer Support Chatbot

A production-ready AI chatbot system for service business websites, powered by **Ollama (Llama 3.1)**, **LangChain**, and **ChromaDB** with an embeddable JavaScript chat widget.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![Ollama](https://img.shields.io/badge/Ollama-Llama%203.1-purple)

---

## ✨ Features

- **RAG-Powered Responses** — Answers questions using your website content and FAQs
- **Web Scraping** — Auto-crawls your website (sitemap + BFS) up to 100 pages
- **Streaming Responses** — Real-time token streaming (SSE) for a natural typing effect
- **Human Escalation** — Detects frustration keywords and provides contact info
- **Embeddable Widget** — Single JS file, works on any website, zero dependencies
- **Dark Mode** — Auto-detects system preference
- **Mobile Responsive** — Works on phones and tablets
- **Auto-Refresh** — Re-scrapes website content every 24 hours
- **FAQ Priority** — FAQ answers are prioritized over scraped content

---

## 📁 Project Structure

```
chatbot-project/
├── backend/
│   ├── main.py              # FastAPI app + all endpoints
│   ├── scraper.py           # Website crawler module
│   ├── rag.py               # RAG pipeline (LangChain + ChromaDB)
│   ├── escalation.py        # Human escalation logic
│   ├── modelfile            # Ollama Modelfile for Aria
│   ├── faq.json             # Company FAQ data
│   ├── requirements.txt     # Python dependencies
│   └── .env                 # Configuration
├── widget/
│   └── aria-widget.js       # Embeddable chat widget
└── README.md
```

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai/) installed and running

### Step 1: Install Ollama

Download and install from [ollama.ai](https://ollama.ai/).

### Step 2: Pull Required Models

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

### Step 3: Install Python Dependencies

```bash
cd chatbot-project/backend
pip install -r requirements.txt
```

### Step 4: Configure Environment

Edit `backend/.env` with your details:

```env
WEBSITE_URL=https://yourwebsite.com
COMPANY_NAME=Your Company Name
SUPPORT_EMAIL=support@yourcompany.com
SUPPORT_PHONE=+91-XXXXXXXXXX
BUSINESS_HOURS=Mon-Fri 9AM-6PM IST
```

### Step 5: (Optional) Customize FAQs

Edit `backend/faq.json` with your company's frequently asked questions:

```json
[
  {
    "question": "What services do you offer?",
    "answer": "We offer web development, mobile apps, and cloud solutions."
  }
]
```

### Step 6: (Optional) Create Custom Ollama Model

```bash
cd backend
ollama create aria -f modelfile
```

Then update `.env` to use `LLM_MODEL=aria`.

### Step 7: Start the Server

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will:
- Load FAQ data into the knowledge base on startup
- Schedule auto-refresh every 24 hours
- Be available at `http://localhost:8000`

### Step 8: Ingest Your Website

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourwebsite.com"}'
```

Or use the FastAPI docs at `http://localhost:8000/docs`.

### Step 9: Add Widget to Your Website

Add this to any HTML page:

```html
<script>
  window.AriaConfig = {
    apiUrl: "http://localhost:8000",
    botName: "Aria",
    primaryColor: "#2563EB",
    companyName: "Your Company Name",
    position: "bottom-right"
  };
</script>
<script src="path/to/aria-widget.js"></script>
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send message, get streaming AI response (SSE) |
| `POST` | `/api/ingest` | Scrape a website URL into the knowledge base |
| `GET` | `/api/health` | Health check with service status |
| `POST` | `/api/escalate` | Trigger human escalation manually |

### Chat Request Example

```json
POST /api/chat
{
  "message": "What services do you offer?",
  "session_id": "optional-session-id"
}
```

Response: Server-Sent Events stream with tokens.

### Ingest Request Example

```json
POST /api/ingest
{
  "url": "https://yourwebsite.com"
}
```

Response:
```json
{
  "status": "success",
  "url": "https://yourwebsite.com",
  "documents_scraped": 25,
  "chunks_created": 142
}
```

---

## ⚙️ Widget Configuration

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `apiUrl` | string | `http://localhost:8000` | Backend API URL |
| `botName` | string | `Aria` | Bot display name |
| `primaryColor` | string | `#2563EB` | Theme color (hex) |
| `companyName` | string | `Your Company` | Company name |
| `position` | string | `bottom-right` | Widget position |

---

## 🔧 Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBSITE_URL` | — | Website to scrape |
| `COMPANY_NAME` | Your Company | Company display name |
| `SUPPORT_EMAIL` | support@yourcompany.com | Escalation email |
| `SUPPORT_PHONE` | +91-XXXXXXXXXX | Escalation phone |
| `BUSINESS_HOURS` | Mon-Fri 9AM-6PM IST | Business hours |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama server URL |
| `LLM_MODEL` | llama3.1 | LLM model name |
| `EMBEDDING_MODEL` | nomic-embed-text | Embedding model |
| `MAX_PAGES` | 100 | Max pages to scrape |
| `AUTO_REFRESH_HOURS` | 24 | Knowledge refresh interval |

---

## 🧑‍💼 Human Escalation

The bot automatically detects frustration keywords:
- "speak to human", "real person", "agent", "manager"
- "not helpful", "useless", "complaint", "frustrated"

When triggered, it displays contact info and logs to `escalations.log`.

---

## 📝 License

MIT License - feel free to use and modify for your business.
