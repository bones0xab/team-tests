import React, { useState } from "react";
import { downloadExport } from "../api/client";

interface Props {
  projectKey: string;
  daysBack: number;
}

const ExportButtons: React.FC<Props> = ({ projectKey, daysBack }) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const formats = [
    { label: "↓  CSV", format: "csv" as const },
    { label: "↓  JSON", format: "json" as const },
    { label: "↓  PDF", format: "pdf" as const },
    { label: "↓  Excel", format: "excel" as const },
  ];

  const onDownload = async (format: (typeof formats)[number]["format"]) => {
    setError(null);
    setBusy(format);
    try {
      await downloadExport(projectKey, daysBack, format);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="export-row fade-in">
      {error && (
        <p className="export-error" role="alert">
          {error}
        </p>
      )}
      {formats.map(({ label, format }) => (
        <button
          key={format}
          type="button"
          className="btn btn-outline"
          disabled={!!busy}
          onClick={() => onDownload(format)}
        >
          {busy === format ? "…" : label}
        </button>
      ))}
    </div>
  );
};

export default ExportButtons;
