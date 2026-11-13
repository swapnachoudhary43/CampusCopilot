import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api, { errorMessage } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { PriorityBadge, StatusBadge } from "../components/Badges";
import { PageHeader } from "../components/Feedback";
import { formatWhen, titleCase } from "../utils/format";

export default function ComplaintDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [item, setItem] = useState(null);
  const [staff, setStaff] = useState([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ status: "", assigned_to: "", department: "", resolution_remarks: "" });

  function load() {
    api.get(`/api/complaints/${id}`).then((response) => {
      setItem(response.data);
      setForm({
        status: response.data.status,
        assigned_to: response.data.assigned_to || "",
        department: response.data.department || "",
        resolution_remarks: response.data.resolution_remarks || "",
      });
    }).catch((err) => setError(errorMessage(err)));
  }

  useEffect(() => {
    load();
    if (user.role === "admin") {
      api.get("/api/users/staff").then((response) => setStaff(response.data)).catch(() => setStaff([]));
    }
  }, [id, user.role]);

  async function save(event) {
    event.preventDefault();
    setError("");
    try {
      const payload = {
        status: form.status,
        department: form.department || null,
        resolution_remarks: form.resolution_remarks || null,
      };
      if (form.assigned_to) payload.assigned_to = Number(form.assigned_to);
      await api.patch(`/api/complaints/${id}`, payload);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (error && !item) return <p className="text-sm text-rose-700">{error}</p>;
  if (!item) return <p className="text-sm text-slate-500">Loading complaint…</p>;

  return (
    <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
      <section className="card p-5">
        <PageHeader title={`#${item.id} ${item.title}`} subtitle={item.description} />
        <div className="flex flex-wrap gap-2">
          <StatusBadge value={item.status} />
          <PriorityBadge value={item.suggested_priority} />
        </div>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-slate-500">Predicted category</dt><dd className="font-medium">{item.predicted_category || "Model file was not available"}</dd></div>
          <div><dt className="text-slate-500">Confidence</dt><dd className="font-medium">{item.prediction_confidence ?? "—"} {item.prediction_model ? `(${item.prediction_model})` : ""}</dd></div>
          <div><dt className="text-slate-500">Your category</dt><dd className="font-medium">{item.user_category || "Not chosen"}</dd></div>
          <div><dt className="text-slate-500">Location</dt><dd className="font-medium">{item.location || "Not given"}</dd></div>
          <div><dt className="text-slate-500">Submitted by</dt><dd className="font-medium">{item.author_name}</dd></div>
          <div><dt className="text-slate-500">Assigned to</dt><dd className="font-medium">{item.assignee_name || "Unassigned"}</dd></div>
        </dl>
        <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">{item.priority_reason} {item.priority_disclaimer}</p>
        <h2 className="mt-6 font-semibold">History</h2>
        <ul className="mt-2 space-y-2 text-sm">
          {item.history.map((row) => (
            <li key={row.id} className="rounded-xl bg-slate-50 px-3 py-2">
              <span className="font-medium">{titleCase(row.action)}</span>
              {row.to_status ? ` → ${titleCase(row.to_status)}` : ""} · {formatWhen(row.created_at)}
              {row.note ? <p className="text-slate-600">{row.note}</p> : null}
            </li>
          ))}
        </ul>
      </section>
      {user.role === "student" ? null : (
        <form className="card h-fit p-5" onSubmit={save}>
          <h2 className="font-semibold">Update</h2>
          {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
          <label className="label mt-3" htmlFor="status">Status</label>
          <select id="status" className="field" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
            {["submitted", "assigned", "in_progress", "resolved", "closed"].map((value) => <option key={value}>{value}</option>)}
          </select>
          {user.role === "admin" ? (
            <>
              <label className="label mt-3" htmlFor="assigned_to">Assign staff</label>
              <select id="assigned_to" className="field" value={form.assigned_to} onChange={(event) => setForm({ ...form, assigned_to: event.target.value })}>
                <option value="">Unchanged</option>
                {staff.map((person) => <option key={person.id} value={person.id}>{person.full_name} ({person.role})</option>)}
              </select>
            </>
          ) : null}
          <label className="label mt-3" htmlFor="department">Department</label>
          <input id="department" className="field" value={form.department} onChange={(event) => setForm({ ...form, department: event.target.value })} />
          <label className="label mt-3" htmlFor="remarks">Resolution remarks</label>
          <textarea id="remarks" className="field min-h-24" value={form.resolution_remarks} onChange={(event) => setForm({ ...form, resolution_remarks: event.target.value })} />
          <button className="btn mt-4">Save update</button>
        </form>
      )}
    </div>
  );
}
