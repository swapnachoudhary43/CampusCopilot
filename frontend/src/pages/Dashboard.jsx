import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api, { errorMessage } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { PageHeader } from "../components/Feedback";
import { StatusBadge } from "../components/Badges";

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        if (user.role === "admin") {
          const [overview, activity] = await Promise.all([
            api.get("/api/analytics/overview"),
            api.get("/api/analytics/activity"),
          ]);
          if (!cancelled) setData({ overview: overview.data, activity: activity.data });
          return;
        }
        const [complaints, notices, events] = await Promise.all([
          api.get("/api/complaints"),
          api.get("/api/notices"),
          api.get("/api/events"),
        ]);
        if (!cancelled) setData({ complaints: complaints.data, notices: notices.data, events: events.data });
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user.role]);

  if (error) return <p className="text-sm text-rose-700">{error}</p>;
  if (!data) return <p className="text-sm text-slate-500">Loading dashboard…</p>;

  if (user.role === "admin") {
    const overview = data.overview;
    return (
      <div>
        <PageHeader title="Administrator dashboard" subtitle="Counts on this page come from the database for the full stored history." />
        <div className="grid gap-4 md:grid-cols-4">
          {[
            ["Users", overview.total_users],
            ["Complaints", overview.total_complaints],
            ["Indexed documents", overview.documents_processed],
            ["Registrations", overview.total_registrations],
          ].map(([label, value]) => (
            <article key={label} className="card p-4">
              <p className="text-sm text-slate-500">{label}</p>
              <p className="mt-2 text-3xl font-semibold">{value}</p>
            </article>
          ))}
        </div>
        <div className="card mt-6 h-72 p-4">
          <p className="mb-3 text-sm font-semibold">Complaints by status</p>
          <ResponsiveContainer width="100%" height="85%">
            <BarChart data={overview.complaints_by_status}>
              <XAxis dataKey="status" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#4f46e5" radius={6} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card mt-6 p-4">
          <p className="text-sm font-semibold">Recent activity</p>
          <ul className="mt-3 divide-y divide-slate-100 text-sm">
            {data.activity.length === 0 ? <li className="py-3 text-slate-500">No activity yet.</li> : null}
            {data.activity.slice(0, 8).map((row) => (
              <li key={row.id} className="flex justify-between gap-3 py-2">
                <span>{row.action}</span>
                <span className="text-slate-500">{row.details}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  const openComplaints = data.complaints.filter((item) => !["resolved", "closed"].includes(item.status)).length;
  return (
    <div>
      <PageHeader
        title={user.role === "faculty" ? "Faculty dashboard" : `Hello, ${user.full_name.split(" ")[0]}`}
        subtitle={user.role === "faculty" ? "Complaints assigned to your account." : "Your complaints, notices, and upcoming events."}
        action={<Link className="btn" to="/app/assistant">Ask the assistant</Link>}
      />
      <div className="grid gap-4 md:grid-cols-3">
        <article className="card p-4"><p className="text-sm text-slate-500">Open complaints</p><p className="mt-2 text-3xl font-semibold">{openComplaints}</p></article>
        <article className="card p-4"><p className="text-sm text-slate-500">Notices</p><p className="mt-2 text-3xl font-semibold">{data.notices.length}</p></article>
        <article className="card p-4"><p className="text-sm text-slate-500">Events</p><p className="mt-2 text-3xl font-semibold">{data.events.length}</p></article>
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section className="card p-4">
          <h2 className="font-semibold">{user.role === "faculty" ? "Assigned complaints" : "My complaints"}</h2>
          <ul className="mt-3 space-y-3">
            {data.complaints.slice(0, 4).map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 text-sm">
                <Link className="font-medium text-indigo-700" to={`/app/complaints/${item.id}`}>{item.title}</Link>
                <StatusBadge value={item.status} />
              </li>
            ))}
            {data.complaints.length === 0 ? <li className="text-sm text-slate-500">No complaints submitted yet.</li> : null}
          </ul>
        </section>
        <section className="card p-4">
          <h2 className="font-semibold">Latest notices</h2>
          <ul className="mt-3 space-y-3 text-sm">
            {data.notices.slice(0, 4).map((item) => (
              <li key={item.id}>
                <p className="font-medium">{item.title}</p>
                <p className="text-slate-600">{item.summary}</p>
              </li>
            ))}
            {data.notices.length === 0 ? <li className="text-slate-500">No notices have been published.</li> : null}
          </ul>
        </section>
      </div>
    </div>
  );
}
