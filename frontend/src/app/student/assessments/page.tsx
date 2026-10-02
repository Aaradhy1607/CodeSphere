"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Assessment, AssessmentStatus } from "@/lib/types";
import {
  Shield, Calendar, Clock, BookOpen, CheckCircle2,
  AlertTriangle, Radio, Play, RefreshCw, BarChart2,
  Lock, ArrowRight, Award
} from "lucide-react";

export default function StudentAssessmentsPage() {
  const router = useRouter();
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ACTIVE" | "UPCOMING" | "PAST">("ACTIVE");
  const [error, setError] = useState<string | null>(null);

  const fetchAssessments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.assessments.list();
      setAssessments(data);
    } catch (err: any) {
      setError(err.message || "Failed to load assessments");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssessments();
  }, []);

  const now = new Date();

  const categorizedAssessments = assessments.filter(a => {
    if (a.status === "DRAFT" || a.status === "ARCHIVED") return false;
    const startT = new Date(a.start_time);
    const endT = new Date(a.end_time);

    if (filter === "ACTIVE") {
      return a.status === "ACTIVE" || (startT <= now && now <= endT);
    } else if (filter === "UPCOMING") {
      return a.status === "SCHEDULED" || (now < startT && a.status === "PUBLISHED");
    } else {
      return a.status === "COMPLETED" || now > endT;
    }
  });

  const getStatusBadge = (status: AssessmentStatus) => {
    switch (status) {
      case "ACTIVE":
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"><Radio className="w-3 h-3 animate-pulse" /> LIVE NOW</span>;
      case "PUBLISHED":
      case "SCHEDULED":
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"><Calendar className="w-3 h-3" /> SCHEDULED</span>;
      case "COMPLETED":
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border border-zinc-500/20">CLOSED</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-500/10 text-zinc-600 dark:text-zinc-400">{status}</span>;
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-6 lg:p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-6">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]">
                <Shield className="w-6 h-6" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight">Assessments & Examination Portal</h1>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Secure proctored exams, placement coding rounds, and technical aptitude screenings.
            </p>
          </div>

          <button
            onClick={fetchAssessments}
            className="p-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)] transition self-start md:self-auto"
            title="Refresh assessments"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Tab Filters */}
        <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-2">
          <button
            onClick={() => setFilter("ACTIVE")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
              filter === "ACTIVE"
                ? "bg-[var(--accent-primary)] text-white shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
            }`}
          >
            <Radio className="w-3.5 h-3.5 animate-pulse" /> Live / Active
          </button>
          <button
            onClick={() => setFilter("UPCOMING")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
              filter === "UPCOMING"
                ? "bg-[var(--accent-primary)] text-white shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
            }`}
          >
            <Calendar className="w-3.5 h-3.5" /> Upcoming
          </button>
          <button
            onClick={() => setFilter("PAST")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
              filter === "PAST"
                ? "bg-[var(--accent-primary)] text-white shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)]"
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" /> Past Tests
          </button>
        </div>

        {error && (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Assessments Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-48 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] animate-pulse" />
            ))}
          </div>
        ) : categorizedAssessments.length === 0 ? (
          <div className="text-center py-16 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl">
            <Shield className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3 opacity-40" />
            <h3 className="text-base font-semibold">No {filter.toLowerCase()} assessments</h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Check back soon for new placement tests or explore past evaluations.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {categorizedAssessments.map((a) => {
              const isOpen = a.status === "ACTIVE" || (new Date(a.start_time) <= now && now <= new Date(a.end_time));

              return (
                <div
                  key={a.id}
                  className="flex flex-col justify-between rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-[var(--border-hover)] transition shadow-sm overflow-hidden"
                >
                  <div className="p-5 space-y-4">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-semibold text-base line-clamp-1 text-[var(--text-primary)]">
                        {a.title}
                      </h3>
                      {getStatusBadge(a.status)}
                    </div>

                    {a.description && (
                      <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{a.description}</p>
                    )}

                    <div className="grid grid-cols-2 gap-2 text-xs text-[var(--text-secondary)] pt-2 border-t border-[var(--border-subtle)]">
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                        <span>{a.duration_minutes} Minutes</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <BookOpen className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                        <span>{a.total_questions} Questions</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Award className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                        <span>{a.total_marks} Total Marks</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Shield className="w-3.5 h-3.5 text-emerald-500" />
                        <span>{a.fullscreen_enforced ? "Proctored" : "Standard"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="p-3 bg-[var(--bg-subtle)]/50 border-t border-[var(--border-subtle)] flex items-center justify-between">
                    <span className="text-[10px] text-[var(--text-muted)]">
                      {new Date(a.end_time).toLocaleDateString()}
                    </span>

                    {isOpen ? (
                      <Link
                        href={`/student/assessments/${a.id}/take`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--accent-primary)] text-white text-xs font-semibold hover:opacity-90 transition shadow-sm"
                      >
                        <Play className="w-3.5 h-3.5" /> Start Exam
                      </Link>
                    ) : filter === "UPCOMING" ? (
                      <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-muted)] text-xs font-semibold">
                        <Lock className="w-3 h-3" /> Locked
                      </span>
                    ) : (
                      <span className="text-xs font-semibold text-[var(--text-secondary)]">
                        Closed
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

      </div>
    </div>
  );
}
