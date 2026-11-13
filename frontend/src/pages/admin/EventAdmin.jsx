import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { PageHeader } from "../../components/Feedback";

const EMPTY = { title: "", description: "", venue: "", starts_at: "", ends_at: "", capacity: 30 };

export default function EventAdmin() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");

  function load() {
    api.get("/api/events").then((response) => setRows(response.data)).catch((err) => setError(errorMessage(err)));
  }
  useEffect(load, []);

  function payload() {
    return {
      ...form,
      capacity: Number(form.capacity),
      starts_at: new Date(form.starts_at).toISOString(),
      ends_at: new Date(form.ends_at).toISOString(),
    };
  }

  async function create(event) {
    event.preventDefault();
    setError("");
    try {
      await api.post("/api/events", payload());
      setForm(EMPTY);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function remove(id) {
    if (!window.confirm("Delete this event and its registrations?")) return;
    await api.delete(`/api/events/${id}`);
    load();
  }

  return (
    <div>
      <PageHeader title="Event management" subtitle="Students register from the Events page or through the assistant after confirmation." />
      {error ? <p className="mb-3 text-sm text-rose-700">{error}</p> : null}
      <form className="card mb-6 grid gap-3 p-5 md:grid-cols-2" onSubmit={create}>
        <input className="field" aria-label="Title" placeholder="Title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
        <input className="field" aria-label="Venue" placeholder="Venue" value={form.venue} onChange={(event) => setForm({ ...form, venue: event.target.value })} required />
        <textarea className="field md:col-span-2" aria-label="Description" placeholder="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} required />
        <input className="field" aria-label="Starts" type="datetime-local" value={form.starts_at} onChange={(event) => setForm({ ...form, starts_at: event.target.value })} required />
        <input className="field" aria-label="Ends" type="datetime-local" value={form.ends_at} onChange={(event) => setForm({ ...form, ends_at: event.target.value })} required />
        <input className="field" aria-label="Capacity" type="number" min="1" value={form.capacity} onChange={(event) => setForm({ ...form, capacity: event.target.value })} required />
        <button className="btn">Create event</button>
      </form>
      <div className="space-y-3">
        {rows.map((row) => (
          <article key={row.id} className="card flex items-center justify-between gap-3 p-4">
            <div>
              <h2 className="font-semibold">{row.title}</h2>
              <p className="text-sm text-slate-600">{row.registered_count}/{row.capacity} · {row.venue}</p>
            </div>
            <button className="btn-ghost" onClick={() => remove(row.id)}>Delete</button>
          </article>
        ))}
      </div>
    </div>
  );
}
