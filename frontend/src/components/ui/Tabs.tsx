"use client";

import React from "react";

export interface TabItem<T extends string> {
  id: T;
  label: string;
  icon?: React.ReactNode;
  badge?: string | number;
}

export interface TabsProps<T extends string> {
  tabs: TabItem<T>[];
  activeTab: T;
  onChange: (tabId: T) => void;
  className?: string;
  size?: "sm" | "md";
}

export function Tabs<T extends string>({
  tabs,
  activeTab,
  onChange,
  className = "",
  size = "md",
}: TabsProps<T>) {
  const sizes = {
    sm: "text-xs px-2.5 py-1 gap-1.5",
    md: "text-xs sm:text-sm px-3 py-1.5 gap-2",
  };

  return (
    <div
      role="tablist"
      className={`inline-flex items-center p-1 rounded-md bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-muted)] ${className}`}
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`inline-flex items-center font-medium rounded transition-all duration-150 focus-visible:outline-none ${
              sizes[size]
            } ${
              isActive
                ? "bg-[var(--bg-surface)] text-[var(--accent-primary)] font-semibold shadow-sm border border-[var(--border-subtle)]"
                : "hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]/50"
            }`}
          >
            {tab.icon && <span className="shrink-0">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span
                className={`ml-1 px-1.5 py-0.2 text-[10px] font-mono rounded-full ${
                  isActive
                    ? "bg-[var(--accent-subtle)] text-[var(--accent-text)] font-bold"
                    : "bg-[var(--bg-hover)] text-[var(--text-muted)]"
                }`}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
