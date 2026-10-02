import type {
  User, UserRole, AccountStatus, Permission, AuthResponse, AuditLog, Event as AppEvent, Question, CodeRunResult, FinalSubmitResult,
  Submission, LeaderboardEntry, LifetimeLeaderboardEntry, StudentReport, PlacementAnalytics, StudentComparison,
  DuplicateCheckResult, QuestionVersion, QuestionAnalytics, QuestionFeedback,
  Assessment, AttemptState, AnswerSaveRequest, AnswerSaveResponse, AntiCheatEventCreate, AntiCheatEventOut, AttemptStatus,
  AssessmentResultDetail, MonitorDashboard, AsyncSubmitResult, SubmissionStatusOut, StudentSubmissionHistoryOut
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

function getAuthHeader(): HeadersInit {
  if (typeof window === "undefined") return { "Content-Type": "application/json" };
  const token = localStorage.getItem("codesphere_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
}

let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = { ...getAuthHeader(), ...options.headers };
  let response = await fetch(url, { ...options, headers });

  // Handle Token Expiration with Auto-Refresh
  if (response.status === 401 && typeof window !== "undefined" && !endpoint.includes("/auth/login") && !endpoint.includes("/auth/refresh")) {
    const refreshToken = localStorage.getItem("codesphere_refresh_token");
    if (refreshToken) {
      if (!isRefreshing) {
        isRefreshing = true;
        refreshPromise = (async () => {
          try {
            const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ refresh_token: refreshToken })
            });
            if (res.ok) {
              const data: AuthResponse = await res.json();
              localStorage.setItem("codesphere_token", data.access_token);
              if (data.refresh_token) {
                localStorage.setItem("codesphere_refresh_token", data.refresh_token);
              }
              if (data.user) {
                localStorage.setItem("codesphere_user", JSON.stringify(data.user));
              }
              return data.access_token;
            } else {
              localStorage.removeItem("codesphere_token");
              localStorage.removeItem("codesphere_refresh_token");
              localStorage.removeItem("codesphere_user");
              window.dispatchEvent(new Event("codesphere_auth_expired"));
              return null;
            }
          } catch {
            return null;
          } finally {
            isRefreshing = false;
            refreshPromise = null;
          }
        })();
      }

      const newAccessToken = await refreshPromise;
      if (newAccessToken) {
        const retryHeaders = {
          ...headers,
          Authorization: `Bearer ${newAccessToken}`
        };
        response = await fetch(url, { ...options, headers: retryHeaders });
      }
    }
  }

  if (!response.ok) {
    let errorDetail = "An unexpected error occurred.";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    throw new Error(errorDetail || `HTTP Error ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Authentication & Access Control
  auth: {
    getMe: () => request<User>("/auth/me"),
    login: (email: string, password?: string) =>
      request<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      }),
    refresh: (refresh_token: string) =>
      request<AuthResponse>("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token })
      }),
    logout: (refresh_token?: string) =>
      request<{ message: string }>("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token })
      }),
    forgotPassword: (email: string) =>
      request<{ message: string }>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email })
      }),
    resetPassword: (token: string, new_password: string) =>
      request<{ message: string }>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password })
      }),
    changePassword: (current_password: string, new_password: string) =>
      request<{ message: string }>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password, new_password })
      }),
    googleAuth: (email: string, full_name?: string, avatar_url?: string, enrollment_no?: string, branch?: string, academic_year?: number) =>
      request<AuthResponse>("/auth/google", {
        method: "POST",
        body: JSON.stringify({ email, full_name, avatar_url, enrollment_no, branch, academic_year })
      }),
    onboarding: (full_name: string, enrollment_no: string, branch: string, academic_year: number, phone?: string) =>
      request<User>("/auth/onboarding", {
        method: "POST",
        body: JSON.stringify({ full_name, enrollment_no, branch, academic_year, phone })
      }),
    listUsers: (search?: string, role?: string, status?: string) => {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (role) params.append("role", role);
      if (status) params.append("status", status);
      return request<User[]>(`/auth/users?${params.toString()}`);
    },
    updateUserRole: (userId: number, role: string) =>
      request<User>(`/auth/users/${userId}/role`, {
        method: "PUT",
        body: JSON.stringify({ role })
      }),
    updateUserStatus: (userId: number, status: string) =>
      request<User>(`/auth/users/${userId}/status`, {
        method: "PUT",
        body: JSON.stringify({ status })
      }),
    getAuditLogs: (limit: number = 100) =>
      request<AuditLog[]>(`/auth/audit-logs?limit=${limit}`),
    getAdmins: () => request<any[]>("/auth/admins"),
    addAdmin: (email: string, name?: string) =>
      request<any>("/auth/admins", {
        method: "POST",
        body: JSON.stringify({ email, name })
      }),
    removeAdmin: (adminId: number) =>
      request<{ message: string }>(`/auth/admins/${adminId}`, { method: "DELETE" }),
    getDemoUsers: () => request<any[]>("/auth/demo-users"),
    switchDemoUser: (user_id?: number, role?: string, email?: string) =>
      request<AuthResponse>("/auth/demo-switch", {
        method: "POST",
        body: JSON.stringify({ user_id, role, email })
      })
  },

  // Students
  students: {
    list: (branch?: string, academic_year?: number, search?: string) => {
      const params = new URLSearchParams();
      if (branch) params.append("branch", branch);
      if (academic_year && academic_year > 0) params.append("academic_year", academic_year.toString());
      if (search) params.append("search", search);
      return request<User[]>(`/students/?${params.toString()}`);
    },
    create: (name: string, email: string, enrollment_no: string, branch: string, academic_year: number) => {
      const params = new URLSearchParams({ name, email, enrollment_no, branch, academic_year: academic_year.toString() });
      return request<User>(`/students/create?${params.toString()}`, { method: "POST" });
    },
    getHistory: (user_id: number) => request<any>(`/students/${user_id}/history`),
    toggleStatus: (user_id: number, is_active: boolean) =>
      request<{ message: string }>(`/students/${user_id}/status?is_active=${is_active}`, { method: "PUT" }),
    delete: (user_id: number) =>
      request<{ message: string }>(`/students/${user_id}`, { method: "DELETE" })
  },

  // Events
  events: {
    list: () => request<AppEvent[]>("/events/"),
    get: (id: number) => request<AppEvent>(`/events/${id}`),
    create: (data: any) =>
      request<AppEvent>("/events/", {
        method: "POST",
        body: JSON.stringify(data)
      }),
    update: (id: number, data: any) =>
      request<{ message: string; event_id: number }>(`/events/${id}`, {
        method: "PUT",
        body: JSON.stringify(data)
      }),
    delete: (id: number) =>
      request<{ message: string }>(`/events/${id}`, { method: "DELETE" }),
    releaseResults: (id: number, release: boolean = true) =>
      request<{ message: string }>(`/events/${id}/release-results?release=${release}`, { method: "POST" }),
    releaseSolutions: (id: number, release: boolean = true) =>
      request<{ message: string }>(`/events/${id}/release-solutions?release=${release}`, { method: "POST" }),
    toggleLeaderboard: (id: number, visible: boolean = true) =>
      request<{ message: string }>(`/events/${id}/toggle-leaderboard?visible=${visible}`, { method: "POST" })
  },

  // Questions & Intelligent Question Engine (Phase 4)
  questions: {
    list: (status?: string, difficulty_min?: number, difficulty_max?: number, search?: string, question_type?: string) => {
      const params = new URLSearchParams();
      if (status) params.append("status", status);
      if (difficulty_min) params.append("difficulty_min", difficulty_min.toString());
      if (difficulty_max) params.append("difficulty_max", difficulty_max.toString());
      if (search) params.append("search", search);
      if (question_type) params.append("question_type", question_type);
      return request<Question[]>(`/questions/?${params.toString()}`);
    },
    get: (id: number) => request<Question>(`/questions/${id}`),
    create: (data: any) =>
      request<Question>("/questions/", {
        method: "POST",
        body: JSON.stringify(data)
      }),
    update: (id: number, data: any) =>
      request<Question>(`/questions/${id}`, {
        method: "PUT",
        body: JSON.stringify(data)
      }),
    delete: (id: number) =>
      request<{ message: string }>(`/questions/${id}`, { method: "DELETE" }),
    uploadImage: async (file: File): Promise<{ image_url: string; filename: string; size_bytes: number; mime_type: string }> => {
      const formData = new FormData();
      formData.append("file", file);
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`${API_BASE_URL}/questions/upload-image`, {
        method: "POST",
        headers,
        body: formData
      });
      if (!res.ok) {
        let errStr = "Image upload failed";
        try {
          const errJson = await res.json();
          errStr = errJson.detail || errStr;
        } catch {}
        throw new Error(errStr);
      }
      return res.json();
    },
    checkDuplicate: (title: string, problem_statement: string, exclude_question_id?: number) =>
      request<DuplicateCheckResult>("/questions/check-duplicate", {
        method: "POST",
        body: JSON.stringify({ title, problem_statement, exclude_question_id })
      }),
    review: (id: number, action: "APPROVED" | "REJECTED" | "DRAFT" | "PENDING_REVIEW", comment?: string, quality_rating?: number, difficulty_feedback?: number) =>
      request<{ message: string; question: Question }>(`/questions/${id}/review`, {
        method: "POST",
        body: JSON.stringify({ action, comment, quality_rating, difficulty_feedback })
      }),
    publish: (id: number, force: boolean = false, change_summary?: string) =>
      request<{ message: string; question: Question }>(`/questions/${id}/publish?force=${force}`, {
        method: "POST",
        body: JSON.stringify({ force, change_summary })
      }),
    getVersions: (id: number) =>
      request<QuestionVersion[]>(`/questions/${id}/versions`),
    getAnalytics: (id: number) =>
      request<QuestionAnalytics>(`/questions/${id}/analytics`),
    submitFeedback: (id: number, data: { action: string; comment?: string; quality_rating?: number; difficulty_feedback?: number }) =>
      request<QuestionFeedback>(`/questions/${id}/feedback`, {
        method: "POST",
        body: JSON.stringify(data)
      }),
    generateAI: (data: {
      topic: string;
      sub_topic?: string;
      question_type?: string;
      difficulty_score: number;
      relative_difficulty?: string;
      blooms_level?: string;
      marks?: number;
      negative_marks?: number;
      time_estimate_minutes?: number;
      learning_objective?: string;
      concept_tags?: string[];
      programming_language?: string;
      image_url?: string;
      reference_blueprint?: string;
      target_branch?: string;
      target_year?: number;
    }) =>
      request<{ question: Question; validation_report: any }>("/questions/generate-ai", {
        method: "POST",
        body: JSON.stringify(data)
      }),
    validate: (id: number) => request<any>(`/questions/${id}/validate`, { method: "POST" }),
    generateMultiLangSolutions: (id: number, source_code?: string, source_language: string = "python") =>
      request<{ question_id: number; reference_solutions: Record<string, string>; validation_report: any }>(`/questions/${id}/generate-solutions`, {
        method: "POST",
        body: JSON.stringify({ source_code, source_language })
      }),
    approve: (id: number, force: boolean = false) =>
      request<{ message: string; question: Question }>(`/questions/${id}/publish?force=${force}`, { method: "POST" })
  },

  // Code Execution & Judging
  execute: {
    run: (question_id: number, code: string, language: string, custom_input?: string) =>
      request<CodeRunResult>("/execute/run", {
        method: "POST",
        body: JSON.stringify({ question_id, code, language, custom_input })
      }),
    submit: (event_id: number, question_id: number, code: string, language: string) =>
      request<FinalSubmitResult>("/execute/submit", {
        method: "POST",
        body: JSON.stringify({ event_id, question_id, code, language })
      }),
    submitAsync: (event_id: number, question_id: number, code: string, language: string) =>
      request<AsyncSubmitResult>("/execute/submit-async", {
        method: "POST",
        body: JSON.stringify({ event_id, question_id, code, language })
      }),
    getStatus: (submission_id: number) =>
      request<SubmissionStatusOut>(`/execute/status/${submission_id}`),
    getHistory: (question_id: number) =>
      request<StudentSubmissionHistoryOut>(`/execute/my-submission-history/${question_id}`),
    getMySubmission: (event_id: number, question_id: number) =>
      request<Submission | null>(`/execute/my-submission/${event_id}/${question_id}`)
  },

  // Leaderboards
  leaderboards: {
    getEvent: (event_id: number, branch: string = "ALL", academic_year: number = 0) =>
      request<LeaderboardEntry[]>(`/leaderboards/event/${event_id}?branch=${branch}&academic_year=${academic_year}`),
    getLifetime: (branch: string = "ALL", academic_year: number = 0) =>
      request<LifetimeLeaderboardEntry[]>(`/leaderboards/lifetime?branch=${branch}&academic_year=${academic_year}`)
  },

  // Placement Analytics
  analytics: {
    getOverview: () => request<PlacementAnalytics>("/analytics/overview"),
    getStudentTopics: (user_id: number) => request<{ topic_mastery: Record<string, number>; score_trajectory: any[] }>(`/analytics/student-topics/${user_id}`),
    compare: (student_ids: number[]) => request<StudentComparison[]>(`/analytics/compare?student_ids=${student_ids.join(",")}`),
    getExportUrl: (branch: string = "ALL", academic_year: number = 0) =>
      `${API_BASE_URL}/analytics/export-csv?branch=${branch}&academic_year=${academic_year}`
  },

  // Reports
  reports: {
    getMyReports: () => request<StudentReport[]>("/reports/my-reports"),
    getOrGenerate: (event_id: number, user_id: number) =>
      request<StudentReport>(`/reports/event/${event_id}/student/${user_id}`)
  },

  // Assessments & Proctoring Platform (Phase 5)
  assessments: {
    list: (params?: { status?: string; event_id?: number }) => {
      const q = new URLSearchParams();
      if (params?.status) q.append("status", params.status);
      if (params?.event_id) q.append("event_id", params.event_id.toString());
      return request<Assessment[]>(`/assessments/?${q.toString()}`);
    },
    get: (id: number) => request<Assessment>(`/assessments/${id}`),
    create: (data: Partial<Assessment>) =>
      request<Assessment>("/assessments/", {
        method: "POST",
        body: JSON.stringify(data)
      }),
    update: (id: number, data: Partial<Assessment>) =>
      request<Assessment>(`/assessments/${id}`, {
        method: "PUT",
        body: JSON.stringify(data)
      }),
    delete: (id: number) =>
      request<{ message: string }>(`/assessments/${id}`, {
        method: "DELETE"
      }),
    publish: (id: number) =>
      request<{ message: string; assessment: Assessment }>(`/assessments/${id}/publish`, {
        method: "POST"
      }),
    close: (id: number) =>
      request<{ message: string; assessment: Assessment }>(`/assessments/${id}/close`, {
        method: "POST"
      }),
    archive: (id: number) =>
      request<{ message: string; assessment: Assessment }>(`/assessments/${id}/archive`, {
        method: "POST"
      }),
    start: (id: number) =>
      request<AttemptState>(`/assessments/${id}/start`, {
        method: "POST"
      }),
    getAttempt: (attempt_id: number) =>
      request<AttemptState>(`/assessments/attempts/${attempt_id}`),
    saveAnswer: (attempt_id: number, data: AnswerSaveRequest) =>
      request<AnswerSaveResponse>(`/assessments/attempts/${attempt_id}/save-answer`, {
        method: "POST",
        body: JSON.stringify(data)
      }),
    logAntiCheat: (attempt_id: number, data: AntiCheatEventCreate) =>
      request<{ message: string; switch_count: number; integrity_score: number; action_taken: string }>(
        `/assessments/attempts/${attempt_id}/anti-cheat-event`,
        {
          method: "POST",
          body: JSON.stringify(data)
        }
      ),
    heartbeat: (attempt_id: number, session_token: string) =>
      request<{ remaining_seconds: number; is_active: boolean; status: AttemptStatus }>(
        `/assessments/attempts/${attempt_id}/heartbeat`,
        {
          method: "POST",
          body: JSON.stringify({ session_token })
        }
      ),
    submit: (attempt_id: number, data: { final_sync_answers?: AnswerSaveRequest[] } = {}) =>
      request<AssessmentResultDetail>(`/assessments/attempts/${attempt_id}/submit`, {
        method: "POST",
        body: JSON.stringify(data)
      }),
    getResult: (attempt_id: number) =>
      request<AssessmentResultDetail>(`/assessments/attempts/${attempt_id}/result`),
    getAssessmentResults: (id: number) =>
      request<AssessmentResultDetail[]>(`/assessments/${id}/results`),
    getMonitor: (id: number) =>
      request<MonitorDashboard>(`/assessments/${id}/monitor`),
    getEvents: (attempt_id: number) =>
      request<AntiCheatEventOut[]>(`/assessments/attempts/${attempt_id}/events`),
    adminAction: (attempt_id: number, data: { action: string; reason: string; extra_minutes?: number }) =>
      request<{ message: string; new_status: AttemptStatus }>(
        `/assessments/attempts/${attempt_id}/admin-action`,
        {
          method: "POST",
          body: JSON.stringify(data)
        }
      )
  }
};
