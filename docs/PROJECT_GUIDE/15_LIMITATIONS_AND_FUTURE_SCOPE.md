# Limitations and future scope

These limits are part of the project, not footnotes to hide. The viva is easier if you say them first.

## Sample data

Four DAVV ordinances are real public PDFs. Four other downloaded DAVV PDFs have no text layer and are not searched. Accounts, complaints, events, and the placeholder notice are DEMO DATA. The complaint training file is hand-written and is not a DAVV log. Another institution can upload its own text PDFs without a code change. The assistant has no hardcoded DAVV answer.

The complaint corpus is 160 sentences written for training. It is balanced and cleaner than real tickets. Words like "bus" make Transportation easy. The class Other is vague, and that shows up in the confusion matrix.

## Language model

Gemini is optional. This copy was run with an empty `GEMINI_API_KEY`. Answers were quotations (`retrieval_only`). Notice summaries used `extractive_fallback`. The Gemini call exists in `generator.py` and was checked against the client library's method name. It was not executed against Google's API here. Do not say it was tested.

If a key is added and the call fails, the mode is `llm_unavailable`. Sources stay. The server does not fill in a fake paragraph.

A language model can still misread a chunk even when the chunk is right. Retrieval-only mode avoids that by quoting. Quoting can also include a header and a footer from the sample PDF, so the card is longer than the one sentence you need.

## Retrieval

FAISS always returns nearest neighbours. The 0.48 cutoff throws away weak ones. That cutoff was chosen from MiniLM scores on these sample PDFs. A new embedder or a very different corpus needs `scripts/probe_scores.py` again.

The library-fine question is cited because some PDFs say the fine is not defined. Similarity treats that as "about the fine". The reader has to use the excerpt. The system does not add an amount, but it also does not understand negation.

Chunks from the same page that pass the cutoff are joined in reading order. A page can still be long, and the card is truncated.

Follow-up search prepends the previous question only for phrases starting with "and", "what about", "how about", "then", or "also", or for fragments shorter than 24 characters. A short full question is searched alone. This is a heuristic, not a dialogue model.

There is no OCR. A scan is stored as `needs_ocr` and is not indexed.

## Machine learning

The hold-out set has 32 rows, 4 per class. One mistake moves a class recall by 0.25. Accuracy 0.625 and macro F1 0.624 are the real scores. They are not a claim about a university helpdesk.

Priority is a keyword list. It is stored with `priority_method=rule_based` and a disclaimer. A priority classifier was not trained, because the only labels we could have made would have been copied from those keywords.

Confidence on one sentence can be low even when the label matches the obvious category. The projector complaint in the demo was Infrastructure at about 0.19. That number is not the test accuracy.

## Security

Passwords are hashed. Roles are checked on the server. The token is still in `localStorage`, logout does not revoke it, and there is no rate limit. Seed passwords are printed in the README for the local demo. SQLite and a single FastAPI process are not a campus deployment.

Complaint privacy uses the same 404 for missing and forbidden ids. Analytics do not paste complaint descriptions into the charts. Audit details can still contain a short title. Do not put a student's private story on a projected chart.

## Analytics

Frequent questions are exact strings after lower-casing and trimming. They are not clustered. The date filter does not apply to the user total. Both behaviours are written in the API `definitions` object.

## Scalability

`IndexFlatIP` scans every vector. That is the right explanation at a few dozen chunks. It is not the index you would use for every PDF of a large university. One SQLite writer will lock under concurrent uploads.

## Future work that is not in this build

- OCR, with a warning when the text is uncertain.
- HttpOnly cookies, shorter tokens, and login rate limits.
- A larger complaint set with staff-assigned categories and priorities, then a new split and a new `metrics.json`.
- Show "uncertain" when class probability is very low.
- Hybrid keyword and vector search, and a reranker.
- Group similar questions before listing them as frequent.
- A migration tool if the tables change. Today, schema changes mean a new SQLite file and a fresh seed.

Do not promise multi-campus tenancy, payments, proctoring, or a guarantee that a language model never errs.
