# 5. Frontend code explanation

The React app lives in `frontend/`. Vite serves it at http://localhost:5173. Axios calls `VITE_API_URL`, which is `http://localhost:8000` in `frontend/.env`.

## How the files are split

| Path | Role |
| --- | --- |
| `src/main.jsx` | Renders `App` |
| `src/App.jsx` | All routes |
| `src/context/AuthContext.jsx` | Token, current user, login, logout |
| `src/services/api.js` | Axios instance. Adds the bearer token. |
| `src/components/AppShell.jsx` | Sidebar. The links depend on `user.role`. |
| `src/components/ProtectedRoute.jsx` | Sends anonymous users to `/login` and the wrong role to `/app` |
| `src/pages` | One screen each |
| `src/pages/admin` | Screens only an administrator should open |

The sidebar hiding a link is a convenience. `ProtectedRoute` is also only a convenience. The API returns 403 if a student calls `/api/users` directly.

## Login state

`localStorage` key `cc_token` holds the JWT. On refresh, `AuthProvider` calls `GET /api/auth/me`. If that fails, the token is removed. Logout deletes the token in the browser. The server does not keep a session to destroy. That is a limitation: a stolen token works until it expires (8 hours by default).

## Talking to the API

```javascript
const response = await api.get("/api/complaints");
```

The interceptor in `api.js` adds `Authorization`. `errorMessage` reads `detail` whether it is a string or a validation list. Forms show that string. They do not show a generic "error" when the server explained the problem.

Document upload uses `FormData` because the body is a file plus fields, not JSON.

## Charts

`pages/admin/Analytics.jsx` and the admin dashboard call `GET /api/analytics/overview`. Recharts plots `complaints_by_status`, `complaints_by_category`, and the daily counts from that JSON. There is no array of fake numbers in the component. If the database is empty, the lists are empty and the page says so.

`pages/admin/ModelEval.jsx` reads `GET /api/ml/metrics`, which is the file `models/metrics.json`. If training has not been run, the API returns 404 and the page shows that message.

## Forms

Labels use `htmlFor` and the input `id`. Required fields use the HTML `required` attribute, and the API validates again. The complaint form can leave category blank. The server then stores only the model's prediction.

The assistant has two modes. "Ask documents" uses `/api/chat`. "Campus actions" uses `/api/agent`. If the latest assistant message has `needs_confirmation`, the page shows Confirm and Cancel. Those buttons send `YES` or `NO`. They do not call a hidden create endpoint by themselves.

## Role screens

- Student: dashboard, assistant, notices, events, registrations, complaints, profile.
- Faculty: dashboard, assistant, assigned complaints, notices, events, profile. The complaint list is the same React page. The API returns only rows assigned to that faculty account.
- Administrator: the student tools that are still useful, plus documents, users, event management, notice management, analytics, and model evaluation.
