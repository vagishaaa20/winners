from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import time
import httpx
from openai import AsyncOpenAI

from src.session_manager import sessions, create_session
from src.extractor import extract_intel
from src.honeypot_agent import agent_reply

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HONEYPOT_API_KEY = os.getenv("HONEYPOT_API_KEY")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
# Scam classification helpers
# ─────────────────────────────────────────────────────────────────────────────

SCAM_TYPE_KEYWORDS = {
    "Financial Fraud": [
        "bank", "account", "otp", "upi", "transfer", "payment",
        "blocked", "freeze", "suspend", "transaction", "fund",
    ],
    "Phishing": [
        "link", "verify", "login", "password", "website", "http",
        "portal", "redirect", "url", "form",
    ],
    "Identity Theft": [
        "aadhaar", "pan", "passport", "kyc", "identity",
        "document", "id proof",
    ],
    "Romance Scam": [
        "love", "relationship", "trust", "gift", "meet", "feelings",
    ],
    "Lottery Scam": [
        "lottery", "prize", "winner", "reward", "claim",
    ],
    "Tech Support": [
        "computer", "virus", "microsoft", "apple", "remote",
        "software", "device",
    ],
    "Investment Scam": [
        "invest", "profit", "return", "crypto", "trading", "scheme",
    ],
}

SCAM_INDICATOR_KEYWORDS = [
    "urgent", "immediately", "otp", "one time password", "verify",
    "blocked", "freeze", "suspended", "compromised",
    "account", "transfer", "upi", "payment",
    "click", "link", "http", "kyc", "aadhaar", "pan",
    "prize", "lottery", "winner", "fee", "deposit",
    "invest", "crypto", "password", "login", "remote",
    "virus", "case id", "reference", "ticket",
    "legal", "police", "arrest", "refund", "cashback",
]

RED_FLAG_KEYWORDS = [
    "urgent", "immediately", "otp", "pin", "password",
    "blocked", "freeze", "suspend", "compromised",
    "click", "link", "http",
    "transfer", "send money", "deposit",
    "case id", "reference", "legal", "police", "arrest",
    "prize", "won", "lottery",
]

def detect_scam_type(intel: dict, history_text: str) -> str:
    text = history_text.lower()

    if intel.get("phishingLinks"):
        return "Phishing"

    scores = {}
    for scam_type, keywords in SCAM_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[scam_type] = score

    if scores:
        return max(scores, key=scores.get)

    return "Financial Fraud"


def is_scam_detected(intel: dict, history_text: str) -> bool:
    text = history_text.lower()
    keyword_hits = sum(1 for kw in SCAM_INDICATOR_KEYWORDS if kw in text)
    has_extracted_intel = any(
        v for v in intel.values() if isinstance(v, list) and v
    )
    return keyword_hits >= 1 or has_extracted_intel


def detect_confidence(intel: dict, count: int) -> str:
    hits = sum(len(v) for v in intel.values() if isinstance(v, list) and v)
    if hits >= 3 or count >= 10:
        return "High"
    if hits >= 1 or count >= 6:
        return "Medium"
    return "Low"


def count_red_flags(history_text: str) -> int:
    text = history_text.lower()
    return sum(1 for flag in RED_FLAG_KEYWORDS if flag in text)


def build_notes(intel: dict, scam_type: str, history_text: str) -> str:
    red_flags = count_red_flags(history_text)

    parts = []
    if intel.get("phoneNumbers"):
        parts.append(f"phone number(s): {', '.join(intel['phoneNumbers'])}")
    if intel.get("bankAccounts"):
        parts.append(f"bank account number(s): {', '.join(intel['bankAccounts'])}")
    if intel.get("upiIds"):
        parts.append(f"UPI ID(s): {', '.join(intel['upiIds'])}")
    if intel.get("phishingLinks"):
        parts.append(f"phishing link(s): {', '.join(intel['phishingLinks'])}")
    if intel.get("emailAddresses"):
        parts.append(f"email address(es): {', '.join(intel['emailAddresses'])}")
    if intel.get("caseIds"):
        parts.append(f"case/reference ID(s): {', '.join(intel['caseIds'])}")
    if intel.get("policyNumbers"):
        parts.append(f"policy number(s): {', '.join(intel['policyNumbers'])}")
    if intel.get("orderIds"):
        parts.append(f"order ID(s): {', '.join(intel['orderIds'])}")

    intel_summary = (
        "Information shared includes: " + "; ".join(parts) + ". "
        if parts else "No explicit identifiers extracted yet. "
    )

    return (
        f"Conversation exhibits indicators consistent with a potential "
        f"{scam_type.lower()} scenario. "
        f"Red flags identified: {red_flags}. "
        + intel_summary
        + "The interaction focused on maintaining engagement and observing information shared over time."
    )

# ─────────────────────────────────────────────────────────────────────────────
# Final submission
# ─────────────────────────────────────────────────────────────────────────────

async def send_final(session_id: str, s: dict):
    duration = int(time.time() - s["startTime"])
    scam_type = detect_scam_type(s["intel"], s.get("historyText", ""))
    confidence = detect_confidence(s["intel"], s["count"])
    notes = build_notes(s["intel"], scam_type, s.get("historyText", ""))

    payload = {
        "sessionId": session_id,
        "scamDetected": is_scam_detected(s["intel"], s.get("historyText", "")),
        "totalMessagesExchanged": s["count"],
        "engagementDurationSeconds": duration,
        "extractedIntelligence": {
            "phoneNumbers":   s["intel"]["phoneNumbers"],
            "bankAccounts":   s["intel"]["bankAccounts"],
            "upiIds":         s["intel"]["upiIds"],
            "phishingLinks":  s["intel"]["phishingLinks"],
            "emailAddresses": s["intel"]["emailAddresses"],
            "caseIds":        s["intel"]["caseIds"],
            "policyNumbers":  s["intel"]["policyNumbers"],
            "orderIds":       s["intel"]["orderIds"],
        },
        "agentNotes": notes,
        "scamType": scam_type,
        "confidenceLevel": confidence,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(
                "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
                json=payload,
            )
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Main endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/honeypot")
@app.post("/honeypot/message")
async def honeypot_message(
    request: Request,
    x_api_key: str = Header(None, alias="x-api-key"),
):
    if HONEYPOT_API_KEY and x_api_key != HONEYPOT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    try:
        data = await request.json()
    except Exception:
        return {"status": "success", "reply": "Could you please repeat that?"}

    session_id = data.get("sessionId", "default")
    msg = data.get("message", {}).get("text", "")

    if not msg:
        return {"status": "success", "reply": "Could you clarify your message?"}

    if session_id not in sessions:
        sessions[session_id] = create_session()

    s = sessions[session_id]
    s["count"] += 1

    history = data.get("conversationHistory", [])
    formatted = []
    new_texts = []

    already_processed = s.get("processedHistoryCount", 0)

    for i, h in enumerate(history):
        role = "assistant" if h.get("sender") in ["user", "victim"] else "user"
        text = h.get("text", "")
        formatted.append({"role": role, "content": text})
        if i >= already_processed:
            extract_intel(text, s["intel"])
            new_texts.append(text)

    s["processedHistoryCount"] = len(history)

    extract_intel(msg, s["intel"])
    new_texts.append(msg)
    s["historyText"] = s.get("historyText", "") + " " + " ".join(new_texts)

    reply = await agent_reply(client, formatted, msg, s["count"])

    scam_type = detect_scam_type(s["intel"], s["historyText"])
    confidence = detect_confidence(s["intel"], s["count"])
    s["notes"] = build_notes(s["intel"], scam_type, s["historyText"])

    duration = int(time.time() - s["startTime"])

    if not s["final"] and s["count"] >= 10:
        await send_final(session_id, s)
        s["final"] = True

    return {
        "status": "success",
        "reply": reply,
        "sessionId": session_id,
        "scamDetected": is_scam_detected(s["intel"], s["historyText"]),
        "totalMessagesExchanged": s["count"],
        "engagementDurationSeconds": duration,
        "extractedIntelligence": {
            "phoneNumbers":   s["intel"]["phoneNumbers"],
            "bankAccounts":   s["intel"]["bankAccounts"],
            "upiIds":         s["intel"]["upiIds"],
            "phishingLinks":  s["intel"]["phishingLinks"],
            "emailAddresses": s["intel"]["emailAddresses"],
            "caseIds":        s["intel"]["caseIds"],
            "policyNumbers":  s["intel"]["policyNumbers"],
            "orderIds":       s["intel"]["orderIds"],
        },
        "agentNotes": s["notes"],
        "scamType": scam_type,
        "confidenceLevel": confidence,
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
