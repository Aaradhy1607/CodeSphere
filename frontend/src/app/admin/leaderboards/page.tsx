"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event, LeaderboardEntry, LifetimeLeaderboardEntry } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { EmptyState } from "@/components/ui/EmptyState";
import { Alert } from "@/components/ui/Alert";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableContainer } from "@/components/ui/Table";
import { Trophy, Calendar, Sparkles, Download } from "lucide-react";

export default function AdminLeaderboardsPage() {
  const router = useRouter();
  const { user, isAdmin, isLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<"LIFETIME" | "EVENT">("LIFETIME");
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  const [branchFilter, setBranchFilter] = useState<string>("ALL");
  const [yearFilter, setYearFilter] = useState<number>(0);

  const [lifetimeData, setLifetimeData] = useState<LifetimeLeaderboardEntry[]>([]);
  const [eventData, setEventData] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && (!user || !isAdmin)) {
      router.push("/");
      return;
    }
    if (user && isAdmin) {
      api.events.list()
        .then((evts) => {
          setEvents(evts || []);
          if (evts && evts.length > 0) {
            setSelectedEventId(evts[0].id);
          }
        })
        .catch(console.error);
    }
  }, [user, isAdmin, isLoading, router]);

  const loadData = () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    if (activeTab === "LIFETIME") {
      api.leaderboards.getLifetime(branchFilter, yearFilter)
        .then((data) => setLifetimeData(data || []))
        .catch((err) => {
          console.error(err);
          setError(err.message || "Failed to load lifetime leaderboard.");
        })
        .finally(() => setLoading(false));
    } else if (selectedEventId) {
      api.leaderboards.getEvent(selectedEventId, branchFilter, yearFilter)
        .then((data) => setEventData(data || []))
        .catch((err) => {
          console.error(err);
          setError(err.message || "Failed to load assessment leaderboard.");
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [user, activeTab, selectedEventId, branchFilter, yearFilter]);

  if (isLoading || !user) {
    return <LoadingState message="Loading Leaderboard Standings..." className="min-h-[60vh]" />;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg" style={{ backgroundColor: "var(--color-warning-subtle)", color: "var(--color-warning)", border: "1px solid var(--border-subtle)" }}>
              <Trophy className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                USAR Placement Leaderboards
              </h1>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Institutional algorithmic merit standings across AIML, AIDS, IIOT, and AR cohorts
              </p>
            </div>
          </div>
        </div>

        {/* View Toggle Tabs */}
        <div className="flex items-center p-1 rounded-lg text-xs" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
          <button
            type="button"
            onClick={() => setActiveTab("LIFETIME")}
            className="px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5"
            style={{
              backgroundColor: activeTab === "LIFETIME" ? "var(--accent-primary)" : "transparent",
              color: activeTab === "LIFETIME" ? "#ffffff" : "var(--text-muted)",
              fontWeight: activeTab === "LIFETIME" ? 600 : 400
            }}
          >
            <Sparkles className="w-3.5 h-3.5" /> Lifetime Placement Rank
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("EVENT")}
            className="px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5"
            style={{
              backgroundColor: activeTab === "EVENT" ? "var(--accent-primary)" : "transparent",
              color: activeTab === "EVENT" ? "#ffffff" : "var(--text-muted)",
              fontWeight: activeTab === "EVENT" ? 600 : 400
            }}
          >
            <Calendar className="w-3.5 h-3.5" /> Assessment Standings
          </button>
        </div>
      </div>

      {/* Filter Controls */}
      <Card className="p-3 sm:p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            {activeTab === "EVENT" && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Event:</span>
                <select
                  value={selectedEventId || ""}
                  onChange={(e) => setSelectedEventId(Number(e.target.value))}
                  className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer max-w-[220px]"
                  style={{
                    backgroundColor: "var(--bg-canvas)",
                    border: "1px solid var(--border-subtle)",
                    color: "var(--text-primary)"
                  }}
                >
                  {events.map((evt) => (
                    <option key={evt.id} value={evt.id}>
                      {evt.title} ({evt.status})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Branch:</span>
              <select
                value={branchFilter}
                onChange={(e) => setBranchFilter(e.target.value)}
                className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
                style={{
                  backgroundColor: "var(--bg-canvas)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)"
                }}
              >
                <option value="ALL">All Branches</option>
                <option value="AIML">AIML</option>
                <option value="AIDS">AIDS</option>
                <option value="IIOT">IIOT</option>
                <option value="AR">AR</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Year:</span>
              <select
                value={yearFilter}
                onChange={(e) => setYearFilter(Number(e.target.value))}
                className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
                style={{
                  backgroundColor: "var(--bg-canvas)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)"
                }}
              >
                <option value={0}>All Years</option>
                <option value={1}>1st Year</option>
                <option value={2}>2nd Year</option>
                <option value={3}>3rd Year</option>
                <option value={4}>4th Year</option>
              </select>
            </div>
          </div>

          <a
            href={api.analytics.getExportUrl(branchFilter, yearFilter)}
            target="_blank"
            rel="noreferrer"
          >
            <Button variant="outline" size="sm" leftIcon={<Download className="w-3.5 h-3.5" />}>
              Export Data
            </Button>
          </a>
        </div>
      </Card>

      {/* Main Table */}
      {loading ? (
        <LoadingState message="Loading Standings..." className="min-h-[40vh]" />
      ) : error ? (
        <Alert variant="error" title="Leaderboard Error" onRetry={loadData}>
          {error}
        </Alert>
      ) : activeTab === "LIFETIME" ? (
        lifetimeData.length === 0 ? (
          <EmptyState
            icon={Trophy}
            title="No Lifetime Records"
            description="No student submissions have been evaluated yet for lifetime placement aggregation."
          />
        ) : (
          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow interactive={false}>
                  <TableHead className="w-16">Rank</TableHead>
                  <TableHead>Student Candidate</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Year</TableHead>
                  <TableHead>Events</TableHead>
                  <TableHead>Problems Solved</TableHead>
                  <TableHead>Lifetime Score</TableHead>
                  <TableHead>Placement Readiness</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lifetimeData.map((cand) => {
                  const branchVariant =
                    cand.branch === "AIML" ? "aiml" :
                    cand.branch === "AIDS" ? "aids" :
                    cand.branch === "IIOT" ? "iiot" :
                    cand.branch === "AR" ? "ar" : "neutral";

                  const readinessVariant =
                    cand.placement_readiness_rating === "Ready" ? "success" :
                    cand.placement_readiness_rating === "High Potential" ? "default" :
                    cand.placement_readiness_rating === "Needs Focus" ? "destructive" : "warning";

                  return (
                    <TableRow key={cand.user_id}>
                      <TableCell className="font-mono font-bold text-xs sm:text-sm">
                        <span style={{ color: cand.rank === 1 ? "var(--color-warning)" : "var(--text-muted)" }}>
                          #{cand.rank}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="font-semibold block text-xs sm:text-sm" style={{ color: "var(--text-primary)" }}>{cand.full_name}</span>
                        <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>{cand.enrollment_no}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={branchVariant as any} size="sm">
                          {cand.branch}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                        Year {cand.academic_year}
                      </TableCell>
                      <TableCell className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                        {cand.events_participated}
                      </TableCell>
                      <TableCell className="font-mono text-xs" style={{ color: "var(--accent-primary)" }}>
                        {cand.total_problems_solved}
                      </TableCell>
                      <TableCell className="font-mono font-bold text-xs sm:text-sm" style={{ color: "var(--color-success)" }}>
                        {cand.total_lifetime_score} pts
                      </TableCell>
                      <TableCell>
                        <Badge variant={readinessVariant as any} size="sm">
                          {cand.placement_readiness_rating || "Developing"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )
      ) : (
        eventData.length === 0 ? (
          <EmptyState
            icon={Calendar}
            title="No Assessment Submissions"
            description="No student submissions have been submitted for this specific assessment round yet."
          />
        ) : (
          <TableContainer>
            <Table>
              <TableHeader>
                <TableRow interactive={false}>
                  <TableHead className="w-16">Rank</TableHead>
                  <TableHead>Student Candidate</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Year</TableHead>
                  <TableHead>Solved</TableHead>
                  <TableHead>Total Score</TableHead>
                  <TableHead>Execution Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {eventData.map((entry) => (
                  <TableRow key={entry.user_id}>
                    <TableCell className="font-mono font-bold text-xs sm:text-sm" style={{ color: "var(--color-warning)" }}>
                      #{entry.rank}
                    </TableCell>
                    <TableCell>
                      <span className="font-semibold block text-xs sm:text-sm" style={{ color: "var(--text-primary)" }}>{entry.full_name}</span>
                      <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>{entry.enrollment_no}</span>
                    </TableCell>
                    <TableCell>
                      <Badge variant="neutral" size="sm">
                        {entry.branch}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                      Year {entry.academic_year}
                    </TableCell>
                    <TableCell className="font-mono text-xs" style={{ color: "var(--accent-primary)" }}>
                      {entry.problems_solved}
                    </TableCell>
                    <TableCell className="font-mono font-bold text-xs sm:text-sm" style={{ color: "var(--color-success)" }}>
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
        )
      )}

    </div>
  );
}
