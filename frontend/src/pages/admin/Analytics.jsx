import { useEffect, useState } from "react";
import { Bar, BarChart, Line, LineChart, Pie, PieChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api, { errorMessage } from "../../services/api";
import { PageHeader } from "../../components/Feedback";

const COLORS = ["#4f46e5", "#0ea5e9", "#f59e0b", "#10b981", "#f43f5e", "#8b5cf6", "#64748b", "#14b8a6"];

export default function Analytics() {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  function load(event) {
    event?.preventDefault();
    const params = {};
    if (fromDate) params.from_date = fromDate;
    if (toDate) params.to_date = toDate;
    api.get("/api/analytics/overview", { params })
      .then((response) => {
        setData(response.data);
        setError("");
      })
      .catch((err) => setError(errorMessage(err)));
  }

  useEffect(load, []);

  return (
    <div>
      <PageHeader title="Analytics" subtitle="Every number is counted from stored records. User totals ignore the date filter; complaints and questions use it." />
      <form className="mb-4 flex flex-wrap items-end gap-3" onSubmit={load}>
        <div>
          <label className="label" htmlFor="from_date">From</label>
          <input id="from_date" type="date" className="field" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="to_date">To</label>
          <input id="to_date" type="date" className="field" value={toDate} onChange={(event) => setToDate(event.target.value)} />
        </div>
        <button className="btn">Apply</button>
      </form>
      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      {!data ? <p className="text-sm text-slate-500">Loading analytics…</p> : null}
      {data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="Complaints by category">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.complaints_by_category}>
                <XAxis dataKey="category" interval={0} angle={-20} height={70} tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#4f46e5" />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Complaints by status">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={data.complaints_by_status} dataKey="count" nameKey="status" outerRadius={90} label>
                  {data.complaints_by_status.map((entry, index) => <Cell key={entry.status} fill={COLORS[index % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Complaints opened by day">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={data.complaints_opened_by_day}>
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Line dataKey="count" stroke="#4f46e5" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Resolved by day">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={data.complaints_resolved_by_day}>
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Line dataKey="count" stroke="#059669" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Event registrations">
            {data.registrations_by_event.length === 0 ? <p className="text-sm text-slate-500">No events.</p> : (
              <ul className="space-y-2 text-sm">{data.registrations_by_event.map((row) => <li key={row.event} className="flex justify-between"><span>{row.event}</span><span>{row.count}</span></li>)}</ul>
            )}
          </ChartCard>
          <ChartCard title="Repeated document questions">
            {data.frequent_questions.length === 0 ? <p className="text-sm text-slate-500">No document questions have been logged.</p> : (
              <ul className="space-y-2 text-sm">{data.frequent_questions.map((row) => <li key={row.question} className="flex justify-between gap-3"><span>{row.question}</span><span>{row.count}</span></li>)}</ul>
            )}
            <p className="mt-3 text-xs text-slate-500">{data.definitions.frequent_questions}</p>
          </ChartCard>
        </div>
      ) : null}
    </div>
  );
}

function ChartCard({ title, children }) {
  return (
    <section className="card p-4">
      <h2 className="mb-3 font-semibold">{title}</h2>
      {children}
    </section>
  );
}
