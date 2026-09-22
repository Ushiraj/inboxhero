# Name : Ushiraj Garg
# Roll no: evernorth-aai-1194540


# =========================================================
# PART 5 MEMORY
# Persistent Standing Instructions
# =========================================================

import json
from datetime import datetime, timezone
from pathlib import Path


# =========================================================
# MEMORY FILE
# =========================================================

MEMORY_FILE = (Path(__file__).resolve().parent / "memory_store.json")


# =========================================================
# TIME HELPER
# =========================================================

def current_timestamp():
    
    return datetime.now(timezone.utc).isoformat()


# =========================================================
# LOAD MEMORY
# =========================================================

def load_memory():
    """
    Load persistent standing instructions from disk.

    The file is read every time this function is called.
    Therefore preferences survive program termination
    and are available after a restart.
    """

    if not MEMORY_FILE.exists():

        return {"preferences": []}


    try:

        with open(MEMORY_FILE,"r",encoding="utf-8") as f:
            data = json.load(f)


        if not isinstance(data, dict):

            return {"preferences": []}


        if "preferences" not in data:

            data["preferences"] = []


        return data


    except (OSError,json.JSONDecodeError):

        return {"preferences": []}


# =========================================================
# SAVE MEMORY
# =========================================================

def save_memory(data):
    """
    Persist memory to disk.

    Because the preferences are written to a JSON file,
    they remain available after the Python process exits.
    """

    with open(MEMORY_FILE,"w",encoding="utf-8") as f:

        json.dump(data,f,indent=2,ensure_ascii=False)


# =========================================================
# NORMALIZATION
# =========================================================

def normalize(value):
    """
    Normalize strings used for matching.
    """

    return str(value or "").strip().lower()


# =========================================================
# STORE PREFERENCE
# =========================================================

def remember_preference(preference_type,value,action,source="owner"):
    """
    Store a persistent standing instruction.

    Examples:

    Correspondent preference:

        remember_preference(
            preference_type="correspondent",
            value="alice@example.com",
            action="always_reply"
        )

    CC preference:

        remember_preference(
            preference_type="cc_on_subject",
            value="Hartwell",
            action="priya@example.com"
        )

    Never-agree preference:

        remember_preference(
            preference_type="never_agree",
            value="automatic contract renewal",
            action="escalate"
        )

    If the same preference_type/value already exists,
    the newer instruction replaces it.
    """

    preference_type = normalize(preference_type)

    value = normalize(value)


    if not preference_type:

        raise ValueError("preference_type cannot be empty.")


    if not value:

        raise ValueError("preference value cannot be empty.")


    memory = load_memory()

    preferences = memory.get("preferences",[])


    # -----------------------------------------------------
    # Check whether the preference already exists.
    # -----------------------------------------------------

    existing = None


    for preference in preferences:

        if (normalize(preference.get("type")) == preference_type 
        and normalize(preference.get("value"))== value):
            existing = preference
            break


    preference_record = {
        "type":
            preference_type,

        "value":
            value,

        "action":
            action,

        "source":
            source,

        "updated_at":
            current_timestamp(),
    }


    # -----------------------------------------------------
    # Update existing preference
    # -----------------------------------------------------

    if existing is not None:

        existing.update(
            preference_record
        )

        status = "updated"


    # -----------------------------------------------------
    # Add new preference
    # -----------------------------------------------------

    else:

        preference_record[
            "created_at"
        ] = current_timestamp()

        preferences.append(
            preference_record
        )

        status = "stored"


    memory["preferences"] = (
        preferences
    )


    save_memory(
        memory
    )


    return {
        "status":
            status,

        "preference":
            preference_record,

        "memory_file":
            str(MEMORY_FILE),
    }


# =========================================================
# GET ALL PREFERENCES
# =========================================================

def get_preferences():
    """
    Return every persistent owner preference.
    """

    memory = load_memory()

    return memory.get(
        "preferences",
        []
    )


# =========================================================
# FIND PREFERENCES FOR AN EMAIL
# =========================================================

def find_matching_preferences(email):
    """
    Find standing instructions that apply to an email.

    Supported preference types:

    correspondent
        Match against sender email address.

    subject_contains
        Match text appearing in the subject.

    body_contains
        Match text appearing in the body.

    cc_on_subject
        Match a topic in the subject and return the
        person who should be copied.

    never_agree
        Match prohibited commitments/topics appearing
        in either subject or body.
    """

    preferences = (
        get_preferences()
    )


    sender = normalize(
        email.get(
            "from"
        )
    )

    subject = normalize(
        email.get(
            "subject"
        )
    )

    body = normalize(
        email.get(
            "body"
        )
    )


    full_text = (
        subject
        + " "
        + body
    )


    matches = []


    for preference in preferences:

        preference_type = normalize(
            preference.get(
                "type"
            )
        )

        value = normalize(
            preference.get(
                "value"
            )
        )


        matched = False


        # -------------------------------------------------
        # Correspondent preference
        # -------------------------------------------------

        if preference_type == "correspondent":

            matched = (
                value in sender
            )


        # -------------------------------------------------
        # Subject preference
        # -------------------------------------------------

        elif (
            preference_type
            == "subject_contains"
        ):

            matched = (
                value in subject
            )


        # -------------------------------------------------
        # Body preference
        # -------------------------------------------------

        elif (
            preference_type
            == "body_contains"
        ):

            matched = (
                value in body
            )


        # -------------------------------------------------
        # CC instruction
        # -------------------------------------------------

        elif (
            preference_type
            == "cc_on_subject"
        ):

            matched = (
                value in subject
            )


        # -------------------------------------------------
        # Never agree instruction
        # -------------------------------------------------

        elif (
            preference_type
            == "never_agree"
        ):

            matched = (
                value in full_text
            )


        if matched:

            matches.append(
                preference
            )


    return matches


# =========================================================
# DELETE PREFERENCE
# =========================================================

def forget_preference(
    preference_type,
    value
):
    """
    Remove one standing instruction.

    This is useful if the owner later changes their mind.
    """

    preference_type = normalize(
        preference_type
    )

    value = normalize(
        value
    )


    memory = load_memory()

    preferences = memory.get(
        "preferences",
        []
    )


    remaining = []

    removed = []


    for preference in preferences:

        if (
            normalize(
                preference.get(
                    "type"
                )
            )
            == preference_type
            and
            normalize(
                preference.get(
                    "value"
                )
            )
            == value
        ):

            removed.append(
                preference
            )

        else:

            remaining.append(
                preference
            )


    memory["preferences"] = (
        remaining
    )


    save_memory(
        memory
    )


    return {
        "status":
            "removed"
            if removed
            else "not_found",

        "removed":
            removed,
    }


# =========================================================
# MEMORY SUMMARY
# =========================================================

def memory_summary():
    """
    Human-readable summary of persistent standing
    instructions.
    """

    preferences = (
        get_preferences()
    )


    if not preferences:

        return (
            "No standing instructions "
            "are currently stored."
        )


    lines = [
        "Persistent standing instructions:"
    ]


    for index, preference in enumerate(
        preferences,
        start=1
    ):

        lines.append(
            f"{index}. "
            f"type={preference.get('type')} | "
            f"value={preference.get('value')} | "
            f"action={preference.get('action')}"
        )


    return "\n".join(
        lines
    )


# =========================================================
# DIRECT TEST
# =========================================================

if __name__ == "__main__":

    print(
        memory_summary()
    )