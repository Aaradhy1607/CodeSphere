"use client";

import React, { useState } from "react";
import {
  CheckCircle2, XCircle, AlertTriangle, Clock, Terminal, Zap,
  Loader2, Copy, Check, ShieldAlert, Cpu, Database
} from "lucide-react";
import { CodeRunResult, SubmissionStatusOut } from "@/lib/types";

interface TestResultsProps {
  results: CodeRunResult | null;
  isRunning?: boolean;
  asyncStatus?: SubmissionStatusOut | null;
  isJudgingAsync?: boolean;
}

const VERDICT_DESCRIPTIONS: Record<string, { summary: string; detail: string; color: string; bg: string; border: string }> = {
  "Accepted": {
    summary: "Accepted",
    detail: "All evaluated test cases passed successfully.",
    color: "var(--status-success-text)",
    bg: "var(--status-success-bg)",
    border: "var(--status-success-border)"
  },
  "Wrong Answer": {
    summary: "Wrong Answer",
    detail: "Your program generated output that differs from the expected result.",
    color: "var(--status-error-text)",
    bg: "var(--status-error-bg)",
    border: "var(--status-error-border)"
  },
  "Time Limit Exceeded": {
    summary: "Time Limit Exceeded",
    detail: "Execution exceeded the maximum allowed CPU time. Optimize algorithmic complexity (avoid nested loops / inefficient I/O).",
    color: "var(--status-warning-text)",
    bg: "var(--status-warning-bg)",
    border: "var(--status-warning-border)"
  },
  "Memory Limit Exceeded": {
    summary: "Memory Limit Exceeded",
    detail: "Program exceeded peak heap memory allocation limits. Check for unbounded arrays, recursion, or memory leaks.",
    color: "var(--status-warning-text)",
    bg: "var(--status-warning-bg)",
    border: "var(--status-warning-border)"
  },
  "Runtime Error": {
    summary: "Runtime Error",
    detail: "Program crashed during execution (non-zero exit code, unhandled exception, index out of range, or null pointer).",
    color: "var(--status-error-text)",
    bg: "var(--status-error-bg)",
    border: "var(--status-error-border)"
  },
  "Compilation Error": {
    summary: "Compilation Error",
    detail: "Source code failed to compile. Review syntax, missing headers/imports, or type mismatches below.",
    color: "var(--status-warning-text)",
    bg: "var(--status-warning-bg)",
    border: "var(--status-warning-border)"
  },
  "Output Limit Exceeded": {
    summary: "Output Limit Exceeded",
    detail: "Program generated output larger than the sandbox buffer limit. Check for infinite print loops.",
    color: "var(--status-warning-text)",
    bg: "var(--status-warning-bg)",
    border: "var(--status-warning-border)"
  }
};

const JUDGE_STAGES = ["QUEUED", "COMPILING", "RUNNING", "EVALUATING", "COMPLETED"];

export function TestResults({ results, isRunning, asyncStatus, isJudgingAsync }: TestResultsProps) {
  const [selectedCaseIdx, setSelectedCaseIdx] = useState<number>(0);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopy = (text: string, key: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  // 1. Asynchronous Judging State Stepper
  if (isJudgingAsync) {
    const currentStatus = (asyncStatus?.status || "QUEUED").toUpperCase();
    const currentIdx = JUDGE_STAGES.indexOf(currentStatus);

    return (
      <div
        role="status"
        aria-live="polite"
        className="p-5 text-left rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4 shadow-xs"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-[var(--accent-primary)]" />
            <span className="text-xs font-bold text-[var(--text-primary)]">Evaluating Institutional Test Vectors...</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] font-semibold uppercase">
            Status: {currentStatus}
          </span>
        </div>

        {/* Stepper Progress */}
        <div className="grid grid-cols-5 gap-1.5 pt-1">
          {JUDGE_STAGES.map((stage, idx) => {
            const isFinished = currentIdx > idx || currentStatus === "COMPLETED";
            const isActive = currentStatus === stage;
            return (
              <div key={stage} className="flex flex-col items-center gap-1">
                <div
                  className={`w-full h-1.5 rounded-full transition-all duration-300 ${
                    isFinished
                      ? "bg-emerald-500"
                      : isActive
                      ? "bg-[var(--accent-primary)] animate-pulse"
                      : "bg-[var(--border-subtle)]"
                  }`}
                />
                <span className={`text-[9px] font-mono tracking-wider ${
                  isActive ? "text-[var(--accent-primary)] font-bold" : isFinished ? "text-emerald-500 font-semibold" : "text-[var(--text-muted)]"
                }`}>
                  {stage}
                </span>
              </div>
            );
          })}
        </div>

        <p className="text-[11px] text-[var(--text-secondary)]">
          Code is running in a deterministic, isolated sandbox with strict resource bounds.
        </p>
      </div>
    );
  }

  // 2. Synchronous Run Running State
  if (isRunning) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex flex-col items-center justify-center py-8 text-[var(--text-muted)] bg-[var(--bg-surface)] rounded-lg border border-[var(--border-subtle)] space-y-2 text-center"
      >
        <Loader2 className="w-5 h-5 animate-spin text-[var(--accent-primary)]" />
        <p className="text-xs font-semibold text-[var(--text-primary)]">Executing in Sandbox...</p>
        <p className="text-[11px] text-[var(--text-muted)] font-mono">Running code against visible sample test cases</p>
      </div>
    );
  }

  // 3. Idle / No Result State
  if (!results) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-[var(--text-muted)] bg-[var(--bg-surface)] rounded-lg border border-dashed border-[var(--border-default)] text-center space-y-1.5">
        <Terminal className="w-5 h-5 text-[var(--text-muted)]" />
        <p className="text-xs font-medium text-[var(--text-secondary)]">No Execution Output</p>
        <p className="text-[11px] text-[var(--text-muted)]">Click &quot;Run Code&quot; (Ctrl+Enter) to validate your solution against sample test vectors</p>
      </div>
    );
  }

  // 4. Render Verdict & Diagnostics
  const verdict = results.verdict || "Wrong Answer";
  const verdictMeta = VERDICT_DESCRIPTIONS[verdict] || {
    summary: verdict,
    detail: results.error_message || "Execution completed.",
    color: "var(--text-primary)",
    bg: "var(--bg-subtle)",
    border: "var(--border-subtle)"
  };

  const isAccepted = verdict === "Accepted";
  const cases = results.sample_results || [];
  const activeCase = cases[selectedCaseIdx];

  return (
    <div className="space-y-3 text-left">
      {/* Verdict Banner */}
      <div
        className="p-3.5 rounded-lg border space-y-2 transition-all shadow-xs"
        style={{
          backgroundColor: verdictMeta.bg,
          borderColor: verdictMeta.border
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex items-center gap-2">
            {isAccepted ? (
              <CheckCircle2 className="w-4 h-4 text-[var(--status-success-text)] shrink-0" />
            ) : verdict.includes("Time") ? (
              <Clock className="w-4 h-4 text-[var(--status-warning-text)] shrink-0" />
            ) : verdict.includes("Memory") ? (
              <Database className="w-4 h-4 text-[var(--status-warning-text)] shrink-0" />
            ) : verdict.includes("Compilation") ? (
              <AlertTriangle className="w-4 h-4 text-[var(--status-warning-text)] shrink-0" />
            ) : (
              <XCircle className="w-4 h-4 text-[var(--status-error-text)] shrink-0" />
            )}

            <div className="flex items-center gap-2">
              <span
                className="text-xs font-bold px-2 py-0.5 rounded font-mono tracking-tight"
                style={{
                  color: verdictMeta.color,
                  backgroundColor: "var(--bg-surface)",
                  border: `1px solid ${verdictMeta.border}`
                }}
              >
                {verdict}
              </span>
              {cases.length > 0 && (
                <span className="text-xs font-semibold text-[var(--text-primary)]">
                  {cases.filter((c) => c.passed).length}/{cases.length} Sample Cases Passed
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono text-[var(--text-secondary)]">
            <span className="flex items-center gap-1" title="Execution Time">
              <Clock className="w-3.5 h-3.5 text-[var(--accent-primary)]" />
              {results.execution_time_ms.toFixed(1)} ms
            </span>
            <span className="flex items-center gap-1" title="Memory Used">
              <Zap className="w-3.5 h-3.5 text-[var(--status-info-text)]" />
              {(results.memory_used_kb / 1024).toFixed(2)} MB
            </span>
          </div>
        </div>

        <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
          {verdictMeta.detail}
        </p>
      </div>

      {/* Compiler or Runtime Diagnostic Report */}
      {results.error_message && (
        <div className="p-3.5 rounded-lg bg-[var(--status-error-bg)] border border-[var(--status-error-border)] space-y-1.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-[var(--status-error-text)] flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5" /> Compiler / Runtime Diagnostic Output
            </span>
            <button
              type="button"
              onClick={() => handleCopy(results.error_message || "", "err_diag")}
              className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)] flex items-center gap-1 focus-visible:outline-none"
            >
              {copiedKey === "err_diag" ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
              <span>{copiedKey === "err_diag" ? "Copied" : "Copy"}</span>
            </button>
          </div>
          <pre className="p-2.5 rounded bg-[var(--bg-surface)] font-mono text-[11px] text-[var(--text-primary)] border border-[var(--border-subtle)] overflow-x-auto whitespace-pre-wrap max-h-48">
            {results.error_message}
          </pre>
        </div>
      )}

      {/* Test Cases Tabs & Breakdown */}
      {cases.length > 0 && (
        <div className="space-y-2.5">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1" role="tablist">
            {cases.map((tc, idx) => (
              <button
                key={`tc-pill-${tc.test_case_id ?? (tc as any).id ?? idx}`}
                type="button"
                role="tab"
                aria-selected={selectedCaseIdx === idx}
                onClick={() => setSelectedCaseIdx(idx)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono font-medium border transition-colors whitespace-nowrap focus-visible:outline-none ${
                  selectedCaseIdx === idx
                    ? "bg-[var(--bg-surface)] border-[var(--accent-primary)] text-[var(--text-primary)] font-bold shadow-xs"
                    : "bg-[var(--bg-subtle)] border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                }`}
              >
                {tc.passed ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--status-success-text)]" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 text-[var(--status-error-text)]" />
                )}
                <span>Case {idx + 1}</span>
              </button>
            ))}
          </div>

          {activeCase && (
            <div className="p-3.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3 text-xs">
              <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)] font-mono">
                <span>Sample Case #{selectedCaseIdx + 1} Execution</span>
                <span>{activeCase.time_ms ? `${activeCase.time_ms.toFixed(1)} ms` : ""}</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Your Output */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--text-secondary)] font-semibold text-[11px]">Your Output (stdout):</span>
                    <button
                      type="button"
                      onClick={() => handleCopy(activeCase.output || "", `out_${selectedCaseIdx}`)}
                      className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)] flex items-center gap-1 focus-visible:outline-none"
                    >
                      {copiedKey === `out_${selectedCaseIdx}` ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                  <pre
                    className={`p-2.5 rounded font-mono text-[11px] overflow-x-auto border max-h-36 ${
                      activeCase.passed
                        ? "bg-[var(--status-success-bg)] text-[var(--status-success-text)] border-[var(--status-success-border)]"
                        : "bg-[var(--status-error-bg)] text-[var(--status-error-text)] border-[var(--status-error-border)]"
                    }`}
                  >
                    {activeCase.output !== undefined && activeCase.output !== "" ? activeCase.output : "(no standard output)"}
                  </pre>
                </div>

                {/* Expected Output */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--text-secondary)] font-semibold text-[11px]">Expected Output:</span>
                    <button
                      type="button"
                      onClick={() => handleCopy(activeCase.expected || results.expected_output || "", `exp_${selectedCaseIdx}`)}
                      className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)] flex items-center gap-1 focus-visible:outline-none"
                    >
                      {copiedKey === `exp_${selectedCaseIdx}` ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                  <pre className="p-2.5 rounded bg-[var(--bg-subtle)] font-mono text-[var(--accent-text)] text-[11px] overflow-x-auto border border-[var(--border-subtle)] max-h-36">
                    {activeCase.expected || results.expected_output || "(expected output)"}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Single Custom Execution Output (if no sample results array) */}
      {cases.length === 0 && results.output !== undefined && (
        <div className="p-3.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-[var(--text-secondary)] text-[11px]">Standard Output (stdout):</span>
            <button
              type="button"
              onClick={() => handleCopy(results.output, "single_out")}
              className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)] flex items-center gap-1 focus-visible:outline-none"
            >
              {copiedKey === "single_out" ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
              <span>{copiedKey === "single_out" ? "Copied" : "Copy"}</span>
            </button>
          </div>
          <pre className="p-2.5 rounded bg-[var(--bg-subtle)] font-mono text-[11px] text-[var(--text-primary)] border border-[var(--border-subtle)] overflow-x-auto max-h-40">
            {results.output || "(no output produced)"}
          </pre>
        </div>
      )}
    </div>
  );
}

