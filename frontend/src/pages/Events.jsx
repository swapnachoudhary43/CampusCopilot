import { useEffect, useState } from "react";
import api, { errorMessage } from "../services/api";
import { DemoBadge } from "../components/Badges";
import { Empty, PageHeader } from "../components/Feedback";
import { formatWhen } from "../utils/format";

export default function Events() {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function load() {
    api.get("/api/events").then((response) => setEvents(response.data)).catch((err) => setError(errorMessage(err)));
  }

  useEffect(load, []);

  async function register(id) {
    setError("");
    setMessage("");
    try {
      await api.post(`/api/events/${id}/register`);
      setMessage("Registration saved.");
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function cancel(id) {
    setError("");
    try {
      await api.post(`/api/events/${id}/cancel`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const now = Date.now();
  const upcoming = (events || []).filter((event) => new Date(event.starts_at).getTime() > now);
  const past = (events || []).filter((event) => new Date(event.starts_at).getTime() <= now);

  return (
    <div>
      <PageHeader title="Events" subtitle="Registration is blocked when the event has started, when you already have a seat, or when the capacity is full." />
      {error ? <p className="mb-3 text-sm text-rose-700">{error}</p> : null}
      {message ? <p className="mb-3 text-sm text-emerald-700">{message}</p> : null}
      {!events ? <p className="text-sm text-slate-500">Loading events…</p> : null}
      {events && upcoming.length === 0 ? <Empty>No upcoming events.</Empty> : null}
      <div className="grid gap-4 md:grid-cols-2">
        {upcoming.map((event) => (
          <article key={event.id} className="card p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold">{event.title}</h2>
              {event.is_demo ? <DemoBadge /> : null}
            </div>
            <p className="mt-2 text-sm text-slate-600">{event.description}</p>
            <p className="mt-3 text-sm">{event.venue}</p>
            <p className="text-sm text-slate-500">{formatWhen(event.starts_at)} to {formatWhen(event.ends_at)}</p>
            <p className="mt-2 text-sm font-medium">{event.registered_count} / {event.capacity} registered</p>
            <div className="mt-4 flex gap-2">
              {event.viewer_registered ? (
                <button className="btn-ghost" onClick={() => cancel(event.id)}>Cancel registration</button>
              ) : (
                <button className="btn" disabled={event.registered_count >= event.capacity} onClick={() => register(event.id)}>
                  {event.registered_count >= event.capacity ? "Full" : "Register"}
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
      {past.length ? <h2 className="mb-3 mt-8 font-semibold">Past events</h2> : null}
      <div className="grid gap-3">
        {past.map((event) => (
          <article key={event.id} className="card p-4 text-sm text-slate-600">
            <p className="font-semibold text-slate-900">{event.title}</p>
            <p>{formatWhen(event.starts_at)} · {event.venue}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
