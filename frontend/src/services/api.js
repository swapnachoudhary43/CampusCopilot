import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("cc_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (!detail) {
    return "The server could not be reached. Check that the backend is running on port 8000.";
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(" ");
  }
  return "The request was rejected.";
}

export default api;
