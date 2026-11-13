# Setup and execution

These steps match a Windows 11 machine using Cursor or VS Code and PowerShell. The project folder in this copy is:

`C:\Users\Swapna Choudhary\OneDrive\Desktop\CampusCopilot`

Python 3.10 and Node.js 18 or newer are enough. This copy was built with Python 3.10.11 and Node 24.

Never put a real Gemini key in a file that you commit. `backend/.env` is listed in `.gitignore`.

## 1. Open the folder

In PowerShell:

```powershell
cd "C:\Users\Swapna Choudhary\OneDrive\Desktop\CampusCopilot"
```

## 2. Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

The first install downloads PyTorch and is large. Wait until it finishes. If pip says a file is locked, pause OneDrive sync for this folder and run the command again.

## 3. Environment file

```powershell
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
```

Open `backend/.env`. Leave `GEMINI_API_KEY` empty for the retrieval-only demo. Replace `SECRET_KEY` with a long random string before you show the project on any network other than your own laptop. Do not commit the filled `.env`.

`frontend/.env` should contain:

```text
VITE_API_URL=http://localhost:8000
```

## 4. Train the complaint classifier

```powershell
cd backend
..\.venv\Scripts\python.exe scripts\train_model.py
```

This writes `data/sample_complaints/complaints.csv` and the files in `models/`. The printed accuracy, precision, recall, and macro F1 must match `models/metrics.json`. On this project those numbers are accuracy 0.625 and macro F1 0.624 for both models. If you change the sentences in `scripts/complaint_corpus.py`, the numbers will change. Report the new file, not the old numbers.

## 5. Create the database and sample data

Still inside `backend`:

```powershell
..\.venv\Scripts\python.exe scripts\seed.py
```

This is safe to run again. It will not duplicate the seeded users, public PDFs, events, or notices. It loads the PDFs listed in `data/official_documents/davv/manifest.json`. It does not invent university PDFs. Re-running it labels every complaint already in the database as DEMO DATA.

The first run downloads `sentence-transformers/all-MiniLM-L6-v2` (about 90 MB). A Hugging Face warning about unauthenticated requests or Windows symlinks is harmless. You can set `HF_HUB_DISABLE_SYMLINKS_WARNING=1` if you want that warning to stop.

At the end, the script prints a retrieval check. The Ordinance 9 question should cite that ordinance. The canteen question should be `insufficient_context`.

Seeded accounts are DEMO DATA, not DAVV accounts:

| Role | Email | Password |
| --- | --- | --- |
| Administrator | admin@example.com | Admin@12345 |
| Faculty | faculty@example.com | Faculty@12345 |
| Student | student@example.com | Student@12345 |
| Student | student2@example.com | Student@12345 |

Change these passwords if the laptop is shared.

`scripts/init_db.py` only creates empty tables. `seed.py` already calls that. You do not need both unless you want an empty database.

## 6. Start the backend

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` and `http://localhost:8000/api/health`. Health should show `classifier_available: true` and a non-zero `indexed_chunks` after seeding.

The first question after startup loads the embedding model. That can take about 20 seconds. Later questions are faster.

## 7. Start the frontend

In a second PowerShell window:

```powershell
cd "C:\Users\Swapna Choudhary\OneDrive\Desktop\CampusCopilot\frontend"
npm install
npm run dev
```

Open `http://localhost:5173`. Log in as `student@example.com` / `Student@12345`.

## 8. Run the tests

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Last recorded run on this copy: **21 passed in 20.94s**. Tests use a temporary SQLite file, the hash embedder, and `LLM_PROVIDER=retrieval_only`. They do not call Gemini and they do not use the demo database.

## 9. Optional checks

Score probe, from `backend`. `PYTHONPATH` is required because running a file in `scripts/` does not put `backend/` on the path:

```powershell
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe scripts\probe_scores.py
..\.venv\Scripts\python.exe scripts\check_answers.py
```

`train_model.py` and `seed.py` add the path themselves. The probe scripts do not.

## Troubleshooting

**`ModuleNotFoundError: app` when running a script.**  
Run it from the `backend` folder. For `probe_scores.py` and `check_answers.py`, set `$env:PYTHONPATH = "."`.

**Registration says the email is invalid.**  
Do not use `.test` addresses. Use `@example.com`.

**Upload says the index was built with a different backend.**  
The demo index is MiniLM. Tests use a hash embedder in a separate database. If you switched `EMBEDDING_BACKEND` on the demo database, log in as admin and use Rebuild search index, or delete `backend/storage/faiss.index` and `faiss_meta.json` and run `seed.py` again.

**A scanned PDF is stored but not searchable.**  
Status `needs_ocr`. This project does not run OCR. Use a text PDF, or say that limitation in the viva.

**The assistant quotes text and says no language model was used.**  
`GEMINI_API_KEY` is empty. That is the intended demo mode. It is not a failure.

**Gemini returns an error after you add a key.**  
The sources should still appear and `answer_mode` should be `llm_unavailable`. Do not paste a made-up answer into the slide.

**Port 8000 or 5173 is already in use.**  
Another terminal is still running the server. Stop that process, or pick a different port and set `VITE_API_URL` to match.

**OneDrive locks `campuscopilot.db` or a `.joblib` file.**  
Pause sync, close extra Python processes, and retry.

**Charts are empty.**  
You are logged in as admin but `seed.py` was not run, or the date filter excludes the sample complaints. Clear the dates and apply again.

**pytest is slow the first time.**  
The hash embedder is used in tests, so the sentence-transformer model should not download during pytest. If a test process still downloads it, check that `EMBEDDING_BACKEND` in the environment is not forcing MiniLM. `tests/conftest.py` sets the hash backend for the suite.
