import { Link } from "react-router-dom";
import { BookOpen, Bot, ChartColumn, ShieldCheck } from "lucide-react";

export default function Landing() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <p className="text-lg font-semibold text-indigo-800">CampusCopilot</p>
        <div className="flex gap-2">
          <Link className="btn-ghost" to="/login">Log in</Link>
          <Link className="btn" to="/register">Create student account</Link>
        </div>
      </header>
      <section className="mx-auto grid max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-indigo-700">M.Tech project demonstration</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
            Campus assistance grounded in institutional documents.
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-slate-600">
            Ask questions from uploaded PDFs, file a complaint only after you confirm it, classify that complaint,
            and show administrators what the database actually contains.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link className="btn" to="/login">Open the demo</Link>
            <a className="btn-ghost" href="http://localhost:8000/docs">API documentation</a>
          </div>
        </div>
        <div className="card p-6">
          <p className="text-sm font-semibold text-slate-900">What the assistant is allowed to do</p>
          <ul className="mt-4 space-y-3 text-sm text-slate-600">
            <li>Answer from retrieved document chunks and show the page.</li>
            <li>Say when the documents do not contain the answer.</li>
            <li>Submit a complaint or event registration only after YES.</li>
            <li>Suggest a complaint category with a trained classifier.</li>
          </ul>
        </div>
      </section>
      <section className="mx-auto grid max-w-6xl gap-4 px-6 pb-16 md:grid-cols-4">
        {[
          [BookOpen, "Retrieval", "PDF text is chunked, embedded, and searched with FAISS."],
          [Bot, "Controlled tools", "The agent can call only five backend functions."],
          [ShieldCheck, "Roles", "Students, faculty, and administrators are checked on the server."],
          [ChartColumn, "Analytics", "Charts are counted from SQLite, not typed into the page."],
        ].map(([Icon, title, copy]) => (
          <article key={title} className="card p-5">
            <Icon className="text-indigo-600" size={20} />
            <h2 className="mt-3 font-semibold">{title}</h2>
            <p className="mt-2 text-sm text-slate-600">{copy}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
