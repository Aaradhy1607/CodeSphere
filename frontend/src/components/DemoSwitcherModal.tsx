"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Modal } from "./ui/Modal";
import { Badge } from "./ui/Badge";
import { ShieldCheck, GraduationCap, CheckCircle2, Loader2, ArrowRight, BookOpen, UserCheck, Shield } from "lucide-react";
import { useToast } from "./ui/Toast";

interface DemoUser {
  id: number;
  email: string;
  name: string;
  role: string;
  branch: string;
  year: number | string;
  enrollment_no: string;
}

interface DemoSwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DemoSwitcherModal({ isOpen, onClose }: DemoSwitcherModalProps) {
  const { user, switchUser } = useAuth();
  const { success, error } = useToast();
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [switchingId, setSwitchingId] = useState<number | null>(null);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      api.auth.getDemoUsers()
        .then(setDemoUsers)
        .catch((err) => {
          console.error(err);
          error("Failed to load demo accounts list.");
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, error]);

  const handleSwitch = async (u: DemoUser) => {
    setSwitchingId(u.id);
    try {
      await switchUser(u.id, u.role, u.email);
      success(`Switched active profile to ${u.name} (${u.role})`);
      onClose();
    } catch (err: any) {
      error(err.message || "Failed to switch user account.");
    } finally {
      setSwitchingId(null);
    }
  };

  const adminRoles = ["SUPER_ADMIN", "ADMIN", "PLACEMENT_ADMIN"];
  const staffRoles = ["FACULTY", "QUESTION_SETTER", "REVIEWER"];
  
  const leadershipUsers = demoUsers.filter((u) => adminRoles.includes(u.role));
  const academicUsers = demoUsers.filter((u) => staffRoles.includes(u.role));
  const studentUsers = demoUsers.filter((u) => u.role === "STUDENT");

  const getRoleBadgeVariant = (role: string): "destructive" | "warning" | "info" | "default" => {
    switch (role) {
      case "SUPER_ADMIN":
        return "destructive";
      case "ADMIN":
      case "PLACEMENT_ADMIN":
        return "warning";
      case "FACULTY":
      case "QUESTION_SETTER":
      case "REVIEWER":
        return "info";
      default:
        return "default";
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="lg"
      title="Role & Identity Switcher (7-Role RBAC)"
      description="Select any verified institutional persona to test role-based permissions in real-time."
    >
      <div className="space-y-5">
        {loading ? (
          <div className="flex items-center justify-center py-8 text-xs text-[var(--text-muted)]">
            <Loader2 className="w-5 h-5 animate-spin text-[var(--accent-primary)] mr-2" />
            Loading verified accounts...
          </div>
        ) : (
          <>
            {/* Leadership & Admin Profiles */}
            <div className="space-y-2.5">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-[var(--status-error-text)] shrink-0" />
                <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                  Placement Cell & System Leadership
                </h3>
              </div>

              <div className="grid grid-cols-1 gap-2">
                {leadershipUsers.map((adm) => {
                  const isCurrent = user?.email.toLowerCase() === adm.email.toLowerCase();
                  const isSwitching = switchingId === adm.id;
                  return (
                    <button
                      key={adm.id}
                      type="button"
                      onClick={() => handleSwitch(adm)}
                      disabled={switchingId !== null}
                      className={`flex items-center justify-between p-3 rounded-md border text-left transition-colors focus-visible:outline-none ${
                        isCurrent
                          ? "bg-[var(--accent-subtle)] border-[var(--accent-border)]"
                          : "bg-[var(--bg-surface)] border-[var(--border-subtle)] hover:bg-[var(--bg-subtle)] hover:border-[var(--border-default)]"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-[var(--status-error-bg)] border border-[var(--status-error-border)] flex items-center justify-center text-[var(--status-error-text)] font-bold text-xs shrink-0 font-mono">
                          {adm.role === "SUPER_ADMIN" ? "ROOT" : "ADM"}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-xs sm:text-sm text-[var(--text-primary)]">{adm.name}</span>
                            <Badge variant={getRoleBadgeVariant(adm.role)} size="sm">
                              {adm.role}
                            </Badge>
                          </div>
                          <p className="text-[11px] text-[var(--text-muted)] font-mono">{adm.email}</p>
                        </div>
                      </div>

                      {isCurrent ? (
                        <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--accent-text)] bg-[var(--accent-subtle)] px-2.5 py-1 rounded border border-[var(--accent-border)]">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Active
                        </span>
                      ) : (
                        <span className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] px-3 py-1 rounded font-medium transition flex items-center gap-1">
                          {isSwitching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <>Select <ArrowRight className="w-3 h-3" /></>}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Academic & Question Specialists */}
            {academicUsers.length > 0 && (
              <div className="space-y-2.5 pt-2 border-t border-[var(--border-subtle)]">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[var(--accent-primary)] shrink-0" />
                  <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                    Academic Faculty & Question Specialists
                  </h3>
                </div>

                <div className="grid grid-cols-1 gap-2">
                  {academicUsers.map((staff) => {
                    const isCurrent = user?.email.toLowerCase() === staff.email.toLowerCase();
                    const isSwitching = switchingId === staff.id;
                    return (
                      <button
                        key={staff.id}
                        type="button"
                        onClick={() => handleSwitch(staff)}
                        disabled={switchingId !== null}
                        className={`flex items-center justify-between p-3 rounded-md border text-left transition-colors focus-visible:outline-none ${
                          isCurrent
                            ? "bg-[var(--accent-subtle)] border-[var(--accent-border)]"
                            : "bg-[var(--bg-surface)] border-[var(--border-subtle)] hover:bg-[var(--bg-subtle)] hover:border-[var(--border-default)]"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded bg-[var(--accent-subtle)] border border-[var(--accent-border)] flex items-center justify-center text-[var(--accent-text)] font-bold text-xs shrink-0 font-mono">
                            {staff.role.slice(0, 3)}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-xs sm:text-sm text-[var(--text-primary)]">{staff.name}</span>
                              <Badge variant={getRoleBadgeVariant(staff.role)} size="sm">
                                {staff.role}
                              </Badge>
                            </div>
                            <p className="text-[11px] text-[var(--text-muted)] font-mono">{staff.email}</p>
                          </div>
                        </div>

                        {isCurrent ? (
                          <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--accent-text)] bg-[var(--accent-subtle)] px-2.5 py-1 rounded border border-[var(--accent-border)]">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Active
                          </span>
                        ) : (
                          <span className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] px-3 py-1 rounded font-medium transition flex items-center gap-1">
                            {isSwitching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <>Select <ArrowRight className="w-3 h-3" /></>}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Student Profiles */}
            <div className="space-y-2.5 pt-2 border-t border-[var(--border-subtle)]">
              <div className="flex items-center gap-2">
                <GraduationCap className="w-4 h-4 text-[var(--accent-primary)] shrink-0" />
                <h3 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                  USAR Student Cohorts (AIML, AIDS, IIOT, AR)
                </h3>
              </div>

              {studentUsers.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {studentUsers.map((stu) => {
                    const isCurrent = user?.email.toLowerCase() === stu.email.toLowerCase();
                    const isSwitching = switchingId === stu.id;
                    const branchVariant =
                      stu.branch === "AIML" ? "aiml" :
                      stu.branch === "AIDS" ? "aids" :
                      stu.branch === "IIOT" ? "iiot" :
                      stu.branch === "AR" ? "ar" : "default";

                    return (
                      <button
                        key={stu.id}
                        type="button"
                        onClick={() => handleSwitch(stu)}
                        disabled={switchingId !== null}
                        className={`flex flex-col justify-between p-3 rounded-md border text-left transition-colors focus-visible:outline-none ${
                          isCurrent
                            ? "bg-[var(--accent-subtle)] border-[var(--accent-border)]"
                            : "bg-[var(--bg-surface)] border-[var(--border-subtle)] hover:bg-[var(--bg-subtle)] hover:border-[var(--border-default)]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="truncate">
                            <p className="font-semibold text-xs sm:text-sm text-[var(--text-primary)] truncate">{stu.name}</p>
                            <p className="text-[11px] text-[var(--text-muted)] font-mono">{stu.enrollment_no}</p>
                          </div>
                          <Badge variant={branchVariant as any} size="sm">
                            {stu.branch} • Yr {stu.year}
                          </Badge>
                        </div>

                        <div className="flex items-center justify-between pt-2 border-t border-[var(--border-subtle)] text-xs">
                          <span className="text-[var(--text-muted)] text-[11px] truncate max-w-[130px]">{stu.email}</span>
                          {isCurrent ? (
                            <span className="text-[var(--accent-text)] font-medium flex items-center gap-1 text-[11px]">
                              <CheckCircle2 className="w-3 h-3" /> Active
                            </span>
                          ) : (
                            <span className="text-[var(--text-muted)] hover:text-[var(--text-primary)] font-medium text-[11px]">
                              {isSwitching ? "Switching..." : "Select →"}
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-[var(--text-muted)] py-3 text-center">No students registered yet.</p>
              )}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
