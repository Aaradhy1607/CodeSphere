import React from "react";
import { Loader2 } from "lucide-react";

export function Spinner({
  size = "md",
  className = "",
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = {
    sm: "w-4 h-4",
    md: "w-6 h-6",
    lg: "w-8 h-8",
  };

  return (
    <Loader2
      className={`animate-spin text-[var(--accent-primary)] ${sizes[size]} ${className}`}
      aria-label="Loading..."
    />
  );
}

export function LoadingState({
  message = "Loading...",
  className = "",
}: {
  message?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={`flex flex-col items-center justify-center p-12 space-y-3 text-center ${className}`}
    >
      <Spinner size="lg" />
      <p className="text-xs font-medium text-[var(--text-muted)] font-mono tracking-wide">{message}</p>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse bg-[var(--bg-subtle)] rounded ${className}`}
      aria-hidden="true"
    />
  );
}
