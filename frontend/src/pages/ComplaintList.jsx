import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { DemoBadge, PriorityBadge, StatusBadge } from "../components/Badges";
import { Empty, PageHeader } from "../components/Feedback";
import { formatWhen } from "../utils/format";

export default function ComplaintList() {
  const { user } = useAuth();
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const params = status ? { status } : {};
    api.get("/api/complaints", { params })
      .then((response) => setRows(response.data))
      .catch((err) => setError(errorMessage(err)));
  }, [status]);

  const title = user.role === "faculty" ? "Assigned complaints" : user.role === "admin" ? "All complaints" : "My complaints";

  return (
    <div>
      <PageHeader
        title={title}
        subtitle="Predicted category comes from the saved classifier. Priority is a separate keyword rule."
        action={user.role !== "faculty" ? <Link className="btn" to="/app/complaints/new">New complaint</Link> : null}
      />
      {error ? <p className="mb-3 text-sm text-rose-700">{error}</p> : null}
      <label className="label" htmlFor="status-filter">Status</label>
      <select id="status-filter" className="field mb-4 max-w-xs" value={status} onChange={(event) => setStatus(event.target.value)}>
        <option value="">All statuses</option>
        {["submitted", "assigned", "in_progress", "resolved", "closed"].map((item) => (
          <option key={item} value={item}>{item.replace("_", " ")}</option>
        ))}
      </select>
      {!rows ? <p className="text-sm text-slate-500">Loading complaints…</p> : null}
      {rows && rows.length === 0 ? <Empty>{status ? "No complaints match this view." : "No complaints submitted yet."}</Empty> : null}
      <div className="space-y-3">
        {rows?.map((row) => (
          <Link key={row.id} to={`/app/complaints/${row.id}`} className="card block p-4 hover:border-indigo-300">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">#{row.id} {row.title}</h2>
              <span className="flex gap-2">{row.is_demo ? <DemoBadge /> : null}<StatusBadge value={row.status} /></span>
            </div>
            <p className="mt-2 text-sm text-slate-600">{row.description}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-indigo-50 px-2 py-1 text-indigo-800">Predicted: {row.predicted_category || "unavailable"}</span>
              <PriorityBadge value={row.suggested_priority} />
              <span className="text-slate-500">{formatWhen(row.created_at)}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
