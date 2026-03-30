import React from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer,
} from "recharts";
import type { Snapshot } from "../api/client";

interface Props {
  snapshots: Snapshot[];
  onSave: () => void;
  onClear: () => void;
}

const HEALTH_SCORE: Record<string, number> = { HEALTHY: 1, WARNING: 2, "AT RISK": 3 };
const HEALTH_LABEL: Record<number, string> = { 1: "HEALTHY", 2: "WARNING", 3: "AT RISK" };

const SnapshotsPanel: React.FC<Props> = ({ snapshots, onSave, onClear }) => {
  const trendData = snapshots.map((s) => ({
    date: s.timestamp.slice(0, 16).replace("T", " "),
    score: HEALTH_SCORE[s.health] ?? 2,
    health: s.health,
  }));

  return (
    <div className="fade-in">
      <div className="snapshots-controls">
        <button className="btn btn-primary" onClick={onSave}>
          Save Snapshot
        </button>
        {snapshots.length > 0 && (
          <button className="btn btn-danger" onClick={onClear}>
            Clear All
          </button>
        )}
      </div>

      {snapshots.length === 0 ? (
        <p style={{ color: "var(--muted)", fontSize: "0.88rem" }}>
          No snapshots saved yet. Click "Save Snapshot" to capture current state.
        </p>
      ) : (
        <>
          <div className="table-wrapper" style={{ marginBottom: "1.25rem" }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Project</th>
                  <th>Health</th>
                  <th>Issues</th>
                  <th>WIP</th>
                  <th>Risks</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((s, i) => (
                  <tr key={i}>
                    <td>{s.timestamp.slice(0, 19).replace("T", " ")}</td>
                    <td>{s.project}</td>
                    <td>
                      <span
                        style={{
                          color:
                            s.health === "HEALTHY" ? "var(--green)"
                            : s.health === "WARNING" ? "var(--yellow)"
                            : "var(--orange)",
                          fontWeight: 600,
                        }}
                      >
                        {s.health}
                      </span>
                    </td>
                    <td>{s.metrics.total}</td>
                    <td>{s.metrics.wip}</td>
                    <td>{s.rules.risks?.length ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {trendData.length > 1 && (
            <div className="chart-card">
              <div className="chart-title">Project Health Trend</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={trendData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,114,188,0.1)" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text2)" }} />
                  <YAxis
                    domain={[1, 3]}
                    ticks={[1, 2, 3]}
                    tickFormatter={(v) => HEALTH_LABEL[v] ?? ""}
                    tick={{ fontSize: 10, fill: "var(--text2)" }}
                    width={65}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: 3,
                      fontSize: 12,
                    }}
                    formatter={(_val, _name, props) => [props.payload.health, "Health"]}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#0072BC"
                    strokeWidth={2.5}
                    dot={{ fill: "#00DFED", r: 5, strokeWidth: 0 }}
                    activeDot={{ r: 7, fill: "#0072BC" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default SnapshotsPanel;
