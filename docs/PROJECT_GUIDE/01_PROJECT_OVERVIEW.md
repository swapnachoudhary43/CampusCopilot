# 1. Project overview

## What CampusCopilot is

CampusCopilot is a small campus web application with three intelligent parts:

1. A document assistant that answers from PDFs the administrator uploaded.
2. A workflow assistant that can submit a complaint or register for an event, but only after the user types YES.
3. A complaint classifier trained with scikit-learn, plus a separate keyword rule for priority.

The initial document library is a set of public PDFs downloaded from the Devi Ahilya Vishwavidyalaya website on 12 November 2026. Each stored file keeps its source URL. Accounts, complaints, and events marked DEMO DATA were written for the demonstration. They are not DAVV records. The assistant does not contain hardcoded DAVV answers. If a question is not supported by an uploaded PDF, it says so.

## Why the project is needed

Students usually look for rules in long PDFs: attendance, fees, the hostel circular, the exam calendar. A normal search box finds keywords. It does not assemble an answer, and it does not say "this document does not contain that." Staff also receive complaints as free text. Someone still has to guess the department. Events are a separate spreadsheet. The project puts these jobs in one application and shows where a model is used and where a plain rule is used.

## Problem statement

Design and build a campus assistance platform that:

- answers institutional questions from uploaded documents and cites the page,
- refuses to invent a rule when the documents do not support an answer,
- performs a few campus actions through checked backend functions,
- classifies complaint text and evaluates that classifier on held-out data,
- gives administrators counts that come from the database.

## Objectives

1. Register users and enforce student, faculty, and administrator permissions on the server.
2. Ingest text PDFs into overlapping chunks, embeddings, and a FAISS index.
3. Answer questions with retrieval-augmented generation, or with labelled quotations if Gemini is not configured.
4. Run complaint and event workflows only after confirmation.
5. Train and compare TF-IDF classifiers, save the chosen model, and show its real test metrics.
6. Summarise notices and mark extracted dates as unverified.
7. Draw admin charts from stored rows.

## Scope

Included: authentication, documents, chat, a five-tool agent, complaints, events, notices, analytics, and the saved classifier.

Not included: OCR for scanned PDFs, a priority classifier, payment processing, a mobile app, or a multi-server deployment. Gemini is optional. This copy was run without an API key, so answers were quotations from the retrieved pages.

## Target users

- Students ask questions, read notices, register for events, and file complaints.
- Faculty see complaints assigned to them and can move those complaints forward.
- Administrators upload documents, manage users, events, and notices, and read the analytics and model page.

## What makes it more than a chatbot

A chatbot wrapper sends every sentence to a language model and hopes the model knows the college. CampusCopilot:

- searches only the uploaded chunks,
- shows the document title, page, and similarity score,
- says when the score is too low to use as evidence,
- never lets the model run SQL or Python,
- stores the complaint classifier on disk and reports the test-set scores from `models/metrics.json`.

## Main features to point at in a demo

| Feature | Where to show it |
| --- | --- |
| Cited answer | Assistant, "Ask documents" |
| Refusal | Ask "What is the canteen menu on Wednesday?" |
| Confirmed complaint | Assistant, "Campus actions" |
| Classifier | Complaint detail, and Admin → Model evaluation |
| Rule-based priority | The amber note on a complaint. It says it is not an ML model. |
| Live charts | Admin → Analytics |
