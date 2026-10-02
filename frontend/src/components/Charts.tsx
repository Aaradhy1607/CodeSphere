"use client";

import React from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  Filler
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";
import { useTheme } from "@/lib/themeContext";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface BranchChartProps {
  data: Record<string, { total_students: number; average_score: number; top_score: number; placement_ready_count: number }>;
}

export function BranchProficiencyChart({ data }: BranchChartProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const branches = Object.keys(data);
  const avgScores = branches.map((b) => data[b]?.average_score || 0);
  const topScores = branches.map((b) => data[b]?.top_score || 0);

  const chartData = {
    labels: branches,
    datasets: [
      {
        label: "Average Score",
        data: avgScores,
        backgroundColor: isDark ? "rgba(20, 184, 166, 0.8)" : "rgba(15, 118, 110, 0.85)",
        borderColor: isDark ? "#2dd4bf" : "#0f766e",
        borderWidth: 1,
        borderRadius: 3,
      },
      {
        label: "Top Score",
        data: topScores,
        backgroundColor: isDark ? "rgba(56, 189, 248, 0.7)" : "rgba(3, 105, 161, 0.75)",
        borderColor: isDark ? "#38bdf8" : "#0284c7",
        borderWidth: 1,
        borderRadius: 3,
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top" as const,
        labels: {
          color: isDark ? "#cbd5e1" : "#334155",
          font: { size: 11, family: "ui-sans-serif, system-ui, sans-serif" },
          boxWidth: 12,
          padding: 12
        }
      },
      tooltip: {
        backgroundColor: isDark ? "#0e141c" : "#ffffff",
        borderColor: isDark ? "#233144" : "#cbd5e1",
        borderWidth: 1,
        titleColor: isDark ? "#f1f5f9" : "#0f172a",
        bodyColor: isDark ? "#cbd5e1" : "#334155",
        padding: 10,
        cornerRadius: 4,
      }
    },
    scales: {
      x: {
        grid: { color: isDark ? "rgba(35, 49, 68, 0.4)" : "rgba(203, 213, 225, 0.6)" },
        ticks: { color: isDark ? "#8899ac" : "#64748b", font: { size: 11, weight: "bold" as const } }
      },
      y: {
        max: 500,
        grid: { color: isDark ? "rgba(35, 49, 68, 0.4)" : "rgba(203, 213, 225, 0.6)" },
        ticks: { color: isDark ? "#8899ac" : "#64748b", font: { size: 10 } }
      }
    }
  };

  return (
    <div className="h-60 w-full">
      <Bar data={chartData} options={options} />
    </div>
  );
}

interface TopicMasteryProps {
  topics: Record<string, number>;
}

export function TopicMasteryProgress({ topics }: TopicMasteryProps) {
  const entries = Object.entries(topics || {});

  if (entries.length === 0) {
    return (
      <div className="py-4 text-center text-xs text-[var(--text-muted)]">
        No topic proficiency records available.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {entries.map(([topic, pct]) => {
        const color =
          pct >= 75 ? "bg-[var(--status-success-text)]" :
          pct >= 60 ? "bg-[var(--accent-primary)]" :
          "bg-[var(--status-warning-text)]";

        return (
          <div key={`topic-mastery-${topic}`} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-[var(--text-primary)]">{topic}</span>
              <span className="font-mono font-bold text-[var(--text-muted)]">{(Number(pct) || 0).toFixed(1)}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-[var(--bg-subtle)] overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${color}`}
                style={{ width: `${Math.min(Number(pct) || 0, 100)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface ScoreTrajectoryProps {
  scores: number[];
  labels?: string[];
}

export function ScoreTrajectoryLine({ scores, labels }: ScoreTrajectoryProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const chartLabels = labels || scores.map((_, i) => `Round ${i + 1}`);

  const chartData = {
    labels: chartLabels,
    datasets: [
      {
        label: "Score",
        data: scores,
        borderColor: isDark ? "#14b8a6" : "#0f766e",
        backgroundColor: isDark ? "rgba(20, 184, 166, 0.12)" : "rgba(15, 118, 110, 0.08)",
        tension: 0.2,
        fill: true,
        pointBackgroundColor: isDark ? "#2dd4bf" : "#0f766e",
        pointBorderColor: isDark ? "#0e141c" : "#ffffff",
        pointBorderWidth: 1.5,
        pointRadius: 3.5,
        pointHoverRadius: 5
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: isDark ? "#0e141c" : "#ffffff",
        borderColor: isDark ? "#233144" : "#cbd5e1",
        borderWidth: 1,
        titleColor: isDark ? "#f1f5f9" : "#0f172a",
        bodyColor: isDark ? "#cbd5e1" : "#334155",
        padding: 8,
        cornerRadius: 4
      }
    },
    scales: {
      x: {
        grid: { color: isDark ? "rgba(35, 49, 68, 0.4)" : "rgba(203, 213, 225, 0.6)" },
        ticks: { color: isDark ? "#8899ac" : "#64748b", font: { size: 10 } }
      },
      y: {
        max: 100,
        min: 0,
        grid: { color: isDark ? "rgba(35, 49, 68, 0.4)" : "rgba(203, 213, 225, 0.6)" },
        ticks: { color: isDark ? "#8899ac" : "#64748b", font: { size: 10 } }
      }
    }
  };

  return (
    <div className="h-40 w-full">
      <Line data={chartData} options={options} />
    </div>
  );
}
