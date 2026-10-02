"use client";

import React, { forwardRef, ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "outline"
  | "ghost"
  | "destructive"
  | "subtle";

export type ButtonSize = "sm" | "md" | "lg" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className = "",
      variant = "primary",
      size = "md",
      isLoading = false,
      disabled = false,
      leftIcon,
      rightIcon,
      type = "button",
      ...props
    },
    ref
  ) => {
    const base =
      "inline-flex items-center justify-center font-medium rounded-md transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] disabled:opacity-50 disabled:cursor-not-allowed select-none active:scale-[0.99]";

    const variants: Record<ButtonVariant, string> = {
      primary:
        "bg-[var(--accent-primary)] hover:bg-[var(--accent-hover)] active:bg-[var(--accent-active)] text-white shadow-sm border border-transparent",
      secondary:
        "bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] active:bg-[var(--bg-active)] text-[var(--text-primary)] border border-[var(--border-subtle)] shadow-sm",
      outline:
        "bg-transparent hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-default)]",
      ghost:
        "bg-transparent hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-transparent",
      destructive:
        "bg-[var(--status-error-text)] hover:opacity-90 text-white border border-transparent shadow-sm",
      subtle:
        "bg-[var(--accent-subtle)] hover:opacity-80 text-[var(--accent-text)] border border-[var(--accent-border)]",
    };

    const sizes: Record<ButtonSize, string> = {
      sm: "text-xs px-2.5 py-1.5 gap-1.5",
      md: "text-xs sm:text-sm px-3.5 py-2 gap-2",
      lg: "text-sm sm:text-base px-5 py-2.5 gap-2.5",
      icon: "p-2 aspect-square",
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isLoading}
        className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
        ) : (
          leftIcon && <span className="shrink-0">{leftIcon}</span>
        )}
        {children}
        {!isLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = "Button";
