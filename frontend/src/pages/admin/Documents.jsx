import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { Empty, PageHeader } from "../../components/Feedback";

const CATEGORIES = ["Regulations", "Examinations", "Attendance", "Fees", "Hostel", "Scholarship", "Calendar", "Syllabus", "Circular", "Other"];

export default function Documents() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ title: "", category: "Other", description: "", source_url: "", publication_date: "" });
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [crawl, setCrawl] = useState(null);

  function loadCrawl() {
    api.get("/api/crawl").then((response) => setCrawl(response.data)).catch(() => setCrawl(null));
  }

  function load() {
    api.get("/api/documents").then((response) => setRows(response.data)).catch((err) => setError(errorMessage(err)));
  }

  useEffect(load, []);
  useEffect(() => {
    loadCrawl();
    const timer = setInterval(loadCrawl, 4000);
    return () => clearInterval(timer);
  }, []);

  async function startCrawl() {
    setBusy(true);
    setError("");
    try {
      await api.post("/api/crawl/start", { max_pages: 70, max_pdfs: 6 });
      setMessage("Official-site crawl started. This page will show pages as they are indexed.");
      loadCrawl();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function upload(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF file.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    const data = new FormData();
    data.append("title", form.title);
    data.append("category", form.category);
    data.append("description", form.description);
    if (form.source_url) data.append("source_url", form.source_url);
    if (form.publication_date) data.append("publication_date", form.publication_date);
    data.append("file", file);
    try {
      const response = await api.post("/api/documents", data);
      setMessage(`${response.data.title} is ${response.data.status}. ${response.data.status_message || ""}`);
      setForm({ title: "", category: "Other", description: "", source_url: "", publication_date: "" });
      setFile(null);
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!window.confirm("Delete this document and remove it from search?")) return;
    await api.delete(`/api/documents/${id}`);
    load();
  }

  async function reindex() {
    setBusy(true);
    setError("");
    try {
      const response = await api.post("/api/documents/reindex");
      setMessage(`Search index rebuilt with ${response.data.indexed_chunks} chunks.`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title="Document management" subtitle="Text PDFs are indexed. A scanned PDF is stored with the status needs OCR and is not searched." action={<button className="btn-ghost" onClick={reindex} disabled={busy}>Rebuild search index</button>} />
      <section className="card mb-6 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Official website crawl</h2>
            <p className="text-sm text-slate-600">Indexes public pages from dauniv.ac.in and ietdavv.edu.in. Student questions do not start a crawl.</p>
          </div>
          <button className="btn" onClick={startCrawl} disabled={busy || crawl?.run?.running}>Start crawl</button>
        </div>
        {crawl?.run?.running ? <p className="mt-2 text-sm text-indigo-700">Crawl in progress.</p> : null}
        {crawl?.counts ? <p className="mt-2 text-sm text-slate-600">{Object.entries(crawl.counts).map(([status, count]) => `${status}: ${count}`).join(" · ")}</p> : null}
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {(crawl?.sites || []).map((site) => (
            <p key={site.url} className="text-xs text-slate-600">
              <span className="font-semibold">{site.name}</span> · {site.status} · {site.pages_indexed} indexed
              {site.error ? ` · ${site.error}` : ""}
              <a className="block text-indigo-700" href={site.url} target="_blank" rel="noreferrer">{site.url}</a>
            </p>
          ))}
        </div>
        <div className="mt-3 space-y-2">
          {(crawl?.records || []).slice(0, 8).map((record) => (
            <p key={record.url} className="text-xs text-slate-600">
              <span className="font-semibold">{record.status}</span> · {record.title || record.url}
              {record.error ? ` · ${record.error}` : ""}
            </p>
          ))}
        </div>
      </section>
      {error ? <p className="mb-3 text-sm text-rose-700">{error}</p> : null}
      {message ? <p className="mb-3 text-sm text-emerald-700">{message}</p> : null}
      <form className="card mb-6 grid gap-3 p-5 md:grid-cols-2" onSubmit={upload}>
        <div>
          <label className="label" htmlFor="title">Title</label>
          <input id="title" className="field" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
        </div>
        <div>
          <label className="label" htmlFor="category">Category</label>
          <select id="category" className="field" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
            {CATEGORIES.map((item) => <option key={item}>{item}</option>)}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="label" htmlFor="description">Description</label>
          <input id="description" className="field" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
        </div>
        <div>
          <label className="label" htmlFor="source-url">Source URL, if this file came from a public page</label>
          <input id="source-url" className="field" value={form.source_url} onChange={(event) => setForm({ ...form, source_url: event.target.value })} placeholder="https://" />
        </div>
        <div>
          <label className="label" htmlFor="published">Publication date, if known</label>
          <input id="published" className="field" value={form.publication_date} onChange={(event) => setForm({ ...form, publication_date: event.target.value })} placeholder="As printed on the document" />
        </div>
        <div>
          <label className="label" htmlFor="file">PDF file</label>
          <input id="file" className="field" type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        </div>
        <div className="flex items-end">
          <button className="btn" disabled={busy}>{busy ? "Processing…" : "Upload and index"}</button>
        </div>
      </form>
      {rows.length === 0 ? <Empty>No documents uploaded.</Empty> : null}
      <div className="space-y-3">
        {rows.map((row) => (
          <article key={row.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <h2 className="font-semibold">{row.title}</h2>
              <p className="text-sm text-slate-600">{row.provenance || "uploaded"} · {row.category} · {row.status} · {row.page_count} pages · {row.chunk_count} chunks</p>
              {row.publication_date ? <p className="text-sm text-slate-600">Publication date: {row.publication_date}</p> : null}
              {row.source_url ? <a className="text-sm text-indigo-700" href={row.source_url} target="_blank" rel="noreferrer">{row.source_url}</a> : null}
              {row.status_message ? <p className="text-sm text-slate-500">{row.status_message}</p> : null}
            </div>
            <button className="btn-ghost" onClick={() => remove(row.id)}>Delete</button>
          </article>
        ))}
      </div>
    </div>
  );
}
