import { useEffect, useState } from "react";
import api, { errorMessage } from "../services/api";
import { DemoBadge } from "../components/Badges";
import { Empty, PageHeader } from "../components/Feedback";
import { formatWhen } from "../utils/format";

export default function Notices() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/notices").then((response) => setRows(response.data)).catch((err) => setError(errorMessage(err)));
  }, []);

  return (
    <div>
      <PageHeader title="Notices" subtitle="Summaries and dates are extracted automatically. A date on this page is not a verified official deadline until you read the notice text." />
      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      {!rows ? <p className="text-sm text-slate-500">Loading notices…</p> : null}
      {rows && rows.length === 0 ? <Empty>No notices yet.</Empty> : null}
      <div className="space-y-4">
        {rows?.map((notice) => (
          <article key={notice.id} className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">{notice.title}</h2>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold">Audience: {notice.audience}</span>
              {notice.provenance === "demo" ? <DemoBadge /> : null}
              {notice.provenance === "official_public_copy" ? <span className="rounded-full bg-indigo-50 px-2 py-1 text-xs font-semibold text-indigo-800">Excerpt from a public PDF</span> : null}
            </div>
            <p className="mt-3 text-sm text-slate-800">{notice.summary}</p>
            <p className="mt-2 text-xs text-amber-800">{notice.extraction_disclaimer} Method: {notice.summary_method}.</p>
            {notice.deadlines?.length ? (
              <ul className="mt-3 list-disc pl-5 text-sm text-slate-700">
                {notice.deadlines.map((item, index) => (
                  <li key={index}>{item.date_text || "Date not detected"} — {item.description}</li>
                ))}
              </ul>
            ) : null}
            {notice.action_items?.length ? (
              <div className="mt-3 text-sm">
                <p className="font-medium">Extracted action items</p>
                <ul className="list-disc pl-5">{notice.action_items.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            ) : null}
            <details className="mt-3 text-sm text-slate-600">
              <summary className="cursor-pointer font-medium text-indigo-700">Full notice</summary>
              <p className="mt-2 whitespace-pre-wrap">{notice.body}</p>
            </details>
            {notice.source_url ? <a className="mt-3 block text-sm text-indigo-700" href={notice.source_url} target="_blank" rel="noreferrer">Source PDF</a> : null}
            <p className="mt-3 text-xs text-slate-400">{formatWhen(notice.created_at)}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
