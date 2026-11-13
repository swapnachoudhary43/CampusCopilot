import { useEffect, useState } from "react";
import api, { errorMessage } from "../../services/api";
import { PageHeader } from "../../components/Feedback";

const EMPTY = { full_name: "", email: "", password: "", role: "faculty", department: "" };

export default function Users() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");

  function load() {
    api.get("/api/users").then((response) => setRows(response.data)).catch((err) => setError(errorMessage(err)));
  }

  useEffect(load, []);

  async function create(event) {
    event.preventDefault();
    setError("");
    try {
      await api.post("/api/users", form);
      setForm(EMPTY);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function update(user, changes) {
    await api.patch(`/api/users/${user.id}`, changes);
    load();
  }

  return (
    <div>
      <PageHeader title="User management" subtitle="Deactivating an account blocks the next login. Passwords are stored only as bcrypt hashes." />
      {error ? <p className="mb-3 text-sm text-rose-700">{error}</p> : null}
      <form className="card mb-6 grid gap-3 p-5 md:grid-cols-5" onSubmit={create}>
        <input className="field" placeholder="Full name" aria-label="Full name" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required />
        <input className="field" type="email" placeholder="Email" aria-label="Email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required />
        <input className="field" type="password" placeholder="Password" aria-label="Password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required />
        <select className="field" aria-label="Role" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
          <option value="student">student</option>
          <option value="faculty">faculty</option>
          <option value="admin">admin</option>
        </select>
        <button className="btn">Add user</button>
      </form>
      <div className="card overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Active</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((user) => (
              <tr key={user.id} className="border-t border-slate-100">
                <td className="px-4 py-3">{user.full_name}</td>
                <td className="px-4 py-3">{user.email}</td>
                <td className="px-4 py-3">
                  <select className="field" value={user.role} aria-label={`Role for ${user.full_name}`} onChange={(event) => update(user, { role: event.target.value })}>
                    <option value="student">student</option>
                    <option value="faculty">faculty</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td className="px-4 py-3">
                  <button className="btn-ghost" onClick={() => update(user, { is_active: !user.is_active })}>
                    {user.is_active ? "Deactivate" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
