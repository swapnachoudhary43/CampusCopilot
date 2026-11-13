import { titleCase } from "../utils/format";

const STATUS = {
  submitted: "bg-slate-100 text-slate-700",
  assigned: "bg-blue-100 text-blue-800",
  in_progress: "bg-amber-100 text-amber-800",
  resolved: "bg-emerald-100 text-emerald-800",
  closed: "bg-slate-200 text-slate-600",
};

const PRIORITY = {
  high: "bg-rose-100 text-rose-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-slate-100 text-slate-700",
};

export function StatusBadge({ value }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS[value] || "bg-slate-100 text-slate-700"}`}>
      {titleCase(value)}
    </span>
  );
}

export function DemoBadge() {
  return <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-900">DEMO DATA</span>;
}

export function PriorityBadge({ value }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${PRIORITY[value] || "bg-slate-100"}`}>
      {titleCase(value)} priority
    </span>
  );
}
