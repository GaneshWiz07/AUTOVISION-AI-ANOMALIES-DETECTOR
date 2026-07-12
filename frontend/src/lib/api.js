import axios from "axios";

// Single shared API client for the whole app. Previously this configuration
// (base URL, interceptors) was duplicated three times: src/pages/api-utils.js,
// src/components/api-utils.js, and inline inside AuthContext.jsx.
const API_BASE_URL = import.meta.env.DEV
  ? "/api/v1" // Use Vite proxy in development
  : import.meta.env.VITE_API_URL ||
    "https://autovision-ai-server.onrender.com/api/v1";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Endpoints where a 401 is an expected, user-facing error (wrong password,
// invalid/expired signup link, etc.) that the calling page already displays -
// these must NOT trigger the session-expired redirect below, or the error
// message gets wiped by the redirect before the user can read it.
const AUTH_ENDPOINTS_WITH_EXPECTED_401 = ["/auth/login", "/auth/signup", "/auth/refresh"];

// Handle auth errors: a 401 from any *other* endpoint means the stored
// session token is invalid/expired, so clear it and send the user to log in.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isAuthEndpoint = AUTH_ENDPOINTS_WITH_EXPECTED_401.some((path) =>
      error.config?.url?.includes(path)
    );
    if (error.response?.status === 401 && !isAuthEndpoint) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: async (email, password) => {
    const response = await api.post("/auth/login", { email, password });
    return response.data;
  },
  signup: async (email, password, full_name) => {
    const payload = { email, password };
    if (full_name && full_name.trim()) {
      payload.full_name = full_name.trim();
    }

    const response = await api.post("/auth/signup", payload);
    return response.data;
  },

  logout: async () => {
    await api.post("/auth/logout");
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },

  getCurrentUser: async () => {
    const response = await api.get("/auth/me");
    return response.data;
  },

  refreshToken: async (refreshToken) => {
    const response = await api.post("/auth/refresh", {
      refresh_token: refreshToken,
    });
    return response.data;
  },
};

// Video API
export const videoAPI = {
  uploadVideo: async (file, onUploadProgress) => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post("/videos/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      onUploadProgress,
    });
    return response.data;
  },

  getVideos: async (limit = 50) => {
    const response = await api.get(`/videos?limit=${limit}`);
    return response.data;
  },

  getVideo: async (videoId) => {
    const response = await api.get(`/videos/${videoId}`);
    return response.data;
  },

  getVideoAnalysis: async (videoId) => {
    const response = await api.get(`/videos/${videoId}/analysis`);
    return response.data;
  },

  deleteVideo: async (videoId) => {
    const response = await api.delete(`/videos/${videoId}`);
    return response.data;
  },

  getVideoEvents: async (videoId) => {
    const response = await api.get(`/videos/${videoId}/events`);
    return response.data;
  },
  processVideo: async (videoId) => {
    const response = await api.post(`/videos/${videoId}/process`);
    return response.data;
  },
  getVideoStreamUrl: (videoId) => {
    const token = localStorage.getItem("access_token");
    const baseUrl =
      import.meta.env.VITE_API_URL ||
      "https://autovision-ai-server.onrender.com/api/v1";
    return `${baseUrl}/videos/${videoId}/stream?token=${encodeURIComponent(
      token
    )}`;
  },
};

// Events API
export const eventAPI = {
  getEvents: async (limit = 100) => {
    const response = await api.get(`/events?limit=${limit}`);
    return response.data;
  },

  updateEvent: async (eventId, data) => {
    const response = await api.put(`/events/${eventId}`, data);
    return response.data;
  },

  provideFeedback: async (eventId, isFalsePositive, feedbackScore) => {
    const response = await api.post(`/events/${eventId}/feedback`, {
      event_id: eventId,
      is_false_positive: isFalsePositive,
      feedback_score: feedbackScore,
    });
    return response.data;
  },
};

// System API
export const systemAPI = {
  getStatus: async () => {
    const response = await api.get("/system/status");
    return response.data;
  },

  getMetrics: async () => {
    const response = await api.get("/system/metrics");
    return response.data;
  },

  getSystemEvents: async (limit = 100, eventType) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (eventType) params.append("event_type", eventType);

    const response = await api.get(`/system/events?${params}`);
    return response.data;
  },

  getRLStatus: async () => {
    const response = await api.get("/rl/status");
    return response.data;
  },

  resetRLTraining: async () => {
    const response = await api.post("/rl/reset");
    return response.data;
  },

  getRAGPatterns: async (patternType) => {
    const params = patternType ? `?pattern_type=${patternType}` : "";
    const response = await api.get(`/rag/patterns${params}`);
    return response.data;
  },
  getRAGStats: async () => {
    const response = await api.get("/rag/stats");
    return response.data;
  },
};

// Settings API
export const settingsAPI = {
  getSettings: async () => {
    const response = await api.get("/settings");
    return response.data;
  },
  updateSettings: async (settings) => {
    const response = await api.put("/settings", settings);
    return response.data;
  },
};

// Video cleanup API
export const cleanupAPI = {
  getCleanupPreview: async () => {
    const response = await api.get("/cleanup/preview");
    return response.data;
  },

  runCleanup: async () => {
    const response = await api.post("/cleanup/run");
    return response.data;
  },
};

export default api;
