# Data sources and provenance

Retrieved on **12 November 2026** from pages on `https://www.dauniv.ac.in`. The files in `data/official_documents/davv/` are the bytes downloaded that day. They were not rewritten. A later upload on the university site can change a file; compare the local PDF with the source URL before a viva.

No separate open licence was printed on those pages. The files are public university documents used here as a local copy for an academic demonstration. Do not present them as your own writing. Do not claim a licence that the university did not state.

The chatbot does not contain a hardcoded DAVV answer. It searches whatever PDFs an administrator has indexed.

## Official public PDFs

| Data | Source | Source URL | Page where the link was found | Status | Publication date | Preprocessing | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Ordinance No. 14, Choice Based Credit System | DAVV common ordinances list | https://www.dauniv.ac.in/frontassets/ordinance/Ordinance-14.pdf | https://www.dauniv.ac.in/common-ordinance | Original public PDF. Text extracted. | 04/12/2017, the Executive Council date printed in the PDF | PyMuPDF text, chunks of about 900 characters, MiniLM embeddings, FAISS | The PDF also says the Coordination Committee met on 25/10/2017. This project did not check whether a later ordinance replaced it. |
| Ordinance No. 6, Examinations (General) | Same list | https://www.dauniv.ac.in/frontassets/ordinance/Ordinance-6.pdf | https://www.dauniv.ac.in/common-ordinance | Original public PDF. Text extracted. | 04/12/2017, printed in the PDF | Same pipeline | 19 pages. The nearest chunk to an attendance question is not always the sentence that states the percentage. See the retrieval note below. |
| Ordinance No. 7, Admission, Transfer and Discipline | Same list | https://www.dauniv.ac.in/frontassets/ordinance/Ordinance-7.pdf | https://www.dauniv.ac.in/common-ordinance | Original public PDF. Text extracted. | 04/12/2017, printed in the PDF | Same pipeline | The stored title is shortened. The website link text is the long admission title. |
| Ordinance No. 9, Award of Fellowship and Scholarship | Same list | https://www.dauniv.ac.in/frontassets/ordinance/Ordinance-9.pdf | https://www.dauniv.ac.in/common-ordinance | Original public PDF. Text extracted. | 04/12/2017, printed in the PDF | Same pipeline | Use this file for the fellowship demo question. The top passage on 12 November 2026 started with the ordinance heading. |
| Academic Calendar for Ph.D. Course Work 2025-26 | Ph.D. notifications page | https://www.dauniv.ac.in/frontassets/notices/Approval%20of%20Academic%20Calendar%20for%20Ph.D.%20Course%20Work%202025-26.pdf | https://www.dauniv.ac.in/phd-notification | Original public PDF. **No text layer.** | Not read from the file | Stored only. Status `needs_ocr`. Not embedded. | PyMuPDF extracted 0 characters from 2 pages. Do not quote dates from this calendar. OCR is not implemented. |
| Revised Notification Regarding Ph.D. Fees | Same page | https://www.dauniv.ac.in/frontassets/notices/RevisedPh.D.FeesNotice.pdf | https://www.dauniv.ac.in/phd-notification | Original public PDF. **No text layer.** | Not read from the file | Stored only. `needs_ocr`. | 0 characters extracted. Do not state a Ph.D. fee from memory. |
| University-Level Anti-Ragging Committee, session 2026-2027 | Homepage announcement | https://www.dauniv.ac.in/adminassets/pdf/08-25-2026_0310pm85285.pdf | https://www.dauniv.ac.in/ | Original public PDF. **No text layer.** | Not read from the file. The URL path contains 08-25-2026, which is only the site's file name. | Stored only. `needs_ocr`. | 0 characters extracted. |
| Academic Programmes Offered | Admissions menu | https://www.dauniv.ac.in/frontassets/notices/academic-programmes-offered-2026.pdf | https://www.dauniv.ac.in/ | Original public PDF. **No text layer.** | Not read from the file | Stored only. `needs_ocr`. | One-page image PDF, about 5 MB. 0 characters extracted. |

Purpose of all eight: the document library and, for the four text ordinances, retrieval practice. An administrator can delete them and upload another institution's PDFs without changing code. New uploads are marked `provenance=uploaded` unless the seed manifest marks `official_public`.

## Retrieval check after this download

Measured with `all-MiniLM-L6-v2` and threshold 0.48 on 12 November 2026, after `scripts/seed.py`:

- "How does Ordinance 9 say fellowships are awarded?" returned `retrieval_only`. Top source: Ordinance No. 9, page 1, score 0.54. The passage includes "Every year the University shall invite applications through an advertisement in the newspaper".
- "Explain the Choice Based Credit System in Ordinance 14." returned `retrieval_only`. Top source: Ordinance No. 14, page 1, score 0.5287. The passage includes the heading "ORDINANCE NO. 14 CHOICE BASED CREDIT SYSTEM".
- "What attendance does Ordinance 6 require for a regular course of study?" returned `retrieval_only`. Top source: Ordinance No. 6, page 2, score 0.6786. That chunk does **not** contain the percentage. The sentence "seventy five percent" is on page 1 of the same PDF and scored 0.4589, below the cutoff, so it was not cited. Ordinance 14, page 3, scored 0.5009 and does contain "atleast seventy-five percent". Read the card before repeating a number.
- "What is the canteen menu on Wednesday?" returned `insufficient_context` with no sources. Its nearest neighbour scored 0.2702.
- "What is the Wi-Fi password?" nearest neighbour scored 0.1245.

Earlier scores such as 0.6033 and a fee of 95000 came from fictional PDFs that have been deleted. Do not quote those figures.

## DEMO DATA, not DAVV records

| Data | Source | Status | Purpose | Limitation |
| --- | --- | --- | --- | --- |
| Four login accounts in `backend/scripts/seed.py` | Written for this project. Emails use example.com. | Synthetic. `is_demo` is true. | Show student, faculty, and admin roles. | Not DAVV people. Passwords are for the local demo. |
| Five complaint rows, plus any complaint already in the local database when seed was re-run | Written for the demonstration, or created while trying the app. | Synthetic. Descriptions end with "DEMO DATA". | Show status changes and the classifier. | Not a DAVV complaint register. Re-running seed currently labels every complaint already in the file as demo. |
| 160 training sentences in `backend/scripts/complaint_corpus.py` | Written by hand for this project. Exported to `data/sample_complaints/complaints.csv`. Column `source` is `synthetic_project_authored`. | Synthetic. No public dataset and no licence, because it is project-authored. | Train TF-IDF plus logistic regression and linear SVM. | Balanced and easier than real tickets. Accuracy 0.625 and macro F1 0.624 are the hold-out scores on this file only. |
| Four events in `data/sample_events/events.json` | Written for this project. | Synthetic. Titles start with "DEMO:". | Registration, capacity, and duplicate checks. | Venues are labelled "not a DAVV location". |
| Notice "DEMO: notice list placeholder" | Written for this project. | Synthetic. | Show an empty-of-policy notice and a summary. | It states no fee, date, or rule. |
| Notice excerpt from Ordinance 6 | Copied from the public PDF, line breaks removed. | `official_public_copy`. Source URL stored. | Show a notice that is an excerpt, not a new circular. | It is not the full ordinance. The summary is extractive when Gemini is not configured. Dates detected by the summariser are not verified. |

## Removed

The fictional Northbridge Institute PDFs, notices, and events were deleted from `data/sample_documents/` and from the local database by `scripts/seed.py`. `scripts/generate_sample_pdfs.py` now refuses to invent new ones.

## Three further public sites, retrieved 12 November 2026

No text was typed in from these sites. Only the original PDF bytes were saved. Titles below are the link text on the page, or the heading printed in the PDF.

`https://dsf.dauniv.ac.in/` is the School of Data Science and Forecasting (SDSF). The page title is "SDSF | School of Data Science and Forecasting". It is not a Dean of Student Welfare site.

`https://cpc.dauniv.ac.in/` is the Centralized Placement Cell. The visible page is a JavaScript application. Two PDFs are linked from that application.

`https://www.ietdavv.edu.in/` is the Institute of Engineering & Technology. Its notices board is `https://notices.ietdavv.edu.in/`. That board said 82 general notices. This retrieval kept the academic calendar and the three current first-year timetable notices on the first page. Candidate lists, result sheets, and photographs were not copied.

| Data | Source page | File | Text layer |
| --- | --- | --- | --- |
| CPC Guidelines | https://cpc.dauniv.ac.in/ | `cpc/cpc-guidelines.pdf` | None. 2 pages, 0 characters. Stored as `needs_ocr`. |
| Centralized Placement Cell Recruitment Brochure 2025-26 | https://cpc.dauniv.ac.in/ | `cpc/cpc-report.pdf` | Yes. The cover line says "RECRUITMENT BROCHURE 2025-26". |
| Admission Guideline B.Tech | https://www.ietdavv.edu.in/index.php/admission/admission-2026-27 | `iet/admission-guideline-btech-2026-27.pdf` | Yes. 5 pages. |
| Regarding CLC Process at IET-DAVV for BTech Program | https://www.ietdavv.edu.in/ | `iet/clc-notice.pdf` | Yes. The PDF is the CLC notice for session 2026-27. |
| Counselling and Mentorship | https://www.ietdavv.edu.in/ | `iet/counselling-mentorship.pdf` | Thin. 686 characters across 6 pages. |
| IET Hostel Details 2025-26 | https://www.ietdavv.edu.in/ | `iet/hostel-info.pdf` | Yes. Hostel names, capacity, and warden emails. It is not a full hostel rule book. |
| IET Placement | https://www.ietdavv.edu.in/ | `iet/placement.pdf` | Yes, but the extracted text is broken up by the brochure layout. |
| Freshers' Induction Program 2026 | https://www.ietdavv.edu.in/index.php/admission/admission-2026-27 | `iet/induction-2026.pdf` | Yes. |
| 05.10.2026 Revised Academic Calendar | https://notices.ietdavv.edu.in/ | `iet/notices/revised-academic-calendar.pdf` | Yes. Board date 16 Oct 2026. |
| Test 3 timing change, B.Tech I year / B.Des. I year | https://notices.ietdavv.edu.in/ | `iet/notices/test3-timing-change.pdf` | Yes. Board date 30 Oct 2026. |
| Revised B.Tech I year / B.Des. I year test 3 timetable | https://notices.ietdavv.edu.in/ | `iet/notices/test3-timetable.pdf` | Yes. Board date 30 Oct 2026. |
| B.Tech I Year Practical Time table, all branches | https://notices.ietdavv.edu.in/ | `iet/notices/btech-i-practical-timetable.pdf` | Yes. Board date 28 Oct 2026. |
| Academic Calendar, linked from SDSF Academics | https://dsf.dauniv.ac.in/academics.php | `dsf/09-21-2025_0119pm66453.pdf` | Scan. Extracted text is only "CamScanner". `needs_ocr`. |
| SDSF class timetables for 2026-27: M.Tech (Dual Degree) AI and Data Science, M.Sc. Data Science and Analytics, Executive M.Tech (Data Science), M.Tech (Data Science / BDA), MBA (Business Analytics) | https://dsf.dauniv.ac.in/academics.php | `dsf/aids.pdf`, `dsf/msc.pdf`, `dsf/executive.pdf`, `dsf/mtech-ds-bda-timetable.pdf`, `dsf/mba.pdf` | Yes. The programme names are the labels on the academics page. |
| End-semester timetables, December 2026 and Nov–Dec 2026 | https://dsf.dauniv.ac.in/academics.php | the two `dsf/revised-time-table-...pdf` files | None. 0 characters. `needs_ocr`. |

The IET scholarships page lists scheme names in HTML and does not link a PDF. Those names were not copied into the database. The SDSF admission page is also HTML. It was not rewritten into a notice.

## What still has to be obtained manually

These public files were downloaded, but they cannot be searched until someone OCRs them or the institution publishes a text PDF:

- Ph.D. coursework academic calendar 2025-26
- Revised Ph.D. fees notice
- Anti-ragging committee notice for 2026-27
- Academic Programmes Offered
- CPC Guidelines
- SDSF Academic Calendar linked from the academics page
- SDSF end-semester timetables for December 2026 and Nov–Dec 2026

A fee table for a university-wide programme was not found as a text PDF. Do not type fees in from memory. If you download a text PDF later, upload it in Document management and paste the source URL. The IET notices board has further pages that were not downloaded.
