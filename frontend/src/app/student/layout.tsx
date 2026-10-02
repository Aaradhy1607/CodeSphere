"use client";

import React, { ReactNode } from "react";
import { ProtectedRoute } from "@/components/ProtectedRoute";

export default function StudentLayout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      {children}
    </ProtectedRoute>
  );
}
