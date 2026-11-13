"""Print raw FAISS scores, including matches below the cutoff.

Run from the backend folder after seeding:
    $env:PYTHONPATH = "."
    ..\\.venv\\Scripts\\python.exe scripts\\probe_scores.py
"""

from app.database.session import get_session_factory, init_db
from app.models.entities import DocumentChunk
from app.services.rag.embeddings import get_embedder
from app.services.rag.vector_store import search_index

init_db()
db = get_session_factory()()
embedder = get_embedder()
questions = [
    "What is the minimum attendance percentage required for examinations?",
    "What is the library overdue fine per day?",
    "What is the tuition fee for the integrated M.Tech programme?",
    "What are the hostel quiet hours?",
    "When do the odd-semester examinations begin?",
    "What is the passing mark for a course?",
    "What is the merit scholarship waiver?",
    "What is the canteen menu on Wednesday?",
    "What is the Wi-Fi password for the academic block?",
]
for question in questions:
    vector = embedder.embed([question])[0]
    hits = search_index(vector, 5)
    print("Q:", question)
    for chunk_id, score in hits:
        chunk = db.get(DocumentChunk, chunk_id)
        title = chunk.document.title if chunk and chunk.document else "?"
        page = chunk.page_number if chunk else "?"
        print(f"  {score:.4f} {title} p{page}")
