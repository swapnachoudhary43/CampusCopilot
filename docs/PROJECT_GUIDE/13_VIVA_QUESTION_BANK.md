# Viva question bank

Answers describe this repository, not a generic chatbot. If a number is not in `models/metrics.json` or in `docs/DATA_SOURCES_AND_PROVENANCE.md`, do not invent one. Official text comes only from the downloaded DAVV PDFs. Accounts, complaints, and events marked DEMO DATA are not DAVV records.

There are 122 questions.

## 1. Project overview

**1. What is CampusCopilot?**  
A campus web application. Students search uploaded PDFs, file complaints, read notices, and register for events. Administrators manage documents, users, and charts counted from the database. A classifier suggests a complaint category.

**2. Who is it for?**  
Students, faculty or staff, and administrators. Public registration creates students only. An administrator creates the other roles.

**3. What problem does it address?**  
Institutional rules sit in long PDFs. A normal chatbot can answer fluently and still be wrong. This project retrieves a page and shows it, and it refuses when the pages do not contain the answer.

**4. Why is it more than a CRUD application?**  
CRUD stores complaints, events, notices, and users. On top of that, PDFs are embedded and searched, answers are tied to pages, an agent can call five checked functions, and a saved model labels complaints. The charts are SQL aggregates, not drawings.

**5. Why is it more than a chatbot wrapper?**  
The assistant cannot run arbitrary SQL or Python. Document answers must come from retrieved chunks. Workflow changes wait for YES. Roles are enforced in FastAPI even if someone calls the API directly.

**6. Is the sample university real?**  
The four text ordinances are public DAVV PDFs with source URLs. Scanned DAVV PDFs are stored as needs_ocr and are not cited. Login accounts, complaints, and events are labelled DEMO DATA and are not DAVV records. Do not invent a fee or a date that is not in a cited excerpt.

**7. What can another college do without editing code?**  
An administrator can upload new text PDFs. Those files are chunked and indexed. Questions then search the new chunks. Categories and roles are still the ones in this project unless the code is changed.

**8. What should you not claim?**  
Do not claim Gemini was tested in this copy, that the classifier is production-ready, that scanned PDFs are readable, or that 0.625 accuracy is a large-scale result.

## 2. Problem statement and objectives

**9. State the problem in one sentence.**  
Students and staff need answers that stay faithful to institutional documents, plus a few campus workflows, without treating a language model as the source of the rules.

**10. What are the main objectives?**  
Cited document answers, a clear refusal, confirmed tool actions, complaint tracking with a trained category model, labelled notice summaries, event registration, and admin analytics from stored rows.

**11. What is in scope?**  
Three roles, PDF text extraction, FAISS search, optional Gemini, five tools, eight complaint categories, events, notices, and SQLite.

**12. What is out of scope?**  
OCR, payments, timetable generation, fine-tuning a language model, arbitrary code execution, and a second model for priority.

**13. Why three roles?**  
A student should not assign complaints or upload official PDFs. Faculty should see only assigned complaints. The administrator sees aggregates and manages documents. Hiding a button is not enough, so the API checks the role.

**14. What does success look like in the demo?**  
A student gets an Ordinance 9 citation whose excerpt matches the heading, the canteen question returns no sources, a complaint is saved only after YES, and the admin chart count matches the complaint table.

**15. Why keep the system small?**  
A 6-credit project has to be explained by the team. A smaller path that is true is stronger than a larger path that the team cannot defend.

## 3. System architecture

**16. Draw the request path in words.**  
The browser talks only to FastAPI. FastAPI reads SQLite. RAG uses FAISS and, if configured, Gemini. The browser never opens the database or the vector index.

**17. Why FastAPI?**  
It gives typed request bodies through Pydantic, dependency injection for the current user, and Swagger at `/docs`, which is useful in a viva.

**18. Why SQLite?**  
It is a single file, needs no server, and is enough for a demonstration. Foreign keys are turned on with `PRAGMA foreign_keys=ON`. It will not serve a whole university at once. That limit is stated, not hidden.

**19. Why React and Vite?**  
React fits a multi-page dashboard with shared layout. Vite is the dev server and the production build. Tailwind handles spacing and the indigo palette without a component library.

**20. Why is RAG a service and not the route function?**  
`routes/chat.py` loads the conversation and calls `answer_question`. Embedding, search, and the prompt live in `services/rag/`. Tests can call that function without HTTP.

**21. Where is configuration?**  
`backend/.env`, read by `app/core/config.py`. The frontend only needs `VITE_API_URL`. Secrets stay on the server.

**22. What happens on startup?**  
The FastAPI lifespan calls `init_db()`, which creates tables if they are missing. It does not seed data and it does not train the model. Those are scripts.

**23. Why no LangGraph?**  
The agent has five tools and a YES/NO gate. A rule function in `intent.py` is easier to explain and to test than a graph framework. LangGraph was not added.

## 4. Python and FastAPI

**24. What is a router?**  
A group of paths. `auth.py` has prefix `/api/auth`. `main.py` includes each router. Adding an endpoint means a function on the right router, a Pydantic body if it accepts JSON, and a role dependency if it is protected.

**25. What is Pydantic doing here?**  
It checks types and constraints before the function runs. A short password or a bad category becomes HTTP 422. The handler can assume the fields exist.

**26. What is a dependency?**  
`get_db` opens a session. `get_current_user` reads the bearer token. `require_roles("admin")` returns 403 for other roles. Routes declare these with `Depends`.

**27. Why status codes instead of always returning 200?**  
Clients and tests branch on them. 201 means created, 401 means log in again, 403 means the role is wrong, 404 means not visible, 409 means a conflict such as a duplicate email.

**28. How would you add a "list my notices" filter?**  
Add an optional query parameter on `GET /api/notices`, filter the SQLAlchemy query, and add a pytest that creates two notices and checks the filter. Do not filter only in React.

**29. What is CORS doing?**  
The API allows the Vite origins in `CORS_ORIGINS`. The browser would block the React app without that. CORS is not authentication.

**30. Why `create_all` and not Alembic?**  
The schema is created from the models for a new SQLite file. That is intentional for this project. Changing a column later does not migrate old files automatically. Delete the demo database and seed again if the models change.

**31. What does the health endpoint prove?**  
That the process is up, which embedder is configured, whether a Gemini key is present, how many vectors are indexed, and whether the joblib file exists. It does not prove that a particular PDF answer is correct.

## 5. React and frontend

**32. How does the UI know who is logged in?**  
`AuthContext` stores the token in `localStorage` under `cc_token` and calls `GET /api/auth/me`. `ProtectedRoute` sends anonymous users to the login page and blocks a role that is not in the route's list.

**33. Is hiding a nav link the security control?**  
No. It is only a convenience. The API repeats the check. A student who requests `/api/users` still gets 403.

**34. How does a page call the API?**  
`frontend/src/services/api.js` is an Axios instance. It attaches the bearer token. Pages call `api.get` and `api.post`. `errorMessage` reads FastAPI's `detail` field.

**35. What does the assistant page show for a document answer?**  
The reply, a badge for `answer_mode`, and a card per source with title, page, similarity, and excerpt. Retrieval-only mode says the language model was not used.

**36. How does Confirm work?**  
If the latest agent message needs confirmation, the page shows Confirm and Cancel. They send the exact strings `YES` and `NO`. The user does not have to remember the keyword, but the server still requires that short reply.

**37. Where do chart numbers come from?**  
`pages/admin/Analytics.jsx` and the admin dashboard call `/api/analytics/overview`. Recharts draws `complaints_by_category` and the other arrays. There is no chart data file of fake counts.

**38. What did the model page display on this copy?**  
Dataset size 160, split 128/32, deployed model logistic regression, accuracy 0.625, macro F1 0.624, and both confusion matrices. Those cells are read from `models/metrics.json`.

## 6. SQL and database

**39. Name the main tables.**  
`users`, `documents`, `document_chunks`, `complaints`, `complaint_history`, `events`, `event_registrations`, `notices`, `conversations`, `chat_messages`, `pending_actions`, `audit_logs`.

**40. What is the users primary key?**  
An integer id. Email is unique. `password_hash` is the bcrypt string. Role is `student`, `faculty`, or `admin`.

**41. Why does `complaints` have two foreign keys to `users`?**  
`user_id` is the author. `assigned_to` is the staff member. SQLAlchemy needs `foreign_keys` on the relationships or it cannot tell them apart.

**42. How is a registration kept unique?**  
A unique constraint on `(event_id, user_id)`. Cancelling sets `status` to `cancelled` instead of deleting the row, so the same pair can register again later only if the service allows that status. The service rejects a second active registration.

**43. Where is the embedding stored?**  
Each `document_chunks` row has a float32 blob, plus document id, page number, and chunk index. FAISS is a second copy for search. After a delete, the index is rebuilt from the blobs.

**44. What does complaint history store?**  
The action, old status, new status, a note, the actor id, and the time. It is the audit trail of the lifecycle.

**45. Give an example complaint row from the demo.**  
A projector complaint can show `predicted_category=Infrastructure`, `priority_method=rule_based`, `suggested_priority=medium`, and `status=submitted`. The exact id depends on seed order. In one browser run the confirmed agent complaint was id 6.

**46. Why indexes?**  
Email lookup, complaint owner, assignee, and event registrations are filtered often. Indexes are declared on those columns in the models. SQLite is still a demo database.

## 7. Authentication and security

**47. How are passwords stored?**  
bcrypt hashes. The plaintext is never saved and never returned by the API. bcrypt only uses the first 72 bytes, so longer passwords are rejected rather than silently truncated.

**48. What is in the JWT?**  
The user id in `sub`, signed with HS256 and `SECRET_KEY`. The role is not trusted from the token. `get_current_user` loads the row.

**49. How long is a token valid?**  
`ACCESS_TOKEN_EXPIRE_MINUTES`, default 480. Logout only deletes the browser copy. A stolen token works until expiry. That is a documented limitation.

**50. How do you prevent one student reading another's complaint?**  
`visible_complaints` filters by `user_id` for students and by `assigned_to` for faculty. A missing or hidden complaint raises the same 404 text.

**51. How do you prevent path traversal on upload?**  
The stored filename is a UUID plus `.pdf`. The original name is kept only as display metadata, with slashes stripped.

**52. Can the agent run SQL that the user typed?**  
No. Tools are Python functions with validated arguments. The user id is taken from the token, not from the sentence.

**53. What is still weak for a real deployment?**  
The token is in `localStorage`, there is no rate limit, CORS is for local Vite, SQLite has one writer, and the seeded passwords are in the README for the demo. Say that before anyone asks.

**54. Why does failed login return one message?**  
`Email or password is incorrect.` does not reveal whether the email exists. The attempt is written to the audit log without the password.

## 8. RAG

**55. What does RAG stand for, and what is the pipeline here?**  
Retrieval-augmented generation. Question, embedding, FAISS, drop scores below 0.48, join chunks of the same page, then either quote them, send them to Gemini, or refuse.

**56. Why RAG instead of fine-tuning?**  
A new PDF must be searchable the day it is uploaded, and the answer must cite a page. Fine-tuning bakes text into weights, does not show the page, and would need a new training run for every circular. This project does not fine-tune.

**57. What is chunking?**  
Pages are cut into windows of about 900 characters with about 150 characters of overlap, so a sentence on a boundary still appears in one window. Each chunk keeps its page number.

**58. What is a citation in this app?**  
Document title, page number, similarity score, and an excerpt. Several chunks of one page that pass the cutoff are joined in reading order. The card shows the highest score on that page.

**59. How do you know a retrieved page is relevant?**  
The score is cosine similarity of normalised MiniLM vectors. On this sample corpus, useful questions scored about 0.51 to 0.68 and the canteen and Wi-Fi questions scored about 0.39 to 0.40. The cutoff 0.48 sits between those groups. It is not a universal constant.

**60. What if two documents are both relevant?**  
Both can be returned. Exam dates cited the calendar at 0.6357 and the examination schedule at 0.6203. A gap rule that keeps only a clear winner would have dropped the second true source, so it was not used.

**61. What happens when the documents do not contain the answer?**  
`answer_mode` is `insufficient_context`, `sources` is empty, and the text says the documents do not contain enough information. The model is not called. The canteen question is the demo of this.

**62. What about the library fine?**  
The sample PDFs say they do not define a library fine. Those sentences score above 0.48, so they are cited. The honest reading is the negation in the excerpt. Do not add a fine amount.

**63. What happens when a new PDF is uploaded?**  
Text is extracted, chunked, embedded, stored, and the FAISS index is rebuilt from all processed chunks. No application code change is required. A scanned PDF is saved as `needs_ocr` and is not searched.

**64. How are hallucinations limited?**  
The prompt, when Gemini is used, may only use the supplied chunks. Retrieval-only mode quotes instead of paraphrasing. Below-threshold chunks are discarded. The reply must admit missing information. This reduces invention. It does not make a language model perfect, and Gemini was not live-tested here.

## 9. Embeddings and vector databases

**65. What is an embedding?**  
A list of numbers that places similar texts near each other. This demo uses `all-MiniLM-L6-v2`, which produces 384-dimensional vectors.

**66. What is cosine similarity here?**  
Vectors are L2-normalised. Their inner product is then the cosine. FAISS `IndexFlatIP` computes that inner product against every stored vector. Exact search is acceptable because the demo has tens of chunks, not millions.

**67. Why FAISS?**  
It is a local library. It does not need a paid vector database. The index is a file under `backend/storage`, rebuilt from SQLite, so it can be explained and deleted.

**68. Why also store the vector in SQLite?**  
FAISS does not hold the page text in a way we want to manage. The database is the source of truth. Rebuild reads the blobs and writes a new index.

**69. What is the hash embedder?**  
A test double selected with `EMBEDDING_BACKEND=hash`. It is deterministic and does not download a model. It is not semantic search. The health endpoint reports which backend is active. Do not demo with `hash`.

**70. What does a score of 0.62 mean?**  
On this index, the attendance question's best chunk scored 0.6033, and the UI later showed about 0.62 for the merged page. It means "closer than the cutoff", not "62 percent probability that the answer is correct".

**71. What breaks if you mix embedding models?**  
Distances from two models are not comparable. Upload is rejected with 409 if the index backend name does not match the current embedder. Reindex after a switch.

**72. Why was 0.35 rejected as a cutoff?**  
At 0.35 the library-fine question and other weak neighbours were returned as if they were evidence. Measured scores showed a gap around 0.40 versus 0.51, so 0.48 was chosen for this corpus and this model.

## 10. LLMs

**73. What is an LLM in this project?**  
A remote Gemini model that writes a sentence from retrieved chunks, or summarises a notice. It is optional. With an empty key the app does not pretend a model answered.

**74. What is retrieval-only mode?**  
`answer_mode=retrieval_only`. The reply quotes excerpts and says a language model was not used. That is what this copy demonstrated.

**75. What is in the Gemini prompt?**  
The question and the retrieved chunks, with title and page. The instruction is to use only that context, cite the page, and say when the context is insufficient. Earlier chat is only a hint for follow-up wording, not a source of rules.

**76. What if the Gemini API fails?**  
`answer_mode=llm_unavailable`. The sources are still shown, with an error. A substitute paragraph is not written by the server. This failure path was not executed against the live API in this environment.

**77. What model name is configured?**  
`GEMINI_MODEL` defaults to `gemini-3.5-flash-lite` in `.env.example`. `gemini-2.0-flash` was shut down on 1 June 2026 and is not the default. The code calls `client.models.generate_content`. Transient Gemini failures are retried. A failed call quotes the retrieved pages and does not show the provider's raw error.

**78. Why not let the LLM answer from its own memory of universities?**  
Those memories are not this institute's PDF, and they may be wrong. The product requirement is to cite uploaded documents or refuse.

**79. Are notice dates verified?**  
No. They are extracted strings. `extraction_disclaimer` says so. `summary_method=extractive_fallback` means the summary is the first sentences of the notice, not a Gemini rewrite.

## 11. AI agents and tool calling

**80. What does "agent" mean here?**  
A function that picks one of five backend tools from the sentence, using rules, then either answers or waits for confirmation. It is not an autonomous planner and it does not call Gemini to choose tools.

**81. How is that different from the document chatbot?**  
The document chatbot only retrieves and answers. The agent can create a complaint or a registration. Those writes are gated.

**82. Name the tools.**  
`search_campus_documents`, `list_available_events`, `check_complaint_status`, `submit_complaint`, `register_for_event`.

**83. Which tools change data?**  
`submit_complaint` and `register_for_event`, and only after YES. Listing, searching, and status checks do not.

**84. Walk through the projector complaint.**  
The sentence matches a complaint pattern. Location "classroom LH-2" is extracted. The classifier labels Infrastructure. The priority rule sees "broken" and suggests medium. The reply asks for YES. Confirm sends YES. The row is inserted and the reply includes the new id and status `submitted`.

**85. What is a valid confirmation?**  
A short reply such as YES. A paragraph that happens to contain "yes" is not confirmation. NO cancels the pending action and writes nothing.

**86. How are arguments checked?**  
The tool functions validate fields the same way the REST API does. Capacity, duplicate registration, and complaint visibility are enforced in the service layer. The model does not supply the user id.

**87. Where is the action recorded?**  
Complaint history, the chat messages, and `audit_logs` for important actions such as complaint creation and event registration. `pending_actions` holds the unconfirmed payload.

## 12. Machine learning

**88. What is the dataset?**  
160 sentences written for this project, 20 in each of 8 categories. Columns include id, text, category, and source. Training uses text and category. The file says the data is synthetic. There is no claim of a public licence because it is project-authored. It does not reflect a real complaint desk.

**89. Why synthetic?**  
A suitable public, campus-specific, labelled set was not used. The limitation is that the sentences are cleaner and more obvious than real complaints. "Bus" is easy for Transportation. "Other" is vague.

**90. What is TF-IDF?**  
Term frequency–inverse document frequency. A word that appears in one complaint and not in most others gets a higher weight. Unigrams and bigrams are used. The vectorizer is fit on the 128 training rows only, then applied to the test rows.

**91. What is logistic regression doing?**  
It learns a weight vector per class and turns the scores into probabilities with a softmax. The deployed model uses those probabilities as confidence.

**92. What is the linear SVM?**  
`LinearSVC` learns a maximum-margin boundary. It is the comparison model. It does not offer `predict_proba`. The code can turn decision margins into a softmax, and it labels that value as not a probability. The deployed model is logistic regression, so the demo confidence is a real class probability.

**93. Why did both models tie?**  
On this split they made the same mistakes. Macro F1 was 0.624 for both. The selection text in `metrics.json` says they tied and logistic regression was kept because it can report a probability. An earlier bug said logistic regression "had the higher" F1 even when the numbers were equal. That wording was corrected and the file was regenerated.

**94. What is the train/test split?**  
`train_test_split` with `test_size=0.2`, `stratify=category`, `random_state=42`. 128 train, 32 test, 4 per class. The test rows are not fit. There is no validation fold beyond that hold-out.

**95. Is the dataset imbalanced?**  
No. Each class has 20 rows. `class_weight="balanced"` is still set so a future uneven file would up-weight rare classes. On this file it does not change the story. The hard classes are hard because the words overlap, not because they had fewer rows.

## 13. Model evaluation

**96. Define accuracy on this test.**  
Correct predictions divided by 32. 20 were correct, so accuracy is 0.625.

**97. Why report macro F1 and not only accuracy?**  
Macro F1 averages the F1 of each class equally. Accuracy can look fine if a big class dominates. This set is balanced, so the two numbers are close, but macro F1 is still the right summary when you care about every category. Here macro F1 is 0.624.

**98. What are precision and recall?**  
Precision: of the rows predicted as a class, how many truly were that class. Recall: of the true rows of a class, how many were found. Macro precision on this run is 0.683. Macro recall is 0.625.

**99. Read one confusion-matrix cell.**  
Transportation's row is four correct predictions. Cleanliness has one correct, two predicted as Infrastructure, and one as Other. Rows are the true class. Columns are the prediction. Each class has support 4.

**100. Why is Infrastructure weak?**  
Several test sentences were predicted as Hostel or Other. Per-class F1 for Infrastructure in this file is 0.25. A live projector sentence was still labelled Infrastructure, with confidence about 0.19. The label can be right while the probability stays modest. Do not quote 0.19 as the model's accuracy.

**101. What would you do if a real dataset were imbalanced?**  
Keep the stratified split, look at per-class recall, and keep `class_weight` or collect more minority examples. Do not only quote accuracy. This project did not need resampling because the synthetic file is balanced.

**102. Where can the examiner see the numbers?**  
`models/metrics.json`, the training script's printout, and the admin Model evaluation page. If the file is missing, the page returns an error telling you to run `scripts/train_model.py`.

**103. Did you tune hyperparameters on the test set?**  
No. Defaults were used with the fixed split. The test set was not used to pick the cutoff of the vectorizer or to choose which model won, except for the pre-declared rule: if logistic regression is within 0.02 macro F1 of the best, deploy it so the API can show a probability. On this run the F1 values were equal, so that rule applied.

## 14. Testing

**104. How do you run tests?**  
From `backend`: `..\.venv\Scripts\python.exe -m pytest -q`. The last recorded result is 21 passed in 20.94s.

**105. Name three behaviours the tests lock in.**  
Invalid login is 401. A student cannot list users. A question with no supporting chunk does not invent an answer. Also: duplicate event registration fails, and the agent does not save a complaint before YES.

**106. Why a hash embedder in tests?**  
So the suite does not download MiniLM and does not depend on GPU or network. Semantic quality is measured separately by `check_answers.py` on the seeded index.

**107. What is not covered by an automated test?**  
A live Gemini HTTP call, OCR, the visual layout of every page, and load. Faculty update rules are tested. The faculty screens were not clicked in the browser pass described in the testing guide.

**108. How was the UI checked?**  
The Vite app was used in a browser: attendance citation, canteen refusal, confirmed complaint, event registration, admin counts, analytics, and the model page. A follow-up bug and a citation that started mid-page were fixed and checked again.

**109. What is a good answer if a test fails on the examiner's laptop?**  
Read the assertion, fix the cause, and re-run. Do not edit the test to match a wrong behaviour, and do not quote the old "21 passed" line after the code has changed.

**110. Where is the test database?**  
A temporary file per test. The suite does not write the demo `campuscopilot.db`.

## 15. Limitations

**111. What are the important limits?**  
Fictional data, no OCR, Gemini optional and untested live, a 32-row test set, exact-match question analytics, SQLite, JWT in localStorage, no rate limit, and retrieval that can cite a sentence whose point is that a fact is absent.

**112. What happens when Gemini is down or unset?**  
Unset: retrieval-only quotations. Configured but failing: sources plus `llm_unavailable`. Neither path fabricates a policy.

**113. Why is citing the library fine a limitation and not a bug in the threshold?**  
The pages really do discuss the fine, by saying it is not defined. Similarity cannot tell "this sentence answers the question" from "this sentence mentions the topic in order to refuse it". The demo instruction is to read the excerpt.

**114. What is weak about frequent questions?**  
They are exact lower-cased strings. "attendance percentage" and "minimum attendance" stay as two rows. Complaint text is excluded, which is deliberate.

**115. What is weak about the first request?**  
The embedding model loads on first use and can take around 20 seconds. Warn the audience. Later questions in the same process are faster.

**116. What must you say about the 0.625 score?**  
It is the hold-out result on 32 synthetic sentences. It is reproducible with `random_state=42`. It is not evidence about a real campus helpdesk.

## 16. Future scope

The last section continues the numbering. These are future work, not implemented features.

**117. What would you add first?**  
OCR for scanned circulars, with the same page citations, and a clear flag when OCR confidence is low.

**118. How would you harden auth?**  
HttpOnly cookies, shorter token life, rotation, and a logout list or short expiry. Rate-limit login.

**119. How would you improve the classifier?**  
Real complaints with permission, more than 4 test rows per class, an error analysis of Infrastructure versus Other, and a probability threshold that shows "uncertain" when confidence is as low as the projector example.

**120. Would you add a priority model later?**  
Only with priority labels that were assigned by staff, not labels generated from the same keywords the rule uses. Otherwise the model just memorizes the rule. Until then the keyword reason should stay visible.

**121. How would search improve?**  
A cross-encoder reranker, hybrid keyword plus vector search, and a fresh probe of the threshold whenever the embedder changes. Cluster similar questions before calling them "frequent".

**122. What should the report not promise?**  
Multi-campus tenancy, mobile apps, payment, proctoring, or a guarantee that the language model never errs. Those are not in this build.
