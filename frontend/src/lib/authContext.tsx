"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";
import { User, UserRole, Permission, AuthResponse, AccountStatus } from "./types";
import { api } from "./api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  role: UserRole | null;
  permissions: Permission[];
  isLoading: boolean;
  needsOnboarding: boolean;
  hasPermission: (permission: Permission) => boolean;
  hasRole: (role: UserRole | UserRole[]) => boolean;
  isSuperAdmin: boolean;
  isAdmin: boolean;
  isPlacementAdmin: boolean;
  isFaculty: boolean;
  isQuestionSetter: boolean;
  isReviewer: boolean;
  isStudent: boolean;
  login: (email: string, password?: string) => Promise<AuthResponse>;
  googleLogin: (
    email: string,
    full_name?: string,
    avatar_url?: string,
    enrollment_no?: string,
    branch?: string,
    academic_year?: number
  ) => Promise<AuthResponse>;
  completeOnboarding: (
    full_name: string,
    enrollment_no: string,
    branch: string,
    academic_year: number,
    phone?: string
  ) => Promise<void>;
  switchUser: (userId?: number, role?: string, email?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const applyAuthData = (data: { user: User; access_token: string; refresh_token?: string; permissions?: Permission[]; needs_onboarding?: boolean }) => {
    localStorage.setItem("codesphere_token", data.access_token);
    if (data.refresh_token) {
      localStorage.setItem("codesphere_refresh_token", data.refresh_token);
    }
    localStorage.setItem("codesphere_user", JSON.stringify(data.user));

    setToken(data.access_token);
    setUser(data.user);
    setPermissions(data.permissions || data.user.permissions || []);
    setNeedsOnboarding(!!data.needs_onboarding);
  };

  const clearAuthData = () => {
    localStorage.removeItem("codesphere_token");
    localStorage.removeItem("codesphere_refresh_token");
    localStorage.removeItem("codesphere_user");
    setToken(null);
    setUser(null);
    setPermissions([]);
    setNeedsOnboarding(false);
  };

  const refreshUser = useCallback(async () => {
    try {
      const storedToken = localStorage.getItem("codesphere_token");
      if (!storedToken) {
        clearAuthData();
        setIsLoading(false);
        return;
      }
      setToken(storedToken);
      const currentUser = await api.auth.getMe();
      setUser(currentUser);
      setPermissions(currentUser.permissions || []);
      if (currentUser.role === "STUDENT" && !currentUser.student_profile) {
        setNeedsOnboarding(true);
      } else {
        setNeedsOnboarding(false);
      }
    } catch (err) {
      console.error("Auth session expired or invalid:", err);
      clearAuthData();
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();

    // Multi-tab synchronization
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "codesphere_token") {
        if (!e.newValue) {
          clearAuthData();
        } else {
          refreshUser();
        }
      }
    };

    const handleAuthExpired = () => {
      clearAuthData();
    };

    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("codesphere_auth_expired", handleAuthExpired);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("codesphere_auth_expired", handleAuthExpired);
    };
  }, [refreshUser]);

  const login = async (email: string, password?: string): Promise<AuthResponse> => {
    setIsLoading(true);
    try {
      const res = await api.auth.login(email, password);
      applyAuthData(res);
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const googleLogin = async (
    email: string,
    full_name?: string,
    avatar_url?: string,
    enrollment_no?: string,
    branch?: string,
    academic_year?: number
  ): Promise<AuthResponse> => {
    setIsLoading(true);
    try {
      const res = await api.auth.googleAuth(email, full_name, avatar_url, enrollment_no, branch, academic_year);
      applyAuthData(res);
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const completeOnboarding = async (
    full_name: string,
    enrollment_no: string,
    branch: string,
    academic_year: number,
    phone?: string
  ) => {
    setIsLoading(true);
    try {
      const updatedUser = await api.auth.onboarding(full_name, enrollment_no, branch, academic_year, phone);
      setUser(updatedUser);
      setNeedsOnboarding(false);
    } finally {
      setIsLoading(false);
    }
  };

  const switchUser = async (userId?: number, role?: string, email?: string) => {
    setIsLoading(true);
    try {
      const res = await api.auth.switchDemoUser(userId, role, email);
      applyAuthData(res);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      const refreshToken = localStorage.getItem("codesphere_refresh_token");
      await api.auth.logout(refreshToken || undefined);
    } catch {
      // Ignore network errors on logout
    } finally {
      clearAuthData();
    }
  };

  const hasPermission = (permission: Permission): boolean => {
    if (!user) return false;
    return permissions.includes(permission) || (user.permissions?.includes(permission) ?? false);
  };

  const hasRole = (targetRole: UserRole | UserRole[]): boolean => {
    if (!user) return false;
    if (Array.isArray(targetRole)) {
      return targetRole.includes(user.role);
    }
    return user.role === targetRole;
  };

  const isSuperAdmin = user?.role === "SUPER_ADMIN";
  const isAdmin = user?.role === "ADMIN" || user?.role === "SUPER_ADMIN";
  const isPlacementAdmin = user?.role === "PLACEMENT_ADMIN";
  const isFaculty = user?.role === "FACULTY";
  const isQuestionSetter = user?.role === "QUESTION_SETTER";
  const isReviewer = user?.role === "REVIEWER";
  const isStudent = user?.role === "STUDENT";

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        role: user?.role || null,
        permissions,
        isLoading,
        needsOnboarding,
        hasPermission,
        hasRole,
        isSuperAdmin,
        isAdmin,
        isPlacementAdmin,
        isFaculty,
        isQuestionSetter,
        isReviewer,
        isStudent,
        login,
        googleLogin,
        completeOnboarding,
        switchUser,
        logout,
        refreshUser
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
