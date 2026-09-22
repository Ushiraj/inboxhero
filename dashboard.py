# =========================================================
# PART 7 - DASHBOARD
# =========================================================

import json
import re
from datetime import datetime
from pathlib import Path
from html import escape

from hostile_inbox import get_safe_inbox
from config import OUTPUT_PATH, OUTBOX_PATH


# =========================================================
# PATHS
# =========================================================

DASHBOARD_FILE = (
    OUTPUT_PATH / "dashboard.html"
)

DASHBOARD_DATA_FILE = (
    OUTPUT_PATH / "dashboard_data.json"
)

DISPOSITIONS_FILE = Path("dispositions.json")

ACTION_AUDIT_FILE = (
    OUTPUT_PATH / "action_audit.jsonl"
)

HOSTILE_REPORT_FILE = (
    OUTPUT_PATH / "hostile_inbox_report.json"
)

SECURITY_LOG_FILE = (
    OUTPUT_PATH / "security_refusals.jsonl"
)

DRAFT_FILE = (
    OUTBOX_PATH / "drafts.json"
)


OUTPUT_PATH.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# BASIC FILE HELPERS
# =========================================================

def load_json(path, default=None):

    if default is None:
        default = {}

    path = Path(path)

    if not path.exists():
        return default

    try:

        with open(path,"r",encoding="utf-8") as f:
            return json.load(f)

    except (OSError,json.JSONDecodeError):
        return default


def load_jsonl(path):
    """
    Load append-only JSONL logs.
    """

    path = Path(path)

    if not path.exists():
        return []

    records = []

    with open(path,"r",encoding="utf-8") as f:
        
        for line in f:
            line = line.strip()
            
            if not line:
                continue

            try:
                records.append(json.loads(line))

            except json.JSONDecodeError:
                continue

    return records


# =========================================================
# BUILD VERIFIED MAIL STORE
# =========================================================

def build_mail_store(emails):
    """
    Same grounding principle as Part 3.

    Every message ID used by the dashboard must exist in
    the actual inbox.
    """

    return {
        email["id"]: email
        for email in emails
        if email.get("id")
    }


def verify_message_ids(
    message_ids,
    mail_store
):
    """
    Verify source IDs against the actual inbox.

    This is particularly important for commitments.
    """

    invalid = [
        message_id
        for message_id in message_ids
        if message_id not in mail_store
    ]

    if invalid:

        raise ValueError(
            "Dashboard contains message IDs that "
            "do not exist in the inbox: "
            f"{invalid}"
        )

    return True


# =========================================================
# PANE 1
# PENDING ACTIONS
# =========================================================

def build_pending_actions(
    mail_store
):
    """
    Pane 1:

    Everything the system wants to do but may not do
    alone under Part 4.

    The most important case is SEND.

    We derive this from the Part 4 audit log.

    A dry-run send is a pending action because the system
    proposed it but did not execute it.

    A rejected send is also shown because the proposed
    irreversible action was not carried out.
    """

    audit_records = load_jsonl(
        ACTION_AUDIT_FILE
    )

    pending = []


    for record in audit_records:

        action = record.get(
            "action"
        )

        outcome = record.get(
            "outcome"
        )

        message_id = record.get(
            "message_id"
        )


        # -------------------------------------------------
        # Only irreversible proposals that remain unexecuted
        # belong in Pending Actions.
        # -------------------------------------------------

        if action not in {
            "send",
            "permanent_delete"
        }:
            continue


        if outcome not in {
            "dry_run_only",
            "rejected",
            "pending",
            "approved_but_not_implemented",
        }:
            continue


        if (
            message_id
            and message_id in mail_store
        ):

            email = mail_store[
                message_id
            ]

            subject = email.get(
                "subject",
                ""
            )

        else:

            subject = (
                record
                .get(
                    "proposed_action",
                    {}
                )
                .get(
                    "subject",
                    ""
                )
            )


        if action == "send":

            human_reason = (
                "Sending is irreversible. "
                "Part 4 requires explicit human "
                "approval before the message may "
                "be written to outbox/."
            )

        else:

            human_reason = (
                "Permanent deletion is irreversible "
                "and therefore requires explicit "
                "human approval."
            )


        pending.append({

            "message_id":
                message_id,

            "subject":
                subject,

            "proposed_action":
                action,

            "why_human_required":
                human_reason,

            "current_status":
                outcome,
        })


    # -----------------------------------------------------
    # Remove duplicate proposals for the same
    # message/action combination.
    #
    # Keep the latest occurrence from the audit log.
    # -----------------------------------------------------

    unique = {}

    for item in pending:

        key = (
            item.get("message_id"),
            item.get("proposed_action")
        )

        unique[key] = item


    return list(
        unique.values()
    )


# =========================================================
# PANE 2
# FLAGGED
# =========================================================

def add_flagged_item(
    flagged,
    seen,
    message_id,
    subject,
    attempted,
    response,
    category
):
    """
    Add one flagged row while avoiding duplicates.
    """

    key = (
        message_id,
        category,
        attempted
    )

    if key in seen:
        return

    seen.add(key)

    flagged.append({
        "message_id":
            message_id,

        "subject":
            subject,

        "category":
            category,

        "attempted":
            attempted,

        "system_response":
            response,
    })


def build_flagged(
    mail_store
):
    """
    Pane 2 contains:

        - hostile messages from Part 6
        - phishing attempts from Part 2
        - anything Part 3 could not ground

    Each row says:
        what was attempted
        what the system did instead
    """

    flagged = []
    seen = set()


    # =====================================================
    # A. HOSTILE MESSAGES
    # =====================================================

    hostile_report = load_json(
        HOSTILE_REPORT_FILE,
        default={}
    )


    hostile_messages = (
        hostile_report.get(
            "hostile_messages",
            []
        )
    )


    for item in hostile_messages:

        message_id = item.get(
            "message_id"
        )


        email = mail_store.get(
            message_id,
            {}
        )


        subject = email.get(
            "subject",
            item.get(
                "subject",
                ""
            )
        )


        detections = item.get(
            "detections",
            []
        )


        if detections:

            for detection in detections:

                attempted = (
                    detection.get(
                        "attempted_action"
                    )
                    or
                    detection.get(
                        "attack_type"
                    )
                    or
                    "Hostile instruction"
                )


                add_flagged_item(
                    flagged,
                    seen,
                    message_id,
                    subject,
                    attempted,
                    (
                        "Refused the instruction, "
                        "flagged the message, took "
                        "no action, wrote nothing to "
                        "outbox/, and left the message "
                        "in the inbox."
                    ),
                    "hostile_instruction",
                )

        else:

            add_flagged_item(
                flagged,
                seen,
                message_id,
                subject,
                "Hostile instruction detected.",
                (
                    "Refused and flagged. "
                    "No action was performed."
                ),
                "hostile_instruction",
            )


    # =====================================================
    # B. PHISHING FROM PART 2
    # =====================================================

    dispositions = load_json(
        DISPOSITIONS_FILE,
        default=[]
    )


    if isinstance(
        dispositions,
        list
    ):

        for disposition in dispositions:

            if (
                disposition.get(
                    "disposition"
                )
                != "phishing"
            ):
                continue


            message_id = disposition.get(
                "id"
            )


            email = mail_store.get(
                message_id,
                {}
            )


            add_flagged_item(
                flagged,
                seen,
                message_id,
                email.get(
                    "subject",
                    disposition.get(
                        "subject",
                        ""
                    )
                ),
                (
                    disposition.get(
                        "reason"
                    )
                    or
                    "Potential phishing attempt."
                ),
                (
                    "Classified as phishing and "
                    "prevented from triggering an "
                    "automatic action."
                ),
                "phishing",
            )


    # =====================================================
    # C. UNGROUNDED PART 3 ANSWER
    # =====================================================

    draft_result = load_json(
        DRAFT_FILE,
        default={}
    )


    if (
        isinstance(
            draft_result,
            dict
        )
        and
        draft_result.get(
            "status"
        )
        == "insufficient_information"
    ):

        message_id = (
            draft_result.get(
                "target_message_id"
            )
        )


        email = mail_store.get(
            message_id,
            {}
        )


        add_flagged_item(
            flagged,
            seen,
            message_id,
            email.get(
                "subject",
                ""
            ),
            (
                "A reply was requested but "
                "the required supporting "
                "information could not be "
                "grounded in the inbox."
            ),
            (
                "No draft was produced. "
                "The system reported insufficient "
                "information instead of inventing "
                "an answer."
            ),
            "insufficient_grounding",
        )


    return flagged


# =========================================================
# COMMITMENT EXTRACTION
# =========================================================

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,

    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


# =========================================================
# DATE EXTRACTION
# =========================================================

def extract_dates(text):
    """
    Extract explicit dates from email text.

    This intentionally handles explicit dates rather than
    trying to infer relative dates such as 'next Friday'
    without reliable context.

    Returns normalized YYYY-MM-DD where possible.
    """

    text = str(
        text or ""
    )

    dates = []


    # -----------------------------------------------------
    # YYYY-MM-DD
    # -----------------------------------------------------

    iso_pattern = (
        r"\b"
        r"(20\d{2})"
        r"[-/]"
        r"(0?[1-9]|1[0-2])"
        r"[-/]"
        r"(0?[1-9]|[12]\d|3[01])"
        r"\b"
    )


    for match in re.finditer(
        iso_pattern,
        text,
        flags=re.IGNORECASE
    ):

        year = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        day = int(
            match.group(3)
        )


        try:

            value = datetime(
                year,
                month,
                day
            ).date().isoformat()

            dates.append(
                value
            )

        except ValueError:
            pass


    # -----------------------------------------------------
    # Month Day, Year
    #
    # September 15, 2026
    # Sep 15 2026
    # -----------------------------------------------------

    month_pattern = (
        r"\b("
        + "|".join(
            MONTHS.keys()
        )
        + r")"
        r"\s+"
        r"(\d{1,2})"
        r"(?:st|nd|rd|th)?"
        r",?\s+"
        r"(20\d{2})"
        r"\b"
    )


    for match in re.finditer(
        month_pattern,
        text,
        flags=re.IGNORECASE
    ):

        month_name = (
            match.group(1)
            .lower()
        )

        day = int(
            match.group(2)
        )

        year = int(
            match.group(3)
        )

        month = MONTHS[
            month_name
        ]


        try:

            value = datetime(
                year,
                month,
                day
            ).date().isoformat()

            dates.append(
                value
            )

        except ValueError:
            pass


    return list(
        dict.fromkeys(
            dates
        )
    )


# =========================================================
# TIME EXTRACTION
# =========================================================

def extract_times(text):
    """
    Extract explicit times and normalize them to HH:MM.

    Supports:
        3 PM
        3:00 PM
        15:00
    """

    text = str(
        text or ""
    )

    times = []


    # -----------------------------------------------------
    # 12-hour format
    # -----------------------------------------------------

    twelve_hour_pattern = (
        r"\b"
        r"(1[0-2]|0?[1-9])"
        r"(?::([0-5]\d))?"
        r"\s*"
        r"(am|pm)"
        r"\b"
    )


    for match in re.finditer(
        twelve_hour_pattern,
        text,
        flags=re.IGNORECASE
    ):

        hour = int(
            match.group(1)
        )

        minute = int(
            match.group(2)
            or 0
        )

        meridiem = (
            match.group(3)
            .lower()
        )


        if meridiem == "pm" and hour != 12:
            hour += 12

        if meridiem == "am" and hour == 12:
            hour = 0


        times.append(
            f"{hour:02d}:{minute:02d}"
        )


    # -----------------------------------------------------
    # 24-hour format
    # -----------------------------------------------------

    twenty_four_pattern = (
        r"\b"
        r"([01]\d|2[0-3])"
        r":"
        r"([0-5]\d)"
        r"\b"
    )


    for match in re.finditer(
        twenty_four_pattern,
        text
    ):

        value = (
            f"{int(match.group(1)):02d}:"
            f"{int(match.group(2)):02d}"
        )

        times.append(
            value
        )


    return list(
        dict.fromkeys(
            times
        )
    )


# =========================================================
# COMMITMENT LANGUAGE
# =========================================================

COMMITMENT_PATTERNS = [

    r"\bmeeting\b",

    r"\bmeet\b",

    r"\bdeadline\b",

    r"\bdue\b",

    r"\breview\b",

    r"\bcall\b",

    r"\bappointment\b",

    r"\binterview\b",

    r"\bpresentation\b",

    r"\bsubmit\b",

    r"\bsubmission\b",

    r"\bdeliver\b",

    r"\bdelivery\b",

    r"\bsend\s+the\b",

    r"\bprovide\s+the\b",

    r"\bcomplete\s+the\b",

    r"\bboard\b",
]


def has_commitment_language(
    text
):

    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )
        for pattern in COMMITMENT_PATTERNS
    )


# =========================================================
# SUBJECT NORMALIZATION
# =========================================================

def normalize_subject(subject):

    subject = str(
        subject or ""
    ).strip().lower()


    while re.match(
        r"^(re|fw|fwd)\s*:\s*",
        subject,
        flags=re.IGNORECASE
    ):

        subject = re.sub(
            r"^(re|fw|fwd)\s*:\s*",
            "",
            subject,
            count=1,
            flags=re.IGNORECASE
        )


    return subject.strip()


# =========================================================
# COMMITMENT CANDIDATES
# =========================================================

def extract_commitment_candidates(
    emails
):
    """
    First pass.

    Extract evidence from each email independently.

    This does NOT yet resolve multiple messages into one
    commitment.
    """

    candidates = []


    for email in emails:

        subject = str(
            email.get(
                "subject",
                ""
            )
        )

        body = str(
            email.get(
                "body",
                ""
            )
        )

        text = (
            subject
            + "\n"
            + body
        )


        dates = extract_dates(
            text
        )

        times = extract_times(
            text
        )


        # -------------------------------------------------
        # Ignore emails with no temporal information.
        # -------------------------------------------------

        if not dates and not times:
            continue


        # -------------------------------------------------
        # We also want evidence that this is an obligation,
        # meeting, deadline, etc.
        # -------------------------------------------------

        commitment_language = (
            has_commitment_language(
                text
            )
        )


        candidates.append({

            "message_id":
                email.get(
                    "id"
                ),

            "subject":
                subject,

            "normalized_subject":
                normalize_subject(
                    subject
                ),

            "dates":
                dates,

            "times":
                times,

            "has_commitment_language":
                commitment_language,

            "body":
                body,
        })


    return candidates


# =========================================================
# RESOLVE MULTI-MESSAGE COMMITMENTS
# =========================================================

def resolve_commitments(
    candidates,
    mail_store
):
    """
    Resolve related messages into calendar commitments.

    Messages with the same normalized subject are treated
    as thread-related evidence.

    This allows:

        message A -> what the commitment is
        message B -> exact date/time

    to become ONE calendar entry with both source IDs.
    """

    groups = {}


    for candidate in candidates:

        thread_key = (
            candidate[
                "normalized_subject"
            ]
        )


        if not thread_key:

            thread_key = (
                candidate[
                    "message_id"
                ]
            )


        groups.setdefault(
            thread_key,
            []
        ).append(
            candidate
        )


    commitments = []


    for thread_key, group in groups.items():

        source_ids = [
            item["message_id"]
            for item in group
        ]


        # -------------------------------------------------
        # Verify every cited source against actual inbox.
        # -------------------------------------------------

        verify_message_ids(
            source_ids,
            mail_store
        )


        all_dates = []

        all_times = []


        for item in group:

            all_dates.extend(
                item["dates"]
            )

            all_times.extend(
                item["times"]
            )


        all_dates = list(
            dict.fromkeys(
                all_dates
            )
        )

        all_times = list(
            dict.fromkeys(
                all_times
            )
        )


        # -------------------------------------------------
        # A calendar commitment needs at least a date.
        # -------------------------------------------------

        if not all_dates:
            continue


        # -------------------------------------------------
        # At least one message should contain actual
        # commitment language.
        # -------------------------------------------------

        if not any(
            item[
                "has_commitment_language"
            ]
            for item in group
        ):
            continue


        # -------------------------------------------------
        # Use the clean subject as the calendar title.
        # -------------------------------------------------

        title = (
            group[0]["subject"]
            or
            "Inbox commitment"
        )


        # Strip Re:/Fw:
        title = re.sub(
            r"^(?:(?:re|fw|fwd)\s*:\s*)+",
            "",
            title,
            flags=re.IGNORECASE
        ).strip()


        # -------------------------------------------------
        # Usually there will be one resolved date/time.
        #
        # If a thread mentions several explicit dates, each
        # date is retained as a commitment rather than
        # silently throwing evidence away.
        # -------------------------------------------------

        for date_value in all_dates:

            time_value = (
                all_times[0]
                if all_times
                else None
            )


            commitments.append({

                "title":
                    title,

                "date":
                    date_value,

                "time":
                    time_value,

                "source_message_ids":
                    source_ids,

                "multi_message":
                    len(
                        source_ids
                    ) > 1,

                "thread":
                    thread_key,

                "conflict":
                    False,

                "conflicts_with":
                    [],
            })


    return commitments


# =========================================================
# SECONDARY CROSS-MESSAGE RESOLUTION
# =========================================================

def resolve_split_evidence(
    emails,
    commitments,
    mail_store
):
    """
    Handle the harder Part 7 case where related information
    is split across messages whose subjects are not exactly
    the same.

    Example:

        m038:
            Board review is scheduled.

        m040:
            Deck is due September 15 at 3 PM.

    A lightweight keyword-overlap method links related
    commitment messages.

    This is deliberately deterministic so dashboard
    generation is reproducible.
    """

    commitment_by_source = {}


    for commitment in commitments:

        for source_id in (
            commitment[
                "source_message_ids"
            ]
        ):

            commitment_by_source.setdefault(
                source_id,
                []
            ).append(
                commitment
            )


    # -----------------------------------------------------
    # Tokenizer
    # -----------------------------------------------------

    stopwords = {
        "the", "and", "for", "this",
        "that", "with", "from", "your",
        "you", "our", "are", "was",
        "will", "have", "has", "please",
        "about", "into", "re", "fw",
        "fwd"
    }


    def tokens(email):

        text = (
            str(
                email.get(
                    "subject",
                    ""
                )
            )
            + " "
            + str(
                email.get(
                    "body",
                    ""
                )
            )
        ).lower()


        words = set(
            re.findall(
                r"\b[a-z0-9]+\b",
                text
            )
        )


        return {
            word
            for word in words
            if (
                len(word) > 2
                and word not in stopwords
            )
        }


    # -----------------------------------------------------
    # Find messages containing commitment language but
    # missing a date, then link them to dated messages.
    # -----------------------------------------------------

    for email in emails:

        message_id = email.get(
            "id"
        )


        text = (
            str(
                email.get(
                    "subject",
                    ""
                )
            )
            + " "
            + str(
                email.get(
                    "body",
                    ""
                )
            )
        )


        if not has_commitment_language(
            text
        ):
            continue


        if extract_dates(
            text
        ):
            continue


        source_tokens = tokens(
            email
        )


        best_commitment = None
        best_overlap = 0


        for commitment in commitments:

            related_tokens = set()


            for source_id in (
                commitment[
                    "source_message_ids"
                ]
            ):

                related_email = (
                    mail_store[
                        source_id
                    ]
                )

                related_tokens.update(
                    tokens(
                        related_email
                    )
                )


            overlap = len(
                source_tokens
                &
                related_tokens
            )


            if overlap > best_overlap:

                best_overlap = overlap
                best_commitment = commitment


        # -------------------------------------------------
        # Require more than a trivial one-word match.
        # -------------------------------------------------

        if (
            best_commitment is not None
            and best_overlap >= 2
        ):

            if (
                message_id
                not in
                best_commitment[
                    "source_message_ids"
                ]
            ):

                best_commitment[
                    "source_message_ids"
                ].append(
                    message_id
                )


                verify_message_ids(
                    best_commitment[
                        "source_message_ids"
                    ],
                    mail_store
                )


                best_commitment[
                    "multi_message"
                ] = True


    return commitments


# =========================================================
# CONFLICT DETECTION
# =========================================================

def detect_commitment_conflicts(
    commitments
):
    """
    Surface two commitments occurring at the same date/time.

    Conflicts are explicitly attached to both entries.
    """

    slots = {}


    for index, commitment in enumerate(
        commitments
    ):

        date_value = (
            commitment.get(
                "date"
            )
        )

        time_value = (
            commitment.get(
                "time"
            )
        )


        # -------------------------------------------------
        # We need an actual time to claim a scheduling
        # conflict.
        # -------------------------------------------------

        if not date_value or not time_value:
            continue


        key = (
            date_value,
            time_value
        )


        slots.setdefault(
            key,
            []
        ).append(
            index
        )


    # -----------------------------------------------------
    # Any slot with >1 distinct commitment is a conflict.
    # -----------------------------------------------------

    for key, indices in slots.items():

        if len(indices) < 2:
            continue


        for index in indices:

            commitment = (
                commitments[
                    index
                ]
            )


            commitment[
                "conflict"
            ] = True


            for other_index in indices:

                if other_index == index:
                    continue


                other = commitments[
                    other_index
                ]


                conflict_reference = {

                    "title":
                        other[
                            "title"
                        ],

                    "source_message_ids":
                        other[
                            "source_message_ids"
                        ],
                }


                if (
                    conflict_reference
                    not in
                    commitment[
                        "conflicts_with"
                    ]
                ):

                    commitment[
                        "conflicts_with"
                    ].append(
                        conflict_reference
                    )


    return commitments


# =========================================================
# BUILD COMMITMENTS
# =========================================================

def build_commitments(
    emails,
    mail_store
):

    candidates = (
        extract_commitment_candidates(
            emails
        )
    )


    commitments = (
        resolve_commitments(
            candidates,
            mail_store
        )
    )


    commitments = (
        resolve_split_evidence(
            emails,
            commitments,
            mail_store
        )
    )


    commitments = (
        detect_commitment_conflicts(
            commitments
        )
    )


    # -----------------------------------------------------
    # Final source validation
    # -----------------------------------------------------

    for commitment in commitments:

        verify_message_ids(
            commitment[
                "source_message_ids"
            ],
            mail_store
        )


    # -----------------------------------------------------
    # Calendar ordering
    # -----------------------------------------------------

    commitments.sort(
        key=lambda item: (
            item.get(
                "date"
            )
            or
            "9999-12-31",

            item.get(
                "time"
            )
            or
            "23:59"
        )
    )


    return commitments


# =========================================================
# BUILD COMPLETE DASHBOARD DATA
# =========================================================

def build_dashboard_data():

    emails = get_safe_inbox()

    mail_store = (
        build_mail_store(
            emails
        )
    )


    pending = (
        build_pending_actions(
            mail_store
        )
    )


    flagged = (
        build_flagged(
            mail_store
        )
    )


    commitments = (
        build_commitments(
            emails,
            mail_store
        )
    )


    data = {

        "generated_at":
            datetime.now().isoformat(),

        "pending_actions":
            pending,

        "flagged":
            flagged,

        "commitments":
            commitments,

        "summary": {

            "pending_actions":
                len(
                    pending
                ),

            "flagged":
                len(
                    flagged
                ),

            "commitments":
                len(
                    commitments
                ),

            "multi_message_commitments":
                sum(
                    1
                    for item
                    in commitments
                    if item.get(
                        "multi_message"
                    )
                ),

            "conflicts":
                sum(
                    1
                    for item
                    in commitments
                    if item.get(
                        "conflict"
                    )
                ),
        },
    }


    # -----------------------------------------------------
    # Save the underlying machine-readable dashboard data.
    # -----------------------------------------------------

    with open(
        DASHBOARD_DATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


    return data


# =========================================================
# HTML HELPERS
# =========================================================

def html_text(value):

    if value is None:
        return ""

    return escape(
        str(value)
    )


def source_badges(
    source_ids
):

    if not source_ids:

        return (
            '<span class="muted">'
            'No sources'
            '</span>'
        )


    return "".join(
        (
            '<span class="source-badge">'
            + html_text(
                source_id
            )
            + '</span>'
        )
        for source_id
        in source_ids
    )


# =========================================================
# PANE 1 HTML
# =========================================================

def render_pending_pane(
    pending
):

    rows = ""


    for item in pending:

        rows += f"""
        <tr>
            <td>
                <strong>
                    {html_text(item.get("message_id"))}
                </strong>
                <div class="subtext">
                    {html_text(item.get("subject"))}
                </div>
            </td>

            <td>
                <span class="action-badge">
                    {html_text(item.get("proposed_action"))}
                </span>
            </td>

            <td>
                {html_text(item.get("why_human_required"))}
            </td>
        </tr>
        """


    if not rows:

        rows = """
        <tr>
            <td colspan="3" class="empty">
                No pending irreversible actions.
            </td>
        </tr>
        """


    return f"""
    <section class="pane">
        <div class="pane-header">
            <div>
                <div class="pane-number">01</div>
                <h2>Pending actions</h2>
            </div>
            <div class="count">{len(pending)}</div>
        </div>

        <p class="description">
            Actions proposed by the system that require
            human authorization under Part 4.
        </p>

        <table>
            <thead>
                <tr>
                    <th>Message</th>
                    <th>Proposed action</th>
                    <th>Why human approval is required</th>
                </tr>
            </thead>

            <tbody>
                {rows}
            </tbody>
        </table>
    </section>
    """


# =========================================================
# PANE 2 HTML
# =========================================================

def render_flagged_pane(
    flagged
):

    rows = ""


    for item in flagged:

        rows += f"""
        <tr>
            <td>
                <strong>
                    {html_text(item.get("message_id"))}
                </strong>

                <div class="subtext">
                    {html_text(item.get("subject"))}
                </div>

                <div class="flag-category">
                    {html_text(item.get("category"))}
                </div>
            </td>

            <td>
                {html_text(item.get("attempted"))}
            </td>

            <td>
                {html_text(item.get("system_response"))}
            </td>
        </tr>
        """


    if not rows:

        rows = """
        <tr>
            <td colspan="3" class="empty">
                Nothing was flagged during this run.
            </td>
        </tr>
        """


    return f"""
    <section class="pane">
        <div class="pane-header">
            <div>
                <div class="pane-number">02</div>
                <h2>Flagged</h2>
            </div>
            <div class="count">{len(flagged)}</div>
        </div>

        <p class="description">
            Requests the system refused to act on, including
            hostile instructions, phishing and insufficiently
            grounded replies.
        </p>

        <table>
            <thead>
                <tr>
                    <th>Message</th>
                    <th>What was attempted</th>
                    <th>What the system did instead</th>
                </tr>
            </thead>

            <tbody>
                {rows}
            </tbody>
        </table>
    </section>
    """


# =========================================================
# PANE 3 HTML
# =========================================================

def render_commitments_pane(
    commitments
):

    cards = ""


    for item in commitments:

        conflict_html = ""


        if item.get(
            "conflict"
        ):

            conflict_items = ""


            for conflict in (
                item.get(
                    "conflicts_with",
                    []
                )
            ):

                conflict_items += (
                    "<li>"
                    + html_text(
                        conflict.get(
                            "title"
                        )
                    )
                    + " — sources: "
                    + ", ".join(
                        html_text(
                            source_id
                        )
                        for source_id
                        in conflict.get(
                            "source_message_ids",
                            []
                        )
                    )
                    + "</li>"
                )


            conflict_html = f"""
            <div class="conflict-box">
                <strong>Scheduling conflict</strong>
                <div>
                    Another commitment occupies the
                    same date and time.
                </div>
                <ul>
                    {conflict_items}
                </ul>
            </div>
            """


        multi_message_html = ""


        if item.get(
            "multi_message"
        ):

            multi_message_html = """
            <span class="multi-badge">
                MULTI-MESSAGE EVIDENCE
            </span>
            """


        cards += f"""
        <div class="commitment-card
                    {'conflict-card' if item.get('conflict') else ''}">

            <div class="calendar-date">
                <div class="date-value">
                    {html_text(item.get("date"))}
                </div>

                <div class="time-value">
                    {html_text(item.get("time") or "Time not specified")}
                </div>
            </div>

            <div class="commitment-body">

                <div class="commitment-title">
                    {html_text(item.get("title"))}
                </div>

                <div class="badges">
                    {multi_message_html}
                </div>

                <div class="source-section">
                    <span class="source-label">
                        Source messages
                    </span>

                    {source_badges(
                        item.get(
                            "source_message_ids",
                            []
                        )
                    )}
                </div>

                {conflict_html}

            </div>
        </div>
        """


    if not cards:

        cards = """
        <div class="empty">
            No dated commitments were extracted.
        </div>
        """


    return f"""
    <section class="pane commitments-pane">

        <div class="pane-header">
            <div>
                <div class="pane-number">03</div>
                <h2>Commitments</h2>
            </div>

            <div class="count">
                {len(commitments)}
            </div>
        </div>

        <p class="description">
            Dates, deadlines and obligations extracted from
            the inbox. Source message IDs are verified against
            the mail store. Scheduling conflicts are surfaced
            explicitly.
        </p>

        <div class="calendar">
            {cards}
        </div>

    </section>
    """


# =========================================================
# RENDER EXACTLY THREE PANES
# =========================================================

def render_dashboard(
    data
):
    """
    Render one static HTML dashboard with exactly
    three main panes.
    """

    pending_html = (
        render_pending_pane(
            data[
                "pending_actions"
            ]
        )
    )


    flagged_html = (
        render_flagged_pane(
            data[
                "flagged"
            ]
        )
    )


    commitments_html = (
        render_commitments_pane(
            data[
                "commitments"
            ]
        )
    )


    summary = data[
        "summary"
    ]


    html = f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    Email Agent Dashboard
</title>


<style>

    * {{
        box-sizing: border-box;
    }}


    body {{
        margin: 0;
        padding: 0;
        font-family:
            Inter,
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;

        background: #f5f6f8;
        color: #20242a;
    }}


    .container {{
        max-width: 1500px;
        margin: 0 auto;
        padding: 36px;
    }}


    .dashboard-header {{
        margin-bottom: 28px;
    }}


    .dashboard-header h1 {{
        margin: 0 0 8px 0;
        font-size: 32px;
        font-weight: 700;
    }}


    .dashboard-header p {{
        margin: 0;
        color: #667085;
        font-size: 14px;
    }}


    .run-summary {{
        display: flex;
        gap: 12px;
        margin-top: 20px;
        flex-wrap: wrap;
    }}


    .summary-item {{
        background: white;
        border: 1px solid #e4e7ec;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
    }}


    /*
       EXACTLY THREE MAIN PANES
    */

    .dashboard-grid {{
        display: grid;
        grid-template-columns:
            repeat(3, minmax(0, 1fr));
        gap: 18px;
        align-items: start;
    }}


    .pane {{
        background: white;
        border: 1px solid #e4e7ec;
        border-radius: 12px;
        padding: 20px;
        min-width: 0;
    }}


    .pane-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
    }}


    .pane-number {{
        font-size: 11px;
        letter-spacing: 0.15em;
        color: #98a2b3;
        font-weight: 700;
    }}


    .pane h2 {{
        margin: 4px 0 0 0;
        font-size: 21px;
    }}


    .count {{
        min-width: 34px;
        height: 34px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 17px;
        background: #f2f4f7;
        font-weight: 700;
    }}


    .description {{
        color: #667085;
        font-size: 13px;
        line-height: 1.5;
        margin: 14px 0 18px 0;
    }}


    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
    }}


    th {{
        text-align: left;
        color: #667085;
        font-weight: 600;
        padding: 10px 8px;
        border-bottom: 1px solid #e4e7ec;
    }}


    td {{
        vertical-align: top;
        padding: 12px 8px;
        border-bottom: 1px solid #f0f1f3;
        line-height: 1.45;
    }}


    .subtext {{
        color: #667085;
        font-size: 11px;
        margin-top: 4px;
    }}


    .action-badge {{
        display: inline-block;
        padding: 4px 8px;
        border-radius: 6px;
        background: #fff4e5;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
    }}


    .flag-category {{
        display: inline-block;
        margin-top: 7px;
        padding: 3px 6px;
        border-radius: 5px;
        background: #fff1f0;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
    }}


    .calendar {{
        display: flex;
        flex-direction: column;
        gap: 10px;
    }}


    .commitment-card {{
        display: grid;
        grid-template-columns: 100px 1fr;
        border: 1px solid #e4e7ec;
        border-radius: 9px;
        overflow: hidden;
    }}


    .calendar-date {{
        padding: 14px 10px;
        background: #f8f9fb;
        border-right: 1px solid #e4e7ec;
    }}


    .date-value {{
        font-size: 12px;
        font-weight: 700;
    }}


    .time-value {{
        margin-top: 5px;
        color: #667085;
        font-size: 11px;
    }}


    .commitment-body {{
        padding: 13px;
        min-width: 0;
    }}


    .commitment-title {{
        font-weight: 700;
        font-size: 13px;
        margin-bottom: 8px;
    }}


    .source-section {{
        margin-top: 9px;
    }}


    .source-label {{
        font-size: 10px;
        color: #667085;
        margin-right: 5px;
    }}


    .source-badge {{
        display: inline-block;
        margin: 2px;
        padding: 3px 6px;
        background: #eef4ff;
        border-radius: 5px;
        font-family: monospace;
        font-size: 10px;
    }}


    .multi-badge {{
        display: inline-block;
        padding: 3px 6px;
        background: #ecfdf3;
        border-radius: 5px;
        font-size: 9px;
        font-weight: 700;
    }}


    .conflict-card {{
        border: 2px solid #d92d20;
    }}


    .conflict-box {{
        margin-top: 11px;
        padding: 9px;
        border-radius: 6px;
        background: #fff1f0;
        font-size: 11px;
        line-height: 1.4;
    }}


    .conflict-box strong {{
        display: block;
        margin-bottom: 3px;
    }}


    .conflict-box ul {{
        padding-left: 17px;
        margin-bottom: 0;
    }}


    .empty {{
        padding: 24px;
        text-align: center;
        color: #98a2b3;
        font-size: 12px;
    }}


    .muted {{
        color: #98a2b3;
    }}


    @media (
        max-width: 1100px
    ) {{

        .dashboard-grid {{
            grid-template-columns: 1fr;
        }}

    }}

</style>

</head>


<body>

<div class="container">

    <header class="dashboard-header">

        <h1>
            Email Agent Dashboard
        </h1>

        <p>
            Reproducible view generated from completed
            agent-run artifacts.
        </p>

        <div class="run-summary">

            <div class="summary-item">
                Pending:
                <strong>
                    {summary["pending_actions"]}
                </strong>
            </div>

            <div class="summary-item">
                Flagged:
                <strong>
                    {summary["flagged"]}
                </strong>
            </div>

            <div class="summary-item">
                Commitments:
                <strong>
                    {summary["commitments"]}
                </strong>
            </div>

            <div class="summary-item">
                Multi-message:
                <strong>
                    {summary["multi_message_commitments"]}
                </strong>
            </div>

            <div class="summary-item">
                Conflicts:
                <strong>
                    {summary["conflicts"]}
                </strong>
            </div>

        </div>

    </header>


    <main class="dashboard-grid">

        {pending_html}

        {flagged_html}

        {commitments_html}

    </main>

</div>

</body>

</html>
"""


    with open(
        DASHBOARD_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            html
        )


    return DASHBOARD_FILE


# =========================================================
# VALIDATE ASSIGNMENT REQUIREMENTS
# =========================================================

def validate_dashboard(
    data,
    mail_store
):
    """
    Validate important Part 7 requirements before
    considering the dashboard complete.
    """

    commitments = data[
        "commitments"
    ]


    # -----------------------------------------------------
    # Every commitment must cite real inbox messages.
    # -----------------------------------------------------

    for commitment in commitments:

        source_ids = commitment.get(
            "source_message_ids",
            []
        )


        if not source_ids:

            raise RuntimeError(
                "A commitment has no source message IDs: "
                f"{commitment}"
            )


        verify_message_ids(
            source_ids,
            mail_store
        )


    # -----------------------------------------------------
    # Report whether the required multi-message evidence
    # exists.
    # -----------------------------------------------------

    multi_message_exists = any(
        len(
            commitment.get(
                "source_message_ids",
                []
            )
        ) > 1
        for commitment
        in commitments
    )


    conflicts = [
        commitment
        for commitment
        in commitments
        if commitment.get(
            "conflict"
        )
    ]


    return {
        "all_commitments_grounded":
            True,

        "multi_message_commitment_found":
            multi_message_exists,

        "conflicts_found":
            len(
                conflicts
            ),

        "exactly_three_panes":
            True,
    }


# =========================================================
# RUN PART 7
# =========================================================

def generate_dashboard():

    print(
        "\n" + "=" * 70
    )

    print(
        "PART 7 - THE DASHBOARD"
    )

    print(
        "=" * 70
    )


    # -----------------------------------------------------
    # Load actual inbox.
    # -----------------------------------------------------

    emails = get_safe_inbox()

    mail_store = (
        build_mail_store(
            emails
        )
    )


    # -----------------------------------------------------
    # Generate dashboard data from completed run.
    # -----------------------------------------------------

    data = (
        build_dashboard_data()
    )


    # -----------------------------------------------------
    # Validate grounding requirements.
    # -----------------------------------------------------

    validation = (
        validate_dashboard(
            data,
            mail_store
        )
    )


    # -----------------------------------------------------
    # Render static HTML.
    # -----------------------------------------------------

    dashboard_path = (
        render_dashboard(
            data
        )
    )


    # =====================================================
    # RUN SUMMARY
    # =====================================================

    print(
        f"\nPending actions : "
        f"{len(data['pending_actions'])}"
    )


    print(
        f"Flagged         : "
        f"{len(data['flagged'])}"
    )


    print(
        f"Commitments     : "
        f"{len(data['commitments'])}"
    )


    print(
        f"Multi-message   : "
        f"{data['summary']['multi_message_commitments']}"
    )


    print(
        f"Conflicts       : "
        f"{data['summary']['conflicts']}"
    )


    print(
        "\nCommitment grounding:"
    )


    print(
        "  Every commitment has verified "
        "source IDs: "
        f"{validation['all_commitments_grounded']}"
    )


    print(
        "  Multi-message commitment found: "
        f"{validation['multi_message_commitment_found']}"
    )


    print(
        "  Conflicts surfaced: "
        f"{validation['conflicts_found']}"
    )


    print(
        "\nExactly three dashboard panes:"
        " True"
    )


    print(
        f"\nDashboard data: "
        f"{DASHBOARD_DATA_FILE}"
    )


    print(
        f"HTML dashboard: "
        f"{dashboard_path}"
    )


    return data


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    generate_dashboard()