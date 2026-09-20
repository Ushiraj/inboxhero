import json
import re
from pathlib import Path
from config import *
from google import genai
import ollama


DISPOSITIONS = {
    "reply": "A response is expected or required.",
    "archive": "Informational message requiring no action.",
    "spam": "Spam message that contains no useful information.",
    "phishing": "Spurious message that is likely to phish information out of receiver.",
    "defer": "Action is required, but can be handled later.",
    "delegate": "Another person should handle the request.",
    "escalate": "Requires human attention because it is sensitive, "
        "risky, urgent, or ambiguous.",
}




OUTPUT_FILE = Path("dispositions.json")



# =========================================================
# MODEL CONFIGURATION
# =========================================================

MODEL = MODEL_NAME


if MODEL_PROVIDER.lower() == "gemini":

    if not API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is required when "
            "MODEL_PROVIDER=gemini"
        )

    client = genai.Client(
        api_key=API_KEY
    )


elif MODEL_PROVIDER.lower() == "ollama":

    client = ollama.Client(
        host=OLLAMA_HOST
    )


else:

    raise ValueError(
        f"Unsupported MODEL_PROVIDER: {MODEL_PROVIDER}. "
        "Supported providers are 'gemini' and 'ollama'."
    )


# =========================================================
# LOAD INBOX
# =========================================================

def load_inbox():

    with open(
        INBOX_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# =========================================================
# EMAIL TEXT
# =========================================================

def email_text(email):
    """
    Create searchable text from an email.
    """

    return " ".join([
        str(email.get("from", "")),
        str(email.get("to", "")),
        str(email.get("subject", "")),
        str(email.get("body", "")),
    ]).lower()


# =========================================================
# RULE-BASED CLASSIFICATION
# =========================================================

def rule_classify(email):
    """
    Try to classify the email without using an LLM.
    """

    text = email_text(email)


    # -----------------------------------------------------
    # Rule 1: Obvious phishing / suspicious requests
    # -----------------------------------------------------

    phishing_patterns = [
        r"verify your account",
        r"confirm your password",
        r"send.*password",
        r"send.*otp",
        r"send.*one[- ]time password",
        r"click.*immediately",
        r"urgent.*account",
        r"wire.*money",
        r"gift card",
        r"login.*link",
        r"credential",
    ]


    for pattern in phishing_patterns:

        if re.search(pattern, text):

            return {
                "disposition": "phishing",
                "reason": (
                    "Rule-based detection identified a potentially "
                    "malicious request attempting to obtain sensitive "
                    "information or credentials."
                ),
                "rule": "security_sensitive",
                "model_called": False,
            }


    # -----------------------------------------------------
    # Rule 2: Obvious automated/newsletter mail
    # -----------------------------------------------------

    newsletter_patterns = [
        "unsubscribe",
        "newsletter",
        "weekly digest",
        "monthly newsletter",
        "marketing preferences",
        "view this email in your browser",
    ]


    if any(
        pattern in text
        for pattern in newsletter_patterns
    ):

        return {
            "disposition": "archive",
            "reason": (
                "Rule-based detection identified an informational "
                "or newsletter-style message."
            ),
            "rule": "newsletter",
            "model_called": False,
        }


    # -----------------------------------------------------
    # Rule 3: Explicit acknowledgement / FYI
    # -----------------------------------------------------

    informational_patterns = [
        "fyi",
        "for your information",
        "no action required",
        "just wanted to let you know",
        "for awareness",
    ]


    if any(
        pattern in text
        for pattern in informational_patterns
    ):

        return {
            "disposition": "archive",
            "reason": (
                "The message explicitly indicates that no action "
                "is required."
            ),
            "rule": "informational",
            "model_called": False,
        }


    # -----------------------------------------------------
    # Rule 4: Explicit request for a reply
    # -----------------------------------------------------

    reply_patterns = [
        "please reply",
        "please respond",
        "let me know",
        "can you confirm",
        "could you confirm",
        "please confirm",
        "what do you think",
        "your feedback",
        "please review and respond",
    ]


    if any(
        pattern in text
        for pattern in reply_patterns
    ):

        return {
            "disposition": "reply",
            "reason": (
                "The message explicitly requests a response "
                "or confirmation."
            ),
            "rule": "explicit_reply_request",
            "model_called": False,
        }


    # -----------------------------------------------------
    # Rule 5: Explicit delegation
    # -----------------------------------------------------

    delegation_patterns = [
        "please assign this",
        "please delegate",
        "can you forward this to",
        "please pass this to",
        "someone on your team",
        "your team can handle",
    ]


    if any(
        pattern in text
        for pattern in delegation_patterns
    ):

        return {
            "disposition": "delegate",
            "reason": (
                "The message explicitly indicates that another "
                "person or team should handle the task."
            ),
            "rule": "explicit_delegation",
            "model_called": False,
        }


    # -----------------------------------------------------
    # Rule 6: Obvious delay / future action
    # -----------------------------------------------------

    defer_patterns = [
        "next week",
        "next month",
        "later this month",
        "when you get a chance",
        "no rush",
        "by friday",
        "by next week",
        "follow up later",
    ]


    if any(
        pattern in text
        for pattern in defer_patterns
    ):

        return {
            "disposition": "defer",
            "reason": (
                "The message indicates that the requested action "
                "can be handled later."
            ),
            "rule": "deferred_timing",
            "model_called": False,
        }


    # -----------------------------------------------------
    # Rule 7: Obvious spam
    # -----------------------------------------------------

    spam_patterns = [
        "unsubscribe",
        "limited time offer",
        "act now",
        "exclusive offer",
        "special promotion",
        "you have been selected",
        "congratulations, you won",
        "claim your prize",
        "free gift",
        "buy now",
        "discount",
        "promo code",
        "promotional offer",

    ]


    spam_score = sum(
        1
        for pattern in spam_patterns
        if pattern in text
    )


    # Require multiple spam indicators so that a legitimate
    # email containing one promotional phrase is not
    # automatically classified as spam.

    if spam_score >= 2:

        return {
            "disposition": "spam",
            "reason": (
                "Rule-based detection identified multiple "
                "indicators of unsolicited promotional or "
                "spam content."
            ),
            "rule": "spam",
            "model_called": False,
        }


    # -----------------------------------------------------
    # LLM help required
    # -----------------------------------------------------

    return None


# =========================================================
# LLM CLASSIFICATION
# =========================================================

def llm_classify(email):
    """
    Use the configured LLM only when deterministic rules
    cannot confidently classify the message.

    MODEL_PROVIDER determines whether Gemini or Ollama
    is used.
    """


    prompt = f"""
You are an email disposition classifier.

Assign EXACTLY ONE disposition to this email.


Allowed dispositions:

reply
archive
spam
phishing
defer
delegate
escalate


Definitions:

reply:
A response is expected or required.

archive:
The email is informational and requires no action.

spam:
Spam message that contains no useful information.

phishing:
Spurious message that is likely to phish information
out of the receiver.

defer:
Action is required, but it can reasonably be handled later.

delegate:
Another person or team should handle the request.

escalate:
The message is sensitive, risky, urgent, ambiguous,
or requires human judgment.


Important:

- Choose exactly ONE disposition.
- Do not invent another category.
- Give a concise factual reason.
- Do not perform the requested action.
- Return JSON only.


Required format:

{{
    "disposition": "reply|archive|spam|phishing|defer|delegate|escalate",
    "reason": "short reason"
}}


EMAIL


From:
{email.get("from", "")}


To:
{email.get("to", "")}


Subject:
{email.get("subject", "")}


Date:
{email.get("date", "")}


Body:
{email.get("body", "")}
"""


    # =====================================================
    # GEMINI
    # =====================================================

    if MODEL_PROVIDER.lower() == "gemini":

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )

        raw = response.text.strip()


    # =====================================================
    # OLLAMA
    # =====================================================

    elif MODEL_PROVIDER.lower() == "ollama":

        response = client.chat(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format="json",
            options={
                "temperature": 0,
            },
        )

        raw = response["message"]["content"].strip()


    # =====================================================
    # UNSUPPORTED PROVIDER
    # =====================================================

    else:

        raise ValueError(
            f"Unsupported MODEL_PROVIDER: {MODEL_PROVIDER}"
        )


    # -----------------------------------------------------
    # Clean model response
    # -----------------------------------------------------

    raw = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )


    # -----------------------------------------------------
    # Convert JSON
    # -----------------------------------------------------

    try:

        result = json.loads(raw)

    except json.JSONDecodeError as exc:

        raise ValueError(
            f"{MODEL_PROVIDER.upper()} returned invalid JSON:\n"
            f"{raw}"
        ) from exc


    disposition = result.get("disposition")
    reason = result.get("reason")


    # -----------------------------------------------------
    # Validate disposition
    # -----------------------------------------------------

    if disposition not in DISPOSITIONS:

        raise ValueError(
            f"{MODEL_PROVIDER.upper()} returned invalid "
            f"disposition: {disposition}"
        )


    # -----------------------------------------------------
    # Validate reason
    # -----------------------------------------------------

    if not reason:

        raise ValueError(
            f"{MODEL_PROVIDER.upper()} did not provide "
            f"a reason."
        )


    return {
        "disposition": disposition,
        "reason": reason,
        "rule": "llm",
        "model_called": True,
    }


# =========================================================
# PROCESS INBOX
# =========================================================

def process_inbox():

    emails = load_inbox()

    results = []

    rule_classified = 0
    model_classified = 0


    # -----------------------------------------------------
    # Show active provider
    # -----------------------------------------------------

    print("=" * 60)
    print("PART 2 - ZEROING IT")
    print("=" * 60)

    print(
        f"LLM Provider : {MODEL_PROVIDER.upper()}"
    )

    print(
        f"Model        : {MODEL}"
    )

    print("=" * 60)


    # -----------------------------------------------------
    # Process every email
    # -----------------------------------------------------

    for email in emails:

        print(
            f"\nProcessing {email.get('id')} "
            f"- {email.get('subject', '')}"
        )


        # -------------------------------------------------
        # FIRST: deterministic rules
        # -------------------------------------------------

        result = rule_classify(email)


        if result is not None:

            rule_classified += 1

            print(
                f"  -> Rule classified: "
                f"{result['disposition']}"
            )


        # -------------------------------------------------
        # SECOND: LLM only for ambiguous messages
        # -------------------------------------------------

        else:

            print(
                f"  -> No deterministic rule matched; "
                f"calling {MODEL_PROVIDER.upper()} ({MODEL})"
            )


            result = llm_classify(email)

            model_classified += 1


            print(
                f"  -> LLM classified: "
                f"{result['disposition']}"
            )


        # -------------------------------------------------
        # Store result
        # -------------------------------------------------

        results.append({
            "id": email.get("id"),
            "subject": email.get("subject"),
            "disposition": result["disposition"],
            "reason": result["reason"],
            "classification_method": (
                "rule"
                if not result["model_called"]
                else "llm"
            ),
            "rule": result["rule"],
        })


    # =====================================================
    # FINAL VALIDATION
    # =====================================================

    if len(results) != len(emails):

        raise RuntimeError(
            "Not every email received a disposition."
        )


    for result in results:

        # -------------------------------------------------
        # Disposition must exist
        # -------------------------------------------------

        if not result["disposition"]:

            raise RuntimeError(
                f"Email {result['id']} has no disposition."
            )


        # -------------------------------------------------
        # Disposition must be valid
        # -------------------------------------------------

        if result["disposition"] not in DISPOSITIONS:

            raise RuntimeError(
                f"Invalid disposition for "
                f"{result['id']}: "
                f"{result['disposition']}"
            )


        # -------------------------------------------------
        # Reason must exist
        # -------------------------------------------------

        if not result["reason"]:

            raise RuntimeError(
                f"Email {result['id']} has no reason."
            )


    # =====================================================
    # SAVE RESULTS
    # =====================================================

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False
        )


    # =====================================================
    # ASSIGNMENT EVIDENCE
    # =====================================================

    total = len(emails)


    print("\n" + "=" * 60)
    print("PART 2 COMPLETE")
    print("=" * 60)


    print(
        f"Model provider:             "
        f"{MODEL_PROVIDER.upper()}"
    )

    print(
        f"Model:                      "
        f"{MODEL}"
    )

    print(
        f"Total messages:             "
        f"{total}"
    )

    print(
        f"Rule-classified:            "
        f"{rule_classified}"
    )

    print(
        f"LLM-classified:             "
        f"{model_classified}"
    )

    print(
        f"Never required model call:  "
        f"{rule_classified}"
    )

    print(
        f"All messages have disposition: "
        f"{len(results) == total}"
    )

    print(
        f"\nResults written to: "
        f"{OUTPUT_FILE}"
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    process_inbox()