# Team contributions

This file is a **suggested** split for three students. It is not a claim that a named person finished a module. The repository was built as one project. Replace "Member 1", "Member 2", and "Member 3" with your names only after the team agrees who will present each part. Until then, say "suggested allocation" in the report.

All three members must be able to explain the whole system. A viva panel can ask the frontend student how FAISS works.

## Suggested allocation

### Member 1 — documents, retrieval, and the language model

- PDF extraction with PyMuPDF, chunking, and the `needs_ocr` path.
- Sentence-transformer embeddings and the FAISS index.
- The RAG pipeline: threshold, citations, refusal, retrieval-only mode, Gemini prompt.
- `scripts/check_answers.py`, `scripts/probe_scores.py`, and the retrieval table in the testing guide.
- How to explain why RAG was chosen instead of fine-tuning.

Primary files: `backend/app/services/rag/`, `backend/scripts/generate_sample_pdfs.py`, `docs/PROJECT_GUIDE/06_RAG_AND_LLM_GUIDE.md`.

### Member 2 — API, database, complaints, agent, and the classifier

- FastAPI routers, SQLAlchemy models, JWT, and role checks.
- Complaint lifecycle and the privacy rule that hides other users' complaints.
- The five agent tools and the YES/NO confirmation.
- TF-IDF, logistic regression, linear SVM, `models/metrics.json`, and the rule-based priority.
- Pytest for auth, complaints, events, and the classifier.

Primary files: `backend/app/routes/`, `backend/app/models/`, `backend/app/services/agent/`, `backend/app/services/ml/`, `backend/tests/`.

### Member 3 — the React application

- Landing, login, registration, and the three dashboards.
- Assistant page, citation cards, and the Confirm button.
- Complaint, event, notice, document, user, analytics, and model pages.
- Axios client, protected routes, empty/loading/error states.
- How a chart gets its numbers from `/api/analytics/overview`.

Primary files: `frontend/src/`.

## Cross-learning checklist

Each person should be able to answer these without opening the code first, then confirm the answer in the file named.

1. Where is the password hashed, and what is stored in the `users` table? (`backend/app/core/security.py`)
2. Why does every request load the user from the database instead of trusting the role inside the token? (`backend/app/core/deps.py`)
3. What are the five complaint statuses, in order? (`backend/app/constants.py`)
4. What happens to a scanned PDF? (`backend/app/services/rag/ingest.py`, status `needs_ocr`)
5. What does similarity 0.48 mean, and where did that number come from? (`backend/.env.example` and `06_RAG_AND_LLM_GUIDE.md`)
6. What are the four `answer_mode` values? (`backend/app/services/rag/pipeline.py`)
7. Name the five agent tools. Which ones wait for YES? (`07_AI_AGENT_GUIDE.md`)
8. Why is there no priority classifier? (`08_MACHINE_LEARNING_GUIDE.md`)
9. What were the train and test sizes, and the macro F1? (`models/metrics.json`)
10. Which React route is admin-only, and where does the API repeat that check? (`frontend/src/App.jsx` and `require_roles("admin")`)
11. Why can the canteen question return no sources even though FAISS always finds nearest neighbours? (the threshold drops them)
12. Which records are public DAVV PDFs, which are DEMO DATA, and where does the UI say so? (`docs/DATA_SOURCES_AND_PROVENANCE.md`, source URLs, the DEMO DATA badge)

## How to practise

Sit together once. Member 1 asks Member 3 to trace one attendance question from the Send button to FAISS. Member 3 asks Member 2 to show the complaint row that the agent created. Member 2 asks Member 1 to explain a wrong classification from the confusion matrix. If someone can only describe their own folder, the checklist is not done.
