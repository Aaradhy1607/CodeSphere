"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { api } from "@/lib/api";
import { Event } from "@/lib/types";
import { CommandVisual } from "@/components/CommandVisual";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Alert } from "@/components/ui/Alert";
import { useToast } from "@/components/ui/Toast";
import {
  ShieldCheck, GraduationCap, ArrowRight,
  CheckCircle2, Trophy, Sparkles, Building2,
  Play, Users, Mail, KeyRound, LogOut
} from "lucide-react";

export default function PlacementCommandCenterPage() {
  const router = useRouter();
  const { user, login, googleLogin, completeOnboarding, needsOnboarding, isLoading, isAdmin, isSuperAdmin, logout } = useAuth();
  const toast = useToast();

  // Authentication Form States
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [authTab, setAuthTab] = useState<"credentials" | "student_sso">("credentials");

  // Student Google SSO Modal
  const [isStudentLoginModal, setIsStudentLoginModal] = useState(false);
  const [studentEmailInput, setStudentEmailInput] = useState("");
  const [studentNameInput, setStudentNameInput] = useState("");

  // Onboarding Modal
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [onboardName, setOnboardName] = useState("");
  const [onboardEnroll, setOnboardEnroll] = useState("");
  const [onboardBranch, setOnboardBranch] = useState("AIML");
  const [onboardYear, setOnboardYear] = useState(3);
  const [onboardPhone, setOnboardPhone] = useState("");

  // Live Database State
  const [events, setEvents] = useState<Event[]>([]);
  const [activeEvent, setActiveEvent] = useState<Event | null>(null);
  const [upcomingEvent, setUpcomingEvent] = useState<Event | null>(null);
  const [dbStats, setDbStats] = useState<{ totalStudents: number; totalEvents: number } | null>(null);

  // Fetch real database telemetry
  useEffect(() => {
    let isMounted = true;
    Promise.allSettled([
      api.events.list(),
      api.analytics.getLandingMetrics()
    ]).then(([eventsRes, metricsRes]) => {
      if (!isMounted) return;

      if (eventsRes.status === "fulfilled") {
        const evts = eventsRes.value || [];
        setEvents(evts);
        const now = new Date();
        const active = evts.find((e) => e.status === "ACTIVE" || (new Date(e.start_time) <= now && new Date(e.end_time) >= now));
        const upcoming = evts.find((e) => e.status === "UPCOMING" || new Date(e.start_time) > now);
        setActiveEvent(active || null);
        setUpcomingEvent(upcoming || null);
      }

      if (metricsRes.status === "fulfilled") {
        const metrics = metricsRes.value;
        setDbStats({
          totalStudents: metrics.total_students,
          totalEvents: metrics.total_events,
        });
      }
    });

    return () => { isMounted = false; };
  }, []);

  // Check Onboarding triggers
  useEffect(() => {
    if (user && needsOnboarding) {
      setOnboardName(user.full_name || "");
      setIsOnboardingOpen(true);
    }
  }, [user, needsOnboarding]);

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError("Please enter your university email address.");
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await login(email, password);
      toast.success("Authentication successful");
      if (res.needs_onboarding) {
        setIsOnboardingOpen(true);
      }
    } catch (err: any) {
      setError(err.message || "Login failed. Please check your credentials.");
      toast.error(err.message || "Login failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStudentGoogleSSO = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = studentEmailInput.trim().toLowerCase();
    if (!cleanEmail.endsWith("@std.ggsipu.ac.in")) {
      setError("Student domain email must end with @std.ggsipu.ac.in");
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await googleLogin(cleanEmail, studentNameInput.trim() || undefined);
      setIsStudentLoginModal(false);
      toast.success("Student single sign-on authenticated");
      if (res.needs_onboarding) {
        setIsOnboardingOpen(true);
      }
    } catch (err: any) {
      setError(err.message || "Student authentication failed.");
      toast.error(err.message || "Student authentication failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCompleteOnboarding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!onboardEnroll || !onboardName) {
      setError("Please provide your full name and university enrollment number.");
      return;
    }

    setIsSubmitting(true);
    try {
      await completeOnboarding(onboardName, onboardEnroll, onboardBranch, onboardYear, onboardPhone);
      setIsOnboardingOpen(false);
      toast.success("Student onboarding complete");
    } catch (err: any) {
      setError(err.message || "Onboarding failed.");
      toast.error(err.message || "Onboarding failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCardLogout = async () => {
    await logout();
    router.replace("/");
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12 space-y-10">
      
      {/* Hero & Command Overview Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* LEFT COLUMN (7 Cols): Institutional Platform Info */}
        <div className="lg:col-span-7 space-y-6">
          
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold" style={{ backgroundColor: "var(--accent-subtle)", color: "var(--accent-primary)", border: "1px solid var(--border-subtle)" }}>
                <Building2 className="w-3.5 h-3.5" /> USAR East Delhi Campus
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--color-success)" }} />
                <span>Training & Placement Cell</span>
              </span>
            </div>

            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight leading-tight" style={{ color: "var(--text-primary)" }}>
              CodeSphere Assessment & Placement Analytics
            </h1>

            <p className="text-sm leading-relaxed max-w-2xl font-normal" style={{ color: "var(--text-secondary)" }}>
              Official university coding evaluation platform. Standardizes algorithmic benchmarking across <strong style={{ color: "var(--text-primary)" }}>AIML, AIDS, IIOT, and AR</strong> cohorts with multi-language online judging, AI diagnostics, and verified placement leaderboards.
            </p>
          </div>

          {/* Institutional Department Telemetry Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            {[
              { code: "AIML", label: "AI & Machine Learning", badge: "aiml" },
              { code: "AIDS", label: "AI & Data Science", badge: "aids" },
              { code: "IIOT", label: "Industrial IoT", badge: "iiot" },
              { code: "AR", label: "Automation & Robotics", badge: "ar" },
            ].map((dept) => (
              <div
                key={dept.code}
                className="p-3 rounded-lg text-left space-y-1 transition-all"
                style={{
                  backgroundColor: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div className="flex items-center justify-between">
                  <Badge variant={dept.badge as any} size="sm">
                    {dept.code}
                  </Badge>
                  <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>Cohort</span>
                </div>
                <p className="text-[11px] font-medium truncate" style={{ color: "var(--text-secondary)" }}>{dept.label}</p>
              </div>
            ))}
          </div>

          {/* System Operations Telemetry */}
          <CommandVisual
            status={activeEvent ? "ACTIVE" : upcomingEvent ? "UPCOMING" : "IDLE"}
            activeEventTitle={activeEvent?.title || upcomingEvent?.title || "USAR Placement Hub"}
            metricLabel="Judge Sandbox"
            metricValue="Python • C++ • C • Java"
            subMetricLabel="Platform Status"
            subMetricValue={activeEvent ? "Live Round" : "Standby Mode"}
          />

          {/* Platform Capability Footprint */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4 text-xs" style={{ borderTop: "1px solid var(--border-subtle)", color: "var(--text-secondary)" }}>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" style={{ color: "var(--accent-primary)" }} />
              <span>Multi-Lang Sandbox (C, C++, Java, Python)</span>
            </div>
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 shrink-0" style={{ color: "var(--color-info)" }} />
              <span>Automated Reference Validation</span>
            </div>
            <div className="flex items-center gap-2">
              <Trophy className="w-4 h-4 shrink-0" style={{ color: "var(--color-warning)" }} />
              <span>Verified Placement Rankings</span>
            </div>
          </div>

        </div>

        {/* RIGHT COLUMN (5 Cols): Authentication / Logged-in State Card */}
        <div className="lg:col-span-5">
          {user ? (
            /* Logged in View */
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm"
                      style={{
                        backgroundColor: isAdmin ? "var(--color-warning-subtle)" : "var(--accent-subtle)",
                        color: isAdmin ? "var(--color-warning)" : "var(--accent-primary)",
                        border: `1px solid ${isAdmin ? "var(--color-warning)" : "var(--accent-primary)"}`
                      }}
                    >
                      {user.full_name?.charAt(0) || "U"}
                    </div>
                    <div>
                      <CardTitle>{user.full_name}</CardTitle>
                      <CardDescription className="font-mono mt-0.5">{user.email}</CardDescription>
                    </div>
                  </div>
                  <Badge variant={isAdmin ? "warning" : "default"}>
                    {isSuperAdmin ? "SUPER_ADMIN" : user.role}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {!isAdmin && user.student_profile && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2.5 rounded-lg" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                      <span className="text-[10px] uppercase font-mono" style={{ color: "var(--text-muted)" }}>Branch / Year</span>
                      <p className="font-bold mt-0.5" style={{ color: "var(--text-primary)" }}>
                        {user.student_profile.branch} • Yr {user.student_profile.academic_year}
                      </p>
                    </div>
                    <div className="p-2.5 rounded-lg" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                      <span className="text-[10px] uppercase font-mono" style={{ color: "var(--text-muted)" }}>Readiness</span>
                      <p className="font-bold mt-0.5" style={{ color: "var(--color-success)" }}>
                        {user.student_profile.placement_readiness_rating || "Developing"}
                      </p>
                    </div>
                  </div>
                )}

                {/* Active Assessment Notification */}
                {activeEvent ? (
                  <div className="p-3.5 rounded-lg space-y-2" style={{ backgroundColor: "var(--color-success-subtle)", border: "1px solid var(--color-success)" }}>
                    <div className="flex items-center justify-between">
                      <Badge variant="success" size="sm" dot>
                        LIVE ASSESSMENT ACTIVE
                      </Badge>
                      <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                        {activeEvent.total_questions || activeEvent.questions?.length || 0} Problems
                      </span>
                    </div>
                    <div>
                      <h4 className="font-bold text-xs" style={{ color: "var(--text-primary)" }}>{activeEvent.title}</h4>
                      <p className="text-[11px] line-clamp-1 mt-0.5" style={{ color: "var(--text-secondary)" }}>
                        {activeEvent.description || "Active USAR assessment round."}
                      </p>
                    </div>
                    <Link href={isAdmin ? `/admin/events/${activeEvent.id}` : `/student/events/${activeEvent.id}`} className="block pt-1">
                      <Button variant="primary" size="sm" className="w-full" leftIcon={<Play className="w-3.5 h-3.5" />}>
                        {isAdmin ? "Monitor Assessment Arena" : "Enter Assessment Arena"}
                      </Button>
                    </Link>
                  </div>
                ) : upcomingEvent ? (
                  <div className="p-3.5 rounded-lg space-y-2" style={{ backgroundColor: "var(--color-info-subtle)", border: "1px solid var(--color-info)" }}>
                    <div className="flex items-center justify-between">
                      <Badge variant="info" size="sm">
                        SCHEDULED ROUND
                      </Badge>
                      <span className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>
                        {new Date(upcomingEvent.start_time).toLocaleDateString()}
                      </span>
                    </div>
                    <h4 className="font-bold text-xs" style={{ color: "var(--text-primary)" }}>{upcomingEvent.title}</h4>
                    <Link
                      href={isAdmin ? `/admin/events/${upcomingEvent.id}` : "/student/events"}
                      className="block pt-1"
                    >
                      <Button variant="secondary" size="sm" className="w-full">
                        View Assessment Details
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="p-3 rounded-lg text-center text-xs" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                    No active assessment running right now.
                  </div>
                )}

                {/* Navigation Action Buttons */}
                <div className="space-y-2 pt-1">
                  {isAdmin ? (
                    <>
                      <Link href="/admin/dashboard" className="block">
                        <Button variant="primary" size="md" className="w-full" leftIcon={<ShieldCheck className="w-4 h-4" />}>
                          Open Admin Command Center
                        </Button>
                      </Link>
                      <div className="grid grid-cols-2 gap-2">
                        <Link href="/admin/questions">
                          <Button variant="secondary" size="sm" className="w-full">
                            Question Bank
                          </Button>
                        </Link>
                        <Link href="/admin/ai-generator">
                          <Button variant="secondary" size="sm" className="w-full">
                            AI Problem Lab
                          </Button>
                        </Link>
                      </div>
                    </>
                  ) : (
                    <>
                      <Link href="/student/dashboard" className="block">
                        <Button variant="primary" size="md" className="w-full" leftIcon={<GraduationCap className="w-4 h-4" />}>
                          Open Student Dashboard
                        </Button>
                      </Link>
                      <div className="grid grid-cols-2 gap-2">
                        <Link href="/student/events">
                          <Button variant="secondary" size="sm" className="w-full">
                            Assessments
                          </Button>
                        </Link>
                        <Link href="/student/leaderboard">
                          <Button variant="secondary" size="sm" className="w-full">
                            Leaderboard
                          </Button>
                        </Link>
                      </div>
                    </>
                  )}

                  {/* Direct Sign Out Action */}
                  <div className="pt-2 border-t border-[var(--border-subtle)]">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 border border-transparent hover:border-red-200 dark:hover:border-red-900/50 cursor-pointer"
                      leftIcon={<LogOut className="w-3.5 h-3.5" />}
                      onClick={handleCardLogout}
                    >
                      Sign Out of Session
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            /* Login Form View */
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Institutional Access</CardTitle>
                    <CardDescription>Sign in to your university placement account</CardDescription>
                  </div>
                  <Badge variant="neutral" size="sm">USAR Single Sign-On</Badge>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {error && (
                  <Alert variant="error" title="Authentication Error">
                    {error}
                  </Alert>
                )}

                {/* Login tabs */}
                <div className="grid grid-cols-2 gap-1 p-1 rounded-lg text-xs" style={{ backgroundColor: "var(--bg-canvas)", border: "1px solid var(--border-subtle)" }}>
                  <button
                    type="button"
                    onClick={() => { setAuthTab("credentials"); setError(null); }}
                    className="py-1.5 px-3 rounded-md font-medium transition"
                    style={{
                      backgroundColor: authTab === "credentials" ? "var(--bg-surface)" : "transparent",
                      color: authTab === "credentials" ? "var(--text-primary)" : "var(--text-muted)",
                      fontWeight: authTab === "credentials" ? 600 : 400,
                      boxShadow: authTab === "credentials" ? "0 1px 2px rgba(0,0,0,0.05)" : "none"
                    }}
                  >
                    Email Login
                  </button>
                  <button
                    type="button"
                    onClick={() => { setAuthTab("student_sso"); setError(null); }}
                    className="py-1.5 px-3 rounded-md font-medium transition"
                    style={{
                      backgroundColor: authTab === "student_sso" ? "var(--bg-surface)" : "transparent",
                      color: authTab === "student_sso" ? "var(--text-primary)" : "var(--text-muted)",
                      fontWeight: authTab === "student_sso" ? 600 : 400,
                      boxShadow: authTab === "student_sso" ? "0 1px 2px rgba(0,0,0,0.05)" : "none"
                    }}
                  >
                    Student Google SSO
                  </button>
                </div>

                {authTab === "credentials" ? (
                  <form onSubmit={handlePasswordLogin} className="space-y-3.5">
                    <Input
                      label="University Email Address"
                      type="email"
                      required
                      placeholder="e.g. placement@ipu.ac.in or rollno@std.ggsipu.ac.in"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      leftIcon={<Mail className="w-4 h-4" />}
                    />

                    <Input
                      label="Password"
                      type="password"
                      required
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      leftIcon={<KeyRound className="w-4 h-4" />}
                      helperText="Enter your institutional account password"
                    />

                    <Button
                      type="submit"
                      variant="primary"
                      size="md"
                      className="w-full"
                      isLoading={isSubmitting}
                    >
                      Sign In to CodeSphere
                    </Button>
                  </form>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                      Students can authenticate using their official GGSIPU student domain email address (<code style={{ color: "var(--accent-primary)" }}>@std.ggsipu.ac.in</code>).
                    </p>
                    <Button
                      variant="primary"
                      size="md"
                      className="w-full"
                      onClick={() => setIsStudentLoginModal(true)}
                      leftIcon={<GraduationCap className="w-4 h-4" />}
                    >
                      Authenticate with Student Domain
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

      </div>

      {/* Student Domain SSO Modal */}
      <Modal
        isOpen={isStudentLoginModal}
        onClose={() => setIsStudentLoginModal(false)}
        title="Student Single Sign-On"
        description="Authenticate with your official GGSIPU student domain email."
        size="sm"
      >
        <form onSubmit={handleStudentGoogleSSO} className="space-y-3.5">
          <Input
            label="Full Name (Optional for first-time)"
            type="text"
            placeholder="e.g. Aarav Sharma"
            value={studentNameInput}
            onChange={(e) => setStudentNameInput(e.target.value)}
          />

          <Input
            label="Student University Email *"
            type="email"
            required
            placeholder="00119011921@std.ggsipu.ac.in"
            value={studentEmailInput}
            onChange={(e) => setStudentEmailInput(e.target.value)}
            helperText="Must end with @std.ggsipu.ac.in"
          />

          <div className="flex items-center justify-end gap-2 pt-3" style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsStudentLoginModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
            >
              Verify & Sign In
            </Button>
          </div>
        </form>
      </Modal>

      {/* Student Onboarding Modal */}
      <Modal
        isOpen={isOnboardingOpen}
        onClose={() => {}}
        title="Student Profile Onboarding"
        description="Please complete your official USAR academic profile for placement eligibility."
        size="md"
        showCloseButton={false}
      >
        <form onSubmit={handleCompleteOnboarding} className="space-y-3.5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Full Name *"
              required
              placeholder="e.g. Aarav Sharma"
              value={onboardName}
              onChange={(e) => setOnboardName(e.target.value)}
            />

            <Input
              label="College Enrollment No. *"
              required
              placeholder="e.g. 02319011922"
              value={onboardEnroll}
              onChange={(e) => setOnboardEnroll(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Select
              label="Department / Branch *"
              value={onboardBranch}
              onChange={(e) => setOnboardBranch(e.target.value)}
            >
              <option value="AIML">Artificial Intelligence & Machine Learning (AIML)</option>
              <option value="AIDS">Artificial Intelligence & Data Science (AIDS)</option>
              <option value="IIOT">Industrial Internet of Things (IIOT)</option>
              <option value="AR">Automation & Robotics (AR)</option>
            </Select>

            <Select
              label="Academic Year *"
              value={onboardYear}
              onChange={(e) => setOnboardYear(Number(e.target.value))}
            >
              <option value={1}>1st Year (B.Tech)</option>
              <option value={2}>2nd Year (B.Tech)</option>
              <option value={3}>3rd Year (B.Tech)</option>
              <option value={4}>4th Year (B.Tech)</option>
            </Select>
          </div>

          <Input
            label="Phone Number (Optional for SMS Alerts)"
            type="tel"
            placeholder="+91 98765 43210"
            value={onboardPhone}
            onChange={(e) => setOnboardPhone(e.target.value)}
          />

          <div className="flex items-center justify-end pt-3" style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isSubmitting}
            >
              Save Profile & Enter Platform
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
