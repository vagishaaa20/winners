import time

sessions: dict = {}


def create_session() -> dict:
    return {
        "count":       0,
        "startTime":   time.time(),
        "final":       False,
        "notes":       "Conversation initiated. Monitoring for urgency pressure or suspicious requests.",
        "intel": {
            "phoneNumbers":  [],
            "bankAccounts":  [],
            "upiIds":        [],
            "phishingLinks": [],
            "emailAddresses":[],
            "caseIds":       [],
            "policyNumbers": [],
            "orderIds":      [],
        },
    }