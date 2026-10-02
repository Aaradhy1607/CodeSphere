"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Question, QuestionType, BloomsLevel, QuestionStatus, DuplicateCheckResult, QuestionVersion, QuestionAnalytics } from "@/lib/types";
import { FormattedQuestionText } from "@/components/FormattedQuestionText";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableContainer } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import {
  PlusCircle, Sparkles, CheckCircle2,
  Search, Code2, Trash2, Eye,
  BarChart3, Upload, Image as ImageIcon,
  CheckCheck, AlertCircle, HelpCircle
} from "lucide-react";

export default function AdminQuestionsPage() {
  const router = useRouter();
  const { user, isAdmin, hasPermission, isLoading } = useAuth();
  const toast = useToast();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals & Panels
  const [isAuthoringModalOpen, setIsAuthoringModalOpen] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<Question | null>(null);
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null);
  const [questionToDelete, setQuestionToDelete] = useState<Question | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Review Dialog State
  const [reviewTarget, setReviewTarget] = useState<Question | null>(null);
  const [reviewAction, setReviewAction] = useState<"APPROVED" | "REJECTED">("APPROVED");
  const [reviewComment, setReviewComment] = useState("");
  const [reviewRating, setReviewRating] = useState(5);
  const [isReviewing, setIsReviewing] = useState(false);

  // Versions Modal
  const [versionTarget, setVersionTarget] = useState<Question | null>(null);
  const [versionsList, setVersionsList] = useState<QuestionVersion[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  // Analytics Modal
  const [analyticsTarget, setAnalyticsTarget] = useState<Question | null>(null);
  const [questionAnalytics, setQuestionAnalytics] = useState<QuestionAnalytics | null>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  // Authoring Form State
  const [authoringTab, setAuthoringTab] = useState<"GENERAL" | "CONTENT" | "DIAGRAM" | "CONFIG">("GENERAL");
  const [qType, setQType] = useState<QuestionType>("CODING");
  const [title, setTitle] = useState("");
  const [problemStatement, setProblemStatement] = useState("");
  const [subject, setSubject] = useState("Computer Science & Engineering");
  const [topic, setTopic] = useState("Data Structures & Algorithms");
  const [subtopic, setSubtopic] = useState("");
  const [bloomsLevel, setBloomsLevel] = useState<BloomsLevel>("APPLY");
  const [marks, setMarks] = useState(100);
  const [negativeMarks, setNegativeMarks] = useState(0);
  const [timeEstimate, setTimeEstimate] = useState(30);
  const [learningObjective, setLearningObjective] = useState("");
  const [conceptTagsStr, setConceptTagsStr] = useState("Arrays, Dynamic Programming");
  const [difficultyScore, setDifficultyScore] = useState(5);

  // MCQ Specific State
  const [optionsList, setOptionsList] = useState<string[]>(["", "", "", ""]);
  const [correctAnswer, setCorrectAnswer] = useState("A");
  const [explanation, setExplanation] = useState("");

  // Coding Specific State
  const [inputFormat, setInputFormat] = useState("");
  const [outputFormat, setOutputFormat] = useState("");
  const [constraints, setConstraints] = useState("");
  const [expectedTime, setExpectedTime] = useState("O(N)");
  const [expectedSpace, setExpectedSpace] = useState("O(1)");
  const [activeLangTab, setActiveLangTab] = useState<"python" | "cpp" | "c" | "java">("python");
  const [refSolutions, setRefSolutions] = useState<Record<string, string>>({
    python: "import sys\n\ndef solve():\n    # Python 3 Reference Solution\n    lines = sys.stdin.read().split()\n    if not lines:\n        return\n    # Write logic here\n\nif __name__ == '__main__':\n    solve()",
    cpp: "#include <iostream>\nusing namespace std;\n\nint main() {\n    // C++17 Solution\n    return 0;\n}",
    c: "#include <stdio.h>\n\nint main() {\n    // C11 Solution\n    return 0;\n}",
    java: "import java.util.Scanner;\n\npublic class Solution {\n    public static void main(String[] args) {\n        // Java Solution\n    }\n}"
  });
  const [testCasesList, setTestCasesList] = useState<{ id: string; input_data: string; expected_output: string; is_hidden: boolean; points: number }[]>([
    { id: "tc-1", input_data: "3\n1 2 3", expected_output: "6", is_hidden: false, points: 10 },
    { id: "tc-2", input_data: "4\n-1 -2 -3 -4", expected_output: "-1", is_hidden: true, points: 20 }
  ]);

  // Diagram / Image State
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isUploadingImage, setIsUploadingImage] = useState(false);

  // Duplicate Scanner State
  const [dupResult, setDupResult] = useState<DuplicateCheckResult | null>(null);
  const [isCheckingDup, setIsCheckingDup] = useState(false);

  const canAuthor = isAdmin || hasPermission("CREATE_QUESTION") || hasPermission("EDIT_QUESTION");
  const canReview = isAdmin || hasPermission("REVIEW_QUESTION");
  const canPublish = isAdmin || hasPermission("PUBLISH_ASSESSMENT") || hasPermission("CREATE_ASSESSMENT");

  const loadQuestions = () => {
    setLoading(true);
    setError(null);
    api.questions.list(
      statusFilter === "ALL" ? undefined : statusFilter,
      undefined,
      undefined,
      search,
      typeFilter === "ALL" ? undefined : typeFilter
    )
      .then(setQuestions)
      .catch((err) => {
        console.error(err);
        setError(err.message || "Failed to load question bank.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!isLoading && (!user || (!canAuthor && !canReview && !isAdmin))) {
      router.push("/");
      return;
    }
    if (user) {
      loadQuestions();
    }
  }, [user, isAdmin, isLoading, statusFilter, typeFilter, router]);

  const resetAuthoringForm = (q?: Question | null) => {
    if (q) {
      setEditingQuestion(q);
      setQType(q.question_type || "CODING");
      setTitle(q.title || "");
      setProblemStatement(q.problem_statement || "");
      setSubject(q.subject || "Computer Science & Engineering");
      setTopic(q.topic || (q.topic_tags && q.topic_tags[0]) || "Data Structures & Algorithms");
      setSubtopic(q.subtopic || "");
      setBloomsLevel(q.blooms_level || "APPLY");
      setMarks(q.marks || 100);
      setNegativeMarks(q.negative_marks || 0);
      setTimeEstimate(q.time_estimate_minutes || 30);
      setLearningObjective(q.learning_objective || "");
      setConceptTagsStr(q.concept_tags?.join(", ") || q.topic_tags?.join(", ") || "");
      setDifficultyScore(q.difficulty_score || 5);
      setInputFormat(q.input_format || "");
      setOutputFormat(q.output_format || "");
      setConstraints(q.constraints || "");
      setExpectedTime(q.expected_time_complexity || "O(N)");
      setExpectedSpace(q.expected_space_complexity || "O(1)");
      setExplanation(q.explanation || "");
      setCorrectAnswer(q.correct_answer || "A");
      setImageUrl(q.image_url || null);
      if (q.options && q.options.length > 0) {
        setOptionsList(q.options);
      } else {
        setOptionsList(["", "", "", ""]);
      }
      if (q.reference_solutions) {
        setRefSolutions({ ...refSolutions, ...q.reference_solutions });
      }
      if (q.test_cases && q.test_cases.length > 0) {
        setTestCasesList(q.test_cases.map(tc => ({
          id: `tc-${tc.id}`,
          input_data: tc.input_data,
          expected_output: tc.expected_output,
          is_hidden: tc.is_hidden,
          points: tc.points
        })));
      }
    } else {
      setEditingQuestion(null);
      setQType("CODING");
      setTitle("");
      setProblemStatement("");
      setSubject("Computer Science & Engineering");
      setTopic("Data Structures & Algorithms");
      setSubtopic("");
      setBloomsLevel("APPLY");
      setMarks(100);
      setNegativeMarks(0);
      setTimeEstimate(30);
      setLearningObjective("");
      setConceptTagsStr("Arrays, Dynamic Programming");
      setDifficultyScore(5);
      setInputFormat("");
      setOutputFormat("");
      setConstraints("");
      setExpectedTime("O(N)");
      setExpectedSpace("O(1)");
      setExplanation("");
      setCorrectAnswer("A");
      setImageUrl(null);
      setOptionsList(["", "", "", ""]);
      setTestCasesList([
        { id: "tc-1", input_data: "3\n1 2 3", expected_output: "6", is_hidden: false, points: 10 },
        { id: "tc-2", input_data: "4\n-1 -2 -3 -4", expected_output: "-1", is_hidden: true, points: 20 }
      ]);
    }
    setDupResult(null);
    setAuthoringTab("GENERAL");
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingImage(true);
    try {
      const res = await api.questions.uploadImage(file);
      setImageUrl(res.image_url);
      toast.success("Image diagram uploaded successfully");
    } catch (err: any) {
      toast.error(err.message || "Failed to upload image.");
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleRunDuplicateCheck = async () => {
    if (!title && !problemStatement) {
      toast.error("Please fill title or problem statement to scan for duplicates");
      return;
    }
    setIsCheckingDup(true);
    try {
      const res = await api.questions.checkDuplicate(title, problemStatement, editingQuestion?.id);
      setDupResult(res);
      if (res.is_duplicate) {
        toast.error(`Duplicate detected: ${res.match_reason}`);
      } else if (res.similarity_score > 0.5) {
        toast.warning(`Near match found (${res.normalized_similarity_percent}%): ${res.match_reason}`);
      } else {
        toast.success("No duplicate questions found. Ready for submission.");
      }
    } catch (err: any) {
      toast.error(err.message || "Duplicate check failed.");
    } finally {
      setIsCheckingDup(false);
    }
  };

  const handleSaveQuestion = async (targetStatus: QuestionStatus = "DRAFT") => {
    if (!title.trim() || !problemStatement.trim()) {
      toast.error("Title and Problem Statement are required.");
      return;
    }

    setIsSubmitting(true);
    const concept_tags = conceptTagsStr.split(",").map(t => t.trim()).filter(Boolean);

    const payload: any = {
      title,
      problem_statement: problemStatement,
      question_type: qType,
      subject,
      topic,
      subtopic: subtopic || undefined,
      blooms_level: bloomsLevel,
      marks: Number(marks),
      negative_marks: Number(negativeMarks),
      time_estimate_minutes: Number(timeEstimate),
      learning_objective: learningObjective || undefined,
      concept_tags,
      difficulty_score: difficultyScore,
      image_url: imageUrl || undefined,
      status: targetStatus
    };

    if (qType === "MCQ") {
      payload.options = optionsList.filter(o => o.trim().length > 0);
      payload.correct_answer = correctAnswer;
      payload.explanation = explanation;
    } else if (qType === "CODING") {
      payload.input_format = inputFormat;
      payload.output_format = outputFormat;
      payload.constraints = constraints;
      payload.expected_time_complexity = expectedTime;
      payload.expected_space_complexity = expectedSpace;
      payload.reference_solutions = refSolutions;
      payload.test_cases = testCasesList.map(tc => ({
        input_data: tc.input_data,
        expected_output: tc.expected_output,
        is_hidden: tc.is_hidden,
        points: tc.points
      }));
    } else {
      payload.explanation = explanation;
    }

    try {
      if (editingQuestion) {
        await api.questions.update(editingQuestion.id, payload);
        toast.success(`Question updated successfully (Status: ${targetStatus})`);
      } else {
        await api.questions.create(payload);
        toast.success(`Question created successfully (Status: ${targetStatus})`);
      }
      setIsAuthoringModalOpen(false);
      loadQuestions();
    } catch (err: any) {
      toast.error(err.message || "Failed to save question.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReviewSubmit = async () => {
    if (!reviewTarget) return;
    setIsReviewing(true);
    try {
      await api.questions.review(
        reviewTarget.id,
        reviewAction,
        reviewComment,
        reviewRating,
        reviewTarget.difficulty_score
      );
      toast.success(`Question successfully ${reviewAction.toLowerCase()}`);
      setReviewTarget(null);
      loadQuestions();
    } catch (err: any) {
      toast.error(err.message || "Failed to submit review decision.");
    } finally {
      setIsReviewing(false);
    }
  };

  const handleDirectPublish = async (q: Question) => {
    try {
      await api.questions.publish(q.id, true);
      toast.success(`Question #${q.id} successfully published to active question bank!`);
      loadQuestions();
    } catch (err: any) {
      toast.error(err.message || "Failed to publish question.");
    }
  };

  const handleOpenVersions = async (q: Question) => {
    setVersionTarget(q);
    setLoadingVersions(true);
    try {
      const vers = await api.questions.getVersions(q.id);
      setVersionsList(vers);
    } catch (err: any) {
      toast.error(err.message || "Failed to load version history.");
    } finally {
      setLoadingVersions(false);
    }
  };

  const handleOpenAnalytics = async (q: Question) => {
    setAnalyticsTarget(q);
    setLoadingAnalytics(true);
    try {
      const an = await api.questions.getAnalytics(q.id);
      setQuestionAnalytics(an);
    } catch (err: any) {
      toast.error(err.message || "Failed to load analytics telemetry.");
    } finally {
      setLoadingAnalytics(false);
    }
  };

  const handleDeleteQuestion = async () => {
    if (!questionToDelete) return;
    setIsDeleting(true);
    try {
      await api.questions.delete(questionToDelete.id);
      toast.success("Question deleted successfully.");
      setQuestionToDelete(null);
      loadQuestions();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete question.");
    } finally {
      setIsDeleting(false);
    }
  };

  const getStatusBadge = (status: QuestionStatus) => {
    switch (status) {
      case "PUBLISHED":
        return <Badge variant="success" className="font-semibold text-xs">PUBLISHED</Badge>;
      case "APPROVED":
        return <Badge variant="info" className="font-semibold text-xs">APPROVED</Badge>;
      case "PENDING_REVIEW":
        return <Badge variant="warning" className="font-semibold text-xs">PENDING REVIEW</Badge>;
      case "AI_GENERATED":
        return <Badge variant="default" className="bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 text-xs">AI CANDIDATE</Badge>;
      case "REJECTED":
        return <Badge variant="destructive" className="font-semibold text-xs">REJECTED</Badge>;
      case "ARCHIVED":
        return <Badge variant="neutral" className="font-semibold text-xs">ARCHIVED</Badge>;
      default:
        return <Badge variant="neutral" className="font-semibold text-xs">DRAFT</Badge>;
    }
  };

  const getTypeBadge = (type?: QuestionType) => {
    switch (type) {
      case "MCQ":
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">MCQ</span>;
      case "SUBJECTIVE":
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">SUBJECTIVE</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">CODING</span>;
    }
  };

  const getQualityBadge = (score?: number) => {
    if (score === undefined || score === null) return <span className="text-[var(--text-muted)] text-xs">N/A</span>;
    let color = "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
    if (score < 60) color = "text-rose-400 bg-rose-500/10 border-rose-500/20";
    else if (score < 80) color = "text-amber-400 bg-amber-500/10 border-amber-500/20";

    return (
      <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-xs font-mono font-bold ${color}`}>
        <span>{Math.round(score)}</span>
        <span className="text-[10px] text-[var(--text-muted)]">/100</span>
      </div>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border-default)] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">Question Bank & Review Hub</h1>
            <span className="text-xs px-2 py-0.5 bg-[var(--accent-subtle)] text-[var(--accent-text)] border border-[var(--accent-border)] rounded-full font-medium">Phase 4 Engine</span>
          </div>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Enterprise assessment repository with AI generation, manual authoring studio, multi-stage peer review, and deterministic quality verification.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/admin/ai-generator">
            <Button variant="secondary" className="gap-2">
              <Sparkles className="w-4 h-4 text-[var(--accent-primary)]" />
              AI Question Synthesis
            </Button>
          </Link>
          {canAuthor && (
            <Button
              variant="primary"
              onClick={() => {
                resetAuthoringForm(null);
                setIsAuthoringModalOpen(true);
              }}
              className="gap-2"
            >
              <PlusCircle className="w-4 h-4" />
              Author Question
            </Button>
          )}
        </div>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border-default)] pb-2 text-xs">
          {[
            { id: "ALL", label: "All Questions" },
            { id: "PUBLISHED", label: "Published" },
            { id: "APPROVED", label: "Approved" },
            { id: "PENDING_REVIEW", label: "Pending Review" },
            { id: "AI_GENERATED", label: "AI Candidates" },
            { id: "DRAFT", label: "Drafts" },
            { id: "REJECTED", label: "Rejected" }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                statusFilter === tab.id
                  ? "bg-[var(--accent-primary)] text-white shadow-sm"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadQuestions()}
              placeholder="Search by title, topic, subject, or concept tags..."
              className="pl-9"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="w-44">
              <Select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="text-xs"
              >
                <option value="ALL">All Types</option>
                <option value="CODING">Coding Problems</option>
                <option value="MCQ">Multiple Choice (MCQ)</option>
                <option value="SUBJECTIVE">Subjective Questions</option>
              </Select>
            </div>
            <Button variant="ghost" size="sm" onClick={loadQuestions}>
              Refresh
            </Button>
          </div>
        </div>
      </div>

      {/* Main Table */}
      {loading ? (
        <LoadingState message="Loading questions from repository..." />
      ) : error ? (
        <Card className="p-6 text-center border-danger/30 bg-danger/5">
          <AlertCircle className="w-8 h-8 text-danger mx-auto mb-2" />
          <p className="text-sm text-danger font-medium">{error}</p>
          <Button variant="outline" size="sm" onClick={loadQuestions} className="mt-4">Retry</Button>
        </Card>
      ) : questions.length === 0 ? (
        <EmptyState
          title="No Questions Found"
          description="No questions match your current status or filter parameters."
          actionLabel="Create First Question"
          onAction={() => {
            resetAuthoringForm(null);
            setIsAuthoringModalOpen(true);
          }}
        />
      ) : (
        <TableContainer>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>Question Details</TableHead>
                <TableHead className="w-28">Type</TableHead>
                <TableHead className="w-28">Difficulty</TableHead>
                <TableHead className="w-28">Quality</TableHead>
                <TableHead className="w-32">Status</TableHead>
                <TableHead className="w-20">Ver</TableHead>
                <TableHead className="text-right w-44">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {questions.map((q) => (
                <TableRow key={q.id}>
                  <TableCell className="font-mono text-xs text-[var(--text-muted)]">#{q.id}</TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)] transition-colors cursor-pointer" onClick={() => setSelectedQuestion(q)}>
                          {q.title}
                        </span>
                        {q.is_ai_generated && (
                          <span className="inline-flex items-center gap-1 text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-1.5 py-0.2 rounded">
                            <Sparkles className="w-2.5 h-2.5" /> AI
                          </span>
                        )}
                        {q.image_url && (
                          <span className="inline-flex items-center gap-1 text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.2 rounded" title="Includes Diagram">
                            <ImageIcon className="w-2.5 h-2.5" /> Diagram
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                        <span>{q.subject || "Computer Science"}</span>
                        <span>•</span>
                        <span className="text-[var(--accent-primary)] font-medium">{q.topic || "DSA"}</span>
                        {q.blooms_level && (
                          <>
                            <span>•</span>
                            <span className="text-[var(--text-muted)] uppercase text-[10px]">{q.blooms_level}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>{getTypeBadge(q.question_type)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: q.difficulty_score && q.difficulty_score > 7 ? '#ef4444' : q.difficulty_score && q.difficulty_score > 4 ? '#f59e0b' : '#10b981' }} />
                      <span className="text-xs font-mono font-medium">{q.difficulty_score || 5}/10</span>
                    </div>
                  </TableCell>
                  <TableCell>{getQualityBadge(q.quality_score)}</TableCell>
                  <TableCell>{getStatusBadge(q.status)}</TableCell>
                  <TableCell>
                    <button
                      onClick={() => handleOpenVersions(q)}
                      className="text-xs font-mono text-[var(--accent-primary)] hover:underline"
                    >
                      v{q.version_number || 1}
                    </button>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedQuestion(q)}
                        title="Preview Problem"
                        className="h-8 w-8 p-0"
                      >
                        <Eye className="w-4 h-4 text-[var(--text-muted)]" />
                      </Button>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenAnalytics(q)}
                        title="Question Analytics Telemetry"
                        className="h-8 w-8 p-0"
                      >
                        <BarChart3 className="w-4 h-4 text-[var(--text-muted)]" />
                      </Button>

                      {canReview && (q.status === "PENDING_REVIEW" || q.status === "AI_GENERATED") && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setReviewTarget(q);
                            setReviewAction("APPROVED");
                            setReviewComment("");
                          }}
                          className="h-8 px-2 text-xs gap-1 text-emerald-400"
                        >
                          <CheckCheck className="w-3.5 h-3.5" /> Review
                        </Button>
                      )}

                      {canPublish && (q.status === "APPROVED" || q.status === "DRAFT") && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDirectPublish(q)}
                          className="h-8 px-2 text-xs text-[var(--accent-primary)]"
                        >
                          Publish
                        </Button>
                      )}

                      {canAuthor && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            resetAuthoringForm(q);
                            setIsAuthoringModalOpen(true);
                          }}
                          title="Edit Question"
                          className="h-8 w-8 p-0"
                        >
                          <Code2 className="w-4 h-4 text-[var(--text-muted)]" />
                        </Button>
                      )}

                      {isAdmin && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setQuestionToDelete(q)}
                          title="Delete"
                          className="h-8 w-8 p-0 text-[var(--status-error-text)] hover:bg-[var(--status-error-bg)]"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* ================= MODAL: QUESTION AUTHORING STUDIO ================= */}
      {isAuthoringModalOpen && (
        <Modal
          isOpen={isAuthoringModalOpen}
          onClose={() => setIsAuthoringModalOpen(false)}
          title={editingQuestion ? `Edit Question: ${editingQuestion.title}` : "Author New Assessment Question"}
          size="xl"
        >
          <div className="space-y-5 max-h-[75vh] overflow-y-auto pr-1">
            {/* Studio Navigation Tabs */}
            <div className="flex border-b border-[var(--border-default)] text-xs gap-4 font-medium">
              {[
                { id: "GENERAL", label: "1. Taxonomy & Metadata" },
                { id: "CONTENT", label: "2. Question & Answers" },
                { id: "DIAGRAM", label: "3. Diagram & Media" },
                { id: "CONFIG", label: "4. Constraints & Testcases" }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setAuthoringTab(tab.id as any)}
                  className={`pb-2 transition-all border-b-2 ${
                    authoringTab === tab.id
                      ? "border-[var(--accent-primary)] text-[var(--accent-primary)] font-semibold"
                      : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* TAB 1: GENERAL TAXONOMY */}
            {authoringTab === "GENERAL" && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Question Type</label>
                    <div className="mt-1">
                      <Select
                        value={qType}
                        onChange={(e) => setQType(e.target.value as QuestionType)}
                      >
                        <option value="CODING">Algorithmic / Coding Problem</option>
                        <option value="MCQ">Multiple Choice Question (MCQ)</option>
                        <option value="SUBJECTIVE">Subjective / Short Answer</option>
                      </Select>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Bloom's Taxonomy Level</label>
                    <div className="mt-1">
                      <Select
                        value={bloomsLevel}
                        onChange={(e) => setBloomsLevel(e.target.value as BloomsLevel)}
                      >
                        <option value="REMEMBER">Remember (Recall Facts)</option>
                        <option value="UNDERSTAND">Understand (Explain Ideas)</option>
                        <option value="APPLY">Apply (Execute / Implement)</option>
                        <option value="ANALYZE">Analyze (Differentiate / Relate)</option>
                        <option value="EVALUATE">Evaluate (Critique / Judge)</option>
                        <option value="CREATE">Create (Synthesize / Design)</option>
                      </Select>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Subject Domain</label>
                    <Input
                      value={subject}
                      onChange={(e) => setSubject(e.target.value)}
                      placeholder="e.g. Computer Science, AI/ML"
                      className="mt-1"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Primary Topic</label>
                    <Input
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder="e.g. Graph Theory, Dynamic Programming"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Subtopic / Specialization</label>
                    <Input
                      value={subtopic}
                      onChange={(e) => setSubtopic(e.target.value)}
                      placeholder="e.g. Topological Sort, Shortest Path"
                      className="mt-1"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Difficulty (1-10)</label>
                    <Input
                      type="number"
                      min={1}
                      max={10}
                      value={difficultyScore}
                      onChange={(e) => setDifficultyScore(Number(e.target.value))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Marks / Points</label>
                    <Input
                      type="number"
                      value={marks}
                      onChange={(e) => setMarks(Number(e.target.value))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Negative Marking</label>
                    <Input
                      type="number"
                      step="0.25"
                      value={negativeMarks}
                      onChange={(e) => setNegativeMarks(Number(e.target.value))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Time Estimate (Min)</label>
                    <Input
                      type="number"
                      value={timeEstimate}
                      onChange={(e) => setTimeEstimate(Number(e.target.value))}
                      className="mt-1"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Learning Objective</label>
                  <Input
                    value={learningObjective}
                    onChange={(e) => setLearningObjective(e.target.value)}
                    placeholder="e.g. Assess student ability to optimize memory consumption in recursion graphs"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Concept Tags (comma-separated)</label>
                  <Input
                    value={conceptTagsStr}
                    onChange={(e) => setConceptTagsStr(e.target.value)}
                    placeholder="Arrays, Binary Search, Sliding Window"
                    className="mt-1"
                  />
                </div>
              </div>
            )}

            {/* TAB 2: CONTENT & ANSWERS */}
            {authoringTab === "CONTENT" && (
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Question Title</label>
                  <Input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Autonomous Drone Path Energy Minimization"
                    className="mt-1 font-medium"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Problem Statement / Prompt</label>
                  <Textarea
                    value={problemStatement}
                    onChange={(e) => setProblemStatement(e.target.value)}
                    rows={6}
                    placeholder="Describe the problem context, inputs, rules, and mathematical properties..."
                    className="mt-1 font-mono text-xs"
                  />
                </div>

                {/* MCQ Options Config */}
                {qType === "MCQ" && (
                  <div className="space-y-3 p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-subtle)]/40">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-[var(--text-primary)]">Multiple Choice Options</label>
                      <span className="text-[11px] text-[var(--text-muted)]">Select the radio button for the correct key</span>
                    </div>

                    {optionsList.map((opt, idx) => {
                      const letter = String.fromCharCode(65 + idx);
                      return (
                        <div key={idx} className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setCorrectAnswer(letter)}
                            className={`w-7 h-7 rounded-full text-xs font-bold transition-all ${
                              correctAnswer === letter
                                ? "bg-[var(--accent-primary)] text-white ring-2 ring-[var(--accent-primary)]/30"
                                : "bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-muted)] hover:border-[var(--accent-primary)]"
                            }`}
                          >
                            {letter}
                          </button>
                          <Input
                            value={opt}
                            onChange={(e) => {
                              const next = [...optionsList];
                              next[idx] = e.target.value;
                              setOptionsList(next);
                            }}
                            placeholder={`Option ${letter} text...`}
                            className="flex-1"
                          />
                        </div>
                      );
                    })}

                    <div>
                      <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Solution Explanation</label>
                      <Textarea
                        value={explanation}
                        onChange={(e) => setExplanation(e.target.value)}
                        rows={3}
                        placeholder="Detailed pedagogical explanation why the chosen option is correct..."
                        className="mt-1 text-xs"
                      />
                    </div>
                  </div>
                )}

                {/* Subjective Explanation / Rubric */}
                {qType === "SUBJECTIVE" && (
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Expected Solution Rubric / Key Points</label>
                    <Textarea
                      value={explanation}
                      onChange={(e) => setExplanation(e.target.value)}
                      rows={4}
                      placeholder="Outline key concepts, formulas, and diagrams that the evaluator must look for..."
                      className="mt-1 text-xs"
                    />
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: DIAGRAM & MEDIA */}
            {authoringTab === "DIAGRAM" && (
              <div className="space-y-4">
                <div className="p-6 rounded-xl border-2 border-dashed border-[var(--border-default)] text-center space-y-3 bg-[var(--bg-subtle)]/20">
                  {imageUrl ? (
                    <div className="space-y-3">
                      <div className="relative inline-block border border-[var(--border-default)] rounded-lg overflow-hidden max-w-md mx-auto shadow-sm">
                        <img src={imageUrl} alt="Question Schematic" className="max-h-60 w-auto object-contain mx-auto" />
                      </div>
                      <div className="flex justify-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setImageUrl(null)}
                          className="text-[var(--status-error-text)]"
                        >
                          Remove Diagram
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <ImageIcon className="w-10 h-10 text-[var(--text-muted)] mx-auto" />
                      <p className="text-sm font-medium text-[var(--text-primary)]">Upload Technical Architecture or Schematic Diagram</p>
                      <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">Supports PNG, JPEG, WEBP or GIF up to 5MB. Diagrams are served statically and passed to Gemini multimodal context during synthesis.</p>
                      <div className="pt-2">
                        <label className="cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-primary)] text-white rounded-lg text-xs font-medium hover:bg-[var(--accent-hover)] transition-colors">
                          <Upload className="w-3.5 h-3.5" />
                          {isUploadingImage ? "Uploading..." : "Browse Image File"}
                          <input
                            type="file"
                            accept="image/png,image/jpeg,image/webp,image/gif"
                            onChange={handleImageUpload}
                            disabled={isUploadingImage}
                            className="hidden"
                          />
                        </label>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 4: CODING CONFIG & TEST CASES */}
            {authoringTab === "CONFIG" && qType === "CODING" && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Input Format</label>
                    <Textarea
                      value={inputFormat}
                      onChange={(e) => setInputFormat(e.target.value)}
                      rows={3}
                      placeholder="e.g. First line contains N, followed by N integers..."
                      className="mt-1 font-mono text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Output Format</label>
                    <Textarea
                      value={outputFormat}
                      onChange={(e) => setOutputFormat(e.target.value)}
                      rows={3}
                      placeholder="e.g. Single integer representing minimal energy required..."
                      className="mt-1 font-mono text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Constraints</label>
                    <Input
                      value={constraints}
                      onChange={(e) => setConstraints(e.target.value)}
                      placeholder="1 <= N <= 10^5"
                      className="mt-1 font-mono text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Expected Time Complexity</label>
                    <Input
                      value={expectedTime}
                      onChange={(e) => setExpectedTime(e.target.value)}
                      placeholder="O(N log N)"
                      className="mt-1 font-mono text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Expected Space Complexity</label>
                    <Input
                      value={expectedSpace}
                      onChange={(e) => setExpectedSpace(e.target.value)}
                      placeholder="O(1)"
                      className="mt-1 font-mono text-xs"
                    />
                  </div>
                </div>

                {/* Reference Solutions */}
                <div className="space-y-2 pt-2 border-t border-[var(--border-default)]">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-[var(--text-primary)] uppercase">Golden Reference Solution</label>
                    <div className="flex gap-1">
                      {(["python", "cpp", "c", "java"] as const).map(lang => (
                        <button
                          key={lang}
                          type="button"
                          onClick={() => setActiveLangTab(lang)}
                          className={`px-2 py-1 rounded text-xs font-mono font-medium ${
                            activeLangTab === lang
                              ? "bg-[var(--accent-primary)] text-white"
                              : "bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          {lang.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>
                  <Textarea
                    value={refSolutions[activeLangTab] || ""}
                    onChange={(e) => setRefSolutions({ ...refSolutions, [activeLangTab]: e.target.value })}
                    rows={6}
                    className="font-mono text-xs"
                  />
                </div>

                {/* Test Cases Table */}
                <div className="space-y-2 pt-2 border-t border-[var(--border-default)]">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-[var(--text-primary)] uppercase">Evaluation Test Vectors</label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setTestCasesList([...testCasesList, { id: `tc-${Date.now()}`, input_data: "", expected_output: "", is_hidden: true, points: 10 }])}
                      className="h-7 text-xs"
                    >
                      + Add Vector
                    </Button>
                  </div>

                  {testCasesList.map((tc, idx) => (
                    <div key={tc.id} className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)]/30 space-y-2">
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span>Test Vector #{idx + 1} {tc.is_hidden ? "(Hidden Evaluator)" : "(Public Sample)"}</span>
                        <div className="flex items-center gap-3">
                          <label className="flex items-center gap-1 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={tc.is_hidden}
                              onChange={(e) => {
                                const next = [...testCasesList];
                                next[idx].is_hidden = e.target.checked;
                                setTestCasesList(next);
                              }}
                            />
                            <span>Hidden</span>
                          </label>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setTestCasesList(testCasesList.filter((_, i) => i !== idx))}
                            className="h-6 w-6 p-0 text-[var(--status-error-text)]"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <Textarea
                          placeholder="Input Data"
                          value={tc.input_data}
                          onChange={(e) => {
                            const next = [...testCasesList];
                            next[idx].input_data = e.target.value;
                            setTestCasesList(next);
                          }}
                          rows={2}
                          className="font-mono text-xs"
                        />
                        <Textarea
                          placeholder="Expected Output"
                          value={tc.expected_output}
                          onChange={(e) => {
                            const next = [...testCasesList];
                            next[idx].expected_output = e.target.value;
                            setTestCasesList(next);
                          }}
                          rows={2}
                          className="font-mono text-xs"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Duplicate Scan Bar */}
            <div className="p-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-subtle)]/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-[var(--text-muted)]" />
                <span className="text-xs text-[var(--text-muted)]">
                  {dupResult
                    ? dupResult.is_duplicate
                      ? `⚠️ ${dupResult.match_reason}`
                      : `✅ Clean: ${dupResult.match_reason}`
                    : "Scan question database to prevent duplicate content before saving."}
                </span>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleRunDuplicateCheck}
                disabled={isCheckingDup}
                className="text-xs"
              >
                {isCheckingDup ? "Scanning..." : "Check Duplicates"}
              </Button>
            </div>
          </div>

          {/* Modal Actions */}
          <div className="flex items-center justify-between border-t border-[var(--border-default)] pt-4 mt-4">
            <Button variant="ghost" onClick={() => setIsAuthoringModalOpen(false)}>
              Cancel
            </Button>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => handleSaveQuestion("DRAFT")}
                disabled={isSubmitting}
              >
                Save Draft
              </Button>
              <Button
                variant="secondary"
                onClick={() => handleSaveQuestion("PENDING_REVIEW")}
                disabled={isSubmitting}
                className="text-amber-400"
              >
                Submit for Review
              </Button>
              {canPublish && (
                <Button
                  variant="primary"
                  onClick={() => handleSaveQuestion("PUBLISHED")}
                  disabled={isSubmitting}
                >
                  Publish Question
                </Button>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* ================= MODAL: PEER REVIEW & APPROVAL ================= */}
      {reviewTarget && (
        <Modal
          isOpen={!!reviewTarget}
          onClose={() => setReviewTarget(null)}
          title={`Peer Review: ${reviewTarget.title}`}
          size="md"
        >
          <div className="space-y-4">
            <div className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)]/50 text-xs space-y-1">
              <div className="font-semibold text-[var(--text-primary)]">Question #{reviewTarget.id}</div>
              <div className="text-[var(--text-muted)]">Type: <span className="text-[var(--text-primary)] font-medium">{reviewTarget.question_type}</span> • Topic: <span className="text-[var(--text-primary)] font-medium">{reviewTarget.topic}</span></div>
              <div className="text-[var(--text-muted)]">Quality Score: <span className="text-emerald-400 font-bold">{Math.round(reviewTarget.quality_score || 0)}/100</span></div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Review Decision</label>
              <div className="grid grid-cols-2 gap-3 mt-1.5">
                <button
                  type="button"
                  onClick={() => setReviewAction("APPROVED")}
                  className={`p-3 rounded-lg border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                    reviewAction === "APPROVED"
                      ? "border-emerald-500 bg-emerald-500/10 text-emerald-400 shadow-sm"
                      : "border-[var(--border-default)] text-[var(--text-muted)] hover:border-emerald-500/40"
                  }`}
                >
                  <CheckCircle2 className="w-4 h-4" /> Approve Question
                </button>
                <button
                  type="button"
                  onClick={() => setReviewAction("REJECTED")}
                  className={`p-3 rounded-lg border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
                    reviewAction === "REJECTED"
                      ? "border-rose-500 bg-rose-500/10 text-rose-400 shadow-sm"
                      : "border-[var(--border-default)] text-[var(--text-muted)] hover:border-rose-500/40"
                  }`}
                >
                  <AlertCircle className="w-4 h-4" /> Request Revision / Reject
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Pedagogical Quality Rating</label>
              <div className="flex gap-2 mt-1">
                {[1, 2, 3, 4, 5].map(star => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setReviewRating(star)}
                    className={`w-8 h-8 rounded-lg font-bold text-xs ${
                      reviewRating >= star
                        ? "bg-[var(--accent-primary)] text-white"
                        : "bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-muted)]"
                    }`}
                  >
                    {star}★
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Reviewer Feedback & Notes</label>
              <Textarea
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
                rows={3}
                placeholder="State specific reasons, required modifications, or commendations..."
                className="mt-1 text-xs"
              />
            </div>

            <div className="flex justify-end gap-2 border-t border-[var(--border-default)] pt-4">
              <Button variant="ghost" onClick={() => setReviewTarget(null)}>Cancel</Button>
              <Button
                onClick={handleReviewSubmit}
                disabled={isReviewing}
                variant={reviewAction === "APPROVED" ? "primary" : "destructive"}
              >
                {isReviewing ? "Submitting..." : "Confirm Decision"}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* ================= MODAL: VERSION HISTORY ================= */}
      {versionTarget && (
        <Modal
          isOpen={!!versionTarget}
          onClose={() => setVersionTarget(null)}
          title={`Revision History: ${versionTarget.title}`}
          size="md"
        >
          <div className="space-y-4">
            <p className="text-xs text-[var(--text-muted)]">
              Published questions produce immutable version chains to ensure historical student assessments and submissions remain tamper-proof.
            </p>

            {loadingVersions ? (
              <LoadingState message="Fetching version lineage..." />
            ) : versionsList.length === 0 ? (
              <div className="text-center py-6 text-xs text-[var(--text-muted)]">No alternate versions found. This is Version 1.</div>
            ) : (
              <div className="space-y-2">
                {versionsList.map((ver) => (
                  <div
                    key={ver.id}
                    className={`p-3 rounded-lg border text-xs flex items-center justify-between ${
                      ver.id === versionTarget.id
                        ? "border-[var(--accent-primary)]/40 bg-[var(--accent-primary)]/5"
                        : "border-[var(--border-default)] bg-[var(--bg-subtle)]/30"
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-[var(--text-primary)]">v{ver.version_number}</span>
                        {ver.is_latest && <Badge variant="info" className="text-[10px] py-0">LATEST</Badge>}
                        <span className="text-[var(--text-muted)]">#{ver.id}</span>
                      </div>
                      <div className="text-[11px] text-[var(--text-muted)] mt-0.5">
                        {ver.change_summary || "Automated revision snapshot"}
                      </div>
                    </div>
                    <div className="text-right text-[11px] text-[var(--text-muted)]">
                      {new Date(ver.created_at).toLocaleDateString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* ================= MODAL: QUESTION ANALYTICS ================= */}
      {analyticsTarget && (
        <Modal
          isOpen={!!analyticsTarget}
          onClose={() => setAnalyticsTarget(null)}
          title={`Performance Telemetry: ${analyticsTarget.title}`}
          size="md"
        >
          {loadingAnalytics ? (
            <LoadingState message="Aggregating telemetry..." />
          ) : questionAnalytics ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)]/40 text-center">
                  <div className="text-xs text-[var(--text-muted)]">Total Attempts</div>
                  <div className="text-lg font-bold text-[var(--text-primary)] font-mono">{questionAnalytics.total_attempts}</div>
                </div>
                <div className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)]/40 text-center">
                  <div className="text-xs text-[var(--text-muted)]">Success Rate</div>
                  <div className="text-lg font-bold text-emerald-400 font-mono">{questionAnalytics.success_rate_percent}%</div>
                </div>
                <div className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)]/40 text-center">
                  <div className="text-xs text-[var(--text-muted)]">Calibrated Diff</div>
                  <div className="text-lg font-bold text-amber-400 font-mono">{questionAnalytics.experienced_difficulty}/10</div>
                </div>
                <div className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)]/40 text-center">
                  <div className="text-xs text-[var(--text-muted)]">Discrimination Index</div>
                  <div className="text-lg font-bold text-[var(--accent-primary)] font-mono">{questionAnalytics.discrimination_index !== undefined && questionAnalytics.discrimination_index !== null ? questionAnalytics.discrimination_index : "N/A"}</div>
                </div>
              </div>

              <div className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)]/30 space-y-2">
                <div className="text-xs font-bold text-[var(--text-primary)] uppercase">Quality Scoring Breakdown</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(questionAnalytics.quality_breakdown || {}).map(([dim, val]) => (
                    <div key={dim} className="flex justify-between items-center bg-[var(--bg-surface)] p-2 rounded border border-[var(--border-default)]">
                      <span className="capitalize text-[var(--text-muted)]">{dim.replace(/_/g, " ")}:</span>
                      <span className="font-mono font-bold text-[var(--accent-primary)]">{String(val)}/100</span>
                    </div>
                  ))}
                </div>
              </div>

              {!questionAnalytics.sample_size_reliable && (
                <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Telemetry is preliminary. A minimum of 5 student attempts is required for statistically validated calibration.</span>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-6 text-xs text-[var(--text-muted)]">No telemetry available.</div>
          )}
        </Modal>
      )}

      {/* ================= MODAL: PREVIEW QUESTION ================= */}
      {selectedQuestion && (
        <Modal
          isOpen={!!selectedQuestion}
          onClose={() => setSelectedQuestion(null)}
          title={`Question Preview: ${selectedQuestion.title}`}
          size="lg"
        >
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
            <div className="flex items-center gap-2">
              {getTypeBadge(selectedQuestion.question_type)}
              <Badge variant="neutral" className="font-mono text-xs">{selectedQuestion.difficulty_score || 5}/10</Badge>
              {getStatusBadge(selectedQuestion.status)}
            </div>

            {selectedQuestion.image_url && (
              <div className="border border-[var(--border-default)] rounded-lg p-2 bg-[var(--bg-surface)] text-center">
                <img src={selectedQuestion.image_url} alt="Problem Schematic" className="max-h-64 object-contain mx-auto" />
              </div>
            )}

            <div className="p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-subtle)]/30">
              <FormattedQuestionText text={selectedQuestion.problem_statement} />
            </div>

            {selectedQuestion.question_type === "MCQ" && selectedQuestion.options && (
              <div className="space-y-2">
                <div className="text-xs font-bold text-[var(--text-primary)] uppercase">Options:</div>
                <div className="grid grid-cols-1 gap-2">
                  {selectedQuestion.options.map((opt, i) => {
                    const letter = String.fromCharCode(65 + i);
                    const isCorrect = selectedQuestion.correct_answer === letter;
                    return (
                      <div
                        key={i}
                        className={`p-2.5 rounded-lg border text-xs flex items-center gap-3 ${
                          isCorrect
                            ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-300 font-semibold"
                            : "border-[var(--border-default)] bg-[var(--bg-surface)]"
                        }`}
                      >
                        <span className="w-5 h-5 rounded-full bg-[var(--bg-subtle)] flex items-center justify-center font-bold font-mono">{letter}</span>
                        <span>{opt}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Delete Confirmation */}
      {questionToDelete && (
        <ConfirmDialog
          isOpen={!!questionToDelete}
          onClose={() => setQuestionToDelete(null)}
          onConfirm={handleDeleteQuestion}
          title="Delete Question"
          message={`Are you sure you want to delete Question #${questionToDelete.id} ('${questionToDelete.title}')? This action cannot be undone.`}
          confirmText={isDeleting ? "Deleting..." : "Delete Permanently"}
          variant="destructive"
        />
      )}
    </div>
  );
}
