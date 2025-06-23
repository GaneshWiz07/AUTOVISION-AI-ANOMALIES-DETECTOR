import React, { createContext, useContext, useEffect, useState } from "react";
import { authAPI, AuthUser } from "@/lib/api";

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  verificationMessage: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (
    email: string,
    password: string,
    fullName?: string
  ) => Promise<{ verificationRequired: boolean }>;
  logout: () => Promise<void>;
  clearVerificationMessage: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [verificationMessage, setVerificationMessage] = useState<string | null>(
    null
  );

  const clearVerificationMessage = () => {
    setVerificationMessage(null);
  };
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      // CRITICAL: Never trust localStorage alone - always validate with server
      const token = localStorage.getItem("access_token");
      if (token) {
        // Always validate token with server - this calls the /auth/me endpoint
        // which validates the token AND checks the database for verified user profile
        const userData = await authAPI.getCurrentUser(); // Only set user if server confirms both token validity AND database verification
        setUser(userData);
      } else {
        // No token means not authenticated
        setUser(null);
      }
    } catch (error) {
      console.error(
        "Auth check failed - user not verified or invalid token:",
        error
      );
      // CRITICAL: Clear all local storage if server validation fails
      // This ensures no localStorage fallback is possible
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      setUser(null);
    } finally {
      setLoading(false);
    }
  };
  const login = async (email: string, password: string) => {
    try {
      const response = await authAPI.login(email, password);

      localStorage.setItem("access_token", response.access_token);
      localStorage.setItem("refresh_token", response.refresh_token);

      setUser(response.user);
    } catch (error: any) {
      console.error("Login failed:", error);

      // Provide user-friendly error messages
      let errorMessage = "Login failed. Please try again.";

      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.response?.status === 401) {
        errorMessage =
          "Invalid email or password. Please check your credentials.";
      } else if (error.response?.status === 403) {
        errorMessage =
          "Account not verified. Please check your email or contact support.";
      } else if (error.message) {
        errorMessage = error.message;
      }

      // Create a new error with the user-friendly message
      const userError = new Error(errorMessage);
      throw userError;
    }
  };
  const signup = async (
    email: string,
    password: string,
    fullName?: string
  ): Promise<{ verificationRequired: boolean }> => {
    try {
      const response = await authAPI.signup(email, password, fullName);

      // Check if this is a verification required response
      if (response.verification_required) {
        // Don't treat this as an error - it's a successful signup that requires verification
        setVerificationMessage(
          response.message ||
            "Account created successfully! Please check your email for a verification link, then sign in."
        );
        return { verificationRequired: true };
      }

      // Complete signup with immediate login
      localStorage.setItem("access_token", response.access_token);
      localStorage.setItem("refresh_token", response.refresh_token);
      setUser(response.user);
      return { verificationRequired: false };
    } catch (error: any) {
      console.error("Signup failed:", error);
      console.error("Error details:", {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        message: error.message,
        code: error.code,
      });

      // Log the full response for debugging
      if (error.response?.data) {
        console.error(
          "Full server response:",
          JSON.stringify(error.response.data, null, 2)
        );
      } // Provide user-friendly error messages
      let errorMessage = "Registration failed. Please try again.";

      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;

        // Check for email verification message
        if (
          detail.includes("check your email for verification") ||
          detail.includes("email confirmation") ||
          detail.includes("verify") ||
          detail.includes("verification")
        ) {
          errorMessage =
            "Account created successfully! Please check your email for a verification link, then sign in.";
        } else {
          errorMessage = detail;
        }
      } else if (error.response?.status === 400) {
        errorMessage =
          "Invalid registration data. Please check your information.";
      } else if (error.response?.status === 409) {
        errorMessage =
          "An account with this email already exists. Please sign in instead.";
      } else if (
        error.code === "NETWORK_ERROR" ||
        error.message?.includes("Network Error")
      ) {
        errorMessage =
          "Cannot connect to server. Please check if the backend is running.";
      } else if (
        error.code === "ECONNREFUSED" ||
        error.message?.includes("ECONNREFUSED")
      ) {
        errorMessage =
          "Server is not responding. Please start the backend server.";
      } else if (error.response?.status === 500) {
        errorMessage =
          "Server error. Please check the database connection and try again.";
      } else if (error.message) {
        errorMessage = error.message;
      }

      // Create a new error with the user-friendly message
      const userError = new Error(errorMessage);
      throw userError;
    }
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      setUser(null);
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
  };
  const value = {
    user,
    loading,
    verificationMessage,
    login,
    signup,
    logout,
    clearVerificationMessage,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
