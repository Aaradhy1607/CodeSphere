"use client";

import React, { ReactNode } from "react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { UserRole } from "@/lib/types";

const ADMIN_ROLES: UserRole[] = [
  "SUPER_ADMIN",
  "ADMIN",
  "PLACEMENT_ADMIN",
  "FACULTY",
  "QUESTION_SETTER",
  "REVIEWER"
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute requiredRole={ADMIN_ROLES}>
      {children}
    </ProtectedRoute>
  );
}
