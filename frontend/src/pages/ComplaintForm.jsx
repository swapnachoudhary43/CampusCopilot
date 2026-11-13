import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { errorMessage } from "../services/api";
import { PageHeader } from "../components/Feedback";

const CATEGORIES = ["", "Infrastructure", "Hostel", "Transportation", "IT Support", "Library", "Academic", "Cleanliness", "Other"];

export default function ComplaintForm() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ title: "", description: "", location: "", user_category: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = { ...form, user_category: form.user_category || null, location: form.location || null };
      const response = await api.post("/api/complaints", payload);
      navigate(`/app/complaints/${response.data.id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="mx-auto max-w-2xl" onSubmit={onSubmit}>
      <PageHeader title="Submit a complaint" subtitle="The category prediction is stored with the complaint. You can also choose a category yourself." />
      {error ? <p className="mb-3 text-sm text-rose-700">{error}</p> : null}
      <label className="label" htmlFor="title">Title</label>
      <input id="title" name="title" className="field mb-3" value={form.title} onChange={update} required minLength={5} />
      <label className="label" htmlFor="description">What happened?</label>
      <textarea id="description" name="description" className="field mb-3 min-h-32" value={form.description} onChange={update} required minLength={10} />
      <label className="label" htmlFor="location">Location</label>
      <input id="location" name="location" className="field mb-3" value={form.location} onChange={update} />
      <label className="label" htmlFor="user_category">Your category, if you want to choose one</label>
      <select id="user_category" name="user_category" className="field mb-4" value={form.user_category} onChange={update}>
        {CATEGORIES.map((item) => <option key={item || "blank"} value={item}>{item || "Let the model suggest it"}</option>)}
      </select>
      <button className="btn" disabled={busy}>{busy ? "Saving…" : "Submit complaint"}</button>
    </form>
  );
}
