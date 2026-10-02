"use client";

import React from "react";
import { Terminal, Shield, HardDrive, Clock } from "lucide-react";
import { Badge } from "./ui/Badge";

interface CommandVisualProps {
  status?: "ACTIVE" | "UPCOMING" | "IDLE";
  activeEventTitle?: string;
  metricLabel?: string;
  metricValue?: string | number;
  subMetricLabel?: string;
  subMetricValue?: string | number;
  interactive?: boolean;
}

export function CommandVisual({
  status = "IDLE",
  activeEventTitle,
  metricLabel = "Online Judge Engine",
  metricValue = "Multi-Lang Sandbox",
  subMetricLabel = "Core State",
  subMetricValue = "Ready",
}: CommandVisualProps) {
  const isLive = status === "ACTIVE";
  const isUpcoming = status === "UPCOMING";

  return (
    <div className="bg-[var(--bg-surface)] rounded-md border border-[var(--border-subtle)] p-4 sm:p-5 text-left space-y-4 shadow-xs">
      {/* Top Header */}
      <div className="flex items-center justify-between gap-3 pb-3 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[var(--status-success-text)]" />
          <span className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider font-mono">
            {isLive ? "Live Assessment Session Active" : isUpcoming ? "Scheduled Assessment Pipeline" : "Assessment Operations Ready"}
          </span>
        </div>

        <Badge variant={isLive ? "success" : isUpcoming ? "default" : "neutral"} size="sm">
          {isLive ? "LIVE ROUND" : isUpcoming ? "STANDBY" : "OPERATIONAL"}
        </Badge>
      </div>

      {/* Grid Specs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
        <div className="p-2.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)]">
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--text-muted)] uppercase">
            <Terminal className="w-3 h-3 text-[var(--accent-primary)]" />
            <span>Sandboxes</span>
          </div>
          <p className="font-semibold text-[var(--text-primary)] mt-1 text-xs">Python • C++ • C • Java</p>
        </div>

        <div className="p-2.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)]">
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--text-muted)] uppercase">
            <Clock className="w-3 h-3 text-[var(--status-success-text)]" />
            <span>Time Limit</span>
          </div>
          <p className="font-semibold text-[var(--text-primary)] mt-1 text-xs">2.0s per test vector</p>
        </div>

        <div className="p-2.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)]">
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--text-muted)] uppercase">
            <HardDrive className="w-3 h-3 text-[var(--discipline-aiml-text)]" />
            <span>Memory Quota</span>
          </div>
          <p className="font-semibold text-[var(--text-primary)] mt-1 text-xs">256 MB Heap</p>
        </div>

        <div className="p-2.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)]">
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--text-muted)] uppercase">
            <Shield className="w-3 h-3 text-[var(--status-warning-text)]" />
            <span>Validation</span>
          </div>
          <p className="font-semibold text-[var(--text-primary)] mt-1 text-xs">Automated Judge</p>
        </div>
      </div>

      {/* Bottom Summary Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-[var(--text-muted)] border-t border-[var(--border-subtle)] font-mono">
        <div className="flex items-center gap-1.5">
          <span>{metricLabel}:</span>
          <span className="font-semibold text-[var(--text-primary)]">{metricValue}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span>{subMetricLabel}:</span>
          <span className="font-semibold text-[var(--status-success-text)]">{subMetricValue}</span>
        </div>
      </div>
    </div>
  );
}
