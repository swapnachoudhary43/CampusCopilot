import { useEffect, useState } from "react";
import api, { errorMessage } from "../services/api";
import { Empty, PageHeader } from "../components/Feedback";
import { formatWhen } from "../utils/format";

export default function Registrations() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/events/me/registrations").then((response) => setRows(response.data)).catch((err) => setError(errorMessage(err)));
  }, []);

  return (
    <div>
      <PageHeader title="My registrations" subtitle="Only registrations that are still active are listed." />
      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      {!rows ? <p className="text-sm text-slate-500">Loading registrations…</p> : null}
      {rows && rows.length === 0 ? <Empty>You have not registered for an event.</Empty> : null}
      <div className="grid gap-3">
        {rows?.map((event) => (
          <article key={event.id} className="card p-4">
            <h2 className="font-semibold">{event.title}</h2>
            <p className="text-sm text-slate-600">{event.venue} · {formatWhen(event.starts_at)}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
