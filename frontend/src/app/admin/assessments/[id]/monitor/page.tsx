"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { MonitorDashboard, CandidateMonitorItem, AntiCheatEventOut, AttemptStatus } from "@/lib/types";
import {
  Shield, Radio, ArrowLeft, RefreshCw, AlertTriangle, Users,
  CheckCircle2, XCircle, Clock, Search, MoreVertical, Eye,
  AlertOctagon, PlusCircle, StopCircle, Ban, Activity
} from "lucide-react";

export default function AssessmentMonitorPage() {
  const params = useParams();
  const assessmentId = Number(params?.id);

  const [data, setData] = useState<MonitorDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [error, setError] = useState<string | null>(null);

  // Selected Candidate for Violation Inspection
  const [selectedAttemptId, setSelectedAttemptId] = useState<number | null>(null);
  const [candidateEvents, setCandidateEvents] = useState<AntiCheatEventOut[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  // Proctor Action Modal
  const [actionModalAttempt, setActionModalAttempt] = useState<CandidateMonitorItem | null>(null);
  const [actionType, setActionType] = useState<string>("EXTEND_TIME");
  const [actionReason, setActionReason] = useState("");
  const [extraMinutes, setExtraMinutes] = useState(10);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  const fetchMonitorData = async (isBackground: boolean = false) => {
    if (!isBackground) setLoading(true);
    try {
      const res = await api.assessments.getMonitor(assessmentId);
      setData(res);
      setError(null);
    } catch (err: any) {
      if (!isBackground) setError(err.message || "Failed to load live monitoring dashboard");
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  useEffect(() => {
    if (!assessmentId) return;
    fetchMonitorData();

    let interval: NodeJS.Timeout | null = null;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchMonitorData(true);
      }, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [assessmentId, autoRefresh]);

  const inspectViolations = async (attemptId: number) => {
    setSelectedAttemptId(attemptId);
    setEventsLoading(true);
    try {
      const events = await api.assessments.getEvents(attemptId);
      setCandidateEvents(events);
    } catch (err: any) {
      alert("Failed to load violation logs: " + err.message);
    } finally {
      setEventsLoading(false);
    }
  };

  const handleExecuteAction = async () => {
    if (!actionModalAttempt) return;
    if (!actionReason.trim()) {
      alert("Please provide a reason for the proctor action audit trail.");
      return;
    }

    setActionSubmitting(true);
    try {
      await api.assessments.adminAction(actionModalAttempt.attempt_id, {
        action: actionType,
        reason: actionReason,
        extra_minutes: actionType === "EXTEND_TIME" ? extraMinutes : undefined
      });
      alert(`Proctor action ${actionType} executed successfully.`);
      setActionModalAttempt(null);
      setActionReason("");
      fetchMonitorData();
    } catch (err: any) {
      alert(err.message || "Failed to execute proctor action");
    } finally {
      setActionSubmitting(false);
    }
  };

  const filteredCandidates = data?.candidates.filter(c => {
    const matchesSearch =
      c.candidate_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.candidate_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.enrollment_no && c.enrollment_no.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = statusFilter === "ALL" || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  }) || [];

  const formatSeconds = (sec: number) => {
    if (sec <= 0) return "00:00";
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const getStatusBadge = (status: AttemptStatus) => {
    switch (status) {
      case "IN_PROGRESS":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">TEST IN PROGRESS</span>;
      case "SUBMITTED":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">SUBMITTED</span>;
      case "AUTO_SUBMITTED":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">TIME EXPIRED</span>;
      case "TERMINATED_CHEATING":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">TERMINATED (CHEATING)</span>;
      case "INVALIDATED":
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border border-zinc-500/20">INVALIDATED</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-zinc-500/10 text-zinc-600 dark:text-zinc-400">{status}</span>;
    }
  };

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center p-8">
        <RefreshCw className="w-6 h-6 animate-spin text-[var(--accent-primary)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <Link href="/admin/assessments" className="hover:text-[var(--text-primary)] flex items-center gap-1 transition">
            <ArrowLeft className="w-4 h-4" /> Assessments
          </Link>
          <span>/</span>
          <span className="text-[var(--text-primary)] font-medium">Live Monitor: {data?.assessment_title}</span>
        </div>

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              <h1 className="text-2xl font-bold tracking-tight">Real-Time Proctoring & Candidate Monitor</h1>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-0.5">
              Live heartbeat telemetry, tab switch tracking, candidate session enforcement & proctor overrides.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-semibold text-[var(--text-secondary)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] px-3 py-2 rounded-lg cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-3.5 h-3.5 rounded text-[var(--accent-primary)]"
              />
              Auto-refresh (5s)
            </label>

            <button
              onClick={() => fetchMonitorData()}
              className="p-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)] transition"
              title="Refresh now"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Real-time Summary Cards */}
        {data && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
              <span className="text-xs text-[var(--text-secondary)]">Total Attempts</span>
              <p className="text-2xl font-bold">{data.total_attempts}</p>
            </div>
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
              <span className="text-xs text-emerald-500 flex items-center gap-1 font-medium">
                <Radio className="w-3 h-3 animate-pulse" /> Active Now
              </span>
              <p className="text-2xl font-bold text-emerald-500">{data.active_candidates}</p>
            </div>
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
              <span className="text-xs text-blue-500 flex items-center gap-1 font-medium">
                <CheckCircle2 className="w-3 h-3" /> Submitted
              </span>
              <p className="text-2xl font-bold text-blue-500">{data.submitted_count}</p>
            </div>
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
              <span className="text-xs text-red-500 flex items-center gap-1 font-medium">
                <AlertOctagon className="w-3 h-3" /> Terminated
              </span>
              <p className="text-2xl font-bold text-red-500">{data.terminated_count}</p>
            </div>
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
              <span className="text-xs text-amber-500 flex items-center gap-1 font-medium">
                <AlertTriangle className="w-3 h-3" /> Violations Logged
              </span>
              <p className="text-2xl font-bold text-amber-500">{data.total_violations}</p>
            </div>
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
              <span className="text-xs text-[var(--text-secondary)]">Avg Integrity</span>
              <p className="text-2xl font-bold">{data.average_integrity_score}%</p>
            </div>
          </div>
        )}

        {/* Filter & Candidate Table */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="relative md:col-span-2">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search candidates by name, email, enrollment number..."
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-sm focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-2 overflow-x-auto">
              {["ALL", "IN_PROGRESS", "SUBMITTED", "TERMINATED_CHEATING"].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition whitespace-nowrap ${
                    statusFilter === st
                      ? "bg-[var(--accent-primary)] text-white"
                      : "bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]"
                  }`}
                >
                  {st.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] text-[var(--text-secondary)] font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Candidate</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Connection</th>
                  <th className="px-4 py-3">Time Left</th>
                  <th className="px-4 py-3">Tab Switches</th>
                  <th className="px-4 py-3">Integrity Score</th>
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {filteredCandidates.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-[var(--text-secondary)]">
                      No candidate sessions matching the selected criteria.
                    </td>
                  </tr>
                ) : (
                  filteredCandidates.map((c) => (
                    <tr key={c.attempt_id} className="hover:bg-[var(--bg-subtle)]/50 transition">
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-semibold text-sm">{c.candidate_name}</p>
                          <p className="text-[10px] text-[var(--text-secondary)] font-mono">{c.candidate_email}</p>
                          {c.enrollment_no && (
                            <p className="text-[10px] text-[var(--text-muted)]">{c.enrollment_no} • {c.branch}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {getStatusBadge(c.status)}
                      </td>
                      <td className="px-4 py-3">
                        {c.is_online ? (
                          <span className="inline-flex items-center gap-1.5 text-emerald-500 font-medium">
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                            Online
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-[var(--text-muted)]">
                            <span className="w-2 h-2 rounded-full bg-zinc-400" />
                            Offline
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono font-medium">
                        {c.status === "IN_PROGRESS" ? formatSeconds(c.remaining_seconds) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-mono font-bold ${c.switch_count >= 3 ? 'text-red-500' : c.switch_count > 0 ? 'text-amber-500' : 'text-emerald-500'}`}>
                          {c.switch_count} switches
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 rounded-full bg-[var(--border-subtle)] overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                c.integrity_score >= 85
                                  ? 'bg-emerald-500'
                                  : c.integrity_score >= 60
                                  ? 'bg-amber-500'
                                  : 'bg-red-500'
                              }`}
                              style={{ width: `${Math.max(5, c.integrity_score)}%` }}
                            />
                          </div>
                          <span className="font-mono text-[11px] font-semibold">{c.integrity_score}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-[11px]">
                        {c.answers_saved_count} / {c.total_questions} Saved
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => inspectViolations(c.attempt_id)}
                            className="px-2 py-1 rounded bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] text-[var(--text-secondary)] transition font-medium flex items-center gap-1"
                            title="Inspect violations"
                          >
                            <Shield className="w-3.5 h-3.5 text-amber-500" /> Logs ({c.events_count})
                          </button>

                          {c.status === "IN_PROGRESS" && (
                            <button
                              onClick={() => setActionModalAttempt(c)}
                              className="px-2 py-1 rounded bg-[var(--accent-primary)]/10 hover:bg-[var(--accent-primary)]/20 text-[var(--accent-primary)] transition font-medium flex items-center gap-1"
                              title="Proctor Action"
                            >
                              <Activity className="w-3.5 h-3.5" /> Action
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Violations Drawer Modal */}
        {selectedAttemptId && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-end">
            <div className="bg-[var(--bg-surface)] border-l border-[var(--border-subtle)] w-full max-w-md h-full flex flex-col p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
                <div>
                  <h3 className="font-bold text-base flex items-center gap-2">
                    <Shield className="w-4 h-4 text-amber-500" /> Anti-Cheat Event Audit Log
                  </h3>
                  <p className="text-xs text-[var(--text-secondary)]">Attempt ID #{selectedAttemptId}</p>
                </div>
                <button
                  onClick={() => setSelectedAttemptId(null)}
                  className="text-xs px-2.5 py-1 rounded border border-[var(--border-subtle)] hover:bg-[var(--bg-subtle)]"
                >
                  Close
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                {eventsLoading ? (
                  <p className="text-center py-8 text-xs text-[var(--text-secondary)]">Loading violation events...</p>
                ) : candidateEvents.length === 0 ? (
                  <div className="text-center py-12 text-[var(--text-secondary)]">
                    <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                    <p className="font-semibold text-xs text-[var(--text-primary)]">Clean Session</p>
                    <p className="text-[11px] mt-1">No anti-cheating violations detected for this candidate.</p>
                  </div>
                ) : (
                  candidateEvents.map((evt) => (
                    <div
                      key={evt.id}
                      className="p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)] space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-xs text-[var(--text-primary)]">{evt.event_type}</span>
                        <span className={`px-1.5 py-0.2 rounded text-[10px] font-semibold ${
                          evt.severity === 'CRITICAL' ? 'bg-red-500/10 text-red-500' :
                          evt.severity === 'HIGH' ? 'bg-orange-500/10 text-orange-500' :
                          evt.severity === 'MEDIUM' ? 'bg-amber-500/10 text-amber-500' : 'bg-blue-500/10 text-blue-500'
                        }`}>
                          {evt.severity}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-muted)] font-mono">
                        {new Date(evt.timestamp).toLocaleString()}
                      </p>
                      {evt.event_data && (
                        <pre className="text-[10px] bg-[var(--bg-surface)] p-2 rounded border border-[var(--border-subtle)] overflow-x-auto text-[var(--text-secondary)]">
                          {JSON.stringify(evt.event_data, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* Proctor Action Modal */}
        {actionModalAttempt && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
              <div className="border-b border-[var(--border-subtle)] pb-3">
                <h3 className="font-bold text-base flex items-center gap-2">
                  <Activity className="w-4 h-4 text-[var(--accent-primary)]" /> Proctor Override Action
                </h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  Candidate: <span className="font-semibold text-[var(--text-primary)]">{actionModalAttempt.candidate_name}</span>
                </p>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold mb-1 text-[var(--text-secondary)]">Action Type</label>
                  <select
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-xs focus:outline-none"
                  >
                    <option value="EXTEND_TIME">Extend Remaining Time</option>
                    <option value="FORCE_SUBMIT">Force Submit Attempt Immediately</option>
                    <option value="TERMINATE">Terminate Attempt (Cheating Penalty)</option>
                    <option value="INVALIDATE">Invalidate Attempt (Zero Score)</option>
                  </select>
                </div>

                {actionType === "EXTEND_TIME" && (
                  <div>
                    <label className="block font-semibold mb-1 text-[var(--text-secondary)]">Extra Time to Add (Minutes)</label>
                    <input
                      type="number"
                      min={1}
                      max={120}
                      value={extraMinutes}
                      onChange={(e) => setExtraMinutes(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-xs focus:outline-none"
                    />
                  </div>
                )}

                <div>
                  <label className="block font-semibold mb-1 text-[var(--text-secondary)]">Reason / Justification *</label>
                  <textarea
                    rows={3}
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                    placeholder="e.g., Granted +10 mins due to campus power outage / network interruption..."
                    className="w-full px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-base)] text-xs focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setActionModalAttempt(null)}
                  className="px-3 py-1.5 rounded-lg border border-[var(--border-subtle)] text-xs font-semibold hover:bg-[var(--bg-subtle)]"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleExecuteAction}
                  disabled={actionSubmitting}
                  className="px-3 py-1.5 rounded-lg bg-[var(--accent-primary)] text-white text-xs font-semibold hover:opacity-90 disabled:opacity-50"
                >
                  {actionSubmitting ? "Executing..." : "Execute Action"}
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
