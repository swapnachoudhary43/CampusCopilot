# 6. RAG and LLM guide

## What an LLM is

A large language model predicts the next piece of text. It is fluent, and it can state a fee or a date that was never in your PDF. That is a hallucination. CampusCopilot does not treat the model as the source of college rules.

## What an embedding is

An embedding is a list of numbers that stands for a piece of text. `all-MiniLM-L6-v2` produces 384 numbers. Sentences with a similar meaning land closer together than unrelated sentences. The model file is downloaded from Hugging Face the first time you seed or upload. It then runs locally. The question and the PDF chunks use the same model. If you change `EMBEDDING_MODEL`, you must rebuild the index, because old vectors and new query vectors would not live in the same space.

## What chunking is

A full PDF is too long to embed as one blob, and a one-line match would lose the surrounding rule. `chunk_pages` in `backend/app/services/rag/chunking.py` walks each page, cleans whitespace, and cuts windows of about 900 characters with about 150 characters of overlap. Each chunk stores the PDF page number. Overlap means a sentence that sits on a cut is still complete in one of the two chunks.

## What FAISS and cosine similarity are

FAISS is a library for nearest-neighbour search. This project uses `IndexFlatIP`: it compares the query with every stored vector. Vectors are L2-normalised, so the inner product equals cosine similarity. The score is about 1 when the directions match and about 0 when they do not. For a few hundred campus chunks an exact scan is accurate and short enough to explain. An approximate index would be a later optimisation, not a requirement here.

The index file is `backend/storage/faiss.index`. `faiss_meta.json` lists the chunk ids in the same order and the name of the embedding backend. Search returns positions. The API looks up those chunk ids in SQLite and reads the title and page from there, not from the PDF filename the browser sent.

## What happens when a PDF is uploaded

`store_pdf` in `backend/app/services/rag/ingest.py`:

1. Rejects non-PDF bytes, files over the size limit, and PDFs with more than 80 pages.
2. Extracts text with PyMuPDF. This is real text, not OCR.
3. If the extracted text is under 40 characters, the row is saved as `needs_ocr` and nothing is indexed. Say this clearly: scanned pages are not supported.
4. Chunks the pages, embeds them, stores the vectors, and rebuilds FAISS from every processed chunk.

Deleting a document deletes its chunks and rebuilds the index from the rows that remain.

## How an answer is built

`answer_question` in `backend/app/services/rag/pipeline.py`:

1. Embeds the question. A follow-up that starts with "and", "what about", "how about", "then", or "also", or a fragment shorter than 24 characters, is prefixed with the previous user question so the search has context. A full question such as "What is the canteen menu on Wednesday?" is searched on its own. The previous chat is not treated as a source of rules.
2. Searches FAISS.
3. Drops chunks below `SIMILARITY_THRESHOLD` (0.48 in this project).
4. Joins every remaining chunk of the same document page in reading order, keeps the highest score for that page, then returns the top 4 pages. Joining avoids citing only the tail of a page when an earlier sentence on that page also matched.
5. If nothing remains, `answer_mode` is `insufficient_context` and `sources` is empty. The sentence says the documents do not contain enough information. No model is called.
6. If Gemini is not configured, `answer_mode` is `retrieval_only`. The reply quotes the excerpts and says a language model did not write them.
7. If Gemini is configured, the prompt in `generator.py` tells the model to use only the supplied chunks, to mention title and page, and to admit when the context is insufficient. If the HTTP call fails, `answer_mode` is `llm_unavailable`. The sources are still shown. A replacement answer is not invented.

## A worked example from this repository

The indexed text is the four DAVV ordinances downloaded on 12 November 2026. No Gemini key was set, so the mode is `retrieval_only`.

Question: "How does Ordinance 9 say fellowships are awarded?"

Top source: **Ordinance No. 9 — Award of Fellowship and Scholarship**, page 1, similarity **0.54**. The passage begins with the ordinance heading. Read that card. Do not add a fellowship amount that is not in the excerpt.

Question: "What attendance does Ordinance 6 require for a regular course of study?"

Top source: Ordinance No. 6, page 2, similarity **0.6786**. That chunk does not contain the percentage. The sentence "seventy five percent" is on page 1 of the same PDF and scored **0.4589**, which is below 0.48, so it was not cited. Ordinance 14, page 3, scored **0.5009** and does contain "atleast seventy-five percent". The highest score is not automatically the answering sentence. Read the card.

Question: "What is the canteen menu on Wednesday?"

Nearest neighbour score **0.2702**, below 0.48. Mode `insufficient_context`, no sources. The Wi-Fi password question scored **0.1245**.

## How the cutoff was chosen

0.48 was first measured on a fictional PDF set that has since been deleted. Those old scores must not be quoted. On the DAVV index, the canteen and Wi-Fi questions sit far below 0.48, and the Ordinance 9 question sits above it. The Ordinance 6 page that actually states the percentage sits just below it. The cutoff is not a universal constant. Run the probe again if the embedder or the PDFs change.

## Hallucination limits

The cutoff removes weak neighbours. It cannot stop a strong but wrong neighbour if the PDF uses the same words. The library-fine case is the example. Retrieval-only mode refuses to paraphrase, which makes that visible. Gemini mode depends on the prompt and can still slip. Read the cited page before you repeat a number in the viva.
