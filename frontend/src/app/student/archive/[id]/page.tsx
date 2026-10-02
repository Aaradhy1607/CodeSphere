"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event, Submission } from "@/lib/types";
import {
  ChevronLeft, CheckCircle2, XCircle, Code2,
  Sparkles, Lock, Copy, Check
} from "lucide-react";
import FormattedQuestionText from "@/components/FormattedQuestionText";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/LoadingState";
import { useToast } from "@/components/ui/Toast";

export default function PostEventArchivePage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const eventId = parseInt(resolvedParams.id);
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const { success } = useToast();

  const [event, setEvent] = useState<Event | null>(null);
  const [selectedQuestionIdx, setSelectedQuestionIdx] = useState<number>(0);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSolLang, setActiveSolLang] = useState<"python" | "cpp" | "c" | "java">("python");
  const [copiedCode, setCopiedCode] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
      return;
    }
    if (user && eventId) {
      api.events.get(eventId)
        .then((evt) => {
          setEvent(evt);
          if (evt.questions && evt.questions.length > 0) {
            loadSubmission(evt.id, evt.questions[0].id);
          }
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [user, isLoading, eventId, router]);

  const loadSubmission = async (evtId: number, qId: number) => {
    try {
      const sub = await api.execute.getMySubmission(evtId, qId);
      setSubmission(sub);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSelectQuestion = (idx: number) => {
    setSelectedQuestionIdx(idx);
    const targetQ = event?.questions?.[idx];
    if (targetQ) {
      loadSubmission(eventId, targetQ.id);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(true);
    success("Code snippet copied to clipboard");
    setTimeout(() => setCopiedCode(false), 2000);
  };

  if (isLoading || loading || !user || !event) {
    return <LoadingState message="Loading archived assessment dossier..." className="min-h-[60vh]" />;
  }

  const questions = event.questions || [];
  const activeQ = questions[selectedQuestionIdx];
  const areSolutionsReleased = event.are_solutions_released || user.role === "ADMIN";

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/student/events"
            className="p-2 rounded-lg border transition"
            style={{
              backgroundColor: "var(--bg-surface)",
              borderColor: "var(--border-subtle)",
              color: "var(--text-primary)"
            }}
            aria-label="Back to Assessments"
          >
            <ChevronLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="neutral" size="sm">Archive & Reference</Badge>
              <Badge variant={event.status === "RESULTS_RELEASED" ? "info" : event.status === "ACTIVE" ? "success" : "neutral"} size="sm">
                {event.status}
              </Badge>
            </div>
            <h1 className="text-2xl font-bold mt-1 tracking-tight" style={{ color: "var(--text-primary)" }}>{event.title}</h1>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/student/reports">
            <Button variant="outline" size="sm">
              <Sparkles className="w-3.5 h-3.5 mr-1.5" style={{ color: "var(--accent-primary)" }} /> Diagnostic Evaluation
            </Button>
          </Link>
        </div>
      </div>

      {/* Main Split Content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Questions List & Problem Spec */}
        <div className="lg:col-span-5 space-y-6">
          {/* Question Selector */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                Assessment Questions ({questions.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {questions.map((q, idx) => (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => handleSelectQuestion(idx)}
                  className="w-full p-3 rounded-lg border text-left text-xs transition flex items-center justify-between"
                  style={{
                    backgroundColor: selectedQuestionIdx === idx ? "var(--accent-subtle)" : "var(--bg-canvas)",
                    borderColor: selectedQuestionIdx === idx ? "var(--accent-primary)" : "var(--border-subtle)",
                    color: selectedQuestionIdx === idx ? "var(--text-primary)" : "var(--text-secondary)",
                    fontWeight: selectedQuestionIdx === idx ? 600 : 400
                  }}
                >
                  <div className="truncate pr-2">
                    <span className="text-[10px] font-mono block" style={{ color: "var(--accent-primary)" }}>Problem {idx + 1}</span>
                    <span className="truncate">{q.title}</span>
                  </div>
                  <Badge variant="neutral" size="sm">
                    {q.difficulty_score}/10
                  </Badge>
                </button>
              ))}
            </CardContent>
          </Card>

          {/* Active Problem Statement */}
          {activeQ && (
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  {activeQ.topic_tags?.map((t, tIdx) => (
                    <Badge key={`tag-${t}-${tIdx}`} variant="neutral" size="sm">
                      {t}
                    </Badge>
                  ))}
                </div>
                <CardTitle className="text-lg">{activeQ.title}</CardTitle>
              </CardHeader>

              <CardContent className="space-y-4">
                <div className="space-y-2 text-xs">
                  <h3 className="font-bold uppercase tracking-wider text-[11px]" style={{ color: "var(--text-muted)" }}>
                    Problem Specification
                  </h3>
                  <div className="leading-relaxed p-4 rounded-xl border" style={{ backgroundColor: "var(--bg-canvas)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}>
                    <FormattedQuestionText text={activeQ.problem_statement} />
                  </div>
                </div>

                <div className="p-3.5 rounded-lg border space-y-2 text-xs" style={{ backgroundColor: "var(--bg-canvas)", borderColor: "var(--border-subtle)" }}>
                  <h4 className="font-semibold" style={{ color: "var(--text-primary)" }}>Constraints & Limits</h4>
                  <div className="font-mono text-[11px]" style={{ color: "var(--color-warning)" }}>
                    <FormattedQuestionText text={activeQ.constraints || "Standard competition limits apply."} />
                  </div>
                  <p className="text-[11px] font-mono pt-1" style={{ borderTop: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                    Time: {activeQ.expected_time_complexity} | Space: {activeQ.expected_space_complexity}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right Column: Submitted Code vs Reference Solution */}
        <div className="lg:col-span-7 space-y-6">
          {/* Submission Outcome Banner */}
          {submission ? (
            <Card>
              <CardContent className="py-4 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg border" style={{
                    backgroundColor: submission.verdict === "Accepted" ? "var(--color-success-subtle)" : "var(--color-danger-subtle)",
                    borderColor: submission.verdict === "Accepted" ? "var(--color-success)" : "var(--color-danger)",
                    color: submission.verdict === "Accepted" ? "var(--color-success)" : "var(--color-danger)"
                  }}>
                    {submission.verdict === "Accepted" ? (
                      <CheckCircle2 className="w-5 h-5" />
                    ) : (
                      <XCircle className="w-5 h-5" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm" style={{ color: "var(--text-primary)" }}>{submission.verdict}</span>
                      <Badge variant="neutral" size="sm">{submission.language}</Badge>
                    </div>
                    <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                      Passed {submission.passed_test_cases} / {submission.total_test_cases} test cases • Score: {submission.score} pts
                    </p>
                  </div>
                </div>

                <div className="text-right text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                  <p>Exec: {submission.execution_time_ms.toFixed(1)} ms</p>
                  <p>{new Date(submission.submitted_at).toLocaleTimeString()}</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-6 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                No verified submission found for this problem during the assessment window.
              </CardContent>
            </Card>
          )}

          {/* Student Submitted Code */}
          {submission && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs px-1">
                <span className="font-bold flex items-center gap-1.5" style={{ color: "var(--text-primary)" }}>
                  <Code2 className="w-4 h-4" style={{ color: "var(--accent-primary)" }} /> Candidate Submission ({submission.language})
                </span>
              </div>
              <pre className="p-4 rounded-xl border font-mono text-xs overflow-x-auto max-h-72" style={{ backgroundColor: "var(--bg-canvas)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}>
                {submission.code}
              </pre>
            </div>
          )}

          {/* Official Reference Solution */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
                <h3 className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-primary)" }}>
                  Official Reference Solutions
                </h3>
              </div>
              {areSolutionsReleased ? (
                <Badge variant="success" size="sm">Solutions Released</Badge>
              ) : (
                <Badge variant="warning" size="sm">
                  <Lock className="w-3 h-3 mr-1" /> Pending Release
                </Badge>
              )}
            </div>

            {areSolutionsReleased && activeQ?.reference_solutions ? (
              <div className="space-y-3">
                {/* Language Switcher */}
                <div className="flex items-center gap-1 p-1 rounded-lg border" style={{ backgroundColor: "var(--bg-canvas)", borderColor: "var(--border-subtle)" }}>
                  {(["python", "cpp", "c", "java"] as const).map((lang) => {
                    const hasCode = !!activeQ.reference_solutions?.[lang];
                    return (
                      <button
                        key={lang}
                        type="button"
                        onClick={() => setActiveSolLang(lang)}
                        className="px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5"
                        style={{
                          backgroundColor: activeSolLang === lang ? "var(--accent-primary)" : "transparent",
                          color: activeSolLang === lang ? "#ffffff" : hasCode ? "var(--text-secondary)" : "var(--text-muted)",
                          fontWeight: activeSolLang === lang ? 600 : 400
                        }}
                      >
                        {lang === "python" ? "Python 3" : lang === "cpp" ? "C++17" : lang === "c" ? "C (C11)" : "Java 17"}
                        {hasCode && <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--color-success)" }} />}
                      </button>
                    );
                  })}
                </div>

                <div className="relative">
                  {activeQ.reference_solutions[activeSolLang] ? (
                    <>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(activeQ.reference_solutions?.[activeSolLang] || "")}
                        className="absolute top-3 right-3 p-1.5 rounded-md text-xs flex items-center gap-1 border z-10 transition hover:opacity-80"
                        style={{
                          backgroundColor: "var(--bg-surface)",
                          borderColor: "var(--border-subtle)",
                          color: "var(--text-secondary)"
                        }}
                      >
                        {copiedCode ? <Check className="w-3.5 h-3.5" style={{ color: "var(--color-success)" }} /> : <Copy className="w-3.5 h-3.5" />}
                        <span className="text-[10px] font-medium">{copiedCode ? "Copied" : "Copy"}</span>
                      </button>
                      <pre className="p-4 pt-10 rounded-xl border font-mono text-xs overflow-x-auto max-h-80" style={{ backgroundColor: "var(--bg-canvas)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}>
                        {activeQ.reference_solutions[activeSolLang]}
                      </pre>
                    </>
                  ) : (
                    <div className="p-8 rounded-xl border text-center text-xs font-mono" style={{ backgroundColor: "var(--bg-canvas)", borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}>
                      No {activeSolLang.toUpperCase()} reference solution provided.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                  Official reference solutions and editorial breakdowns will be released by the Placement Committee once evaluation finishes.
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
