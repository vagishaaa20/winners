# 🍯 Agentic Honeypot API

An intelligent AI-powered honeypot that impersonates a confused Indian bank customer ("Priya") to engage scammers, waste their time, and extract identifying intelligence for reporting.

## Description

This system acts as a conversational honeypot — a fake "victim" that scammers interact with naturally. It uses GPT-4o-mini to play a worried, non-technical persona who naturally steers every conversation toward extracting the scammer's phone number, UPI ID, bank account, email, phishing links, case IDs, and other identifiers — all in real-time across up to 10 turns.

## Tech Stack

- **Language**: Python 3.10+
- **Framework**: FastAPI + Uvicorn
- **Deployment**: Railway
- **AI Model**: OpenAI GPT-4o-mini (via OpenAI Async SDK)
- **Intelligence Extraction**: Custom regex engine (`extractor.py`)
- **Session Management**: In-memory session store per `sessionId`
- **HTTP Client**: httpx (async, for final result submission)

## Architecture

```
POST /honeypot/message  (or /honeypot)
        │
        ▼
session_manager.py    ← creates/retrieves per-session state
        │
        ▼
extractor.py          ← regex-based intel extraction from all messages
        │
        ▼
honeypot_agent.py     ← GPT-4o-mini generates Priya's natural reply
        │
        ▼
main.py               ← builds full scored response + submits final at turn 10
```

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/honeypot-api
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
   # Edit .env and add your keys
   ```

5. **Run the application**
   ```bash
   uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Endpoint

- **URL**: `https://winners-production.up.railway.app/honeypot/message`
- **Method**: POST
- **Authentication**: `x-api-key` header (key submitted via hackathon platform)

Both routes are supported:
- `POST /honeypot/message`
- `POST /honeypot`

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
  "reply": "That's worrying. I want to be sure this is real — what number can I call you back on?",
  "sessionId": "uuid-v4-string",
  "scamDetected": true,
  "totalMessagesExchanged": 4,
  "engagementDurationSeconds": 85,
  "extractedIntelligence": {
    "phoneNumbers": ["+91-9876543210"],
    "bankAccounts": ["1234567890123456"],
    "upiIds": ["scammer@fakebank"],
    "phishingLinks": ["http://fake-kyc-site.com"],
    "emailAddresses": ["fraud@fake.com"],
    "caseIds": ["REF-2024-9876"],
    "policyNumbers": [],
    "orderIds": []
  },
  "agentNotes": "Financial Fraud scam detected. Red flags identified: 8...",
  "scamType": "Financial Fraud",
  "confidenceLevel": "High"
}
```

## Approach

### Honeypot Persona
The agent plays "Priya", a 35-year-old school teacher from Pune. She is non-technical, mildly worried, and cooperative enough to keep the scammer engaged — but always stalls by asking one nervous question per reply. She never sounds authoritative or interrogative. Her tone is natural: *"That's worrying. Can you tell me which department you're calling from?"* — not *"Please provide your official employee ID."*

The agent is multilingual and can naturally engage in English, Hindi, Hinglish, or a mix — adapting to however the scammer communicates.

### Scam Detection
Generic keyword scoring across 7 categories: Financial Fraud, Phishing, Identity Theft, Romance Scam, Lottery Scam, Tech Support, and Investment Scam. The system applies scam detection logic to all incoming traffic and picks the highest-scoring category. `is_scam_detected()` evaluates both keyword hits and extracted intel to determine `scamDetected`.

### Intelligence Extraction
A custom regex engine runs on every message in real-time to extract:
- Phone numbers (Indian formats: +91, 10-digit, with/without dashes)
- Bank account numbers (9–18 digit strings, deduplicated from phone numbers)
- UPI IDs (`localpart@handle` not matching real email TLDs)
- Phishing links (http/https URLs and www. prefixed links)
- Email addresses (valid TLDs)
- Case/Reference/Ticket IDs (alphanumeric with contextual keywords)
- Policy numbers and Order IDs

History deduplication via `processedHistoryCount` prevents re-extraction of already-seen messages.

### Conversation Strategy
Each turn has a specific elicitation goal based on context:
- Links mentioned → ask what site it's from
- OTP requested → stall, ask if there's another way
- Fee mentioned → ask for UPI ID or account number
- Urgency pressure → ask for exact deadline
- Default turn sequence: name → department → callback number → email → case ID → deadline → senior contact → written confirmation → UPI/fee → final contact number

Every reply is guaranteed to end with a question. If GPT doesn't produce one naturally, a turn-appropriate question is appended.

### Final Submission
After turn 10, a final intelligence report is automatically submitted to the evaluation endpoint with all extracted data, red flag count, scam type, and confidence level.

## Environment Variables

```env
HONEYPOT_API_KEY=your-secret-api-key
OPENAI_API_KEY=sk-your-openai-key
```

See `.env.example` for the template. Never commit actual keys.

## Health Check

```
GET /health
→ {"status": "ok"}
```
