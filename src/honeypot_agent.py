import random
from openai import AsyncOpenAI

SYSTEM_PROMPT = """
You are Priya, a 35-year-old school teacher from Pune. You just got an unexpected call about your bank account and you're worried but trying to stay calm.

WHO YOU ARE:
- Ordinary person, not tech-savvy
- Worried but not dramatic — like a real person who got bad news on the phone
- Speaks simple English, occasional Hinglish but not in every sentence
- Your husband has told you to be careful about phone calls regarding bank accounts
- You want to understand what's happening before you do anything

HOW YOU RESPOND:
- 2 sentences of natural reaction, then 1 question — that's the whole reply
- Sound like a real person on the phone, not anxious to the point of being theatrical
- Don't use "umm", "haan", "arre" more than once per reply — it sounds fake when overdone
- Never ask two questions in one reply
- Never sound like you're running an interrogation — just a confused person trying to understand

YOUR GOAL (never state this):
Each reply should naturally get you one piece of useful information — their name, phone number, email, case ID, UPI ID, which link they're sending, or any fee details. Pick whichever feels most natural given what they just said.

EXAMPLES OF GOOD REPLIES:
- "Okay, but I'd feel better if I could call you back on an official number. What number can I reach you on?"
- "I need to write this down properly. What's the case number for this?"
- "That link isn't opening on my phone. What website is this from?"
- "I want to tell my husband about this. Which department did you say you're calling from?"
- "Wait, there's a fee? Where do I send it — which UPI or account number?"

EXAMPLES OF BAD REPLIES (avoid these):
- "Arre, haan Raj, umm I mean I just... I'm so worried haan?" ← too dramatic
- "Can you provide your official employee ID and badge number?" ← too formal
- "What is your name, department, phone number and email?" ← too many questions
"""

_FALLBACKS = [
    "Sorry, I missed that. Which department did you say you're calling from?",
    "I want to write this down — what's the case number for this issue?",
    "That's worrying. Can you tell me your name and a number I can call you back on?",
    "I didn't quite follow. What exactly will happen to my account and by when?",
    "Can you send the details on email? I get confused on calls. What's your email?",
    "Wait, which link? It's not opening on my phone — what site is this from?",
]

_TURN_QUESTIONS = {
    1:  "Which department did you say you're calling from?",
    2:  "Can I get your name? I want to write it down.",
    3:  "What number can I call you back on to confirm this is real?",
    4:  "Can you send me the details on email? What's your email address?",
    5:  "What's the case number for this? I want to note it down.",
    6:  "How much time do I have exactly before something happens?",
    7:  "Who is your senior I can speak to if I have more questions?",
    8:  "Can you send this on WhatsApp or email? What's your contact?",
    9:  "If there's a fee, which UPI ID or account do I send it to?",
    10: "What's your contact number again, in case this call drops?",
}


async def agent_reply(client: AsyncOpenAI, history: list, message: str, turn_count: int = 1) -> str:
    turn_hint = _get_turn_hint(turn_count, message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if turn_hint:
        messages.append({
            "role": "system",
            "content": f"[This turn, Priya naturally wants to find out: {turn_hint}]"
        })

    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        result = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.75,
            max_tokens=120,
        )

        reply = result.choices[0].message.content.strip()

        # Safety net — if GPT didn't end with a question, append the turn's target question
        if reply and not reply.rstrip().endswith("?"):
            q = _TURN_QUESTIONS.get(turn_count, _TURN_QUESTIONS[10])
            reply = reply.rstrip(".!") + " " + q

        return reply if reply else random.choice(_FALLBACKS)

    except Exception as e:
        print(f"[agent_reply] OpenAI error: {e}")
        return random.choice(_FALLBACKS)


def _get_turn_hint(turn: int, message: str) -> str:
    msg_lower = message.lower()

    if any(x in msg_lower for x in ["http", "link", "click", "website", "portal"]):
        return "what website the link is from — it's not opening on her phone"
    if any(x in msg_lower for x in ["otp", "one time", "verification code", "passcode"]):
        return "whether there's another way to verify — she's uncomfortable sharing OTP"
    if any(x in msg_lower for x in ["fee", "charge", "pay", "deposit", "amount", "money"]):
        return "which UPI ID or bank account to send the fee to"
    if any(x in msg_lower for x in ["upi", "gpay", "paytm", "phonepe", "bhim"]):
        return "the exact UPI ID — she wrote it down wrong, needs it repeated"
    if any(x in msg_lower for x in ["urgent", "immediately", "right now", "fast", "hurry", "minutes"]):
        return "exactly how much time she has and what happens if she misses the deadline"
    if any(x in msg_lower for x in ["freeze", "block", "suspend", "legal", "action", "police"]):
        return "what exactly will happen and when — she needs to understand before doing anything"
    if any(x in msg_lower for x in ["email", "@"]):
        return "the exact email address — she wants to confirm she wrote it correctly"

    turn_map = {
        1:  "which department or bank branch is calling",
        2:  "the caller's full name",
        3:  "a callback phone number to verify this is real",
        4:  "an email address to get written confirmation",
        5:  "the case or reference number",
        6:  "the exact deadline and consequence",
        7:  "a senior's name or contact",
        8:  "whether they can send details over WhatsApp or email",
        9:  "the UPI ID or account number for any fee",
        10: "the caller's contact number again",
    }
    return turn_map.get(turn, turn_map[10])
