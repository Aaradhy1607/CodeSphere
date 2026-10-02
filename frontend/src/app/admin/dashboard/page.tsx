"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { PlacementAnalytics, Event } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { BranchProficiencyChart, TopicMasteryProgress } from "@/components/Charts";
import { CommandVisual } from "@/components/CommandVisual";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { Alert } from "@/components/ui/Alert";
import {
  Users, Calendar, Sparkles, Trophy, PlusCircle, Download,
  BarChart3, ArrowRight, Database, Activity, Sliders
} from "lucide-react";

export default function AdminDashboardPage() {
  const router = useRouter();
  const { user, isAdmin, isLoading } = useAuth();
  const [analytics, setAnalytics] = useState<PlacementAnalytics | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.analytics.getOverview(),
      api.events.list()
    ])
      .then(([an, evts]) => {
        setAnalytics(an);
        setEvents(evts || []);
      })
      .catch((err) => {
        console.error(err);
        setError(err.message || "Failed to load command center data.");
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

  if (isLoading || loading) {
    return <LoadingState message="Loading Placement Cell Command Center..." className="min-h-[70vh]" />;
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Alert variant="error" title="Failed to Load Dashboard" onRetry={loadData}>
          {error}
        </Alert>
      </div>
    );
  }

  const activeEvents = events.filter((e) => e.status === "ACTIVE");
  const upcomingEvents = events.filter((e) => e.status === "UPCOMING");
  const activeEvent = activeEvents[0];
  const nextUpcomingEvent = upcomingEvents[0];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      
      {/* Placement Cell Admin Command Bar */}
      <div
        className="rounded-xl p-5 sm:p-6 transition-all"
        style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          boxShadow: "var(--shadow-sm)"
        }}
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="warning" size="sm" dot>
                Placement Cell Administration
              </Badge>
              <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                USAR East Delhi Campus
              </span>
            </div>

            <h1 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Assessment & Placement Operations Hub
            </h1>

            <p className="text-xs sm:text-sm max-w-2xl font-normal leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Institutional orchestrator for AIML, AIDS, IIOT, and AR cohorts. Manage sandboxed coding tests, review live submissions, synthesize AI problems, and track student placement readiness.
            </p>
          </div>

          {/* Quick Admin Actions */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <Link href="/admin/events">
              <Button variant="primary" size="sm" leftIcon={<PlusCircle className="w-4 h-4" />}>
                Create Assessment
              </Button>
            </Link>
            <Link href="/admin/ai-generator">
              <Button variant="secondary" size="sm" leftIcon={<Sparkles className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />}>
                AI Problem Lab
              </Button>
            </Link>
            <a
              href={api.analytics.getExportUrl()}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="outline" size="sm" leftIcon={<Download className="w-4 h-4" style={{ color: "var(--color-success)" }} />}>
                Export CSV
              </Button>
            </a>
          </div>
        </div>
      </div>

      {/* Real KPI Metrics Bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard
          title="Registered Students"
          value={analytics?.total_registered_students || 0}
          subtitle="AIML, AIDS, IIOT, AR cohorts"
          icon={Users}
          iconColor="text-[var(--accent-primary)]"
          iconBg="bg-[var(--accent-subtle)]"
        />
        <StatCard
          title="Assessments Conducted"
          value={analytics?.total_events_conducted || 0}
          subtitle={`${activeEvents.length} currently active`}
          icon={Calendar}
          iconColor="text-[var(--color-success)]"
          iconBg="bg-[var(--color-success-subtle)]"
        />
        <StatCard
          title="Submissions Evaluated"
          value={analytics?.total_submissions || 0}
          subtitle="Multi-language sandboxed runs"
          icon={Activity}
          iconColor="text-[var(--color-info)]"
          iconBg="bg-[var(--color-info-subtle)]"
        />
        <StatCard
          title="Placement Ready Tier-1"
          value={analytics?.top_performers ? analytics.top_performers.filter((p) => p.placement_readiness_rating === "Ready").length : 0}
          subtitle="Top consistency & score"
          icon={Trophy}
          iconColor="text-[var(--color-warning)]"
          iconBg="bg-[var(--color-warning-subtle)]"
        />
      </div>

      {/* Main Grid: 3-Column Structured Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* LEFT COLUMN: Branch Performance Chart & Quick Modules (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Branch Comparison</CardTitle>
                  <CardDescription>Average vs Top Scores across USAR departments</CardDescription>
                </div>
                <BarChart3 className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
              </div>
            </CardHeader>
            <CardContent>
              {analytics?.branch_performance && Object.keys(analytics.branch_performance).length > 0 ? (
                <BranchProficiencyChart data={analytics.branch_performance} />
              ) : (
                <div className="p-6 rounded-lg text-center text-xs" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                  No departmental performance records available yet.
                </div>
              )}
            </CardContent>
            <CardFooter>
              <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>Departmental Analytics</span>
              <Link href="/admin/analytics" className="text-xs font-semibold hover:underline flex items-center gap-1" style={{ color: "var(--accent-primary)" }}>
                Full Report <ArrowRight className="w-3 h-3" />
              </Link>
            </CardFooter>
          </Card>

          {/* Quick Management Shortcuts */}
          <div className="grid grid-cols-2 gap-2.5">
            <Link href="/admin/questions" className="block">
              <Card interactive className="p-3 text-xs flex items-center justify-between font-semibold" style={{ color: "var(--text-primary)" }}>
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
                  <span>Question Bank</span>
                </div>
                <ArrowRight className="w-3 h-3" style={{ color: "var(--text-muted)" }} />
              </Card>
            </Link>

            <Link href="/admin/students" className="block">
              <Card interactive className="p-3 text-xs flex items-center justify-between font-semibold" style={{ color: "var(--text-primary)" }}>
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4" style={{ color: "var(--color-success)" }} />
                  <span>Student Roster</span>
                </div>
                <ArrowRight className="w-3 h-3" style={{ color: "var(--text-muted)" }} />
              </Card>
            </Link>
          </div>
        </div>

        {/* CENTER COLUMN: Central Assessment Stage & Telemetry (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <CommandVisual
            status={activeEvent ? "ACTIVE" : nextUpcomingEvent ? "UPCOMING" : "IDLE"}
            activeEventTitle={activeEvent?.title || nextUpcomingEvent?.title}
            metricLabel="Evaluation Engine"
            metricValue={activeEvent ? "LIVE ROUND" : "READY"}
            subMetricLabel="Total Submissions"
            subMetricValue={`${analytics?.total_submissions || 0}`}
          />

          {/* Active Event Command Stage */}
          {activeEvent ? (
            <Card style={{ borderColor: "var(--accent-primary)", backgroundColor: "var(--accent-subtle)" }}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Badge variant="success" size="sm" dot>
                    ACTIVE ASSESSMENT
                  </Badge>
                  <span className="text-xs font-mono font-bold" style={{ color: "var(--accent-primary)" }}>
                    {activeEvent.total_participants} Participants
                  </span>
                </div>
                <CardTitle className="mt-1">{activeEvent.title}</CardTitle>
                <CardDescription>
                  Target: {activeEvent.target_branch} {activeEvent.target_year > 0 ? `(Yr ${activeEvent.target_year})` : ""} • {activeEvent.duration_minutes} mins
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-2">
                  <Link href="/admin/events" className="flex-1">
                    <Button variant="primary" size="sm" className="w-full" leftIcon={<Sliders className="w-3.5 h-3.5" />}>
                      Event Controls
                    </Button>
                  </Link>
                  <Link href="/admin/leaderboards">
                    <Button variant="secondary" size="sm" leftIcon={<Trophy className="w-3.5 h-3.5" style={{ color: "var(--color-warning)" }} />}>
                      Standings
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ) : nextUpcomingEvent ? (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Badge variant="info" size="sm">
                    NEXT SCHEDULED ROUND
                  </Badge>
                  <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
                    {new Date(nextUpcomingEvent.start_time).toLocaleDateString()}
                  </span>
                </div>
                <CardTitle className="mt-1">{nextUpcomingEvent.title}</CardTitle>
                <CardDescription>
                  Duration: {nextUpcomingEvent.duration_minutes} mins • {nextUpcomingEvent.total_questions} Questions
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <Link href="/admin/events" className="block">
                  <Button variant="secondary" size="sm" className="w-full" leftIcon={<Calendar className="w-3.5 h-3.5" />}>
                    Manage Scheduled Events
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            <Card className="text-center p-6 space-y-2">
              <Calendar className="w-6 h-6 mx-auto" style={{ color: "var(--text-muted)" }} />
              <div>
                <h4 className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>No Active Event</h4>
                <p className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                  Schedule a new coding assessment round for USAR students.
                </p>
              </div>
              <div className="pt-1">
                <Link href="/admin/events">
                  <Button variant="secondary" size="sm" leftIcon={<PlusCircle className="w-3.5 h-3.5" />}>
                    Schedule Assessment
                  </Button>
                </Link>
              </div>
            </Card>
          )}
        </div>

        {/* RIGHT COLUMN: Cohort Strengths & Top Candidates (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Top Placement Candidates</CardTitle>
                  <CardDescription>Institutional lifetime leaderboard</CardDescription>
                </div>
                <Link href="/admin/leaderboards" className="text-xs font-semibold hover:underline" style={{ color: "var(--accent-primary)" }}>
                  View All
                </Link>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {analytics?.top_performers && analytics.top_performers.length > 0 ? (
                analytics.top_performers.slice(0, 4).map((cand) => (
                  <div
                    key={cand.user_id}
                    className="flex items-center justify-between p-2.5 rounded-lg text-xs transition"
                    style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <span className="font-mono font-bold w-5" style={{ color: "var(--color-warning)" }}>#{cand.rank}</span>
                      <div className="truncate">
                        <p className="font-semibold truncate" style={{ color: "var(--text-primary)" }}>{cand.full_name}</p>
                        <p className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>{cand.branch} • Yr {cand.academic_year}</p>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <span className="font-mono font-bold" style={{ color: "var(--color-success)" }}>{cand.total_lifetime_score} pts</span>
                      <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>{cand.total_problems_solved} Solved</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 rounded-lg text-center text-xs" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                  No candidate submissions recorded yet.
                </div>
              )}
            </CardContent>
            <CardFooter>
              <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>Leaderboard Scope</span>
              <span className="text-[11px] font-mono" style={{ color: "var(--text-secondary)" }}>Lifetime Aggregate</span>
            </CardFooter>
          </Card>

          {/* Cohort Topic Strengths */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Cohort Topic Strengths</CardTitle>
                <Sparkles className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
              </div>
            </CardHeader>
            <CardContent>
              {analytics?.topic_mastery && Object.keys(analytics.topic_mastery).length > 0 ? (
                <TopicMasteryProgress topics={analytics.topic_mastery} />
              ) : (
                <p className="text-xs py-1 text-center" style={{ color: "var(--text-muted)" }}>No topic aggregate data yet.</p>
              )}
            </CardContent>
          </Card>
        </div>

      </div>

    </div>
  );
}
