/** API types - mirror the FastAPI responses in src/backend/zusage/api. */

export type Lang = "de" | "fr" | "it" | "en";
export type InterviewLang = Lang | "gsw";
export type Criterion = "clarity" | "relevance" | "motivation" | "self_awareness" | "communication" | "examples";
export const CRITERIA: Criterion[] = ["clarity", "relevance", "motivation", "self_awareness", "communication", "examples"];
export type Phase = "intro" | "motivation" | "strengths" | "situational" | "candidate_questions" | "closing";

export interface User {
  id: string;
  username: string;
  display_name: string;
  role: "student" | "teacher" | "admin";
  ui_lang: Lang;
  consent_share: boolean;
  onboarded: boolean;
  classroom: { id: string; name: string; school: string } | null;
}

export interface AppConfig {
  natural_voice?: boolean;
  push_public_key?: string;
  version: string;
  mode: "live" | "offline";
  model: string;
  demo: boolean;
}

export type Localized = Partial<Record<InterviewLang, string>>;

export interface Occupation {
  id: string;
  level: "EFZ" | "EBA";
  field: string;
  icon: string;
  name: Localized;
  company: { name: string; town: string };
  competencies: string[];
}

export interface Persona {
  id: string;
  difficulty: number;
  avatar: string;
  name: Localized;
  role: Localized;
}

export interface Catalog {
  occupations: Occupation[];
  personas: Persona[];
  criteria: Record<Criterion, Localized>;
  levels: Record<number, Localized>;
  languages: InterviewLang[];
}

export interface Assessment {
  scores: Partial<Record<Criterion, number>>;
  evidence?: string;
  strength?: string;
  tip?: string;
  better_answer?: string;
  quality?: "strong" | "solid" | "weak" | "off_topic" | "empty";
  flag?: string;
  degraded?: boolean;
  privacy_note?: string;
}

export interface Turn {
  idx: number;
  question: string;
  qid: string;
  phase: Phase;
  is_followup: boolean;
  answer: string;
  bridge: string;
  retry_of: number | null;
  previous?: { answer: string; scores: Partial<Record<Criterion, number>> } | null;
  self_rating?: number | null;
  assessment?: Assessment;
}

export interface Report {
  overall: number;
  averages: Partial<Record<Criterion, number>>;
  narrative: {
    headline?: string;
    summary?: string;
    strengths?: string[];
    goals?: { title: string; how: string }[];
    best_moment?: string;
    wise_feedback?: string;
  };
  answers: number;
  planned: number;
  followups: number;
  retries: number;
  llm_calls_per_answer: number;
}

export interface Interview {
  id: string;
  status: "active" | "completed" | "abandoned";
  mode: "training" | "real" | "drill";
  length: string;
  language: InterviewLang;
  feedback_language: Lang;
  occupation: { id: string; label: string; level: string; icon: string } | null;
  persona: { id: string; name: string; role: string; avatar: string } | null;
  company: { name: string; town: string };
  application_id: string | null;
  interviewer_message: string;
  current: { phase: Phase | null; is_followup: boolean };
  phases: Phase[];
  progress: { answered: number; planned: number };
  done: boolean;
  safety_pause: boolean;
  safety_message: string | null;
  last_feedback: Assessment | null;
  can_retry: boolean;
  turns: Turn[];
  report: Report | null;
  overall: number | null;
  confidence_before: number | null;
  confidence_after: number | null;
  usage: {
    llm_calls: number;
    answers: number;
    calls_per_answer: number;
    tokens_in: number;
    tokens_out: number;
    avg_latency_ms: number;
    model: string;
  };
  created_at: string;
  completed_at: string | null;
}

export interface InterviewSummary {
  id: string;
  status: string;
  mode: string;
  language: InterviewLang;
  occupation: string;
  company: string | null;
  persona: string;
  overall: number | null;
  answers: number;
  averages: Partial<Record<Criterion, number>> | null;
  confidence_before: number | null;
  confidence_after: number | null;
  created_at: string;
}

export type AppStatus = "interested" | "schnupper" | "applied" | "interview" | "offer" | "rejected";
export const APP_STATUSES: AppStatus[] = ["interested", "schnupper", "applied", "interview", "offer", "rejected"];

export interface Application {
  id: string;
  company: string;
  occupation_id: string;
  title: string;
  town: string;
  posting: string;
  status: AppStatus;
  history: { from?: string; to: string; at: string }[];
  interview_at: string | null;
  contact_name: string;
  notes: string;
  created_at: string;
  updated_at: string;
  practice_sessions: number;
  best_score: number | null;
}

export interface Drill {
  id: string;
  question_id: string;
  question: string;
  phase: Phase;
  criterion: Criterion | "";
  box: number;
  due_at: string;
  due: boolean;
  last_score: number | null;
  best_score: number | null;
  reps: number;
  occupation_id: string;
}

export interface Dashboard {
  due_drills: Drill[];
  next_drill_at: string | null;
  upcoming_interviews: Application[];
  follow_ups: Application[];
  active_interview: Interview | null;
  stats: {
    sessions: number;
    answers: number;
    streak: number;
    last_overall: number | null;
    confidence_gain: number | null;
    applications: Record<AppStatus, number>;
  };
  criteria: Partial<Record<Criterion, number>>;
  focus: Criterion[];
}

export interface TimelinePoint {
  id: string;
  date: string;
  overall: number | null;
  averages: Partial<Record<Criterion, number>>;
  mode: string;
  confidence_before: number | null;
  confidence_after: number | null;
}

export interface Progress {
  timeline: TimelinePoint[];
  criteria_now: Partial<Record<Criterion, number>>;
  calibration: { n: number; accuracy: number; bias: number } | null;
  drills: Drill[];
  streak: number;
}

export interface ProfileData {
  age?: number;
  school?: string;
  canton?: string;
  hobbies?: string[];
  experience?: string;
  strengths?: string;
  stories?: { title: string; text: string }[];
  target_occupation_id?: string;
  interview_language?: InterviewLang;
  persona_id?: string;
}

export interface ClassSummary {
  id: string;
  name: string;
  school: string;
  code: string;
  students: number;
}

export interface StudentRow {
  id: string;
  name: string;
  username: string;
  sessions: number;
  drills_done: number;
  last_practice: string | null;
  latest_overall: number | null;
  first_overall: number | null;
  averages: Partial<Record<Criterion, number>>;
  weakest: Criterion | null;
  confidence_gain: number | null;
  applications: Record<AppStatus, number>;
  consent_share: boolean;
  flags: ("inactive" | "low_confidence" | "interview_soon" | "has_offer")[];
}

export interface ClassOverview {
  class: { id: string; name: string; school: string; code: string };
  students: StudentRow[];
  class_averages: Partial<Record<Criterion, number>>;
  weak_spots: Criterion[];
  weekly_sessions: { week: string; sessions: number }[];
  pipeline: Record<AppStatus, number>;
  students_with_offer: number;
  active_last_7d: number;
}

export interface StudentDetail {
  student: { id: string; name: string; consent_share: boolean };
  timeline: TimelinePoint[];
  sessions: {
    id: string;
    date: string;
    mode: string;
    occupation: string;
    language: InterviewLang;
    overall: number | null;
    averages: Partial<Record<Criterion, number>> | null;
    goals: { title: string; how: string }[] | null;
    detail?: Interview;
  }[];
  applications: { company: string; occupation_id: string; status: AppStatus; interview_at: string | null }[];
}
