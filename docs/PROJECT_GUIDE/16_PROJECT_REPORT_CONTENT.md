# Project report content

This is source material for the university report. Rewrite it in the department's format. Do not paste it as finished chapters without adding your names, guide, and college.

Numbers below come from this repository's `models/metrics.json` and from the retrieval check in `11_TESTING_AND_EVALUATION.md`. If you retrain or change the PDFs, replace the numbers. Do not keep the old ones.

References are real publications and documentation pages. Open each link before you submit. Pages move. If a link fails, find the same work on the publisher site and cite what you actually read. Do not add papers you have not opened. Do not invent results from those papers.

## Chapter 1. Introduction

Campus information is spread across regulations, calendars, fee notes, and hostel rules. Students ask questions that have a short factual answer, but the answer is only trustworthy if it can be pointed at a page. A chat window that replies from a general language model can sound confident and still state the wrong percentage or the wrong date.

CampusCopilot is a web application for that setting. Uploaded PDFs are split into chunks, embedded, and searched. The answer shows the document and the page, or it says the documents do not contain the answer. A second mode can submit a complaint or register for an event, and it waits for an explicit confirmation. Complaints are stored with a status history and a category from a saved classifier. Priority is a separate keyword rule. Administrators see counts computed from the database.

The starting library is public DAVV PDFs listed in `docs/DATA_SOURCES_AND_PROVENANCE.md`. Demonstration accounts, complaints, and events are labelled and are not DAVV records. Another institution can upload its own text PDFs without changing the source code.

## Chapter 2. Literature review

Write this chapter from the papers, in your own words, after you have read them. The notes below are only a map.

Retrieval-augmented generation attaches a search step to a generator so the generator conditions on retrieved text instead of on parameters alone. Lewis and colleagues describe that pattern for knowledge-intensive tasks (arXiv:2005.11401). This project uses the same idea at campus scale: the knowledge is the uploaded PDF, and the citation is the page number.

Sentence embeddings map text to vectors so that related sentences lie closer together. Reimers and Gurevych introduce Sentence-BERT for that (arXiv:1908.10084). The demo model is `all-MiniLM-L6-v2`, a small distilled transformer in that family. Wang and colleagues describe the MiniLM distillation setup (arXiv:2002.10957). The model card is on Hugging Face. Say which model you ran. Do not claim you trained it.

Nearest-neighbour search over those vectors is exact in this project. Johnson, Douze, and Jégou present FAISS for similarity search (arXiv:1702.08734). We use `IndexFlatIP` on normalised vectors, which is cosine similarity, because the index is small enough to scan.

The transformer architecture that current language models use is described by Vaswani and colleagues (arXiv:1706.03762). This project does not train a transformer. It optionally calls Gemini to phrase an answer from retrieved chunks. If you did not call Gemini during your demo, write that.

TF-IDF is a classical weighting of words. Spärck Jones discussed inverse document frequency in the Journal of Documentation (1972). The vector-space view of documents is associated with Salton, Wong, and Yang (Communications of the ACM, 1975). Logistic regression and linear support-vector machines are standard linear classifiers. Cortes and Vapnik, "Support-Vector Networks" (Machine Learning, 1995), is the usual SVM citation. The implementations are scikit-learn, described by Pedregosa and colleagues (JMLR, 2011).

JSON Web Tokens are specified in RFC 7519. Password hashing guidance is on the OWASP Password Storage Cheat Sheet. This project uses bcrypt.

For the tools, cite the documentation you used: FastAPI, React, PyMuPDF, FAISS, Sentence Transformers, and the Gemini API docs if you enabled Gemini.

Suggested reference list. Verify before submission:

1. P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," arXiv:2005.11401. https://arxiv.org/abs/2005.11401
2. N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," arXiv:1908.10084. https://arxiv.org/abs/1908.10084
3. W. Wang et al., "MiniLM: Deep Self-Attention Distillation for Task-Agnostic Compression of Pre-Trained Transformers," arXiv:2002.10957. https://arxiv.org/abs/2002.10957
4. J. Johnson, M. Douze, and H. Jégou, "Billion-scale similarity search with GPUs," arXiv:1702.08734. https://arxiv.org/abs/1702.08734
5. A. Vaswani et al., "Attention Is All You Need," arXiv:1706.03762. https://arxiv.org/abs/1706.03762
6. F. Pedregosa et al., "Scikit-learn: Machine Learning in Python," Journal of Machine Learning Research, vol. 12, pp. 2825–2830, 2011. https://jmlr.org/papers/v12/pedregosa11a.html
7. C. Cortes and V. Vapnik, "Support-Vector Networks," Machine Learning, vol. 20, pp. 273–297, 1995. https://doi.org/10.1007/BF00994018
8. K. Spärck Jones, "A statistical interpretation of term specificity and its application in retrieval," Journal of Documentation, vol. 28, no. 1, pp. 11–21, 1972. https://doi.org/10.1108/eb026526
9. G. Salton, A. Wong, and C. S. Yang, "A vector space model for automatic indexing," Communications of the ACM, vol. 18, no. 11, pp. 613–620, 1975. https://doi.org/10.1145/361219.361220
10. M. Jones, J. Bradley, and N. Sakimura, "JSON Web Token (JWT)," RFC 7519, 2015. https://www.rfc-editor.org/rfc/rfc7519
11. OWASP, "Password Storage Cheat Sheet." https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
12. Sentence Transformers model card, `all-MiniLM-L6-v2`. https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
13. FAISS. https://github.com/facebookresearch/faiss
14. PyMuPDF documentation. https://pymupdf.readthedocs.io/
15. FastAPI documentation. https://fastapi.tiangolo.com/
16. React documentation. https://react.dev/
17. Gemini API documentation, only if you used it. https://ai.google.dev/gemini-api/docs

## Chapter 3. Problem definition and objectives

Problem: provide campus answers and a small set of workflows so that rules come from uploaded documents, changes to records are confirmed, and complaint categories come from an evaluated model rather than from an unstated prompt.

Objectives:

1. Register and log in three roles, with checks on the server.
2. Ingest text PDFs, including files added later, and cite page numbers.
3. Refuse when retrieval is below the cutoff.
4. Run complaint submission and event registration through explicit tools and a confirmation step.
5. Train and compare two classifiers, save one, and show the evaluation file.
6. Summarise notices without presenting extracted dates as verified facts.
7. Show analytics counted from the database.

Non-objectives: OCR, fine-tuning, a priority classifier, payments, and production hardening.

## Chapter 4. System analysis and requirements

Functional requirements follow the three roles in the project brief: students ask, register, and complain; faculty update assigned complaints; administrators manage users, documents, notices, events, and charts.

Non-functional requirements that this build actually meets:

- Passwords are hashed. Tokens expire. Roles are reloaded from the database.
- Uploads are limited to 15 MB and 80 pages, must be PDF bytes, and scanned files are not indexed.
- The API documents itself at `/docs`.
- Official PDFs keep their source URL. Demonstration rows are labelled DEMO DATA.

Requirements it does not meet, and should be listed as such: revocation of tokens, rate limiting, OCR, and a measured Gemini quality score.

## Chapter 5. Proposed methodology

Document path: PyMuPDF text extraction, overlapping chunks, MiniLM embeddings, FAISS inner-product search, threshold 0.48, then either a quotation, a Gemini prompt restricted to those chunks, or a refusal.

Agent path: keyword and pattern rules select one of five Python functions. Mutations wait in `pending_actions` until the next user message is a short YES.

Learning path: TF-IDF on the training split, logistic regression versus linear SVM, stratified 80/20 split, macro-averaged precision, recall, and F1, plus a confusion matrix. Priority stays a rule because there are no independent priority labels.

Why not fine-tuning: a new circular must be citable the day it is uploaded. Fine-tuning would hide the text inside weights and would need a new training run.

## Chapter 6. System design and architecture

Include the Mermaid diagram from `02_SYSTEM_ARCHITECTURE.md` and the schema diagram from `03_DATABASE_GUIDE.md`. Explain that the browser never opens SQLite or FAISS. Explain `answer_mode`. Explain that analytics SQL lives in `services/analytics/metrics.py`.

Design decisions worth a subsection:

- Exact FAISS scan instead of an approximate index.
- No LangGraph.
- Logistic regression deployed when macro F1 is tied or within 0.02, because it exposes class probabilities.
- Same 404 text for a hidden complaint and a missing complaint.

## Chapter 7. Implementation

Follow `04_BACKEND_CODE_EXPLANATION.md` and `05_FRONTEND_CODE_EXPLANATION.md`. Mention the stack actually installed: FastAPI, SQLAlchemy, PyJWT, bcrypt, PyMuPDF, sentence-transformers, faiss-cpu, scikit-learn, React, Vite, Tailwind, React Router, Axios, Recharts. Gemini uses the `google-genai` package when a key is present.

Screenshots to take yourselves, after seed:

- Ordinance 9 answer with the fellowship excerpt and the source card.
- Canteen refusal with no sources.
- Complaint confirmation showing Infrastructure and the rule-based priority.
- Admin analytics.
- Model evaluation page showing 0.625 and 0.624.

Do not draw numbers onto a screenshot.

## Chapter 8. Results and evaluation

Classification, from `models/metrics.json` on the synthetic 160-row set, stratified split, `random_state=42`, 128 train and 32 test:

| Model | Accuracy | Macro precision | Macro recall | Macro F1 |
| --- | --- | --- | --- | --- |
| Logistic regression (deployed) | 0.625 | 0.683 | 0.625 | 0.624 |
| Linear SVM | 0.625 | 0.683 | 0.625 | 0.624 |

20 of 32 test rows were correct. Per-class F1 on this split: Transportation 1.00, IT Support 0.89, Hostel 0.75, Library 0.75, Academic 0.75, Cleanliness 0.40, Infrastructure 0.25, Other 0.20. The confusion matrices are identical and are printed in the metrics file. Infrastructure was confused with Hostel and Other. Cleanliness was often predicted as Infrastructure.

State the limits in the same section: four test rows per class, synthetic sentences, balanced classes so `class_weight` is not the reason for the score.

Retrieval, with `all-MiniLM-L6-v2` and threshold 0.48, after the public DAVV ordinances were indexed:

- Fellowships: Ordinance No. 9, page 1, score 0.54. The excerpt includes the newspaper-advertisement sentence.
- Choice Based Credit System: Ordinance No. 14, page 1, score 0.5287. The excerpt includes the ordinance heading.
- Ordinance 6 attendance wording: the highest chunk, page 2 at 0.6786, does not contain the percentage. The page 1 sentence "seventy five percent" scored 0.4589 and was not cited.
- Canteen menu: nearest score 0.2702, `insufficient_context`, no sources. Wi-Fi password: nearest score 0.1245.

Pytest on this copy: 21 passed in 20.94s. That suite uses a hash embedder and does not call Gemini. Gemini generation was not measured. Retrieval numbers for the DAVV ordinances are in `docs/DATA_SOURCES_AND_PROVENANCE.md`. Do not reuse scores from the deleted fictional PDFs.

## Chapter 9. Conclusion and future scope

The system demonstrates grounded document answers, a refusal path, confirmed tools, a saved classifier with a published confusion matrix, and charts from SQLite. Official text is limited to the downloaded PDFs that have a text layer. Demonstration records are labelled. OCR, token revocation, a real complaint corpus, and a live Gemini evaluation are future work. Use `15_LIMITATIONS_AND_FUTURE_SCOPE.md` rather than a generic "deep learning will improve everything" ending.

## Chapter 10. References

Use the verified list from Chapter 2. Add your college's required citation style. If the examiner asks for a result, point to Chapter 8 and the file it came from, not to a paper's leaderboard.
