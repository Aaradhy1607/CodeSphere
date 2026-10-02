"use client";

import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Compass, Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-4 text-center space-y-5">
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center shadow-inner"
        style={{
          backgroundColor: "var(--accent-subtle)",
          border: "1px solid var(--border-subtle)",
          color: "var(--accent-primary)"
        }}
      >
        <Compass className="w-7 h-7" />
      </div>

      <div className="space-y-1.5 max-w-md">
        <span className="text-xs font-mono font-bold uppercase tracking-wider" style={{ color: "var(--accent-primary)" }}>
          404 — Page Not Found
        </span>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
          Resource Unavailable
        </h1>
        <p className="text-xs sm:text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          The requested page, assessment round, or problem identifier could not be located in the CodeSphere system.
        </p>
      </div>

      <div className="flex items-center gap-3 pt-2">
        <Link href="/">
          <Button variant="primary" size="md" leftIcon={<Home className="w-4 h-4" />}>
            Return Home
          </Button>
        </Link>
      </div>
    </div>
  );
}
