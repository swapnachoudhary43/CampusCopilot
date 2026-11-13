import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { PageHeader } from "../../components/Feedback";

const EMPTY = { title: "", body: "", audience: "all" };

export default function NoticeAdmin() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");

  function load() {
    api.get("/api/notices").then((response) => setRows(response.data)).catch((err) => setError(errorMessage(err)));
  }
  useEffect(load, []);

  async function create(event) {
    event.preventDefault();
    setError("");
    try {
      await api.post("/api/notices", form);
      setForm(EMPTY);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function remove(id) {
    await api.delete(`/api/notices/${id}`);
    load();
  }

  return (
    <div>
      <PageHeader title="Notice management" subtitle="Saving a notice runs the summary. If Gemini is not configured, the extractive fallback is used and labelled." />
      {error ? <p className="mb-3 text-sm text-rose-700">{error}</p> : null}
      <form className="card mb-6 grid gap-3 p-5" onSubmit={create}>
        <input className="field" aria-label="Title" placeholder="Title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
        <select className="field" aria-label="Audience" value={form.audience} onChange={(event) => setForm({ ...form, audience: event.target.value })}>
          <option value="all">all</option>
          <option value="students">students</option>
          <option value="faculty">faculty</option>
          <option value="hostel">hostel</option>
        </select>
        <textarea className="field min-h-32" aria-label="Notice text" placeholder="Notice text" value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} required />
        <button className="btn w-fit">Publish notice</button>
      </form>
      <div className="space-y-3">
        {rows.map((row) => (
          <article key={row.id} className="card p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold">{row.title}</h2>
                <p className="mt-2 text-sm text-slate-700">{row.summary}</p>
                <p className="mt-1 text-xs text-amber-800">{row.summary_method} · {row.extraction_disclaimer}</p>
              </div>
              <button className="btn-ghost" onClick={() => remove(row.id)}>Delete</button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
