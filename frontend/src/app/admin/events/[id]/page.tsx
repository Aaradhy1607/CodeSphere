"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event, LeaderboardEntry } from "@/lib/types";
import { CountdownTimer } from "@/components/CountdownTimer";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { Alert } from "@/components/ui/Alert";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableContainer } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import {
  ChevronLeft, Users, Trophy,
  Lock, Unlock, FileText, RefreshCw
} from "lucide-react";

export default function AdminEventMonitorPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const eventId = parseInt(resolvedParams.id);
  const router = useRouter();
  const { user, isAdmin, isLoading } = useAuth();
  const toast = useToast();

  const [event, setEvent] = useState<Event | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    Promise.all([
      api.events.get(eventId),
      api.leaderboards.getEvent(eventId)
    ]).then(([evt, lb]) => {
      setEvent(evt);
      setLeaderboard(lb || []);
    }).catch((err) => {
      console.error(err);
      setError(err.message || "Failed to load live monitor data.");
    })
    .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!isLoading && (!user || !isAdmin)) {
      router.push("/");
      return;
    }
    if (user && isAdmin && eventId) {
      loadData();
      const interval = setInterval(loadData, 10000); // 10s live poll
      return () => clearInterval(interval);
    }
  }, [user, isAdmin, isLoading, eventId, router]);

  const handleToggleResults = async () => {
    if (!event) return;
    try {
      await api.events.releaseResults(event.id, !event.are_results_released);
      toast.success(!event.are_results_released ? "Results released to students" : "Results locked");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to toggle results release.");
    }
  };

  const handleToggleSolutions = async () => {
    if (!event) return;
    try {
      await api.events.releaseSolutions(event.id, !event.are_solutions_released);
      toast.success(!event.are_solutions_released ? "Reference solutions published" : "Solutions locked");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to toggle solutions release.");
    }
  };

  if (isLoading || loading) {
    return <LoadingState message="Connecting to Live Arena Monitor..." className="min-h-[60vh]" />;
  }

  if (error || !event) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Alert variant="error" title="Event Monitor Error" onRetry={loadData}>
          {error || "Assessment event not found."}
        </Alert>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/admin/events">
            <Button variant="secondary" size="icon" aria-label="Back to events">
              <ChevronLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <Badge variant={event.status === "ACTIVE" ? "success" : "default"} size="sm" dot={event.status === "ACTIVE"}>
                {event.status}
              </Badge>
              <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>Live Operations</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight mt-1" style={{ color: "var(--text-primary)" }}>
              {event.title}
            </h1>
          </div>
        </div>

        {/* Live Timer & Release Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <CountdownTimer endTime={event.end_time} label="Ends In" />

          <Button
            variant={event.are_results_released ? "outline" : "secondary"}
            size="sm"
            onClick={handleToggleResults}
            leftIcon={event.are_results_released ? <Unlock className="w-3.5 h-3.5" style={{ color: "var(--color-success)" }} /> : <Lock className="w-3.5 h-3.5" />}
          >
            {event.are_results_released ? "Results Released" : "Release Results"}
          </Button>

          <Button
            variant={event.are_solutions_released ? "outline" : "secondary"}
            size="sm"
            onClick={handleToggleSolutions}
            leftIcon={<FileText className="w-3.5 h-3.5" style={{ color: "var(--accent-primary)" }} />}
          >
            {event.are_solutions_released ? "Solutions Published" : "Publish Solutions"}
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4 sm:p-5">
          <div className="flex items-center justify-between text-xs font-semibold uppercase mb-1" style={{ color: "var(--text-secondary)" }}>
            <span>Live Submitting Candidates</span>
            <Users className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
          </div>
          <p className="text-2xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>{leaderboard.length}</p>
          <p className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>Students with evaluated submissions</p>
        </Card>

        <Card className="p-4 sm:p-5">
          <div className="flex items-center justify-between text-xs font-semibold uppercase mb-1" style={{ color: "var(--text-secondary)" }}>
            <span>Assessment Problems</span>
            <FileText className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
          </div>
          <p className="text-2xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>{event.questions?.length || 0}</p>
          <p className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>Total problems in round pool</p>
        </Card>

        <Card className="p-4 sm:p-5">
          <div className="flex items-center justify-between text-xs font-semibold uppercase mb-1" style={{ color: "var(--text-secondary)" }}>
            <span>Top Score</span>
            <Trophy className="w-4 h-4" style={{ color: "var(--color-warning)" }} />
          </div>
          <p className="text-2xl font-bold font-mono" style={{ color: "var(--color-success)" }}>
            {leaderboard.length > 0 ? `${leaderboard[0].total_score} pts` : "0 pts"}
          </p>
          <p className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>
            Leader: {leaderboard.length > 0 ? leaderboard[0].full_name : "N/A"}
          </p>
        </Card>
      </div>

      {/* Live Standings Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Live Candidate Standings</CardTitle>
              <CardDescription>Auto-refreshes every 10 seconds</CardDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={loadData} leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>
              Refresh
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {leaderboard.length === 0 ? (
            <div className="p-8 text-center text-xs" style={{ color: "var(--text-muted)" }}>
              No student submissions recorded yet for this assessment.
            </div>
          ) : (
            <TableContainer className="border-0 rounded-none">
              <Table>
                <TableHeader>
                  <TableRow interactive={false}>
                    <TableHead className="w-16">Rank</TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead>Branch & Year</TableHead>
                    <TableHead>Problems Solved</TableHead>
                    <TableHead>Total Score</TableHead>
                    <TableHead>Execution Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leaderboard.map((entry) => (
                    <TableRow key={entry.user_id}>
                      <TableCell className="font-mono font-bold text-xs" style={{ color: "var(--color-warning)" }}>
                        #{entry.rank}
                      </TableCell>
                      <TableCell>
                        <span className="font-semibold block" style={{ color: "var(--text-primary)" }}>{entry.full_name}</span>
                        <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>{entry.enrollment_no}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="neutral" size="sm">
                          {entry.branch} • Yr {entry.academic_year}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                        {entry.problems_solved} / {event.questions?.length || 0}
                      </TableCell>
                      <TableCell className="font-mono font-bold text-xs" style={{ color: "var(--color-success)" }}>
                        {entry.total_score} pts
                      </TableCell>
                      <TableCell className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                        {(entry.total_time_ms / 1000).toFixed(1)}s
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
