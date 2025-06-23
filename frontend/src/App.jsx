import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import LoadingSpinner from "./components/LoadingSpinner";
import Login from "./pages/Login";
import SignUp from "./pages/SignUp";
import Dashboard from "./pages/Dashboard";
import VideoAnalytics from "./pages/VideoAnalytics";

// Protected Route component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="md" />
      </div>
    );
  }

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
};

// Public Route component (redirect to dashboard if authenticated)
const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="md" />
      </div>
    );
  }

  return isAuthenticated ? <Navigate to="/" /> : <>{children}</>;
};

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Router>
          <Routes>
            {" "}
            {/* Public routes */}
            <Route
              path="/login"
              element={
                <PublicRoute>
                  <Login />
                </PublicRoute>
              }
            />
            <Route
              path="/signup"
              element={
                <PublicRoute>
                  <SignUp />
                </PublicRoute>
              }
            />{" "}
            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Layout>
                    <Dashboard />
                  </Layout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/analytics"
              element={
                <ProtectedRoute>
                  <Layout>
                    <VideoAnalytics />
                  </Layout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <Layout>
                    <VideoAnalytics />
                  </Layout>
                </ProtectedRoute>
              }
            />
            {/* Legacy redirect for /videos to /analytics */}
            <Route path="/videos" element={<Navigate to="/analytics" />} />
            {/* Catch all route */}
            <Route path="*" element={<Navigate to="/" />} />{" "}
          </Routes>
        </Router>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
