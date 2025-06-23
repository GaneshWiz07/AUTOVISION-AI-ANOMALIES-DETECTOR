import React, { createContext, useContext, useState, useEffect } from "react";
import { authAPI } from "@lib/api.js";

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [verificationMessage, setVerificationMessage] = useState("");

  // Check if user is logged in on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("access_token");
      if (token) {
        try {
          const userData = await authAPI.getCurrentUser();
          setUser(userData);
          setIsAuthenticated(true);
        } catch (error) {
          console.error("Auth check failed:", error);
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        }
      }
      setLoading(false);
    };

    checkAuth();
  }, []);

  const login = async (email, password) => {
    try {
      const response = await authAPI.login(email, password);

      if (response.access_token) {
        localStorage.setItem("access_token", response.access_token);
        if (response.refresh_token) {
          localStorage.setItem("refresh_token", response.refresh_token);
        }

        // Get user data
        const userData = await authAPI.getCurrentUser();
        setUser(userData);
        setIsAuthenticated(true);

        return response;
      } else {
        throw new Error("No access token received");
      }
    } catch (error) {
      console.error("Login failed:", error);
      throw error;
    }
  };

  const signup = async (email, password, fullName) => {
    try {
      const response = await authAPI.signup(email, password, fullName);

      if (response.verification_required) {
        setVerificationMessage(
          "Please check your email and click the verification link before logging in."
        );
        return { verificationRequired: true };
      }

      // If no verification required, log the user in
      if (response.access_token) {
        localStorage.setItem("access_token", response.access_token);
        if (response.refresh_token) {
          localStorage.setItem("refresh_token", response.refresh_token);
        }

        const userData = await authAPI.getCurrentUser();
        setUser(userData);
        setIsAuthenticated(true);

        return { verificationRequired: false };
      }

      return response;
    } catch (error) {
      console.error("Signup failed:", error);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  const clearVerificationMessage = () => {
    setVerificationMessage("");
  };

  const value = {
    user,
    loading,
    isAuthenticated,
    verificationMessage,
    login,
    signup,
    logout,
    clearVerificationMessage,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
