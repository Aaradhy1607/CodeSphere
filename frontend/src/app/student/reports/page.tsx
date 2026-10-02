"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { StudentReport } from "@/lib/types";
import {
  CheckCircle2, AlertTriangle, TrendingUp,
  Clock, Brain, ChevronRight, BarChart3
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";

export default function StudentReportsPage() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [reports, setReports] = useState<StudentReport[]>([]);
  const [selectedReportIdx, setSelectedReportIdx] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
      return;
    }
    if (user) {
      api.reports.getMyReports()
        .then(setReports)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [user, isLoading, router]);

  if (isLoading || loading || !user) {
    return <LoadingState message="Loading cognitive evaluation reports..." className="min-h-[60vh]" />;
  }

  const activeReport = reports[selectedReportIdx];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg" style={{ backgroundColor: "var(--accent-subtle)", color: "var(--accent-primary)", border: "1px solid var(--border-subtle)" }}>
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                Algorithmic Performance Diagnostics
              </h1>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                AI-synthesized algorithmic diagnostic feedback and cognitive problem-solving evaluations
              </p>
            </div>
          </div>
        </div>

        {reports.length > 0 && (
          <Badge variant="neutral" size="md">
            {reports.length} Verified Assessment Reports
          </Badge>
        )}
      </div>

      {reports.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={Brain}
              title="No Diagnostic Evaluations Generated Yet"
              description="Once you participate in scheduled coding assessments and results are finalized, deep performance insights and cognitive feedback will appear here."
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Report Selectors */}
          <div className="lg:col-span-4 space-y-3">
            <h2 className="text-xs font-bold uppercase tracking-wider px-1" style={{ color: "var(--text-muted)" }}>
              Assessment History
            </h2>
            <div className="space-y-2">
              {reports.map((rep, idx) => (
                <button
                  key={rep.id}
                  type="button"
                  onClick={() => setSelectedReportIdx(idx)}
                  className="w-full p-4 rounded-xl border text-left transition space-y-2"
                  style={{
                    backgroundColor: selectedReportIdx === idx ? "var(--accent-subtle)" : "var(--bg-surface)",
                    borderColor: selectedReportIdx === idx ? "var(--accent-primary)" : "var(--border-subtle)",
                    boxShadow: selectedReportIdx === idx ? "0 1px 3px rgba(0,0,0,0.05)" : "none"
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono font-bold" style={{ color: "var(--text-muted)" }}>
                      {new Date(rep.generated_at).toLocaleDateString()}
                    </span>
                    <Badge variant="success" size="sm">
                      Score: {rep.score} pts
                    </Badge>
                  </div>
                  <p className="font-bold text-xs line-clamp-1" style={{ color: "var(--text-primary)" }}>
                    {rep.event_title}
                  </p>
                  <div className="flex items-center justify-between text-[11px] pt-1" style={{ borderTop: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                    <span>Rank {rep.rank} of {rep.total_participants}</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Right Column: Detailed Diagnostic Report */}
          {activeReport && (
            <div className="lg:col-span-8 space-y-6">
              <Card>
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <Badge variant="neutral" size="sm" className="mb-1">
                        Evaluation Dossier
                      </Badge>
                      <CardTitle className="text-xl">{activeReport.event_title}</CardTitle>
                      <CardDescription>
                        Generated on {new Date(activeReport.generated_at).toLocaleDateString()}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="px-3 py-1.5 rounded-lg text-center" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                        <span className="text-[10px] uppercase font-semibold block" style={{ color: "var(--text-muted)" }}>Cohort Rank</span>
                        <span className="font-mono font-bold text-sm" style={{ color: "var(--text-primary)" }}>#{activeReport.rank}</span>
                      </div>
                      <div className="px-3 py-1.5 rounded-lg text-center" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                        <span className="text-[10px] uppercase font-semibold block" style={{ color: "var(--text-muted)" }}>Assessment Score</span>
                        <span className="font-mono font-bold text-sm" style={{ color: "var(--color-success)" }}>{activeReport.score}</span>
                      </div>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="space-y-6">
                  {/* Overall Summary */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
                      <Brain className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} /> Algorithmic Assessment Synthesis
                    </h3>
                    <div className="text-xs sm:text-sm leading-relaxed p-4 rounded-xl border font-sans" style={{ backgroundColor: "var(--bg-canvas)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}>
                      {activeReport.overall_performance_summary}
                    </div>
                  </div>

                  {/* Strengths & Improvement Areas Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Strengths */}
                    <div className="p-4 rounded-xl space-y-3" style={{ backgroundColor: "var(--color-success-subtle)", border: "1px solid var(--color-success)" }}>
                      <h4 className="font-bold text-xs flex items-center gap-2" style={{ color: "var(--color-success)" }}>
                        <CheckCircle2 className="w-4 h-4 shrink-0" /> Verified Competencies
                      </h4>
                      <ul className="space-y-2 text-xs" style={{ color: "var(--text-primary)" }}>
                        {activeReport.strengths?.map((str, i) => (
                          <li key={`strength-${str}-${i}`} className="flex items-start gap-2">
                            <span className="font-bold shrink-0" style={{ color: "var(--color-success)" }}>•</span>
                            <span>{str}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Areas for Improvement */}
                    <div className="p-4 rounded-xl space-y-3" style={{ backgroundColor: "var(--color-warning-subtle)", border: "1px solid var(--color-warning)" }}>
                      <h4 className="font-bold text-xs flex items-center gap-2" style={{ color: "var(--color-warning)" }}>
                        <AlertTriangle className="w-4 h-4 shrink-0" /> Recommended Remediation Areas
                      </h4>
                      <ul className="space-y-2 text-xs" style={{ color: "var(--text-primary)" }}>
                        {activeReport.areas_for_improvement?.map((imp, i) => (
                          <li key={`improvement-${imp}-${i}`} className="flex items-start gap-2">
                            <span className="font-bold shrink-0" style={{ color: "var(--color-warning)" }}>•</span>
                            <span>{imp}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Topic Breakdown Matrix */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
                      <BarChart3 className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} /> Topic Mastery Matrix
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {Object.entries(activeReport.topic_performance || {}).map(([topic, rating]) => {
                        const badgeVariant =
                          rating.includes("High") || rating.includes("Mastery") ? "success" :
                          rating.includes("Moderate") || rating.includes("Good") ? "info" : "warning";

                        return (
                          <div
                            key={topic}
                            className="flex items-center justify-between p-3 rounded-lg text-xs"
                            style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}
                          >
                            <span className="font-medium truncate" style={{ color: "var(--text-primary)" }}>{topic}</span>
                            <Badge variant={badgeVariant} size="sm">
                              {rating}
                            </Badge>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Cognitive Insights & Efficiency */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 text-xs" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                    <div className="p-3.5 rounded-lg space-y-1" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                      <span className="text-[10px] uppercase font-bold flex items-center gap-1.5" style={{ color: "var(--text-muted)" }}>
                        <Clock className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} /> Execution Time Rating
                      </span>
                      <p className="font-bold" style={{ color: "var(--text-primary)" }}>{activeReport.time_efficiency_rating || "Standard"}</p>
                    </div>
                    <div className="p-3.5 rounded-lg space-y-1" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                      <span className="text-[10px] uppercase font-bold flex items-center gap-1.5" style={{ color: "var(--text-muted)" }}>
                        <TrendingUp className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} /> Longitudinal Trajectory
                      </span>
                      <p style={{ color: "var(--text-secondary)" }}>{activeReport.comparative_analysis || "Steady baseline performance recorded across rounds."}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
