import { createContext, useContext, useEffect, useState } from "react";
import api from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("cc_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/api/auth/me")
      .then((response) => setUser(response.data))
      .catch(() => localStorage.removeItem("cc_token"))
      .finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const response = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("cc_token", response.data.access_token);
    setUser(response.data.user);
    return response.data.user;
  }

  async function register(payload) {
    const response = await api.post("/api/auth/register", payload);
    localStorage.setItem("cc_token", response.data.access_token);
    setUser(response.data.user);
    return response.data.user;
  }

  function logout() {
    localStorage.removeItem("cc_token");
    setUser(null);
  }

  function updateUser(next) {
    setUser(next);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
