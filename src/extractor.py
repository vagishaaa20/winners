import re


def add_unique(lst, items):
    for i in items:
        if i and i not in lst:
            lst.append(i)


_EMAIL_TLD = re.compile(r'\.(com|net|org|in|io|co|edu|gov|info|biz)', re.I)


def extract_intel(text: str, intel: dict):

    # ── EMAILS ────────────────────────────────────────────────────────────────
    # Standard emails with real TLDs
    emails = re.findall(r'\b[\w\.-]+@[\w\.-]+\.\w{2,}\b', text)
    real_emails = [e for e in emails if _EMAIL_TLD.search(e)]
    add_unique(intel["emailAddresses"], real_emails)
    email_set = set(e.lower() for e in intel["emailAddresses"])

    # FIX 1: context emails — scammer says "email me at x@y" where x@y has no TLD
    ctx_emails = re.findall(
        r'(?:email(?:ing)?|mail|send|contact|reach)[^.]{0,60}?\b([\w\.-]+@[\w\.-]+)\b',
        text, re.I
    )
    for e in ctx_emails:
        if e.lower() not in email_set and not _EMAIL_TLD.search(e):
            add_unique(intel["emailAddresses"], [e])
            email_set.add(e.lower())

    # ── PHONE NUMBERS ─────────────────────────────────────────────────────────
    raw_phones = re.findall(r'(?<![A-Za-z\d\-])(\+?\d[\d\-\s]{9,16})(?!\d)', text)
    clean_phones = []
    for p in raw_phones:
        digits = re.sub(r'\D', '', p)
        if 10 <= len(digits) <= 13:
            has_plus = p.strip().startswith('+')
            # FIX 2: +91-XXXXXXXXXX = 12 digits but is a phone, not a bank account
            if has_plus or not re.fullmatch(r'\d{12,18}', digits):
                clean_phones.append(p.strip())
    add_unique(intel["phoneNumbers"], clean_phones)

    # ── BANK ACCOUNTS ─────────────────────────────────────────────────────────
    accounts = re.findall(r'\b\d{12,18}\b', text)
    add_unique(intel["bankAccounts"], accounts)

    # ── UPI IDs ───────────────────────────────────────────────────────────────
    # Build local-part set from known emails to block variants like support@fakebank
    # when support@fakebank.com is already captured as a real email
    known_local_parts = set(e.split('@')[0].lower() for e in intel["emailAddresses"])

    raw_upi = re.findall(r'\b[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,}\b', text)
    for u in raw_upi:
        if u.lower() in email_set:
            continue
        if _EMAIL_TLD.search(u):
            continue
        if u.split('@')[0].lower() in known_local_parts:
            continue
        add_unique(intel["upiIds"], [u])

    # ── PHISHING LINKS ────────────────────────────────────────────────────────
    links = re.findall(r'https?://[^\s)\]>"\']+', text)
    clean_links = [l.rstrip(').,;"\'>]') for l in links]
    add_unique(intel["phishingLinks"], [l for l in clean_links if l])

    # ── CASE IDs ──────────────────────────────────────────────────────────────
    # FIX 3: Reference before Ref (longest first) + support "is" keyword
    raw_case = re.findall(
        r'(?:Case\s*Reference|Reference\s*(?:ID|No|Number)?|Case\s*(?:ID|No|Number)?|Ref\s*(?:ID|No|Number)?|Ticket\s*(?:ID|No|Number)?)\s*(?:is\s*)?[:\-#]?\s*([A-Z0-9][A-Z0-9\-]{4,})',
        text,
        re.I,
    )
    clean_case = []
    for c in raw_case:
        if any(ch.isdigit() for ch in c) and not re.fullmatch(r'\d{4,}', c):
            clean_case.append(c)
    # FIX 4: drop substring duplicates (e.g. "2023-98765" when "REF-2023-98765" exists)
    clean_case = [c for c in clean_case if not any(c != o and c in o for o in clean_case)]
    add_unique(intel["caseIds"], clean_case)

    # ── POLICY NUMBERS ────────────────────────────────────────────────────────
    policy = re.findall(r'Policy[^\w]*([A-Z0-9\-]{5,})', text, re.I)
    add_unique(intel["policyNumbers"], policy)

    # ── ORDER IDs ─────────────────────────────────────────────────────────────
    order = re.findall(r'Order[^\w]*([A-Z0-9\-]{5,})', text, re.I)
    add_unique(intel["orderIds"], order)