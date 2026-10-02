"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AssessmentResultDetail, Assessment } from "@/lib/types";
import {
  BarChart2, ArrowLeft, RefreshCw, Trophy, CheckCircle2,
  XCircle, Clock, Shield, Search, Eye, Download, Award
} from "lucide-react";

export default function AssessmentResultsPage() {
  const params = useParams();
  const assessmentId = Number(params?.id);

  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [results, setResults] = useState<AssessmentResultDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Selected Result for deep breakdown modal
  const [selectedResult, setSelectedResult] = useState<AssessmentResultDetail | null>(null);

  const fetchResults = async () => {
    setLoading(true);
    setError(null);
    try {
      const [aData, rData] = await Promise.all([
        api.assessments.get(assessmentId),
        api.assessments.getAssessmentResults(assessmentId)
      ]);
      setAssessment(aData);
      setResults(rData);
    } catch (err: any) {
      setError(err.message || "Failed to load assessment results");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (assessmentId) {
      fetchResults();
    }
  }, [assessmentId]);

  const totalCandidates = results.length;
  const passedCount = results.filter(r => r.passed).length;
  const passRate = totalCandidates > 0 ? ((passedCount / totalCandidates) * 100).toFixed(1) : "0";
  const avgScore = totalCandidates > 0 ? (results.reduce((acc, r) => acc + r.score_obtained, 0) / totalCandidates).toFixed(1) : "0";
  const topScore = totalCandidates > 0 ? Math.max(...results.map(r => r.score_obtained)).toFixed(1) : "0";
  const avgIntegrity = totalCandidates > 0 ? (results.reduce((acc, r) => acc + r.integrity_score, 0) / totalCandidates).toFixed(1) : "0";

  const filteredResults = results.filter(r => {
    const name = r.student_name || "";
    const enroll = r.enrollment_no || "";
    const branch = r.branch || "";
    const q = searchQuery.toLowerCase();
    return name.toLowerCase().includes(q) || enroll.toLowerCase().includes(q) || branch.toLowerCase().includes(q);
  });

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <Link href="/admin/assessments" className="hover:text-[var(--text-primary)] flex items-center gap-1 transition">
            <ArrowLeft className="w-4 h-4" /> Assessments
          </Link>
          <span>/</span>
          <span className="text-[var(--text-primary)] font-medium">Cohort Results: {assessment?.title}</span>
        </div>

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Assessment Evaluation & Performance Report</h1>
            <p className="text-sm text-[var(--text-secondary)] mt-0.5">
              Automated scoring analytics, cohort percentile rankings & anti-cheat verification.
            </p>
          </div>

          <button
            onClick={fetchResults}
            className="p-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)] transition self-start md:self-auto"
            title="Refresh results"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-[var(--text-secondary)]">Total Graded</span>
            <p className="text-2xl font-bold">{totalCandidates}</p>
          </div>
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-emerald-500 font-medium">Pass Rate</span>
            <p className="text-2xl font-bold text-emerald-500">{passRate}%</p>
          </div>
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-blue-500 font-medium">Average Score</span>
            <p className="text-2xl font-bold text-blue-500">{avgScore} <span className="text-xs text-[var(--text-muted)]">/ {assessment?.total_marks}</span></p>
          </div>
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-amber-500 font-medium flex items-center gap-1">
              <Trophy className="w-3.5 h-3.5" /> Top Score
            </span>
            <p className="text-2xl font-bold text-amber-500">{topScore}</p>
          </div>
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
              <Shield className="w-3.5 h-3.5 text-emerald-500" /> Avg Integrity
            </span>
            <p className="text-2xl font-bold">{avgIntegrity}%</p>
          </div>
        </div>

        {/* Search & Candidates Leaderboard */}
        <div className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search candidate name, enrollment number, branch..."
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-sm focus:outline-none"
            />
          </div>

          <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] text-[var(--text-secondary)] font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Rank</th>
                  <th className="px-4 py-3">Candidate</th>
                  <th className="px-4 py-3">Score Obtained</th>
                  <th className="px-4 py-3">Percentage</th>
                  <th className="px-4 py-3">Percentile</th>
                  <th className="px-4 py-3">Result</th>
                  <th className="px-4 py-3">Time Taken</th>
                  <th className="px-4 py-3">Integrity</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {filteredResults.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-8 text-center text-[var(--text-secondary)]">
                      {loading ? "Loading results..." : "No candidate results recorded yet."}
                    </td>
                  </tr>
                ) : (
                  filteredResults.map((r, idx) => (
                    <tr key={r.id} className="hover:bg-[var(--bg-subtle)]/50 transition">
                      <td className="px-4 py-3">
                        <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${
                          idx === 0 ? 'bg-amber-500 text-black' :
                          idx === 1 ? 'bg-slate-300 text-black' :
                          idx === 2 ? 'bg-amber-700 text-white' :
                          'bg-[var(--bg-subtle)] text-[var(--text-secondary)]'
                        }`}>
                          {idx + 1}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-semibold text-sm">{r.student_name || `Candidate #${r.user_id}`}</p>
                          <p className="text-[10px] text-[var(--text-muted)]">{r.enrollment_no || "—"} • {r.branch || "—"}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono font-bold text-sm">
                        {r.score_obtained} <span className="text-[10px] text-[var(--text-muted)] font-normal">/ {r.total_possible_score}</span>
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold">
                        {r.percentage.toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 font-mono">
                        {r.percentile !== undefined && r.percentile !== null ? `${r.percentile.toFixed(1)}%ile` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {r.passed ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                            <CheckCircle2 className="w-3 h-3" /> PASS
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
                            <XCircle className="w-3 h-3" /> FAIL
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-[11px] text-[var(--text-secondary)]">
                        {formatDuration(r.time_taken_seconds)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-mono font-semibold ${r.integrity_score >= 85 ? 'text-emerald-500' : r.integrity_score >= 60 ? 'text-amber-500' : 'text-red-500'}`}>
                          {r.integrity_score}%
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setSelectedResult(r)}
                          className="px-2.5 py-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition text-xs font-semibold inline-flex items-center gap-1"
                        >
                          <Eye className="w-3.5 h-3.5" /> Breakdown
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Detailed Breakdown Drawer / Modal */}
        {selectedResult && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl max-w-2xl w-full max-h-[85vh] flex flex-col p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
                <div>
                  <h3 className="font-bold text-base">Candidate Evaluation Breakdown</h3>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {selectedResult.student_name} • Score: {selectedResult.score_obtained} / {selectedResult.total_possible_score} ({selectedResult.percentage.toFixed(1)}%)
                  </p>
                </div>
                <button
                  onClick={() => setSelectedResult(null)}
                  className="text-xs px-2.5 py-1 rounded border border-[var(--border-subtle)] hover:bg-[var(--bg-subtle)]"
                >
                  Close
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-4 pr-1 text-xs">
                {/* Section & Topic Breakdown */}
                {selectedResult.evaluation_breakdown?.section_breakdown && (
                  <div>
                    <h4 className="font-bold text-xs uppercase tracking-wider text-[var(--text-secondary)] mb-2">Section Performance</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(selectedResult.evaluation_breakdown.section_breakdown).map(([sec, val]: [string, any]) => (
                        <div key={sec} className="p-2.5 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)] flex items-center justify-between">
                          <span className="font-semibold">{sec}</span>
                          <span className="font-mono font-bold text-[var(--accent-primary)]">{val.score} / {val.total}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Question List Breakdown */}
                <div>
                  <h4 className="font-bold text-xs uppercase tracking-wider text-[var(--text-secondary)] mb-2">Question Results</h4>
                  <div className="space-y-2">
                    {selectedResult.evaluation_breakdown?.question_results?.map((q, qIdx) => (
                      <div
                        key={q.question_id || qIdx}
                        className="p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)] space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold">{q.title || `Question #${q.question_id}`}</span>
                          <span className={`font-mono font-bold ${q.marks_awarded > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                            {q.marks_awarded} / {q.max_marks} Marks
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-[var(--text-muted)] font-mono">
                          <span>{q.question_type}</span>
                          {q.test_cases_passed !== undefined && (
                            <>
                              <span>•</span>
                              <span>Test Cases: {q.test_cases_passed} / {q.total_test_cases}</span>
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
