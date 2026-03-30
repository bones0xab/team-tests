import React, { useMemo } from "react";
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Legend, Area, AreaChart, Cell,
} from "recharts";
import type { Issue } from "../api/client";

const COLORS = ["#0072BC","#00DFED","#00CB5D","#19A3FC","#FFC400","#FF7A00","#005B96","#009AA4"];

interface Props {
  issues: Issue[];
  dailyUpdateActivity?: { date: string; count: number }[];
  teamActivityHeatmap?: { assignee: string; cells: { weekday: string; hour: number; count: number }[] }[];
}

// ── Status Bar Chart ────────────────────────────────────────────────────────
const StatusChart: React.FC<{ issues: Issue[] }> = ({ issues }) => {
  const data = useMemo(() => {
    const counts: Record<string, number> = {};
    issues.forEach((i) => {
      const s = i.status_name || "Unknown";
      counts[s] = (counts[s] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [issues]);

  return (
    <div className="chart-card">
      <div className="chart-title">Issues by Status</div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,114,188,0.1)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11, fill: "var(--text2)" }}
            angle={-30}
            textAnchor="end"
            interval={0}
          />
          <YAxis tick={{ fontSize: 11, fill: "var(--text2)" }} />
          <Tooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 3,
              fontSize: 12,
              color: "var(--text)",
            }}
          />
          <Bar dataKey="value" radius={[2, 2, 0, 0]}>
            {data.map((_, idx) => (
              <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

// ── Assignee Pie Chart ──────────────────────────────────────────────────────
const AssigneeChart: React.FC<{ issues: Issue[] }> = ({ issues }) => {
  const data = useMemo(() => {
    const counts: Record<string, number> = {};
    issues.forEach((i) => {
      const a = i.assignee || "Unassigned";
      counts[a] = (counts[a] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  }, [issues]);

  return (
    <div className="chart-card">
      <div className="chart-title">Issues by Assignee</div>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={65}
            outerRadius={100}
            dataKey="value"
            paddingAngle={2}
          >
            {data.map((_, idx) => (
              <Cell key={idx} fill={COLORS[idx % COLORS.length]} stroke="var(--card)" strokeWidth={2} />
            ))}
          </Pie>
          <Legend
            wrapperStyle={{ fontSize: 11, color: "var(--text2)" }}
            iconSize={10}
            iconType="circle"
          />
          <Tooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 3,
              fontSize: 12,
              color: "var(--text)",
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

// ── Timeline Area Chart ─────────────────────────────────────────────────────
const TimelineChart: React.FC<{ issues: Issue[]; backendData?: { date: string; count: number }[] }> = ({ issues, backendData }) => {
  const data = useMemo(() => {
    if (backendData && backendData.length > 0) return backendData;
    const counts: Record<string, number> = {};
    issues.forEach((i) => {
      if (i.updated_at) {
        const day = String(i.updated_at).slice(0, 10);
        counts[day] = (counts[day] || 0) + 1;
      }
    });
    return Object.entries(counts)
      .map(([date, count]) => ({ date, count }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [issues, backendData]);

  return (
    <div className="chart-card" style={{ marginBottom: "1.25rem" }}>
      <div className="chart-title">Daily Update Activity</div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#0072BC" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#0072BC" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,114,188,0.1)" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text2)" }} />
          <YAxis tick={{ fontSize: 10, fill: "var(--text2)" }} />
          <Tooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 3,
              fontSize: 12,
              color: "var(--text)",
            }}
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke="#0072BC"
            strokeWidth={2.5}
            fill="url(#blueGrad)"
            dot={{ fill: "#00DFED", r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: "#0072BC" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

// ── Heatmap ────────────────────────────────────────────────
const HeatmapChart: React.FC<{ issues: Issue[]; backendData?: { assignee: string; cells: { weekday: string; hour: number; count: number }[] }[] }> = ({ issues, backendData }) => {
  const { assignees, columns, matrix } = useMemo(() => {
    if (backendData && backendData.length > 0) {
      // Backend provides Weekday x Hour
      const assignees = backendData.map(d => d.assignee);
      // Filter out empty columns to keep the heatmap compact
      const allCells = backendData.flatMap(d => d.cells);
      const activeColumns = new Set<string>();
      allCells.forEach(c => {
        if (c.count > 0) activeColumns.add(`${c.weekday} ${c.hour}:00`);
      });
      const columns = Array.from(activeColumns).sort();
      
      const matrix = backendData.map(d => {
        return columns.map(col => {
          const [wd, hr] = col.split(" ");
          const hourNum = parseInt(hr.split(":")[0], 10); // Parse hour part correctly
          const cell = d.cells.find(c => c.weekday === wd && c.hour === hourNum);
          return cell ? cell.count : 0;
        });
      });
      return { assignees, columns, matrix };
    }

    const counts: Record<string, Record<string, number>> = {};
    const dateSet = new Set<string>();

    issues.forEach((i) => {
      const a = i.assignee || "Unassigned";
      const d = i.updated_at ? String(i.updated_at).slice(0, 10) : null;
      if (!d) return;
      dateSet.add(d);
      if (!counts[a]) counts[a] = {};
      counts[a][d] = (counts[a][d] || 0) + 1;
    });

    const columns = Array.from(dateSet).sort().slice(-14); // last 14 active days
    const assignees = Object.keys(counts);
    const matrix: number[][] = assignees.map((a) =>
      columns.map((d) => counts[a][d] || 0)
    );
    return { assignees, columns, matrix };
  }, [issues, backendData]);

  const maxVal = Math.max(1, ...matrix.flat());

  if (assignees.length === 0 || columns.length === 0) {
    return (
      <div className="chart-card">
        <div className="chart-title">Team Activity Heatmap</div>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem", padding: "1rem 0" }}>
          Not enough activity data to display heatmap.
        </p>
      </div>
    );
  }

  const cellSize = 28;
  const labelWidth = 110;

  return (
    <div className="chart-card" style={{ overflowX: "auto" }}>
      <div className="chart-title">Team Activity Heatmap</div>
      <div style={{ minWidth: labelWidth + columns.length * cellSize }}>
        {/* Date headers */}
        <div style={{ display: "flex", marginLeft: labelWidth }}>
          {columns.map((d) => (
            <div
              key={d}
              style={{
                width: cellSize,
                fontSize: 9,
                color: "var(--muted)",
                textAlign: "center",
                transform: "rotate(-45deg)",
                transformOrigin: "bottom left",
                marginBottom: 4,
                paddingLeft: 4,
                whiteSpace: "nowrap",
              }}
            >
              {d.length > 5 ? d.slice(5) : d}
            </div>
          ))}
        </div>
        {/* Rows */}
        {assignees.map((a, ai) => (
          <div key={a} style={{ display: "flex", alignItems: "center", marginBottom: 3 }}>
            <div
              style={{
                width: labelWidth,
                fontSize: 11,
                color: "var(--text2)",
                paddingRight: 8,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={a}
            >
              {a}
            </div>
            {matrix[ai].map((val, di) => {
              const intensity = val / maxVal;
              const bg =
                val === 0
                  ? "rgba(0,114,188,0.05)"
                  : `rgba(0,${Math.round(114 + (223 - 114) * intensity)},${Math.round(188 + (237 - 188) * intensity)},${0.2 + 0.8 * intensity})`;
              return (
                <div
                  key={di}
                  title={`${a} · ${columns[di]}: ${val} updates`}
                  style={{
                    width: cellSize - 2,
                    height: cellSize - 2,
                    marginRight: 2,
                    background: bg,
                    borderRadius: 2,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 9,
                    color: intensity > 0.5 ? "#fff" : "var(--muted)",
                    cursor: "default",
                  }}
                >
                  {val > 0 ? val : ""}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Main Charts export ──────────────────────────────────────────────────────
const Charts: React.FC<Props> = React.memo(({ issues, dailyUpdateActivity, teamActivityHeatmap }) => (
  <div className="charts-root">
    <div className="charts-grid">
      <StatusChart issues={issues} />
      <AssigneeChart issues={issues} />
    </div>
    <TimelineChart issues={issues} backendData={dailyUpdateActivity} />
    <HeatmapChart issues={issues} backendData={teamActivityHeatmap} />
  </div>
));

export default Charts;
