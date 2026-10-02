"use client";

import React, { useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { AlertCircle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("CodeSphere Application Error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-4 text-center space-y-5">
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center"
        style={{
          backgroundColor: "var(--color-danger-subtle)",
          border: "1px solid var(--color-danger)",
          color: "var(--color-danger)"
        }}
      >
        <AlertCircle className="w-7 h-7" />
      </div>

      <div className="space-y-1.5 max-w-md">
        <span className="text-xs font-mono font-bold uppercase tracking-wider" style={{ color: "var(--color-danger)" }}>
          Runtime Exception
        </span>
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
          Something went wrong
        </h1>
        <p className="text-xs sm:text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {error.message || "An unexpected client error occurred while rendering the page."}
        </p>
      </div>

      <div className="flex items-center gap-3 pt-2">
        <Button
          variant="primary"
          size="md"
          onClick={() => reset()}
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          Try Again
        </Button>
        <Link href="/">
          <Button variant="secondary" size="md" leftIcon={<Home className="w-4 h-4" />}>
            Home
          </Button>
        </Link>
      </div>
    </div>
  );
}
