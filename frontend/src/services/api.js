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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    if (status === 401 && localStorage.getItem("cc_token")) {
      localStorage.removeItem("cc_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }
    if (status === 429 && error.response?.data && typeof error.response.data.detail !== "string") {
      error.response.data.detail = "Too many requests. Wait a moment and try again.";
    }
    return Promise.reject(error);
  },
);

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
