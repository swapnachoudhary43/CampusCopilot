import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  BarChart3,
  CalendarDays,
  ClipboardList,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Megaphone,
  Menu,
  MessagesSquare,
  Plus,
  Sparkles,
  Ticket,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const LINKS = {
  student: [
    ["/app", "Dashboard", LayoutDashboard],
    ["/app/assistant", "Assistant", MessagesSquare],
    ["/app/notices", "Notices", Megaphone],
    ["/app/events", "Events", CalendarDays],
    ["/app/registrations", "My registrations", Ticket],
    ["/app/complaints/new", "New complaint", Plus],
    ["/app/complaints", "My complaints", ClipboardList],
  ],
  faculty: [
    ["/app", "Dashboard", LayoutDashboard],
    ["/app/assistant", "Assistant", MessagesSquare],
    ["/app/complaints", "Assigned complaints", ClipboardList],
    ["/app/notices", "Notices", Megaphone],
    ["/app/events", "Events", CalendarDays],
  ],
  admin: [
    ["/app", "Dashboard", LayoutDashboard],
    ["/app/assistant", "Assistant", MessagesSquare],
    ["/app/admin/documents", "Documents", FileText],
    ["/app/complaints", "Complaints", ClipboardList],
    ["/app/admin/users", "Users", Users],
    ["/app/admin/events", "Events", CalendarDays],
    ["/app/admin/notices", "Notices", Megaphone],
    ["/app/admin/analytics", "Analytics", BarChart3],
    ["/app/admin/models", "Model evaluation", Sparkles],
  ],
};

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const links = LINKS[user.role] || LINKS.student;

  function signOut() {
    logout();
    navigate("/");
  }

  const sidebar = (
    <div className="flex h-full flex-col bg-slate-950 text-slate-100">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="rounded-xl bg-indigo-500 p-2">
          <GraduationCap size={20} />
        </div>
        <div>
          <p className="text-sm font-semibold">CampusCopilot</p>
          <p className="text-xs text-slate-400">Document assistant</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {links.map(([to, label, Icon]) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/app"}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${
                isActive ? "bg-indigo-600 text-white" : "text-slate-300 hover:bg-slate-800"
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-800 p-4">
        <p className="text-sm font-medium">{user.full_name}</p>
        <p className="text-xs capitalize text-slate-400">{user.role}</p>
        <button className="mt-3 flex items-center gap-2 text-sm text-slate-300 hover:text-white" onClick={signOut}>
          <LogOut size={16} /> Log out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="hidden lg:block">{sidebar}</aside>
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} aria-label="Close menu" />
          <div className="relative h-full w-72">{sidebar}</div>
        </div>
      ) : null}
      <div>
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:px-8">
          <button className="rounded-lg p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
          <p className="text-xs text-slate-500">
            Answers come only from uploaded PDFs. Accounts, complaints, and events marked DEMO DATA are not official university records.
          </p>
          <NavLink to="/app/profile" className="text-sm font-medium text-indigo-700">
            Profile
          </NavLink>
        </header>
        <main className="px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
