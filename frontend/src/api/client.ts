const BASE = import.meta.env.VITE_API_URL ?? "";

export function setToken(token: string) {
  localStorage.setItem("access_token", token);
}

export function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function clearToken() {
  localStorage.removeItem("access_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// ── Jira Explorer types ────────────────────────────────────────────────────
export interface JiraMeta {
  projects: { key: string; name: string }[];
  issueTypes: string[];
  statuses: string[];
  priorities: string[];
  users: string[];
  sprints: string[];
  labels: string[];
  components: string[];
}

export interface JiraIssue {
  key: string;
  summary: string;
  project: { key: string; name: string };
  issueType: string;
  status: string;
  priority: string;
  assignee: string | null;
  reporter: string;
  sprint: string | null;
  labels: string[];
  components: string[];
  created: string;
  dueDate: string | null;
  url: string;
}

export interface JiraSearchParams {
  projectKeys?: string[];
  issueTypes?: string[];
  statuses?: string[];
  priorities?: string[];
  assignees?: string[];
  reporters?: string[];
  sprints?: string[];
  createdFrom?: string;
  createdTo?: string;
  dueDateFrom?: string;
  dueDateTo?: string;
  labels?: string[];
  components?: string[];
  page?: number;
  pageSize?: number;
}

export interface JiraSearchResult {
  total: number;
  page: number;
  pageSize: number;
  issues: JiraIssue[];
}

export interface Metrics {

  total: number;
  done: number;
  wip: number;
  done_ratio: number;
  wip_ratio: number;
  stale_in_progress_count: number;
  [key: string]: unknown;
}

export interface Rules {
  project_health: "HEALTHY" | "WARNING" | "AT RISK" | "UNKNOWN";
  risks: string[];
  actions: string[];
  [key: string]: unknown;
}

export interface Issue {
  key: string;
  summary: string;
  status_name: string;
  assignee: string | null;
  days_since_update: number;
  updated_at: string;
  priority?: string;
  [key: string]: unknown;
}

export interface Project {
  identity: {
    project_key: string;
    project_name: string;
  };
}

export interface DashboardResponse {
  project_key: string;
  days_back: number;
  project_health: "HEALTHY" | "WARNING" | "AT RISK" | "UNKNOWN";
  rules: {
    project_health: "HEALTHY" | "WARNING" | "AT RISK" | "UNKNOWN";
    risks: string[];
    actions: string[];
  };
  metrics: Metrics;
  page: number;
  page_size: number;
  total_issues: number;
  chart_data: {
    labels: string[];
    values: number[];
  } | null;
  assignee_chart_data: {
    labels: string[];
    values: number[];
  } | null;
  daily_update_activity: { date: string; count: number }[];
  team_activity_heatmap: { assignee: string; cells: { weekday: string; hour: number; count: number }[] }[];
  issues_table: Issue[];
  projects: Project[];
  error: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterResponse {
  message: string;
  username: string;
}

export interface CurrentUser {
  id: number;
  username: string;
  email: string | null;
  is_active: boolean;
  roles: string[];
  permissions: string[];
}

export interface Snapshot {
  timestamp: string;
  project: string;
  health: string;
  metrics: Metrics;
  rules: Rules;
}

export interface AdminRole {
  id: number;
  name: string;
  permissions: string[];
}

export interface ManagedUser {
  id: number;
  username: string;
  email: string | null;
  is_active: boolean;
  created_at: string;
  roles: string[];
  role_ids: number[];
  permissions: string[];
}

export interface CreateUserPayload {
  username: string;
  email?: string;
  password: string;
  role_id: number;
  is_active: boolean;
}

export interface UpdateUserPayload {
  username?: string;
  email?: string;
  password?: string;
  role_id?: number;
  is_active?: boolean;
}

export interface AIInsightsResponse {
  project_health: "HEALTHY" | "WARNING" | "AT RISK" | "UNKNOWN";
  risks: string[];
  actions: string[];
}

export interface AIProjectOption {
  key: string;
  name: string;
}

export interface TeamSprint {
  id: string;
  name: string;
  state: string;
}

export interface TeamScorecardMemberMetrics {
  tasks_completed: number;
  tasks_in_progress: number;
  tasks_todo: number;
  overdue_rate: number;
  avg_resolution_time: number | null;
  blocked_tasks: number;
  velocity_trend: number[];
}

export interface TeamScorecardMemberAI {
  performance_score: number;
  performance_label: "Excellent" | "Good" | "Needs Attention" | "At Risk";
  ai_summary: string;
  ai_flag: string | null;
}

export interface TeamScorecardMember {
  accountId: string;
  displayName: string;
  avatarUrl: string;
  metrics: TeamScorecardMemberMetrics;
  ai: TeamScorecardMemberAI;
}

export interface TeamScorecardResponse {
  project: { key: string; name: string };
  sprint: { id: string; name: string };
  members: TeamScorecardMember[];
  generated_at: string;
}

export const api = {
  login: (username: string, password: string) =>
    request<LoginResponse>("/api/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  register: (username: string, email: string, password: string) =>
    request<RegisterResponse>("/api/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    }),

  getMe: () => request<CurrentUser>("/api/me"),

  logout: async () => {
    clearToken();
    return { message: "Logged out" };
  },

  getDashboard: (projectKey?: string, daysBack = 30, page = 1, pageSize = 25) => {
    const params = new URLSearchParams({
      days_back: String(daysBack),
      page: String(page),
      page_size: String(pageSize),
    });

    if (projectKey) {
      params.set("project_key", projectKey);
    }

    return request<DashboardResponse>(`/api/dashboard?${params.toString()}`);
  },

  sendAlert: (projectKey: string) =>
    request<{ status: string; project_key: string; health: string }>(
      `/api/alerts/send?project_key=${encodeURIComponent(projectKey)}`,
      { method: "POST" }
    ),

  getAIProjects: () => request<AIProjectOption[]>("/api/ai/projects"),

  getAIInsights: (projectKey?: string) => {
    const suffix = projectKey
      ? `?project_key=${encodeURIComponent(projectKey)}`
      : "";
    return request<AIInsightsResponse>(`/api/ai/insights${suffix}`);
  },
  
  getTeamSprints: (projectKey: string) =>
    request<{ sprints: TeamSprint[] }>(`/api/team/sprints?projectKey=${encodeURIComponent(projectKey)}`),
    
  getTeamScorecard: (projectKey: string, sprintId: string) =>
    request<TeamScorecardResponse>(`/api/team/scorecard?projectKey=${encodeURIComponent(projectKey)}&sprintId=${encodeURIComponent(sprintId)}`),

  getPortfolio: (daysBack = 30) =>
    request<any[]>(`/api/portfolio?days_back=${daysBack}`),

  getSnapshots: () => request<Snapshot[]>("/api/snapshots"),

  saveSnapshot: (snap: Omit<Snapshot, "timestamp">) =>
    request<Snapshot>("/api/snapshots", {
      method: "POST",
      body: JSON.stringify(snap),
    }),

  deleteSnapshots: () =>
    request<{ message: string }>("/api/snapshots", {
      method: "DELETE",
    }),

  listRoles: () => request<AdminRole[]>("/api/admin/roles"),

  listUsers: () => request<ManagedUser[]>("/api/admin/users"),

  createUser: (payload: CreateUserPayload) =>
    request<ManagedUser>("/api/admin/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateUser: (userId: number, payload: UpdateUserPayload) =>
    request<ManagedUser>(`/api/admin/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  setUserStatus: (userId: number, isActive: boolean) =>
    request<ManagedUser>(`/api/admin/users/${userId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    }),

  deleteUser: (userId: number) =>
    request<void>(`/api/admin/users/${userId}`, {
      method: "DELETE",
    }),

  getJiraMeta: () =>
    request<JiraMeta>("/api/jira/meta"),

  searchJiraIssues: (params: JiraSearchParams) => {
    const qs = new URLSearchParams();
    const appendList = (key: string, arr: string[]) =>
      arr.forEach((v) => qs.append(key, v));

    appendList("projectKeys", params.projectKeys ?? []);
    appendList("issueTypes", params.issueTypes ?? []);
    appendList("statuses", params.statuses ?? []);
    appendList("priorities", params.priorities ?? []);
    appendList("assignees", params.assignees ?? []);
    appendList("reporters", params.reporters ?? []);
    appendList("sprints", params.sprints ?? []);
    appendList("labels", params.labels ?? []);
    appendList("components", params.components ?? []);
    if (params.createdFrom) qs.set("createdFrom", params.createdFrom);
    if (params.createdTo) qs.set("createdTo", params.createdTo);
    if (params.dueDateFrom) qs.set("dueDateFrom", params.dueDateFrom);
    if (params.dueDateTo) qs.set("dueDateTo", params.dueDateTo);
    qs.set("page", String(params.page ?? 0));
    qs.set("pageSize", String(params.pageSize ?? 25));

    return request<JiraSearchResult>(`/api/jira/issues/search?${qs.toString()}`);
  },
};

/** Authenticated download (sends Bearer token). A raw link cannot attach Authorization. */
export async function downloadExport(
  projectKey: string,
  daysBack: number,
  format: "csv" | "json" | "pdf" | "excel"
): Promise<void> {
  const token = getToken();
  const params = new URLSearchParams({ days_back: String(daysBack) });
  const url = `${BASE}/api/project/${encodeURIComponent(projectKey)}/export/${format}?${params}`;
  const res = await fetch(url, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    let err: { detail?: unknown };
    try {
      err = await res.json();
    } catch {
      throw new Error(res.statusText);
    }
    const d = err.detail;
    const msg =
      typeof d === "string"
        ? d
        : Array.isArray(d)
          ? d.map((x) => JSON.stringify(x)).join(", ")
          : res.statusText;
    throw new Error(msg);
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition");
  let filename = `${projectKey}_export.${format === "json" ? "json" : "csv"}`;
  if (format === "pdf") filename = `${projectKey}_export.pdf`;
  if (format === "excel") filename = `${projectKey}_export.xls`;
  const m = cd && /filename="([^"]+)"/.exec(cd);
  if (m) filename = m[1];
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export const hasPermission = (
  user: CurrentUser | null,
  permission: string
): boolean => !!user?.permissions?.includes(permission);
