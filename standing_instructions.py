# =========================================================
# PART 5 - STANDING INSTRUCTIONS
# =========================================================

import json
from pathlib import Path

from read_inbox import load_inbox

from memory import (
    remember_preference,
    find_matching_preferences,
    memory_summary,
)

from config import OUTPUT_PATH


# =========================================================
# OUTPUT
# =========================================================

PART5_OUTPUT_FILE = (
    OUTPUT_PATH
    / "standing_instructions_result.json"
)


OUTPUT_PATH.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# RECORD A STANDING INSTRUCTION
# =========================================================

def record_preference(
    preference_type,
    value,
    action
):
    """
    Record a standing instruction supplied by the owner.

    The preference is persisted by memory.py and therefore
    survives program exit/restart.
    """

    result = remember_preference(
        preference_type=
            preference_type,

        value=
            value,

        action=
            action,

        source=
            "owner_standing_instruction",
    )


    print(
        "\n" + "=" * 70
    )

    print(
        "STANDING INSTRUCTION RECORDED"
    )

    print(
        "=" * 70
    )


    print(
        f"\nType   : "
        f"{preference_type}"
    )


    print(
        f"Value  : "
        f"{value}"
    )


    print(
        f"Action : "
        f"{action}"
    )


    print(
        "\nThe preference has been "
        "persisted to disk."
    )


    print(
        "It will remain available after "
        "the program exits and restarts."
    )


    return result


# =========================================================
# APPLY STANDING INSTRUCTIONS
# =========================================================

def apply_standing_instructions(
    email
):
    """
    Apply persistent owner preferences to an email.

    This function does NOT rely on memory from the current
    Python process.

    memory.py reloads the persistent memory file from disk.

    Therefore this function can be executed after the
    original process has completely exited.
    """


    # -----------------------------------------------------
    # Retrieve matching persisted preferences
    # -----------------------------------------------------

    preferences = (
        find_matching_preferences(
            email
        )
    )


    # -----------------------------------------------------
    # Default result
    # -----------------------------------------------------

    result = {
        "message_id":
            email.get(
                "id"
            ),

        "subject":
            email.get(
                "subject"
            ),

        "sender":
            email.get(
                "from"
            ),

        "standing_instruction_applied":
            False,

        "matched_preferences":
            [],

        "effects":
            {
                "disposition_override":
                    None,

                "cc":
                    [],

                "escalate":
                    False,

                "never_agree":
                    [],
            },
    }


    # -----------------------------------------------------
    # No memory applies
    # -----------------------------------------------------

    if not preferences:

        return result


    result[
        "standing_instruction_applied"
    ] = True


    # =====================================================
    # APPLY EACH MATCHING PREFERENCE
    # =====================================================

    for preference in preferences:

        preference_type = (
            preference.get(
                "type"
            )
        )

        value = (
            preference.get(
                "value"
            )
        )

        action = (
            preference.get(
                "action"
            )
        )


        # Record exactly which persistent memory affected
        # this email.

        result[
            "matched_preferences"
        ].append(
            {
                "type":
                    preference_type,

                "value":
                    value,

                "action":
                    action,

                "source":
                    preference.get(
                        "source"
                    ),
            }
        )


        # -------------------------------------------------
        # 1. CORRESPONDENT-SPECIFIC BEHAVIOUR
        # -------------------------------------------------

        if (
            preference_type
            == "correspondent"
        ):

            # Example:
            #
            # correspondent =
            #     boss@example.com
            #
            # action =
            #     always_reply

            if action == "always_reply":

                result[
                    "effects"
                ][
                    "disposition_override"
                ] = "reply"


            elif action == "always_archive":

                result[
                    "effects"
                ][
                    "disposition_override"
                ] = "archive"


            elif action == "always_escalate":

                result[
                    "effects"
                ][
                    "disposition_override"
                ] = "escalate"

                result[
                    "effects"
                ][
                    "escalate"
                ] = True


        # -------------------------------------------------
        # 2. SUBJECT-BASED INSTRUCTION
        # -------------------------------------------------

        elif (
            preference_type
            == "subject_contains"
        ):

            if action in {
                "reply",
                "archive",
                "defer",
                "delegate",
                "escalate",
            }:

                result[
                    "effects"
                ][
                    "disposition_override"
                ] = action


            if action == "escalate":

                result[
                    "effects"
                ][
                    "escalate"
                ] = True


        # -------------------------------------------------
        # 3. BODY-BASED INSTRUCTION
        # -------------------------------------------------

        elif (
            preference_type
            == "body_contains"
        ):

            if action in {
                "reply",
                "archive",
                "defer",
                "delegate",
                "escalate",
            }:

                result[
                    "effects"
                ][
                    "disposition_override"
                ] = action


        # -------------------------------------------------
        # 4. CC STANDING INSTRUCTION
        # -------------------------------------------------

        elif (
            preference_type
            == "cc_on_subject"
        ):

            # Here action contains the person/email
            # who must be copied.

            if (
                action
                and
                action not in result[
                    "effects"
                ][
                    "cc"
                ]
            ):

                result[
                    "effects"
                ][
                    "cc"
                ].append(
                    action
                )


        # -------------------------------------------------
        # 5. NEVER-AGREE RULE
        # -------------------------------------------------

        elif (
            preference_type
            == "never_agree"
        ):

            result[
                "effects"
            ][
                "never_agree"
            ].append(
                value
            )


            # Never-agree instructions are deliberately
            # escalated rather than allowing the agent to
            # make the commitment.

            result[
                "effects"
            ][
                "escalate"
            ] = True


            result[
                "effects"
            ][
                "disposition_override"
            ] = "escalate"


    return result


# =========================================================
# PROCESS ONE EMAIL
# =========================================================

def process_message_with_memory(
    message_id
):
    """
    Process one inbox message using standing instructions
    loaded from persistent memory.
    """


    # -----------------------------------------------------
    # Load inbox
    # -----------------------------------------------------

    emails = load_inbox()


    # -----------------------------------------------------
    # Find target message
    # -----------------------------------------------------

    target_email = None


    for email in emails:

        if (
            email.get(
                "id"
            )
            == message_id
        ):

            target_email = email
            break


    if target_email is None:

        raise ValueError(
            f"Message {message_id} "
            "does not exist in inbox."
        )


    # =====================================================
    # DISPLAY
    # =====================================================

    print(
        "\n" + "=" * 70
    )

    print(
        "PART 5 - STANDING INSTRUCTIONS"
    )

    print(
        "=" * 70
    )


    print(
        f"\nMessage ID : "
        f"{target_email.get('id')}"
    )


    print(
        f"From       : "
        f"{target_email.get('from')}"
    )


    print(
        f"Subject    : "
        f"{target_email.get('subject')}"
    )


    # =====================================================
    # SHOW MEMORY AFTER RESTART
    # =====================================================

    print(
        "\n" + "-" * 70
    )

    print(
        "PERSISTENT MEMORY LOADED"
    )

    print(
        "-" * 70
    )


    print(
        memory_summary()
    )


    # =====================================================
    # APPLY MEMORY
    # =====================================================

    result = (
        apply_standing_instructions(
            target_email
        )
    )


    # =====================================================
    # DISPLAY RESULT
    # =====================================================

    print(
        "\n" + "-" * 70
    )

    print(
        "STANDING INSTRUCTION RESULT"
    )

    print(
        "-" * 70
    )


    if result[
        "standing_instruction_applied"
    ]:

        print(
            "\nStanding instruction applied: YES"
        )


        print(
            "\nMatched preference(s):"
        )


        for preference in (
            result[
                "matched_preferences"
            ]
        ):

            print(
                f"  -> "
                f"{preference['type']} | "
                f"{preference['value']} | "
                f"{preference['action']}"
            )


        effects = result[
            "effects"
        ]


        # ---------------------------------------------
        # Disposition override
        # ---------------------------------------------

        if effects[
            "disposition_override"
        ]:

            print(
                "\nDisposition override:"
            )

            print(
                f"  -> "
                f"{effects['disposition_override']}"
            )


        # ---------------------------------------------
        # CC instructions
        # ---------------------------------------------

        if effects["cc"]:

            print(
                "\nCC required:"
            )


            for person in effects[
                "cc"
            ]:

                print(
                    f"  -> {person}"
                )


        # ---------------------------------------------
        # Never-agree instructions
        # ---------------------------------------------

        if effects[
            "never_agree"
        ]:

            print(
                "\nOwner has instructed the "
                "agent never to agree to:"
            )


            for instruction in (
                effects[
                    "never_agree"
                ]
            ):

                print(
                    f"  -> {instruction}"
                )


        # ---------------------------------------------
        # Escalation
        # ---------------------------------------------

        if effects[
            "escalate"
        ]:

            print(
                "\nESCALATION REQUIRED"
            )


            print(
                "The agent must not make this "
                "commitment automatically."
            )


    else:

        print(
            "\nStanding instruction applied: NO"
        )


        print(
            "No stored owner preference matched "
            "this message."
        )


    # =====================================================
    # SAVE EVIDENCE
    # =====================================================

    with open(
        PART5_OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )


    print(
        f"\nResult saved to: "
        f"{PART5_OUTPUT_FILE}"
    )


    return result


# =========================================================
# SHOW ALL STANDING INSTRUCTIONS
# =========================================================

def show_standing_instructions():

    print(
        "\n" + "=" * 70
    )

    print(
        "OWNER STANDING INSTRUCTIONS"
    )

    print(
        "=" * 70
    )


    print(
        "\n" + memory_summary()
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    show_standing_instructions()