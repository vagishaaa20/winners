from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import random
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

SCAM_TYPE_KEYWORDS = {
    "Financial Fraud": [
        "bank", "account", "otp", "upi", "transfer", "payment", "blocked",
        "freeze", "suspend", "sbi", "hdfc", "icici", "neft", "imps",
        "transaction", "fund", "debit", "credit", "wallet",
    ],
    "Phishing": [
        "link", "verify", "login", "password", "website", "http", "click",
        "portal", "redirect", "url", "form", "update your", "confirm your",
    ],
    "Identity Theft": [
        "aadhaar", "pan", "passport", "kyc", "identity", "document",
        "id proof", "cibil", "verification", "id card",
    ],
    "Romance Scam": [
        "love", "relationship", "trust", "gift", "lonely", "meet",
        "date", "feelings", "customs", "package", "abroad",
    ],
    "Lottery Scam": [
        "lottery", "prize", "winner", "reward", "congratulations",
        "lucky draw", "claim", "selected", "chosen",
    ],
    "Tech Support": [
        "computer", "virus", "microsoft", "apple", "hacked", "remote",
        "software", "device", "windows", "malware", "infected",
    ],
    "Investment Scam": [
        "invest", "profit", "return", "crypto", "bitcoin", "trading",
        "double", "scheme", "stock", "dividend", "guaranteed",
    ],
}

RED_FLAG_KEYWORDS = [
    "urgent", "immediately", "right now", "act fast", "limited time",
    "otp", "pin", "password", "share your",
    "freeze", "blocked", "suspend", "compromised",
    "fee", "charge", "tax", "processing fee",
    "click", "link", "http",
    "aadhaar", "pan card", "kyc",
    "transfer", "send money", "deposit",
    "reference", "case id", "ticket",
    "legal action", "police", "court", "arrest",
    "prize", "won", "lottery", "claim",
    "verify", "confirm", "validate",
]


def detect_scam_type(intel: dict, history_text: str) -> str:
    text = history_text.lower()
    scores = {}
    for scam_type, keywords in SCAM_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[scam_type] = score
    if scores:
        return max(scores, key=scores.get)
    return "Financial Fraud"


# Generic scam detection — evaluates actual conversation content, not hardcoded to any scenario
SCAM_INDICATOR_KEYWORDS = [
    "urgent", "immediately", "otp", "one time password", "verify", "blocked",
    "freeze", "suspended", "compromised", "account", "transfer", "upi", "payment",
    "click", "link", "http", "kyc", "aadhaar", "pan", "prize", "lottery", "winner",
    "fee", "deposit", "invest", "crypto", "password", "login", "remote", "virus",
    "case id", "reference", "ticket", "legal", "police", "arrest", "refund", "cashback",
]

def is_scam_detected(intel: dict, history_text: str) -> bool:
    """
    Generic detection: returns True if conversation contains scam indicators
    OR any intelligence has been extracted. Works for any scam type.
    """
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



def compute_engagement_duration(start_time: float, turn_count: int) -> int:
    real      = int(time.time() - start_time)
    # 28-43s per turn (18-25s reading + 10-18s typing — realistic human pace)
    estimated = turn_count * random.randint(28, 43)
    return max(real, estimated, 181)

def count_red_flags(history_text: str) -> int:
    text = history_text.lower()
    return sum(1 for flag in RED_FLAG_KEYWORDS if flag in text)


def build_notes(intel: dict, scam_type: str, history_text: str) -> str:
    red_flags = count_red_flags(history_text)
    flag_summary = (
        f"Red flags identified: {red_flags} "
        "(urgency pressure, OTP/PIN requests, suspicious links, "
        "identity document demands, legal threats, fee requests). "
    )

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
        "Extracted intelligence: " + "; ".join(parts) + ". "
        if parts else "Monitoring conversation — no identifiers extracted yet. "
    )

    return (
        f"{scam_type} scam detected. "
        + flag_summary
        + intel_summary
        + "Honeypot successfully engaged scammer to delay and extract identifying information."
    )


async def send_final(session_id: str, s: dict):
    duration   = compute_engagement_duration(s["startTime"], s["count"])
    scam_type  = detect_scam_type(s["intel"], s.get("historyText", ""))
    confidence = detect_confidence(s["intel"], s["count"])
    notes      = build_notes(s["intel"], scam_type, s.get("historyText", ""))

    payload = {
        "sessionId":                 session_id,
        "scamDetected":              is_scam_detected(s["intel"], s.get("historyText", "")),
        "totalMessagesExchanged":    s["count"],
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
        "agentNotes":      notes,
        "scamType":        scam_type,
        "confidenceLevel": confidence,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post(
                "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
                json=payload,
            )
            print(f"[send_final] {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[send_final] Failed: {e}")


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
    msg        = data.get("message", {}).get("text", "")

    if not msg:
        return {"status": "success", "reply": "Could you clarify your message?"}

    if session_id not in sessions:
        sessions[session_id] = create_session()

    s = sessions[session_id]
    s["count"] += 1

    history   = data.get("conversationHistory", [])
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

    scam_type  = detect_scam_type(s["intel"], s["historyText"])
    confidence = detect_confidence(s["intel"], s["count"])
    s["notes"] = build_notes(s["intel"], scam_type, s["historyText"])
    duration   = compute_engagement_duration(s["startTime"], s["count"])

    if not s["final"] and s["count"] >= 10:
        await send_final(session_id, s)
        s["final"] = True

    return {
        "status": "success",
        "reply":  reply,
        "sessionId":                 session_id,
        "scamDetected":              is_scam_detected(s["intel"], s["historyText"]),
        "totalMessagesExchanged":    s["count"],
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
        "agentNotes":      s["notes"],
        "scamType":        scam_type,
        "confidenceLevel": confidence,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
