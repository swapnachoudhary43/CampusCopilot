# API reference

The API is a FastAPI application. Interactive docs are at `http://localhost:8000/docs` while the backend is running. Every path below is implemented in `backend/app/routes` and `backend/app/main.py`.

Send JSON with `Content-Type: application/json`, except document upload, which uses `multipart/form-data`.

Protected routes expect:

```http
Authorization: Bearer <access_token>
```

The token comes from register or login. It contains the user id. The server loads that user from SQLite on every request, so a deactivated account or a changed role takes effect immediately.

## Common errors

| Status | When |
| --- | --- |
| 401 | Missing token, expired token, or wrong email/password. |
| 403 | The token is valid, but the role is not allowed to do this. |
| 404 | The record does not exist, or it exists but this user is not allowed to see it. Complaints use the same 404 wording so one student cannot discover another student's complaint id. |
| 409 | Duplicate email, or a PDF uploaded while the FAISS index was built with a different embedding backend. |
| 422 | The JSON failed validation (short password, unknown category, bad email). |
| 400 | A business rule failed, such as resolving a complaint with no remarks. |
| 503 | The classifier file is missing, or re-indexing failed. |

A validation error looks like:

```json
{"detail": [{"type": "string_too_short", "loc": ["body", "password"], "msg": "String should have at least 8 characters"}]}
```

Passwords must be at least 8 characters, contain a letter and a digit, and be at most 72 bytes. Public registration always creates a student. Only an administrator can create faculty or admin accounts.

Emails must be real-looking addresses. `example.com` works. Some reserved suffixes, including `.test`, are rejected by the email validator.

---

## Health

### `GET /`

No authentication. Returns the app name and a pointer to `/docs`.

### `GET /api/health`

No authentication. Reports the embedding backend, whether a Gemini key is configured (true/false only, never the key), how many chunks are in FAISS, and whether `models/deployed.joblib` exists.

```json
{
  "status": "ok",
  "embedding_backend": "sentence-transformers",
  "llm_mode": "retrieval_only",
  "gemini_configured": false,
  "indexed_chunks": 23,
  "classifier_available": true
}
```

`llm_mode` is `gemini` when a key is set and `LLM_PROVIDER` is `auto` or `gemini`. It is `retrieval_only` when no key is set. It is `gemini_missing` when `LLM_PROVIDER=gemini` but the key is empty.

---

## `/api/auth`

### `POST /api/auth/register` — public, 201

Creates a student and returns a token.

```json
{
  "full_name": "Meera Nair",
  "email": "meera@example.com",
  "password": "Student@12345",
  "department": "AI and Data Science"
}
```

Response includes `access_token`, `token_type` (`bearer`), and `user` (id, name, email, role, department, is_active, created_at). `409` if the email already exists.

### `POST /api/auth/login` — public

```json
{"email": "student@example.com", "password": "Student@12345"}
```

Same token shape as register. `401` with `Email or password is incorrect.` for a wrong password, an unknown email, or an inactive account. The message does not say which of those it was.

### `GET /api/auth/me` — any logged-in user

Returns the current user. This is what the React app calls after it finds a saved token.

### `PATCH /api/auth/me` — any logged-in user

```json
{"full_name": "Meera Nair", "department": "AI and Data Science"}
```

Both fields are optional. Role cannot be changed here.

### `POST /api/auth/change-password` — any logged-in user

```json
{"current_password": "Student@12345", "new_password": "Student@123456"}
```

`400` if the current password is wrong. Response: `{"detail": "Password updated."}`

Logout is not an API call. The browser deletes `cc_token` from `localStorage`. The token remains valid until it expires (480 minutes by default).

---

## `/api/users` — administrator only

### `GET /api/users`

Every account. A student receives `403`.

### `GET /api/users/staff`

Active faculty and admin accounts. Used when assigning a complaint.

### `POST /api/users` — 201

```json
{
  "full_name": "Rahul Iyer",
  "email": "rahul@example.com",
  "password": "Faculty@12345",
  "department": "Computer Science",
  "role": "faculty"
}
```

`role` must be `student`, `faculty`, or `admin`.

### `PATCH /api/users/{user_id}`

```json
{"role": "faculty", "is_active": false, "department": "Library"}
```

Any subset of `full_name`, `department`, `role`, `is_active`. Deactivating a user makes their next request fail even if the token has not expired.

---

## `/api/documents`

### `GET /api/documents` — any logged-in user

Administrators see every document, including `needs_ocr`. Other roles see only `status=processed`. The response does not include the server file path. Stored names are random UUIDs.

### `GET /api/documents/index-status` — any logged-in user

```json
{"indexed_chunks": 23}
```

### `POST /api/documents` — administrator, 201, multipart

Form fields: `title` (required), `category` (default `Other`), `description` (optional), `file` (PDF).

Allowed categories are in `backend/app/constants.py`: Regulations, Examinations, Fees, Hostel, Scholarship, Calendar, Syllabus, Circular, Other.

Checks, all returned as `400` unless noted:

- Larger than 15 MB.
- Filename does not end in `.pdf`.
- Bytes do not start with `%PDF`.
- PyMuPDF cannot open the file, the PDF has no pages, or it has more than 80 pages.
- `409` if the existing FAISS index was built with a different embedding backend. Use `POST /api/documents/reindex` after changing `EMBEDDING_BACKEND`.

A PDF with almost no extractable text (under 40 characters) is saved with `status: "needs_ocr"` and is not indexed. OCR is not implemented. The message says so.

A successful text PDF returns `status: "processed"`, `page_count`, and `chunk_count`.

### `DELETE /api/documents/{document_id}` — administrator

Deletes the row, its chunks, the file, and rebuilds FAISS from the chunks that remain.

### `POST /api/documents/reindex` — administrator

Re-embeds every processed document and rebuilds the index. Returns `{"indexed_chunks": <count>}`.

---

## `/api/chat` — any logged-in user

Conversations are private. Another user's id returns `404`.

### `GET /api/chat/sessions`

This user's RAG conversations (`kind` is `rag`).

### `POST /api/chat/sessions` — 201

Creates a conversation titled `New conversation`.

### `GET /api/chat/sessions/{id}/messages`

The messages in order. Assistant messages include `sources` (document id, title, page, excerpt, score) and `metadata.answer_mode`.

### `POST /api/chat/sessions/{id}/messages`

```json
{"content": "What is the minimum attendance percentage required to sit for examinations?"}
```

The service embeds the question, searches FAISS, and either quotes passages, calls Gemini, or refuses. `answer_mode` is one of:

| Mode | Meaning |
| --- | --- |
| `retrieval_only` | No Gemini key. The reply quotes the pages and says a language model was not used. |
| `gemini` | Gemini wrote the answer from the retrieved chunks. |
| `insufficient_context` | Nothing scored at or above 0.48. `sources` is empty. The reply refuses to guess. |
| `llm_unavailable` | Gemini was configured but the call failed. Sources are still returned. No invented answer. |

A follow-up that starts with "and", "what about", "how about", "then", or "also", or a fragment shorter than 24 characters, is searched together with the previous user question. A full question is searched on its own.

### `DELETE /api/chat/sessions/{id}`

Deletes that user's conversation.

---

## `/api/agent` — any logged-in user

Same session shape as chat, but `kind` is `agent`. There is no delete route for agent sessions.

### `POST /api/agent/sessions/{id}/messages`

```json
{"content": "I want to complain about a broken projector in classroom LH-2."}
```

The router is a Python rule set in `backend/app/services/agent/intent.py`, not Gemini function calling. It may only call `search_campus_documents`, `list_available_events`, `check_complaint_status`, `submit_complaint`, and `register_for_event`.

Creating or changing a record sets `needs_confirmation` to true and stores a pending action. Nothing is written until the next message is exactly a short confirmation such as `YES`. `NO` cancels. A long sentence that merely contains the word "yes" is not treated as confirmation.

The user id always comes from the token. The tools cannot read another user's complaints.

---

## `/api/complaints` — any logged-in user, filtered by role

Students see their own complaints. Faculty see complaints assigned to them. Administrators see all.

### `GET /api/complaints`

Optional query: `status`, `category`. `category` filters on the predicted category.

### `POST /api/complaints` — 201

```json
{
  "title": "Broken projector",
  "description": "The projector in classroom LH-2 does not power on.",
  "location": "LH-2",
  "user_category": "Infrastructure"
}
```

`user_category` is optional and must be one of the eight labels. The response adds the model prediction, confidence, model name, and a rule-based priority. `priority_method` is `rule_based`. `priority_disclaimer` says it is not a trained priority model.

### `GET /api/complaints/{id}`

Includes `history`. `404` if it is not visible to this user.

### `PATCH /api/complaints/{id}`

```json
{
  "status": "assigned",
  "department": "Estate office",
  "assigned_to": 2,
  "resolution_remarks": "Replaced the lamp."
}
```

Students receive `403`. Faculty can update only complaints assigned to them. Allowed status moves:

- submitted → assigned or in_progress
- assigned → in_progress or resolved
- in_progress → resolved
- resolved → closed

Resolving or closing requires remarks. `assigned_to` must be an active faculty or admin user.

---

## `/api/events`

### `GET /api/events` — any logged-in user

Each event includes `registered_count` and `viewer_registered`.

### `POST /api/events` — administrator, 201

```json
{
  "title": "DEMO: assistant workshop",
  "description": "DEMO DATA. Not a university event. A sample session on retrieval and citations.",
  "venue": "DEMO venue — not a DAVV location",
  "starts_at": "2026-11-20T10:00:00Z",
  "ends_at": "2026-11-20T13:00:00Z",
  "capacity": 40
}
```

`ends_at` must be after `starts_at`. Capacity is 1 to 5000.

### `PUT /api/events/{id}` — administrator

Same body as create. `404` if the event is missing.

### `DELETE /api/events/{id}` — administrator

### `POST /api/events/{id}/register` — any logged-in user

Registers the token's user. `400` if the event has started, the user is already registered, or the capacity is full. Capacity counts rows with `status=registered`.

### `POST /api/events/{id}/cancel` — any logged-in user

Sets that user's registration to `cancelled`. The row is kept. `400` if they were not registered.

### `GET /api/events/me/registrations` — any logged-in user

Events where this user currently has status `registered`.

---

## `/api/notices`

### `GET /api/notices` and `GET /api/notices/{id}` — any logged-in user

Each notice includes `summary`, `summary_method`, `detected_audience`, `deadlines`, `action_items`, and `extraction_disclaimer`.

`summary_method` is `extractive_fallback` when Gemini is not configured, or `gemini` when the model returned a summary. Deadlines and action items are extracted text. The disclaimer says they are not verified facts. `audience` is the value the administrator chose. `detected_audience` is a separate guess from the text.

### `POST /api/notices` — administrator, 201

```json
{
  "title": "Exam registration",
  "body": "Students must register for end-semester examinations by 25 November 2026.",
  "audience": "students"
}
```

`audience` is `all`, `students`, `faculty`, or `hostel`. Body must be at least 20 characters. The summary is generated when the notice is saved.

### `PUT /api/notices/{id}` — administrator

Same body. The summary is generated again.

### `DELETE /api/notices/{id}` — administrator

---

## `/api/analytics` — administrator only

### `GET /api/analytics/overview`

Optional query: `from_date=2026-10-01` and `to_date=2026-11-12`. `400` if the end is before the start.

`total_users`, `users_by_role`, document counts, and `notices` ignore the date filter. Complaints, registrations, and frequent questions use it.

`frequent_questions` is the exact lower-cased, trimmed text of RAG user messages, limited to 8. It is not semantic clustering, and complaint text is excluded.

`definitions` in the JSON explains those rules so the dashboard does not have to hardcode the meaning.

### `GET /api/analytics/activity`

The latest 20 audit rows: action, entity type, entity id, a short detail string, and time. Complaint descriptions are not copied into the dashboard aggregates. Activity details can include a complaint title or event title because those actions were logged that way. Do not paste private complaint text into a slide.

---

## `/api/ml`

### `GET /api/ml/metrics` — administrator

The contents of `models/metrics.json`. `404` if training has not been run. The page does not invent numbers.

### `POST /api/ml/predict` — any logged-in user

```json
{"text": "The projector in LH-2 is broken and will not turn on."}
```

```json
{
  "predicted_category": "Infrastructure",
  "confidence": 0.19,
  "confidence_type": "predicted_class_probability",
  "model_name": "logistic_regression",
  "suggested_priority": "medium",
  "priority_method": "rule_based",
  "priority_reason": "Matched keyword 'broken'."
}
```

The confidence above is an example of one sentence, not the test-set score. The test-set scores are in `metrics.json`: accuracy 0.625 and macro F1 0.624. `503` if `models/deployed.joblib` is missing.
