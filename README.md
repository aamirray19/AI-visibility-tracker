# AI Campaign & Brand Visibility Tracker

A comprehensive analytics platform that tracks how AI models (ChatGPT, Gemini, Perplexity, etc.) mention and rank your brand across different search intents. Built with FastAPI, Next.js, and Groq AI.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Groq API Key ([Get one free](https://console.groq.com))
- Google AI Studio API Key ([Get one](https://aistudio.google.com/app/apikey))

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/aamirray19/AI-visibility-tracker.git 
cd ai-visible-tracker
```

2. **Configure environment variables**
```bash
# Create .env file in project root
echo "GROQ_API_KEY=your_groq_api_key_here" > .env
echo "GOOGLE_API_KEY=your_google_ai_studio_api_key_here" >> .env
```

3. **Start the application**
```bash
docker-compose up --build -d
```

4. **Access the dashboard**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api
- Database: PostgreSQL on port 5432

### First Campaign

1. Enter a product category (e.g., "CRM software")
2. Select your brand from AI-generated suggestions
3. System generates 100 diverse prompts (80 commercial, 20 informational)
4. Watch real-time processing and analytics

---

## 📊 Key Features

### Advanced Analytics
- **AI Visibility Score**: Percentage of prompts where your brand appears
- **Citation Share**: How often your URLs are cited vs competitors
- **Competitor Leaderboard**: Track competitor mentions and sentiment
- **Top Cited Pages**: Most referenced URLs across AI responses
- **Sentiment Analysis**: Brand perception tracking
- **Intent Segmentation**: Commercial vs informational performance

### Real-Time Processing
- Sequential prompt processing (respects rate limits)
- Live progress tracking
- Automatic retry logic for API failures
- 2-second delay between requests (30 RPM limit)

---

## 🏗️ Architecture

### Tech Stack
- **Backend**: FastAPI + SQLModel + AsyncPG
- **Frontend**: Next.js 14 + TailwindCSS + Framer Motion
- **AI Models**: Groq GPT-OSS 120B + Google AI Studio Gemma 3 27B (both with built-in web search)
- **Queue**: Redis + ARQ for background jobs
- **Database**: PostgreSQL 15

### System Flow
```
User Input → Brand Discovery (Groq) → Prompt Generation (Groq) 
→ Queue Jobs → Worker Processes → AI Execution (Groq GPT-OSS 120B + Google Gemma 3 27B with web search) 
→ Analysis (Groq) → Database → Real-time Dashboard
```

---

## 🎯 Key Design Decisions

### 1. **Dual Model Monitoring**
**Decision**: Run each prompt against Groq GPT-OSS 120B and Google Gemma 3 27B using inbuilt web search

**Rationale**:
- **14,400 requests/day** free tier (vs Gemini's 20/day)
- **30 RPM** vs Gemini's 15-20 RPM
- **10x faster** response times
- **No quota headaches** during development
- Cost-effective for production scaling

**Trade-offs**: Higher request volume and more API key management, but much richer cross-model visibility data

**Location**: `backend/app/services/executor.py`, `analyzer.py`, `llm.py`, `prompt_factory.py`

---

### 2. **Sequential Job Processing with Rate Limiting**
**Decision**: Process one prompt at a time with 2-second delays

**Rationale**:
- Prevents rate limit errors (30 RPM = 1 req/2s)
- Ensures reliable completion vs parallel failures
- Simplifies error handling and retry logic
- Predictable processing time (~7 minutes for 100 prompts)

**Trade-offs**: Slower than parallel processing, but 100% reliable

**Location**: `backend/app/worker.py` (line 124: `max_jobs = 1`, line 49: `await asyncio.sleep(2)`)

---

### 3. **Direct API Calls Instead of Browser Automation**
**Decision**: Use LiteLLM for direct API calls vs Playwright/Selenium

**Rationale**:
- **90% faster** execution (API call vs browser render)
- **No CAPTCHA issues** or anti-bot detection
- **Simpler infrastructure** (no headless browsers)
- **Better error handling** with retry logic
- **Lower resource usage** (no Chrome instances)

**Trade-offs**: Can't capture visual elements or screenshots, but not needed for text analysis

**Location**: `backend/app/services/executor.py` (replaced `crawler.py`)

---

### 4. **Comprehensive Analysis with Structured JSON**
**Decision**: Use LLM for brand detection, competitor tracking, and URL extraction

**Rationale**:
- **Semantic understanding** vs regex (handles variations: "HubSpot" vs "Hubspot")
- **Context-aware** sentiment analysis
- **Automatic competitor detection** without predefined lists
- **URL attribution** to brands (knows salesforce.com = Salesforce)
- **Flexible schema** for future metric additions

**Trade-offs**: Adds ~1-2 seconds per prompt, but provides rich insights

**Location**: `backend/app/services/analyzer.py` (lines 26-103)

---

### 5. **Dual Database Model: Results + Derived Tables**
**Decision**: Store raw results + separate tables for competitors and URLs

**Rationale**:
- **Efficient aggregation** for leaderboards (no JSON parsing in SQL)
- **Flexible querying** for citation share metrics
- **Scalable analytics** as data grows
- **Maintains raw data** for re-analysis if needed
- **Optimized indexes** on foreign keys

**Trade-offs**: Slightly more complex schema, but enables advanced analytics

**Location**: 
- `backend/app/models/result.py` (main results)
- `backend/app/models/cited_url.py` (URL tracking)
- `backend/app/models/competitor_mention.py` (competitor tracking)

---

## 🔧 What We'd Improve

### Short-term (Production Ready)
1. **Add caching** for dashboard queries (Redis)
2. **Implement pagination** for large result sets
3. **Add export functionality** (CSV/PDF reports)
4. **Improve error notifications** (email/Slack alerts)
5. **Add user authentication** (JWT tokens)

### Medium-term (Scale)
1. **Multi-platform support** (test ChatGPT, Claude, Perplexity)
2. **Historical tracking** (trend analysis over time)
3. **Competitor benchmarking** (compare against industry averages)
4. **Custom prompt templates** (user-defined scenarios)
5. **Webhook integrations** (Zapier, Make.com)

### Long-term (Enterprise)
1. **Multi-tenant architecture** (team workspaces)
2. **Advanced ML models** (predict brand visibility trends)
3. **Real-time monitoring** (alert on ranking changes)
4. **API rate limit optimizer** (dynamic batching)
5. **White-label solution** (custom branding for agencies)

---

## 📁 Project Structure

```
ai-visible-tracker/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI endpoints
│   │   ├── models/        # SQLModel schemas
│   │   ├── services/      # Business logic (LLM, analysis)
│   │   ├── core/          # Database, queue config
│   │   └── worker.py      # ARQ background jobs
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/              # Next.js pages
│   ├── components/       # React components
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env
└── README.md
```

---

## 🐛 Troubleshooting

### Prompts not generating
```bash
# Check if API keys are set
docker-compose exec backend python -c "import os; print(os.getenv('GROQ_API_KEY'), os.getenv('GOOGLE_API_KEY'))"

# Restart backend
docker-compose restart backend worker
```

### Rate limit errors
```bash
# Increase delay in worker.py (line 49)
await asyncio.sleep(3)  # Change from 2 to 3 seconds
```

### Database connection issues
```bash
# Reset database
docker-compose down -v
docker-compose up --build -d
```

---

## 📝 API Documentation

### Create Campaign
```bash
POST /api/campaigns/create
{
  "brand": "HubSpot",
  "category": "CRM software"
}
```

### Get Dashboard
```bash
GET /api/campaigns/{campaign_id}
```

### Discover Brands
```bash
POST /api/companies/discover
{
  "category": "CRM software"
}
```

---




