import React from "react";

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "destructive"
  | "info"
  | "neutral"
  | "aiml"
  | "aids"
  | "iiot"
  | "ar";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: "sm" | "md";
  dot?: boolean;
}

export function Badge({
  children,
  variant = "default",
  size = "md",
  dot = false,
  className = "",
  ...props
}: BadgeProps) {
  const base =
    "inline-flex items-center font-semibold rounded border tracking-wide select-none transition-colors";

  const sizes = {
    sm: "text-[10px] px-1.5 py-0.5 gap-1 font-mono",
    md: "text-xs px-2 py-0.5 gap-1.5 font-medium",
  };

  const variants: Record<BadgeVariant, { container: string; dot: string }> = {
    default: {
      container: "bg-[var(--accent-subtle)] text-[var(--accent-text)] border-[var(--accent-border)]",
      dot: "bg-[var(--accent-primary)]",
    },
    success: {
      container: "bg-[var(--status-success-bg)] text-[var(--status-success-text)] border-[var(--status-success-border)]",
      dot: "bg-[var(--status-success-text)]",
    },
    warning: {
      container: "bg-[var(--status-warning-bg)] text-[var(--status-warning-text)] border-[var(--status-warning-border)]",
      dot: "bg-[var(--status-warning-text)]",
    },
    destructive: {
      container: "bg-[var(--status-error-bg)] text-[var(--status-error-text)] border-[var(--status-error-border)]",
      dot: "bg-[var(--status-error-text)]",
    },
    info: {
      container: "bg-[var(--status-info-bg)] text-[var(--status-info-text)] border-[var(--status-info-border)]",
      dot: "bg-[var(--status-info-text)]",
    },
    neutral: {
      container: "bg-[var(--bg-subtle)] text-[var(--text-secondary)] border-[var(--border-default)]",
      dot: "bg-[var(--text-muted)]",
    },
    aiml: {
      container: "bg-[var(--discipline-aiml-bg)] text-[var(--discipline-aiml-text)] border-[var(--discipline-aiml-border)] font-mono font-bold",
      dot: "bg-[var(--discipline-aiml-text)]",
    },
    aids: {
      container: "bg-[var(--discipline-aids-bg)] text-[var(--discipline-aids-text)] border-[var(--discipline-aids-border)] font-mono font-bold",
      dot: "bg-[var(--discipline-aids-text)]",
    },
    iiot: {
      container: "bg-[var(--discipline-iiot-bg)] text-[var(--discipline-iiot-text)] border-[var(--discipline-iiot-border)] font-mono font-bold",
      dot: "bg-[var(--discipline-iiot-text)]",
    },
    ar: {
      container: "bg-[var(--discipline-ar-bg)] text-[var(--discipline-ar-text)] border-[var(--discipline-ar-border)] font-mono font-bold",
      dot: "bg-[var(--discipline-ar-text)]",
    },
  };

  const current = variants[variant] || variants.default;

  return (
    <span className={`${base} ${sizes[size]} ${current.container} ${className}`} {...props}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${current.dot} shrink-0`} />}
      {children}
    </span>
  );
}
