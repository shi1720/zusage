/** Typed API client. Auth is an HttpOnly session cookie, so requests just
 * include credentials - no token handling in JavaScript (XSS-safer). */

import type {
  AppConfig,
  Application,
  Catalog,
  ClassOverview,
  ClassSummary,
  Dashboard,
  Drill,
  Interview,
  InterviewLang,
  InterviewSummary,
  Lang,
  ProfileData,
  Progress,
  StudentDetail,
  User,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const put = <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) });
const del = <T>(path: string) => request<T>(path, { method: "DELETE" });

export interface StartInterview {
  occupation_id: string;
  language: InterviewLang;
  persona_id: string;
  mode: "training" | "real";
  length: "quick" | "full";
  application_id?: string | null;
  posting?: string;
  confidence_before?: number | null;
}

export interface OutreachDraft { id:string; application_id:string|null; company:string; kind:string; subject:string; contents:string; status:string; model:string; fallback:boolean; sources:string[]; }
export interface WorkspaceData { push_enabled:boolean; weekly_goal:number; weekly_sessions:number; tour_complete:boolean; key_configured:boolean; key_hint:string; drafts:OutreachDraft[]; nudges:{id:string; company:string; draft_id:string; kind:string; done:boolean}[]; momentum:{points:number;level:string}; activation:Record<string,boolean>; }
export interface ApplicationAnalytics { stages:Record<string,number>; total:number; interview_rate:number; offer_rate:number; quiet_rate:number; median_days_to_interview:number|null; weekly:{week:string;applications:number}[]; }
export const api = {
  workspace: {
    push:(subscription:unknown)=>post<{ok:boolean}>("/api/workspace/push",subscription),
    disablePush:()=>del<{ok:boolean}>("/api/workspace/push"),
    capture:(text:string)=>post<Partial<Application>>("/api/workspace/capture",{text}),
    get:()=>request<WorkspaceData>("/api/workspace"),
    preferences:(body:{weekly_goal:number;tour_complete:boolean})=>patch<{ok:boolean}>("/api/workspace/preferences",body),
    key:(key:string)=>put<{ok:boolean}>("/api/workspace/key",{key}),
    removeKey:()=>del<{ok:boolean}>("/api/workspace/key"),
    password:(current_password:string,new_password:string)=>put<{ok:boolean}>("/api/workspace/password",{current_password,new_password}),
    recoveryCode:()=>post<{code:string}>("/api/workspace/recovery-code"),
    recover:(username:string,code:string,new_password:string)=>post<{ok:boolean}>("/api/workspace/recover",{username,code,new_password}),
    generate:(body:{application_id:string;kind:string})=>post<OutreachDraft>("/api/workspace/generate",body),
    updateDraft:(id:string,body:{contents:string;subject:string;status?:string})=>patch<OutreachDraft>(`/api/workspace/drafts/${id}`,body),
    scan:()=>post<{ok:boolean}>("/api/workspace/scan"),
    done:(id:string)=>post<{ok:boolean}>(`/api/workspace/nudges/${id}/done`),
    analytics:()=>request<ApplicationAnalytics>("/api/workspace/analytics"),
    import:(body:{contents:string;kind:string})=>post<{imported:number;errors:{row:number;reason:string}[]}>("/api/workspace/import",body),
    download:async(kind:string)=>{const response=await fetch(`/api/workspace/export/${kind}`,{credentials:"same-origin"});if(!response.ok)throw new Error("Could not export your data");const url=URL.createObjectURL(await response.blob());const a=document.createElement("a");a.href=url;a.download=`zusage-${kind}.csv`;a.click();URL.revokeObjectURL(url);},
  },
  config: () => request<AppConfig>("/api/config"),
  catalog: () => request<Catalog>("/api/catalog"),

  auth: {
    me: () => request<User>("/api/me"),
    login: (username: string, password: string) => post<User>("/api/auth/login", { username, password }),
    register: (body: {
      username: string;
      password: string;
      display_name: string;
      role: "student" | "teacher";
      class_code?: string;
      ui_lang: Lang;
    }) => post<User>("/api/auth/register", body),
    demo: (role: "student" | "teacher") => post<User>(`/api/auth/demo/${role}`),
    logout: () => post<{ ok: boolean }>("/api/auth/logout"),
  },

  me: {
    update: (body: Partial<Pick<User, "display_name" | "ui_lang" | "consent_share" | "onboarded">>) =>
      patch<User>("/api/me", body),
    joinClass: (code: string) => post<User>("/api/me/join-class", { code }),
    leaveClass: () => post<User>("/api/me/leave-class"),
    profile: () => request<{ data: ProfileData }>("/api/me/profile"),
    saveProfile: (data: ProfileData) => put<{ data: ProfileData }>("/api/me/profile", { data }),
    export: () => request<unknown>("/api/me/export"),
    remove: () => del<{ ok: boolean }>("/api/me"),
  },

  interviews: {
    list: () => request<InterviewSummary[]>("/api/interviews"),
    get: (id: string) => request<Interview>(`/api/interviews/${id}`),
    start: (body: StartInterview) => post<Interview>("/api/interviews", body),
    answer: (id: string, answer: string) => post<Interview>(`/api/interviews/${id}/answer`, { answer }),
    retry: (id: string, answer: string) => post<Interview>(`/api/interviews/${id}/retry`, { answer }),
    rate: (id: string, turn_idx: number, rating: number) =>
      post<Interview>(`/api/interviews/${id}/self-rating`, { turn_idx, rating }),
    resume: (id: string) => post<Interview>(`/api/interviews/${id}/resume`),
    finish: (id: string, confidence_after?: number | null) =>
      post<Interview>(`/api/interviews/${id}/finish`, { confidence_after: confidence_after ?? null }),
    remove: (id: string) => del<{ ok: boolean }>(`/api/interviews/${id}`),
  },

  applications: {
    list: () => request<Application[]>("/api/applications"),
    create: (body: Partial<Application>) => post<Application>("/api/applications", body),
    update: (id: string, body: Partial<Application>) => patch<Application>(`/api/applications/${id}`, body),
    remove: (id: string) => del<{ ok: boolean }>(`/api/applications/${id}`),
    restore: (id: string) => post<Application>(`/api/applications/${id}/restore`),
  },

  drills: {
    list: () => request<Drill[]>("/api/drills"),
    start: (id: string, language?: InterviewLang) =>
      post<Interview>(`/api/drills/${id}/start`, language ? { language } : {}),
  },

  dashboard: () => request<Dashboard>("/api/dashboard"),
  progress: () => request<Progress>("/api/progress"),

  classes: {
    list: () => request<ClassSummary[]>("/api/classes"),
    create: (name: string, school: string) => post<ClassSummary>("/api/classes", { name, school }),
    get: (id: string) => request<ClassOverview>(`/api/classes/${id}`),
    newCode: (id: string) => post<{ code: string }>(`/api/classes/${id}/new-code`),
    student: (id: string, studentId: string) => request<StudentDetail>(`/api/classes/${id}/students/${studentId}`),
  },
};
