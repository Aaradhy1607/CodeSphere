"use client";

import React, { useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Clock, Terminal, Zap, Loader2 } from "lucide-react";
import { CodeRunResult } from "@/lib/types";

interface TestResultsProps {
  results: CodeRunResult | null;
  isRunning?: boolean;
}

export function TestResults({ results, isRunning }: TestResultsProps) {
  const [selectedCaseIdx, setSelectedCaseIdx] = useState<number>(0);

  if (isRunning) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex flex-col items-center justify-center py-10 text-[var(--text-muted)] bg-[var(--bg-subtle)] rounded-md border border-[var(--border-subtle)] space-y-2"
      >
        <Loader2 className="w-5 h-5 animate-spin text-[var(--accent-primary)]" />
        <p className="text-xs font-semibold text-[var(--text-primary)]">Executing sandbox evaluation...</p>
        <p className="text-[11px] text-[var(--text-muted)] font-mono">Running code against validation test vectors</p>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-[var(--text-muted)] bg-[var(--bg-subtle)]/40 rounded-md border border-dashed border-[var(--border-default)] text-center space-y-1.5">
        <Terminal className="w-5 h-5 text-[var(--text-muted)]" />
        <p className="text-xs text-[var(--text-muted)] font-medium">Click &quot;Run Code&quot; to test your solution against visible test cases</p>
      </div>
    );
  }

  const isAccepted = results.verdict === "Accepted";
  const isCE = results.verdict === "Compilation Error";
  const isTLE = results.verdict === "Time Limit Exceeded";

  const verdictStyles =
    isAccepted ? { badge: "text-[var(--status-success-text)] bg-[var(--status-success-bg)] border-[var(--status-success-border)]", icon: <CheckCircle2 className="w-4 h-4 text-[var(--status-success-text)]" /> } :
    isCE ? { badge: "text-[var(--status-warning-text)] bg-[var(--status-warning-bg)] border-[var(--status-warning-border)]", icon: <AlertTriangle className="w-4 h-4 text-[var(--status-warning-text)]" /> } :
    isTLE ? { badge: "text-[var(--status-warning-text)] bg-[var(--status-warning-bg)] border-[var(--status-warning-border)]", icon: <Clock className="w-4 h-4 text-[var(--status-warning-text)]" /> } :
    { badge: "text-[var(--status-error-text)] bg-[var(--status-error-bg)] border-[var(--status-error-border)]", icon: <XCircle className="w-4 h-4 text-[var(--status-error-text)]" /> };

  const cases = results.sample_results || [];
  const activeCase = cases[selectedCaseIdx];

  return (
    <div className="space-y-3 text-left">
      {/* Verdict Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-md bg-[var(--bg-subtle)] border border-[var(--border-subtle)]">
        <div className="flex items-center gap-2.5">
          {verdictStyles.icon}
          <div className="flex items-center gap-2">
            <span className={`text-xs font-bold px-2 py-0.5 rounded border ${verdictStyles.badge}`}>
              {results.verdict}
            </span>
            {cases.length > 0 && (
              <span className="text-xs text-[var(--text-muted)] font-medium">
                {cases.filter((c) => c.passed).length} of {cases.length} sample cases passed
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono text-[var(--text-muted)]">
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-[var(--accent-primary)]" />
            {results.execution_time_ms.toFixed(1)} ms
          </span>
          <span className="flex items-center gap-1">
            <Zap className="w-3.5 h-3.5 text-[var(--status-info-text)]" />
            {(results.memory_used_kb / 1024).toFixed(1)} MB
          </span>
        </div>
      </div>

      {/* Error Output Detail */}
      {results.error_message && (
        <div className="p-3 rounded-md bg-[var(--status-error-bg)] border border-[var(--status-error-border)] text-xs space-y-1">
          <p className="font-bold text-[var(--status-error-text)]">Compiler / Runtime Diagnostic:</p>
          <pre className="font-mono text-[var(--text-primary)] bg-[var(--bg-surface)] p-2.5 rounded border border-[var(--border-subtle)] overflow-x-auto whitespace-pre-wrap text-[11px]">
            {results.error_message}
          </pre>
        </div>
      )}

      {/* Test Cases Tabs */}
      {cases.length > 0 && (
        <div className="space-y-2.5">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1" role="tablist">
            {cases.map((tc, idx) => (
              <button
                key={`tc-result-${tc.test_case_id ?? (tc as any).id ?? idx}`}
                type="button"
                role="tab"
                aria-selected={selectedCaseIdx === idx}
                onClick={() => setSelectedCaseIdx(idx)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium border transition-colors whitespace-nowrap focus-visible:outline-none ${
                  selectedCaseIdx === idx
                    ? "bg-[var(--bg-surface)] border-[var(--border-focus)] text-[var(--text-primary)] font-semibold shadow-xs"
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
            <div className="p-3.5 rounded-md bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-2.5 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <p className="text-[var(--text-muted)] font-semibold text-[11px]">Your Output:</p>
                  <pre
                    className={`p-2.5 rounded font-mono text-[11px] overflow-x-auto border ${
                      activeCase.passed
                        ? "bg-[var(--bg-surface)] text-[var(--status-success-text)] border-[var(--status-success-border)]"
                        : "bg-[var(--status-error-bg)] text-[var(--status-error-text)] border-[var(--status-error-border)]"
                    }`}
                  >
                    {activeCase.output || "(empty output)"}
                  </pre>
                </div>

                <div className="space-y-1">
                  <p className="text-[var(--text-muted)] font-semibold text-[11px]">Expected Output:</p>
                  <pre className="p-2.5 rounded bg-[var(--bg-surface)] font-mono text-[var(--accent-text)] text-[11px] overflow-x-auto border border-[var(--border-subtle)]">
                    {activeCase.expected || results.expected_output || "(expected output)"}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
