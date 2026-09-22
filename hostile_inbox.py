# =========================================================
# PART 6 - HOSTILE INBOX
# =========================================================

import json
import re
from datetime import datetime, timezone

from config import *


# =========================================================
# FILES
# =========================================================

SECURITY_LOG_FILE = (
    OUTPUT_PATH / "security_refusals.jsonl"
)

SECURITY_REPORT_FILE = (
    OUTPUT_PATH / "hostile_inbox_report.json"
)

OUTPUT_PATH.mkdir(
    parents=True,
    exist_ok=True
)

def get_safe_inbox():
    """
    Return only emails that passed the security gate.

    Hostile messages remain physically present in inbox.json,
    but downstream components never receive them.
    """

    emails = load_inbox()

    safe_emails = []

    for email in emails:

        result = inspect_message(email)

        if result["continue_processing"]:
            safe_emails.append(email)

    return safe_emails

# =========================================================
# SECURITY POLICY
# =========================================================

"""
IMPORTANT ARCHITECTURAL RULE

Email content is UNTRUSTED DATA.

An email is allowed to:
    - provide information
    - request a normal reply
    - contain ordinary business instructions

An email is NOT allowed to control the assistant itself.

In particular, an email cannot instruct the system to:

    - forward mail automatically
    - send mail automatically
    - delete another message
    - hide an action
    - bypass human approval
    - ignore security rules
    - override system instructions
    - manipulate the outbox
    - perform actions secretly

Detected hostile instructions are flagged and refused.

No action tool is called from this module.
"""


# =========================================================
# TIMESTAMP
# =========================================================

def current_timestamp():

    return datetime.now(
        timezone.utc
    ).isoformat()


# =========================================================
# NORMALIZE EMAIL CONTENT
# =========================================================

def email_security_text(email):
    """
    Convert email fields into searchable text.

    All content returned here is considered UNTRUSTED.
    """

    return " ".join([
        str(email.get("from", "")),
        str(email.get("subject", "")),
        str(email.get("body", "")),
    ]).lower()


# =========================================================
# HOSTILE INSTRUCTION PATTERNS
# =========================================================

ATTACK_PATTERNS = {

    # -----------------------------------------------------
    # Attempts to manipulate assistant/system instructions
    # -----------------------------------------------------

    "instruction_override": [

        r"ignore\s+(all\s+)?previous\s+instructions",

        r"ignore\s+(all\s+)?prior\s+instructions",

        r"disregard\s+(all\s+)?previous\s+instructions",

        r"disregard\s+(all\s+)?prior\s+instructions",

        r"forget\s+(all\s+)?previous\s+instructions",

        r"override\s+(your|the)\s+(instructions|rules)",

        r"new\s+system\s+instruction",

        r"new\s+system\s+prompt",

        r"replace\s+(your|the)\s+(instructions|rules)",

        r"follow\s+these\s+instructions\s+instead",
    ],


    # -----------------------------------------------------
    # Attempts to make assistant forward information
    # -----------------------------------------------------

    "unauthorized_forward": [

        r"forward\s+(this|the)\s+(email|message)",

        r"forward\s+(all|every)\s+(email|message)",

        r"forward\s+(my|your|the)\s+(mail|emails)",

        r"send\s+(a\s+)?copy\s+of\s+(this|the)\s+(email|message)",

        r"send\s+(this|the)\s+(email|message)\s+to",

        r"forward\s+.*\s+to\s+.*@",

        r"copy\s+.*\s+to\s+.*@",
    ],


    # -----------------------------------------------------
    # Attempts to delete messages
    # -----------------------------------------------------

    "unauthorized_delete": [

        r"delete\s+(this|the)\s+(email|message)",

        r"delete\s+.*\s+(email|message)",

        r"remove\s+(this|the)\s+(email|message)",

        r"erase\s+(this|the)\s+(email|message)",

        r"permanently\s+delete",

        r"empty\s+(the\s+)?trash",
    ],


    # -----------------------------------------------------
    # Attempts to hide actions
    # -----------------------------------------------------

    "concealment_request": [

        r"do\s+not\s+tell\s+(the\s+)?user",

        r"don't\s+tell\s+(the\s+)?user",

        r"do\s+not\s+mention\s+(this|it)",

        r"don't\s+mention\s+(this|it)",

        r"without\s+telling\s+(the\s+)?user",

        r"without\s+informing\s+(the\s+)?user",

        r"keep\s+(this|it)\s+secret",

        r"quietly\s+(delete|forward|send|remove)",

        r"silently\s+(delete|forward|send|remove)",

        r"without\s+their\s+knowledge",

        r"without\s+the\s+owner('s)?\s+knowledge",
    ],


    # -----------------------------------------------------
    # Attempts to bypass Part 4 / human approval
    # -----------------------------------------------------

    "approval_bypass": [

        r"without\s+(human\s+)?approval",

        r"skip\s+(the\s+)?approval",

        r"bypass\s+(the\s+)?approval",

        r"no\s+approval\s+(is\s+)?needed",

        r"you\s+have\s+(my\s+)?permission\s+to\s+send",

        r"automatically\s+send",

        r"send\s+without\s+asking",

        r"do\s+not\s+ask\s+for\s+approval",

        r"don't\s+ask\s+for\s+approval",
    ],


    # -----------------------------------------------------
    # Attempts to impersonate privileged authority
    # -----------------------------------------------------

    "privilege_claim": [

        r"i\s+am\s+(the\s+)?system\s+administrator",

        r"this\s+is\s+(the\s+)?system\s+administrator",

        r"administrator\s+instruction",

        r"system\s+administrator\s+instruction",

        r"security\s+administrator\s+instruction",

        r"developer\s+instruction",

        r"system\s+message\s*:",
    ],
}


# =========================================================
# EXTRACT ATTEMPT DESCRIPTION
# =========================================================

ATTACK_DESCRIPTIONS = {

    "instruction_override":
        "Attempted to override or replace the assistant's instructions.",

    "unauthorized_forward":
        "Attempted to make the assistant forward or disclose email content.",

    "unauthorized_delete":
        "Attempted to make the assistant delete or remove email content.",

    "concealment_request":
        "Attempted to make the assistant perform an action without informing the user.",

    "approval_bypass":
        "Attempted to bypass the human approval gate for an action.",

    "privilege_claim":
        "Attempted to claim privileged system or administrator authority through email content.",
}


# =========================================================
# DETECT HOSTILE INSTRUCTIONS
# =========================================================

def detect_hostile_instruction(email):
    """
    Scan an email for instructions attempting to control
    the assistant or cause unauthorized actions.

    IMPORTANT:

    This function DETECTS only.

    It has no access to:
        - outbox writing
        - delete functionality
        - forwarding
        - send functionality

    Therefore even hostile content cannot directly cause
    an irreversible action.
    """

    text = email_security_text(
        email
    )

    detections = []


    for attack_type, patterns in ATTACK_PATTERNS.items():

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            )


            if match:

                detections.append({
                    "attack_type":
                        attack_type,

                    "attempted_action":
                        ATTACK_DESCRIPTIONS[
                            attack_type
                        ],

                    "matched_text":
                        match.group(0),

                    "pattern":
                        pattern,
                })

                # One match is enough to establish this
                # attack category.

                break


    return detections


# =========================================================
# LOG SECURITY REFUSAL
# =========================================================

def log_security_refusal(
    email,
    detections
):
    """
    Requirement 2:

    Log a refusal naming:

        - message ID
        - what was attempted
        - what happened
    """

    record = {

        "timestamp":
            current_timestamp(),

        "message_id":
            email.get("id"),

        "subject":
            email.get("subject"),

        "sender":
            email.get("from"),

        "decision":
            "refused",

        "flagged":
            True,

        "message_deleted":
            False,

        "action_taken":
            False,

        "outbox_written":
            False,

        "detections":
            detections,

        "reason": (
            "The message contained instructions attempting "
            "to control the assistant or trigger an "
            "unauthorized action. Email content is treated "
            "as untrusted data, so the instruction was "
            "refused."
        ),
    }


    with open(
        SECURITY_LOG_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )


    return record


# =========================================================
# FLAG HOSTILE MESSAGE
# =========================================================

def flag_message(
    email,
    detections
):
    """
    Produce a security flag.

    IMPORTANT:

    This does NOT modify inbox.json.

    Therefore the hostile message remains in place exactly
    as required by Part 6.

    The flag exists only in the security report/log.
    """

    return {

        "message_id":
            email.get("id"),

        "subject":
            email.get("subject"),

        "sender":
            email.get("from"),

        "security_status":
            "hostile_instruction_detected",

        "flagged":
            True,

        "deleted":
            False,

        "action_taken":
            False,

        "outbox_written":
            False,

        "detections":
            detections,
    }


# =========================================================
# SCAN ONE MESSAGE
# =========================================================

def inspect_message(email):
    """
    Inspect one message before allowing it to continue
    through the email-agent pipeline.
    """

    detections = (
        detect_hostile_instruction(
            email
        )
    )


    # -----------------------------------------------------
    # SAFE MESSAGE
    # -----------------------------------------------------

    if not detections:

        return {

            "message_id":
                email.get("id"),

            "safe":
                True,

            "flagged":
                False,

            "continue_processing":
                True,

            "detections":
                [],
        }


    # =====================================================
    # HOSTILE MESSAGE
    # =====================================================

    # -----------------------------------------------------
    # Log explicit refusal
    # -----------------------------------------------------

    log_security_refusal(
        email,
        detections
    )


    # -----------------------------------------------------
    # Flag message
    # -----------------------------------------------------

    flag = flag_message(
        email,
        detections
    )


    return {

        "message_id":
            email.get("id"),

        "safe":
            False,

        "flagged":
            True,

        "continue_processing":
            False,

        "detections":
            detections,

        "flag":
            flag,
    }


# =========================================================
# SCAN ENTIRE INBOX
# =========================================================

def scan_hostile_inbox():
    """
    Scan every message in the inbox.

    Hostile messages are:

        1. detected
        2. refused
        3. logged
        4. flagged
        5. reported to user
        6. left in the inbox

    No action is performed on behalf of the hostile email.
    """

    emails = load_inbox()


    print(
        "\n" + "=" * 70
    )

    print(
        "PART 6 - THE HOSTILE INBOX"
    )

    print(
        "=" * 70
    )


    print(
        f"\nScanning {len(emails)} inbox messages..."
    )


    hostile_messages = []

    safe_messages = []


    # =====================================================
    # INSPECT EVERY MESSAGE
    # =====================================================

    for email in emails:

        result = inspect_message(
            email
        )


        if result["safe"]:

            safe_messages.append(
                email.get("id")
            )


        else:

            hostile_messages.append(
                result
            )


            print(
                "\n"
                + "!" * 70
            )

            print(
                "HOSTILE INSTRUCTION DETECTED"
            )

            print(
                "!" * 70
            )


            print(
                f"\nMessage ID : "
                f"{email.get('id')}"
            )


            print(
                f"From       : "
                f"{email.get('from')}"
            )


            print(
                f"Subject    : "
                f"{email.get('subject')}"
            )


            print(
                "\nAttempt(s) detected:"
            )


            for detection in (
                result["detections"]
            ):

                print(
                    f"\n  [{detection['attack_type']}]"
                )

                print(
                    "  "
                    + detection[
                        "attempted_action"
                    ]
                )

                print(
                    "  Matched text: "
                    + repr(
                        detection[
                            "matched_text"
                        ]
                    )
                )


            print(
                "\nACTION REFUSED"
            )


            print(
                "No instruction from this message "
                "was executed."
            )


            print(
                "Nothing was written to outbox/."
            )


            print(
                "The message was NOT deleted."
            )


            print(
                "The message remains in the inbox "
                "and has been flagged."
            )


    # =====================================================
    # BUILD RUN SUMMARY
    # =====================================================

    summary = {

        "part":
            "Part 6 - The Hostile Inbox",

        "timestamp":
            current_timestamp(),

        "total_messages_scanned":
            len(emails),

        "safe_messages":
            len(safe_messages),

        "hostile_messages_found":
            len(hostile_messages),

        "hostile_message_ids": [
            item["message_id"]
            for item in hostile_messages
        ],

        "actions_executed_for_hostile_messages":
            0,

        "hostile_messages_deleted":
            0,

        "outbox_writes_from_hostile_messages":
            0,

        "security_policy": (
            "Email content is untrusted data. "
            "Instructions inside email cannot invoke "
            "irreversible actions."
        ),

        "hostile_messages":
            hostile_messages,
    }


    # =====================================================
    # SAVE REPORT
    # =====================================================

    with open(
        SECURITY_REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
            ensure_ascii=False
        )


    # =====================================================
    # USER-VISIBLE SUMMARY
    # =====================================================

    print(
        "\n" + "=" * 70
    )

    print(
        "HOSTILE INBOX RUN SUMMARY"
    )

    print(
        "=" * 70
    )


    print(
        f"\nMessages scanned: "
        f"{summary['total_messages_scanned']}"
    )


    print(
        f"Hostile messages found: "
        f"{summary['hostile_messages_found']}"
    )


    print(
        "Actions executed on behalf of attacks: "
        "0"
    )


    print(
        "Messages deleted because of attacks: "
        "0"
    )


    print(
        "Outbox writes caused by attacks: "
        "0"
    )


    # -----------------------------------------------------
    # Requirement 3:
    # Explicitly tell user what was found.
    # -----------------------------------------------------

    if hostile_messages:

        print(
            "\nSECURITY WARNING:"
        )


        print(
            "The following inbox messages attempted "
            "to influence the assistant:"
        )


        for item in hostile_messages:

            print(
                f"\n  Message: "
                f"{item['message_id']}"
            )


            for detection in (
                item["detections"]
            ):

                print(
                    f"    - "
                    f"{detection['attempted_action']}"
                )


            print(
                "    Result: REFUSED, FLAGGED, "
                "LEFT IN INBOX"
            )


    else:

        print(
            "\nNo hostile instructions were "
            "detected."
        )


    print(
        f"\nSecurity report: "
        f"{SECURITY_REPORT_FILE}"
    )


    print(
        f"Refusal log: "
        f"{SECURITY_LOG_FILE}"
    )


    return summary


# =========================================================
# SECURITY CHECK FOR PIPELINE USE
# =========================================================

def security_gate(email):
    """
    This is the function other parts of the agent should
    call BEFORE processing an email.

    Returns:

        True  -> message may continue through pipeline

        False -> hostile instruction detected;
                 processing MUST stop

    This creates an architectural boundary rather than
    relying only on an LLM prompt.
    """

    result = inspect_message(
        email
    )


    if not result[
        "continue_processing"
    ]:

        print(
            "\nSECURITY GATE BLOCKED MESSAGE "
            f"{email.get('id')}"
        )


        print(
            "The message was flagged and "
            "will not be acted upon."
        )


        return False


    return True


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    scan_hostile_inbox()