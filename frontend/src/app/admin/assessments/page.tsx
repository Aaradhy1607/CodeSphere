"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Assessment, AssessmentStatus } from "@/lib/types";
import {
  Shield, Plus, Search, Filter, Calendar, Clock,
  CheckCircle2, AlertTriangle, Users, Play, Archive,
  Eye, RefreshCw, BarChart2, Radio, Edit3, Trash2
} from "lucide-react";

export default function AdminAssessmentsPage() {
  const router = useRouter();
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchAssessments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.assessments.list(statusFilter !== "ALL" ? { status: statusFilter } : undefined);
      setAssessments(data);
    } catch (err: any) {
      setError(err.message || "Failed to load assessments");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssessments();
  }, [statusFilter]);

  const handlePublish = async (id: number) => {
    if (!confirm("Are you sure you want to publish this assessment? It will be visible to students.")) return;
    setActionLoading(id);
    try {
      await api.assessments.publish(id);
      fetchAssessments();
    } catch (err: any) {
      alert(err.message || "Failed to publish assessment");
    } finally {
      setActionLoading(null);
    }
  };

  const handleClose = async (id: number) => {
    if (!confirm("Close this assessment? No new attempts will be allowed.")) return;
    setActionLoading(id);
    try {
      await api.assessments.close(id);
      fetchAssessments();
    } catch (err: any) {
      alert(err.message || "Failed to close assessment");
    } finally {
      setActionLoading(null);
    }
  };

  const handleArchive = async (id: number) => {
    if (!confirm("Archive this assessment?")) return;
    setActionLoading(id);
    try {
      await api.assessments.archive(id);
      fetchAssessments();
    } catch (err: any) {
      alert(err.message || "Failed to archive assessment");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this draft assessment? This action cannot be undone.")) return;
    setActionLoading(id);
    try {
      await api.assessments.delete(id);
      fetchAssessments();
    } catch (err: any) {
      alert(err.message || "Failed to delete assessment");
    } finally {
      setActionLoading(null);
    }
  };

  const filteredAssessments = assessments.filter(a => {
    const matchesSearch =
      a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (a.description && a.description.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesSearch;
  });

  const getStatusBadge = (status: AssessmentStatus) => {
    switch (status) {
      case "ACTIVE":
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"><Radio className="w-3 h-3 animate-pulse" /> LIVE NOW</span>;
      case "PUBLISHED":
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"><CheckCircle2 className="w-3 h-3" /> PUBLISHED</span>;
      case "SCHEDULED":
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"><Calendar className="w-3 h-3" /> SCHEDULED</span>;
      case "COMPLETED":
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20"><CheckCircle2 className="w-3 h-3" /> COMPLETED</span>;
      case "ARCHIVED":
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20"><Archive className="w-3 h-3" /> ARCHIVED</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border border-zinc-500/20">DRAFT</span>;
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-6">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]">
                <Shield className="w-6 h-6" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight">Assessments & Proctoring Studio</h1>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Authoritative exam sessions, anti-cheating enforcement, candidate monitoring & automated evaluation.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchAssessments}
              className="p-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] transition text-[var(--text-secondary)]"
              title="Refresh assessments"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <Link
              href="/admin/assessments/create"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--accent-primary)] text-white text-sm font-semibold hover:opacity-90 transition shadow-sm"
            >
              <Plus className="w-4 h-4" /> Create Assessment
            </Link>
          </div>
        </div>

        {/* Filters & Search */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative md:col-span-2">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search assessments by title or topic..."
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] transition"
            />
          </div>

          <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
            {["ALL", "DRAFT", "PUBLISHED", "ACTIVE", "COMPLETED"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition whitespace-nowrap ${
                  statusFilter === st
                    ? "bg-[var(--accent-primary)] text-white"
                    : "bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]"
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Assessment Cards Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-48 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] animate-pulse" />
            ))}
          </div>
        ) : filteredAssessments.length === 0 ? (
          <div className="text-center py-16 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl">
            <Shield className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3 opacity-40" />
            <h3 className="text-base font-semibold">No assessments found</h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Get started by creating your first secure proctored assessment for placement screening or campus tests.
            </p>
            <Link
              href="/admin/assessments/create"
              className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-xs font-semibold hover:opacity-90 transition"
            >
              <Plus className="w-3.5 h-3.5" /> Create Assessment
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredAssessments.map((a) => (
              <div
                key={a.id}
                className="flex flex-col justify-between rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-[var(--border-hover)] transition shadow-sm overflow-hidden"
              >
                <div className="p-5 space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-base line-clamp-1 hover:text-[var(--accent-primary)] transition">
                      <Link href={`/admin/assessments/${a.id}/edit`}>{a.title}</Link>
                    </h3>
                    {getStatusBadge(a.status)}
                  </div>

                  {a.description && (
                    <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{a.description}</p>
                  )}

                  <div className="grid grid-cols-2 gap-2 text-xs text-[var(--text-secondary)] pt-2 border-t border-[var(--border-subtle)]">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                      <span>{a.duration_minutes} Mins</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Users className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                      <span>{a.total_questions} Questions</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <BarChart2 className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                      <span>{a.total_marks} Marks ({a.pass_percentage}% Pass)</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5 text-emerald-500" />
                      <span>{a.fullscreen_enforced ? "Strict Proctor" : "Standard"}</span>
                    </div>
                  </div>
                </div>

                {/* Card Action Footer */}
                <div className="p-3 bg-[var(--bg-subtle)]/50 border-t border-[var(--border-subtle)] flex items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-1">
                    {a.status === "DRAFT" && (
                      <button
                        onClick={() => handlePublish(a.id)}
                        disabled={actionLoading === a.id}
                        className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white font-medium transition disabled:opacity-50"
                      >
                        Publish
                      </button>
                    )}
                    {a.status === "ACTIVE" && (
                      <Link
                        href={`/admin/assessments/${a.id}/monitor`}
                        className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white font-medium transition flex items-center gap-1"
                      >
                        <Radio className="w-3 h-3 animate-pulse" /> Live Monitor
                      </Link>
                    )}
                    {a.status === "PUBLISHED" && (
                      <Link
                        href={`/admin/assessments/${a.id}/monitor`}
                        className="px-2.5 py-1 rounded bg-zinc-700 hover:bg-zinc-800 text-white font-medium transition flex items-center gap-1"
                      >
                        <Eye className="w-3 h-3" /> Monitor
                      </Link>
                    )}
                    {(a.status === "ACTIVE" || a.status === "PUBLISHED") && (
                      <button
                        onClick={() => handleClose(a.id)}
                        disabled={actionLoading === a.id}
                        className="px-2.5 py-1 rounded bg-amber-600/10 hover:bg-amber-600/20 text-amber-600 dark:text-amber-400 font-medium transition disabled:opacity-50"
                      >
                        Close
                      </button>
                    )}
                    <Link
                      href={`/admin/assessments/${a.id}/results`}
                      className="px-2.5 py-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)] font-medium transition flex items-center gap-1"
                    >
                      <BarChart2 className="w-3 h-3" /> Results
                    </Link>
                  </div>

                  <div className="flex items-center gap-1">
                    <Link
                      href={`/admin/assessments/${a.id}/edit`}
                      className="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)] transition"
                      title="Edit assessment"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </Link>
                    {a.status === "DRAFT" ? (
                      <button
                        onClick={() => handleDelete(a.id)}
                        disabled={actionLoading === a.id}
                        className="p-1 rounded text-red-500 hover:bg-red-500/10 transition disabled:opacity-50"
                        title="Delete draft"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    ) : (
                      a.status !== "ARCHIVED" && (
                        <button
                          onClick={() => handleArchive(a.id)}
                          disabled={actionLoading === a.id}
                          className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-surface)] transition disabled:opacity-50"
                          title="Archive"
                        >
                          <Archive className="w-3.5 h-3.5" />
                        </button>
                      )
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
