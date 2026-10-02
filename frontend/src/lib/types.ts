export type UserRole =
  | "STUDENT"
  | "FACULTY"
  | "QUESTION_SETTER"
  | "REVIEWER"
  | "PLACEMENT_ADMIN"
  | "ADMIN"
  | "SUPER_ADMIN";

export type AccountStatus = "ACTIVE" | "DISABLED" | "PENDING_VERIFICATION";

export type Permission =
  | "VIEW_STUDENTS"
  | "MANAGE_STUDENTS"
  | "EXPORT_STUDENT_DATA"
  | "VIEW_QUESTIONS"
  | "CREATE_QUESTION"
  | "EDIT_QUESTION"
  | "DELETE_QUESTION"
  | "REVIEW_QUESTION"
  | "CREATE_ASSESSMENT"
  | "EDIT_ASSESSMENT"
  | "PUBLISH_ASSESSMENT"
  | "DELETE_ASSESSMENT"
  | "VIEW_ASSESSMENT_RESULTS"
  | "SUBMIT_CODE"
  | "VIEW_OWN_SUBMISSIONS"
  | "VIEW_ALL_SUBMISSIONS"
  | "VIEW_ANALYTICS"
  | "VIEW_PLACEMENT_ANALYTICS"
  | "MANAGE_USERS"
  | "MANAGE_ROLES"
  | "VIEW_AUDIT_LOGS"
  | "MANAGE_SYSTEM_SETTINGS";

export type Branch = "AIML" | "AIDS" | "IIOT" | "AR" | "ALL";

export interface StudentProfile {
  id: number;
  enrollment_no: string;
  branch: string;
  academic_year: number;
  phone?: string;
  is_approved: boolean;
  total_events_participated: number;
  total_lifetime_score: number;
  total_problems_solved: number;
  average_score: number;
  consistency_score: number;
  placement_readiness_rating: "Ready" | "High Potential" | "Developing" | "Needs Focus" | string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  status?: AccountStatus;
  permissions?: Permission[];
  is_active: boolean;
  avatar_url?: string;
  last_login_at?: string;
  created_at: string;
  student_profile?: StudentProfile;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
  permissions: Permission[];
  needs_onboarding: boolean;
}

export interface AuditLog {
  id: number;
  user_id?: number;
  actor_email: string;
  action: string;
  ip_address?: string;
  user_agent?: string;
  status: string;
  details?: Record<string, any>;
  created_at: string;
}

export interface TestCase {
  id: number;
  question_id: number;
  input_data: string;
  expected_output: string;
  is_hidden: boolean;
  explanation?: string;
  points: number;
}

export interface ExampleCase {
  input: string;
  output: string;
  explanation?: string;
}

export type QuestionType = "CODING" | "MCQ" | "SUBJECTIVE";
export type BloomsLevel = "REMEMBER" | "UNDERSTAND" | "APPLY" | "ANALYZE" | "EVALUATE" | "CREATE";
export type QuestionStatus = "DRAFT" | "AI_GENERATED" | "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "PUBLISHED" | "ARCHIVED" | "UNDER_REVIEW";

export interface QualityBreakdown {
  completeness: number;
  clarity: number;
  correctness: number;
  difficulty_consistency: number;
  test_coverage: number;
}

export interface Question {
  id: number;
  title: string;
  slug: string;
  problem_statement: string;
  input_format?: string;
  output_format?: string;
  constraints?: string;
  question_type?: QuestionType;
  subject?: string;
  topic?: string;
  subtopic?: string;
  blooms_level?: BloomsLevel;
  marks?: number;
  negative_marks?: number;
  time_estimate_minutes?: number;
  learning_objective?: string;
  concept_tags?: string[];
  options?: string[];
  correct_answer?: string;
  explanation?: string;
  image_url?: string;
  image_metadata?: Record<string, any>;
  examples?: ExampleCase[];
  topic_tags?: string[];
  difficulty_score: number; // 1-10
  expected_time_complexity?: string;
  expected_space_complexity?: string;
  time_limit_seconds?: number;
  memory_limit_mb?: number;
  reference_solutions?: Record<string, string>;
  status: QuestionStatus;
  validation_status?: "PENDING" | "PASSED" | "FAILED";
  validation_notes?: string;
  quality_score?: number;
  quality_breakdown?: QualityBreakdown | Record<string, any>;
  similarity_hash?: string;
  similarity_score?: number;
  duplicate_of_id?: number;
  version_number?: number;
  parent_question_id?: number;
  is_latest?: boolean;
  change_summary?: string;
  author_id?: number;
  reviewer_id?: number;
  reviewer_feedback?: string;
  reviewed_at?: string;
  rejection_reason?: string;
  total_attempts?: number;
  correct_attempts?: number;
  average_time_seconds?: number;
  experienced_difficulty?: number;
  discrimination_index?: number;
  skip_count?: number;
  is_ai_generated: boolean;
  created_at: string;
  updated_at?: string;
  test_cases_count?: number;
  test_cases?: TestCase[];
  visible_test_cases?: TestCase[];
  points?: number;
  order_index?: number;
}

export interface QuestionVersion {
  id: number;
  title: string;
  version_number: number;
  status: QuestionStatus;
  change_summary?: string;
  is_latest: boolean;
  parent_question_id?: number;
  created_at: string;
}

export interface QuestionFeedback {
  id: number;
  question_id: number;
  reviewer_id?: number;
  action: string;
  comment?: string;
  quality_rating?: number;
  difficulty_feedback?: number;
  created_at: string;
}

export interface DuplicateCheckResult {
  is_duplicate: boolean;
  similarity_score: number;
  normalized_similarity_percent: number;
  matched_question_id?: number;
  matched_title?: string;
  match_reason: string;
  similarity_hash?: string;
}

export interface QuestionAnalytics {
  id: number;
  title: string;
  question_type: string;
  difficulty_score: number;
  experienced_difficulty: number;
  total_attempts: number;
  correct_attempts: number;
  success_rate_percent: number;
  average_time_seconds: number;
  discrimination_index?: number;
  skip_count: number;
  quality_score: number;
  quality_breakdown: QualityBreakdown | Record<string, any>;
  sample_size_reliable: boolean;
}

export interface Event {
  id: number;
  title: string;
  description?: string;
  target_branch: string;
  target_year: number;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  status: "UPCOMING" | "ACTIVE" | "ENDED" | "RESULTS_RELEASED";
  is_leaderboard_visible: boolean;
  allow_branch_questions: boolean;
  are_solutions_released: boolean;
  are_results_released: boolean;
  created_at: string;
  total_questions: number;
  total_participants: number;
  questions?: Question[];
}

export interface CodeRunResult {
  verdict: string;
  passed: boolean;
  execution_time_ms: number;
  memory_used_kb: number;
  output: string;
  expected_output?: string;
  error_message?: string;
  sample_results: {
    test_case_id?: number;
    is_hidden: boolean;
    passed: boolean;
    verdict: string;
    time_ms: number;
    output: string;
    expected: string;
    error?: string;
  }[];
}

export interface FinalSubmitResult {
  submission_id: number;
  verdict: string;
  score: number;
  passed_test_cases: number;
  total_test_cases: number;
  execution_time_ms: number;
  error_message?: string;
  is_final: boolean;
}

export interface Submission {
  id: number;
  event_id: number;
  question_id: number;
  question_title?: string;
  user_id: number;
  student_name?: string;
  enrollment_no?: string;
  branch?: string;
  language: string;
  code: string;
  verdict: string;
  passed_test_cases: number;
  total_test_cases: number;
  score: number;
  execution_time_ms: number;
  error_message?: string;
  is_final: boolean;
  submitted_at: string;
  reference_solution?: string;
}

export interface LeaderboardEntry {
  rank: number;
  user_id: number;
  full_name: string;
  enrollment_no: string;
  branch: string;
  academic_year: number;
  total_score: number;
  problems_solved: number;
  total_time_ms: number;
  last_submission_time?: string;
}

export interface LifetimeLeaderboardEntry {
  rank: number;
  user_id: number;
  full_name: string;
  enrollment_no: string;
  branch: string;
  academic_year: number;
  events_participated: number;
  total_lifetime_score: number;
  total_problems_solved: number;
  average_score: number;
  consistency_score: number;
  placement_readiness_rating: string;
}

export interface StudentReport {
  id: number;
  event_id: number;
  event_title?: string;
  user_id: number;
  student_name?: string;
  enrollment_no?: string;
  branch?: string;
  academic_year?: number;
  score: number;
  rank: number;
  total_participants: number;
  overall_performance_summary: string;
  strengths: string[];
  areas_for_improvement: string[];
  topic_performance: Record<string, string>;
  time_efficiency_rating: string;
  problem_solving_pattern?: string;
  difficulty_handling?: string;
  comparative_analysis?: string;
  generated_at: string;
}

export interface PlacementAnalytics {
  total_registered_students: number;
  total_events_conducted: number;
  total_submissions: number;
  branch_performance: Record<string, {
    total_students: number;
    average_score: number;
    top_score: number;
    placement_ready_count: number;
  }>;
  year_performance: Record<string, {
    total_students: number;
    average_score: number;
    ready_count: number;
  }>;
  topic_mastery: Record<string, number>;
  top_performers: LifetimeLeaderboardEntry[];
  needs_attention_students: LifetimeLeaderboardEntry[];
}

export interface StudentComparison {
  id: number;
  student_id: number;
  user_id: number;
  full_name: string;
  name: string;
  email: string;
  enrollment_no: string;
  branch: string;
  academic_year: number;
  total_score: number;
  total_lifetime_score: number;
  total_events: number;
  total_solved: number;
  average_score: number;
  consistency: number;
  placement_readiness: string;
  readiness: string;
  recent_scores: number[];
  strengths: string[];
  topic_mastery: Record<string, number>;
}

// ==========================================
// PHASE 5: ASSESSMENT & PROCTORING ENGINE TYPES
// ==========================================

export type AssessmentStatus = "DRAFT" | "SCHEDULED" | "PUBLISHED" | "ACTIVE" | "COMPLETED" | "ARCHIVED";
export type AttemptStatus = "IN_PROGRESS" | "SUBMITTED" | "AUTO_SUBMITTED" | "TERMINATED_CHEATING" | "EVALUATED" | "INVALIDATED";
export type AntiCheatEventType =
  | "TAB_SWITCH"
  | "WINDOW_BLUR"
  | "FULLSCREEN_EXIT"
  | "COPY_PASTE"
  | "RIGHT_CLICK"
  | "DEVTOOLS_OPEN"
  | "MULTI_SESSION"
  | "HEARTBEAT_LOSS"
  | "SUSPICIOUS_KEYSTROKE";
export type AntiCheatSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface AssessmentQuestionLink {
  question_id: number;
  section_name?: string;
  order_index?: number;
  marks?: number;
  negative_marks?: number;
  question?: Question;
}

export interface Assessment {
  id: number;
  title: string;
  description?: string;
  event_id?: number;
  status: AssessmentStatus;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  pass_percentage: number;
  max_attempts: number;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  show_results_immediately: boolean;
  allow_review: boolean;
  code_test_visible_count: number;
  max_tab_switches: number;
  auto_terminate_on_cheat: boolean;
  paste_detection_enabled: boolean;
  fullscreen_enforced: boolean;
  webcam_proctoring_enabled: boolean;
  total_marks: number;
  total_questions: number;
  created_by?: number;
  created_at: string;
  updated_at?: string;
  questions?: AssessmentQuestionLink[];
}

export interface AttemptQuestionState {
  question_id: number;
  section_name: string;
  order_index: number;
  marks: number;
  negative_marks: number;
  title: string;
  description: string;
  question_type: "MCQ" | "MULTIPLE_SELECT" | "CODING" | "SUBJECTIVE";
  options?: Array<{ id: string; text: string }>;
  code_template?: Record<string, string>;
  visible_test_cases?: Array<{ id?: number; input_data: string; expected_output: string; explanation?: string }>;
  selected_options?: string[];
  submitted_code?: string;
  submitted_language?: string;
  submitted_text?: string;
  is_flagged?: boolean;
}

export interface AttemptState {
  attempt_id: number;
  assessment_id: number;
  assessment_title: string;
  status: AttemptStatus;
  start_time: string;
  end_time_deadline: string;
  duration_minutes: number;
  remaining_seconds: number;
  current_session_token: string;
  max_tab_switches: number;
  fullscreen_enforced: boolean;
  paste_detection_enabled: boolean;
  auto_terminate_on_cheat: boolean;
  questions: AttemptQuestionState[];
  tab_switch_count: number;
  integrity_score: number;
}

export interface AnswerSaveRequest {
  question_id: number;
  selected_options?: string[];
  submitted_code?: string;
  submitted_language?: string;
  submitted_text?: string;
  is_flagged?: boolean;
  time_spent_seconds?: number;
}

export interface AnswerSaveResponse {
  success: boolean;
  question_id: number;
  saved_at: string;
  remaining_seconds: number;
}

export interface AntiCheatEventCreate {
  event_type: AntiCheatEventType;
  severity: AntiCheatSeverity;
  event_data?: Record<string, any>;
}

export interface AntiCheatEventOut {
  id: number;
  attempt_id: number;
  user_id: number;
  event_type: AntiCheatEventType;
  severity: AntiCheatSeverity;
  event_data?: Record<string, any>;
  timestamp: string;
}

export interface AssessmentResultDetail {
  id: number;
  attempt_id: number;
  assessment_id: number;
  user_id: number;
  student_name?: string;
  enrollment_no?: string;
  branch?: string;
  score_obtained: number;
  total_possible_score: number;
  percentage: number;
  percentile?: number;
  passed: boolean;
  integrity_score: number;
  time_taken_seconds: number;
  submitted_at: string;
  evaluation_breakdown: {
    questions_graded: number;
    score_obtained: number;
    total_possible: number;
    percentage: number;
    section_breakdown?: Record<string, { score: number; total: number }>;
    topic_breakdown?: Record<string, { score: number; total: number }>;
    difficulty_breakdown?: Record<string, { score: number; total: number }>;
    question_results?: Array<{
      question_id: number;
      question_type: string;
      title?: string;
      marks_awarded: number;
      max_marks: number;
      is_correct?: boolean;
      user_answer?: any;
      correct_answer?: any;
      explanation?: string;
      test_cases_passed?: number;
      total_test_cases?: number;
      error_message?: string;
    }>;
  };
}

export interface CandidateMonitorItem {
  attempt_id: number;
  user_id: number;
  candidate_name: string;
  candidate_email: string;
  enrollment_no?: string;
  branch?: string;
  status: AttemptStatus;
  start_time: string;
  end_time_deadline: string;
  remaining_seconds: number;
  switch_count: number;
  integrity_score: number;
  last_heartbeat_at: string;
  is_online: boolean;
  answers_saved_count: number;
  total_questions: number;
  events_count: number;
}

export interface MonitorDashboard {
  assessment_id: number;
  assessment_title: string;
  status: AssessmentStatus;
  total_registered: number;
  total_attempts: number;
  active_candidates: number;
  submitted_count: number;
  terminated_count: number;
  total_violations: number;
  average_integrity_score: number;
  candidates: CandidateMonitorItem[];
}

