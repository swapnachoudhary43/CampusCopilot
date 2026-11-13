# Demo script (about 12 minutes)

The document library is public DAVV PDFs. Accounts, complaints, and events are labelled DEMO DATA and are not DAVV records. If a number is not in the citation card, do not say it. If Gemini is not configured, do not apologise for retrieval-only mode. That mode is the honest fallback.

Accounts (DEMO DATA):

- Student: `student@example.com` / `Student@12345` (Meera Nair)
- Admin: `admin@example.com` / `Admin@12345` (Asha Menon)

Have two terminals already running: the project virtualenv uvicorn on port 8000, and `npm run dev`. Open the app once before the audience arrives so the embedding model is loaded. The first question after a cold start can take about 20 seconds.

## 0. Introduction (1 minute)

"CampusCopilot answers from uploaded PDFs and cites the page. If the PDFs do not contain the answer, it says so. A separate assistant can file a complaint or register for an event, but only after YES. Complaints get a category from a saved model. Priority is a keyword rule, and the screen says so. The ordinances are public DAVV files. The accounts, complaints, and events are demonstration records."

## 1. Student login (1 minute)

Open the landing page. Point at retrieval, refusal, confirmation, and database charts. Log in as Meera. The dashboard counts come from the API. If a list is empty, the page says so. Notices that are DEMO DATA carry that badge. Mention that summaries are labelled extracted, not verified.

## 2. A question that is in a PDF (2 minutes)

Assistant → Ask documents. Use "How does Ordinance 9 say fellowships are awarded?"

Expected:

- Badge: Quoted from documents — language model not used (unless a Gemini key is set, in which case the badge is Generated from retrieved documents).
- Source card: Ordinance No. 9 — Award of Fellowship and Scholarship, page 1, similarity about 0.54.
- The excerpt includes the heading and the sentence that the university invites applications through a newspaper advertisement.

Read that sentence from the card. Do not add a fellowship amount.

Optional second question, in a new conversation: "Explain the Choice Based Credit System in Ordinance 14." Expected source: Ordinance No. 14, page 1, score about 0.53, with the ordinance heading in the excerpt.

Do not use an attendance question as the main demo. On this index the highest Ordinance 6 chunk does not contain the percentage, and the page that does scored below 0.48.

## 3. A question that is not in the PDFs (1 minute)

New conversation. Ask "What is the canteen menu on Wednesday?"

Expected: "The uploaded institutional documents do not contain enough information" and no source cards. Badge: Not found in the uploaded documents.

Four downloaded PDFs (Ph.D. calendar, Ph.D. fees, anti-ragging committee, academic programmes) are stored as needs_ocr. They are not searched. Say that if someone asks why a scanned notice is missing.

## 4. Complaint through the assistant (2 minutes)

Campus actions. Choose "I want to complain about a broken projector in classroom LH-2."

Expected preview:

- Title and location include classroom LH-2.
- Predicted category Infrastructure, with a confidence. In one earlier run this was about 0.19. Say that confidence is the model's probability for this sentence, not the test-set accuracy.
- Suggested priority medium because of the keyword "broken", and the text says it is not a machine-learning priority model.

Click Confirm. Expected: a new complaint id and status `submitted`, with a DEMO DATA badge. Cancel on a second try if you want to show that NO writes nothing.

## 5. Event registration (1 minute)

Events. "DEMO: one-seat tour" may already be full. Register for "DEMO: assistant workshop". The count increases by one and the button becomes Cancel registration. Say these events are demonstration rows, not DAVV events.

## 6. Administrator (3 minutes)

Log out. Log in as `admin@example.com` / `Admin@12345`.

Dashboard: the counts come from the database. They change when you add a complaint. Do not memorise an old screenshot. Recent activity lists `complaint_created` and `event_registered` after those actions.

Analytics: category and status charts, registrations by event, and the questions you just asked. The user total ignores the date filter. Complaint counts do not.

Model evaluation: 160 synthetic rows, 128/32 split, logistic regression and linear SVM both at accuracy 0.625 and macro F1 0.624. Point at Transportation (all 4 correct) and Infrastructure or Other (weak). "We deployed logistic regression because the F1 scores tied and it can report a probability. This is not a real helpdesk log."

Documents: four ordinances are processed and show a source URL. Four scans show needs_ocr. Do not claim those scans were read.

## 7. Close (1 minute)

"The browser only calls FastAPI. FastAPI uses SQLite, FAISS, and the saved scikit-learn file. Gemini is optional. The test suite last recorded here was 21 passed. Official text comes from the downloaded PDFs. Demonstration records are labelled. There is no OCR, and the classifier was not trained on a real helpdesk."

## If something fails

| What you see | What to do |
| --- | --- |
| First question spins for a while | Say the embedding model is loading. Do not refresh repeatedly. |
| Badge says language model not used | Continue. Quote the excerpt. This is the no-key mode. |
| Badge says language model unavailable, but sources are listed | Gemini failed. Read the source card. Do not type your own answer. |
| Canteen question cites an ordinance | New conversation, then ask again. |
| A scanned notice is not found | It is stored as needs_ocr. OCR is not implemented. |
| Model page says metrics are missing | Run `python scripts/train_model.py` from `backend` with the project virtualenv before the demo. |
| Charts are zero | The database has no rows for that chart. Say so. Run `python scripts/seed.py` only if you want the labelled demonstration rows. |
| Login is rejected | Seed has not been run, or the password was changed. |
