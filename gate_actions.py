# =========================================================
# PART 4 - THE THINGS WE CANNOT UNDO
# =========================================================

import json
from datetime import datetime, timezone
from pathlib import Path

from config import OUTPUT_PATH, OUTBOX_PATH





# =========================================================
# PATHS
# =========================================================


AUDIT_LOG_FILE = (
    OUTPUT_PATH / "action_audit.jsonl"
)

EMAIL_DRAFT_FILE = (
    OUTBOX_PATH / "drafts.json"
)


OUTBOX_PATH.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_PATH.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# ACTION CLASSIFICATION
# =========================================================

ACTION_POLICY = {

    "draft": {
        "reversible": True,
        "requires_approval": False,
        "reason": (
            "A draft can be edited, replaced, "
            "or discarded before sending."
        ),
    },

    "archive": {
        "reversible": True,
        "requires_approval": False,
        "reason": (
            "Archived messages can be restored "
            "to the inbox."
        ),
    },

    "defer": {
        "reversible": True,
        "requires_approval": False,
        "reason": (
            "A deferred action can be rescheduled "
            "or cancelled."
        ),
    },

    "delegate": {
        "reversible": True,
        "requires_approval": False,
        "reason": (
            "The delegation decision can be changed "
            "before an external action is performed."
        ),
    },

    "delete": {
        "reversible": True,
        "requires_approval": False,
        "reason": (
            "Delete means moving a message to a "
            "recoverable trash state in this design. "
            "It does not permanently destroy data."
        ),
    },

    "send": {
        "reversible": False,
        "requires_approval": True,
        "reason": (
            "Once a message is sent, the recipient "
            "may read or act on it and the action "
            "cannot reliably be undone."
        ),
    },

    "permanent_delete": {
        "reversible": False,
        "requires_approval": True,
        "reason": (
            "Permanent deletion destroys the message "
            "and cannot be reversed."
        ),
    },
}


# =========================================================
# TIME
# =========================================================

def current_timestamp():
    """
    Return an ISO-8601 UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


# =========================================================
# AUDIT LOGGING
# =========================================================

def log_gated_decision(
    action,
    proposed_action,
    human_decision,
    outcome,
    message_id=None,
    details=None
):
    """
    Append one gated decision to the audit log.

    Part 4 requires recording:

        1. What was proposed
        2. What the human said
        3. What happened

    JSONL is used so each decision is an independent,
    append-only audit record.
    """

    record = {
        "timestamp": current_timestamp(),
        "message_id": message_id,
        "action": action,
        "proposed_action": proposed_action,
        "human_decision": human_decision,
        "outcome": outcome,
        "details": details or {},
    }


    with open(
        AUDIT_LOG_FILE,
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
# ACTION POLICY HELPERS
# =========================================================

def get_action_policy(action):
    """
    Return the safety policy associated with an action.
    """

    if action not in ACTION_POLICY:

        raise ValueError(
            f"Unknown action: {action}"
        )


    return ACTION_POLICY[action]


def is_reversible(action):
    """
    Check whether an action is reversible.
    """

    return get_action_policy(
        action
    )["reversible"]


def requires_approval(action):
    """
    Check whether explicit approval is required.
    """

    return get_action_policy(
        action
    )["requires_approval"]


# =========================================================
# LOAD PART 3 DRAFT
# =========================================================

def load_email_reply_draft():
    """
    Load the grounded draft created by Part 3.

    Part 4 does not create another answer. It acts on the
    already-grounded draft from Part 3.
    """

    if not EMAIL_DRAFT_FILE.exists():

        raise FileNotFoundError(
            "No email draft was found. "
            "Run answer email before attempting to send."
        )


    with open(
        EMAIL_DRAFT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        result = json.load(f)


    # -----------------------------------------------------
    # Only a successful grounded Part 3 draft may proceed.
    # -----------------------------------------------------

    if result.get("status") != "drafted":

        raise ValueError(
            "Answer reply task did not produce a grounded draft. "
            "Nothing can be sent."
        )


    if not result.get("draft"):

        raise ValueError(
            "Part 3 output contains no draft. "
            "Nothing can be sent."
        )


    if not result.get("source_message_ids"):

        raise ValueError(
            "Part 3 draft contains no grounding sources. "
            "Nothing can be sent."
        )


    return result


# =========================================================
# BUILD SEND PROPOSAL
# =========================================================

def build_send_proposal(
    email_reply_result,
    recipient=None,
    subject=None
):
    """
    Convert a grounded Part 3 draft into a proposed send
    action.

    This does NOT send anything.
    """

    target_message_id = (
        email_reply_result[
            "target_message_id"
        ]
    )


    proposal = {
        "action": "send",
        "target_message_id":
            target_message_id,

        "recipient":
            recipient,

        "subject":
            subject,

        "body":
            email_reply_result["draft"],

        "source_message_ids":
            email_reply_result[
                "source_message_ids"
            ],
    }


    return proposal


# =========================================================
# DISPLAY EXACT PROPOSED ACTION
# =========================================================

def display_send_proposal(
    proposal
):
    """
    Show exactly what the system proposes to send.

    This supports both:
        - dry-run
        - explicit human approval
    """

    print(
        "\n" + "=" * 70
    )

    print(
        "PROPOSED IRREVERSIBLE ACTION"
    )

    print(
        "=" * 70
    )


    print(
        "\nAction:"
    )

    print(
        "SEND MESSAGE"
    )


    print(
        "\nTarget message ID:"
    )

    print(
        proposal[
            "target_message_id"
        ]
    )


    print(
        "\nRecipient:"
    )

    print(
        proposal.get(
            "recipient"
        )
        or
        "(not specified)"
    )


    print(
        "\nSubject:"
    )

    print(
        proposal.get(
            "subject"
        )
        or
        "(not specified)"
    )


    print(
        "\nGrounding sources:"
    )


    for source_id in (
        proposal[
            "source_message_ids"
        ]
    ):

        print(
            f"  - {source_id}"
        )


    print(
        "\nMessage body:"
    )

    print(
        "-" * 70
    )

    print(
        proposal[
            "body"
        ]
    )

    print(
        "-" * 70
    )


# =========================================================
# WRITE TO OUTBOX
# =========================================================

def write_to_outbox(
    proposal
):
    """
    Perform the irreversible SEND action.

    Assignment requirement:

        Sending writes to outbox/,
        one file per message,
        and nowhere else.

    This function therefore writes the sent message ONLY
    to OUTBOX_PATH.
    """

    message_id = (
        proposal[
            "target_message_id"
        ]
    )


    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )


    filename = (
        f"{message_id}_{timestamp}.json"
    )


    output_file = (
        OUTBOX_PATH / filename
    )


    sent_message = {
        "message_id":
            message_id,

        "sent_at":
            current_timestamp(),

        "recipient":
            proposal.get(
                "recipient"
            ),

        "subject":
            proposal.get(
                "subject"
            ),

        "body":
            proposal["body"],

        "source_message_ids":
            proposal[
                "source_message_ids"
            ],
    }


    # -----------------------------------------------------
    # IMPORTANT:
    # The actual sent message is written only to outbox/.
    # -----------------------------------------------------

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            sent_message,
            f,
            indent=2,
            ensure_ascii=False
        )


    return output_file


# =========================================================
# DRY RUN
# =========================================================

def dry_run_send(
    proposal
):
    """
    Show exactly what would happen without performing
    the irreversible send action.
    """

    display_send_proposal(
        proposal
    )


    print(
        "\nDRY RUN"
    )

    print(
        "No message was sent."
    )

    print(
        "No file was written to outbox/."
    )


    # -----------------------------------------------------
    # Log the gated decision
    # -----------------------------------------------------

    log_gated_decision(
        action="send",

        proposed_action=proposal,

        human_decision=(
            "No approval requested "
            "because dry-run mode was used."
        ),

        outcome="dry_run_only",

        message_id=proposal[
            "target_message_id"
        ],

        details={
            "outbox_written": False,
            "irreversible_action_performed":
                False,
        },
    )


    return {
        "status": "dry_run",
        "sent": False,
        "outbox_file": None,
    }


# =========================================================
# HUMAN APPROVAL
# =========================================================

def request_send_approval(
    proposal
):
    """
    Request explicit human approval for exactly ONE
    irreversible send action.

    Approval is intentionally per-action rather than
    blanket approval.
    """

    display_send_proposal(
        proposal
    )


    print(
        "\nThis action is IRREVERSIBLE."
    )

    print(
        "Once sent, the message cannot reliably "
        "be recalled."
    )


    print(
        "\nApprove this exact send action?"
    )

    print(
        "Type YES to approve."
    )

    print(
        "Anything else will reject it."
    )


    decision = input(
        "\nApproval: "
    ).strip()


    approved = (
        decision == "YES"
    )


    return approved, decision


# =========================================================
# EXECUTE SEND WITH HUMAN GATE
# =========================================================

def execute_send(
    proposal
):
    """
    Gate the irreversible send action with explicit human
    approval.

    Nothing is written to outbox/ unless the human types
    exactly:

        YES
    """

    policy = get_action_policy(
        "send"
    )


    # Safety assertion

    if policy["reversible"]:

        raise RuntimeError(
            "Configuration error: send must "
            "be classified as irreversible."
        )


    # -----------------------------------------------------
    # Ask for approval
    # -----------------------------------------------------

    approved, human_response = (
        request_send_approval(
            proposal
        )
    )


    # =====================================================
    # HUMAN REJECTED
    # =====================================================

    if not approved:

        print(
            "\nSEND CANCELLED"
        )

        print(
            "Nothing was written to outbox/."
        )


        log_gated_decision(
            action="send",

            proposed_action=proposal,

            human_decision=(
                human_response
                or
                "(no response)"
            ),

            outcome="rejected",

            message_id=proposal[
                "target_message_id"
            ],

            details={
                "outbox_written": False,
                "irreversible_action_performed":
                    False,
            },
        )


        return {
            "status": "rejected",
            "sent": False,
            "outbox_file": None,
        }


    # =====================================================
    # HUMAN APPROVED
    # =====================================================

    print(
        "\nApproval received."
    )


    try:

        # -------------------------------------------------
        # Perform irreversible action
        # -------------------------------------------------

        output_file = (
            write_to_outbox(
                proposal
            )
        )


        # -------------------------------------------------
        # Log what happened
        # -------------------------------------------------

        log_gated_decision(
            action="send",

            proposed_action=proposal,

            human_decision=(
                human_response
            ),

            outcome="executed",

            message_id=proposal[
                "target_message_id"
            ],

            details={
                "outbox_written": True,

                "outbox_file":
                    str(output_file),

                "irreversible_action_performed":
                    True,
            },
        )


        print(
            "\nMESSAGE SENT"
        )

        print(
            f"Outbox file: "
            f"{output_file}"
        )


        return {
            "status": "sent",
            "sent": True,
            "outbox_file":
                str(output_file),
        }


    # =====================================================
    # FAILURE AFTER APPROVAL
    # =====================================================

    except Exception as exc:

        log_gated_decision(
            action="send",

            proposed_action=proposal,

            human_decision=(
                human_response
            ),

            outcome="failed",

            message_id=proposal[
                "target_message_id"
            ],

            details={
                "outbox_written": False,

                "irreversible_action_performed":
                    False,

                "error":
                    str(exc),
            },
        )


        raise


# =========================================================
# PERMANENT DELETE GATE
# =========================================================

def request_permanent_delete(
    message_id
):
    """
    Demonstrate how permanent deletion would be gated.

    The assignment asks us to state whether deleting is
    reversible.

    Normal 'delete' in this design means recoverable trash.

    'permanent_delete' is separate and irreversible.

    This function intentionally does not implement actual
    permanent deletion because the assignment only requires
    classification and gating.
    """


    proposed_action = {
        "action":
            "permanent_delete",

        "message_id":
            message_id,
    }


    print(
        "\n" + "=" * 70
    )

    print(
        "PROPOSED IRREVERSIBLE ACTION"
    )

    print(
        "=" * 70
    )


    print(
        "\nAction: "
        "PERMANENT DELETE"
    )


    print(
        f"Message ID: "
        f"{message_id}"
    )


    print(
        "\nThis action cannot be undone."
    )


    print(
        "Type YES to approve permanent deletion."
    )


    decision = input(
        "\nApproval: "
    ).strip()


    approved = (
        decision == "YES"
    )


    if approved:

        # -------------------------------------------------
        # We deliberately do NOT actually destroy the
        # message in this assignment implementation.
        # -------------------------------------------------

        outcome = (
            "approved_but_not_implemented"
        )


        print(
            "\nPermanent deletion was approved, "
            "but physical deletion is not implemented."
        )


    else:

        outcome = "rejected"


        print(
            "\nPermanent deletion cancelled."
        )


    # -----------------------------------------------------
    # Log decision
    # -----------------------------------------------------

    log_gated_decision(
        action="permanent_delete",

        proposed_action=proposed_action,

        human_decision=(
            decision
            or
            "(no response)"
        ),

        outcome=outcome,

        message_id=message_id,

        details={
            "irreversible_action_performed":
                False,
        },
    )


    return {
        "approved": approved,
        "outcome": outcome,
    }


# =========================================================
# DISPLAY ACTION POLICY
# =========================================================

def display_action_policy():
    """
    Print the action classification used by the system.
    """

    print(
        "\n" + "=" * 70
    )

    print(
        "ACTION SAFETY POLICY"
    )

    print(
        "=" * 70
    )


    for action, policy in (
        ACTION_POLICY.items()
    ):

        classification = (
            "REVERSIBLE"
            if policy["reversible"]
            else "IRREVERSIBLE"
        )


        print(
            f"\n{action.upper()}"
        )


        print(
            f"  Classification: "
            f"{classification}"
        )


        print(
            f"  Approval required: "
            f"{policy['requires_approval']}"
        )


        print(
            f"  Reason: "
            f"{policy['reason']}"
        )


# =========================================================
# RUN PART 4
# =========================================================

def gate_actions(
    dry_run=True,
    recipient=None,
    subject=None
):
    """
    Run Part 4 using the grounded draft created by Part 3.

    Recommended first test:

        gate_actions(dry_run=True)

    This shows exactly what would be sent without writing
    anything to outbox/.

    Actual gated send:

        gate_actions(dry_run=False)

    This requires explicit human approval.
    """


    print(
        "\n" + "=" * 70
    )

    print(
        "PART 4 - THE THINGS YOU CANNOT UNDO"
    )

    print(
        "=" * 70
    )


    # -----------------------------------------------------
    # Show policy
    # -----------------------------------------------------

    display_action_policy()


    # -----------------------------------------------------
    # Load grounded Part 3 draft
    # -----------------------------------------------------

    email_reply_result = (
        load_email_reply_draft()
    )


    # -----------------------------------------------------
    # Create proposed send
    # -----------------------------------------------------

    proposal = build_send_proposal(
        email_reply_result,
        recipient=recipient,
        subject=subject,
    )


    # =====================================================
    # DRY RUN
    # =====================================================

    if dry_run:

        return dry_run_send(
            proposal
        )


    # =====================================================
    # EXPLICIT HUMAN APPROVAL
    # =====================================================

    return execute_send(
        proposal
    )


# =========================================================
# OPTIONAL DIRECT EXECUTION
# =========================================================

if __name__ == "__main__":

    # -----------------------------------------------------
    # Start with dry-run mode.
    #
    # This shows exactly what would be sent but performs
    # no irreversible action.
    # -----------------------------------------------------

    gate_actions(
        dry_run=True
    )