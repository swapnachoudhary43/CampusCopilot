# Implementation status

Updated after the local demo run on this copy. "Completed" means the code path exists and was executed here. "Partial" means the code exists but was not executed against the external service. "Not built" means it was left out on purpose or was never started.

## Completed

- Student registration, login, logout (client-side), profile update, password change, JWT, bcrypt.
- Roles `student`, `faculty`, and `admin`, checked in FastAPI. Public registration creates students only.
- PDF upload checks: extension, `%PDF` header, 15 MB, 80 pages, empty or image-only PDFs saved as `needs_ocr` and not indexed.
- Chunking, MiniLM embeddings, FAISS `IndexFlatIP`, citations with title and page, delete and rebuild.
- RAG uses semantic search and BM25, fused with reciprocal rank fusion. Scores are reported separately. A semantic cutoff alone does not decide every hit. Retrieval-only quotations are used when no Gemini key is set. Gemini calls use `GEMINI_MODEL` (default `gemini-3.5-flash-lite`). Transient failures are retried, then the retrieved pages are returned without the provider error.
- A scanned PDF stays `needs_ocr`. If its title matches an examination-timetable question, the assistant names that file and does not substitute a class timetable.
- Duplicate PDF uploads are rejected by SHA-256. Password changes increment `token_version` so older tokens stop working. The last active administrator cannot be removed. Login failures are rate limited in the API process. Public `/api/health` returns only `status`.
- Page excerpts join the matching chunks of a page in reading order. On the DAVV index the highest-scoring Ordinance 6 chunk does not contain the attendance percentage; see `docs/DATA_SOURCES_AND_PROVENANCE.md`.
- Full questions are not treated as follow-ups. Only explicit follow-up prefixes and fragments under 24 characters reuse the previous question.
- Complaint create, list, detail, assign, status changes, remarks required to resolve or close, history, and hiding other users' complaints.
- Agent tools: search documents, list events, check own complaint status, submit complaint, register for event. Mutations wait for YES. NO writes nothing.
- TF-IDF logistic regression and linear SVM trained on 160 synthetic complaints. Both: accuracy 0.625, macro precision 0.683, macro recall 0.625, macro F1 0.624. Logistic regression deployed. File: `models/metrics.json`.
- Keyword priority, stored as `rule_based`, with a disclaimer. No priority classifier.
- Events with capacity, duplicate prevention, and cancel. Notices with labelled extractive summaries when Gemini is absent.
- Admin analytics and the model page read from the database and from `metrics.json`.
- React pages for the three roles, including assistant, complaints, events, notices, documents, users, analytics, and model evaluation.
- Pytest: **21 passed in 20.94s** (`pytest -q` from `backend`).
- Public DAVV PDFs replaced the fictional Northbridge documents. Provenance is in `docs/DATA_SOURCES_AND_PROVENANCE.md`. Scanned PDFs are `needs_ocr` and are not cited. Demo accounts, complaints, and events are labelled DEMO DATA.
- On 12 November 2026, original PDFs linked from cpc.dauniv.ac.in, dsf.dauniv.ac.in (SDSF), and ietdavv.edu.in were downloaded and indexed when they had a text layer. No text was typed in from those sites.
- An earlier browser check used the deleted fictional PDFs (attendance citation, canteen refusal, projector complaint, workshop registration, admin charts). Those document counts and citations are not the current library. The current index was checked by script, not by a new browser pass.

## Partial

- Gemini answer generation and Gemini notice JSON. The code is in `backend/app/services/rag/generator.py` and `backend/app/services/notices.py`. No API key was set, so those branches were not called. The fallbacks were called.
- Faculty screens. The API rules are covered by `test_faculty_updates_only_assigned_complaint`. Those screens were not clicked in the browser pass.
- Agent event registration was tested in pytest (`test_agent_event_registration`). The browser registration used the Events page, not the agent prompt.

## Not built, on purpose

- OCR.
- A priority classifier. Keyword labels would have been circular.
- LangGraph or an LLM that chooses tools.
- Token revocation, httpOnly cookies, and rate limits.
- A real complaint log. The classifier corpus is synthetic and labelled. The ordinance PDFs are public files; four scans still need OCR.
- Alembic migrations. `create_all` builds a new SQLite file.
- Semantic clustering of frequent questions. The dashboard uses exact normalised strings.

## Not simulated

The app does not invent language-model text. With no key it quotes documents and says so. With a failed Gemini call it would show the error and the sources. Charts are SQL aggregates. Model scores are the training script's output.

## Known fixes included in this copy

- Emails use `@example.com` because the validator rejects `.test`.
- Similarity cutoff is 0.48 after measuring MiniLM scores. 0.35 let weak neighbours through.
- Complaint author relationship names `Complaint.user_id` so it is not confused with `assigned_to`.
- The assistant page no longer refers to a missing `response` object after a successful send.
