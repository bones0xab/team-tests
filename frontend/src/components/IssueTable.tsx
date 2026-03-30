import React, { useState, useMemo } from "react";
import type { Issue } from "../api/client";

interface Props {
  issues: Issue[];
}

function getBadgeClass(status: string): string {
  const s = status.toLowerCase();
  if (s.includes("done") || s.includes("closed") || s.includes("resolved")) return "badge-done";
  if (s.includes("progress") || s.includes("active")) return "badge-progress";
  if (s.includes("review") || s.includes("testing")) return "badge-review";
  return "badge-todo";
}

const IssueTable: React.FC<Props> = ({ issues }) => {
  const [statusFilter, setStatusFilter] = useState("All");
  const [sortBy, setSortBy] = useState<"days_since_update" | "status_name" | "assignee">(
    "days_since_update"
  );
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const statuses = useMemo(() => {
    const s = new Set(issues.map((i) => i.status_name).filter(Boolean));
    return ["All", ...Array.from(s).sort()];
  }, [issues]);

  const filtered = useMemo(() => {
    let list = statusFilter === "All"
      ? [...issues]
      : issues.filter((i) => i.status_name === statusFilter);

    list.sort((a, b) => {
      const av = a[sortBy] ?? "";
      const bv = b[sortBy] ?? "";
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [issues, statusFilter, sortBy, sortDir]);

  const handleSort = (col: typeof sortBy) => {
    if (col === sortBy) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  const arrow = (col: typeof sortBy) =>
    sortBy === col ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  return (
    <div className="fade-in">
      <div className="table-controls">
        <div>
          <label style={{ fontSize: "0.78rem", color: "var(--muted)", marginRight: "0.4rem" }}>
            Status
          </label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            {statuses.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Key</th>
              <th>Summary</th>
              <th onClick={() => handleSort("status_name")}>Status{arrow("status_name")}</th>
              <th onClick={() => handleSort("assignee")}>Assignee{arrow("assignee")}</th>
              <th onClick={() => handleSort("days_since_update")}>
                Days Inactive{arrow("days_since_update")}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((issue) => (
              <tr key={issue.key}>
                <td>
                  <span style={{ fontFamily: "'Rajdhani', sans-serif", fontWeight: 600, color: "var(--blue)" }}>
                    {issue.key}
                  </span>
                </td>
                <td style={{ maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {issue.summary}
                </td>
                <td>
                  <span className={`badge ${getBadgeClass(issue.status_name)}`}>
                    {issue.status_name}
                  </span>
                </td>
                <td>{issue.assignee || "Unassigned"}</td>
                <td>
                  <span style={{ color: issue.days_since_update > 7 ? "var(--orange)" : "var(--text2)" }}>
                    {issue.days_since_update}d
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="count-label">
        Showing {filtered.length} of {issues.length} issues
      </div>
    </div>
  );
};

export default React.memo(IssueTable);
