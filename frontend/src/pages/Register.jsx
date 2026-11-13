import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../services/api";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", department: "" });
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
      await register(form);
      navigate("/app");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-4 px-6" onSubmit={onSubmit}>
      <h1 className="text-2xl font-semibold">Student registration</h1>
      <p className="text-sm text-slate-600">Public registration always creates a student. Faculty and administrator accounts are created by an administrator.</p>
      {error ? <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
      <label className="label" htmlFor="full_name">Full name</label>
      <input id="full_name" name="full_name" className="field" value={form.full_name} onChange={update} required />
      <label className="label" htmlFor="email">Email</label>
      <input id="email" name="email" type="email" className="field" value={form.email} onChange={update} required />
      <label className="label" htmlFor="department">Department</label>
      <input id="department" name="department" className="field" value={form.department} onChange={update} />
      <label className="label" htmlFor="password">Password</label>
      <input id="password" name="password" type="password" className="field" value={form.password} onChange={update} required />
      <p className="text-xs text-slate-500">Use at least 8 characters with one letter and one number.</p>
      <button className="btn" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
      <Link className="text-sm font-semibold text-indigo-700" to="/login">I already have an account</Link>
    </form>
  );
}
