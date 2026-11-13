# 4. Backend code explanation

Run the API from the `backend` folder so `app` imports cleanly:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Swagger is at http://localhost:8000/docs.

## Folder map

| Path | What it does |
| --- | --- |
| `app/main.py` | Creates the FastAPI app, CORS, routers, and `/api/health` |
| `app/core/config.py` | Reads `backend/.env` |
| `app/core/security.py` | bcrypt and JWT |
| `app/core/deps.py` | `get_current_user` and `require_roles` |
| `app/database/session.py` | Engine, sessions, SQLite foreign keys |
| `app/models/entities.py` | All tables |
| `app/schemas/api.py` | Pydantic request and response models |
| `app/routes/*.py` | One file per URL group |
| `app/services/rag/` | Ingestion and answering |
| `app/services/agent/` | Intent, tools, confirmation |
| `app/services/ml/` | Train, predict, priority rules |
| `app/services/complaints.py` | Who may see or edit a complaint |
| `app/services/events.py` | Capacity and duplicate checks |
| `app/services/notices.py` | Summary and date extraction |
| `app/services/analytics/metrics.py` | SQL counts for the dashboard |
| `scripts/train_model.py` | Writes `models/metrics.json` |
| `scripts/seed.py` | Sample users, PDFs, events, notices, complaints |

## A request, end to end

`POST /api/complaints` hits `routes/complaints.py`. That file checks the JSON with `ComplaintCreate`, then calls `create_complaint`. The service hashes nothing (the user is already logged in), calls the classifier if `models/deployed.joblib` exists, calls `suggest_priority`, inserts the complaint and a history row, writes an audit row, and commits. The route turns the row into a dictionary with `complaint_out`. The password hash is not on `UserPublic`, so it cannot appear in the JSON.

## Authentication

`hash_password` uses bcrypt. The cost is `BCRYPT_ROUNDS` (12 in normal use, 4 in tests). Passwords longer than 72 bytes are rejected because bcrypt would silently ignore the extra bytes.

`create_access_token` puts the user id in `sub` and an expiry in `exp`. It signs with `SECRET_KEY` using HS256.

`get_current_user` reads `Authorization: Bearer ...`, decodes the token, and loads that user. If `is_active` is false, the answer is 401. `require_roles("admin")` then checks `user.role` from the database. Hiding a button in React is not the control. The test `test_student_cannot_list_users` expects HTTP 403.

Public registration forces `role="student"` even if a client sends another role. The field is not on `RegisterRequest`.

## How to add an endpoint

1. Add a Pydantic model in `app/schemas/api.py` if the body is new.
2. Put the database work in a service, not in the route, if it is more than a few lines.
3. Add a function on the right router with a path, a response code, and `Depends(get_current_user)` or `require_roles(...)`.
4. Include the router in `create_app` if it is a new file. The existing routers are already included.
5. Add a pytest that covers the allowed role and one forbidden role.

Example shape:

```python
@router.get("/example")
def example(user: User = Depends(require_roles("admin"))):
    return {"ok": True}
```

## Errors

Validation problems return 422 with Pydantic's `detail` list. Wrong login returns 401 and the same sentence whether the email or the password was wrong. Missing permission returns 403. A student asking for another student's complaint gets 404 and the sentence "That complaint is not available on your account." The API does not say "that belongs to someone else."

## Health

`GET /api/health` needs no login. It reports the embedding backend, whether a Gemini key is present (not the key itself), the FAISS chunk count, and whether `deployed.joblib` exists. Use it before a demo.
