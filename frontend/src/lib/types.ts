/* Mirror of backend/app/schemas/*.py — keep 1:1. No `any`. */

export type Role = "recruiter" | "candidate";
export type ApplicationStatus =
  | "submitted"
  | "parsed"
  | "ai_assessed"
  | "recruiter_review"
  | "shortlisted"
  | "interview"
  | "selected"
  | "rejected"
  | "withdrawn";
export type ProcessingState = "queued" | "processing" | "done" | "failed";
export type ParseStatus = "pending" | "processing" | "parsed" | "failed";
export type RequirementKind = "required" | "preferred";
export type EvidenceStatus = "evidenced" | "partial" | "missing_evidence" | "confirmed_absent";
export type MatchType = "exact" | "alias" | "related" | "semantic" | "self_reported" | "none";
export type Verification = "verified" | "fuzzy" | "unverified" | "self_reported";
export type SkillSource = "ai" | "rules" | "candidate" | "recruiter";
export type Presence = "present" | "absent";
export type Difficulty = "beginner" | "intermediate" | "advanced";
export type JobStatus = "open" | "closed";
export type InterviewType = "technical" | "hr" | "behavioral" | "panel" | "final";
export type InterviewStatus = "scheduled" | "completed" | "cancelled";
export type Recommendation = "strong_yes" | "yes" | "no" | "strong_no";
export type EducationLevel = "none" | "high_school" | "diploma" | "bachelor" | "master" | "phd";
export type EmploymentType = "full_time" | "part_time" | "contract" | "internship";
export type WorkMode = "onsite" | "hybrid" | "remote";
export type ExtractionMethod = "llm" | "rules";
export type Severity = "info" | "warning" | "critical";

export interface Msg {
  detail: string;
}

export interface CandidateBrief {
  id: string;
  full_name: string;
  email: string;
  headline: string | null;
  location: string | null;
}

export interface JobBrief {
  id: string;
  title: string;
  department: string | null;
  location: string | null;
  status: JobStatus;
}

export interface Evidence {
  quote: string;
  start: number | null;
  end: number | null;
  similarity: number | null;
  section: string | null;
}

export interface Flag {
  type: string;
  message: string;
  severity: Severity;
}

/* ----------------------------------------------------------------- auth */
export interface RegisterIn {
  email: string;
  password: string;
  full_name: string;
  role: Role;
  invite_code?: string | null;
}
export interface LoginIn {
  email: string;
  password: string;
}
export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  created_at: string;
  email_verified?: boolean;
}
export interface HealthComponent {
  ok: boolean;
  detail: string | null;
}
export interface HealthOut {
  status: string;
  database: HealthComponent;
  database_backend: string;
  llm: HealthComponent;
  llm_model: string | null;
  embeddings: HealthComponent;
  embedding_model: string | null;
  embedding_dim: number | null;
}

/* ----------------------------------------------------------------- jobs */
export interface JobWeights {
  skills: number;
  experience: number;
  projects: number;
  qualifications: number;
}
export interface RequirementIn {
  skill: string;
  kind: RequirementKind;
  importance: number;
}
export interface RequirementOut {
  id: string;
  skill: string;
  kind: RequirementKind;
  importance: number;
}
export interface JobIn {
  title: string;
  department?: string | null;
  location?: string | null;
  employment_type: EmploymentType;
  work_mode: WorkMode;
  salary_min?: number | null;
  salary_max?: number | null;
  currency: string;
  description: string;
  min_experience_years: number;
  education_level: EducationLevel;
  qualifications: string[];
  requirements: RequirementIn[];
  weights?: JobWeights | null;
}
export type JobUpdate = Partial<JobIn>;
export interface JobOut {
  id: string;
  recruiter_id: string;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: EmploymentType;
  work_mode: WorkMode;
  salary_min: number | null;
  salary_max: number | null;
  currency: string;
  description: string;
  min_experience_years: number;
  education_level: EducationLevel;
  qualifications: string[];
  weights: JobWeights;
  status: JobStatus;
  version: number;
  requirements: RequirementOut[];
  applicant_count: number;
  shortlisted_count: number;
  pending_review_count: number;
  has_applied: boolean | null;
  created_at: string;
  updated_at: string;
}
export interface JobListItem {
  id: string;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: EmploymentType;
  work_mode: WorkMode;
  status: JobStatus;
  salary_min: number | null;
  salary_max: number | null;
  currency: string;
  min_experience_years: number;
  required_skills: string[];
  preferred_skills: string[];
  applicant_count: number;
  shortlisted_count: number;
  pending_review_count: number;
  has_applied: boolean | null;
  created_at: string;
}
export interface JobExtractIn {
  title?: string | null;
  description: string;
}
export interface ExtractedSkill {
  skill: string;
  importance: number;
  verified: boolean;
  evidence: string | null;
}
export interface JobExtractOut {
  required_skills: ExtractedSkill[];
  preferred_skills: ExtractedSkill[];
  min_experience_years: number | null;
  education_level: EducationLevel | null;
  qualifications: string[];
  method: ExtractionMethod;
  warnings: string[];
}

/* ----------------------------------------------------------------- resumes */
export interface ContactInfo {
  name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  links: string[];
}
export interface EducationItem {
  degree: string | null;
  level: string | null;
  field: string | null;
  institution: string | null;
  start_year: number | null;
  end_year: number | null;
  evidence: string | null;
  start: number | null;
  end: number | null;
  verification: Verification;
}
export interface ExperienceItem {
  title: string | null;
  company: string | null;
  start_date: string | null;
  end_date: string | null;
  current: boolean;
  description: string | null;
  skills: string[];
  evidence: string | null;
  start: number | null;
  end: number | null;
  verification: Verification;
}
export interface ProjectItem {
  name: string | null;
  description: string | null;
  tech: string[];
  url: string | null;
  evidence: string | null;
  start: number | null;
  end: number | null;
  verification: Verification;
}
export interface ParsedResume {
  contact: ContactInfo;
  summary: string | null;
  education: EducationItem[];
  experience: ExperienceItem[];
  projects: ProjectItem[];
  certifications: string[];
  total_years_claimed: number | null;
}
export interface CandidateSkillOut {
  id: string;
  name: string;
  raw_name: string | null;
  category: string | null;
  presence: Presence;
  source: SkillSource;
  verification: Verification;
  evidence: string | null;
  start: number | null;
  end: number | null;
  removed: boolean;
}
export interface ResumeOut {
  id: string;
  candidate_id: string;
  filename: string;
  content_type: string | null;
  size: number;
  parse_status: ParseStatus;
  parse_error: string | null;
  warnings: string[];
  integrity_flags: Flag[];
  extraction_method: ExtractionMethod | null;
  page_count: number | null;
  is_current: boolean;
  parsed: ParsedResume | null;
  skills: CandidateSkillOut[];
  created_at: string;
  application_count?: number;
  in_use?: boolean;
  notices?: ResumeNotice[];
}
export interface ResumeNotice {
  code: string;
  level: "info" | "warning" | "error";
  message: string;
  action: "reparse" | "edit" | null;
}
export interface ResumeDetailOut extends ResumeOut {
  text: string | null;
}
export interface SkillAddIn {
  name: string;
  presence: Presence;
}
export interface SkillPatchIn {
  name?: string | null;
  presence?: Presence | null;
  confirm?: boolean | null;
  removed?: boolean | null;
}
export interface ParsedPatchIn {
  contact?: ContactInfo | null;
  summary?: string | null;
  education?: EducationItem[] | null;
  experience?: ExperienceItem[] | null;
  projects?: ProjectItem[] | null;
  certifications?: string[] | null;
}
export interface ProfileIn {
  headline?: string | null;
  phone?: string | null;
  location?: string | null;
  links?: string[] | null;
  interests?: string[] | null;
  talent_pool_opt_in?: boolean | null;
  retention_until?: string | null;
  whatsapp_enabled?: boolean | null;
}
export interface ProfileOut {
  user_id: string;
  full_name: string;
  email: string;
  headline: string | null;
  phone: string | null;
  location: string | null;
  links: string[];
  interests: string[];
  talent_pool_opt_in: boolean;
  retention_until: string | null;
  whatsapp_enabled?: boolean;
  contact_checks?: ContactChecks;
  completion?: ProfileCompletion;
}
export interface ProfileCompletion {
  percent: number;
  missing: string[];
}
export interface EmailCheck {
  value: string;
  valid_format: boolean;
  verified: boolean;
  verified_at: string | null;
}
export interface WhatsappCheck {
  status: "declared" | "not_declared" | "unknown";
  link: string | null;
  note: string;
}
export interface PhoneCheck {
  raw: string;
  e164: string | null;
  valid: boolean;
  possible: boolean;
  country_code: string | number | null;
  region: string | null;
  country: string | null;
  location: string | null;
  line_type: string | null;
  national_length: number | null;
  issues: string[];
  whatsapp: WhatsappCheck;
}
export interface ContactChecks {
  email: EmailCheck;
  phone: PhoneCheck | null;
}

/* ----------------------------------------------------------------- assessment */
export interface RequirementResult {
  requirement_id: string | null;
  skill: string;
  kind: RequirementKind;
  importance: number;
  status: EvidenceStatus;
  credit: number;
  match_type: MatchType;
  matched_as: string | null;
  evidence: Evidence[];
  explanation: string;
}
export type ComponentDetails = Record<string, string | number | boolean | null | string[] | number[] | undefined>;
export interface ComponentScore {
  score: number;
  weight: number;
  points: number;
  applicable: boolean;
  details: Record<string, unknown>;
}
export interface LearningSuggestion {
  skill: string;
  suggestion: string;
}
export interface AssessmentOut {
  id: string;
  application_id: string;
  job_version: number;
  total_score: number;
  override_score: number | null;
  override_reason: string | null;
  effective_score: number;
  components: Record<string, ComponentScore>;
  requirements: RequirementResult[];
  strengths: string[];
  gaps: string[];
  learning_suggestions: LearningSuggestion[];
  summary: string | null;
  summary_method: string | null;
  flags: Flag[];
  semantic_available: boolean;
  stale: boolean;
  created_at: string;
  updated_at: string;
}
export interface ComponentSummary {
  skills: number | null;
  experience: number | null;
  projects: number | null;
  qualifications: number | null;
}
export interface ApplicationRowOut {
  id: string;
  candidate: CandidateBrief;
  status: ApplicationStatus;
  processing_state: ProcessingState;
  processing_error: string | null;
  effective_score: number | null;
  total_score: number | null;
  override_score: number | null;
  components: ComponentSummary;
  matched_skills: string[];
  missing_skills: string[];
  flags: Flag[];
  is_duplicate: boolean;
  resume_id: string | null;
  applied_at: string;
  updated_at: string;
}
export interface JobApplicantsOut {
  job: JobBrief;
  total: number;
  status_counts: Record<string, number>;
  items: ApplicationRowOut[];
}
export interface NoteIn {
  body: string;
}
export interface NoteOut {
  id: string;
  application_id: string;
  author_id: string;
  author_name: string;
  body: string;
  created_at: string;
}
export interface HistoryEventOut {
  id: string;
  action: string;
  from_value: string | null;
  to_value: string | null;
  actor_id: string | null;
  actor_name: string | null;
  actor_role: string | null;
  note: string | null;
  created_at: string;
}
export interface ApplicationDetailOut {
  id: string;
  job: JobBrief;
  candidate: CandidateBrief;
  resume: ResumeDetailOut | null;
  status: ApplicationStatus;
  processing_state: ProcessingState;
  processing_error: string | null;
  cover_note: string | null;
  is_duplicate: boolean;
  assessment: AssessmentOut | null;
  allowed_transitions: ApplicationStatus[];
  notes_count: number;
  contact_checks?: ContactChecks | null;
  interviews: InterviewOut[];
  applied_at: string;
  updated_at: string;
}
export interface TransitionIn {
  to_status: ApplicationStatus;
  reason?: string | null;
}
export interface OverrideIn {
  score: number;
  reason: string;
}
export interface FairnessVariant {
  name: string;
  description: string;
  score: number;
  delta: number;
  model_input_identical: boolean;
}
export interface FairnessOut {
  baseline_score: number;
  max_abs_delta: number;
  passed: boolean;
  variants: FairnessVariant[];
  note: string;
}
export interface CompareCandidate {
  application_id: string;
  candidate: CandidateBrief;
  status: ApplicationStatus;
  effective_score: number | null;
  components: ComponentSummary;
  requirements: RequirementResult[];
  strengths: string[];
  gaps: string[];
  flags: Flag[];
  missing_information: string[];
}
export interface CompareOut {
  job: JobBrief;
  candidates: CompareCandidate[];
}

/* ----------------------------------------------------------------- candidate views */
export interface ApplyIn {
  job_id: string;
  resume_id?: string | null;
  cover_note?: string | null;
}
export interface TimelineItem {
  label: string;
  at: string;
}
export interface CandidateInterviewOut {
  id: string;
  interview_type: string;
  start_at: string;
  end_at: string;
  location: string | null;
  interviewer_name: string | null;
  status: string;
}
export interface CandidateApplicationOut {
  id: string;
  job: JobBrief;
  status: ApplicationStatus;
  status_label: string;
  processing_state: ProcessingState;
  processing_error: string | null;
  resume_id: string | null;
  resume_filename: string | null;
  cover_note: string | null;
  timeline: TimelineItem[];
  interviews: CandidateInterviewOut[];
  can_withdraw: boolean;
  applied_at: string;
  updated_at: string;
}

/* ----------------------------------------------------------------- questions & interviews */
export interface QuestionOut {
  id: string;
  application_id: string;
  difficulty: Difficulty;
  category: string;
  question: string;
  answer_guidelines: string[];
  related_skill: string | null;
  source_quote: string | null;
  source_verified: boolean | null;
  is_edited: boolean;
  position: number;
  created_at: string;
}
export interface QuestionGenerateIn {
  beginner: number;
  intermediate: number;
  advanced: number;
  include_projects: boolean;
  append: boolean;
}
export interface QuestionIn {
  difficulty: Difficulty;
  category: string;
  question: string;
  answer_guidelines: string[];
  related_skill?: string | null;
}
export interface QuestionPatch {
  difficulty?: Difficulty | null;
  category?: string | null;
  question?: string | null;
  answer_guidelines?: string[] | null;
  related_skill?: string | null;
}
export interface FeedbackRatings {
  technical: number;
  communication: number;
  problem_solving: number;
  culture_fit: number;
}
export interface FeedbackIn {
  ratings: FeedbackRatings;
  recommendation: Recommendation;
  comments?: string | null;
}
export interface FeedbackOut {
  id: string;
  interview_id: string;
  author_id: string;
  author_name: string;
  ratings: FeedbackRatings;
  recommendation: Recommendation;
  comments: string | null;
  created_at: string;
}
export interface ConflictOut {
  kind: string;
  interview_id: string;
  start_at: string;
  end_at: string;
  with_whom: string;
  message: string;
}
export interface InterviewIn {
  interviewer_name: string;
  interviewer_email?: string | null;
  interview_type: InterviewType;
  start_at: string;
  duration_minutes: number;
  location?: string | null;
  notes?: string | null;
  force?: boolean;
}
export interface InterviewPatch {
  interviewer_name?: string | null;
  interviewer_email?: string | null;
  interview_type?: InterviewType | null;
  start_at?: string | null;
  duration_minutes?: number | null;
  location?: string | null;
  notes?: string | null;
  status?: InterviewStatus | null;
  force?: boolean;
}
export interface InterviewOut {
  id: string;
  application_id: string;
  candidate_id: string | null;
  candidate_name: string;
  job_id: string | null;
  job_title: string;
  interviewer_name: string;
  interviewer_email: string | null;
  interview_type: InterviewType;
  start_at: string;
  end_at: string;
  location: string | null;
  notes: string | null;
  status: InterviewStatus;
  has_conflict: boolean;
  conflict_details: ConflictOut[];
  feedback: FeedbackOut[];
  created_at: string;
}
export interface ConflictErrorOut {
  detail: string;
  code: string;
  conflicts: ConflictOut[];
}

/* ----------------------------------------------------------------- analytics & misc */
export interface Kpis {
  active_jobs: number;
  total_jobs: number;
  total_applications: number;
  shortlisted: number;
  pending_reviews: number;
  interviews_scheduled: number;
  selected: number;
  rejected: number;
}
export interface JobStageCount {
  job_id: string;
  title: string;
  total: number;
  by_stage: Record<string, number>;
}
export interface StageCount {
  stage: string;
  label: string;
  count: number;
}
export interface SkillGap {
  skill: string;
  count: number;
  percent: number;
}
export interface ScoreBucket {
  bucket: string;
  count: number;
}
export interface ActivityItem {
  at: string;
  text: string;
  application_id: string | null;
}
export interface AnalyticsOut {
  kpis: Kpis;
  applications_by_job: JobStageCount[];
  stage_funnel: StageCount[];
  shortlist_rate: number | null;
  avg_processing_seconds: number | null;
  avg_time_to_decision_hours: number | null;
  top_skill_gaps: SkillGap[];
  score_distribution: ScoreBucket[];
  recent_activity: ActivityItem[];
  job_filter: JobBrief | null;
}
export interface NotificationOut {
  id: string;
  type: string;
  channel: string;
  title: string;
  body: string | null;
  link: string | null;
  recipient_email: string | null;
  read: boolean;
  created_at: string;
}
export interface DuplicateOut {
  id: string;
  status: string;
  reasons: string[];
  similarity: number | null;
  candidate_a: CandidateBrief;
  candidate_b: CandidateBrief;
  created_at: string;
}

/* ----------------------------------------------------------------- search */
export interface TalentSearchIn {
  query: string;
  job_id?: string | null;
  limit?: number;
}
export interface SearchApplicationRef {
  application_id: string;
  job_id: string;
  job_title: string;
  status: ApplicationStatus;
}
export interface TalentSearchResult {
  candidate: CandidateBrief;
  resume_id: string;
  score: number;
  semantic_score: number | null;
  skill_coverage: number | null;
  matched_skills: string[];
  evidence: Evidence[];
  applications: SearchApplicationRef[];
  in_talent_pool: boolean;
}
export interface TalentSearchOut {
  query: string;
  detected_skills: string[];
  mode: string;
  results: TalentSearchResult[];
  warning: string | null;
}
export interface RecommendationOut {
  job: JobBrief;
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  reason: string;
}
export interface TalentPoolItem {
  candidate: CandidateBrief;
  resume_id: string;
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  previously_applied_to: string | null;
  invited: boolean;
}

/* ----------------------------------------------------------------- candidate dashboard & match */
export interface UpcomingInterview extends CandidateInterviewOut {
  job_title: string;
}
export interface CandidateDashboardOut {
  profile: ProfileOut;
  resumes: ResumeOut[];
  applications: CandidateApplicationOut[];
  recommendations: RecommendationOut[];
  open_jobs: JobListItem[];
  upcoming_interviews: UpcomingInterview[];
  unread_notifications: number;
}
export type MatchBand = "strong" | "good" | "partial" | "low";
export interface MyMatchRequirement {
  skill: string;
  kind: RequirementKind;
  importance: number;
  status: EvidenceStatus;
  matched_as: string | null;
  evidence: string | null;
}
export interface MyMatchOut {
  job: JobBrief;
  resume: { id: string; filename: string } | null;
  needs_resume: boolean;
  score: number;
  band: MatchBand;
  components: ComponentSummary;
  requirements: MyMatchRequirement[];
  strengths: string[];
  gaps: string[];
  improvements: LearningSuggestion[];
  tips: string[];
  already_applied: boolean;
  semantic_available: boolean;
}
export interface DeleteResumesOut {
  deleted: string[];
  blocked: { id: string; filename: string; reason: string }[];
}
