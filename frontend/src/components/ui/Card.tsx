import React from "react";

export function Card({
  children,
  className = "",
  interactive = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { interactive?: boolean }) {
  return (
    <div
      className={`bg-[var(--bg-surface)] rounded-lg border border-[var(--border-subtle)] text-[var(--text-primary)] shadow-sm transition-all duration-150 ${
        interactive
          ? "hover:border-[var(--border-default)] hover:bg-[var(--bg-subtle)] cursor-pointer"
          : ""
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`p-4 sm:p-5 flex flex-col space-y-1.5 border-b border-[var(--border-subtle)] ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={`text-sm sm:text-base font-bold text-[var(--text-primary)] tracking-tight leading-tight ${className}`}
      {...props}
    >
      {children}
    </h3>
  );
}

export function CardDescription({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={`text-xs text-[var(--text-muted)] leading-normal ${className}`} {...props}>
      {children}
    </p>
  );
}

export function CardContent({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`p-4 sm:p-5 ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`p-4 sm:p-5 border-t border-[var(--border-subtle)] flex items-center justify-between gap-3 text-xs bg-[var(--bg-subtle)]/50 rounded-b-lg ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
