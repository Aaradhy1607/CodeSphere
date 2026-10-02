"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event, LeaderboardEntry, LifetimeLeaderboardEntry } from "@/lib/types";
import { Trophy, Calendar, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableContainer } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Select } from "@/components/ui/Select";

export default function StudentLeaderboardPage() {
  const router = useRouter();
  const { user, isLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<"LIFETIME" | "EVENT">("LIFETIME");
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  const [branchFilter, setBranchFilter] = useState<string>("ALL");
  const [yearFilter, setYearFilter] = useState<number>(0);

  const [lifetimeData, setLifetimeData] = useState<LifetimeLeaderboardEntry[]>([]);
  const [eventData, setEventData] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
      return;
    }
    if (user) {
      api.events.list()
        .then((evts) => {
          setEvents(evts);
          if (evts.length > 0) {
            setSelectedEventId(evts[0].id);
          }
        })
        .catch(console.error);
    }
  }, [user, isLoading, router]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    if (activeTab === "LIFETIME") {
      api.leaderboards.getLifetime(branchFilter, yearFilter)
        .then(setLifetimeData)
        .catch(console.error)
        .finally(() => setLoading(false));
    } else if (selectedEventId) {
      api.leaderboards.getEvent(selectedEventId, branchFilter, yearFilter)
        .then(setEventData)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [user, activeTab, selectedEventId, branchFilter, yearFilter]);

  if (isLoading || !user) {
    return <LoadingState message="Authenticating session..." className="min-h-[60vh]" />;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg" style={{ backgroundColor: "var(--color-warning-subtle)", color: "var(--color-warning)", border: "1px solid var(--border-subtle)" }}>
              <Trophy className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>Institutional Leaderboard</h1>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Placement rank standings, assessment leaderboards, and verified DSA mastery records
              </p>
            </div>
          </div>
        </div>

        {/* View Toggle */}
        <div className="flex items-center p-1 rounded-lg text-xs" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
          <button
            type="button"
            onClick={() => setActiveTab("LIFETIME")}
            className="px-3.5 py-1.5 rounded-md font-medium transition flex items-center gap-2"
            style={{
              backgroundColor: activeTab === "LIFETIME" ? "var(--accent-primary)" : "transparent",
              color: activeTab === "LIFETIME" ? "#ffffff" : "var(--text-muted)",
              fontWeight: activeTab === "LIFETIME" ? 600 : 400
            }}
          >
            <Sparkles className="w-3.5 h-3.5" /> Lifetime Standings
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("EVENT")}
            className="px-3.5 py-1.5 rounded-md font-medium transition flex items-center gap-2"
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
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              {activeTab === "EVENT" && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Assessment:</span>
                  <Select
                    value={selectedEventId || ""}
                    onChange={(e) => setSelectedEventId(Number(e.target.value))}
                  >
                    {events.map((evt) => (
                      <option key={evt.id} value={evt.id}>
                        {evt.title} ({evt.status})
                      </option>
                    ))}
                  </Select>
                </div>
              )}

              {/* Branch Filter */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Branch:</span>
                <Select
                  value={branchFilter}
                  onChange={(e) => setBranchFilter(e.target.value)}
                >
                  <option value="ALL">All Disciplines</option>
                  <option value="AIML">AI & ML (AIML)</option>
                  <option value="AIDS">AI & DS (AIDS)</option>
                  <option value="IIOT">Industrial IoT (IIOT)</option>
                  <option value="AR">Automation & Robotics (AR)</option>
                </Select>
              </div>

              {/* Year Filter */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Year:</span>
                <Select
                  value={yearFilter}
                  onChange={(e) => setYearFilter(Number(e.target.value))}
                >
                  <option value={0}>All Cohorts</option>
                  <option value={1}>1st Year (Fresher)</option>
                  <option value={2}>2nd Year (Sophomore)</option>
                  <option value={3}>3rd Year (Junior)</option>
                  <option value={4}>4th Year (Senior)</option>
                </Select>
              </div>
            </div>

            <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
              Showing {activeTab === "LIFETIME" ? lifetimeData.length : eventData.length} Ranked Students
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Leaderboard Table */}
      <TableContainer>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Rank</TableHead>
              <TableHead>Student</TableHead>
              <TableHead>Branch & Cohort</TableHead>
              {activeTab === "LIFETIME" ? (
                <>
                  <TableHead>Assessments</TableHead>
                  <TableHead>Solved</TableHead>
                  <TableHead>Avg Score</TableHead>
                  <TableHead>Total Score</TableHead>
                  <TableHead className="text-right">Readiness</TableHead>
                </>
              ) : (
                <>
                  <TableHead>Problems Solved</TableHead>
                  <TableHead>Total Execution Time</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                </>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="py-12 text-center">
                  <LoadingState message="Computing current standings..." />
                </TableCell>
              </TableRow>
            ) : activeTab === "LIFETIME" ? (
              lifetimeData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="py-12">
                    <EmptyState
                      icon={Trophy}
                      title="No Student Rankings Recorded Yet"
                      description="Participate in scheduled assessments to gain points and qualify for college placement standings."
                    />
                  </TableCell>
                </TableRow>
              ) : (
                lifetimeData.map((row) => {
                  const isCurrent = user.id === row.user_id;
                  const rankDisplay =
                    row.rank === 1 ? "🥇 #1" : row.rank === 2 ? "🥈 #2" : row.rank === 3 ? "🥉 #3" : `#${row.rank}`;

                  const readinessVariant =
                    row.placement_readiness_rating === "Ready" ? "success" :
                    row.placement_readiness_rating === "High Potential" ? "info" : "warning";

                  return (
                    <TableRow
                      key={row.user_id}
                      style={{
                        backgroundColor: isCurrent ? "var(--accent-subtle)" : undefined,
                        fontWeight: isCurrent ? 600 : 400
                      }}
                    >
                      <TableCell className="font-bold text-xs" style={{ color: "var(--text-primary)" }}>
                        {rankDisplay}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)", color: "var(--accent-primary)" }}>
                            {row.full_name.charAt(0)}
                          </div>
                          <div>
                            <div className="flex items-center gap-1.5">
                              <span className="font-semibold text-xs" style={{ color: "var(--text-primary)" }}>{row.full_name}</span>
                              {isCurrent && (
                                <Badge variant="default" size="sm">YOU</Badge>
                              )}
                            </div>
                            <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>{row.enrollment_no}</span>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <Badge variant={row.branch.toLowerCase() as any} size="sm">{row.branch}</Badge>
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>Yr {row.academic_year}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>{row.events_participated}</TableCell>
                      <TableCell className="font-mono text-xs font-semibold" style={{ color: "var(--color-success)" }}>{row.total_problems_solved}</TableCell>
                      <TableCell className="font-mono text-xs font-semibold" style={{ color: "var(--accent-primary)" }}>{row.average_score}</TableCell>
                      <TableCell className="font-mono font-bold text-xs" style={{ color: "var(--text-primary)" }}>
                        {row.total_lifetime_score}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant={readinessVariant} size="sm">
                          {row.placement_readiness_rating}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })
              )
            ) : (
              eventData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-12">
                    <EmptyState
                      icon={Calendar}
                      title="No Assessment Results Available"
                      description="Results will be tabulated when the assessment concludes and evaluation is finalized."
                    />
                  </TableCell>
                </TableRow>
              ) : (
                eventData.map((row) => {
                  const isCurrent = user.id === row.user_id;
                  const rankDisplay =
                    row.rank === 1 ? "🥇 #1" : row.rank === 2 ? "🥈 #2" : row.rank === 3 ? "🥉 #3" : `#${row.rank}`;

                  return (
                    <TableRow
                      key={row.user_id}
                      style={{
                        backgroundColor: isCurrent ? "var(--accent-subtle)" : undefined,
                        fontWeight: isCurrent ? 600 : 400
                      }}
                    >
                      <TableCell className="font-bold text-xs" style={{ color: "var(--text-primary)" }}>
                        {rankDisplay}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)", color: "var(--accent-primary)" }}>
                            {row.full_name.charAt(0)}
                          </div>
                          <div>
                            <div className="flex items-center gap-1.5">
                              <span className="font-semibold text-xs" style={{ color: "var(--text-primary)" }}>{row.full_name}</span>
                              {isCurrent && (
                                <Badge variant="default" size="sm">YOU</Badge>
                              )}
                            </div>
                            <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>{row.enrollment_no}</span>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <Badge variant={row.branch.toLowerCase() as any} size="sm">{row.branch}</Badge>
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>Yr {row.academic_year}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs font-semibold" style={{ color: "var(--color-success)" }}>
                        {row.problems_solved}
                      </TableCell>
                      <TableCell className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                        {row.total_time_ms.toFixed(1)} ms
                      </TableCell>
                      <TableCell className="text-right font-mono font-bold text-xs" style={{ color: "var(--color-success)" }}>
                        {row.total_score} pts
                      </TableCell>
                    </TableRow>
                  );
                })
              )
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </div>
  );
}
