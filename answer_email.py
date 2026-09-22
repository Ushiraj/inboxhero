# =========================================================
# PART 3 - ANSWER EMAILS
# =========================================================


import json
import re
from read_inbox import *
from config import OUTBOX_PATH
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer




OUTPUT_FILE = OUTBOX_PATH / "drafts.json"
RETRIEVAL_METHOD = "keyword_search_rag_faiss_cosine_similarity"

OUTBOX_PATH.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# BUILD MAIL STORE
# =========================================================

def build_mail_store(emails):
    """
    Create a dictionary of:
        message_id -> email

    This lets us verify that every message cited by the
    draft actually exists in inbox.json.
    """

    return { email["id"]: email for email in emails if email.get("id")}


# =========================================================
# NORMALIZE SUBJECT
# =========================================================

def normalize_subject(subject):
    """
    Remove common reply/forward prefixes so messages from
    the same thread can be matched.
    """

    subject = str(subject or "").lower().strip()

    # Remove repeated prefixes
    while re.match(r"^(re|fw|fwd)\s*:\s*",subject,flags=re.IGNORECASE):
        subject = re.sub(r"^(re|fw|fwd)\s*:\s*",
            "",
            subject,
            count=1,
            flags=re.IGNORECASE
        )

    return subject.strip()


# =========================================================
# TOKENIZATION
# =========================================================

def tokenize(text):
    """
    Extract meaningful words for simple keyword retrieval.
    """

    words = re.findall(
        r"\b[a-zA-Z0-9]+\b",
        str(text).lower()
    )

    stopwords = {
        "the", "a", "an",
        "and", "or", "but",
        "to", "of", "in",
        "on", "for", "with",
        "is", "are", "was",
        "were", "be", "been",
        "this", "that", "it",
        "i", "you", "we",
        "they", "he", "she",
        "my", "your", "our",
        "their", "me", "us",
        "at", "by", "from",
        "as", "if", "so",
        "do", "does", "did",
        "have", "has", "had",
        "can", "could",
        "would", "should",
        "will",
        "please",
        "thanks",
        "thank",
        "hi",
        "hello",
    }

    return {
        word
        for word in words
        if (
            word not in stopwords
            and len(word) > 2
        )
    }


# =========================================================
# KEYWORD SCORE
# =========================================================

def keyword_score(target_email,candidate_email):
    """
    Calculate keyword overlap between two emails.
    """

    target_tokens = tokenize(email_text(target_email))

    candidate_tokens = tokenize(email_text(candidate_email))

    common_words = (target_tokens & candidate_tokens)

    return len(common_words)


# =========================================================
# EMBEDDING MODEL FOR RAG RETRIEVAL
# =========================================================

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

# =========================================================
# RETRIEVE EARLIER MESSAGES
# =========================================================

def retrieval_text(email):
    """
    Create the document text used for semantic retrieval.

    The email ID is deliberately not embedded because it
    has no semantic meaning.
    """

    return f"""
From: {email.get("from", "")}
To: {email.get("to", "")}
Subject: {email.get("subject", "")}

{email.get("body", "")}
""".strip()

# =========================================================
# RAG RETRIEVAL USING FAISS + COSINE SIMILARITY
# =========================================================

def retrieve_context(
    target_email,
    emails,
    max_results=5,
    similarity_threshold=0.25
):
    """
    Retrieve semantically relevant EARLIER emails using:

        SentenceTransformer embeddings
                +
        FAISS cosine similarity

    Only messages appearing before the target message are
    eligible for retrieval.

    Returns the top semantically similar earlier messages.
    """

    target_id = target_email["id"]


    # -----------------------------------------------------
    # STEP 1:
    # Locate target email
    # -----------------------------------------------------

    target_index = None

    for index, email in enumerate(emails):

        if email.get("id") == target_id:

            target_index = index
            break


    if target_index is None:

        raise ValueError(
            f"Target message {target_id} "
            "does not exist in inbox."
        )


    # -----------------------------------------------------
    # STEP 2:
    # Only earlier messages are allowed
    # -----------------------------------------------------

    earlier_messages = emails[:target_index]


    if not earlier_messages:

        return []


    # -----------------------------------------------------
    # STEP 3:
    # Convert earlier emails into documents
    # -----------------------------------------------------

    documents = [
        retrieval_text(email)
        for email in earlier_messages
    ]


    # -----------------------------------------------------
    # STEP 4:
    # Generate embeddings for earlier emails
    # -----------------------------------------------------

    document_embeddings = embedding_model.encode(
        documents,
        convert_to_numpy=True,
        show_progress_bar=False,
    )


    document_embeddings = np.asarray(
        document_embeddings,
        dtype="float32"
    )


    # -----------------------------------------------------
    # STEP 5:
    # Normalize embeddings
    #
    # FAISS IndexFlatIP performs inner product.
    #
    # Once vectors are normalized:
    #
    #       inner product = cosine similarity
    #
    # -----------------------------------------------------

    faiss.normalize_L2(
        document_embeddings
    )


    # -----------------------------------------------------
    # STEP 6:
    # Build FAISS index
    # -----------------------------------------------------

    embedding_dimension = (
        document_embeddings.shape[1]
    )


    index = faiss.IndexFlatIP(
        embedding_dimension
    )


    index.add(
        document_embeddings
    )


    # -----------------------------------------------------
    # STEP 7:
    # Embed target email
    # -----------------------------------------------------

    query_text = retrieval_text(
        target_email
    )


    query_embedding = embedding_model.encode(
        [query_text],
        convert_to_numpy=True,
        show_progress_bar=False,
    )


    query_embedding = np.asarray(
        query_embedding,
        dtype="float32"
    )


    faiss.normalize_L2(
        query_embedding
    )


    # -----------------------------------------------------
    # STEP 8:
    # Search FAISS
    # -----------------------------------------------------

    number_to_search = min(
        max_results,
        len(earlier_messages)
    )


    similarities, indices = index.search(
        query_embedding,
        number_to_search
    )


    # -----------------------------------------------------
    # STEP 9:
    # Convert FAISS results back to emails
    # -----------------------------------------------------

    candidates = []


    for similarity, index_position in zip(
        similarities[0],
        indices[0]
    ):

        # FAISS can theoretically return -1
        if index_position < 0:
            continue


        similarity = float(
            similarity
        )


        # Ignore weak semantic matches
        if similarity < similarity_threshold:
            continue


        matched_email = earlier_messages[
            index_position
        ]


        candidates.append({
            "email": matched_email,

            "score": round(
                similarity,
                4
            ),

            "retrieval_reason":
                "semantic_keyword_search_faiss",
        })


    return candidates

# =========================================================
# VERIFY MESSAGE IDS
# =========================================================

def verify_message_ids(
    message_ids,
    mail_store
):
    """
    Ensure every cited message really exists in inbox.json.
    """

    invalid_ids = [
        message_id
        for message_id in message_ids
        if message_id not in mail_store
    ]


    if invalid_ids:

        raise ValueError(
            "Invalid source message IDs: "
            f"{invalid_ids}"
        )


    return True


# =========================================================
# FORMAT RETRIEVED CONTEXT
# =========================================================

def format_context(
    retrieved_messages
):
    """
    Convert retrieved emails into text that can be supplied
    to the LLM.
    """

    context = []


    for item in retrieved_messages:

        email = item["email"]


        context.append(
            f"""
MESSAGE ID: {email.get("id")}

FROM:
{email.get("from", "")}

TO:
{email.get("to", "")}

DATE:
{email.get("date", "")}

SUBJECT:
{email.get("subject", "")}

BODY:
{email.get("body", "")}

----------------------------------------
"""
        )


    return "\n".join(context)


# =========================================================
# PART 3 LLM CALL
# =========================================================

def call_llm_to_answer(prompt):

    if MODEL_PROVIDER.lower() == "gemini":
        response = (client.models.generate_content(model=MODEL,contents=prompt))
        return response.text.strip()

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

        return (
            response["message"]["content"]
            .strip()
        )


    else:

        raise ValueError(
            "Unsupported MODEL_PROVIDER: "
            f"{MODEL_PROVIDER}"
        )


# =========================================================
# DRAFT GROUNDED REPLY
# =========================================================

def draft_grounded_reply(
    target_email,
    retrieved_messages,
    mail_store
):
    """
    Draft a reply using only information contained in the
    retrieved earlier messages.
    """


    # -----------------------------------------------------
    # Requirement 4:
    # No information -> no draft
    # -----------------------------------------------------

    if not retrieved_messages:

        return {
            "target_message_id":
                target_email["id"],

            "status":
                "insufficient_information",

            "draft":
                None,

            "source_message_ids":
                [],

            "reason": (
                "The required information "
                "was not found in the inbox."
            ),
        }


    # -----------------------------------------------------
    # IDs actually read by the LLM
    # -----------------------------------------------------

    retrieved_ids = [
        item["email"]["id"]
        for item in retrieved_messages
    ]


    # Make sure they really exist.

    verify_message_ids(
        retrieved_ids,
        mail_store
    )


    context = format_context(
        retrieved_messages
    )


    # =====================================================
    # PROMPT
    # =====================================================

    prompt = f"""
You are drafting a reply to an email.

The reply MUST be grounded entirely in earlier messages
retrieved from the user's inbox.


STRICT RULES:

1. Use ONLY information contained in the EARLIER MESSAGES.

2. Do not use outside knowledge.

3. Do not invent facts.

4. Do not invent names, dates, numbers, decisions,
   commitments, deadlines, meetings, attachments,
   prices, or other details.

5. If the target email cannot be answered using the
   supplied earlier messages, do NOT draft a reply.

6. source_message_ids must contain ONLY message IDs
   whose information you actually used in the draft.

7. Do not cite a message merely because it was provided.

8. Return JSON only.


If sufficient information exists:

{{
    "can_answer": true,
    "draft": "your reply",
    "source_message_ids": ["m001"],
    "reason": "brief explanation"
}}


If sufficient information DOES NOT exist:

{{
    "can_answer": false,
    "draft": null,
    "source_message_ids": [],
    "reason": "The required information is not available in the inbox."
}}


==================================================
TARGET EMAIL
==================================================

MESSAGE ID:
{target_email.get("id")}

FROM:
{target_email.get("from", "")}

TO:
{target_email.get("to", "")}

SUBJECT:
{target_email.get("subject", "")}

BODY:
{target_email.get("body", "")}


==================================================
EARLIER MESSAGES RETRIEVED FROM INBOX
==================================================

{context}
"""


    # -----------------------------------------------------
    # Call LLM
    # -----------------------------------------------------

    raw = call_llm_to_answer(
        prompt
    )


    # -----------------------------------------------------
    # Clean response
    # -----------------------------------------------------

    raw = (
        raw
        .replace(
            "```json",
            ""
        )
        .replace(
            "```",
            ""
        )
        .strip()
    )


    try:

        result = json.loads(
            raw
        )

    except json.JSONDecodeError as exc:

        raise ValueError(
            f"{MODEL_PROVIDER.upper()} "
            "returned invalid JSON:\n"
            f"{raw}"
        ) from exc


    # =====================================================
    # READ RESULT
    # =====================================================

    can_answer = result.get(
        "can_answer",
        False
    )

    draft = result.get(
        "draft"
    )

    source_ids = result.get(
        "source_message_ids",
        []
    )

    reason = result.get(
        "reason",
        ""
    )


    # =====================================================
    # GROUNDING VALIDATION
    # =====================================================

    # -----------------------------------------------------
    # Check that every source exists in inbox.json
    # -----------------------------------------------------

    verify_message_ids(
        source_ids,
        mail_store
    )


    # -----------------------------------------------------
    # Check that every cited source was actually retrieved
    # and therefore read by the LLM.
    # -----------------------------------------------------

    invalid_sources = [
        message_id
        for message_id in source_ids
        if message_id not in retrieved_ids
    ]


    if invalid_sources:

        raise ValueError(
            "LLM cited messages it never read: "
            f"{invalid_sources}"
        )


    # =====================================================
    # NO ANSWER
    # =====================================================

    if not can_answer:

        return {
            "target_message_id":
                target_email["id"],

            "status":
                "insufficient_information",

            "draft":
                None,

            "source_message_ids":
                [],

            "reason": (
                reason
                or
                "The required information "
                "is not available in the inbox."
            ),
        }


    # =====================================================
    # MODEL CLAIMED ANSWER BUT PROVIDED NO SOURCES
    # =====================================================

    if not source_ids:

        return {
            "target_message_id":
                target_email["id"],

            "status":
                "insufficient_information",

            "draft":
                None,

            "source_message_ids":
                [],

            "reason": (
                "Draft rejected because no "
                "supporting message IDs were cited."
            ),
        }


    # =====================================================
    # SUCCESS
    # =====================================================

    return {
        "target_message_id":
            target_email["id"],

        "status":
            "drafted",

        "draft":
            draft,

        "source_message_ids":
            source_ids,

        "reason":
            reason,
    }


# =========================================================
# PART 3
# =========================================================

def answer_email(message_id):
    """
    Main function for Part 3.

    Usage:
        answer_email("m008")
    """


    emails = load_inbox()


    # -----------------------------------------------------
    # Build verified mail store
    # -----------------------------------------------------

    mail_store = build_mail_store(emails)


    # -----------------------------------------------------
    # Make sure target exists
    # -----------------------------------------------------

    if message_id not in mail_store:
        raise ValueError(f"Message {message_id}does not exist in inbox.")


    target_email = mail_store[message_id]


    print("=" * 60)
    print("PART 3 - ANSWERING PROPERLY")
    print("=" * 60)

    print(f"Target message:{message_id}")

    print(f"Subject: {target_email.get('subject', '')}")

    print(f"Retrieval method: {RETRIEVAL_METHOD}")


    # -----------------------------------------------------
    # Retrieve evidence
    # -----------------------------------------------------

    retrieved = retrieve_context(target_email, emails)
    
    print( f"\nRetrieved {len(retrieved)} semantically relevant earlier messages.")

    for item in retrieved:
        email = item["email"]
        print(f"  -> {email['id']} | cosine_similarity={item['score']:.4f} | {email.get('subject', '')}")


    # -----------------------------------------------------
    # Draft grounded reply
    # -----------------------------------------------------

    result = draft_grounded_reply(target_email, retrieved,mail_store)


    # -----------------------------------------------------
    # Save result
    # -----------------------------------------------------

    with open(OUTPUT_FILE,"w",encoding="utf-8") as f:
        json.dump(result,f,indent=2,ensure_ascii=False)


    # -----------------------------------------------------
    # Display result
    # -----------------------------------------------------

    print("\n" + "=" * 60)
    print("PART 3 RESULT")
    print("=" * 60)
    print(f"Status: {result['status']}")


    if result["status"] == "drafted":
        print("\nSources actually used:")

        for source_id in (result["source_message_ids"]):
            print(f"  -> {source_id}")
        
        print("\nDraft:")
        print("-" * 60)

        print(result["draft"])
        print("-" * 60)
    else:
        print("\nNo draft created.")
        print(f"Reason: {result['reason']}")


    print(f"\nSaved to:{OUTPUT_FILE}")


    return result



if __name__=="__main__":

    answer_email("m008")