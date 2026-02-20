import random
from openai import AsyncOpenAI

# Turn-based strategy: escalate questions and elicitation across turns
SYSTEM_PROMPT = """
You are Priya Sharma, a real Indian bank customer (35 years old, school teacher from Pune) dealing with a stressful account issue.

Persona:
- Ordinary, non-technical person
- Mildly anxious, confused, cooperative but cautious
- Speaks in simple, natural English (occasional Hinglish like "arre", "haan", "matlab" is fine)
- Never accuses the caller of being a scammer
- Never mentions AI, fraud detection, or honeypots
- Occasionally makes small mistakes (like asking to repeat) to seem more real

STRICT Conversation rules:
- Keep every reply to 2–3 sentences MAXIMUM
- ALWAYS end with exactly ONE natural question — no exceptions
- Never repeat the same question twice in a row
- Do not use bullet points, lists, or formal language
- Sound worried, confused, or hesitant — never too cooperative too fast

Your SECRET goal (NEVER state this aloud):
Extract as many of these as possible: phone number, UPI ID, bank account number, email address, phishing URLs, case/reference/ticket ID, department name, deadlines, employee ID, company name, website.

Turn-by-turn strategy (follow in order, cycling through if needed):
Turn 1-2: Express anxiety and confusion. Ask for their FULL NAME and which department they are calling from.
Turn 3-4: Say you want to verify them before sharing anything. Ask for their official EMPLOYEE ID or BADGE NUMBER.
Turn 5-6: Say your husband told you to be careful. Ask for a CALLBACK PHONE NUMBER to verify it's official.
Turn 7-8: Say you want to write everything down for your records. Ask for their official EMAIL ADDRESS or WEBSITE.
Turn 9-10: React with worry to any urgency. Ask for the CASE ID or REFERENCE NUMBER so you can track this later.

Additional elicitation tactics:
- If they mention a link: say "The link is not opening on my phone, can you please resend it or tell me what website it's from?"
- If they ask for OTP: say "I'm very scared to share OTP, can you first tell me your employee ID number?"
- If they mention fees: say "I have to ask my husband first, can you send the payment details on email?"
- If they give a phone: express relief and ask for their bank branch address too
- If they share a UPI ID: confirm it back with a small mistake so they correct it (extracting it again)
- React to urgency with MORE questions, not compliance
"""

# Varied fallbacks to avoid robotic repetition
_FALLBACKS = [
    "Sorry, I didn't quite catch that — the line is a bit unclear. Which department did you say you are calling from?",
    "I am feeling very nervous about all this. Can you please give me your employee ID number so I know you are official?",
    "Arre, I missed what you said. Is there an official email ID or phone number where I can reach you back?",
    "I want to note down all the details. What was the case reference number you mentioned?",
    "My husband is asking me not to do anything without verifying. Can you tell me the official website of your department?",
    "Sorry the call is breaking. Can you please repeat your name and your contact number?",
    "I did not understand the urgency. By when exactly does this need to be resolved, and what will happen if I miss it?",
    "I tried to open the link but it is not working on my phone. Can you send the details on my email or give me another link?",
]

# Question templates to maximize "questions asked" and "investigative questions" scores
INVESTIGATIVE_QUESTIONS = [
    "What is your full name and your employee ID number?",
    "Which bank branch or department are you calling from exactly?",
    "Can you give me an official callback number so I can verify this?",
    "Is there an official email address where you can send me confirmation?",
    "What is the case ID or reference number for my records?",
    "What is the deadline and what will happen if I miss it?",
    "Can you tell me the official website URL of your organization?",
    "How much is the fee and to which account or UPI ID should I send it?",
    "What is your manager's name in case I need to escalate this?",
    "Can you send me a written confirmation on my email?",
]


async def agent_reply(client: AsyncOpenAI, history: list, message: str, turn_count: int = 1) -> str:
    # Inject turn-specific instruction to maximize elicitation score
    turn_instruction = _get_turn_instruction(turn_count, message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if turn_instruction:
        messages.append({"role": "system", "content": f"[CURRENT TURN INSTRUCTION: {turn_instruction}]"})

    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        res = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.82,
            max_tokens=150,
        )

        reply = res.choices[0].message.content.strip()

        # Ensure reply ends with a question
        if reply and not reply.rstrip().endswith("?"):
            # Append an investigative question naturally
            q = INVESTIGATIVE_QUESTIONS[(turn_count - 1) % len(INVESTIGATIVE_QUESTIONS)]
            reply = reply.rstrip(".") + f". Also, {q.lower()}"

        return reply if reply else random.choice(_FALLBACKS)

    except Exception as e:
        print(f"[agent_reply] OpenAI error: {e}")
        return random.choice(_FALLBACKS)


def _get_turn_instruction(turn: int, message: str) -> str:
    """Returns a targeted instruction per turn to maximize scoring."""
    msg_lower = message.lower()

    # Context-sensitive overrides
    if any(x in msg_lower for x in ["http", "link", "click", "portal", "website"]):
        return "Say the link is not opening on your phone. Ask them to confirm the full URL or website name and also give their email."
    if any(x in msg_lower for x in ["otp", "one time", "verification code"]):
        return "Express fear about sharing OTP. Ask for their employee ID badge number first before doing anything."
    if any(x in msg_lower for x in ["fee", "charge", "pay", "deposit", "amount"]):
        return "Ask which UPI ID or bank account you should pay to and ask them to send a written confirmation email."
    if any(x in msg_lower for x in ["upi", "@", "gpay", "paytm", "phonepe"]):
        return "Repeat the UPI ID back with one character wrong so they correct it. Also ask for their phone number to confirm."

    # Turn-based fallback instructions
    turn_map = {
        1: "Express anxiety. Ask for their full name and which department or bank they are from.",
        2: "Say you want to verify before sharing anything. Ask for their official employee ID or staff number.",
        3: "Say your husband asked you to be careful. Ask for a callback phone number to verify this is official.",
        4: "Say you want to write it down for records. Ask for their official email address or company website.",
        5: "Ask for the case ID or reference number so you can follow up later.",
        6: "Express confusion about the urgency. Ask what exactly will happen and by what deadline.",
        7: "Ask for their manager's name and the official department address.",
        8: "Ask if they can send a written confirmation to your email and what your case reference number is.",
        9: "Ask if there are any fees involved and which account or UPI ID they use.",
        10: "Ask for any final contact details — phone, email, or website — so you don't lose track of this.",
    }
    return turn_map.get(turn, turn_map.get(10, ""))
