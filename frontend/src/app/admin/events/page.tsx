"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event, Question } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Alert } from "@/components/ui/Alert";
import { useToast } from "@/components/ui/Toast";
import {
  Calendar, PlusCircle,
  Eye, Trash2
} from "lucide-react";

export default function AdminEventsPage() {
  const router = useRouter();
  const { user, isAdmin, isLoading } = useAuth();
  const toast = useToast();

  const [events, setEvents] = useState<Event[]>([]);
  const [questionsBank, setQuestionsBank] = useState<Question[]>([]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [eventToDelete, setEventToDelete] = useState<Event | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [targetBranch, setTargetBranch] = useState("ALL");
  const [targetYear, setTargetYear] = useState(0);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(120);
  const [isLeaderboardVisible, setIsLeaderboardVisible] = useState(true);
  const [selectedQuestionIds, setSelectedQuestionIds] = useState<number[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.events.list(),
      api.questions.list("APPROVED")
    ]).then(([evts, qs]) => {
      setEvents(evts || []);
      setQuestionsBank(qs || []);
    }).catch((err) => {
      console.error(err);
      setError(err.message || "Failed to load events data.");
    })
    .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!isLoading && (!user || !isAdmin)) {
      router.push("/");
      return;
    }
    if (user && isAdmin) {
      loadData();
    }
  }, [user, isAdmin, isLoading, router]);

  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !startTime || !endTime) {
      toast.error("Please fill in event title, start time, and end time.");
      return;
    }

    setIsSubmitting(true);
    try {
      const qLinks = selectedQuestionIds.map((qid, idx) => ({
        question_id: qid,
        branch_override: "ALL",
        year_override: 0,
        points: 100,
        order_index: idx + 1
      }));

      await api.events.create({
        title,
        description,
        target_branch: targetBranch,
        target_year: targetYear,
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        duration_minutes: durationMinutes,
        is_leaderboard_visible: isLeaderboardVisible,
        allow_branch_questions: false,
        questions: qLinks
      });

      setIsCreateModalOpen(false);
      setTitle("");
      setDescription("");
      setSelectedQuestionIds([]);
      toast.success("Assessment round created successfully");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to create event");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteEvent = async () => {
    if (!eventToDelete) return;
    setIsDeleting(true);
    try {
      await api.events.delete(eventToDelete.id);
      toast.success("Assessment deleted");
      setEventToDelete(null);
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete assessment event.");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggleResults = async (eventId: number, current: boolean) => {
    try {
      await api.events.releaseResults(eventId, !current);
      toast.success(!current ? "Results released to students" : "Results unreleased");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to update results release status");
    }
  };

  const handleToggleSolutions = async (eventId: number, current: boolean) => {
    try {
      await api.events.releaseSolutions(eventId, !current);
      toast.success(!current ? "Reference solutions published" : "Solutions hidden");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to update solutions release status");
    }
  };

  const handleToggleLeaderboard = async (eventId: number, current: boolean) => {
    try {
      await api.events.toggleLeaderboard(eventId, !current);
      toast.success(!current ? "Leaderboard enabled" : "Leaderboard hidden");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to update leaderboard visibility");
    }
  };

  const toggleQuestionSelection = (qid: number) => {
    if (selectedQuestionIds.includes(qid)) {
      setSelectedQuestionIds(selectedQuestionIds.filter((id) => id !== qid));
    } else {
      setSelectedQuestionIds([...selectedQuestionIds, qid]);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg" style={{ backgroundColor: "var(--accent-subtle)", color: "var(--accent-primary)", border: "1px solid var(--border-subtle)" }}>
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                Assessment Management
              </h1>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Schedule coding rounds, configure question pools, and govern live event access controls
              </p>
            </div>
          </div>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsCreateModalOpen(true)}
          leftIcon={<PlusCircle className="w-4 h-4" />}
        >
          Schedule Assessment
        </Button>
      </div>

      {/* Content */}
      {loading ? (
        <LoadingState message="Loading Assessments..." className="min-h-[40vh]" />
      ) : error ? (
        <Alert variant="error" title="Failed to Load Events" onRetry={loadData}>
          {error}
        </Alert>
      ) : events.length === 0 ? (
        <EmptyState
          icon={Calendar}
          title="No Assessments Created"
          description="There are currently no scheduled or active coding assessment rounds."
          actionLabel="Schedule Assessment"
          onAction={() => setIsCreateModalOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {events.map((evt) => {
            const isActive = evt.status === "ACTIVE";
            const isUpcoming = evt.status === "UPCOMING";
            const statusVariant = isActive ? "success" : isUpcoming ? "default" : "neutral";

            return (
              <Card key={evt.id} className="flex flex-col justify-between">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant={statusVariant as any} size="sm" dot={isActive}>
                      {evt.status.replace("_", " ")}
                    </Badge>
                    <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
                      {evt.target_branch} {evt.target_year > 0 ? `(Yr ${evt.target_year})` : "(All Years)"}
                    </span>
                  </div>

                  <CardTitle className="mt-1.5">{evt.title}</CardTitle>
                  <CardDescription className="line-clamp-2">
                    {evt.description || "USAR institutional coding assessment."}
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-3 pt-0 text-xs">
                  <div className="grid grid-cols-2 gap-2 font-mono text-[11px] p-2.5 rounded-lg" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                    <div>
                      <span className="block text-[10px]" style={{ color: "var(--text-muted)" }}>DURATION</span>
                      <span className="font-bold" style={{ color: "var(--text-primary)" }}>{evt.duration_minutes} Mins</span>
                    </div>
                    <div>
                      <span className="block text-[10px]" style={{ color: "var(--text-muted)" }}>PROBLEMS</span>
                      <span className="font-bold" style={{ color: "var(--accent-primary)" }}>{evt.total_questions || evt.questions?.length || 0} Questions</span>
                    </div>
                  </div>

                  {/* Operational Switch Toggles */}
                  <div className="space-y-1.5 pt-2" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                    <div className="flex items-center justify-between">
                      <span className="text-[11px]" style={{ color: "var(--text-secondary)" }}>Leaderboard:</span>
                      <button
                        type="button"
                        onClick={() => handleToggleLeaderboard(evt.id, evt.is_leaderboard_visible)}
                        className="text-[11px] font-semibold px-2 py-0.5 rounded transition"
                        style={{
                          backgroundColor: evt.is_leaderboard_visible ? "var(--color-success-subtle)" : "var(--bg-canvas)",
                          color: evt.is_leaderboard_visible ? "var(--color-success)" : "var(--text-muted)",
                          border: `1px solid ${evt.is_leaderboard_visible ? "var(--color-success)" : "var(--border-subtle)"}`
                        }}
                      >
                        {evt.is_leaderboard_visible ? "Public ✓" : "Hidden"}
                      </button>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-[11px]" style={{ color: "var(--text-secondary)" }}>Results:</span>
                      <button
                        type="button"
                        onClick={() => handleToggleResults(evt.id, evt.are_results_released)}
                        className="text-[11px] font-semibold px-2 py-0.5 rounded transition"
                        style={{
                          backgroundColor: evt.are_results_released ? "var(--color-success-subtle)" : "var(--bg-canvas)",
                          color: evt.are_results_released ? "var(--color-success)" : "var(--text-muted)",
                          border: `1px solid ${evt.are_results_released ? "var(--color-success)" : "var(--border-subtle)"}`
                        }}
                      >
                        {evt.are_results_released ? "Released ✓" : "Withheld"}
                      </button>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-[11px]" style={{ color: "var(--text-secondary)" }}>Solutions:</span>
                      <button
                        type="button"
                        onClick={() => handleToggleSolutions(evt.id, evt.are_solutions_released)}
                        className="text-[11px] font-semibold px-2 py-0.5 rounded transition"
                        style={{
                          backgroundColor: evt.are_solutions_released ? "var(--accent-subtle)" : "var(--bg-canvas)",
                          color: evt.are_solutions_released ? "var(--accent-primary)" : "var(--text-muted)",
                          border: `1px solid ${evt.are_solutions_released ? "var(--accent-primary)" : "var(--border-subtle)"}`
                        }}
                      >
                        {evt.are_solutions_released ? "Published ✓" : "Locked"}
                      </button>
                    </div>
                  </div>
                </CardContent>

                <CardFooter className="justify-between">
                  <Link href={`/admin/events/${evt.id}`}>
                    <Button variant="secondary" size="sm" leftIcon={<Eye className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} />}>
                      Live Monitor
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setEventToDelete(evt)}
                    aria-label={`Delete event ${evt.title}`}
                  >
                    <Trash2 className="w-4 h-4" style={{ color: "var(--color-danger)" }} />
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Event Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Schedule Assessment Round"
        description="Configure round window, target branch cohort, and select problems from the question bank."
        size="lg"
      >
        <form onSubmit={handleCreateEvent} className="space-y-4 text-xs">
          <Input
            label="Assessment Title *"
            required
            placeholder="e.g. USAR DSA Placement League — Round 3"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />

          <Textarea
            label="Instructions / Description"
            rows={2}
            placeholder="Important guidelines for student candidates..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Select
              label="Target Department"
              value={targetBranch}
              onChange={(e) => setTargetBranch(e.target.value)}
            >
              <option value="ALL">All Cohorts (AIML, AIDS, IIOT, AR)</option>
              <option value="AIML">AIML Only</option>
              <option value="AIDS">AIDS Only</option>
              <option value="IIOT">IIOT Only</option>
              <option value="AR">AR Only</option>
            </Select>

            <Select
              label="Target Year"
              value={targetYear}
              onChange={(e) => setTargetYear(Number(e.target.value))}
            >
              <option value={0}>All Years</option>
              <option value={1}>1st Year</option>
              <option value={2}>2nd Year</option>
              <option value={3}>3rd Year (Internship)</option>
              <option value={4}>4th Year (Full-time)</option>
            </Select>

            <Input
              label="Duration (Minutes)"
              type="number"
              min={15}
              max={360}
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Start Window *"
              type="datetime-local"
              required
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
            />
            <Input
              label="End Window *"
              type="datetime-local"
              required
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
            />
          </div>

          {/* Select Questions from Approved Bank */}
          <div className="space-y-2 pt-2" style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <div className="flex items-center justify-between">
              <span className="font-bold" style={{ color: "var(--text-primary)" }}>
                Select Questions ({selectedQuestionIds.length} chosen)
              </span>
              <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
                Pool: {questionsBank.length} approved problems
              </span>
            </div>

            <div className="max-h-48 overflow-y-auto space-y-1.5 p-2 rounded-lg" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
              {questionsBank.length === 0 ? (
                <p className="text-xs text-center py-3" style={{ color: "var(--text-muted)" }}>
                  No approved questions in bank. Please approve problems first.
                </p>
              ) : (
                questionsBank.map((q) => {
                  const isSelected = selectedQuestionIds.includes(q.id);
                  return (
                    <div
                      key={q.id}
                      onClick={() => toggleQuestionSelection(q.id)}
                      className="p-2.5 rounded-lg border text-xs cursor-pointer flex items-center justify-between transition"
                      style={{
                        backgroundColor: isSelected ? "var(--accent-subtle)" : "var(--bg-surface)",
                        borderColor: isSelected ? "var(--accent-primary)" : "var(--border-subtle)",
                        color: "var(--text-primary)"
                      }}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                          className="rounded pointer-events-none"
                        />
                        <span className="font-medium truncate">{q.title}</span>
                      </div>
                      <Badge variant="neutral" size="sm">
                        Diff {q.difficulty_score}/10
                      </Badge>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-3" style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <Button variant="outline" size="sm" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>
              Publish Assessment
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={eventToDelete !== null}
        onClose={() => setEventToDelete(null)}
        onConfirm={handleDeleteEvent}
        title="Delete Assessment Round"
        message={`Are you sure you want to delete "${eventToDelete?.title}"? All associated student submissions and test metrics will be permanently deleted.`}
        confirmText="Delete Assessment"
        variant="destructive"
        isLoading={isDeleting}
      />

    </div>
  );
}
