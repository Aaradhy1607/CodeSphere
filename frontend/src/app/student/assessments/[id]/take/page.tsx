"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AttemptState, AttemptQuestionState, AntiCheatEventType, AntiCheatSeverity, CodeRunResult } from "@/lib/types";
import {
  Shield, Clock, AlertTriangle, CheckCircle2, Bookmark,
  ChevronLeft, ChevronRight, Play, RefreshCw, Lock, Send,
  Code2, FileText, CheckSquare, ListFilter, Maximize2, AlertOctagon, Terminal
} from "lucide-react";
import { CodeEditor } from "@/components/CodeEditor";
import { TestResults } from "@/components/TestResults";

export default function TakeAssessmentPage() {
  const params = useParams();
  const router = useRouter();
  const assessmentId = Number(params?.id);

  // Attempt State
  const [attempt, setAttempt] = useState<AttemptState | null>(null);
  const [loading, setLoading] = useState(true);
  const [examStarted, setExamStarted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Navigation & Answers State
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, {
    selected_options?: string[];
    submitted_code?: string;
    submitted_language?: string;
    submitted_text?: string;
    is_flagged?: boolean;
  }>>({});

  // Autosave status: 'SAVED' | 'SAVING' | 'RETRYING'
  const [saveStatus, setSaveStatus] = useState<"SAVED" | "SAVING" | "RETRYING">("SAVED");
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Server Timer Synchronization
  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Anti-cheat tracking
  const [tabSwitches, setTabSwitches] = useState(0);
  const [antiCheatWarning, setAntiCheatWarning] = useState<string | null>(null);
  const [isTerminated, setIsTerminated] = useState(false);

  // Code runner state for coding questions
  const [codeRunning, setCodeRunning] = useState(false);
  const [codeRunResult, setCodeRunResult] = useState<CodeRunResult | null>(null);
  const [customInput, setCustomInput] = useState("");

  // Submit Modal
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // 1. Initialize or Resume Assessment Attempt
  const initAttempt = async () => {
    setLoading(true);
    setError(null);
    try {
      const state = await api.assessments.start(assessmentId);
      setAttempt(state);
      setRemainingSeconds(state.remaining_seconds);
      setTabSwitches(state.tab_switch_count);

      // Populate existing answers from attempt questions
      const initialAnswers: Record<number, any> = {};
      state.questions.forEach((q: AttemptQuestionState) => {
        initialAnswers[q.question_id] = {
          selected_options: q.selected_options || [],
          submitted_code: q.submitted_code || (q.code_template ? (q.code_template["python"] || Object.values(q.code_template)[0]) : ""),
          submitted_language: q.submitted_language || "python",
          submitted_text: q.submitted_text || "",
          is_flagged: q.is_flagged || false
        };
      });
      setAnswers(initialAnswers);

      if (state.status === "SUBMITTED" || state.status === "AUTO_SUBMITTED" || state.status === "TERMINATED_CHEATING") {
        router.push(`/student/assessments/${assessmentId}/results/${state.attempt_id}`);
        return;
      }
    } catch (err: any) {
      setError(err.message || "Failed to start assessment attempt");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (assessmentId) {
      initAttempt();
    }
  }, [assessmentId]);

  // 2. Submit Attempt Function
  const handleSubmitExam = async () => {
    if (!attempt || submitting) return;
    setSubmitting(true);
    try {
      // Build final sync payload
      const finalSync = Object.entries(answers).map(([qId, ans]) => ({
        question_id: Number(qId),
        selected_options: ans.selected_options,
        submitted_code: ans.submitted_code,
        submitted_language: ans.submitted_language,
        submitted_text: ans.submitted_text,
        is_flagged: ans.is_flagged
      }));

      const res = await api.assessments.submit(attempt.attempt_id, { final_sync_answers: finalSync });
      router.push(`/student/assessments/${assessmentId}/results/${attempt.attempt_id}`);
    } catch (err: any) {
      alert("Submission error: " + (err.message || "Please try again."));
      setSubmitting(false);
    }
  };

  // 3. Local & Server Timer Countdown
  useEffect(() => {
    if (!examStarted || remainingSeconds <= 0) return;

    timerIntervalRef.current = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timerIntervalRef.current!);
          handleSubmitExam();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, [examStarted, remainingSeconds]);

  // 4. Heartbeat Sync (every 15s)
  useEffect(() => {
    if (!examStarted || !attempt) return;

    heartbeatIntervalRef.current = setInterval(async () => {
      try {
        const hb = await api.assessments.heartbeat(attempt.attempt_id, attempt.current_session_token);
        setRemainingSeconds(hb.remaining_seconds);
        if (!hb.is_active || hb.status === "TERMINATED_CHEATING") {
          setIsTerminated(true);
        }
      } catch (err) {
        console.warn("Heartbeat sync error:", err);
      }
    }, 15000);

    return () => {
      if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
    };
  }, [examStarted, attempt]);

  // 5. Anti-Cheat Event Logging
  const logViolation = useCallback(async (eventType: AntiCheatEventType, severity: AntiCheatSeverity = "MEDIUM", details?: any) => {
    if (!attempt || !examStarted) return;
    try {
      const res = await api.assessments.logAntiCheat(attempt.attempt_id, {
        event_type: eventType,
        severity,
        event_data: details
      });
      setTabSwitches(res.switch_count);
      setAntiCheatWarning(`Warning: ${eventType.replace("_", " ")} recorded! (Violations: ${res.switch_count}/${attempt.max_tab_switches})`);
      setTimeout(() => setAntiCheatWarning(null), 5000);

      if (res.action_taken === "AUTO_TERMINATED_CHEATING") {
        setIsTerminated(true);
      }
    } catch (err) {
      console.warn("Anti-cheat logging failed:", err);
    }
  }, [attempt, examStarted]);

  // 6. Proctoring Listeners (Visibility / Blur / Copy-Paste / Fullscreen)
  useEffect(() => {
    if (!examStarted || !attempt) return;

    const handleVisibilityChange = () => {
      if (document.hidden) {
        logViolation("TAB_SWITCH", "HIGH", { reason: "Document visibility hidden" });
      }
    };

    const handleWindowBlur = () => {
      logViolation("WINDOW_BLUR", "MEDIUM", { reason: "Window lost focus" });
    };

    const handleFullscreenChange = () => {
      const inFull = !!document.fullscreenElement;
      setIsFullscreen(inFull);
      if (!inFull && attempt.fullscreen_enforced) {
        logViolation("FULLSCREEN_EXIT", "HIGH", { reason: "Exited fullscreen mode" });
      }
    };

    const handlePaste = (e: ClipboardEvent) => {
      if (attempt.paste_detection_enabled) {
        e.preventDefault();
        logViolation("COPY_PASTE", "HIGH", { reason: "Clipboard paste intercepted" });
      }
    };

    const handleContextMenu = (e: MouseEvent) => {
      e.preventDefault();
      logViolation("RIGHT_CLICK", "LOW", { reason: "Context menu right click blocked" });
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      // Intercept F12 or Ctrl+Shift+I / Cmd+Option+I
      if (e.key === "F12" || (e.ctrlKey && e.shiftKey && (e.key === "I" || e.key === "J" || e.key === "C"))) {
        e.preventDefault();
        logViolation("DEVTOOLS_OPEN", "CRITICAL", { key: e.key });
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleWindowBlur);
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("paste", handlePaste);
    document.addEventListener("contextmenu", handleContextMenu);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleWindowBlur);
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("paste", handlePaste);
      document.removeEventListener("contextmenu", handleContextMenu);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [examStarted, attempt, logViolation]);

  // 7. Autosave Debounce
  const triggerAutosave = useCallback((qId: number, currentAns: any) => {
    if (!attempt) return;
    setSaveStatus("SAVING");
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    saveTimeoutRef.current = setTimeout(async () => {
      try {
        await api.assessments.saveAnswer(attempt.attempt_id, {
          question_id: qId,
          selected_options: currentAns.selected_options,
          submitted_code: currentAns.submitted_code,
          submitted_language: currentAns.submitted_language,
          submitted_text: currentAns.submitted_text,
          is_flagged: currentAns.is_flagged
        });
        setSaveStatus("SAVED");
      } catch (err) {
        console.warn("Autosave error:", err);
        setSaveStatus("RETRYING");
      }
    }, 1200);
  }, [attempt]);

  // 8. Update Answer Handlers
  const handleOptionSelect = (qId: number, optionId: string, isMultiple: boolean) => {
    const cur = answers[qId] || {};
    let newOptions: string[] = [];

    if (isMultiple) {
      const selected = cur.selected_options || [];
      if (selected.includes(optionId)) {
        newOptions = selected.filter(o => o !== optionId);
      } else {
        newOptions = [...selected, optionId];
      }
    } else {
      newOptions = [optionId];
    }

    const updated = { ...cur, selected_options: newOptions };
    setAnswers(prev => ({ ...prev, [qId]: updated }));
    triggerAutosave(qId, updated);
  };

  const handleCodeChange = (qId: number, code: string, lang: string) => {
    const cur = answers[qId] || {};
    const updated = { ...cur, submitted_code: code, submitted_language: lang };
    setAnswers(prev => ({ ...prev, [qId]: updated }));
    triggerAutosave(qId, updated);
  };

  const handleTextChange = (qId: number, text: string) => {
    const cur = answers[qId] || {};
    const updated = { ...cur, submitted_text: text };
    setAnswers(prev => ({ ...prev, [qId]: updated }));
    triggerAutosave(qId, updated);
  };

  const toggleFlag = (qId: number) => {
    const cur = answers[qId] || {};
    const updated = { ...cur, is_flagged: !cur.is_flagged };
    setAnswers(prev => ({ ...prev, [qId]: updated }));
    triggerAutosave(qId, updated);
  };

  // 9. Run Visible Test Cases for Coding
  const handleRunVisibleCode = async (q: AttemptQuestionState) => {
    const userCode = answers[q.question_id]?.submitted_code || "";
    const lang = answers[q.question_id]?.submitted_language || "python";

    setCodeRunning(true);
    setCodeRunResult(null);

    try {
      const res = await api.execute.run(q.question_id, userCode, lang, customInput || undefined);
      setCodeRunResult(res);
    } catch (err: any) {
      alert("Execution error: " + (err.message || "Failed to execute code"));
    } finally {
      setCodeRunning(false);
    }
  };

  const requestFullscreenAndStart = async () => {
    try {
      if (document.documentElement.requestFullscreen) {
        await document.documentElement.requestFullscreen();
      }
    } catch (e) {
      console.warn("Fullscreen request bypassed or denied:", e);
    }
    setExamStarted(true);
  };

  const formatTimer = (sec: number) => {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) {
      return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center p-8">
        <RefreshCw className="w-6 h-6 animate-spin text-[var(--accent-primary)]" />
      </div>
    );
  }

  if (error || !attempt) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl p-6 text-center space-y-4 shadow-lg">
          <AlertTriangle className="w-10 h-10 text-red-500 mx-auto" />
          <h2 className="text-lg font-bold">Unable to Start Assessment</h2>
          <p className="text-xs text-[var(--text-secondary)]">{error || "Assessment attempt unavailable."}</p>
          <Link
            href="/student/assessments"
            className="inline-block px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-xs font-semibold"
          >
            Return to Assessments
          </Link>
        </div>
      </div>
    );
  }

  // Pre-Exam Instruction & Fullscreen Modal
  if (!examStarted) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] flex items-center justify-center p-4">
        <div className="max-w-xl w-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="flex items-center gap-3 border-b border-[var(--border-subtle)] pb-4">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-500">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold">{attempt.assessment_title}</h1>
              <p className="text-xs text-[var(--text-secondary)]">Secure Proctored Assessment Session</p>
            </div>
          </div>

          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-[var(--bg-base)] border border-[var(--border-subtle)] space-y-2">
              <h3 className="font-semibold text-sm">Exam Instructions & Rules:</h3>
              <ul className="space-y-1.5 text-[var(--text-secondary)] list-disc pl-4">
                <li>Total Duration: <strong className="text-[var(--text-primary)]">{attempt.duration_minutes} minutes</strong>. Timer runs server-side.</li>
                <li>Questions: <strong className="text-[var(--text-primary)]">{attempt.questions.length} questions</strong> across multiple sections.</li>
                <li>Answers are <strong className="text-emerald-500">continuously autosaved</strong>. You can safely refresh without loss.</li>
                {attempt.fullscreen_enforced && (
                  <li><strong className="text-amber-500">Fullscreen enforcement:</strong> Exiting full screen mode logs an anti-cheat event.</li>
                )}
                <li>
                  <strong className="text-red-500">Tab Switch Limit:</strong> Maximum {attempt.max_tab_switches} tab switches allowed before automatic termination.
                </li>
              </ul>
            </div>

            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                By clicking Start Exam, your session token will be locked to this browser and full-screen proctoring will commence.
              </span>
            </div>
          </div>

          <button
            onClick={requestFullscreenAndStart}
            className="w-full py-3 rounded-xl bg-[var(--accent-primary)] text-white font-bold text-sm hover:opacity-90 transition flex items-center justify-center gap-2 shadow-lg shadow-[var(--accent-primary)]/20"
          >
            <Maximize2 className="w-4 h-4" /> Enter Fullscreen & Start Exam
          </button>
        </div>
      </div>
    );
  }

  // Cheating Termination Screen
  if (isTerminated) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-[var(--bg-surface)] border border-red-500/30 rounded-2xl p-8 text-center space-y-4 shadow-2xl">
          <div className="w-12 h-12 rounded-full bg-red-500/10 text-red-500 flex items-center justify-center mx-auto">
            <AlertOctagon className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-red-500">Assessment Terminated</h2>
          <p className="text-xs text-[var(--text-secondary)]">
            This examination session has been terminated by the anti-cheating engine or proctor due to excessive tab switching or integrity violations.
          </p>
          <Link
            href={`/student/assessments/${assessmentId}/results/${attempt.attempt_id}`}
            className="inline-block px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-xs font-semibold"
          >
            View Final Status
          </Link>
        </div>
      </div>
    );
  }

  const currentQ = attempt.questions[currentIndex];
  const currentAnswer = answers[currentQ?.question_id] || {};

  const totalAnswered = Object.values(answers).filter(a =>
    (a.selected_options && a.selected_options.length > 0) ||
    (a.submitted_code && a.submitted_code.trim().length > 0) ||
    (a.submitted_text && a.submitted_text.trim().length > 0)
  ).length;

  const totalFlagged = Object.values(answers).filter(a => a.is_flagged).length;

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] flex flex-col select-none">
      
      {/* Top Header Navigation Bar */}
      <header className="sticky top-0 z-40 bg-[var(--bg-surface)] border-b border-[var(--border-subtle)] px-4 py-2.5 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <h2 className="font-bold text-xs sm:text-sm line-clamp-1">{attempt.assessment_title}</h2>
            <p className="text-[10px] text-[var(--text-secondary)] font-medium">
              Section: {currentQ?.section_name || "General"} • Q{currentIndex + 1} of {attempt.questions.length}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Autosave Pill */}
          <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-medium text-[var(--text-secondary)]">
            {saveStatus === "SAVING" ? (
              <span className="text-amber-500 flex items-center gap-1">
                <RefreshCw className="w-3 h-3 animate-spin" /> Saving...
              </span>
            ) : saveStatus === "RETRYING" ? (
              <span className="text-red-500 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Offline (retrying)
              </span>
            ) : (
              <span className="text-emerald-500 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Saved
              </span>
            )}
          </div>

          {/* Countdown Clock */}
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg border font-mono font-bold text-xs ${
            remainingSeconds < 300
              ? 'bg-red-500/10 border-red-500/30 text-red-500 animate-pulse'
              : 'bg-[var(--bg-base)] border-[var(--border-subtle)] text-[var(--text-primary)]'
          }`}>
            <Clock className="w-3.5 h-3.5" />
            <span>{formatTimer(remainingSeconds)}</span>
          </div>

          {/* Submit Exam CTA */}
          <button
            onClick={() => setIsSubmitModalOpen(true)}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition shadow-sm"
          >
            Submit Test
          </button>
        </div>
      </header>

      {/* Warning Banner */}
      {antiCheatWarning && (
        <div className="bg-red-500 text-white text-xs font-bold px-4 py-2 text-center animate-bounce">
          {antiCheatWarning}
        </div>
      )}

      {/* Main Examination Body */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        
        {/* Left / Center: Question & Answer Workspace */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {currentQ && (
            <div className="max-w-4xl mx-auto space-y-6">
              
              {/* Question Header Card */}
              <div className="p-5 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/20">
                      {currentQ.question_type.replace("_", " ")}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)] font-medium">
                      Marks: +{currentQ.marks} {currentQ.negative_marks > 0 ? `| -${currentQ.negative_marks}` : ""}
                    </span>
                  </div>

                  <button
                    onClick={() => toggleFlag(currentQ.question_id)}
                    className={`flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg transition ${
                      currentAnswer.is_flagged
                        ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/30'
                        : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]'
                    }`}
                  >
                    <Bookmark className="w-3.5 h-3.5" />
                    {currentAnswer.is_flagged ? "Flagged for Review" : "Flag for Review"}
                  </button>
                </div>

                <h3 className="text-base font-bold text-[var(--text-primary)] leading-snug">
                  {currentQ.title}
                </h3>

                {currentQ.description && (
                  <div className="text-xs text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed border-t border-[var(--border-subtle)] pt-3">
                    {currentQ.description}
                  </div>
                )}
              </div>

              {/* Dynamic Answer Interface */}
              <div className="p-5 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
                
                {/* 1. MCQ Single Choice */}
                {currentQ.question_type === "MCQ" && currentQ.options && (
                  <div className="space-y-2.5">
                    <span className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                      Select One Correct Option:
                    </span>
                    <div className="space-y-2">
                      {currentQ.options.map((opt) => {
                        const isSelected = currentAnswer.selected_options?.includes(opt.id);
                        return (
                          <div
                            key={opt.id}
                            onClick={() => handleOptionSelect(currentQ.question_id, opt.id, false)}
                            className={`p-3.5 rounded-xl border cursor-pointer transition flex items-start gap-3 ${
                              isSelected
                                ? 'bg-[var(--accent-primary)]/10 border-[var(--accent-primary)] text-[var(--text-primary)] shadow-sm'
                                : 'bg-[var(--bg-base)] border-[var(--border-subtle)] hover:border-[var(--border-hover)] text-[var(--text-secondary)]'
                            }`}
                          >
                            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 border ${
                              isSelected
                                ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)]'
                                : 'bg-[var(--bg-surface)] border-[var(--border-subtle)] text-[var(--text-muted)]'
                            }`}>
                              {opt.id}
                            </span>
                            <span className="text-xs leading-relaxed font-medium">{opt.text}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 2. Multiple Select */}
                {currentQ.question_type === "MULTIPLE_SELECT" && currentQ.options && (
                  <div className="space-y-2.5">
                    <span className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                      Select All Correct Options (One or More):
                    </span>
                    <div className="space-y-2">
                      {currentQ.options.map((opt) => {
                        const isSelected = currentAnswer.selected_options?.includes(opt.id);
                        return (
                          <div
                            key={opt.id}
                            onClick={() => handleOptionSelect(currentQ.question_id, opt.id, true)}
                            className={`p-3.5 rounded-xl border cursor-pointer transition flex items-start gap-3 ${
                              isSelected
                                ? 'bg-[var(--accent-primary)]/10 border-[var(--accent-primary)] text-[var(--text-primary)] shadow-sm'
                                : 'bg-[var(--bg-base)] border-[var(--border-subtle)] hover:border-[var(--border-hover)] text-[var(--text-secondary)]'
                            }`}
                          >
                            <div className={`w-4 h-4 rounded mt-0.5 flex items-center justify-center border shrink-0 ${
                              isSelected
                                ? 'bg-[var(--accent-primary)] border-[var(--accent-primary)] text-white'
                                : 'border-[var(--border-subtle)] bg-[var(--bg-surface)]'
                            }`}>
                              {isSelected && <CheckCircle2 className="w-3.5 h-3.5" />}
                            </div>
                            <span className="text-xs leading-relaxed font-medium">{opt.text}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 3. Coding Question Workspace */}
                {currentQ.question_type === "CODING" && (
                  <div className="space-y-4">
                    {/* Top Action / Execution Bar */}
                    <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
                      <div className="flex items-center gap-2">
                        <Code2 className="w-4 h-4 text-[var(--accent-primary)]" />
                        <span className="text-xs font-bold text-[var(--text-primary)]">Code Workspace</span>
                        <span className="text-[10px] text-[var(--text-muted)] font-mono hidden sm:inline">(Ctrl+Enter to Run)</span>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleRunVisibleCode(currentQ)}
                          disabled={codeRunning}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[var(--accent-primary)] text-white text-xs font-bold hover:opacity-90 disabled:opacity-50 transition cursor-pointer shadow-xs"
                        >
                          <Play className="w-3.5 h-3.5" /> {codeRunning ? "Running..." : "Run Code"}
                        </button>
                      </div>
                    </div>

                    {/* Monaco Code Editor Component */}
                    <div className="h-[380px] rounded-lg overflow-hidden border border-[var(--border-subtle)]">
                      <CodeEditor
                        code={currentAnswer.submitted_code || ""}
                        onChange={(val) => handleCodeChange(currentQ.question_id, val, currentAnswer.submitted_language || "python")}
                        language={currentAnswer.submitted_language || "python"}
                        onLanguageChange={(newLang) => handleCodeChange(currentQ.question_id, currentAnswer.submitted_code || "", newLang)}
                        onRun={() => handleRunVisibleCode(currentQ)}
                      />
                    </div>

                    {/* Bottom Console Panel (Tabs: Sample Cases, Custom Input, Output) */}
                    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden space-y-0">
                      {/* Console Tabs Header */}
                      <div className="flex items-center justify-between px-3 py-1.5 bg-[var(--bg-base)] border-b border-[var(--border-subtle)] text-xs">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setCustomInput("")}
                            className={`px-2.5 py-1 rounded-md font-medium text-xs transition ${
                              customInput === "" ? "bg-[var(--bg-surface)] text-[var(--text-primary)] font-bold shadow-xs border border-[var(--border-subtle)]" : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                            }`}
                          >
                            Sample Test Cases
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              if (customInput === "") setCustomInput(" ");
                            }}
                            className={`px-2.5 py-1 rounded-md font-medium text-xs transition ${
                              customInput !== "" ? "bg-[var(--bg-surface)] text-[var(--text-primary)] font-bold shadow-xs border border-[var(--border-subtle)]" : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                            }`}
                          >
                            Custom Input (stdin)
                          </button>
                        </div>
                        <span className="text-[10px] font-mono text-[var(--text-muted)] hidden sm:inline">
                          Isolated Sandbox Execution
                        </span>
                      </div>

                      {/* Tab 1: Sample Test Cases */}
                      {customInput === "" && (
                        <div className="p-3.5 space-y-3">
                          {currentQ.visible_test_cases && currentQ.visible_test_cases.length > 0 ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              {currentQ.visible_test_cases.map((tc, idx) => (
                                <div key={idx} className="p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)] space-y-1.5 text-xs font-mono">
                                  <div className="flex items-center justify-between">
                                    <span className="text-[10px] font-bold text-[var(--text-muted)]">Example Case #{idx + 1}</span>
                                  </div>
                                  <div>
                                    <span className="text-[10px] text-[var(--text-secondary)] block font-sans">Input:</span>
                                    <pre className="bg-[var(--bg-surface)] p-2 rounded border border-[var(--border-subtle)] text-[11px] overflow-x-auto">{tc.input_data}</pre>
                                  </div>
                                  <div>
                                    <span className="text-[10px] text-[var(--text-secondary)] block font-sans">Expected Output:</span>
                                    <pre className="bg-[var(--bg-surface)] p-2 rounded border border-[var(--border-subtle)] text-[11px] text-[var(--accent-text)] overflow-x-auto">{tc.expected_output}</pre>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-[var(--text-muted)] p-2">Standard problem constraints and hidden evaluation apply for this question.</p>
                          )}
                        </div>
                      )}

                      {/* Tab 2: Custom Input */}
                      {customInput !== "" && (
                        <div className="p-3.5 space-y-1.5 text-xs">
                          <label className="block text-[11px] font-semibold text-[var(--text-secondary)]">
                            Custom Standard Input (stdin):
                          </label>
                          <textarea
                            rows={3}
                            value={customInput.trim() === "" ? "" : customInput}
                            onChange={(e) => setCustomInput(e.target.value)}
                            placeholder="Enter test input data to feed into stdin..."
                            className="w-full p-2.5 rounded-md font-mono text-xs bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                      )}

                      {/* Execution Output Box */}
                      {(codeRunResult || codeRunning) && (
                        <div className="p-3.5 border-t border-[var(--border-subtle)]">
                          <TestResults results={codeRunResult} isRunning={codeRunning} />
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 4. Subjective / Essay Question */}
                {currentQ.question_type === "SUBJECTIVE" && (
                  <div className="space-y-3">
                    <span className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                      Written Response:
                    </span>
                    <textarea
                      rows={8}
                      value={currentAnswer.submitted_text || ""}
                      onChange={(e) => handleTextChange(currentQ.question_id, e.target.value)}
                      placeholder="Type your explanation or descriptive answer..."
                      className="w-full p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-base)] text-xs focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)] leading-relaxed"
                    />
                    <div className="flex justify-end text-[10px] text-[var(--text-muted)]">
                      {(currentAnswer.submitted_text || "").length} characters • {((currentAnswer.submitted_text || "").trim().split(/\s+/).filter(Boolean).length)} words
                    </div>
                  </div>
                )}

              </div>

              {/* Bottom Question Step Footer */}
              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={() => setCurrentIndex(prev => Math.max(0, prev - 1))}
                  disabled={currentIndex === 0}
                  className="px-4 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] text-xs font-semibold transition disabled:opacity-30 flex items-center gap-1.5"
                >
                  <ChevronLeft className="w-4 h-4" /> Previous
                </button>

                <button
                  onClick={() => setCurrentIndex(prev => Math.min(attempt.questions.length - 1, prev + 1))}
                  disabled={currentIndex === attempt.questions.length - 1}
                  className="px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-xs font-semibold hover:opacity-90 transition disabled:opacity-30 flex items-center gap-1.5"
                >
                  Next <ChevronRight className="w-4 h-4" />
                </button>
              </div>

            </div>
          )}
        </main>

        {/* Right Sidebar: Question Palette & Overview */}
        <aside className="w-full md:w-72 bg-[var(--bg-surface)] border-t md:border-t-0 md:border-l border-[var(--border-subtle)] p-4 space-y-4 overflow-y-auto">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] mb-2">Question Palette</h4>
            <div className="grid grid-cols-2 gap-2 text-[10px] text-[var(--text-secondary)] mb-4">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-emerald-500" />
                <span>{totalAnswered} Answered</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-purple-500" />
                <span>{totalFlagged} Flagged</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-[var(--bg-base)] border border-[var(--border-subtle)]" />
                <span>{attempt.questions.length - totalAnswered} Unattempted</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-5 gap-2">
            {attempt.questions.map((q, idx) => {
              const ans = answers[q.question_id];
              const isAnswered =
                (ans?.selected_options && ans.selected_options.length > 0) ||
                (ans?.submitted_code && ans.submitted_code.trim().length > 0) ||
                (ans?.submitted_text && ans.submitted_text.trim().length > 0);
              const isFlagged = ans?.is_flagged;
              const isCurrent = idx === currentIndex;

              return (
                <button
                  key={q.question_id}
                  onClick={() => setCurrentIndex(idx)}
                  className={`h-9 rounded-lg font-mono font-bold text-xs transition flex items-center justify-center relative ${
                    isCurrent
                      ? 'ring-2 ring-[var(--accent-primary)] ring-offset-2 ring-offset-[var(--bg-surface)]'
                      : ''
                  } ${
                    isAnswered
                      ? 'bg-emerald-500 text-white'
                      : 'bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]'
                  }`}
                >
                  {idx + 1}
                  {isFlagged && (
                    <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-purple-500 border border-white" />
                  )}
                </button>
              );
            })}
          </div>
        </aside>

      </div>

      {/* Submit Confirmation Modal */}
      {isSubmitModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center mx-auto">
                <Send className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-base">Ready to Submit Your Exam?</h3>
              <p className="text-xs text-[var(--text-secondary)]">
                Once submitted, your answers will be finalized and evaluated. You will not be able to modify your submission.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[var(--bg-base)] border border-[var(--border-subtle)] grid grid-cols-3 gap-2 text-center text-xs">
              <div>
                <span className="block font-bold text-base text-emerald-500">{totalAnswered}</span>
                <span className="text-[10px] text-[var(--text-secondary)]">Answered</span>
              </div>
              <div>
                <span className="block font-bold text-base text-purple-500">{totalFlagged}</span>
                <span className="text-[10px] text-[var(--text-secondary)]">Flagged</span>
              </div>
              <div>
                <span className="block font-bold text-base text-[var(--text-muted)]">{attempt.questions.length - totalAnswered}</span>
                <span className="text-[10px] text-[var(--text-secondary)]">Unanswered</span>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={() => setIsSubmitModalOpen(false)}
                className="flex-1 py-2 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold hover:bg-[var(--bg-subtle)]"
              >
                Continue Exam
              </button>
              <button
                onClick={handleSubmitExam}
                disabled={submitting}
                className="flex-1 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Confirm & Submit"}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
