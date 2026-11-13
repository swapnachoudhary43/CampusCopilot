import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../services/api";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("student@example.com");
  const [password, setPassword] = useState("Student@12345");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate("/app");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden bg-slate-950 p-12 text-white lg:block">
        <p className="text-sm text-indigo-200">CampusCopilot</p>
        <h1 className="mt-6 text-4xl font-semibold">Sign in.</h1>
        <p className="mt-4 max-w-md text-slate-300">
          Seeded accounts are marked DEMO DATA. They are not Devi Ahilya Vishwavidyalaya accounts. Change the passwords before any deployment outside this project.
        </p>
      </div>
      <form className="mx-auto flex w-full max-w-md flex-col justify-center gap-4 px-6 py-12" onSubmit={onSubmit}>
        <h2 className="text-2xl font-semibold">Log in</h2>
        {error ? <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
        <label className="label" htmlFor="email">Email</label>
        <input id="email" className="field" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <label className="label" htmlFor="password">Password</label>
        <input id="password" className="field" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        <button className="btn" disabled={busy}>{busy ? "Checking…" : "Log in"}</button>
        <p className="text-sm text-slate-600">
          New student? <Link className="font-semibold text-indigo-700" to="/register">Create an account</Link>
        </p>
        <p className="text-xs text-slate-500">
          Seeded demo: student@example.com / Student@12345, faculty@example.com / Faculty@12345, admin@example.com / Admin@12345.
        </p>
      </form>
    </div>
  );
}
