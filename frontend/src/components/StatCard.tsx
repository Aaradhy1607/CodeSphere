"use client";

import React from "react";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  onClick?: () => void;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconColor = "text-[var(--accent-primary)]",
  iconBg = "bg-[var(--accent-subtle)] border-[var(--accent-border)]",
  trend,
  onClick,
}: StatCardProps) {
  return (
    <div
      onClick={onClick}
      className={`bg-[var(--bg-surface)] p-4 sm:p-5 rounded-md border border-[var(--border-subtle)] text-left flex flex-col justify-between transition-colors shadow-xs ${
        onClick ? "cursor-pointer hover:border-[var(--border-default)] hover:bg-[var(--bg-subtle)]" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-3 mb-2.5">
        <span className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-wider font-mono truncate">
          {title}
        </span>
        <div
          className={`p-1.5 rounded border ${iconBg} ${iconColor} shrink-0`}
          aria-hidden="true"
        >
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div>
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="text-xl sm:text-2xl font-bold text-[var(--text-primary)] tracking-tight font-mono">
            {value}
          </span>
          {trend && (
            <span
              className={`text-[10px] font-bold font-mono px-1.5 py-0.2 rounded border ${
                trend.isPositive
                  ? "bg-[var(--status-success-bg)] text-[var(--status-success-text)] border-[var(--status-success-border)]"
                  : "bg-[var(--status-error-bg)] text-[var(--status-error-text)] border-[var(--status-error-border)]"
              }`}
            >
              {trend.isPositive ? "+" : ""}
              {trend.value}
            </span>
          )}
        </div>
        {subtitle && (
          <p className="text-[11px] text-[var(--text-muted)] mt-1 truncate leading-tight">
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
}
