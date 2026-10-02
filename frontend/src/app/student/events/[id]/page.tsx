"use client";

import React, { useEffect, useState, use, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event, CodeRunResult, FinalSubmitResult, Submission, SubmissionStatusOut, StudentSubmissionHistoryOut } from "@/lib/types";
import { CodeEditor } from "@/components/CodeEditor";
import { CountdownTimer } from "@/components/CountdownTimer";
import { TestResults } from "@/components/TestResults";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { LoadingState } from "@/components/ui/LoadingState";
import { Alert } from "@/components/ui/Alert";
import { FormattedQuestionText } from "@/components/FormattedQuestionText";
import { useToast } from "@/components/ui/Toast";
import confetti from "canvas-confetti";
import {
  Play, Send, ChevronLeft, Terminal, History, Copy, Check, CheckCircle2, Clock, Zap, AlertTriangle
} from "lucide-react";

export default function AssessmentArenaPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const eventId = parseInt(resolvedParams.id);
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const toast = useToast();

  const [event, setEvent] = useState<Event | null>(null);
  const [activeQuestionIdx, setActiveQuestionIdx] = useState<number>(0);
  const [language, setLanguage] = useState<string>("python");
  const [code, setCode] = useState<string>("");
  const [customInput, setCustomInput] = useState<string>("");
  const [activeBottomTab, setActiveBottomTab] = useState<"results" | "testcases" | "custom_input" | "history">("results");

  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [runResults, setRunResults] = useState<CodeRunResult | null>(null);

  // Async Judging & Submission State
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isJudgingAsync, setIsJudgingAsync] = useState<boolean>(false);
  const [asyncStatus, setAsyncStatus] = useState<SubmissionStatusOut | null>(null);
  const [existingSubmission, setExistingSubmission] = useState<Submission | null>(null);

  // Submission History Tab State
  const [submissionHistory, setSubmissionHistory] = useState<StudentSubmissionHistoryOut | null>(null);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);

  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<"problem" | "editor" | "console">("editor");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleCopy = (text: string, key: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    }
  };

  const fetchHistory = useCallback(async (qId: number) => {
    setLoadingHistory(true);
    try {
      const hist = await api.execute.getHistory(qId);
      setSubmissionHistory(hist);
    } catch {
      setSubmissionHistory(null);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  // Load Event and Questions
  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
      return;
    }
    if (user && eventId) {
      setLoading(true);
      setError(null);
      api.events.get(eventId)
        .then((evt) => {
          setEvent(evt);
          if (evt.questions && evt.questions.length > 0) {
            loadDraftOrTemplate(evt.questions[0].id, "python");
            checkSubmissionStatus(evt.id, evt.questions[0].id);
            fetchHistory(evt.questions[0].id);
          }
        })
        .catch((err) => {
          console.error(err);
          setError(err.message || "Failed to load assessment arena.");
        })
        .finally(() => setLoading(false));
    }
  }, [user, isLoading, eventId, router, fetchHistory]);

  // Load local draft or default template
  const loadDraftOrTemplate = (questionId: number, lang: string) => {
    const draftKey = `draft_event_${eventId}_q_${questionId}_lang_${lang}`;
    const savedDraft = typeof localStorage !== "undefined" ? localStorage.getItem(draftKey) : null;
    if (savedDraft) {
      setCode(savedDraft);
    } else {
      if (lang === "python") {
        setCode("import sys\n\ndef solve():\n    # Read input from stdin\n    input_data = sys.stdin.read().split()\n    if not input_data:\n        return\n    \n    # Write your logic here\n    \nif __name__ == '__main__':\n    solve()\n");
      } else if (lang === "cpp") {
        setCode("#include <iostream>\n#include <vector>\n#include <string>\n#include <algorithm>\nusing namespace std;\n\nint main() {\n    ios_base::sync_with_stdio(false);\n    cin.tie(NULL);\n    // Write your logic here\n    return 0;\n}\n");
      } else if (lang === "c") {
        setCode("#include <stdio.h>\n#include <stdlib.h>\n\nint main() {\n    // Write your logic here\n    return 0;\n}\n");
      } else if (lang === "java") {
        setCode("import java.util.Scanner;\n\npublic class Solution {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        // Write your logic here\n    }\n}\n");
      } else if (lang === "javascript" || lang === "js") {
        setCode("const fs = require('fs');\n\nfunction solve() {\n    const input = fs.readFileSync(0, 'utf-8').trim().split(/\\s+/);\n    if (!input || input.length === 0 || input[0] === '') return;\n    // Write your logic here\n}\n\nsolve();\n");
      }
    }
  };

  const handleCodeChange = (newCode: string) => {
    setCode(newCode);
    const activeQ = event?.questions?.[activeQuestionIdx];
    if (activeQ && typeof localStorage !== "undefined") {
      const draftKey = `draft_event_${eventId}_q_${activeQ.id}_lang_${language}`;
      localStorage.setItem(draftKey, newCode);
    }
  };

  const handleLanguageChange = (newLang: string) => {
    const activeQ = event?.questions?.[activeQuestionIdx];
    if (activeQ && typeof localStorage !== "undefined") {
      localStorage.setItem(`draft_event_${eventId}_q_${activeQ.id}_lang_${language}`, code);
    }
    setLanguage(newLang);
    if (activeQ) {
      loadDraftOrTemplate(activeQ.id, newLang);
    }
  };

  const checkSubmissionStatus = async (evtId: number, qId: number) => {
    try {
      const sub = await api.execute.getMySubmission(evtId, qId);
      setExistingSubmission(sub);
      if (sub) {
        setCode(sub.code);
        setLanguage(sub.language);
      }
    } catch (err) {
      console.error("Submission check error:", err);
    }
  };

  const switchQuestion = (idx: number) => {
    if (!event?.questions || idx < 0 || idx >= event.questions.length) return;
    const currentQ = event.questions[activeQuestionIdx];
    if (currentQ && typeof localStorage !== "undefined") {
      localStorage.setItem(`draft_event_${eventId}_q_${currentQ.id}_lang_${language}`, code);
    }

    setActiveQuestionIdx(idx);
    setRunResults(null);
    setAsyncStatus(null);
    const targetQ = event.questions[idx];
    if (targetQ) {
      loadDraftOrTemplate(targetQ.id, language);
      checkSubmissionStatus(eventId, targetQ.id);
      fetchHistory(targetQ.id);
    }
  };

  const handleRunCode = async () => {
    const activeQ = event?.questions?.[activeQuestionIdx];
    if (!activeQ || isRunning || isJudgingAsync) return;

    setIsRunning(true);
    setRunResults(null);
    setActiveBottomTab("results");
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setMobileTab("console");
    }

    try {
      const res = await api.execute.run(
        activeQ.id,
        code,
        language,
        customInput.trim() !== "" ? customInput : undefined
      );
      setRunResults(res);
      if (res.passed) {
        toast.success(`Sample test cases passed (${res.execution_time_ms.toFixed(1)}ms)`);
      } else {
        toast.warning(`Sample verdict: ${res.verdict}`);
      }
    } catch (err: any) {
      setRunResults({
        verdict: "Compilation Error",
        passed: false,
        execution_time_ms: 0,
        memory_used_kb: 0,
        output: "",
        error_message: err.message || "Execution error in judge sandbox.",
        sample_results: []
      });
      toast.error(err.message || "Compilation / runtime error");
    } finally {
      setIsRunning(false);
    }
  };

  const handleFinalSubmit = async () => {
    const activeQ = event?.questions?.[activeQuestionIdx];
    if (!activeQ || isJudgingAsync || isSubmitting) return;

    setIsSubmitting(true);
    setIsSubmitModalOpen(false);
    setIsJudgingAsync(true);
    setActiveBottomTab("results");
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setMobileTab("console");
    }

    try {
      const asyncRes = await api.execute.submitAsync(eventId, activeQ.id, code, language);
      setAsyncStatus({
        submission_id: asyncRes.submission_id,
        status: asyncRes.status,
        passed_test_cases: 0,
        total_test_cases: activeQ.test_cases_count || 0,
        score: 0,
        execution_time_ms: 0,
        memory_used_kb: 0,
        submitted_at: asyncRes.enqueued_at,
        is_final: true
      });

      // Poll status
      let attempts = 0;
      const maxAttempts = 25;
      const pollInterval = 600;

      const poll = async () => {
        attempts++;
        try {
          const statusRes = await api.execute.getStatus(asyncRes.submission_id);
          setAsyncStatus(statusRes);

          if (statusRes.status === "COMPLETED" || statusRes.status === "FAILED") {
            setIsJudgingAsync(false);
            setIsSubmitting(false);
            checkSubmissionStatus(eventId, activeQ.id);
            fetchHistory(activeQ.id);

            if (statusRes.verdict === "Accepted") {
              confetti({
                particleCount: 80,
                spread: 70,
                origin: { y: 0.6 }
              });
              toast.success(`Verdict Accepted! Passed ${statusRes.passed_test_cases}/${statusRes.total_test_cases} test cases (+${statusRes.score} pts)`);
            } else {
              toast.warning(`Verdict: ${statusRes.verdict} (${statusRes.passed_test_cases}/${statusRes.total_test_cases} passed)`);
            }

            setRunResults({
              verdict: statusRes.verdict || "Wrong Answer",
              passed: statusRes.verdict === "Accepted",
              execution_time_ms: statusRes.execution_time_ms,
              memory_used_kb: statusRes.memory_used_kb,
              output: "",
              error_message: statusRes.error_message,
              sample_results: (statusRes.test_case_results || []).filter(tc => !tc.is_hidden).map(tc => ({
                is_hidden: false,
                passed: tc.passed,
                verdict: tc.verdict || "",
                time_ms: tc.time_ms,
                output: tc.output || "",
                expected: tc.expected || "",
                error: tc.error
              }))
            });
            return;
          }

          if (attempts < maxAttempts) {
            setTimeout(poll, pollInterval);
          } else {
            setIsJudgingAsync(false);
            setIsSubmitting(false);
            toast.warning("Judging is taking slightly longer. Check your submission history shortly.");
          }
        } catch (err: any) {
          if (attempts < maxAttempts) {
            setTimeout(poll, pollInterval);
          } else {
            setIsJudgingAsync(false);
            setIsSubmitting(false);
            toast.error(err.message || "Failed to retrieve judging status");
          }
        }
      };

      setTimeout(poll, 400);
    } catch (err: any) {
      setIsJudgingAsync(false);
      setIsSubmitting(false);
      toast.error(err.message || "Final submission failed. Please try again.");
    }
  };

  if (isLoading || loading) {
    return <LoadingState message="Connecting to Sandboxed Assessment Arena..." className="min-h-[70vh]" />;
  }

  if (error || !event) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Alert variant="error" title="Assessment Arena Error">
          {error || "Assessment not found or closed."}
        </Alert>
      </div>
    );
  }

  const questions = event.questions || [];
  const activeQ = questions[activeQuestionIdx];

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] sm:h-[calc(100vh-4rem)] overflow-hidden" style={{ backgroundColor: "var(--bg-canvas)" }}>
      
      {/* Top Arena Header Bar */}
      <div className="flex items-center justify-between px-3 sm:px-5 py-2 shrink-0 text-xs" style={{ backgroundColor: "var(--bg-surface)", borderBottom: "1px solid var(--border-subtle)" }}>
        {/* Left: Back & Title */}
        <div className="flex items-center gap-3">
          <Link href="/student/events">
            <Button variant="ghost" size="icon" aria-label="Back to assessments list">
              <ChevronLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div className="truncate max-w-[200px] sm:max-w-xs md:max-w-md">
            <h1 className="font-bold text-xs sm:text-sm truncate" style={{ color: "var(--text-primary)" }}>{event.title}</h1>
            <p className="text-[10px] font-mono hidden sm:block" style={{ color: "var(--text-muted)" }}>
              Target: {event.target_branch} • Question {activeQuestionIdx + 1} of {questions.length}
            </p>
          </div>
        </div>

        {/* Center: Problem Navigation Selector */}
        <div className="hidden md:flex items-center gap-1.5 p-1 rounded-lg" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
          {questions.map((q, idx) => {
            const isCurrent = activeQuestionIdx === idx;
            return (
              <button
                key={q.id}
                type="button"
                onClick={() => switchQuestion(idx)}
                className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold transition"
                style={{
                  backgroundColor: isCurrent ? "var(--accent-primary)" : "transparent",
                  color: isCurrent ? "#ffffff" : "var(--text-muted)"
                }}
              >
                P{idx + 1}
              </button>
            );
          })}
        </div>

        {/* Right: Timer & Execution Actions */}
        <div className="flex items-center gap-2">
          <CountdownTimer endTime={event.end_time} label="Time" />

          <Button
            variant="secondary"
            size="sm"
            onClick={handleRunCode}
            isLoading={isRunning}
            leftIcon={<Play className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} />}
          >
            Run Code
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsSubmitModalOpen(true)}
            leftIcon={<Send className="w-3.5 h-3.5" />}
          >
            Submit
          </Button>
        </div>
      </div>

      {/* Mobile Tab Switcher */}
      <div className="flex lg:hidden items-center justify-around p-1 text-xs shrink-0" style={{ backgroundColor: "var(--bg-surface)", borderBottom: "1px solid var(--border-subtle)" }}>
        <button
          type="button"
          onClick={() => setMobileTab("problem")}
          className="py-1.5 px-3 rounded-md font-medium transition"
          style={{
            backgroundColor: mobileTab === "problem" ? "var(--accent-subtle)" : "transparent",
            color: mobileTab === "problem" ? "var(--accent-primary)" : "var(--text-muted)",
            fontWeight: mobileTab === "problem" ? 600 : 400
          }}
        >
          Problem ({activeQuestionIdx + 1}/{questions.length})
        </button>
        <button
          type="button"
          onClick={() => setMobileTab("editor")}
          className="py-1.5 px-3 rounded-md font-medium transition"
          style={{
            backgroundColor: mobileTab === "editor" ? "var(--accent-subtle)" : "transparent",
            color: mobileTab === "editor" ? "var(--accent-primary)" : "var(--text-muted)",
            fontWeight: mobileTab === "editor" ? 600 : 400
          }}
        >
          Code Editor
        </button>
        <button
          type="button"
          onClick={() => setMobileTab("console")}
          className="py-1.5 px-3 rounded-md font-medium transition"
          style={{
            backgroundColor: mobileTab === "console" ? "var(--accent-subtle)" : "transparent",
            color: mobileTab === "console" ? "var(--accent-primary)" : "var(--text-muted)",
            fontWeight: mobileTab === "console" ? 600 : 400
          }}
        >
          Output & Test Cases
        </button>
      </div>

      {/* Main Split Body */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        
        {/* LEFT PANE (5 Cols): Problem Specification & Examples */}
        <div
          className={`lg:col-span-5 h-full overflow-y-auto p-4 sm:p-5 space-y-4 text-left ${
            mobileTab !== "problem" ? "hidden lg:block" : "block"
          }`}
          style={{ borderRight: "1px solid var(--border-subtle)" }}
        >
          {activeQ ? (
            <div className="space-y-4">
              {/* Problem Heading */}
              <div className="space-y-1.5 pb-3" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold" style={{ color: "var(--accent-primary)" }}>
                      Problem {activeQuestionIdx + 1} of {questions.length}
                    </span>
                    <Badge
                      variant={
                        activeQ.difficulty_score <= 3 ? "success" : activeQ.difficulty_score <= 7 ? "default" : "warning"
                      }
                      size="sm"
                    >
                      Diff {activeQ.difficulty_score}/10
                    </Badge>
                  </div>

                  {existingSubmission && (
                    <Badge variant={existingSubmission.verdict === "Accepted" ? "success" : "neutral"} size="sm">
                      {existingSubmission.verdict === "Accepted" ? "Solved ✓" : "Submitted"}
                    </Badge>
                  )}
                </div>

                <h2 className="text-base sm:text-lg font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                  {activeQ.title}
                </h2>

                <div className="flex flex-wrap gap-1 pt-1">
                  {activeQ.topic_tags?.map((t, tIdx) => (
                    <span
                      key={`tag-${t}-${tIdx}`}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono"
                      style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)", color: "var(--text-secondary)" }}
                    >
                      {t}
                    </span>
                  ))}
                  <span className="text-[10px] font-mono ml-auto" style={{ color: "var(--text-muted)" }}>
                    Time: {activeQ.time_limit_seconds || 2}s • Mem: {activeQ.memory_limit_mb || 256}MB
                  </span>
                </div>
              </div>

              {/* Problem Statement */}
              <div className="space-y-1.5">
                <FormattedQuestionText text={activeQ.problem_statement} />
              </div>

              {/* Input / Output Format */}
              <div className="space-y-2.5 pt-2 text-xs" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                {activeQ.input_format && (
                  <div className="p-3 rounded-lg space-y-1" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
                    <span className="font-semibold block text-[11px]" style={{ color: "var(--text-primary)" }}>Input Format:</span>
                    <FormattedQuestionText text={activeQ.input_format} />
                  </div>
                )}

                {activeQ.output_format && (
                  <div className="p-3 rounded-lg space-y-1" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
                    <span className="font-semibold block text-[11px]" style={{ color: "var(--text-primary)" }}>Output Format:</span>
                    <FormattedQuestionText text={activeQ.output_format} />
                  </div>
                )}

                {activeQ.constraints && (
                  <div className="p-3 rounded-lg space-y-1" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
                    <span className="font-semibold block text-[11px]" style={{ color: "var(--text-primary)" }}>Constraints:</span>
                    <FormattedQuestionText text={activeQ.constraints} />
                  </div>
                )}
              </div>

              {/* Visible Sample Cases */}
              {activeQ.visible_test_cases && activeQ.visible_test_cases.length > 0 && (
                <div className="space-y-2 pt-2 text-xs" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                  <span className="font-bold uppercase tracking-wider text-[11px]" style={{ color: "var(--text-primary)" }}>Sample Cases:</span>
                  {activeQ.visible_test_cases.map((tc, idx) => (
                    <div key={`sample-case-${tc.id ?? idx}`} className="p-3 rounded-lg space-y-2" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
                      <span className="font-mono font-bold text-[10px]" style={{ color: "var(--text-muted)" }}>Example {idx + 1}</span>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                          <span className="text-[10px] font-mono block" style={{ color: "var(--text-muted)" }}>Input:</span>
                          <pre className="p-2 rounded font-mono text-[11px] overflow-x-auto" style={{ backgroundColor: "var(--bg-canvas)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)" }}>
                            {tc.input_data}
                          </pre>
                        </div>
                        <div>
                          <span className="text-[10px] font-mono block" style={{ color: "var(--text-muted)" }}>Expected Output:</span>
                          <pre className="p-2 rounded font-mono text-[11px] overflow-x-auto" style={{ backgroundColor: "var(--bg-canvas)", color: "var(--accent-primary)", border: "1px solid var(--border-subtle)" }}>
                            {tc.expected_output}
                          </pre>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-xs" style={{ color: "var(--text-muted)" }}>
              No problem selected.
            </div>
          )}
        </div>

        {/* RIGHT PANE (7 Cols): Monaco Editor & Output Console Split */}
        <div
          className={`lg:col-span-7 flex flex-col h-full overflow-hidden ${
            mobileTab === "problem" ? "hidden lg:flex" : "flex"
          }`}
        >
          {/* Top Half: Code Editor */}
          <div
            className={`w-full overflow-hidden ${
              mobileTab === "console" ? "hidden lg:flex lg:flex-1" : "flex-1 flex"
            }`}
          >
            <CodeEditor
              code={code}
              onChange={handleCodeChange}
              language={language}
              onLanguageChange={handleLanguageChange}
              onRun={handleRunCode}
            />
          </div>

          {/* Bottom Half: Test Results, Custom Input, Sample Cases & Submission History */}
          <div
            className={`flex flex-col ${
              mobileTab === "console" ? "flex-1 overflow-y-auto" : "h-64 sm:h-72 shrink-0 overflow-hidden"
            }`}
            style={{ borderTop: "1px solid var(--border-subtle)", backgroundColor: "var(--bg-surface)" }}
          >
            {/* Console Tabs Header */}
            <div className="flex items-center justify-between px-3.5 py-1.5 shrink-0 text-xs" style={{ backgroundColor: "var(--bg-canvas)", borderBottom: "1px solid var(--border-subtle)" }}>
              <div className="flex items-center gap-1 overflow-x-auto">
                <button
                  type="button"
                  onClick={() => setActiveBottomTab("results")}
                  className="px-2.5 py-1 rounded-md font-medium text-xs transition shrink-0"
                  style={{
                    backgroundColor: activeBottomTab === "results" ? "var(--bg-surface)" : "transparent",
                    color: activeBottomTab === "results" ? "var(--text-primary)" : "var(--text-muted)",
                    fontWeight: activeBottomTab === "results" ? 700 : 500,
                    border: activeBottomTab === "results" ? "1px solid var(--border-subtle)" : "1px solid transparent"
                  }}
                >
                  Judge Output
                </button>
                <button
                  type="button"
                  onClick={() => setActiveBottomTab("custom_input")}
                  className="px-2.5 py-1 rounded-md font-medium text-xs transition shrink-0"
                  style={{
                    backgroundColor: activeBottomTab === "custom_input" ? "var(--bg-surface)" : "transparent",
                    color: activeBottomTab === "custom_input" ? "var(--text-primary)" : "var(--text-muted)",
                    fontWeight: activeBottomTab === "custom_input" ? 700 : 500,
                    border: activeBottomTab === "custom_input" ? "1px solid var(--border-subtle)" : "1px solid transparent"
                  }}
                >
                  Custom Input
                </button>
                <button
                  type="button"
                  onClick={() => setActiveBottomTab("testcases")}
                  className="px-2.5 py-1 rounded-md font-medium text-xs transition shrink-0"
                  style={{
                    backgroundColor: activeBottomTab === "testcases" ? "var(--bg-surface)" : "transparent",
                    color: activeBottomTab === "testcases" ? "var(--text-primary)" : "var(--text-muted)",
                    fontWeight: activeBottomTab === "testcases" ? 700 : 500,
                    border: activeBottomTab === "testcases" ? "1px solid var(--border-subtle)" : "1px solid transparent"
                  }}
                >
                  Sample Cases
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setActiveBottomTab("history");
                    if (activeQ) fetchHistory(activeQ.id);
                  }}
                  className="px-2.5 py-1 rounded-md font-medium text-xs transition shrink-0 flex items-center gap-1"
                  style={{
                    backgroundColor: activeBottomTab === "history" ? "var(--bg-surface)" : "transparent",
                    color: activeBottomTab === "history" ? "var(--text-primary)" : "var(--text-muted)",
                    fontWeight: activeBottomTab === "history" ? 700 : 500,
                    border: activeBottomTab === "history" ? "1px solid var(--border-subtle)" : "1px solid transparent"
                  }}
                >
                  <History className="w-3 h-3" />
                  <span>My Submissions {submissionHistory ? `(${submissionHistory.total_submissions})` : ""}</span>
                </button>
              </div>

              <span className="text-[10px] font-mono hidden md:inline" style={{ color: "var(--text-muted)" }}>
                Isolated Sandboxed Judge
              </span>
            </div>

            {/* Console Content */}
            <div className="p-3.5 overflow-y-auto flex-1 text-xs">
              {/* Tab 1: Judge Results */}
              {activeBottomTab === "results" && (
                <TestResults
                  results={runResults}
                  isRunning={isRunning}
                  asyncStatus={asyncStatus}
                  isJudgingAsync={isJudgingAsync}
                />
              )}

              {/* Tab 2: Custom Standard Input */}
              {activeBottomTab === "custom_input" && (
                <div className="space-y-1.5 text-left">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold block text-[11px]" style={{ color: "var(--text-secondary)" }}>
                      Standard Input (stdin):
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] font-mono">Passed to program via standard input</span>
                  </div>
                  <textarea
                    rows={4}
                    value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)}
                    placeholder="Enter custom test input data..."
                    className="w-full p-2.5 rounded-lg font-mono text-xs"
                    style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)", color: "var(--text-primary)" }}
                  />
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Clicking &quot;Run Code&quot; with custom input will evaluate only against this input.
                  </p>
                </div>
              )}

              {/* Tab 3: Sample Cases */}
              {activeBottomTab === "testcases" && (
                <div className="space-y-3 text-left">
                  {activeQ?.visible_test_cases && activeQ.visible_test_cases.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {activeQ.visible_test_cases.map((tc, idx) => (
                        <div
                          key={`sample-tab-case-${tc.id ?? idx}`}
                          className="p-3 rounded-lg space-y-2 border"
                          style={{ backgroundColor: "var(--bg-canvas)", borderColor: "var(--border-subtle)" }}
                        >
                          <div className="flex items-center justify-between font-mono text-[10px]">
                            <span className="font-bold" style={{ color: "var(--text-primary)" }}>Sample #{idx + 1}</span>
                            <button
                              type="button"
                              onClick={() => handleCopy(tc.input_data, `tab_tc_in_${idx}`)}
                              className="flex items-center gap-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                            >
                              {copiedKey === `tab_tc_in_${idx}` ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                              <span>{copiedKey === `tab_tc_in_${idx}` ? "Copied" : "Copy Input"}</span>
                            </button>
                          </div>
                          <div>
                            <span className="text-[10px] font-mono block text-[var(--text-muted)]">Input:</span>
                            <pre className="p-2 rounded font-mono text-[11px] overflow-x-auto" style={{ backgroundColor: "var(--bg-surface)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)" }}>
                              {tc.input_data}
                            </pre>
                          </div>
                          <div>
                            <span className="text-[10px] font-mono block text-[var(--text-muted)]">Expected Output:</span>
                            <pre className="p-2 rounded font-mono text-[11px] overflow-x-auto" style={{ backgroundColor: "var(--bg-surface)", color: "var(--accent-text)", border: "1px solid var(--border-subtle)" }}>
                              {tc.expected_output}
                            </pre>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-6 text-[var(--text-muted)]">
                      No public sample test cases available for this question.
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4: Submission History */}
              {activeBottomTab === "history" && (
                <div className="space-y-3 text-left">
                  {loadingHistory ? (
                    <div className="text-center py-6 text-xs text-[var(--text-muted)]">
                      Loading submission history...
                    </div>
                  ) : submissionHistory && submissionHistory.history && submissionHistory.history.length > 0 ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)] pb-1 border-b border-[var(--border-subtle)]">
                        <span>Total Attempts: <strong className="text-[var(--text-primary)]">{submissionHistory.total_submissions}</strong></span>
                        {submissionHistory.best_execution_time_ms !== undefined && submissionHistory.best_execution_time_ms !== null && (
                          <span className="font-mono">Fastest: {submissionHistory.best_execution_time_ms.toFixed(1)}ms</span>
                        )}
                      </div>

                      <div className="divide-y divide-[var(--border-subtle)] overflow-x-auto">
                        <table className="w-full text-[11px] font-mono">
                          <thead>
                            <tr className="text-[var(--text-muted)] text-left">
                              <th className="py-1.5 pr-3">#</th>
                              <th className="py-1.5 pr-3">Verdict</th>
                              <th className="py-1.5 pr-3">Score</th>
                              <th className="py-1.5 pr-3">Lang</th>
                              <th className="py-1.5 pr-3">Time</th>
                              <th className="py-1.5 pr-3">Memory</th>
                              <th className="py-1.5 pr-3">Passed</th>
                            </tr>
                          </thead>
                          <tbody>
                            {submissionHistory.history.map((item) => {
                              const isAc = item.verdict === "Accepted";
                              return (
                                <tr key={item.submission_id} className="border-t border-[var(--border-subtle)]">
                                  <td className="py-2 pr-3 text-[var(--text-muted)]">#{item.attempt_number}</td>
                                  <td className="py-2 pr-3">
                                    <span
                                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                        isAc
                                          ? "text-emerald-500 bg-emerald-500/10"
                                          : item.verdict.includes("Time") || item.verdict.includes("Memory")
                                          ? "text-amber-500 bg-amber-500/10"
                                          : "text-rose-500 bg-rose-500/10"
                                      }`}
                                    >
                                      {item.verdict}
                                    </span>
                                  </td>
                                  <td className="py-2 pr-3 font-semibold text-[var(--text-primary)]">
                                    {item.score !== undefined ? `${item.score} pts` : "-"}
                                  </td>
                                  <td className="py-2 pr-3 text-[var(--text-secondary)] uppercase">{item.language}</td>
                                  <td className="py-2 pr-3 text-[var(--text-secondary)]">{item.execution_time_ms.toFixed(1)}ms</td>
                                  <td className="py-2 pr-3 text-[var(--text-secondary)]">{(item.memory_used_kb / 1024).toFixed(1)}MB</td>
                                  <td className="py-2 pr-3 text-[var(--text-secondary)]">
                                    {item.test_cases_passed}/{item.test_cases_total}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-6 text-xs text-[var(--text-muted)]">
                      No past submissions found for this question yet. Click Submit to evaluate your code!
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

      </div>

      {/* Submit Confirmation Modal */}
      <Modal
        isOpen={isSubmitModalOpen}
        onClose={() => setIsSubmitModalOpen(false)}
        title="Submit Final Solution"
        description={`Submit your ${language.toUpperCase()} solution for evaluation against hidden institutional test vectors.`}
        size="sm"
      >
        <div className="space-y-3.5 text-xs text-left">
          <div className="p-3 rounded-lg space-y-1" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
            <div className="flex items-center justify-between font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
              <span>Problem:</span>
              <span className="font-bold" style={{ color: "var(--text-primary)" }}>{activeQ?.title}</span>
            </div>
            <div className="flex items-center justify-between font-mono text-[11px]" style={{ color: "var(--text-secondary)" }}>
              <span>Language:</span>
              <span className="font-bold uppercase" style={{ color: "var(--accent-primary)" }}>{language}</span>
            </div>
          </div>

          <p className="leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            Your code will be evaluated in the sandboxed runtime against all hidden benchmark test cases. Your score and verdict will be recorded and updated on the leaderboard.
          </p>

          <div className="flex items-center justify-end gap-2 pt-2" style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <Button variant="outline" size="sm" onClick={() => setIsSubmitModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleFinalSubmit}
              isLoading={isSubmitting || isJudgingAsync}
              leftIcon={<Send className="w-3.5 h-3.5" />}
            >
              Confirm & Submit Solution
            </Button>
          </div>
        </div>
      </Modal>

    </div>
  );
}
