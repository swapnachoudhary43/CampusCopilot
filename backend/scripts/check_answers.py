"""Check grounded answer modes after the similarity cutoff. Diagnostic only."""

from app.core.config import get_settings
from app.database.session import get_session_factory, init_db
from app.services.rag.pipeline import answer_question

init_db()
print("threshold", get_settings().similarity_threshold)
db = get_session_factory()()
questions = [
    "How does Ordinance 9 say fellowships are awarded?",
    "Explain the Choice Based Credit System in Ordinance 14.",
    "What is the canteen menu on Wednesday?",
]
for question in questions:
    result = answer_question(db, question)
    titles = [f"{source['document_title']} p{source['page_number']} ({source['score']})" for source in result["sources"]]
    print(question)
    print(result["answer_mode"], "|", " ; ".join(titles) or "no sources")
    if result["sources"]:
        print(result["sources"][0]["excerpt"][:180].replace("\n", " "))
    print("---")
db.close()
