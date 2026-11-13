import { useState } from "react";
import api, { errorMessage } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { PageHeader } from "../components/Feedback";

export default function Profile() {
  const { user, updateUser } = useAuth();
  const [profile, setProfile] = useState({ full_name: user.full_name, department: user.department || "" });
  const [password, setPassword] = useState({ current_password: "", new_password: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function saveProfile(event) {
    event.preventDefault();
    setError("");
    try {
      const response = await api.patch("/api/auth/me", profile);
      updateUser(response.data);
      setMessage("Profile saved.");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    setError("");
    try {
      await api.post("/api/auth/change-password", password);
      setPassword({ current_password: "", new_password: "" });
      setMessage("Password updated.");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="grid max-w-3xl gap-4">
      <PageHeader title="Profile" subtitle={`${user.email} · ${user.role}`} />
      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      <form className="card p-5" onSubmit={saveProfile}>
        <label className="label" htmlFor="full_name">Full name</label>
        <input id="full_name" className="field mb-3" value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} />
        <label className="label" htmlFor="department">Department</label>
        <input id="department" className="field mb-4" value={profile.department} onChange={(event) => setProfile({ ...profile, department: event.target.value })} />
        <button className="btn">Save profile</button>
      </form>
      <form className="card p-5" onSubmit={savePassword}>
        <h2 className="mb-3 font-semibold">Change password</h2>
        <label className="label" htmlFor="current_password">Current password</label>
        <input id="current_password" type="password" className="field mb-3" value={password.current_password} onChange={(event) => setPassword({ ...password, current_password: event.target.value })} />
        <label className="label" htmlFor="new_password">New password</label>
        <input id="new_password" type="password" className="field mb-4" value={password.new_password} onChange={(event) => setPassword({ ...password, new_password: event.target.value })} />
        <button className="btn">Update password</button>
      </form>
    </div>
  );
}
