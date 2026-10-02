"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Question, QuestionType, BloomsLevel } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { FormattedQuestionText } from "@/components/FormattedQuestionText";
import { useToast } from "@/components/ui/Toast";
import {
  Sparkles, Sliders, CheckCircle2, Play,
  ChevronLeft, Upload, Image as ImageIcon,
  CheckCheck
} from "lucide-react";

export default function AIQuestionGeneratorPage() {
  const router = useRouter();
  const { user, isAdmin, hasPermission, isLoading } = useAuth();
  const toast = useToast();

  // Generator Controls State
  const [qType, setQType] = useState<QuestionType>("CODING");
  const [topic, setTopic] = useState("Dynamic Programming");
  const [subTopic, setSubTopic] = useState("Grid Navigation & Energy Optimization");
  const [bloomsLevel, setBloomsLevel] = useState<BloomsLevel>("APPLY");
  const [difficultyScore, setDifficultyScore] = useState(6);
  const [relativeDiff, setRelativeDiff] = useState("similar");
  const [marks, setMarks] = useState(100);
  const [negativeMarks, setNegativeMarks] = useState(0);
  const [timeEstimate, setTimeEstimate] = useState(30);
  const [learningObjective, setLearningObjective] = useState("");
  const [conceptTagsStr, setConceptTagsStr] = useState("Dynamic Programming, 2D Grid");
  const [targetBranch, setTargetBranch] = useState("ALL");
  const [targetYear, setTargetYear] = useState(3);
  const [blueprint, setBlueprint] = useState(
    "Robotic rover moving in a 2D matrix where each cell has a energy cost and certain cells contain recharging solar beacons. Needs O(M*N) DP solution."
  );

  // Multimodal Image Context State
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isUploadingImage, setIsUploadingImage] = useState(false);

  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedQuestion, setGeneratedQuestion] = useState<Question | null>(null);
  const [validationReport, setValidationReport] = useState<any>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isApproved, setIsApproved] = useState(false);
  const [activeSolLang, setActiveSolLang] = useState<"python" | "cpp" | "c" | "java">("python");

  const canAuthor = isAdmin || hasPermission("CREATE_QUESTION") || hasPermission("EDIT_QUESTION");
  const canPublish = isAdmin || hasPermission("PUBLISH_ASSESSMENT");

  useEffect(() => {
    if (!isLoading && (!user || (!canAuthor && !isAdmin))) {
      router.push("/");
    }
  }, [user, isAdmin, canAuthor, isLoading, router]);

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingImage(true);
    try {
      const res = await api.questions.uploadImage(file);
      setImageUrl(res.image_url);
      toast.success("Multimodal diagram uploaded! Gemini will analyze this visual context during question synthesis.");
    } catch (err: any) {
      toast.error(err.message || "Failed to upload image.");
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerating(true);
    setGeneratedQuestion(null);
    setValidationReport(null);
    setIsApproved(false);

    try {
      const concept_tags = conceptTagsStr.split(",").map(t => t.trim()).filter(Boolean);
      const res = await api.questions.generateAI({
        topic,
        sub_topic: subTopic,
        question_type: qType,
        difficulty_score: difficultyScore,
        relative_difficulty: relativeDiff,
        blooms_level: bloomsLevel,
        marks: Number(marks),
        negative_marks: Number(negativeMarks),
        time_estimate_minutes: Number(timeEstimate),
        learning_objective: learningObjective || undefined,
        concept_tags,
        image_url: imageUrl || undefined,
        reference_blueprint: blueprint,
        target_branch: targetBranch,
        target_year: targetYear
      });

      setGeneratedQuestion(res.question);
      setValidationReport(res.validation_report);
      toast.success("Synthesized new question with deterministic quality validation score");
    } catch (err: any) {
      toast.error(err.message || "AI problem generation failed. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRunValidation = async () => {
    if (!generatedQuestion) return;
    setIsValidating(true);
    try {
      const res = await api.questions.validate(generatedQuestion.id);
      setValidationReport(res);
      toast.success("Validation completed against sandbox execution runner");
    } catch (err: any) {
      toast.error(err.message || "Validation execution failed.");
    } finally {
      setIsValidating(false);
    }
  };

  const handlePublish = async () => {
    if (!generatedQuestion) return;
    try {
      await api.questions.publish(generatedQuestion.id, true);
      setIsApproved(true);
      toast.success("Question approved and published to official Question Bank!");
    } catch (err: any) {
      toast.error(err.message || "Failed to publish question.");
    }
  };

  const handleSubmitForReview = async () => {
    if (!generatedQuestion) return;
    try {
      await api.questions.review(generatedQuestion.id, "PENDING_REVIEW", "Submitted from AI Generator for peer curriculum review.");
      toast.success("Question submitted to Faculty Review Queue!");
    } catch (err: any) {
      toast.error(err.message || "Failed to submit for review.");
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border-default)] pb-5">
        <div>
          <Link
            href="/admin/questions"
            className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-2 transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" /> Back to Question Bank
          </Link>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
              AI Question Synthesis Studio
            </h1>
            <span className="text-xs px-2 py-0.5 bg-[var(--accent-subtle)] text-[var(--accent-text)] border border-[var(--accent-border)] rounded-full font-medium">Phase 4 Engine</span>
          </div>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Generate high-yield assessment questions across Coding, MCQ, and Subjective formats with Gemini multimodal comprehension, Bloom's taxonomy calibration, and sandbox verification.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Configuration Panel */}
        <div className="lg:col-span-5 space-y-6">
          <Card>
            <CardHeader className="pb-4 border-b border-[var(--border-default)]">
              <CardTitle className="text-base font-bold flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[var(--accent-primary)]" /> Synthesis Parameters
              </CardTitle>
              <CardDescription className="text-xs">
                Configure domain taxonomy, Bloom's level, visual schematics, and difficulty calibration.
              </CardDescription>
            </CardHeader>

            <CardContent className="pt-4">
              <form onSubmit={handleGenerate} className="space-y-4">
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

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Primary Topic</label>
                    <Input
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder="e.g. Dynamic Programming"
                      required
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Subtopic Context</label>
                    <Input
                      value={subTopic}
                      onChange={(e) => setSubTopic(e.target.value)}
                      placeholder="e.g. Tree DP, Knapsack"
                      className="mt-1"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Bloom's Taxonomy</label>
                    <div className="mt-1">
                      <Select
                        value={bloomsLevel}
                        onChange={(e) => setBloomsLevel(e.target.value as BloomsLevel)}
                      >
                        <option value="REMEMBER">Remember</option>
                        <option value="UNDERSTAND">Understand</option>
                        <option value="APPLY">Apply (Default)</option>
                        <option value="ANALYZE">Analyze</option>
                        <option value="EVALUATE">Evaluate</option>
                        <option value="CREATE">Create</option>
                      </Select>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Difficulty (1-10)</label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="range"
                        min="1"
                        max="10"
                        value={difficultyScore}
                        onChange={(e) => setDifficultyScore(parseInt(e.target.value))}
                        className="w-full accent-primary cursor-pointer"
                      />
                      <span className="font-mono font-bold text-sm text-[var(--accent-primary)] w-6 text-right">
                        {difficultyScore}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Marks</label>
                    <Input
                      type="number"
                      value={marks}
                      onChange={(e) => setMarks(Number(e.target.value))}
                      className="mt-1 text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Neg Marks</label>
                    <Input
                      type="number"
                      step="0.25"
                      value={negativeMarks}
                      onChange={(e) => setNegativeMarks(Number(e.target.value))}
                      className="mt-1 text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Est Time (m)</label>
                    <Input
                      type="number"
                      value={timeEstimate}
                      onChange={(e) => setTimeEstimate(Number(e.target.value))}
                      className="mt-1 text-xs"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-[var(--text-muted)] uppercase">Blueprint Prompt & Constraints</label>
                  <Textarea
                    value={blueprint}
                    onChange={(e) => setBlueprint(e.target.value)}
                    rows={3}
                    placeholder="Describe specific scenario, constraints, graph structure, or edge case requirements..."
                    className="mt-1 text-xs"
                  />
                </div>

                {/* Multimodal Diagram Upload */}
                <div className="p-3 rounded-lg border border-dashed border-[var(--border-default)] bg-[var(--bg-subtle)]/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                      <ImageIcon className="w-3.5 h-3.5 text-[var(--accent-primary)]" /> Diagram Comprehension (Optional)
                    </label>
                    {imageUrl && (
                      <button
                        type="button"
                        onClick={() => setImageUrl(null)}
                        className="text-[11px] text-[var(--status-error-text)] hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  {imageUrl ? (
                    <div className="border border-[var(--border-default)] rounded p-1 bg-[var(--bg-surface)] text-center">
                      <img src={imageUrl} alt="Uploaded Diagram" className="max-h-28 object-contain mx-auto" />
                    </div>
                  ) : (
                    <div>
                      <label className="cursor-pointer inline-flex items-center gap-1.5 text-xs text-[var(--accent-primary)] font-medium hover:underline">
                        <Upload className="w-3 h-3" />
                        {isUploadingImage ? "Uploading diagram..." : "Upload architecture / system diagram"}
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp,image/gif"
                          onChange={handleImageUpload}
                          disabled={isUploadingImage}
                          className="hidden"
                        />
                      </label>
                    </div>
                  )}
                </div>

                <Button
                  type="submit"
                  disabled={isGenerating || !topic.trim()}
                  className="w-full gap-2 mt-2"
                >
                  <Sparkles className="w-4 h-4" />
                  {isGenerating ? "Synthesizing Problem with AI Engine..." : "Generate Question"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right: Synthesis Results & Quality Review */}
        <div className="lg:col-span-7 space-y-6">
          {!generatedQuestion && !isGenerating && (
            <Card className="p-12 text-center border-dashed border-[var(--border-default)]">
              <div className="max-w-md mx-auto space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-[var(--accent-subtle)] border border-[var(--accent-border)] flex items-center justify-center mx-auto text-[var(--accent-primary)]">
                  <Sparkles className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-[var(--text-primary)]">Awaiting Question Synthesis</h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Configure your subject parameters on the left and click Generate. The Intelligent AI Question Engine will synthesize problem statements, schema validation, quality scoring, and test vectors.
                </p>
              </div>
            </Card>
          )}

          {isGenerating && (
            <Card className="p-12 text-center border-[var(--border-default)]">
              <div className="max-w-md mx-auto space-y-4">
                <div className="w-12 h-12 rounded-2xl bg-[var(--accent-subtle)] flex items-center justify-center mx-auto animate-pulse text-[var(--accent-primary)]">
                  <Sparkles className="w-6 h-6 animate-spin" />
                </div>
                <h3 className="text-base font-bold text-[var(--text-primary)]">Generating & Validating Problem</h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Invoking Gemini provider, performing structural verification, checking duplication hashes, and calculating deterministic quality profile...
                </p>
              </div>
            </Card>
          )}

          {generatedQuestion && (
            <div className="space-y-6">
              {/* Question Header Card */}
              <Card>
                <CardHeader className="pb-4 border-b border-[var(--border-default)]">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="info" className="text-xs">{generatedQuestion.question_type || "CODING"}</Badge>
                        <Badge variant="neutral" className="text-xs font-mono">{generatedQuestion.difficulty_score || 5}/10</Badge>
                        <Badge variant="success" className="text-xs">DETERMINISTIC QUALITY: {Math.round(generatedQuestion.quality_score || 0)}/100</Badge>
                      </div>
                      <CardTitle className="text-lg font-bold mt-2 text-[var(--text-primary)]">
                        {generatedQuestion.title}
                      </CardTitle>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="pt-4 space-y-4">
                  {/* Quality Breakdown Bars */}
                  {generatedQuestion.quality_breakdown && (
                    <div className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)]/40 space-y-2">
                      <div className="text-xs font-bold text-[var(--text-primary)] uppercase flex items-center justify-between">
                        <span>Quality Profile Breakdown</span>
                        <span className="text-emerald-400 font-mono">{Math.round(generatedQuestion.quality_score || 0)}% Validated</span>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                        {Object.entries(generatedQuestion.quality_breakdown).map(([dim, val]) => (
                          <div key={dim} className="bg-[var(--bg-surface)] p-2 rounded border border-[var(--border-default)] flex justify-between items-center">
                            <span className="capitalize text-[var(--text-muted)] text-[11px]">{dim.replace(/_/g, " ")}:</span>
                            <span className="font-mono font-bold text-[var(--accent-primary)]">{String(val)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Diagram if present */}
                  {generatedQuestion.image_url && (
                    <div className="border border-[var(--border-default)] rounded-lg p-2 bg-[var(--bg-surface)] text-center">
                      <img src={generatedQuestion.image_url} alt="Problem Diagram" className="max-h-56 object-contain mx-auto" />
                    </div>
                  )}

                  {/* Problem Statement */}
                  <div className="p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-subtle)]/20">
                    <FormattedQuestionText text={generatedQuestion.problem_statement} />
                  </div>

                  {/* MCQ Options Display */}
                  {generatedQuestion.question_type === "MCQ" && generatedQuestion.options && (
                    <div className="space-y-2">
                      <div className="text-xs font-bold text-[var(--text-primary)] uppercase">Multiple Choice Options</div>
                      <div className="grid grid-cols-1 gap-2">
                        {generatedQuestion.options.map((opt, i) => {
                          const letter = String.fromCharCode(65 + i);
                          const isCorrect = generatedQuestion.correct_answer === letter;
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
                      {generatedQuestion.explanation && (
                        <div className="p-3 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] text-xs text-[var(--text-muted)]">
                          <span className="font-bold text-[var(--text-primary)]">Explanation: </span>
                          {generatedQuestion.explanation}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Coding Constraints & Reference Solutions */}
                  {generatedQuestion.question_type === "CODING" && (
                    <div className="space-y-3">
                      {generatedQuestion.constraints && (
                        <div className="text-xs font-mono bg-[var(--bg-surface)] p-2 rounded border border-[var(--border-default)]">
                          <span className="font-bold text-[var(--text-primary)]">Constraints: </span>
                          {generatedQuestion.constraints}
                        </div>
                      )}

                      {/* Golden Reference Solutions */}
                      {generatedQuestion.reference_solutions && (
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-[var(--text-primary)] uppercase">Verified Reference Solutions</span>
                            <div className="flex gap-1">
                              {(["python", "cpp", "c", "java"] as const).map(lang => (
                                <button
                                  key={lang}
                                  type="button"
                                  onClick={() => setActiveSolLang(lang)}
                                  className={`px-2 py-0.5 rounded text-xs font-mono ${
                                    activeSolLang === lang ? "bg-[var(--accent-primary)] text-white" : "bg-[var(--bg-surface)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                                  }`}
                                >
                                  {lang.toUpperCase()}
                                </button>
                              ))}
                            </div>
                          </div>
                          <pre className="p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-default)] font-mono text-xs overflow-x-auto max-h-48 text-[var(--text-primary)]">
                            {generatedQuestion.reference_solutions[activeSolLang] || "No solution generated for this language."}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Actions Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-default)] pt-4">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleRunValidation}
                        disabled={isValidating}
                        className="gap-1.5 text-xs"
                      >
                        <Play className="w-3.5 h-3.5 text-emerald-400" />
                        {isValidating ? "Validating..." : "Sandbox Test"}
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleSubmitForReview}
                        className="gap-1.5 text-xs text-amber-400"
                      >
                        <CheckCheck className="w-3.5 h-3.5" />
                        Submit for Peer Review
                      </Button>
                    </div>

                    <div className="flex items-center gap-2">
                      <Link href="/admin/questions">
                        <Button variant="ghost" size="sm" className="text-xs">
                          Edit in Studio
                        </Button>
                      </Link>
                      {canPublish && (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={handlePublish}
                          disabled={isApproved}
                          className="gap-1.5 text-xs"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          {isApproved ? "Published to Question Bank" : "Publish to Question Bank"}
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
