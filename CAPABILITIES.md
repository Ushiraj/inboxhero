# CAPABILITIES.md

**Student:** USHIRAJ GARG, evernorth-aai-1194540

**Repository:** https://github.com/Ushiraj/inboxhero

Run everything through one entry point:

```bash
python demo.py --cap R1        # one capability
python demo.py --all           # all of them, in the order below


## System Overview

inboxHero is an agentic email-processing system built without an agent
framework. It processes an inbox, classifies messages, retrieves relevant
earlier messages when context is required, drafts grounded replies, remembers
standing instructions across process restarts, protects irreversible actions
behind a human gate, detects hostile instructions embedded in email content,
and generates a three-pane operational dashboard.

The primary model used by the pipeline is **gemini-3.5-flash-lite**.

The project was also developed and tested against a local
**gemma4:e2b** model through Ollama to reduce dependency on external API rate
limits during development.

The supplied inbox contains **100 messages**.

The disposition vocabulary is:

- `reply`
- `archive`
- `spam`
- `phishing`
- `defer`
- `delegate`
- `escalate`

Every message must receive exactly one disposition and a stated reason.

The Part 2 implementation uses deterministic rules first and invokes the
configured LLM only when no deterministic rule confidently handles the
message.

The currently recorded run produced:

- Messages processed: **100**
- Deterministically handled: **11**
- LLM classified: **89**
- Messages without a disposition: **0**

These counts should be treated as run results and should be updated if the
final demonstration run produces different values.

---

# Architecture and Safety Model

## Retrieval

Context-dependent answering uses:

`keyword_search_rag_faiss_cosine_similarity`

Earlier inbox messages are embedded and retrieved using FAISS cosine
similarity. A generated reply may cite only messages that:

1. exist in the inbox mail store, and
2. were actually retrieved and supplied as context.

If sufficient information is not present in the inbox, the system reports
insufficient information and does not invent a reply.

---

## Reversible Actions

The following actions are considered reversible in this design:

- draft
- label
- archive
- defer
- delete to recoverable trash

A deletion to trash is considered reversible because the original message
remains recoverable.

---

## Irreversible Actions

The following actions are considered irreversible:

- send
- permanent delete

Sending cannot reliably be undone after the recipient receives the message.

Permanent deletion destroys the recoverable copy of the message.

Both therefore pass through the Part 4 action gate.

---

## Irreversible-Action Gate

The system supports both:

1. **Dry-run mode**
2. **Explicit per-action human approval**

Dry-run displays the action that would have occurred without executing it.

When dry-run is disabled, an irreversible action requires explicit human
approval before execution.

Human approval is intentionally reserved for irreversible actions rather than
routine reversible operations. This reduces approval fatigue and preserves
human attention for actions with meaningful external consequences.

---

## Untrusted Email Boundary

Email content is treated as **untrusted data**.

Instructions appearing inside an email do not automatically become
instructions to the agent.

Hostile messages attempting to make the agent forward mail, delete
information, hide an action, bypass approval, or perform another unauthorized
operation are refused and flagged.

The hostile message itself is retained in the inbox.

Tools capable of irreversible actions remain accessible only through the
Part 4 gate.

---

# Required Capabilities

## R1 — Zero the Inbox

**Tier:** B  
**Assignment:** Part 2

### Claim

Assigns every message exactly one disposition and a stated reason, routing
obvious messages through deterministic rules before using the configured LLM.

### Command

```bash
python demo.py --cap R1

## Final Report

1. What did you refuse to automate?

I refused to automate the final sending of an email. For e.g., even when my agent prepares a grounded reply for m008, it only creates the draft in the "OUTBOX" fodler. The gate_actions.py still requires my approval before anything is written to the outbox. Drafting can be undone but sending an email cannot be undone.

2. Where does untrusted text enter your system?

The untrusted text can enter my system via inbox.json. The sender, subject, body, quoted text, and any instructions inside an email are data, not commands for the program. This became particularly important for messages such as m024, which contains an instruction intended to make an agent perform an action. The hostile_inbox.py flags such messages instead of giving them access to action functions. This is not dependent only on telling the LLM to ignore suspicious instructions—the code that can actually send something is separated into gate_actions.py and requires approval. So an attacker would have to get past both the application's action boundary and the human approval gate, rather than simply putting a convincing instruction in an email.

3. Who is accountable when it sends the wrong thing?

Since the email is ultimately being sent in the owner's name, I consider the owner accountable for approving the final send. Hence, we should not allow the model to silently send a generated response. At the same time, the system keeps enough information to understand where an error came from: answer_email.py records which earlier message IDs were used to ground a draft, while gate_actions.py records the proposed action and the approval decision. The demo also writes capability events to trace.jsonl, so we can follow what happened across the pipeline. This makes it possible to distinguish whether a bad email came from incorrect retrieval, a bad generated draft, or a message that should not have been approved in the first place.

4. Name your own machinery.

I did not use an agent framework, instead I used Python modules which can be called and can act as a framework. The "read_inbox.py" and "answer_email.py" perform the main agent-like reasoning work, individual functions such as process_inbox() and answer_email() behave like tasks, and the final code "demo.py" acts as the router that decides which capability to run. All the modules and the final code can perform the same capabilites as "CrewAI" framework. 

