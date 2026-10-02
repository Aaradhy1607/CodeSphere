import React from "react";
import { LucideIcon, Inbox } from "lucide-react";
import { Button } from "./Button";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  actionLabel,
  onAction,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-md bg-[var(--bg-subtle)]/60 border border-dashed border-[var(--border-default)] space-y-3 ${className}`}
    >
      <div className="w-10 h-10 rounded-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-muted)] shadow-sm">
        <Icon className="w-5 h-5" />
      </div>

      <div className="max-w-md space-y-1">
        <h4 className="text-sm font-bold text-[var(--text-primary)] tracking-tight">{title}</h4>
        {description && (
          <p className="text-xs text-[var(--text-muted)] leading-relaxed">{description}</p>
        )}
      </div>

      {actionLabel && onAction && (
        <div className="pt-2">
          <Button size="sm" variant="secondary" onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      )}
    </div>
  );
}
