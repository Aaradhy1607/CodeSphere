"use client";

import React, { forwardRef, SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      id,
      label,
      error,
      helperText,
      children,
      className = "",
      disabled = false,
      ...props
    },
    ref
  ) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full space-y-1.5 text-left">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-xs font-semibold text-[var(--text-secondary)] select-none"
          >
            {label}
            {props.required && <span className="text-[var(--status-error-text)] ml-1">*</span>}
          </label>
        )}

        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            disabled={disabled}
            className={`w-full appearance-none rounded-md bg-[var(--bg-surface)] border text-xs sm:text-sm text-[var(--text-primary)] pl-3 pr-9 py-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:border-[var(--border-focus)] disabled:opacity-50 disabled:bg-[var(--bg-subtle)] cursor-pointer ${
              error
                ? "border-[var(--status-error-border)] focus-visible:ring-[var(--status-error-text)]"
                : "border-[var(--border-default)] hover:border-[var(--border-strong)]"
            } ${className}`}
            {...props}
          >
            {children}
          </select>

          <ChevronDown className="w-4 h-4 text-[var(--text-muted)] absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>

        {error ? (
          <p className="text-[11px] text-[var(--status-error-text)] font-medium">{error}</p>
        ) : helperText ? (
          <p className="text-[11px] text-[var(--text-muted)]">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

Select.displayName = "Select";
