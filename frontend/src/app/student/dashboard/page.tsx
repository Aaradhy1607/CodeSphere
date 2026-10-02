"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event, StudentReport } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { TopicMasteryProgress, ScoreTrajectoryLine } from "@/components/Charts";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { Alert } from "@/components/ui/Alert";
import {
  Trophy, Calendar, CheckCircle2, Sparkles,
  TrendingUp, PlayCircle, Award
} from "lucide-react";

export default function StudentDashboard() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [events, setEvents] = useState<Event[]>([]);
  const [reports, setReports] = useState<StudentReport[]>([]);
  const [topicMastery, setTopicMastery] = useState<Record<string, number>>({});
  const [scoreTrajectory, setScoreTrajectory] = useState<any[]>([]);
  const [userRank, setUserRank] = useState<number | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    if (!user) return;
    setLoadingData(true);
    setError(null);
    Promise.all([
      api.events.list(),
      api.reports.getMyReports(),
      api.analytics.getStudentTopics(user.id),
      api.leaderboards.getLifetime(user.student_profile?.branch || "ALL")
    ])
      .then(([evts, reps, topicData, leaderboard]) => {
        setEvents(evts || []);
        setReports(reps || []);
        if (topicData) {
          setTopicMastery(topicData.topic_mastery || {});
          setScoreTrajectory(topicData.score_trajectory || []);
        }
        if (leaderboard && Array.isArray(leaderboard)) {
          const entry = leaderboard.find((e) => e.user_id === user.id);
          if (entry) {
            setUserRank(entry.rank);
          }
        }
      })
      .catch((err) => {
        console.error(err);
        setError(err.message || "Failed to load student dashboard.");
      })
      .finally(() => setLoadingData(false));
  };

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
      return;
    }
    if (user) {
      loadData();
    }
  }, [user, isLoading, router]);

  if (isLoading || loadingData || !user) {
    return <LoadingState message="Loading Student Dashboard..." className="min-h-[70vh]" />;
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

  const profile = user.student_profile;
  const activeEvents = events.filter((e) => e.status === "ACTIVE");
  const upcomingEvents = events.filter((e) => e.status === "UPCOMING");

  const branchVariant =
    profile?.branch === "AIML" ? "aiml" :
    profile?.branch === "AIDS" ? "aids" :
    profile?.branch === "IIOT" ? "iiot" :
    profile?.branch === "AR" ? "ar" : "neutral";

  const readinessVariant =
    profile?.placement_readiness_rating === "Ready" ? "success" :
    profile?.placement_readiness_rating === "High Potential" ? "default" :
    profile?.placement_readiness_rating === "Needs Focus" ? "destructive" : "warning";

  const activeEvent = activeEvents[0];
  const nextUpcomingEvent = upcomingEvents[0];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      
      {/* Student Profile Hero Banner */}
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
              <Badge variant={branchVariant as any} size="sm">
                {profile?.branch || "USAR"} • Year {profile?.academic_year || 3}
              </Badge>
              <Badge variant={readinessVariant as any} size="sm">
                Readiness: {profile?.placement_readiness_rating || "Developing"}
              </Badge>
              {userRank !== null && userRank > 0 && (
                <Badge variant="warning" size="sm">
                  <Trophy className="w-3 h-3 mr-1" /> Rank #{userRank}
                </Badge>
              )}
            </div>

            <h1 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Welcome, {user.full_name}
            </h1>

            <p className="text-xs sm:text-sm font-normal flex flex-wrap items-center gap-2" style={{ color: "var(--text-secondary)" }}>
              <span>Enrollment: <strong className="font-mono" style={{ color: "var(--text-primary)" }}>{profile?.enrollment_no || "N/A"}</strong></span>
              <span>•</span>
              <span>University School of Automation & Robotics</span>
            </p>
          </div>

          {/* Action Hub Buttons */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <Link href="/student/events">
              <Button variant="primary" size="sm" leftIcon={<Calendar className="w-4 h-4" />}>
                Assessment Arena
              </Button>
            </Link>
            <Link href="/student/leaderboard">
              <Button variant="secondary" size="sm" leftIcon={<Trophy className="w-4 h-4" style={{ color: "var(--color-warning)" }} />}>
                Leaderboard
              </Button>
            </Link>
            <Link href="/student/reports">
              <Button variant="outline" size="sm" leftIcon={<Sparkles className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />}>
                AI Diagnostics
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Real KPI Metrics Bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard
          title="Total Lifetime Score"
          value={profile?.total_lifetime_score || 0}
          subtitle="Cumulative verified points"
          icon={Award}
          iconColor="text-[var(--color-success)]"
          iconBg="bg-[var(--color-success-subtle)]"
        />
        <StatCard
          title="Problems Solved"
          value={profile?.total_problems_solved || 0}
          subtitle="Across all assessments"
          icon={CheckCircle2}
          iconColor="text-[var(--accent-primary)]"
          iconBg="bg-[var(--accent-subtle)]"
        />
        <StatCard
          title="Events Participated"
          value={profile?.total_events_participated || 0}
          subtitle="USAR scheduled rounds"
          icon={Calendar}
          iconColor="text-[var(--color-info)]"
          iconBg="bg-[var(--color-info-subtle)]"
        />
        <StatCard
          title="Consistency Rating"
          value={`${profile?.consistency_score || 85}%`}
          subtitle="Evaluation stability"
          icon={TrendingUp}
          iconColor="text-[var(--color-warning)]"
          iconBg="bg-[var(--color-warning-subtle)]"
        />
      </div>

      {/* Main Grid: 3-Column Structured Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* LEFT COLUMN: Active Assessment Stage & Scheduled Events (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {activeEvent ? (
            <Card style={{ borderColor: "var(--color-success)", backgroundColor: "var(--color-success-subtle)" }}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Badge variant="success" size="sm" dot>
                    ASSESSMENT IN PROGRESS
                  </Badge>
                  <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
                    {activeEvent.duration_minutes} Mins
                  </span>
                </div>
                <CardTitle className="mt-1">{activeEvent.title}</CardTitle>
                <CardDescription>
                  {activeEvent.description || "Active coding assessment round for your cohort."}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <Link href={`/student/events/${activeEvent.id}`} className="block">
                  <Button variant="primary" size="md" className="w-full" leftIcon={<PlayCircle className="w-4 h-4" />}>
                    Enter Assessment Arena
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ) : nextUpcomingEvent ? (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Badge variant="info" size="sm">
                    UPCOMING ROUND
                  </Badge>
                  <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
                    {new Date(nextUpcomingEvent.start_time).toLocaleDateString()}
                  </span>
                </div>
                <CardTitle className="mt-1">{nextUpcomingEvent.title}</CardTitle>
                <CardDescription>
                  Starts at {new Date(nextUpcomingEvent.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <Link href="/student/events" className="block">
                  <Button variant="secondary" size="sm" className="w-full">
                    View Assessment Schedule
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            <Card className="p-6 text-center space-y-2">
              <Calendar className="w-6 h-6 mx-auto" style={{ color: "var(--text-muted)" }} />
              <div>
                <h4 className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>No Live Assessment</h4>
                <p className="text-[11px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                  The Placement Cell has not published any live rounds at this moment.
                </p>
              </div>
            </Card>
          )}

          {/* Score Trajectory Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Score Trajectory</CardTitle>
              <CardDescription>Performance history across recent rounds</CardDescription>
            </CardHeader>
            <CardContent>
              {scoreTrajectory.length > 0 ? (
                <ScoreTrajectoryLine scores={scoreTrajectory} />
              ) : (
                <div className="p-6 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                  Participate in assessments to build your trajectory curve.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* RIGHT COLUMN: Topic Mastery & Recent AI Reports (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Algorithmic Topic Mastery</CardTitle>
                  <CardDescription>Personalized proficiency in core placement DSA topics</CardDescription>
                </div>
                <Sparkles className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
              </div>
            </CardHeader>
            <CardContent>
              {Object.keys(topicMastery).length > 0 ? (
                <TopicMasteryProgress topics={topicMastery} />
              ) : (
                <div className="p-6 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                  No topic mastery data recorded yet.
                </div>
              )}
            </CardContent>
          </Card>

          {/* AI Diagnostic Reports Preview */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Recent AI Diagnostic Reports</CardTitle>
                  <CardDescription>Cognitive feedback on completed assessments</CardDescription>
                </div>
                <Link href="/student/reports" className="text-xs font-semibold hover:underline" style={{ color: "var(--accent-primary)" }}>
                  All Reports
                </Link>
              </div>
            </CardHeader>

            <CardContent className="space-y-2.5">
              {reports.length > 0 ? (
                reports.slice(0, 3).map((rep) => (
                  <div
                    key={rep.id}
                    className="p-3 rounded-xl flex items-center justify-between text-xs"
                    style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}
                  >
                    <div>
                      <span className="font-semibold block" style={{ color: "var(--text-primary)" }}>{rep.event_title}</span>
                      <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
                        Rank #{rep.rank} of {rep.total_participants} • {new Date(rep.generated_at).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold" style={{ color: "var(--color-success)" }}>{rep.score} pts</span>
                      <Link href="/student/reports">
                        <Button variant="secondary" size="sm">
                          Read Report
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-6 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                  No diagnostic reports generated yet. Reports are generated once assessment results are released.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

      </div>

    </div>
  );
}
