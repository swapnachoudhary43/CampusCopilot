import { useEffect, useState } from "react";
import api, { errorMessage } from "../services/api";
import { Alert, PageHeader } from "../components/Feedback";

const DOCUMENT_QUESTIONS = [
  "How does Ordinance 9 say fellowships are awarded?",
  "Explain the Choice Based Credit System in Ordinance 14.",
  "What is the canteen menu on Wednesday?",
];

const ACTION_PROMPTS = [
  "I want to complain about a broken projector in classroom LH-2.",
  "Show me upcoming events and register me for DEMO: assistant workshop.",
  "What is my complaint status?",
];

const MODE_COPY = {
  gemini: "Generated from retrieved documents",
  retrieval_only: "Quoted from documents — language model not used",
  insufficient_context: "Not found in the uploaded documents",
  llm_unavailable: "Language model unavailable",
  gemini_fallback: "Gemini unavailable — showing retrieved source passages",
};

export default function Assistant() {
  const [mode, setMode] = useState("documents");
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const base = mode === "documents" ? "/api/chat" : "/api/agent";

  useEffect(() => {
    setActiveId(null);
    setMessages([]);
    api.get(`${base}/sessions`).then((response) => setSessions(response.data)).catch((err) => setError(errorMessage(err)));
  }, [base]);

  async function openSession(id) {
    setActiveId(id);
    const response = await api.get(`${base}/sessions/${id}/messages`);
    setMessages(response.data);
  }

  async function ensureSession() {
    if (activeId) return activeId;
    const response = await api.post(`${base}/sessions`);
    setSessions((current) => [response.data, ...current]);
    setActiveId(response.data.id);
    return response.data.id;
  }

  async function send(content) {
    const question = content.trim();
    if (!question) return;
    setBusy(true);
    setError("");
    try {
      const id = await ensureSession();
      await api.post(`${base}/sessions/${id}/messages`, { content: question });
      const history = await api.get(`${base}/sessions/${id}/messages`);
      const sessionList = await api.get(`${base}/sessions`);
      setSessions(sessionList.data);
      setMessages(history.data);
      setText("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const last = messages[messages.length - 1];
  const waiting = Boolean(last?.needs_confirmation || last?.metadata?.needs_confirmation);

  return (
    <div>
      <PageHeader
        title="Campus assistant"
        subtitle="Document questions search the uploaded PDFs. Campus actions can file a complaint or register for an event only after you reply YES."
      />
      <div className="mb-4 flex gap-2">
        <button className={mode === "documents" ? "btn" : "btn-ghost"} onClick={() => setMode("documents")}>Ask documents</button>
        <button className={mode === "actions" ? "btn" : "btn-ghost"} onClick={() => setMode("actions")}>Campus actions</button>
      </div>
      <Alert>{error}</Alert>
      <div className="mt-4 grid gap-4 lg:grid-cols-[240px_1fr]">
        <aside className="card p-3">
          <button
            className="btn w-full"
            onClick={() => {
              setActiveId(null);
              setMessages([]);
            }}
          >
            New conversation
          </button>
          <ul className="mt-3 space-y-1">
            {sessions.map((session) => (
              <li key={session.id}>
                <button className={`w-full rounded-lg px-2 py-2 text-left text-sm ${session.id === activeId ? "bg-indigo-50 text-indigo-800" : "hover:bg-slate-50"}`} onClick={() => openSession(session.id)}>
                  {session.title}
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <section className="card flex min-h-[540px] flex-col">
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {messages.length === 0 ? (
              <div>
                <p className="text-sm text-slate-500">Try one of these. Do not type passwords into the assistant.</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(mode === "documents" ? DOCUMENT_QUESTIONS : ACTION_PROMPTS).map((prompt) => (
                    <button key={prompt} className="btn-ghost text-left" onClick={() => send(prompt)} disabled={busy}>{prompt}</button>
                  ))}
                </div>
              </div>
            ) : null}
            {messages.map((message) => (
              <article key={message.id} className={message.role === "user" ? "ml-8 rounded-2xl bg-indigo-600 px-4 py-3 text-sm text-white" : "mr-8 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-800"}>
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.metadata?.answer_mode ? (
                  <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-indigo-700">{MODE_COPY[message.metadata.answer_mode] || message.metadata.answer_mode}</p>
                ) : null}
                {message.sources?.length ? (
                  <div className="mt-3 grid gap-2">
                    {message.sources.map((source) => (
                      <div key={`${source.document_id}-${source.page_number}`} className="rounded-xl border border-slate-200 bg-white p-3 text-slate-700">
                        <p className="text-xs font-semibold text-slate-900">{source.document_title} · page {source.page_number} · similarity {source.score}</p>
                        <p className="mt-1 text-xs">{source.excerpt}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
            {busy ? <p className="text-sm text-slate-500">Working…</p> : null}
          </div>
          {waiting ? (
            <div className="flex gap-2 border-t border-slate-100 px-4 py-3">
              <button className="btn" disabled={busy} onClick={() => send("YES")}>Confirm</button>
              <button className="btn-ghost" disabled={busy} onClick={() => send("NO")}>Cancel</button>
            </div>
          ) : null}
          <form
            className="flex gap-2 border-t border-slate-100 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              send(text);
            }}
          >
            <label className="sr-only" htmlFor="assistant-message">Message</label>
            <input id="assistant-message" className="field" value={text} onChange={(event) => setText(event.target.value)} placeholder={mode === "documents" ? "Ask about a campus rule" : "Describe the action you want"} />
            <button className="btn" disabled={busy || text.trim().length < 2}>Send</button>
          </form>
        </section>
      </div>
    </div>
  );
}
