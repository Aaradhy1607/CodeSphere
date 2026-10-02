"use client";

import React, { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Question, Assessment } from "@/lib/types";
import {
  Shield, ArrowLeft, Plus, Trash2, AlertTriangle,
  BookOpen, Settings, Layers, Search, RefreshCw
} from "lucide-react";

interface AssessmentQuestionItem {
  question_id: number;
  section_name: string;
  order_index: number;
  marks: number;
  negative_marks: number;
  title: string;
  type: string;
  difficulty: string;
}

export default function EditAssessmentPage() {
  const router = useRouter();
  const params = useParams();
  const assessmentId = Number(params?.id);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [passPercentage, setPassPercentage] = useState(60);
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  const [shuffleQuestions, setShuffleQuestions] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(true);
  const [showResultsImmediately, setShowResultsImmediately] = useState(true);
  const [allowReview, setAllowReview] = useState(true);
  const [codeTestVisibleCount, setCodeTestVisibleCount] = useState(2);
  const [maxTabSwitches, setMaxTabSwitches] = useState(3);
  const [autoTerminateOnCheat, setAutoTerminateOnCheat] = useState(true);
  const [pasteDetectionEnabled, setPasteDetectionEnabled] = useState(true);
  const [fullscreenEnforced, setFullscreenEnforced] = useState(true);
  const [webcamProctoringEnabled, setWebcamProctoringEnabled] = useState(false);

  const [selectedQuestions, setSelectedQuestions] = useState<AssessmentQuestionItem[]>([]);

  // Question Picker
  const [isQuestionPickerOpen, setIsQuestionPickerOpen] = useState(false);
  const [availableQuestions, setAvailableQuestions] = useState<Question[]>([]);
  const [pickerSearch, setPickerSearch] = useState("");
  const [pickerTypeFilter, setPickerTypeFilter] = useState("ALL");
  const [pickerLoading, setPickerLoading] = useState(false);

  const pad = (n: number) => n.toString().padStart(2, "0");
  const formatDT = (dateStr: string) => {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  useEffect(() => {
    if (!assessmentId) return;

    const loadAssessment = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.assessments.get(assessmentId);
        setTitle(data.title);
        setDescription(data.description || "");
        setDurationMinutes(data.duration_minutes);
        setPassPercentage(data.pass_percentage);
        setMaxAttempts(data.max_attempts);
        setStartTime(formatDT(data.start_time));
        setEndTime(formatDT(data.end_time));

        setShuffleQuestions(data.shuffle_questions);
        setShuffleOptions(data.shuffle_options);
        setShowResultsImmediately(data.show_results_immediately);
        setAllowReview(data.allow_review);
        setCodeTestVisibleCount(data.code_test_visible_count);
        setMaxTabSwitches(data.max_tab_switches);
        setAutoTerminateOnCheat(data.auto_terminate_on_cheat);
        setPasteDetectionEnabled(data.paste_detection_enabled);
        setFullscreenEnforced(data.fullscreen_enforced);
        setWebcamProctoringEnabled(data.webcam_proctoring_enabled);

        if (data.questions) {
          setSelectedQuestions(
            data.questions.map((q: any, idx: number) => ({
              question_id: q.question_id,
              section_name: q.section_name || "General",
              order_index: q.order_index ?? idx,
              marks: q.marks ?? 5,
              negative_marks: q.negative_marks ?? 0,
              title: q.question?.title || `Question #${q.question_id}`,
              type: q.question?.question_type || "MCQ",
              difficulty: (q.question as any)?.difficulty || (q.question?.difficulty_score >= 7 ? "HARD" : q.question?.difficulty_score >= 4 ? "MEDIUM" : "EASY")
            }))
          );
        }
      } catch (err: any) {
        setError(err.message || "Failed to load assessment");
      } finally {
        setLoading(false);
      }
    };

    loadAssessment();
  }, [assessmentId]);

  const fetchAvailableQuestions = async () => {
    setPickerLoading(true);
    try {
      const qs = await api.questions.list();
      setAvailableQuestions(qs);
    } catch (err: any) {
      console.error("Failed to load questions:", err);
    } finally {
      setPickerLoading(false);
    }
  };

  const openQuestionPicker = () => {
    setIsQuestionPickerOpen(true);
    if (availableQuestions.length === 0) {
      fetchAvailableQuestions();
    }
  };

  const handleAddQuestion = (q: Question) => {
    if (selectedQuestions.some(sq => sq.question_id === q.id)) return;
    const defaultMarks = q.question_type === "CODING" ? 20 : 5;
    const defaultNegative = q.question_type === "CODING" ? 0 : 1;
    const defaultSection = q.question_type === "CODING" ? "Coding Section" : "General";
    const diff = (q as any).difficulty || (q.difficulty_score >= 7 ? "HARD" : q.difficulty_score >= 4 ? "MEDIUM" : "EASY");

    setSelectedQuestions(prev => [
      ...prev,
      {
        question_id: q.id,
        section_name: defaultSection,
        order_index: prev.length,
        marks: defaultMarks,
        negative_marks: defaultNegative,
        title: q.title,
        type: q.question_type || "MCQ",
        difficulty: diff
      }
    ]);
  };

  const handleRemoveQuestion = (qId: number) => {
    setSelectedQuestions(prev => prev.filter(q => q.question_id !== qId));
  };

  const handleUpdateQuestion = (qId: number, field: keyof AssessmentQuestionItem, value: any) => {
    setSelectedQuestions(prev =>
      prev.map(q => (q.question_id === qId ? { ...q, [field]: value } : q))
    );
  };

  const totalMarks = selectedQuestions.reduce((sum, q) => sum + (Number(q.marks) || 0), 0);

  const handleSubmit = async () => {
    if (!title.trim()) {
      setError("Please provide an assessment title");
      return;
    }
    if (selectedQuestions.length === 0) {
      setError("Please add at least one question to the assessment");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const payload = {
        title,
        description,
        duration_minutes: durationMinutes,
        pass_percentage: passPercentage,
        max_attempts: maxAttempts,
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        shuffle_questions: shuffleQuestions,
        shuffle_options: shuffleOptions,
        show_results_immediately: showResultsImmediately,
        allow_review: allowReview,
        code_test_visible_count: codeTestVisibleCount,
        max_tab_switches: maxTabSwitches,
        auto_terminate_on_cheat: autoTerminateOnCheat,
        paste_detection_enabled: pasteDetectionEnabled,
        fullscreen_enforced: fullscreenEnforced,
        webcam_proctoring_enabled: webcamProctoringEnabled,
        questions: selectedQuestions.map((q, idx) => ({
          question_id: q.question_id,
          section_name: q.section_name || "General",
          order_index: idx,
          marks: Number(q.marks) || 1,
          negative_marks: Number(q.negative_marks) || 0
        }))
      };

      await api.assessments.update(assessmentId, payload);
      router.push("/admin/assessments");
    } catch (err: any) {
      setError(err.message || "Failed to update assessment");
      setSaving(false);
    }
  };

  const filteredPickerQuestions = availableQuestions.filter(q => {
    const qTags = q.topic_tags || q.concept_tags || [];
    const matchesSearch =
      q.title.toLowerCase().includes(pickerSearch.toLowerCase()) ||
      qTags.some((t: string) => t.toLowerCase().includes(pickerSearch.toLowerCase()));
    const matchesType = pickerTypeFilter === "ALL" || q.question_type === pickerTypeFilter;
    return matchesSearch && matchesType;
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center p-8">
        <RefreshCw className="w-6 h-6 animate-spin text-[var(--accent-primary)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-6 lg:p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <Link href="/admin/assessments" className="hover:text-[var(--text-primary)] flex items-center gap-1 transition">
            <ArrowLeft className="w-4 h-4" /> Back to Assessments
          </Link>
          <span>/</span>
          <span className="text-[var(--text-primary)] font-medium">Edit Assessment #{assessmentId}</span>
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Edit Assessment</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Update test parameters, question allocations and proctoring thresholds.
            </p>
          </div>

          <button
            onClick={handleSubmit}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-sm font-semibold hover:opacity-90 transition disabled:opacity-50 shadow-sm"
          >
            {saving ? "Saving Changes..." : "Save Changes"}
          </button>
        </div>

        {error && (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Left Column: Form Details & Questions */}
          <div className="lg:col-span-2 space-y-6">
            
            <div className="p-6 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <h2 className="font-semibold text-base flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-[var(--accent-primary)]" /> General Details
              </h2>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Assessment Title *</label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Instructions & Description</label>
                  <textarea
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Start Date & Time</label>
                    <input
                      type="datetime-local"
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">End Date & Time</label>
                    <input
                      type="datetime-local"
                      value={endTime}
                      onChange={(e) => setEndTime(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Duration (Mins)</label>
                    <input
                      type="number"
                      min={5}
                      max={360}
                      value={durationMinutes}
                      onChange={(e) => setDurationMinutes(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Pass %</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={passPercentage}
                      onChange={(e) => setPassPercentage(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Max Attempts</label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={maxAttempts}
                      onChange={(e) => setMaxAttempts(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Questions List */}
            <div className="p-6 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-base flex items-center gap-2">
                    <Layers className="w-4 h-4 text-[var(--accent-primary)]" /> Exam Questions ({selectedQuestions.length})
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                    Total Marks: <span className="font-bold text-[var(--accent-primary)]">{totalMarks}</span>
                  </p>
                </div>

                <button
                  type="button"
                  onClick={openQuestionPicker}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--accent-primary)] text-white text-xs font-semibold hover:opacity-90 transition"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Questions
                </button>
              </div>

              <div className="space-y-3">
                {selectedQuestions.map((q, idx) => (
                  <div
                    key={q.question_id}
                    className="p-4 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)] space-y-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] flex items-center justify-center text-xs font-bold text-[var(--text-secondary)]">
                          {idx + 1}
                        </span>
                        <div>
                          <span className="font-semibold text-sm line-clamp-1">{q.title}</span>
                          <div className="flex items-center gap-2 text-[10px] text-[var(--text-muted)] mt-0.5">
                            <span className="px-1.5 py-0.2 rounded bg-[var(--bg-surface)] border border-[var(--border-subtle)] font-mono">{q.type}</span>
                            <span>•</span>
                            <span>{q.difficulty}</span>
                          </div>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleRemoveQuestion(q.question_id)}
                        className="p-1 rounded text-red-500 hover:bg-red-500/10 transition"
                        title="Remove question"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-[var(--border-subtle)] text-xs">
                      <div>
                        <label className="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">Section Name</label>
                        <input
                          type="text"
                          value={q.section_name}
                          onChange={(e) => handleUpdateQuestion(q.question_id, "section_name", e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-xs focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">Marks (+)</label>
                        <input
                          type="number"
                          min={0.5}
                          step={0.5}
                          value={q.marks}
                          onChange={(e) => handleUpdateQuestion(q.question_id, "marks", parseFloat(e.target.value))}
                          className="w-full px-2.5 py-1.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-xs focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">Negative Marks (-)</label>
                        <input
                          type="number"
                          min={0}
                          step={0.25}
                          value={q.negative_marks}
                          onChange={(e) => handleUpdateQuestion(q.question_id, "negative_marks", parseFloat(e.target.value))}
                          className="w-full px-2.5 py-1.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-xs focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* Right Column: Settings */}
          <div className="space-y-6">
            
            <div className="p-6 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <h2 className="font-semibold text-base flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-500" /> Security & Proctoring
              </h2>

              <div className="space-y-3">
                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <span className="text-xs font-semibold">Fullscreen Lockdown</span>
                  <input
                    type="checkbox"
                    checked={fullscreenEnforced}
                    onChange={(e) => setFullscreenEnforced(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <span className="text-xs font-semibold">Copy/Paste Interception</span>
                  <input
                    type="checkbox"
                    checked={pasteDetectionEnabled}
                    onChange={(e) => setPasteDetectionEnabled(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <span className="text-xs font-semibold">Auto-Terminate on Cheating</span>
                  <input
                    type="checkbox"
                    checked={autoTerminateOnCheat}
                    onChange={(e) => setAutoTerminateOnCheat(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <div>
                  <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Max Allowed Tab Switches</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={maxTabSwitches}
                    onChange={(e) => setMaxTabSwitches(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="p-6 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <h2 className="font-semibold text-base flex items-center gap-2">
                <Settings className="w-4 h-4 text-blue-500" /> Randomization & Rules
              </h2>

              <div className="space-y-3">
                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <span className="text-xs font-semibold">Shuffle Questions</span>
                  <input
                    type="checkbox"
                    checked={shuffleQuestions}
                    onChange={(e) => setShuffleQuestions(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <span className="text-xs font-semibold">Shuffle Options</span>
                  <input
                    type="checkbox"
                    checked={shuffleOptions}
                    onChange={(e) => setShuffleOptions(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <span className="text-xs font-semibold">Immediate Results</span>
                  <input
                    type="checkbox"
                    checked={showResultsImmediately}
                    onChange={(e) => setShowResultsImmediately(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <span className="text-xs font-semibold">Allow Solutions Review</span>
                  <input
                    type="checkbox"
                    checked={allowReview}
                    onChange={(e) => setAllowReview(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>
              </div>
            </div>

          </div>

        </div>

        {/* Question Selector Drawer / Modal */}
        {isQuestionPickerOpen && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl">
              
              <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-base">Select Questions</h3>
                  <p className="text-xs text-[var(--text-secondary)]">Pick questions to add to this assessment</p>
                </div>
                <button
                  onClick={() => setIsQuestionPickerOpen(false)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-subtle)]"
                >
                  Done
                </button>
              </div>

              <div className="p-4 border-b border-[var(--border-subtle)] grid grid-cols-1 sm:grid-cols-3 gap-2">
                <div className="sm:col-span-2 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                  <input
                    type="text"
                    value={pickerSearch}
                    onChange={(e) => setPickerSearch(e.target.value)}
                    placeholder="Search questions..."
                    className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-xs focus:outline-none"
                  />
                </div>
                <select
                  value={pickerTypeFilter}
                  onChange={(e) => setPickerTypeFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-xs focus:outline-none"
                >
                  <option value="ALL">All Types</option>
                  <option value="MCQ">MCQ</option>
                  <option value="MULTIPLE_SELECT">Multiple Select</option>
                  <option value="CODING">Coding</option>
                  <option value="SUBJECTIVE">Subjective</option>
                </select>
              </div>

              <div className="p-4 overflow-y-auto space-y-2 flex-1">
                {pickerLoading ? (
                  <p className="text-center text-xs py-8 text-[var(--text-secondary)]">Loading questions...</p>
                ) : filteredPickerQuestions.length === 0 ? (
                  <p className="text-center text-xs py-8 text-[var(--text-secondary)]">No matching questions found.</p>
                ) : (
                  filteredPickerQuestions.map((q) => {
                    const isSelected = selectedQuestions.some(sq => sq.question_id === q.id);
                    return (
                      <div
                        key={q.id}
                        className={`p-3 rounded-lg border transition flex items-center justify-between gap-3 ${
                          isSelected
                            ? "bg-[var(--accent-primary)]/5 border-[var(--accent-primary)]/40"
                            : "bg-[var(--bg-base)] border-[var(--border-subtle)] hover:border-[var(--border-hover)]"
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <h4 className="font-semibold text-xs truncate">{q.title}</h4>
                          <div className="flex items-center gap-2 text-[10px] text-[var(--text-secondary)] mt-0.5">
                            <span className="font-mono">{q.question_type}</span>
                            <span>•</span>
                            <span>Score: {q.difficulty_score || 5}/10</span>
                          </div>
                        </div>

                        {isSelected ? (
                          <button
                            type="button"
                            onClick={() => handleRemoveQuestion(q.id)}
                            className="px-2.5 py-1 rounded bg-red-500/10 text-red-500 text-xs font-semibold hover:bg-red-500/20"
                          >
                            Remove
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleAddQuestion(q)}
                            className="px-2.5 py-1 rounded bg-[var(--accent-primary)] text-white text-xs font-semibold hover:opacity-90"
                          >
                            Add
                          </button>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

            </div>
          </div>
        )}

      </div>
    </div>
  );
}
