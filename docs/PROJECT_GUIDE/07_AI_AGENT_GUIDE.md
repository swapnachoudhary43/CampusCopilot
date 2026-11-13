# 7. AI agent guide

## What "agent" means here

In this project an agent is a loop that chooses one backend function, asks for anything missing, and waits for YES before it changes data. It is not a general agent that can browse the web or write code.

The choice is made by rules in `backend/app/services/agent/intent.py`. Gemini is not asked to pick the tool. That was deliberate. A rule list is readable in a viva, it works with no API key, and it cannot emit an unknown function name. The weakness is wording: "I want to complain about..." is recognised; a vague "the projector is annoying" is sent to document search instead.

## Chatbot versus this agent

| | Document chatbot | Workflow agent |
| --- | --- | --- |
| Route | `/api/chat` | `/api/agent` |
| Changes the database? | Only by saving the chat | Yes, after YES |
| How it decides | Always searches documents | Pattern list, then one tool |
| Uses Gemini? | Only to phrase an answer, and only if a key is set | No |

## The five tools

Defined in `backend/app/services/agent/workflow.py` and executed only from the `TOOLS` dictionary:

1. `search_campus_documents` — runs the RAG pipeline for this user.
2. `list_available_events` — upcoming events. Read only.
3. `check_complaint_status` — complaints whose `user_id` is the logged-in user. A complaint id that belongs to someone else gets the same "not on your account" reply as a missing id.
4. `submit_complaint` — creates a complaint. Confirmation required.
5. `register_for_event` — registers the logged-in user. Confirmation required. Capacity and duplicates are the same checks the event API uses.

There is no tool that accepts SQL or Python.

## Confirmation

`pending_actions` stores the tool name and the JSON arguments while status is `confirming`. The assistant message shows the title, the text, the predicted category if the model file exists, and the rule-based priority. Only a short reply matches YES: `yes`, `y`, `confirm`, `ok`, `okay`, `proceed`, `submit`. A long sentence that happens to contain "yes" is not enough. NO cancels the pending row.

Arguments are read back from that row and passed into the Python function. The function checks types and permissions again. The user's id comes from the token, not from the JSON.

## Example: a complaint

User: "I want to complain about a broken projector in classroom LH-2."

1. The submit pattern matches, and the sentence is not only a "what is the policy" question.
2. The text after "complain about" becomes the description. "classroom LH-2" becomes the location.
3. No complaint row exists yet. The reply asks for YES.
4. YES calls `create_complaint` for the current user.
5. The reply includes the new id, the predicted category, and the rule-based priority.

The automated test `test_agent_complaint_waits_for_confirmation` checks that the list is empty before YES and has one row after YES.

## Example: an event

User: "Show me upcoming events and register me for the AI workshop."

Register is checked before the event list, because the sentence asks to register. The name must match exactly one upcoming event title by substring or by token overlap of at least 0.6. The seeded event is "DEMO: assistant workshop". The reply asks for YES. YES calls `register_for_event`. A full event or a second registration returns the same error the REST API returns, and the pending action is cancelled.

## Safety points to mention

- One user cannot read another user's complaints through the agent.
- Faculty status updates are not a tool. Faculty use the complaint screen, and the service checks `assigned_to`.
- Audit rows are written when a complaint is created or an event registration is saved.
- If a confirmation is waiting, a new question does not silently replace it. The assistant repeats the draft and asks for YES or NO.
