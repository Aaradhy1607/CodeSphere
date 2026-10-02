"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { PlacementAnalytics, User, StudentComparison } from "@/lib/types";
import { BranchProficiencyChart, TopicMasteryProgress } from "@/components/Charts";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { Alert } from "@/components/ui/Alert";
import { useToast } from "@/components/ui/Toast";
import {
  BarChart3, ArrowRightLeft, Sparkles,
  FileSpreadsheet
} from "lucide-react";

export default function AdminAnalyticsPage() {
  const router = useRouter();
  const { user, isAdmin, isLoading } = useAuth();
  const toast = useToast();

  const [analytics, setAnalytics] = useState<PlacementAnalytics | null>(null);
  const [studentsList, setStudentsList] = useState<User[]>([]);
  const [compareStudent1, setCompareStudent1] = useState<number | null>(null);
  const [compareStudent2, setCompareStudent2] = useState<number | null>(null);
  const [comparisonResults, setComparisonResults] = useState<StudentComparison[]>([]);

  const [exportBranch, setExportBranch] = useState("ALL");
  const [exportYear, setExportYear] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.analytics.getOverview(),
      api.students.list()
    ]).then(([an, stus]) => {
      setAnalytics(an);
      // Deduplicate student list by primary key id to guarantee unique option keys
      const seen = new Set<number>();
      const uniqueStudents = (stus || []).filter((s) => {
        if (!s || !s.id || seen.has(s.id)) return false;
        seen.add(s.id);
        return true;
      });
      setStudentsList(uniqueStudents);
      if (uniqueStudents.length >= 2) {
        setCompareStudent1(uniqueStudents[0].id);
        setCompareStudent2(uniqueStudents[1].id);
        api.analytics.compare([uniqueStudents[0].id, uniqueStudents[1].id])
          .then((res) => {
            setComparisonResults(Array.isArray(res) ? res : []);
          })
          .catch(console.error);
      }
    }).catch((err) => {
      console.error(err);
      setError(err.message || "Failed to load placement analytics.");
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

  const handleRunComparison = async () => {
    if (!compareStudent1 || !compareStudent2) {
      toast.error("Please select two candidate profiles to compare.");
      return;
    }
    if (compareStudent1 === compareStudent2) {
      toast.error("Please select two different students for comparison.");
      return;
    }
    try {
      const res = await api.analytics.compare([compareStudent1, compareStudent2]);
      setComparisonResults(Array.isArray(res) ? res : []);
      toast.success("Comparison report updated");
    } catch (err: any) {
      toast.error(err.message || "Failed to compare students");
    }
  };

  if (isLoading || loading) {
    return <LoadingState message="Aggregating Placement Analytics..." className="min-h-[60vh]" />;
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Alert variant="error" title="Failed to Load Analytics" onRetry={loadData}>
          {error}
        </Alert>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      
      {/* Header & CSV Export Widget */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg" style={{ backgroundColor: "var(--accent-subtle)", color: "var(--accent-primary)", border: "1px solid var(--border-subtle)" }}>
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
                USAR Placement Analytics
              </h1>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Departmental DSA benchmarks, long-term student trajectory comparison, and recruiter export data
              </p>
            </div>
          </div>
        </div>

        {/* CSV Export Widget */}
        <Card className="p-2 flex flex-wrap items-center gap-2">
          <select
            value={exportBranch}
            onChange={(e) => setExportBranch(e.target.value)}
            className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
            style={{
              backgroundColor: "var(--bg-canvas)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)"
            }}
            aria-label="Export branch filter"
          >
            <option value="ALL">All Branches</option>
            <option value="AIML">AIML</option>
            <option value="AIDS">AIDS</option>
            <option value="IIOT">IIOT</option>
            <option value="AR">AR</option>
          </select>

          <select
            value={exportYear}
            onChange={(e) => setExportYear(Number(e.target.value))}
            className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
            style={{
              backgroundColor: "var(--bg-canvas)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)"
            }}
            aria-label="Export year filter"
          >
            <option value={0}>All Years</option>
            <option value={3}>3rd Year</option>
            <option value={4}>4th Year</option>
          </select>

          <a
            href={api.analytics.getExportUrl(exportBranch, exportYear)}
            target="_blank"
            rel="noreferrer"
          >
            <Button variant="primary" size="sm" leftIcon={<FileSpreadsheet className="w-4 h-4" />}>
              Download CSV
            </Button>
          </a>
        </Card>
      </div>

      {/* Main Grid: Branch Comparison & Topic Proficiency */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left: Branch Proficiency */}
        <div className="lg:col-span-7 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Departmental Performance (AIML, AIDS, IIOT, AR)</CardTitle>
              <CardDescription>Average vs Top Cumulative Placement Assessment Scores</CardDescription>
            </CardHeader>

            <CardContent>
              {analytics?.branch_performance ? (
                <BranchProficiencyChart data={analytics.branch_performance} />
              ) : (
                <div className="p-8 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                  No branch comparison data recorded.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Topic Mastery Distribution */}
        <div className="lg:col-span-5 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>DSA Topic Mastery Distribution</CardTitle>
                  <CardDescription>Success rate across algorithmic categories</CardDescription>
                </div>
                <Sparkles className="w-4 h-4" style={{ color: "var(--accent-primary)" }} />
              </div>
            </CardHeader>

            <CardContent>
              {analytics?.topic_mastery ? (
                <TopicMasteryProgress topics={analytics.topic_mastery} />
              ) : (
                <div className="p-8 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                  No topic mastery data available.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

      </div>

      {/* Side-by-Side Student Comparison Tool */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ArrowRightLeft className="w-4 h-4" style={{ color: "var(--accent-primary)" }} /> Multi-Candidate Comparative Analytics
              </CardTitle>
              <CardDescription>
                Compare algorithmic proficiency trajectories between two candidates
              </CardDescription>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={compareStudent1 || ""}
                onChange={(e) => setCompareStudent1(Number(e.target.value))}
                className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
                style={{
                  backgroundColor: "var(--bg-canvas)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)"
                }}
                aria-label="Candidate A"
              >
                {studentsList.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name} ({s.student_profile?.branch || "USAR"})
                  </option>
                ))}
              </select>

              <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>VS</span>

              <select
                value={compareStudent2 || ""}
                onChange={(e) => setCompareStudent2(Number(e.target.value))}
                className="text-xs rounded-lg px-2.5 py-1.5 cursor-pointer"
                style={{
                  backgroundColor: "var(--bg-canvas)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)"
                }}
                aria-label="Candidate B"
              >
                {studentsList.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name} ({s.student_profile?.branch || "USAR"})
                  </option>
                ))}
              </select>

              <Button variant="secondary" size="sm" onClick={handleRunComparison}>
                Compare
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {comparisonResults && comparisonResults.length === 2 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {comparisonResults.map((cand) => (
                <div key={`candidate-comparison-${cand.student_id ?? cand.id ?? cand.user_id}`} className="p-4 rounded-xl space-y-3 text-xs" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                  <div className="flex items-center justify-between pb-2" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <div>
                      <span className="font-bold text-sm block" style={{ color: "var(--text-primary)" }}>{cand.full_name}</span>
                      <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
                        {cand.branch} • Year {cand.academic_year}
                      </span>
                    </div>
                    <Badge variant={cand.placement_readiness === "Ready" ? "success" : "default"} size="sm">
                      {cand.placement_readiness || "Developing"}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 rounded" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
                      <span className="text-[10px] uppercase font-mono block" style={{ color: "var(--text-muted)" }}>Score</span>
                      <span className="font-mono font-bold" style={{ color: "var(--color-success)" }}>{cand.total_score || 0}</span>
                    </div>
                    <div className="p-2 rounded" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
                      <span className="text-[10px] uppercase font-mono block" style={{ color: "var(--text-muted)" }}>Solved</span>
                      <span className="font-mono font-bold" style={{ color: "var(--accent-primary)" }}>{cand.total_solved || 0}</span>
                    </div>
                    <div className="p-2 rounded" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}>
                      <span className="text-[10px] uppercase font-mono block" style={{ color: "var(--text-muted)" }}>Consistency</span>
                      <span className="font-mono font-bold" style={{ color: "var(--color-warning)" }}>{cand.consistency || 85}%</span>
                    </div>
                  </div>

                  {cand.topic_mastery && (
                    <div className="space-y-1.5 pt-1">
                      <span className="font-semibold text-[11px]" style={{ color: "var(--text-primary)" }}>Topic Proficiency:</span>
                      <TopicMasteryProgress topics={cand.topic_mastery} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-xs" style={{ color: "var(--text-muted)" }}>
              Select two student profiles above and click &quot;Compare&quot; to inspect comparative telemetry.
            </div>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
