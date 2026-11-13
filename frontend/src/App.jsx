import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import AppShell from "./components/AppShell";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Assistant from "./pages/Assistant";
import Notices from "./pages/Notices";
import Events from "./pages/Events";
import Registrations from "./pages/Registrations";
import ComplaintForm from "./pages/ComplaintForm";
import ComplaintList from "./pages/ComplaintList";
import ComplaintDetail from "./pages/ComplaintDetail";
import Profile from "./pages/Profile";
import Documents from "./pages/admin/Documents";
import Users from "./pages/admin/Users";
import EventAdmin from "./pages/admin/EventAdmin";
import NoticeAdmin from "./pages/admin/NoticeAdmin";
import Analytics from "./pages/admin/Analytics";
import ModelEval from "./pages/admin/ModelEval";

function Shell({ roles, children }) {
  return (
    <ProtectedRoute roles={roles}>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/app" element={<Shell><Dashboard /></Shell>} />
          <Route path="/app/assistant" element={<Shell><Assistant /></Shell>} />
          <Route path="/app/notices" element={<Shell><Notices /></Shell>} />
          <Route path="/app/events" element={<Shell><Events /></Shell>} />
          <Route path="/app/registrations" element={<Shell roles={["student", "admin"]}><Registrations /></Shell>} />
          <Route path="/app/complaints/new" element={<Shell roles={["student", "admin"]}><ComplaintForm /></Shell>} />
          <Route path="/app/complaints" element={<Shell><ComplaintList /></Shell>} />
          <Route path="/app/complaints/:id" element={<Shell><ComplaintDetail /></Shell>} />
          <Route path="/app/profile" element={<Shell><Profile /></Shell>} />
          <Route path="/app/admin/documents" element={<Shell roles={["admin"]}><Documents /></Shell>} />
          <Route path="/app/admin/users" element={<Shell roles={["admin"]}><Users /></Shell>} />
          <Route path="/app/admin/events" element={<Shell roles={["admin"]}><EventAdmin /></Shell>} />
          <Route path="/app/admin/notices" element={<Shell roles={["admin"]}><NoticeAdmin /></Shell>} />
          <Route path="/app/admin/analytics" element={<Shell roles={["admin"]}><Analytics /></Shell>} />
          <Route path="/app/admin/models" element={<Shell roles={["admin"]}><ModelEval /></Shell>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
