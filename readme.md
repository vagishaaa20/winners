# 🍯 Agentic Honeypot API

An intelligent AI-powered honeypot that impersonates a confused Indian bank customer ("Priya") to engage scammers, waste their time, and extract identifying intelligence for reporting.

## Description

This system acts as a conversational honeypot — a fake "victim" that scammers interact with naturally. It uses an LLM-driven persona to ask investigative questions, keep scammers engaged, and extract phone numbers, UPI IDs, bank accounts, phishing links, and other identifiers from the conversation in real-time.

## Tech Stack

- **Language**: Python 3.10+
- **Framework**: FastAPI + Uvicorn
- **AI Model**: OpenAI GPT-4o-mini (via OpenAI Async SDK)
- **Intelligence Extraction**: Custom regex engine (`extractor.py`)
- **Session Management**: In-memory session store
- **HTTP Client**: httpx (async)

## Architecture

```
POST /honeypot/message
        │
        ▼
session_manager.py    ← creates/retrieves per-session state
        │
        ▼
extractor.py          ← regex-based intel extraction from all messages
        │
        ▼
honeypot_agent.py     ← GPT-4o-mini generates Priya's reply
        │
        ▼
main.py               ← builds full scored response + submits final at turn 10
```

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/vagishaaa20/winners.git
   cd honeypot-api
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your keys
   ```

5. **Run the application**
   ```bash
   uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Endpoint

- **URL**: `https://your-deployed-url.com/honeypot/message`
- **Method**: POST
- **Authentication**: `x-api-key` header

### Request Format
```json
{
  "sessionId": "uuid-v4-string",
  "message": {
    "sender": "scammer",
    "text": "URGENT: Your SBI account has been compromised...",
    "timestamp": "2025-02-11T10:30:00Z"
  },
  "conversationHistory": [],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
```

### Response Format
```json
{
  "status": "success",
  "reply": "Arre, I am very worried now. Can you please give me your employee ID?",
  "sessionId": "uuid-v4-string",
  "scamDetected": true,
  "totalMessagesExchanged": 3,
  "engagementDurationSeconds": 245,
  "extractedIntelligence": {
    "phoneNumbers": ["+91-9876543210"],
    "bankAccounts": ["123456789012"],
    "upiIds": ["scammer@fakebank"],
    "phishingLinks": ["http://fake-kyc-site.com"],
    "emailAddresses": ["fraud@fake.com"],
    "caseIds": ["REF-2024-9876"],
    "policyNumbers": [],
    "orderIds": []
  },
  "agentNotes": "Financial Fraud scam detected. Red flags: 5...",
  "scamType": "Financial Fraud",
  "confidenceLevel": "High"
}
```

## Approach

### Honeypot Strategy
The agent plays "Priya Sharma", a 35-year-old school teacher from Pune — non-technical, mildly anxious, and cooperative enough to keep the scammer engaged without giving away any real information.

### Scam Detection
All conversations are treated as scam scenarios (the evaluation system only sends scam traffic). Scam type is classified dynamically using keyword scoring across 7 scam categories: Financial Fraud, Phishing, Identity Theft, Romance Scam, Lottery Scam, Tech Support, and Investment Scam.

### Intelligence Extraction
A custom regex engine (`extractor.py`) runs on every message in real-time to extract:
- Phone numbers (Indian formats: +91, 10-digit, with/without dashes)
- Bank account numbers (9–18 digit strings, deduplicated from phone numbers)
- UPI IDs (`localpart@handle` patterns not matching real email TLDs)
- Phishing links (http/https URLs and www. prefixed links)
- Email addresses (with valid TLDs)
- Case/Reference/Ticket IDs (alphanumeric with contextual keywords)
- Policy numbers and Order IDs

### Conversation Quality
The agent follows a turn-by-turn elicitation strategy:
- **Turn 1–2**: Ask for name and department
- **Turn 3–4**: Request employee ID for verification
- **Turn 5–6**: Ask for callback phone number
- **Turn 7–8**: Request official email or website
- **Turn 9–10**: Ask for case/reference ID for records

Context-sensitive overrides trigger whenever links, OTPs, fees, or UPI IDs are mentioned.

### Engagement Maximization
- Sessions are maintained for up to 10 turns
- Final intelligence report auto-submits after turn 10
- Duration is tracked from session creation
- Replies always end with a question to prompt scammer responses

## Environment Variables

```env
HONEYPOT_API_KEY=your-secret-api-key
OPENAI_API_KEY=sk-your-openai-key
```

See `.env.example` for template.

## Health Check

```
GET /health
→ {"status": "ok"}
```
