import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { CurrentUser, JiraIssue, JiraMeta, JiraSearchParams } from "../api/client";
import { api } from "../api/client";
import "./JiraExplorerPage.css";

// ── Types ────────────────────────────────────────────────────────────────
interface Props { user: CurrentUser; onLogout: () => void; }

type SortKey = keyof Pick<
  JiraIssue,
  "key" | "summary" | "issueType" | "status" | "priority" | "assignee" | "created" | "dueDate"
>;

const emptyFilters: JiraSearchParams = {
  projectKeys: [], issueTypes: [], statuses: [], priorities: [],
  assignees: [], reporters: [], sprints: [], labels: [], components: [],
  createdFrom: "", createdTo: "", dueDateFrom: "", dueDateTo: "",
  page: 0, pageSize: 25,
};

// ── Helpers ───────────────────────────────────────────────────────────────
const PRIORITY_ORDER: Record<string, number> = {
  Blocker: 0, Highest: 1, High: 2, Medium: 3, Low: 4, Lowest: 5,
};

function statusChip(s: string) {
  const lc = s.toLowerCase();
  if (lc.includes("done") || lc.includes("closed") || lc.includes("resolved"))
    return "jx-chip jx-chip-done";
  if (lc.includes("progress") || lc.includes("review"))
    return "jx-chip jx-chip-progress";
  if (lc.includes("block"))
    return "jx-chip jx-chip-blocked";
  return "jx-chip jx-chip-todo";
}

function priorityChip(p: string) {
  const lc = p.toLowerCase();
  if (lc === "highest" || lc === "high" || lc === "blocker")
    return "jx-chip jx-chip-p-high";
  if (lc === "medium")
    return "jx-chip jx-chip-p-medium";
  return "jx-chip jx-chip-p-low";
}

function sortIssues(issues: JiraIssue[], key: SortKey, asc: boolean): JiraIssue[] {
  return [...issues].sort((a, b) => {
    let va: string | number = a[key] ?? "";
    let vb: string | number = b[key] ?? "";
    if (key === "priority") {
      va = PRIORITY_ORDER[a.priority] ?? 99;
      vb = PRIORITY_ORDER[b.priority] ?? 99;
    }
    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  });
}

function countActiveFilters(f: JiraSearchParams): number {
  const lists: (keyof JiraSearchParams)[] = [
    "projectKeys", "issueTypes", "statuses", "priorities",
    "assignees", "reporters", "sprints", "labels", "components",
  ];
  let n = 0;
  for (const k of lists) n += ((f[k] as string[]) ?? []).length;
  if (f.createdFrom || f.createdTo) n++;
  if (f.dueDateFrom || f.dueDateTo) n++;
  return n;
}

// ── Tag input component ───────────────────────────────────────────────────
function TagInput({
  values, onChange, placeholder,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const add = (v: string) => {
    const trimmed = v.trim();
    if (trimmed && !values.includes(trimmed)) onChange([...values, trimmed]);
    setDraft("");
  };

  return (
    <div
      className="jx-tags-wrap"
      onClick={() => inputRef.current?.focus()}
    >
      {values.map((v) => (
        <span className="jx-tag" key={v}>
          {v}
          <span
            className="jx-tag-x"
            onClick={(e) => { e.stopPropagation(); onChange(values.filter((x) => x !== v)); }}
          >×</span>
        </span>
      ))}
      <input
        ref={inputRef}
        className="jx-tag-input"
        value={draft}
        placeholder={values.length === 0 ? placeholder : ""}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(draft); }
          if (e.key === "Backspace" && draft === "" && values.length > 0) {
            onChange(values.slice(0, -1));
          }
        }}
        onBlur={() => { if (draft.trim()) add(draft); }}
      />
    </div>
  );
}

// ── Checkbox group component ──────────────────────────────────────────────
function CheckGroup({
  options, selected, onChange,
}: {
  options: string[];
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const toggle = (v: string) =>
    onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]);

  return (
    <div className="jx-check-group">
      {options.map((opt) => (
        <label className="jx-check-item" key={opt}>
          <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)} />
          {opt}
        </label>
      ))}
    </div>
  );
}

// ── Multi-select dropdown ─────────────────────────────────────────────────
function MultiSelect({
  options, selected, onChange, placeholder,
}: {
  options: { key: string; name: string }[];
  selected: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const toggle = (key: string) =>
    onChange(selected.includes(key) ? selected.filter((x) => x !== key) : [...selected, key]);

  return (
    <div className="jx-check-group" style={{ maxHeight: 160 }}>
      {options.length === 0 && (
        <div style={{ padding: "6px 8px", fontSize: 12, color: "var(--muted2)" }}>
          {placeholder ?? "No options"}
        </div>
      )}
      {options.map((opt) => (
        <label className="jx-check-item" key={opt.key}>
          <input type="checkbox" checked={selected.includes(opt.key)} onChange={() => toggle(opt.key)} />
          <span style={{ fontFamily: "var(--mono)", fontSize: 11, marginRight: 4 }}>{opt.key}</span>
          {opt.name !== opt.key && (
            <span style={{ fontSize: 12, color: "var(--muted2)" }}>{opt.name}</span>
          )}
        </label>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────
const JiraExplorerPage: React.FC<Props> = ({ user, onLogout }) => {
  const navigate = useNavigate();

  const [meta, setMeta] = useState<JiraMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);

  const [filters, setFilters] = useState<JiraSearchParams>(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState<JiraSearchParams>(emptyFilters);

  const [issues, setIssues] = useState<JiraIssue[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const [sortKey, setSortKey] = useState<SortKey>("created");
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  // Load meta
  useEffect(() => {
    api.getJiraMeta()
      .then(setMeta)
      .catch((e) => setMetaError(e instanceof Error ? e.message : "Failed to load metadata"));
  }, []);

  // Search
  const doSearch = useCallback(async (params: JiraSearchParams, pg: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.searchJiraIssues({ ...params, page: pg, pageSize: PAGE_SIZE });
      setIssues(res.issues);
      setTotal(res.total);
      setPage(pg);
      setSearched(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const applyFilters = () => {
    const applied = { ...filters, page: 0 };
    setAppliedFilters(applied);
    doSearch(applied, 0);
  };

  const clearFilters = () => {
    setFilters(emptyFilters);
    setAppliedFilters(emptyFilters);
    setIssues([]);
    setTotal(0);
    setSearched(false);
    setPage(0);
  };

  const goPage = (pg: number) => doSearch(appliedFilters, pg);

  const setListFilter = (key: keyof JiraSearchParams, values: string[]) =>
    setFilters((f) => ({ ...f, [key]: values }));

  // Sorted issues (client-side)
  const sortedIssues = useMemo(
    () => sortIssues(issues, sortKey, sortAsc),
    [issues, sortKey, sortAsc]
  );

  const onSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc((a) => !a);
    else { setSortKey(key); setSortAsc(true); }
  };

  const sortArrow = (key: SortKey) =>
    sortKey !== key ? " ⇅" : sortAsc ? " ↑" : " ↓";

  const activeCnt = countActiveFilters(filters);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="jx-root">
      {/* Nav */}
      <nav className="jx-nav">
        <img src="/logo.webp" alt="NTT DATA" className="jx-nav-logo" />
        <div className="jx-nav-sep" />
        <span className="jx-nav-title">JIRA EXPLORER</span>
        <div className="jx-nav-right">
            <span style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--muted)" }}>
              {user.username}
            </span>
            <button className="jx-btn jx-btn-ghost" onClick={() => navigate("/dashboard")}>
              ← Dashboard
            </button>
            <button className="jx-btn jx-btn-ghost" onClick={onLogout}>Sign out</button>
          </div>
      </nav>

      <div className="jx-body">
        {/* ── Sidebar ── */}
        <aside className="jx-sidebar">
          <div className="jx-sidebar-head">
            <span className="jx-sidebar-title">
              Filters
              {activeCnt > 0 && <span className="jx-filter-badge">{activeCnt}</span>}
            </span>
          </div>

          <div className="jx-sidebar-body">
            {/* Project */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Project</div>
              <MultiSelect
                options={meta?.projects ?? []}
                selected={filters.projectKeys ?? []}
                onChange={(v) => setListFilter("projectKeys", v)}
                placeholder="Loading projects..."
              />
            </div>

            {/* Issue Type */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Issue Type</div>
              <CheckGroup
                options={meta?.issueTypes ?? ["Bug", "Story", "Task", "Epic", "Sub-task"]}
                selected={filters.issueTypes ?? []}
                onChange={(v) => setListFilter("issueTypes", v)}
              />
            </div>

            {/* Status */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Status</div>
              <CheckGroup
                options={meta?.statuses ?? ["To Do", "In Progress", "In Review", "Done", "Blocked"]}
                selected={filters.statuses ?? []}
                onChange={(v) => setListFilter("statuses", v)}
              />
            </div>

            {/* Priority */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Priority</div>
              <CheckGroup
                options={meta?.priorities ?? ["Lowest", "Low", "Medium", "High", "Highest"]}
                selected={filters.priorities ?? []}
                onChange={(v) => setListFilter("priorities", v)}
              />
            </div>

            {/* Assignee */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Assignee</div>
              <TagInput
                values={filters.assignees ?? []}
                onChange={(v) => setListFilter("assignees", v)}
                placeholder="Type name + Enter"
              />
            </div>

            {/* Reporter */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Reporter</div>
              <TagInput
                values={filters.reporters ?? []}
                onChange={(v) => setListFilter("reporters", v)}
                placeholder="Type name + Enter"
              />
            </div>

            {/* Sprint */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Sprint</div>
              <TagInput
                values={filters.sprints ?? []}
                onChange={(v) => setListFilter("sprints", v)}
                placeholder="Sprint name or ID + Enter"
              />
            </div>

            {/* Created */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Created Date</div>
              <div className="jx-date-row">
                <input
                  type="date"
                  className="jx-input"
                  value={filters.createdFrom ?? ""}
                  onChange={(e) => setFilters((f) => ({ ...f, createdFrom: e.target.value }))}
                />
                <input
                  type="date"
                  className="jx-input"
                  value={filters.createdTo ?? ""}
                  onChange={(e) => setFilters((f) => ({ ...f, createdTo: e.target.value }))}
                />
              </div>
            </div>

            {/* Due date */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Due Date</div>
              <div className="jx-date-row">
                <input
                  type="date"
                  className="jx-input"
                  value={filters.dueDateFrom ?? ""}
                  onChange={(e) => setFilters((f) => ({ ...f, dueDateFrom: e.target.value }))}
                />
                <input
                  type="date"
                  className="jx-input"
                  value={filters.dueDateTo ?? ""}
                  onChange={(e) => setFilters((f) => ({ ...f, dueDateTo: e.target.value }))}
                />
              </div>
            </div>

            {/* Label / Component */}
            <div className="jx-filter-group">
              <div className="jx-filter-label">Labels</div>
              <TagInput
                values={filters.labels ?? []}
                onChange={(v) => setListFilter("labels", v)}
                placeholder="frontend, bugfix…"
              />
            </div>
            <div className="jx-filter-group">
              <div className="jx-filter-label">Components</div>
              <TagInput
                values={filters.components ?? []}
                onChange={(v) => setListFilter("components", v)}
                placeholder="API, UI…"
              />
            </div>
          </div>

          <div className="jx-sidebar-actions">
            <button
              className="jx-btn jx-btn-primary"
              onClick={applyFilters}
              disabled={loading}
            >
              {loading ? "Searching…" : "Apply Filters"}
            </button>
            <button
              className="jx-btn jx-btn-ghost"
              onClick={clearFilters}
              disabled={loading}
            >
              Clear
            </button>
          </div>
        </aside>

        {/* ── Main ── */}
        <main className="jx-main">
          <div className="jx-main-head">
            <div>
              <div className="jx-page-label">Jira Data Center</div>
              <div className="jx-page-title">Issue Explorer</div>
            </div>
            {searched && (
              <span className="jx-total-badge">
                {total.toLocaleString()} result{total !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          {metaError && (
            <div style={{ padding: "12px 20px", color: "var(--red)", fontSize: 13 }}>
              ⚠ Meta load failed: {metaError} — filters still work, dropdowns may be empty.
            </div>
          )}

          {loading && (
            <div className="jx-state">
              <div className="jx-spinner" />
              Searching Jira…
            </div>
          )}

          {!loading && error && (
            <div className="jx-state" style={{ color: "var(--red)" }}>
              ⚠ {error}
            </div>
          )}

          {!loading && !error && !searched && (
            <div className="jx-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              Set your filters and click <strong style={{ color: "var(--blue)" }}>Apply Filters</strong>
            </div>
          )}

          {!loading && !error && searched && sortedIssues.length === 0 && (
            <div className="jx-state">No issues match your filters.</div>
          )}

          {!loading && sortedIssues.length > 0 && (
            <>
              <div className="jx-table-wrap">
                <table className="jx-table">
                  <thead>
                    <tr>
                      {([
                        ["key", "Key"],
                        ["summary", "Summary"],
                        ["issueType", "Type"],
                        ["status", "Status"],
                        ["priority", "Priority"],
                        ["assignee", "Assignee"],
                        ["created", "Created"],
                        ["dueDate", "Due"],
                      ] as [SortKey, string][]).map(([k, label]) => (
                        <th
                          key={k}
                          className={sortKey === k ? "sorted" : ""}
                          onClick={() => onSort(k)}
                        >
                          {label}{sortArrow(k)}
                        </th>
                      ))}
                      <th>Sprint</th>
                      <th>Labels</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedIssues.map((issue) => (
                      <tr key={issue.key}>
                        <td>
                          <a
                            className="jx-key-link"
                            href={issue.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {issue.key}
                          </a>
                        </td>
                        <td style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {issue.summary}
                        </td>
                        <td>
                          <span className="jx-chip jx-chip-type">{issue.issueType}</span>
                        </td>
                        <td>
                          <span className={statusChip(issue.status)}>{issue.status}</span>
                        </td>
                        <td>
                          <span className={priorityChip(issue.priority)}>{issue.priority}</span>
                        </td>
                        <td>{issue.assignee ?? <span style={{ color: "var(--muted2)" }}>—</span>}</td>
                        <td style={{ fontFamily: "var(--mono)", fontSize: 11 }}>{issue.created}</td>
                        <td style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
                          {issue.dueDate ?? <span style={{ color: "var(--muted2)" }}>—</span>}
                        </td>
                        <td style={{ fontSize: 11, color: "var(--muted)" }}>{issue.sprint ?? "—"}</td>
                        <td>
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                            {issue.labels.slice(0, 3).map((l) => (
                              <span
                                key={l}
                                style={{
                                  fontFamily: "var(--mono)",
                                  fontSize: 10,
                                  background: "var(--surface2)",
                                  padding: "1px 6px",
                                  borderRadius: 4,
                                  color: "var(--muted)",
                                }}
                              >
                                {l}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="jx-pagination">
                <span className="jx-pag-info">
                  {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total.toLocaleString()}
                </span>
                <div className="jx-pag-btns">
                  <button className="jx-pag-btn" disabled={page === 0} onClick={() => goPage(0)}>«</button>
                  <button className="jx-pag-btn" disabled={page === 0} onClick={() => goPage(page - 1)}>‹ Prev</button>
                  <span className="jx-pag-current">Page {page + 1} / {totalPages}</span>
                  <button className="jx-pag-btn" disabled={page + 1 >= totalPages} onClick={() => goPage(page + 1)}>Next ›</button>
                  <button className="jx-pag-btn" disabled={page + 1 >= totalPages} onClick={() => goPage(totalPages - 1)}>»</button>
                </div>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
};

export default JiraExplorerPage;
