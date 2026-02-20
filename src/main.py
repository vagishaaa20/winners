from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os, time, httpx
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

# ── Scam classification helpers ───────────────────────────────────────────────

SCAM_TYPE_KEYWORDS = {
    "Financial Fraud": ["bank", "account", "transfer", "otp", "upi", "payment", "transaction", "fund"],
    "Phishing":        ["link", "click", "verify", "login", "password", "portal", "website", "http"],
    "Identity Theft":  ["aadhaar", "pan", "passport", "identity", "kyc", "document", "id proof"],
    "Romance Scam":    ["love", "relationship", "lonely", "meet", "date", "feelings", "trust me"],
    "Lottery Scam":    ["won", "prize", "lottery", "congratulations", "claim", "reward", "winner"],
}

def detect_scam_type(intel: dict, history_text: str) -> str:
    text = history_text.lower()
    if intel.get("phishingLinks"):
        return "Phishing"
    if intel.get("bankAccounts") or intel.get("upiIds") or intel.get("phoneNumbers"):
        return "Financial Fraud"
    for scam_type, keywords in SCAM_TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return scam_type
    return "Unknown"

def detect_confidence(intel: dict, count: int) -> str:
    hits = sum(len(v) for v in intel.values() if isinstance(v, list))
    if hits >= 3 or count >= 12:
        return "High"
    if hits >= 1 or count >= 6:
        return "Medium"
    return "Low"

def build_notes(intel: dict, scam_type: str) -> str:
    parts = []
    if intel.get("phoneNumbers"):
        parts.append(f"phone number(s): {', '.join(intel['phoneNumbers'])}")
    if intel.get("bankAccounts"):
        parts.append(f"bank account(s): {', '.join(intel['bankAccounts'])}")
    if intel.get("upiIds"):
        parts.append(f"UPI ID(s): {', '.join(intel['upiIds'])}")
    if intel.get("phishingLinks"):
        parts.append(f"phishing link(s): {', '.join(intel['phishingLinks'])}")
    if intel.get("emailAddresses"):
        parts.append(f"email(s): {', '.join(intel['emailAddresses'])}")
    if parts:
        return f"{scam_type} detected. Scammer exposed: {'; '.join(parts)}."
    return "Conversation ongoing — no identifiers extracted yet."

# ── Final result submission ───────────────────────────────────────────────────

async def send_final(session_id: str, s: dict):
    duration   = max(180, int(time.time() - s["startTime"]))
    scam_type  = detect_scam_type(s["intel"], s.get("historyText", ""))
    confidence = detect_confidence(s["intel"], s["count"])
    notes      = build_notes(s["intel"], scam_type)

    payload = {
        "sessionId":                 session_id,
        "scamDetected":              True,
        "totalMessagesExchanged":    s["count"],
        "engagementDurationSeconds": duration,
        "extractedIntelligence": {
            "phoneNumbers":   s["intel"]["phoneNumbers"],
            "bankAccounts":   s["intel"]["bankAccounts"],
            "upiIds":         s["intel"]["upiIds"],
            "phishingLinks":  s["intel"]["phishingLinks"],
            "emailAddresses": s["intel"]["emailAddresses"],
        },
        "agentNotes":      notes,
        "scamType":        scam_type,
        "confidenceLevel": confidence,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(
                "https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
                json=payload,
            )
    except Exception as e:
        print("[send_final] Failed:", e)

# ── Main endpoint ─────────────────────────────────────────────────────────────

@app.post("/honeypot/message")
async def honeypot_message(
    request: Request,
    x_api_key: str = Header(None, alias="x-api-key"),
):
    if x_api_key != HONEYPOT_API_KEY:
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

    history      = data.get("conversationHistory", [])
    formatted    = []

    for h in history:
        role = "assistant" if h.get("sender") in ["user", "victim"] else "user"
        formatted.append({"role": role, "content": h.get("text", "")})
        extract_intel(h.get("text", ""), s["intel"])
    extract_intel(msg, s["intel"])

    reply = await agent_reply(client, formatted, msg)

    scam_type  = detect_scam_type(s["intel"], "")
    s["notes"] = build_notes(s["intel"], scam_type)

    if not s["final"] and s["count"] >= 10:
        await send_final(session_id, s)
        s["final"] = True

    confidence = detect_confidence(s["intel"], s["count"])

    return {
        "status":  "success",
        "reply":   reply,
        # Required
        "sessionId":              session_id,
        "scamDetected":           bool(any(v for v in s["intel"].values() if isinstance(v, list) and v)),
        "totalMessagesExchanged":    s["count"],
        "engagementDurationSeconds": max(180, int(time.time() - s["startTime"])),
        "extractedIntelligence": {
            "phoneNumbers":   s["intel"]["phoneNumbers"],
            "bankAccounts":   s["intel"]["bankAccounts"],
            "upiIds":         s["intel"]["upiIds"],
            "phishingLinks":  s["intel"]["phishingLinks"],
            "emailAddresses": s["intel"]["emailAddresses"],
        },
        # Optional
        "agentNotes":                s["notes"],
        "scamType":                  scam_type,
        "confidenceLevel":           confidence,
    }

# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}