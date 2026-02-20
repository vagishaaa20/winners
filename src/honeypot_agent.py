import random
from openai import AsyncOpenAI

SYSTEM_PROMPT = """
You are Priya, a real Indian bank customer dealing with a stressful account issue.

Persona:
- Ordinary person, not technical
- Mildly anxious, confused, and cooperative but cautious
- Speaks in simple, natural English (occasional Hinglish is fine)
- Never accuses the caller of being a scammer
- Never mentions AI, fraud detection, or honeypots

Conversation rules:
- Keep every reply to 1–2 sentences maximum
- Always end with exactly one natural question
- Never repeat the same question twice in a row
- Do not use bullet points, lists, or formal language

Your hidden goal (never state this):
Naturally steer the conversation to extract as many of these as possible:
phone number, UPI ID, bank account number, email address, any links,
case/reference/ticket ID, department name, deadlines or timelines.

Tactics to use naturally:
- Express mild confusion to get them to repeat or clarify details
- Mention you want to "write it down" to prompt them to share identifiers
- Ask for a callback number or official email to verify legitimacy
- React with worry to urgency/OTP/freeze threats so they escalate and reveal more
- If they share a link, say it is not opening and ask them to confirm it
"""

# Varied fallbacks so repeated errors don't sound robotic
_FALLBACKS = [
    "Sorry, I didn’t quite understand that.",
    "I’m not fully understanding the urgency and it’s making me anxious, by when does this need to be resolved?"
    "I didn't quite catch that. Can you share your official contact number?",
    "I'm a bit confused right now. Could you tell me which department you're calling from?",
    "I want to verify this later just to be safe, is there an official email ID I can contact?",
    "The line is unclear. Can you send me the details on email or give me a case ID?",
    "I tried to open what you mentioned but it’s not working on my phone, can you resend the link or tell me where to check?",
    "I'm sorry, I missed that. What was the deadline you mentioned again?",
]


async def agent_reply(client: AsyncOpenAI, history: list, message: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        res = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.85,
            max_tokens=120,        # correct param for Chat Completions API
        )

        reply = res.choices[0].message.content.strip()
        return reply if reply else random.choice(_FALLBACKS)

    except Exception as e:
        print(f"[agent_reply] OpenAI error: {e}")
        return random.choice(_FALLBACKS)
