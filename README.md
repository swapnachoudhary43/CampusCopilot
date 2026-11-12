# CampusCopilot

CampusCopilot is a final-year demonstration of a campus assistant. Students ask questions about uploaded institutional PDFs. The system retrieves relevant pages, cites them, and refuses to invent a rule when the documents do not contain the answer. A separate assistant can file a complaint or register for an event, but only after the user confirms. Complaints are labelled by a saved scikit-learn model. Priority is a visible keyword rule, not a second model.

The starting document library is public material from **Devi Ahilya Vishwavidyalaya, Indore**, downloaded from dauniv.ac.in on 12 November 2026. Source URLs are stored with each file. See [docs/DATA_SOURCES_AND_PROVENANCE.md](docs/DATA_SOURCES_AND_PROVENANCE.md). Accounts, complaints, and events marked DEMO DATA were written for this project and are not DAVV records. Four of the downloaded PDFs have no text layer, so they are stored as `needs_ocr` and are not used as citations.

## What you can demonstrate

- Student, faculty, and administrator logins, with roles enforced by the API.
- Upload a text PDF, chunk it, embed it, and search it.
- A cited answer, and a refusal when the corpus has no answer.
- Complaint submission, including through the assistant after YES.
- Category prediction from the trained model, plus a rule-based priority.
- Events with capacity and duplicate checks.
- Notice summaries labelled as extracted, not verified.
- Admin charts counted from SQLite.

## Run it on Windows

Use PowerShell. The full beginner steps are in [docs/PROJECT_GUIDE/10_SETUP_AND_EXECUTION.md](docs/PROJECT_GUIDE/10_SETUP_AND_EXECUTION.md).

```powershell
cd "C:\Users\Swapna Choudhary\OneDrive\Desktop\CampusCopilot"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
copy backend\.env.example backend\.env
cd backend
..\.venv\Scripts\python.exe scripts\train_model.py
..\.venv\Scripts\python.exe scripts\seed.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```

Open http://localhost:5173 and http://localhost:8000/docs.

### Sample accounts

These exist only after `scripts/seed.py`. They are for the local demo.

| Role | Email | Password |
| --- | --- | --- |
| Administrator | admin@example.com | Admin@12345 |
| Faculty | faculty@example.com | Faculty@12345 |
| Student | student@example.com | Student@12345 |
| Student | student2@example.com | Student@12345 |

## Tests and model result

From `backend`, on the machine used to build this copy:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Last run recorded for this copy: **21 passed in 20.94s**.

The complaint classifier was trained on 160 synthetic complaints, with a stratified 128/32 split (`random_state=42`). Logistic regression and linear SVM both scored:

- Accuracy 0.625
- Macro precision 0.683
- Macro recall 0.625
- Macro F1 0.624

Logistic regression is the deployed model because it can report a class probability. The figures are copied from `models/metrics.json` after `scripts/train_model.py`. Re-running that script with the same seed reproduces them.

## Repository map

- `backend/app` — FastAPI application
- `frontend/src` — React application
- `data/official_documents/davv/` — public DAVV PDFs and `manifest.json`
- `data/sample_complaints/` — synthetic classifier sentences, not DAVV complaints
- `data/sample_events/` and `data/sample_notices/` — small DEMO DATA sets
- `models/` — saved classifier and `metrics.json`
- `docs/PROJECT_GUIDE/` — the viva guide
- `docs/IMPLEMENTATION_STATUS.md` — what is finished, partial, or intentionally not built

Gemini is optional. With an empty `GEMINI_API_KEY`, document answers quote the retrieved pages and say that no language model was used. The project does not invent an answer when the API is missing.
