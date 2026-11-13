# Testing and evaluation

Do not say "all tests pass" from memory. The command and the result below were run on this copy.

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

Result: **21 passed in 20.94s**.

## How the suite is isolated

`backend/tests/conftest.py` gives every test a temporary SQLite file, `EMBEDDING_BACKEND=hash`, `LLM_PROVIDER=retrieval_only`, and a long test `SECRET_KEY`. bcrypt cost is 4 so hashing stays fast. The hash embedder is a bag-of-tokens stand-in. It is not the model used in the demo. Retrieval tests still check the pipeline: chunk, store, search, cite, and refuse.

Gemini was not called. There was no API key in this environment. The code path that calls Gemini is in `backend/app/services/rag/generator.py`. It was reviewed against the `google-genai` client (`models.generate_content`), but it has not been executed against Google's servers here. Say that clearly.

## Test cases

Authentication (`tests/test_auth.py`):

- Register, then `GET /api/auth/me` returns the same student.
- Wrong password returns 401.
- Duplicate email returns 409.
- A student token cannot `GET /api/users` (403).
- A request with no token returns 401.

Documents and RAG (`tests/test_documents_and_rag.py`, `tests/test_chunking.py`):

- A non-PDF upload is rejected.
- Bytes that are not a real PDF are rejected even if the name ends in `.pdf`.
- A PDF with no extractable text is stored as `needs_ocr` and is not indexed.
- A small text PDF is indexed. A question about its rule returns the document title, the page, and the number that was written in the PDF.
- A question whose words are not in the PDF returns `insufficient_context` and an empty source list.
- A student cannot upload.
- A long page is split into overlapping chunks.

Workflows (`tests/test_workflows.py`):

- A student creates a complaint and cannot read another user's complaint (404, not 403, so the existence is not confirmed).
- Faculty can update a complaint only after it is assigned to them. Resolving without remarks fails. A second faculty member cannot update it.
- Event registration rejects a duplicate and rejects a registration when capacity is 1 and already taken.
- The agent shows a complaint preview and does not insert a row until the next message is `YES`.
- `NO` does not insert a row.
- The agent registers the logged-in user for an event only after `YES`.
- A notice summary is labelled `extractive_fallback` when no Gemini key is set, and the disclaimer is present.
- Analytics counts grow when a complaint is added. The numbers come from the test database, not from constants in the route.

Machine learning (`tests/test_ml.py`):

- Trains on a temporary copy of the synthetic corpus.
- Checks the split is 128/32, stratified, and that the vectorizer was fit on the training split only.
- Checks the deployed bundle can predict one of the eight labels.
- The test does not assert the 0.625 figure, because that figure belongs to the saved experiment file. The experiment file is the record of the real run.

## RAG evaluation on the DAVV PDFs

This is separate from pytest. After the fictional PDFs were removed and the public ordinances were indexed, these scores were measured with `all-MiniLM-L6-v2` and threshold 0.48. The older Northbridge scores are withdrawn.

| Question | Result |
| --- | --- |
| How fellowships are awarded under Ordinance 9 | `retrieval_only`. Ordinance 9, page 1, score 0.54. The passage starts with the ordinance heading. |
| Attendance under Ordinance 6 | `retrieval_only`. Top hit is Ordinance 6, page 2, score 0.6786, and that chunk does not contain the percentage. Page 1, which says "seventy five percent", scored 0.4589 and was excluded. Ordinance 14, page 3, scored 0.5009 and does contain "atleast seventy-five percent". |
| Canteen menu | `insufficient_context`. No sources. Nearest score 0.2702. |
| Wi-Fi password | Not cited. Nearest score 0.1245. |

The earlier browser check of a 75 percent quotation used the deleted fictional PDFs. Do not describe that screen as the current corpus.

A bug found during that check: any question shorter than 50 characters was treated as a follow-up, so "What is the canteen menu on Wednesday?" inherited the previous attendance question and cited the attendance PDF. That rule now applies only to explicit follow-ups ("and", "what about", "how about", "then", "also") and fragments shorter than 24 characters. A later check with the attendance question still in the history returned `insufficient_context` and zero sources for the canteen question.

## Classification evaluation

From `models/metrics.json` after `scripts/train_model.py` on the 160 synthetic sentences:

- 20 complaints in each of 8 classes. The set is balanced.
- Stratified shuffle split, `test_size=0.2`, `random_state=42`: 128 train, 32 test, 4 test rows per class.
- TF-IDF unigrams and bigrams, fit on the training rows only.
- Logistic regression and linear SVM, both with `class_weight="balanced"`.
- Both models: accuracy 0.625, macro precision 0.683, macro recall 0.625, macro F1 0.624. 20 of 32 test rows were correct.
- Logistic regression is deployed because the scores tied and it can report `predict_proba`.

The confusion matrix is in `08_MACHINE_LEARNING_GUIDE.md` and on the admin Model evaluation page, which reads the JSON file. Transportation and IT Support were perfect on this tiny test split. Infrastructure, Cleanliness, and Other were weak. With 4 examples per class, one mistake moves recall by 0.25. Do not describe 0.625 as a production accuracy.

## What was exercised in the browser

An earlier pass on `http://127.0.0.1:5173` used the fictional PDFs that have since been deleted. It checked login, a refusal, a confirmed complaint, event registration, admin charts, and the model page. Those document titles and counts are not the current library. The current ordinance scores are the table above, measured by script. A browser pass on the DAVV library was not repeated in that earlier session.

Faculty screens were not clicked in that browser pass. Faculty restrictions are covered by `test_faculty_updates_only_assigned_complaint`.

## Known limits of this evaluation

- No live Gemini call, so generation quality and notice JSON from Gemini are unmeasured.
- The hash embedder in pytest does not measure MiniLM quality. The table above is the MiniLM check.
- The classifier test set has 32 rows. The scores are reproducible, and they are also fragile.
- No load test was run. The first embedding load is the slow step a demo audience will notice.
