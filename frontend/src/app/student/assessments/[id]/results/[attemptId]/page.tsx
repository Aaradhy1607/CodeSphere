"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AssessmentResultDetail, Assessment } from "@/lib/types";
import {
  Award, CheckCircle2, XCircle, Clock, Shield,
  ArrowLeft, RefreshCw, Layers, BookOpen, AlertTriangle, ChevronDown, ChevronUp
} from "lucide-react";

export default function StudentAssessmentResultPage() {
  const params = useParams();
  const assessmentId = Number(params?.id);
  const attemptId = Number(params?.attemptId);

  const [result, setResult] = useState<AssessmentResultDetail | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedQuestions, setExpandedQuestions] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (!attemptId) return;

    const fetchResult = async () => {
      setLoading(true);
      setError(null);
      try {
        const [rData, aData] = await Promise.all([
          api.assessments.getResult(attemptId),
          api.assessments.get(assessmentId)
        ]);
        setResult(rData);
        setAssessment(aData);
      } catch (err: any) {
        setError(err.message || "Failed to load examination result.");
      } finally {
        setLoading(false);
      }
    };

    fetchResult();
  }, [attemptId, assessmentId]);

  const toggleQuestion = (qId: number) => {
    setExpandedQuestions(prev => ({ ...prev, [qId]: !prev[qId] }));
  };

  const formatDuration = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s}s`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center p-8">
        <RefreshCw className="w-6 h-6 animate-spin text-[var(--accent-primary)]" />
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl p-6 text-center space-y-4 shadow-lg">
          <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto" />
          <h2 className="text-lg font-bold">Result Pending or Unavailable</h2>
          <p className="text-xs text-[var(--text-secondary)]">{error || "The result for this attempt is still processing or has been restricted by the administrator."}</p>
          <Link
            href="/student/assessments"
            className="inline-block px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-xs font-semibold"
          >
            Back to Assessments
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-6 lg:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <Link href="/student/assessments" className="hover:text-[var(--text-primary)] flex items-center gap-1 transition">
            <ArrowLeft className="w-4 h-4" /> My Assessments
          </Link>
          <span>/</span>
          <span className="text-[var(--text-primary)] font-medium">Result & Score Report</span>
        </div>

        {/* Score & Status Hero Banner */}
        <div className={`p-6 sm:p-8 rounded-2xl border text-center space-y-4 shadow-lg ${
          result.passed
            ? 'bg-emerald-500/10 border-emerald-500/30'
            : 'bg-red-500/10 border-red-500/30'
        }`}>
          <div className="inline-flex p-3 rounded-full bg-[var(--bg-surface)] shadow-sm">
            {result.passed ? (
              <CheckCircle2 className="w-8 h-8 text-emerald-500" />
            ) : (
              <XCircle className="w-8 h-8 text-red-500" />
            )}
          </div>

          <div>
            <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider mb-2 ${
              result.passed ? 'bg-emerald-500 text-white' : 'bg-red-500 text-white'
            }`}>
              {result.passed ? "PASSED ASSESSMENT" : "NEEDS IMPROVEMENT"}
            </span>
            <h1 className="text-3xl font-bold tracking-tight">{assessment?.title || "Assessment"}</h1>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Submitted on {new Date(result.submitted_at).toLocaleString()}
            </p>
          </div>

          <div className="flex items-center justify-center gap-6 pt-2">
            <div>
              <span className="text-xs text-[var(--text-secondary)] block">Score Obtained</span>
              <span className="text-2xl font-bold font-mono text-[var(--text-primary)]">
                {result.score_obtained} <span className="text-sm font-normal text-[var(--text-muted)]">/ {result.total_possible_score}</span>
              </span>
            </div>
            <div className="h-8 w-px bg-[var(--border-subtle)]" />
            <div>
              <span className="text-xs text-[var(--text-secondary)] block">Percentage</span>
              <span className="text-2xl font-bold font-mono text-[var(--accent-primary)]">
                {result.percentage.toFixed(1)}%
              </span>
            </div>
            {result.percentile !== undefined && result.percentile !== null && (
              <>
                <div className="h-8 w-px bg-[var(--border-subtle)]" />
                <div>
                  <span className="text-xs text-[var(--text-secondary)] block">Cohort Percentile</span>
                  <span className="text-2xl font-bold font-mono text-purple-500">
                    {result.percentile.toFixed(1)}%ile
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Performance Metrics Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-[var(--text-muted)]" /> Time Spent
            </span>
            <p className="text-lg font-bold font-mono">{formatDuration(result.time_taken_seconds)}</p>
          </div>
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
              <Shield className="w-3.5 h-3.5 text-emerald-500" /> Integrity Score
            </span>
            <p className="text-lg font-bold font-mono text-emerald-500">{result.integrity_score}%</p>
          </div>
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
              <BookOpen className="w-3.5 h-3.5 text-[var(--text-muted)]" /> Questions
            </span>
            <p className="text-lg font-bold font-mono">{result.evaluation_breakdown?.questions_graded || "—"}</p>
          </div>
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
            <span className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
              <Award className="w-3.5 h-3.5 text-amber-500" /> Pass Threshold
            </span>
            <p className="text-lg font-bold font-mono">{assessment?.pass_percentage || 60}%</p>
          </div>
        </div>

        {/* Section Breakdown */}
        {result.evaluation_breakdown?.section_breakdown && (
          <div className="p-6 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4 shadow-sm">
            <h3 className="font-bold text-sm uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-2">
              <Layers className="w-4 h-4 text-[var(--accent-primary)]" /> Section-Wise Breakdown
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {Object.entries(result.evaluation_breakdown.section_breakdown).map(([sec, val]: [string, any]) => (
                <div key={sec} className="p-3.5 rounded-xl bg-[var(--bg-base)] border border-[var(--border-subtle)] flex items-center justify-between">
                  <span className="font-semibold text-xs">{sec}</span>
                  <span className="font-mono font-bold text-xs text-[var(--accent-primary)]">
                    {val.score} / {val.total} Marks ({val.total > 0 ? ((val.score / val.total) * 100).toFixed(0) : 0}%)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Detailed Question Review (If Allowed) */}
        {assessment?.allow_review && result.evaluation_breakdown?.question_results && (
          <div className="space-y-4">
            <h3 className="font-bold text-sm uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-[var(--accent-primary)]" /> Detailed Solution & Question Review
            </h3>

            <div className="space-y-3">
              {result.evaluation_breakdown.question_results.map((q, idx) => {
                const isExpanded = expandedQuestions[q.question_id];
                const isFullMarks = q.marks_awarded === q.max_marks;
                const isPartial = q.marks_awarded > 0 && q.marks_awarded < q.max_marks;

                return (
                  <div
                    key={q.question_id || idx}
                    className="rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden shadow-sm transition"
                  >
                    <div
                      onClick={() => toggleQuestion(q.question_id)}
                      className="p-4 flex items-center justify-between cursor-pointer hover:bg-[var(--bg-subtle)]/50 transition gap-4"
                    >
                      <div className="flex items-center gap-3">
                        <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
                          isFullMarks ? 'bg-emerald-500 text-white' : isPartial ? 'bg-amber-500 text-white' : 'bg-red-500 text-white'
                        }`}>
                          {idx + 1}
                        </span>
                        <div>
                          <h4 className="font-semibold text-xs sm:text-sm text-[var(--text-primary)] line-clamp-1">
                            {q.title || `Question #${q.question_id}`}
                          </h4>
                          <span className="text-[10px] text-[var(--text-muted)] font-mono">{q.question_type}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className={`font-mono font-bold text-xs ${
                          isFullMarks ? 'text-emerald-500' : isPartial ? 'text-amber-500' : 'text-red-500'
                        }`}>
                          {q.marks_awarded} / {q.max_marks} Marks
                        </span>
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-[var(--text-muted)]" /> : <ChevronDown className="w-4 h-4 text-[var(--text-muted)]" />}
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="p-4 bg-[var(--bg-base)] border-t border-[var(--border-subtle)] space-y-3 text-xs">
                        {q.user_answer && (
                          <div>
                            <span className="font-bold text-[var(--text-secondary)] block mb-1">Your Submission:</span>
                            <pre className="p-2.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] font-mono text-[11px] overflow-x-auto whitespace-pre-wrap">
                              {typeof q.user_answer === 'object' ? JSON.stringify(q.user_answer, null, 2) : String(q.user_answer)}
                            </pre>
                          </div>
                        )}

                        {q.correct_answer && (
                          <div>
                            <span className="font-bold text-emerald-500 block mb-1">Correct Answer / Key:</span>
                            <pre className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap">
                              {typeof q.correct_answer === 'object' ? JSON.stringify(q.correct_answer, null, 2) : String(q.correct_answer)}
                            </pre>
                          </div>
                        )}

                        {q.explanation && (
                          <div>
                            <span className="font-bold text-[var(--text-secondary)] block mb-1">Explanation:</span>
                            <p className="text-[var(--text-secondary)] leading-relaxed">{q.explanation}</p>
                          </div>
                        )}

                        {q.test_cases_passed !== undefined && (
                          <div className="flex items-center gap-2 font-mono text-[11px] text-[var(--text-muted)] pt-1">
                            <span>Test Cases: {q.test_cases_passed} / {q.total_test_cases} passed</span>
                            {q.error_message && <span className="text-red-500">({q.error_message})</span>}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
