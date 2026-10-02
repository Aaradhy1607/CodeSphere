import React from "react";
import { AlertCircle, CheckCircle2, AlertTriangle, Info, RefreshCw } from "lucide-react";
import { Button } from "./Button";

export type AlertVariant = "error" | "warning" | "success" | "info";

export interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  onRetry?: () => void;
  className?: string;
}

export function Alert({
  variant = "info",
  title,
  children,
  onRetry,
  className = "",
}: AlertProps) {
  const styles: Record<AlertVariant, { bg: string; icon: React.ReactNode }> = {
    error: {
      bg: "bg-[var(--status-error-bg)] border-[var(--status-error-border)] text-[var(--status-error-text)]",
      icon: <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />,
    },
    warning: {
      bg: "bg-[var(--status-warning-bg)] border-[var(--status-warning-border)] text-[var(--status-warning-text)]",
      icon: <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />,
    },
    success: {
      bg: "bg-[var(--status-success-bg)] border-[var(--status-success-border)] text-[var(--status-success-text)]",
      icon: <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />,
    },
    info: {
      bg: "bg-[var(--status-info-bg)] border-[var(--status-info-border)] text-[var(--status-info-text)]",
      icon: <Info className="w-4 h-4 shrink-0 mt-0.5" />,
    },
  };

  const current = styles[variant];

  return (
    <div
      role="alert"
      className={`p-3.5 sm:p-4 rounded-md border text-xs leading-relaxed flex items-start gap-3 ${current.bg} ${className}`}
    >
      {current.icon}
      <div className="flex-1 space-y-1">
        {title && <p className="font-bold tracking-tight">{title}</p>}
        <div className="text-[var(--text-secondary)]">{children}</div>
      </div>
      {onRetry && (
        <Button
          size="sm"
          variant="outline"
          onClick={onRetry}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          className="shrink-0"
        >
          Retry
        </Button>
      )}
    </div>
  );
}
