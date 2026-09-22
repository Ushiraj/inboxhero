"""
============================================================
inboxHero - Assignment 06
demo.py
============================================================

Single demonstration entry point for every capability listed
in capabilities.json.

Examples
--------

Required capabilities:

    python demo.py --cap R1
    python demo.py --cap R2 --msg m008
    python demo.py --cap R3 --dry-run
    python demo.py --cap R4
    python demo.py --cap R5
    python demo.py --cap R6

Additional capabilities:

    python demo.py --cap X1 --sender example
    python demo.py --cap X2
    python demo.py --cap X3 --msg m008
    python demo.py --cap X4

Run all:

    python demo.py --all

Safe full demonstration:

    python demo.py --all --dry-run


DESIGN
------

demo.py is intentionally only an orchestration layer.

The implementation of Parts 2-8 remains in the modules that
implement those parts. demo.py gives the evaluator one stable
entry point and writes trace.jsonl evidence for the manifest.

Email content is never treated as authority to perform an
irreversible action. Sending and permanent deletion remain
behind the Part 4 action gate.
"""

import argparse
import json
import sys
import traceback

from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

TRACE_FILE = ROOT / "trace.jsonl"

CAPABILITIES_FILE = ROOT / "capabilities.json"


# ============================================================
# CAPABILITY REGISTRY
# ============================================================

CAPABILITY_INFO = {

    "R1": {
        "name": "Zero the inbox",
        "tier": "B",
        "part": "Part 2",
    },

    "R2": {
        "name": "Grounded reply",
        "tier": "B",
        "part": "Part 3",
    },

    "R3": {
        "name": "Gate the irreversible",
        "tier": "C",
        "part": "Part 4",
    },

    "R4": {
        "name": "Persistent preference",
        "tier": "C",
        "part": "Part 5",
    },

    "R5": {
        "name": "Refuse embedded instructions",
        "tier": "C",
        "part": "Part 6",
    },

    "R6": {
        "name": "Dashboard",
        "tier": "C",
        "part": "Part 7",
    },

    "X1": {
        "name": "Sender lookup",
        "tier": "A",
        "part": "Part 8",
    },

    "X2": {
        "name": "Morning digest",
        "tier": "B",
        "part": "Part 8",
    },

    "X3": {
        "name": "Thread summary and open question",
        "tier": "B",
        "part": "Part 8",
    },

    "X4": {
        "name": "Follow-up tracking",
        "tier": "C",
        "part": "Part 8",
    },
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def utc_now():
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def json_safe(value):
    """
    Convert a value into something JSON serializable.

    Trace logging must never make a capability fail merely
    because its return value contains a Path or other object.
    """

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):

        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):

        return [
            json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        )
    ) or value is None:

        return value

    return str(value)


# ============================================================
# TRACE
# ============================================================

def trace_event(
    cap,
    event,
    **details
):
    """
    Append one event to trace.jsonl.

    trace.jsonl is demonstration evidence, not an action
    mechanism.

    Do not place complete email bodies or complete drafts
    here. The trace should record metadata about what
    happened rather than duplicate message content.
    """

    record = {
        "timestamp": utc_now(),
        "cap": cap,
        "event": event,
    }

    for key, value in details.items():

        record[key] = json_safe(
            value
        )

    with open(
        TRACE_FILE,
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


# ============================================================
# DISPLAY HELPERS
# ============================================================

def print_banner(cap):
    """
    Display a consistent capability heading.
    """

    info = CAPABILITY_INFO[
        cap
    ]

    print(
        "\n"
        + "=" * 72
    )

    print(
        f"inboxHero | {cap} | "
        f"{info['name']}"
    )

    print(
        "=" * 72
    )

    print(
        f"Assignment section : "
        f"{info['part']}"
    )

    print(
        f"Tier               : "
        f"{info['tier']}"
    )

    print(
        "=" * 72
    )


def print_json_result(result):
    """
    Pretty-print a returned dictionary/list where useful.
    """

    if result is None:
        return

    if isinstance(
        result,
        (dict, list)
    ):

        print(
            "\nStructured result:"
        )

        print(
            json.dumps(
                json_safe(result),
                indent=2,
                ensure_ascii=False
            )
        )


# ============================================================
# MANIFEST
# ============================================================

def load_manifest():
    """
    Load capabilities.json when present.

    demo.py does not depend on the manifest for its internal
    routing, but validating it helps catch submission errors.
    """

    if not CAPABILITIES_FILE.exists():

        return None

    with open(
        CAPABILITIES_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def validate_manifest():
    """
    Check that capabilities.json contains the same capability
    IDs exposed by demo.py.

    This prevents CAPABILITIES.md, capabilities.json and
    demo.py from silently drifting apart.
    """

    manifest = load_manifest()

    if manifest is None:

        print(
            "\nWARNING: capabilities.json "
            "was not found."
        )

        return False

    declared = {
        item.get("id")
        for item in manifest.get(
            "capabilities",
            []
        )
    }

    expected = set(
        CAPABILITY_INFO.keys()
    )

    missing = (
        expected - declared
    )

    unknown = (
        declared - expected
    )

    if missing:

        print(
            "\nWARNING: capabilities.json "
            "is missing:"
        )

        for cap in sorted(missing):

            print(
                f"  - {cap}"
            )

    if unknown:

        print(
            "\nWARNING: capabilities.json "
            "contains capabilities demo.py "
            "does not expose:"
        )

        for cap in sorted(unknown):

            print(
                f"  - {cap}"
            )

    return not missing and not unknown


# ============================================================
# R1
# PART 2 - ZERO THE INBOX
# ============================================================

def run_r1(args):
    """
    Process the entire inbox.

    read_inbox.process_inbox() already implements:

        deterministic rules first
        LLM fallback
        exactly one disposition
        reason for every disposition
        final rule/LLM counts
    """

    print_banner(
        "R1"
    )

    trace_event(
        "R1",
        "start"
    )

    import read_inbox

    # --------------------------------------------------------
    # Execute actual Part 2 implementation
    # --------------------------------------------------------

    read_inbox.process_inbox()

    # --------------------------------------------------------
    # process_inbox() writes the results rather than returning
    # them, so read its configured output file afterwards.
    # --------------------------------------------------------

    output_file = Path(
        read_inbox.OUTPUT_FILE
    )

    if not output_file.exists():

        raise RuntimeError(
            "Part 2 completed but its disposition "
            f"file was not found: {output_file}"
        )

    with open(
        output_file,
        "r",
        encoding="utf-8"
    ) as f:

        decisions = json.load(f)

    emails = (
        read_inbox.load_inbox()
    )

    mail_ids = {
        email.get("id")
        for email in emails
    }

    # --------------------------------------------------------
    # Validate one disposition per inbox message
    # --------------------------------------------------------

    decision_ids = []

    rule_count = 0
    llm_count = 0

    for decision in decisions:

        message_id = (
            decision.get("id")
            or
            decision.get(
                "message_id"
            )
        )

        decision_ids.append(
            message_id
        )

        if decision.get(
            "model_called"
        ):

            llm_count += 1

        else:

            rule_count += 1

        trace_event(
            "R1",
            "decision",
            message_id=message_id,
            disposition=decision.get(
                "disposition"
            ),
            reason=decision.get(
                "reason"
            ),
            model_called=decision.get(
                "model_called"
            ),
            rule=decision.get(
                "rule"
            )
        )

    decision_id_set = set(
        decision_ids
    )

    missing_ids = (
        mail_ids - decision_id_set
    )

    duplicate_count = (
        len(decision_ids)
        -
        len(decision_id_set)
    )

    undecided = len(
        missing_ids
    )

    print(
        "\n"
        + "-" * 72
    )

    print(
        "R1 DEMO SUMMARY"
    )

    print(
        "-" * 72
    )

    print(
        f"messages processed: "
        f"{len(emails)}"
    )

    print(
        f"rule handled:       "
        f"{rule_count}"
    )

    print(
        f"LLM classified:     "
        f"{llm_count}"
    )

    print(
        f"duplicate decisions:"
        f" {duplicate_count}"
    )

    print(
        f"undecided:          "
        f"{undecided}"
    )

    if missing_ids:

        print(
            "\nMissing message IDs:"
        )

        for message_id in sorted(
            missing_ids
        ):

            print(
                f"  - {message_id}"
            )

    if duplicate_count:

        raise RuntimeError(
            "R1 produced more than one decision "
            "for at least one message."
        )

    if undecided:

        raise RuntimeError(
            "R1 left inbox messages without "
            "a disposition."
        )

    trace_event(
        "R1",
        "summary",
        messages_processed=len(
            emails
        ),
        rule_handled=rule_count,
        llm_classified=llm_count,
        undecided=undecided,
        duplicate_decisions=
            duplicate_count,
        output_file=str(
            output_file
        )
    )

    return {
        "messages_processed":
            len(emails),

        "rule_handled":
            rule_count,

        "llm_classified":
            llm_count,

        "undecided":
            undecided,

        "output_file":
            str(output_file),
    }


# ============================================================
# R2
# PART 3 - GROUNDED REPLY
# ============================================================

def run_r2(args):
    """
    Demonstrate the grounded reply capability.
    """

    print_banner(
        "R2"
    )

    message_id = (
        args.msg
        or "m008"
    )

    print(
        f"\nTarget message: "
        f"{message_id}"
    )

    trace_event(
        "R2",
        "start",
        message_id=message_id
    )

    from answer_email import (
        answer_email
    )

    result = answer_email(
        message_id
    )

    trace_event(
        "R2",
        "draft",
        message_id=message_id,
        status=result.get(
            "status"
        ),
        cited_message_ids=result.get(
            "source_message_ids",
            []
        ),
        grounded=(
            result.get("status")
            == "drafted"
        )
    )

    print_json_result(
        result
    )

    return result


# ============================================================
# R3
# PART 4 - GATE IRREVERSIBLE ACTIONS
# ============================================================

def run_r3(args):
    """
    Demonstrate the irreversible-action gate.

    The actual Part 4 function is gate_actions().
    """

    print_banner(
        "R3"
    )

    # --------------------------------------------------------
    # Manifest demonstration uses --dry-run.
    #
    # If --dry-run is omitted, the underlying implementation
    # may ask the human for explicit approval.
    # --------------------------------------------------------

    dry_run = bool(
        args.dry_run
    )

    print(
        "\nMode: "
        + (
            "DRY RUN"
            if dry_run
            else "HUMAN APPROVAL"
        )
    )

    trace_event(
        "R3",
        "start",
        dry_run=dry_run
    )

    from gate_actions import (
        gate_actions
    )

    result = gate_actions(
        dry_run=dry_run
    )

    trace_event(
        "R3",
        "gate",
        dry_run=dry_run,
        status=(
            result.get("status")
            if isinstance(
                result,
                dict
            )
            else "completed"
        ),
        sent=(
            result.get("sent")
            if isinstance(
                result,
                dict
            )
            else None
        ),
        outbox_file=(
            result.get(
                "outbox_file"
            )
            if isinstance(
                result,
                dict
            )
            else None
        )
    )

    print_json_result(
        result
    )

    return result


# ============================================================
# R4
# PART 5 - PERSISTENT PREFERENCE
# ============================================================

def _find_legal_demo_message():
    """
    Find a real Legal-related message from the inbox.

    This avoids hard-coding an imaginary sample message ID.
    """

    from read_inbox import (
        load_inbox
    )

    emails = load_inbox()

    for email in emails:

        text = " ".join([
            str(
                email.get(
                    "subject",
                    ""
                )
            ),
            str(
                email.get(
                    "body",
                    ""
                )
            ),
        ]).lower()

        if "legal" in text:

            return email

    return None


def run_r4(args):
    """
    Demonstrate persistent standing instructions.

    First process:
        Store the preference and stop.

    Second process:
        Detect that the preference already exists on disk
        and apply it to a matching message.

    This makes the process restart visible rather than
    pretending persistence within one Python interpreter.
    """

    print_banner(
        "R4"
    )

    try:

        from memory import (
            get_preferences
        )

        from standing_instructions import (
            record_preference,
            process_message_with_memory
        )

    except ImportError as exc:

        raise RuntimeError(
            "R4 requires the final Part 5 "
            "memory.py and standing_instructions.py. "
            "Make sure both files are present in the "
            "project root."
        ) from exc

    # --------------------------------------------------------
    # Demonstration preference
    # --------------------------------------------------------
    #
    # This corresponds to the manifest statement:
    #
    #     CC co-founder on Legal mail
    #
    # It is stored structurally rather than encoded in
    # demo.py behavior.
    # --------------------------------------------------------

    preference_type = (
        "subject_contains"
    )

    preference_value = (
        "legal"
    )

    preference_action = (
        "cc:co-founder"
    )

    preferences = (
        get_preferences()
    )

    preference_exists = False

    for preference in preferences:

        stored_type = str(
            preference.get(
                "type",
                preference.get(
                    "preference_type",
                    ""
                )
            )
        ).lower()

        stored_value = str(
            preference.get(
                "value",
                ""
            )
        ).lower()

        if (
            stored_type
            == preference_type
            and
            stored_value
            == preference_value
        ):

            preference_exists = True
            break

    # ========================================================
    # FIRST INVOCATION
    # ========================================================

    if not preference_exists:

        print(
            "\nNo stored demonstration "
            "preference was found."
        )

        print(
            "\nRecording standing instruction:"
        )

        print(
            "  When Legal mail is encountered, "
            "CC the co-founder."
        )

        result = record_preference(
            preference_type=
                preference_type,
            value=
                preference_value,
            action=
                preference_action
        )

        trace_event(
            "R4",
            "preference_stored",
            preference_type=
                preference_type,
            value=
                preference_value,
            action=
                preference_action
        )

        print(
            "\nPreference has been persisted "
            "to disk."
        )

        print(
            "\nTo demonstrate persistence, "
            "allow this process to exit and "
            "run exactly the same command again:"
        )

        print(
            "\n    python demo.py --cap R4"
        )

        print(
            "\nThe second process will load "
            "the standing instruction without "
            "being told it again."
        )

        return {
            "status":
                "preference_stored",

            "restart_required":
                True,

            "preference":
                "CC co-founder on Legal mail",
        }

    # ========================================================
    # SECOND INVOCATION
    # ========================================================

    print(
        "\nStored preference found on disk."
    )

    print(
        "This invocation did not restate "
        "the preference."
    )

    target = (
        _find_legal_demo_message()
    )

    if target is None:

        raise RuntimeError(
            "The standing instruction was loaded, "
            "but no Legal-related inbox message "
            "was found for the demonstration."
        )

    message_id = target.get(
        "id"
    )

    print(
        f"\nApplying persisted preference "
        f"to message: {message_id}"
    )

    print(
        f"Subject: "
        f"{target.get('subject', '')}"
    )

    trace_event(
        "R4",
        "preference_reloaded",
        message_id=message_id,
        preference=(
            "CC co-founder on Legal mail"
        )
    )

    result = (
        process_message_with_memory(
            message_id
        )
    )

    trace_event(
        "R4",
        "preference_applied",
        message_id=message_id,
        status="completed"
    )

    print_json_result(
        result
    )

    return result


# ============================================================
# R5
# PART 6 - HOSTILE INBOX
# ============================================================

def run_r5(args):
    """
    Demonstrate hostile-inbox refusal.

    The hostile scanner is read-only with respect to inbox
    content and cannot itself send/delete mail.
    """

    print_banner(
        "R5"
    )

    trace_event(
        "R5",
        "start"
    )

    try:

        from hostile_inbox import (
            scan_hostile_inbox
        )

    except ImportError as exc:

        raise RuntimeError(
            "R5 requires hostile_inbox.py "
            "from Part 6."
        ) from exc

    result = (
        scan_hostile_inbox()
    )

    hostile_ids = []

    hostile_details = []

    if isinstance(
        result,
        dict
    ):

        hostile_ids = (
            result.get(
                "hostile_message_ids",
                []
            )
            or
            result.get(
                "flagged_message_ids",
                []
            )
        )

        hostile_details = (
            result.get(
                "hostile_details",
                []
            )
            or
            result.get(
                "flagged",
                []
            )
        )

    # --------------------------------------------------------
    # Trace each refusal individually when details are
    # available.
    # --------------------------------------------------------

    for item in hostile_details:

        if not isinstance(
            item,
            dict
        ):

            continue

        trace_event(
            "R5",
            "refusal",
            message_id=(
                item.get(
                    "message_id"
                )
                or
                item.get("id")
            ),
            attempted_action=(
                item.get(
                    "attempted_action"
                )
                or
                item.get(
                    "attack_type"
                )
            ),
            action_taken=False,
            deleted=False
        )

    # If the module only returned IDs, still produce evidence.

    if (
        not hostile_details
        and hostile_ids
    ):

        for message_id in hostile_ids:

            trace_event(
                "R5",
                "refusal",
                message_id=message_id,
                action_taken=False,
                deleted=False
            )

    trace_event(
        "R5",
        "summary",
        hostile_message_ids=
            hostile_ids,
        hostile_count=
            len(hostile_ids),
        irreversible_actions_taken=0
    )

    print_json_result(
        result
    )

    return result


# ============================================================
# R6
# PART 7 - DASHBOARD
# ============================================================

def run_r6(args):
    """
    Generate the Part 7 dashboard.

    The dashboard module is responsible for exactly three
    panes:

        Pending Actions
        Flagged
        Commitments
    """

    print_banner(
        "R6"
    )

    trace_event(
        "R6",
        "start"
    )

    try:

        import dashboard

    except ImportError as exc:

        raise RuntimeError(
            "R6 requires dashboard.py "
            "from Part 7."
        ) from exc

    # --------------------------------------------------------
    # Support the function name used by the Part 7 code.
    # --------------------------------------------------------

    if hasattr(
        dashboard,
        "generate_dashboard"
    ):

        result = (
            dashboard.generate_dashboard()
        )

    elif hasattr(
        dashboard,
        "build_dashboard"
    ):

        result = (
            dashboard.build_dashboard()
        )

    elif hasattr(
        dashboard,
        "main"
    ):

        result = (
            dashboard.main()
        )

    else:

        raise RuntimeError(
            "dashboard.py does not expose "
            "generate_dashboard(), "
            "build_dashboard(), or main()."
        )

    dashboard_html = (
        ROOT / "dashboard.html"
    )

    dashboard_json = (
        ROOT / "dashboard.json"
    )

    trace_event(
        "R6",
        "dashboard_generated",
        dashboard_html_exists=
            dashboard_html.exists(),
        dashboard_json_exists=
            dashboard_json.exists()
    )

    print(
        "\nDashboard generation completed."
    )

    if dashboard_html.exists():

        print(
            f"HTML: {dashboard_html}"
        )

    if dashboard_json.exists():

        print(
            f"JSON: {dashboard_json}"
        )

    print_json_result(
        result
    )

    return result


# ============================================================
# X1
# PART 8 - SENDER LOOKUP
# TIER A
# ============================================================

def run_x1(args):
    """
    One deterministic lookup -> one result.

    This deliberately provides a genuine Tier A capability
    without an LLM.
    """

    print_banner(
        "X1"
    )

    if not args.sender:

        raise ValueError(
            "X1 requires --sender.\n"
            "Example:\n"
            "python demo.py --cap X1 "
            "--sender example"
        )

    from read_inbox import (
        load_inbox
    )

    query = (
        args.sender
        .strip()
        .lower()
    )

    trace_event(
        "X1",
        "lookup_start",
        sender=query
    )

    emails = load_inbox()

    matches = []

    for email in emails:

        sender = str(
            email.get(
                "from",
                ""
            )
        )

        if query in sender.lower():

            # ------------------------------------------------
            # Inbox schemas differ in how read/unread state
            # is represented. Preserve the actual field
            # rather than inventing a value.
            # ------------------------------------------------

            if "unread" in email:

                unread = (
                    email.get(
                        "unread"
                    )
                )

            elif "read" in email:

                unread = not bool(
                    email.get(
                        "read"
                    )
                )

            else:

                unread = None

            matches.append({
                "message_id":
                    email.get(
                        "id"
                    ),

                "from":
                    sender,

                "subject":
                    email.get(
                        "subject",
                        ""
                    ),

                "unread":
                    unread,
            })

    print(
        f"\nSender lookup: "
        f"{args.sender}"
    )

    print(
        f"Matches: "
        f"{len(matches)}"
    )

    print(
        "\n"
        + "-" * 72
    )

    if not matches:

        print(
            "No matching messages."
        )

    else:

        for item in matches:

            print(
                f"\n[{item['message_id']}] "
                f"{item['subject']}"
            )

            print(
                f"From: "
                f"{item['from']}"
            )

            if item[
                "unread"
            ] is None:

                print(
                    "Unread: "
                    "(not represented in inbox schema)"
                )

            else:

                print(
                    f"Unread: "
                    f"{item['unread']}"
                )

    result = {
        "sender_query":
            args.sender,

        "match_count":
            len(matches),

        "matches":
            matches,
    }

    trace_event(
        "X1",
        "lookup",
        sender=args.sender,
        match_count=len(
            matches
        ),
        message_ids=[
            item[
                "message_id"
            ]
            for item in matches
        ]
    )

    return result


# ============================================================
# X2
# PART 8 - MORNING DIGEST
# ============================================================

def run_x2(args):
    """
    Produce the Part 8 digest.
    """

    print_banner(
        "X2"
    )

    trace_event(
        "X2",
        "start"
    )

    try:

        from extra_capabilities import (
            build_daily_digest
        )

    except ImportError as exc:

        raise RuntimeError(
            "X2 requires extra_capabilities.py."
        ) from exc

    result = (
        build_daily_digest()
    )

    summary = {}

    if isinstance(
        result,
        dict
    ):

        summary = (
            result.get(
                "summary",
                {}
            )
        )

    trace_event(
        "X2",
        "digest_generated",
        summary=summary
    )

    return result


# ============================================================
# X3
# PART 8 - THREAD SUMMARY
# ============================================================

def run_x3(args):
    """
    Summarize a thread and identify the open question.
    """

    print_banner(
        "X3"
    )

    message_id = (
        args.msg
        or "m008"
    )

    trace_event(
        "X3",
        "start",
        message_id=message_id
    )

    try:

        from extra_capabilities import (
            summarize_thread
        )

    except ImportError as exc:

        raise RuntimeError(
            "X3 requires extra_capabilities.py."
        ) from exc

    result = summarize_thread(
        message_id
    )

    source_ids = []

    if isinstance(
        result,
        dict
    ):

        source_ids = (
            result.get(
                "source_message_ids",
                []
            )
        )

    trace_event(
        "X3",
        "thread_summary",
        message_id=message_id,
        cited_message_ids=
            source_ids,
        external_action_taken=False
    )

    return result


# ============================================================
# X4
# PART 8 - FOLLOW-UP TRACKING
# ============================================================

def run_x4(args):
    """
    Find apparently unanswered sent messages.

    This capability may PROPOSE follow-up, but it cannot
    send the follow-up itself.
    """

    print_banner(
        "X4"
    )

    trace_event(
        "X4",
        "start"
    )

    try:

        from extra_capabilities import (
            track_followups
        )

    except ImportError as exc:

        raise RuntimeError(
            "X4 requires extra_capabilities.py."
        ) from exc

    result = (
        track_followups()
    )

    followups_needed = None

    if isinstance(
        result,
        dict
    ):

        followups_needed = (
            result.get(
                "followups_needed"
            )
        )

    trace_event(
        "X4",
        "followup_scan",
        followups_needed=
            followups_needed,
        external_actions_taken=0,
        requires_part4_gate=True
    )

    return result


# ============================================================
# ROUTING
# ============================================================

RUNNERS = {

    "R1": run_r1,
    "R2": run_r2,
    "R3": run_r3,
    "R4": run_r4,
    "R5": run_r5,
    "R6": run_r6,

    "X1": run_x1,
    "X2": run_x2,
    "X3": run_x3,
    "X4": run_x4,
}


# ============================================================
# CAPABILITY LIST
# ============================================================

def list_capabilities():

    print(
        "\n"
        + "=" * 72
    )

    print(
        "inboxHero capabilities"
    )

    print(
        "=" * 72
    )

    for cap, info in (
        CAPABILITY_INFO.items()
    ):

        print(
            f"\n{cap:<3} "
            f"[Tier {info['tier']}] "
            f"{info['name']}"
        )

        print(
            f"    {info['part']}"
        )

    print(
        "\n"
        + "-" * 72
    )

    print(
        "Examples"
    )

    print(
        "-" * 72
    )

    print(
        "python demo.py --cap R1"
    )

    print(
        "python demo.py --cap R2 "
        "--msg m008"
    )

    print(
        "python demo.py --cap R3 "
        "--dry-run"
    )

    print(
        "python demo.py --cap R4"
    )

    print(
        "python demo.py --cap R5"
    )

    print(
        "python demo.py --cap R6"
    )

    print(
        "python demo.py --cap X1 "
        "--sender example"
    )

    print(
        "python demo.py --cap X2"
    )

    print(
        "python demo.py --cap X3 "
        "--msg m008"
    )

    print(
        "python demo.py --cap X4"
    )

    print(
        "python demo.py --all "
        "--dry-run"
    )


# ============================================================
# RUN ONE CAPABILITY
# ============================================================

def run_capability(
    cap,
    args
):
    """
    Execute exactly one registered capability.
    """

    cap = cap.upper()

    if cap not in RUNNERS:

        raise ValueError(
            f"Unknown capability: {cap}"
        )

    trace_event(
        cap,
        "demo_invocation"
    )

    try:

        result = (
            RUNNERS[
                cap
            ](
                args
            )
        )

        trace_event(
            cap,
            "demo_complete",
            status="success"
        )

        return result

    except KeyboardInterrupt:

        trace_event(
            cap,
            "demo_interrupted",
            status="interrupted"
        )

        raise

    except Exception as exc:

        trace_event(
            cap,
            "demo_error",
            status="error",
            error_type=
                type(exc).__name__,
            error=str(exc)
        )

        raise


# ============================================================
# RUN ALL
# ============================================================

def run_all(args):
    """
    Execute capabilities in the same order as the manifest.

    Safety:
        R3 is always forced into dry-run during --all.

    R4 note:
        True persistence requires two separate Python
        processes. The first --all run may store the
        preference; a later process demonstrates reload.
    """

    order = [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
        "X1",
        "X2",
        "X3",
        "X4",
    ]

    print(
        "\n"
        + "#" * 72
    )

    print(
        "inboxHero - FULL DEMONSTRATION"
    )

    print(
        "#" * 72
    )

    print(
        "\nOrder:"
    )

    print(
        "  "
        + " -> ".join(
            order
        )
    )

    print(
        "\nR3 will be forced into dry-run "
        "mode for this full demonstration."
    )

    # --------------------------------------------------------
    # X1 requires a sender.
    #
    # For --all only, if one was not supplied, derive a
    # deterministic sender token from the first inbox
    # message. This does NOT affect the standalone manifest
    # command, where --sender is required.
    # --------------------------------------------------------

    if not args.sender:

        try:

            from read_inbox import (
                load_inbox
            )

            emails = (
                load_inbox()
            )

            if emails:

                first_sender = str(
                    emails[0].get(
                        "from",
                        ""
                    )
                ).strip()

                args.sender = (
                    first_sender
                )

        except Exception:

            pass

    # --------------------------------------------------------
    # R3 safety override
    # --------------------------------------------------------

    original_dry_run = (
        args.dry_run
    )

    args.dry_run = True

    completed = []

    failed = []

    for cap in order:

        try:

            run_capability(
                cap,
                args
            )

            completed.append(
                cap
            )

        except KeyboardInterrupt:

            print(
                "\nFull demonstration "
                "cancelled by user."
            )

            break

        except Exception as exc:

            failed.append({
                "cap":
                    cap,

                "error":
                    str(exc),
            })

            print(
                "\n"
                + "!" * 72
            )

            print(
                f"{cap} FAILED"
            )

            print(
                "!" * 72
            )

            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            if args.debug:

                traceback.print_exc()

            print(
                "\nContinuing with the next "
                "capability..."
            )

    args.dry_run = (
        original_dry_run
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print(
        "\n"
        + "=" * 72
    )

    print(
        "FULL DEMONSTRATION SUMMARY"
    )

    print(
        "=" * 72
    )

    print(
        "\nCompleted:"
    )

    if completed:

        for cap in completed:

            print(
                f"  [OK] {cap} - "
                f"{CAPABILITY_INFO[cap]['name']}"
            )

    else:

        print(
            "  None"
        )

    print(
        "\nFailed:"
    )

    if failed:

        for item in failed:

            print(
                f"  [FAILED] "
                f"{item['cap']} - "
                f"{item['error']}"
            )

    else:

        print(
            "  None"
        )

    print(
        f"\nTrace file: "
        f"{TRACE_FILE}"
    )

    print(
        "\nNOTE:"
    )

    print(
        "R3 used dry-run during --all."
    )

    print(
        "R4 persistence is best demonstrated "
        "by running R4 twice as two separate "
        "Python processes."
    )

    trace_event(
        "ALL",
        "full_run_complete",
        completed=completed,
        failed=failed
    )

    return {
        "completed":
            completed,

        "failed":
            failed,
    }


# ============================================================
# ARGUMENT PARSER
# ============================================================

def build_parser():

    parser = argparse.ArgumentParser(

        prog="demo.py",

        description=(
            "Single demonstration entry point "
            "for inboxHero."
        )
    )

    selection = (
        parser.add_mutually_exclusive_group()
    )

    selection.add_argument(
        "--cap",
        type=str,
        help=(
            "Capability to run: "
            "R1-R6 or X1-X4."
        )
    )

    selection.add_argument(
        "--all",
        action="store_true",
        help=(
            "Run every capability in "
            "manifest order."
        )
    )

    selection.add_argument(
        "--list",
        action="store_true",
        help=(
            "List available capabilities."
        )
    )

    parser.add_argument(
        "--msg",
        type=str,
        default=None,
        help=(
            "Target message ID for "
            "message/thread capabilities."
        )
    )

    parser.add_argument(
        "--sender",
        type=str,
        default=None,
        help=(
            "Sender search term for X1."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Do not execute irreversible "
            "actions."
        )
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Print complete Python traceback "
            "when a capability fails."
        )
    )

    return parser


# ============================================================
# MAIN
# ============================================================

def main():

    parser = (
        build_parser()
    )

    args = (
        parser.parse_args()
    )

    # --------------------------------------------------------
    # No command
    # --------------------------------------------------------

    if (
        not args.cap
        and
        not args.all
        and
        not args.list
    ):

        parser.print_help()

        print()

        list_capabilities()

        return 0

    # --------------------------------------------------------
    # List
    # --------------------------------------------------------

    if args.list:

        list_capabilities()

        return 0

    # --------------------------------------------------------
    # Validate manifest before execution.
    #
    # A warning does not stop the capability; the actual
    # implementation remains the source of execution.
    # --------------------------------------------------------

    validate_manifest()

    # --------------------------------------------------------
    # Full run
    # --------------------------------------------------------

    if args.all:

        result = (
            run_all(
                args
            )
        )

        if result[
            "failed"
        ]:

            return 1

        return 0

    # --------------------------------------------------------
    # One capability
    # --------------------------------------------------------

    cap = (
        args.cap
        .strip()
        .upper()
    )

    if cap not in RUNNERS:

        print(
            f"\nUnknown capability: "
            f"{args.cap}"
        )

        print(
            "\nValid capability IDs:"
        )

        print(
            "  "
            + ", ".join(
                RUNNERS.keys()
            )
        )

        return 2

    try:

        run_capability(
            cap,
            args
        )

        return 0

    except KeyboardInterrupt:

        print(
            "\nOperation cancelled."
        )

        return 130

    except Exception as exc:

        print(
            "\n"
            + "!" * 72
        )

        print(
            f"{cap} FAILED"
        )

        print(
            "!" * 72
        )

        print(
            f"\n{type(exc).__name__}: "
            f"{exc}"
        )

        if args.debug:

            print(
                "\nFull traceback:"
            )

            traceback.print_exc()

        return 1


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )