import React, { useEffect } from "react";

export type ToastState =
  | { status: "success"; message: string }
  | { status: "error"; message: string }
  | null;

interface Props {
  toast: ToastState;
  onDismiss: () => void;
}

const ToastNotification: React.FC<Props> = ({ toast, onDismiss }) => {
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(onDismiss, 4000);
    return () => clearTimeout(id);
  }, [toast, onDismiss]);

  if (!toast) return null;

  const isSuccess = toast.status === "success";

  return (
    <div className={`toast-notification toast-${toast.status}`} role="alert">
      <span className="toast-icon">{isSuccess ? "✔" : "✖"}</span>
      <span className="toast-message">{toast.message}</span>
      <button className="toast-close" onClick={onDismiss} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
};

export default ToastNotification;
