"use client";

import React, { forwardRef, TextareaHTMLAttributes } from "react";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      id,
      label,
      error,
      helperText,
      className = "",
      disabled = false,
      rows = 4,
      ...props
    },
    ref
  ) => {
    const textareaId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full space-y-1.5 text-left">
        {label && (
          <label
            htmlFor={textareaId}
            className="block text-xs font-semibold text-[var(--text-secondary)] select-none"
          >
            {label}
            {props.required && <span className="text-[var(--status-error-text)] ml-1">*</span>}
          </label>
        )}

        <textarea
          ref={ref}
          id={textareaId}
          rows={rows}
          disabled={disabled}
          className={`w-full rounded-md bg-[var(--bg-surface)] border text-xs sm:text-sm text-[var(--text-primary)] placeholder-[var(--text-faint)] p-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:border-[var(--border-focus)] disabled:opacity-50 disabled:bg-[var(--bg-subtle)] ${
            error
              ? "border-[var(--status-error-border)] focus-visible:ring-[var(--status-error-text)]"
              : "border-[var(--border-default)] hover:border-[var(--border-strong)]"
          } ${className}`}
          {...props}
        />

        {error ? (
          <p className="text-[11px] text-[var(--status-error-text)] font-medium">{error}</p>
        ) : helperText ? (
          <p className="text-[11px] text-[var(--text-muted)]">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

Textarea.displayName = "Textarea";
