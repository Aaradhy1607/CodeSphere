"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Question } from "@/lib/types";
import {
  Shield, ArrowLeft, Plus, Trash2, CheckCircle2, AlertTriangle,
  Clock, Calendar, Sparkles, BookOpen, Settings, Layers, Search, Eye
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

export default function CreateAssessmentPage() {
  const router = useRouter();

  // Basic Details
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [passPercentage, setPassPercentage] = useState(60);
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  // Exam Settings & Anti-Cheat
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

  // Questions Selected
  const [selectedQuestions, setSelectedQuestions] = useState<AssessmentQuestionItem[]>([]);

  // Question Picker Modal
  const [isQuestionPickerOpen, setIsQuestionPickerOpen] = useState(false);
  const [availableQuestions, setAvailableQuestions] = useState<Question[]>([]);
  const [pickerSearch, setPickerSearch] = useState("");
  const [pickerTypeFilter, setPickerTypeFilter] = useState("ALL");
  const [pickerLoading, setPickerLoading] = useState(false);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize start/end times with sensible defaults (starts today, ends in 7 days)
  useEffect(() => {
    const now = new Date();
    const pad = (n: number) => n.toString().padStart(2, "0");
    const formatDT = (d: Date) =>
      `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    
    setStartTime(formatDT(now));
    const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    setEndTime(formatDT(nextWeek));
  }, []);

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
    const defaultSection = q.question_type === "CODING" ? "Coding Section" : "Aptitude & Technical";
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

  const handleSubmit = async (publishImmediately: boolean = false) => {
    if (!title.trim()) {
      setError("Please provide an assessment title");
      return;
    }
    if (selectedQuestions.length === 0) {
      setError("Please add at least one question to the assessment");
      return;
    }
    if (!startTime || !endTime) {
      setError("Please specify valid start and end dates");
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

      const newAssessment = await api.assessments.create(payload);
      if (publishImmediately) {
        await api.assessments.publish(newAssessment.id);
      }
      router.push("/admin/assessments");
    } catch (err: any) {
      setError(err.message || "Failed to create assessment");
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

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-6 lg:p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <Link href="/admin/assessments" className="hover:text-[var(--text-primary)] flex items-center gap-1 transition">
            <ArrowLeft className="w-4 h-4" /> Back to Assessments
          </Link>
          <span>/</span>
          <span className="text-[var(--text-primary)] font-medium">Create Assessment</span>
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Create Secure Assessment</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Build a server-authoritative examination with deterministic randomization & proctoring.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => handleSubmit(false)}
              disabled={saving}
              className="px-4 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] text-sm font-semibold transition disabled:opacity-50"
            >
              Save as Draft
            </button>
            <button
              onClick={() => handleSubmit(true)}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-sm font-semibold hover:opacity-90 transition disabled:opacity-50 shadow-sm"
            >
              {saving ? "Creating..." : "Save & Publish"}
            </button>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Main Column: Basic Details & Question Section */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* General Info */}
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
                    placeholder="e.g., Campus Placement Round 1 - Full Stack & DSA"
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Instructions & Description</label>
                  <textarea
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Instructions for students regarding marking scheme, section rules, and proctoring policy..."
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">Start Date & Time (Window Opens) *</label>
                    <input
                      type="datetime-local"
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-[var(--text-secondary)]">End Date & Time (Window Closes) *</label>
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
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
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
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
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
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Questions Selection & Section Configuration */}
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
                  <Plus className="w-3.5 h-3.5" /> Add from Question Bank
                </button>
              </div>

              {selectedQuestions.length === 0 ? (
                <div className="p-8 text-center border-2 border-dashed border-[var(--border-subtle)] rounded-xl">
                  <BookOpen className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-2 opacity-50" />
                  <p className="text-sm font-medium">No questions added yet</p>
                  <p className="text-xs text-[var(--text-secondary)] mt-1">
                    Add MCQs, Multi-Select, Coding or Subjective questions from the question bank.
                  </p>
                  <button
                    type="button"
                    onClick={openQuestionPicker}
                    className="mt-3 inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-[var(--border-subtle)] text-xs font-semibold hover:bg-[var(--bg-subtle)] transition"
                  >
                    <Plus className="w-3.5 h-3.5" /> Select Questions
                  </button>
                </div>
              ) : (
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
                            placeholder="Section Name"
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
              )}
            </div>

          </div>

          {/* Right Column: Proctoring, Security & Randomization Settings */}
          <div className="space-y-6">
            
            {/* Anti-Cheating & Proctoring Policy */}
            <div className="p-6 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <h2 className="font-semibold text-base flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-500" /> Security & Proctoring
              </h2>

              <div className="space-y-3">
                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <div className="pr-2">
                    <span className="block text-xs font-semibold">Fullscreen Lockdown</span>
                    <span className="block text-[10px] text-[var(--text-secondary)]">Force full-screen mode before exam starts</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={fullscreenEnforced}
                    onChange={(e) => setFullscreenEnforced(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <div className="pr-2">
                    <span className="block text-xs font-semibold">Copy/Paste Interception</span>
                    <span className="block text-[10px] text-[var(--text-secondary)]">Prevent clipboard paste in code & subjective editor</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={pasteDetectionEnabled}
                    onChange={(e) => setPasteDetectionEnabled(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <div className="pr-2">
                    <span className="block text-xs font-semibold">Auto-Terminate on Cheating</span>
                    <span className="block text-[10px] text-[var(--text-secondary)]">Auto-submit when tab switch limit is exceeded</span>
                  </div>
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

            {/* Randomization & Delivery */}
            <div className="p-6 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-4">
              <h2 className="font-semibold text-base flex items-center gap-2">
                <Settings className="w-4 h-4 text-blue-500" /> Randomization & Rules
              </h2>

              <div className="space-y-3">
                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <div className="pr-2">
                    <span className="block text-xs font-semibold">Shuffle Questions</span>
                    <span className="block text-[10px] text-[var(--text-secondary)]">Deterministic random order per candidate</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={shuffleQuestions}
                    onChange={(e) => setShuffleQuestions(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <div className="pr-2">
                    <span className="block text-xs font-semibold">Shuffle MCQ Options</span>
                    <span className="block text-[10px] text-[var(--text-secondary)]">Deterministic random option letters per candidate</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={shuffleOptions}
                    onChange={(e) => setShuffleOptions(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <div className="pr-2">
                    <span className="block text-xs font-semibold">Immediate Results</span>
                    <span className="block text-[10px] text-[var(--text-secondary)]">Show scores right after submission</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={showResultsImmediately}
                    onChange={(e) => setShowResultsImmediately(e.target.checked)}
                    className="w-4 h-4 rounded text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] cursor-pointer">
                  <div className="pr-2">
                    <span className="block text-xs font-semibold">Allow Solutions Review</span>
                    <span className="block text-[10px] text-[var(--text-secondary)]">Allow candidate to inspect solutions & explanations</span>
                  </div>
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
                  <p className="text-xs text-[var(--text-secondary)]">Pick published questions to include in this assessment</p>
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
                  <p className="text-center text-xs py-8 text-[var(--text-secondary)]">Loading question bank...</p>
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
                            {q.topic_tags && q.topic_tags.length > 0 && (
                              <>
                                <span>•</span>
                                <span className="truncate">{q.topic_tags.slice(0, 3).join(", ")}</span>
                              </>
                            )}
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
