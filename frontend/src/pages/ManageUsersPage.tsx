import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { AdminRole, CurrentUser, ManagedUser } from "../api/client";
import { api } from "../api/client";

type UserFormState = {
  id: number | null;
  username: string;
  email: string;
  password: string;
  role_id: number | null;
  is_active: boolean;
};

interface Props {
  user: CurrentUser;
  onLogout: () => void;
}

const emptyForm: UserFormState = {
  id: null, username: "", email: "", password: "", role_id: null, is_active: true,
};

/* ─── tiny icon helpers ─────────────────────────────────── */
const Icon = ({ d, size = 14 }: { d: string; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);



const ManageUsersPage: React.FC<Props> = ({ user, onLogout }) => {
  const [users, setUsers]       = useState<ManagedUser[]>([]);
  const [roles, setRoles]       = useState<AdminRole[]>([]);
  const [form, setForm]         = useState<UserFormState>(emptyForm);
  const [loading, setLoading]   = useState(false);
  const [submitting, setSub]    = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [search, setSearch]     = useState("");

  const roleById = useMemo(
    () => new Map<number, AdminRole>(roles.map((r) => [r.id, r])),
    [roles]
  );

  const stats = useMemo(() => {
    const active = users.filter((u) => u.is_active).length;
    return { total: users.length, active, inactive: users.length - active };
  }, [users]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return q ? users.filter(u =>
      u.username.toLowerCase().includes(q) || (u.email ?? "").toLowerCase().includes(q)
    ) : users;
  }, [users, search]);

  const loadData = async () => {
    setLoading(true); setError(null);
    try {
      const [u, r] = await Promise.all([api.listUsers(), api.listRoles()]);
      setUsers(u); setRoles(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally { setLoading(false); }
  };

  useEffect(() => { void loadData(); }, []);

  const resetForm = () => setForm(emptyForm);

  const startEdit = (t: ManagedUser) => {
    setForm({ id: t.id, username: t.username, email: t.email ?? "", password: "",
      role_id: t.role_ids[0] ?? roles[0]?.id ?? null, is_active: t.is_active });
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setSub(true); setError(null);
    try {
      if (!form.role_id) throw new Error("Select a role");
      if (form.id) {
        await api.updateUser(form.id, { username: form.username, email: form.email || undefined,
          password: form.password || undefined, role_id: form.role_id, is_active: form.is_active });
      } else {
        if (!form.password.trim()) throw new Error("Password required");
        await api.createUser({ username: form.username, email: form.email || undefined,
          password: form.password, role_id: form.role_id, is_active: form.is_active });
      }
      await loadData(); resetForm();
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to save");
    } finally { setSub(false); }
  };

  const onDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete "${name}"?`)) return;
    try { await api.deleteUser(id); await loadData(); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to delete"); }
  };

  const onToggle = async (t: ManagedUser) => {
    try { await api.setUserStatus(t.id, !t.is_active); await loadData(); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to update"); }
  };

  const onRoleChange = async (id: number, roleId: number) => {
    try { await api.updateUser(id, { role_id: roleId }); await loadData(); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to change role"); }
  };

  const isEditing = !!form.id;
  const selectedRole = form.role_id ? roleById.get(form.role_id) : null;

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=DM+Mono:wght@400;500&family=Outfit:wght@300;400;500;600&display=swap');

        /* ── BASE — always applied ───────────────────────── */
        .mup-root {
          min-height: 100vh;
          background: var(--ink);
          font-family: 'Outfit', sans-serif;
          color: var(--text);
          display: flex;
          flex-direction: column;
        }

        /* ── LIGHT MODE — default ────────────────────────── */
        .mup-root {
          --ink:        #FFFFFF;
          --ink2:       #F4F6FA;
          --surface:    #FFFFFF;
          --surface2:   #E8EDF8;
          --rim:        rgba(0,0,0,0.1);
          --rim2:       rgba(0,0,0,0.05);
          --blue:       #0072BC;
          --blue-dim:   rgba(0,114,188,0.12);
          --blue-glow:  rgba(0,114,188,0.25);
          --blue-light: #19A3FC;
          --blue-dark:  #005B96;
          --cyan:       #007A85;
          --cyan-dim:   rgba(0,122,133,0.12);
          --green:      #00875A;
          --green-dim:  rgba(0,135,90,0.12);
          --red:        #CC3300;
          --red-dim:    rgba(204,51,0,0.1);
          --yellow:     #946200;
          --yellow-dim: rgba(148,98,0,0.1);
          --navy:       #070F26;
          --muted:      rgba(0,0,0,0.45);
          --muted2:     rgba(0,0,0,0.28);
          --text:       #070F26;
          --text2:      rgba(7,15,38,0.72);
          --shadow:     0 1px 3px rgba(0,0,0,0.1);
          --mono:       'DM Mono', monospace;
        }

        /* ── DARK MODE — via toggle ──────────────────────── */
        [data-theme="dark"] .mup-root {
          --ink:        #070F26;
          --ink2:       #0D1630;
          --surface:    #111E3A;
          --surface2:   #172448;
          --rim:        rgba(255,255,255,0.08);
          --rim2:       rgba(255,255,255,0.04);
          --blue:       #19A3FC;
          --blue-dim:   rgba(25,163,252,0.15);
          --blue-glow:  rgba(25,163,252,0.35);
          --blue-light: #19A3FC;
          --blue-dark:  #0072BC;
          --cyan:       #00DFED;
          --cyan-dim:   rgba(0,223,237,0.15);
          --green:      #00CB5D;
          --green-dim:  rgba(0,203,93,0.15);
          --red:        #FF5733;
          --red-dim:    rgba(255,87,51,0.14);
          --yellow:     #FFC400;
          --yellow-dim: rgba(255,196,0,0.14);
          --navy:       #070F26;
          --muted:      rgba(255,255,255,0.42);
          --muted2:     rgba(255,255,255,0.25);
          --text:       #FFFFFF;
          --text2:      rgba(255,255,255,0.68);
          --shadow:     0 1px 3px rgba(0,0,0,0.5);
        }

        /* ── NAV ─────────────────────────────────────────── */
        .mup-nav {
          height: 56px;
          background: var(--ink2);
          border-bottom: 1px solid var(--rim);
          box-shadow: 0 1px 4px rgba(7,15,38,0.10);
          display: flex;
          align-items: center;
          padding: 0 28px;
          gap: 0;
          position: sticky;
          top: 0;
          z-index: 100;
          flex-shrink: 0;
        }

        [data-theme="dark"] .mup-nav {
          background: #0D1630;
          border-bottom: 1px solid rgba(25,163,252,0.12);
          box-shadow: 0 1px 8px rgba(0,0,0,0.4);
        }

        .mup-nav-brand {
          display: flex;
          align-items: center;
          margin-right: 28px;
          flex-shrink: 0;
        }

        .mup-nav-logo {
          height: 56px;
          width: auto;
          display: block;
          object-fit: contain;
        }

        .mup-nav-sep {
          width: 1px; height: 20px;
          background: var(--rim);
          margin: 0 20px;
        }

        .mup-nav-crumb {
          font-size: 12px;
          font-weight: 500;
          color: var(--muted);
          letter-spacing: 0.04em;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .mup-nav-crumb span { color: var(--text2); }

        .mup-nav-right {
          margin-left: auto;
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .mup-nav-user {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 5px 12px 5px 6px;
          background: var(--surface);
          border: 1px solid var(--rim);
          border-radius: 20px;
        }

        .mup-nav-avatar {
          width: 24px; height: 24px;
          border-radius: 50%;
          background: linear-gradient(135deg, #0072BC, #00DFED);
          display: grid; place-items: center;
          font-family: 'Rajdhani', sans-serif;
          font-weight: 700;
          font-size: 11px;
          color: #fff;
          flex-shrink: 0;
        }

        .mup-nav-username {
          font-size: 12px;
          font-weight: 500;
          color: var(--text2);
          letter-spacing: 0.03em;
        }

        /* ── BUTTON SYSTEM ───────────────────────────────── */
        .xbtn {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 0 14px;
          height: 34px;
          border-radius: 8px;
          font-family: 'Outfit', sans-serif;
          font-size: 13px;
          font-weight: 500;
          letter-spacing: 0.01em;
          cursor: pointer;
          border: none;
          transition: all 0.15s ease;
          white-space: nowrap;
          text-decoration: none;
          flex-shrink: 0;
        }

        .xbtn:disabled { opacity: 0.45; cursor: not-allowed; }

        .xbtn-primary {
          background: var(--blue);
          color: #fff;
          box-shadow: 0 1px 2px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.12);
        }
        .xbtn-primary:hover:not(:disabled) {
          background: #19A3FC;
          box-shadow: 0 0 0 3px var(--blue-dim), 0 1px 2px rgba(0,0,0,0.3);
        }

        .xbtn-ghost {
          background: var(--surface2);
          color: var(--text2);
          border: 1px solid var(--rim);
        }
        .xbtn-ghost:hover:not(:disabled) {
          background: var(--surface);
          color: var(--text);
          border-color: rgba(255,255,255,0.15);
        }

        .xbtn-danger {
          background: var(--red-dim);
          color: var(--red);
          border: 1px solid rgba(240,82,82,0.25);
        }
        .xbtn-danger:hover:not(:disabled) {
          background: rgba(240,82,82,0.25);
          box-shadow: 0 0 0 3px rgba(240,82,82,0.12);
        }

        .xbtn-success {
          background: var(--green-dim);
          color: var(--green);
          border: 1px solid rgba(16,185,129,0.25);
        }
        .xbtn-success:hover:not(:disabled) {
          background: rgba(16,185,129,0.25);
        }

        .xbtn-icon {
          width: 32px; height: 32px;
          padding: 0;
          border-radius: 8px;
          display: grid; place-items: center;
        }

        .xbtn-nav-logout {
          height: 30px;
          padding: 0 12px;
          border-radius: 6px;
          font-size: 12px;
          background: transparent;
          color: var(--muted);
          border: 1px solid var(--rim);
        }
        .xbtn-nav-logout:hover { background: var(--red-dim); color: var(--red); border-color: rgba(240,82,82,0.3); }

        /* ── MAIN ────────────────────────────────────────── */
        .mup-main { flex: 1; padding: 28px 32px 48px; }

        /* ── TOOLBAR ─────────────────────────────────────── */
        .mup-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 24px;
          flex-wrap: wrap;
        }

        .mup-toolbar-left { display: flex; flex-direction: column; gap: 2px; }

        .mup-page-label {
          font-size: 11px;
          font-weight: 500;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: #005B96;
        }

        [data-theme="dark"] .mup-page-label { color: #19A3FC; }

        .mup-page-heading {
          font-family: 'Rajdhani', sans-serif;
          font-size: 26px;
          font-weight: 700;
          color: var(--text);
          letter-spacing: 0.02em;
          line-height: 1;
        }

        .mup-toolbar-right {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        /* ── STAT CARDS ──────────────────────────────────── */
        .mup-stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          margin-bottom: 24px;
        }

        .mup-stat {
          background: var(--surface);
          border: 1px solid var(--rim);
          border-radius: 12px;
          padding: 16px 20px;
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .mup-stat-icon {
          width: 38px; height: 38px;
          border-radius: 10px;
          display: grid; place-items: center;
          flex-shrink: 0;
        }

        .mup-stat-icon.blue   { background: var(--blue-dim); color: var(--blue); }
        .mup-stat-icon.green  { background: var(--green-dim); color: var(--green); }
        .mup-stat-icon.muted  { background: var(--rim2); color: var(--muted); }

        .mup-stat-num {
          font-family: 'Rajdhani', sans-serif;
          font-size: 28px;
          font-weight: 700;
          color: var(--text);
          line-height: 1;
        }

        .mup-stat-label {
          font-size: 11px;
          font-weight: 500;
          color: var(--muted);
          letter-spacing: 0.06em;
          text-transform: uppercase;
          margin-top: 2px;
        }

        /* ── ERROR ───────────────────────────────────────── */
        .mup-error {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 16px;
          background: var(--red-dim);
          border: 1px solid rgba(240,82,82,0.3);
          border-radius: 10px;
          color: var(--red);
          font-size: 13px;
          margin-bottom: 20px;
        }

        /* ── GRID ────────────────────────────────────────── */
        .mup-grid {
          display: grid;
          grid-template-columns: 340px 1fr;
          gap: 16px;
          align-items: start;
        }

        @media (max-width: 1100px) {
          .mup-grid { grid-template-columns: 1fr; }
          .mup-main { padding: 20px 16px 40px; }
          .mup-stats { grid-template-columns: repeat(3, 1fr); }
        }

        @media (max-width: 640px) {
          .mup-stats { grid-template-columns: 1fr; }
        }

        /* ── PANEL ───────────────────────────────────────── */
        .mup-panel {
          background: var(--surface);
          border: 1px solid var(--rim);
          border-radius: 14px;
          overflow: hidden;
          box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }

        .mup-panel-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 20px;
          border-bottom: 1px solid var(--rim);
        }

        .mup-panel-head-title {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--muted);
        }

        .mup-panel-head-dot {
          width: 7px; height: 7px;
          border-radius: 50%;
          background: #0072BC;
          box-shadow: 0 0 8px #0072BC;
        }

        .mup-panel-head-dot.editing {
          background: #FFC400;
          box-shadow: 0 0 8px #FFC400;
          animation: blink 1.4s ease-in-out infinite;
        }

        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }

        .mup-panel-body { padding: 20px; }

        /* ── FORM ────────────────────────────────────────── */
        .mup-form { display: flex; flex-direction: column; gap: 14px; }

        .mup-field { display: flex; flex-direction: column; gap: 6px; }

        .mup-field-label {
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--muted);
        }

        .mup-input {
          background: var(--ink2);
          border: 1px solid var(--rim);
          border-radius: 8px;
          color: var(--text);
          padding: 0 12px;
          height: 38px;
          font-size: 13.5px;
          font-family: 'Outfit', sans-serif;
          font-weight: 400;
          outline: none;
          width: 100%;
          transition: border-color 0.15s, box-shadow 0.15s;
          box-sizing: border-box;
          color-scheme: light;
        }

        [data-theme="dark"] .mup-input { color-scheme: dark; }

        .mup-input::placeholder { color: var(--muted2); }
        .mup-input:focus {
          border-color: var(--blue);
          box-shadow: 0 0 0 3px var(--blue-dim);
        }
        .mup-input option { background: var(--surface2); color: var(--text); }

        .mup-toggle-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: var(--ink2);
          border: 1px solid var(--rim);
          border-radius: 8px;
          padding: 10px 14px;
          cursor: pointer;
        }

        .mup-toggle-label {
          font-size: 13px;
          font-weight: 500;
          color: var(--text2);
        }

        .mup-switch {
          position: relative;
          width: 36px; height: 20px;
          flex-shrink: 0;
        }

        .mup-switch input { opacity: 0; width: 0; height: 0; }

        .mup-switch-track {
          position: absolute;
          inset: 0;
          background: var(--rim);
          border-radius: 20px;
          transition: background 0.2s;
          cursor: pointer;
        }

        .mup-switch-track::after {
          content: '';
          position: absolute;
          top: 3px; left: 3px;
          width: 14px; height: 14px;
          border-radius: 50%;
          background: var(--muted);
          transition: transform 0.2s, background 0.2s;
        }

        .mup-switch input:checked + .mup-switch-track {
          background: #00CB5D;
          box-shadow: 0 0 8px rgba(0,203,93,0.4);
        }

        .mup-switch input:checked + .mup-switch-track::after {
          transform: translateX(16px);
          background: #fff;
        }

        .mup-form-footer {
          display: flex;
          gap: 8px;
          padding-top: 4px;
        }

        /* ── PERMS ───────────────────────────────────────── */
        .mup-perms-block {
          background: var(--ink2);
          border: 1px solid var(--rim);
          border-radius: 8px;
          padding: 12px;
        }

        .mup-perms-title {
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--muted2);
          margin-bottom: 8px;
        }

        .mup-perms-wrap { display: flex; flex-wrap: wrap; gap: 5px; }

        .mup-perm-chip {
          font-family: var(--mono);
          font-size: 10px;
          padding: 3px 8px;
          background: var(--cyan-dim);
          color: #007A85;
          border-radius: 4px;
          letter-spacing: 0.04em;
        }

        [data-theme="dark"] .mup-perm-chip {
          background: rgba(0,223,237,0.12);
          color: #00DFED;
        }

        /* ── SEARCH ──────────────────────────────────────── */
        .mup-search-wrap {
          position: relative;
          flex: 1;
          max-width: 260px;
        }

        .mup-search-icon {
          position: absolute;
          left: 10px; top: 50%;
          transform: translateY(-50%);
          color: var(--muted);
          pointer-events: none;
        }

        .mup-search-input {
          width: 100%;
          background: var(--surface2);
          border: 1px solid var(--rim);
          border-radius: 8px;
          color: var(--text);
          padding: 0 12px 0 32px;
          height: 34px;
          font-size: 13px;
          font-family: 'Outfit', sans-serif;
          outline: none;
          transition: border-color 0.15s;
          box-sizing: border-box;
        }

        .mup-search-input::placeholder { color: var(--muted2); }
        .mup-search-input:focus { border-color: var(--blue); }

        /* ── TABLE ───────────────────────────────────────── */
        .mup-table-wrap { overflow-x: auto; }

        .mup-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13.5px;
        }

        .mup-table thead tr {
          border-bottom: 1px solid var(--rim);
        }

        .mup-table th {
          text-align: left;
          padding: 11px 16px;
          font-size: 10.5px;
          font-weight: 600;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--muted2);
          white-space: nowrap;
          background: var(--ink2);
        }

        .mup-table tbody tr {
          border-bottom: 1px solid var(--rim2);
          transition: background 0.12s;
        }

        .mup-table tbody tr:last-child { border-bottom: none; }
        .mup-table tbody tr:hover { background: var(--surface2); }

        .mup-table td {
          padding: 12px 16px;
          color: var(--text2);
          vertical-align: middle;
        }

        .mup-cell-user { display: flex; align-items: center; gap: 10px; }

        .mup-cell-avatar {
          width: 30px; height: 30px;
          border-radius: 8px;
          background: var(--blue-dim);
          border: 1px solid rgba(0,114,188,0.25);
          display: grid; place-items: center;
          font-family: 'Rajdhani', sans-serif;
          font-weight: 700;
          font-size: 12px;
          color: var(--blue);
          flex-shrink: 0;
        }

        .mup-cell-name { font-weight: 600; color: var(--text); font-size: 13.5px; }
        .mup-cell-email { font-size: 11.5px; color: var(--muted); font-family: var(--mono); }

        .mup-cell-id {
          font-family: var(--mono);
          font-size: 11px;
          color: var(--muted2);
          background: var(--rim2);
          padding: 2px 7px;
          border-radius: 4px;
        }

        .mup-role-select {
          background: var(--surface2);
          border: 1px solid var(--rim);
          border-radius: 6px;
          color: var(--text2);
          padding: 5px 8px;
          font-size: 12px;
          font-family: 'Outfit', sans-serif;
          font-weight: 500;
          outline: none;
          cursor: pointer;
          transition: border-color 0.15s;
          color-scheme: light;
        }

        [data-theme="dark"] .mup-role-select { color-scheme: dark; }

        .mup-role-select:focus { border-color: var(--blue); }
        .mup-role-select option { background: var(--surface2); color: var(--text); }

        .mup-badge {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 3px 9px;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.05em;
          white-space: nowrap;
        }

        .mup-badge-dot { width: 5px; height: 5px; border-radius: 50%; }

        .mup-badge-active { background: var(--green-dim); color: var(--green); }
        .mup-badge-active .mup-badge-dot { background: #00CB5D; box-shadow: 0 0 5px #00CB5D; }

        .mup-badge-inactive { background: var(--rim2); color: var(--muted); }
        .mup-badge-inactive .mup-badge-dot { background: var(--muted); }

        .mup-actions { display: flex; align-items: center; gap: 6px; }

        .mup-empty {
          padding: 48px 24px;
          text-align: center;
          color: var(--muted);
          font-size: 13px;
        }

        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      <div className="mup-root">

        {/* ── Nav ── */}
        <nav className="mup-nav">
          <div className="mup-nav-brand">
            <img src="/logo.webp" alt="NTT DATA" className="mup-nav-logo" />
          </div>

          <div className="mup-nav-sep" />

          <div className="mup-nav-crumb">
            <Link to="/admin" style={{ color: "inherit", textDecoration: "none" }}>Admin</Link>
            <Icon d="M9 18l6-6-6-6" size={10} />
            <span>Users</span>
          </div>

          <div className="mup-nav-right">
            <div className="mup-nav-user">
              <div className="mup-nav-avatar">{user.username.charAt(0).toUpperCase()}</div>
              <span className="mup-nav-username">{user.username}</span>
            </div>
            <button className="xbtn xbtn-nav-logout" onClick={onLogout}>
              <Icon d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" size={12} />
              Sign out
            </button>
          </div>
        </nav>

        {/* ── Main ── */}
        <div className="mup-main">

          {/* Toolbar */}
          <div className="mup-toolbar">
            <div className="mup-toolbar-left">
              <div className="mup-page-label">Administration</div>
              <div className="mup-page-heading">User Management</div>
            </div>
            <div className="mup-toolbar-right">
              <Link className="xbtn xbtn-ghost" to="/admin">
                <Icon d="M19 12H5M12 5l-7 7 7 7" />
                Back
              </Link>
              <Link className="xbtn xbtn-ghost" to="/dashboard">
                <Icon d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                Dashboard
              </Link>
            </div>
          </div>

          {/* Stats */}
          <div className="mup-stats">
            {[
              { label: "Total Users", value: stats.total, cls: "blue",
                icon: "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 7a4 4 0 100 8 4 4 0 000-8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" },
              { label: "Active", value: stats.active, cls: "green",
                icon: "M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3" },
              { label: "Inactive", value: stats.inactive, cls: "muted",
                icon: "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 7a4 4 0 100 8 4 4 0 000-8zM18 8l4 4m0-4l-4 4" },
            ].map(s => (
              <div className="mup-stat" key={s.label}>
                <div className={`mup-stat-icon ${s.cls}`}>
                  <Icon d={s.icon} size={17} />
                </div>
                <div>
                  <div className="mup-stat-num">{s.value}</div>
                  <div className="mup-stat-label">{s.label}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Error */}
          {error && (
            <div className="mup-error">
              <Icon d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01" size={15} />
              {error}
            </div>
          )}

          {/* Grid */}
          <div className="mup-grid">

            {/* ── Form Panel ── */}
            <div className="mup-panel">
              <div className="mup-panel-head">
                <div className="mup-panel-head-title">
                  <span className={`mup-panel-head-dot ${isEditing ? "editing" : ""}`} />
                  {isEditing ? "Edit User" : "New User"}
                </div>
                {isEditing && (
                  <button className="xbtn xbtn-ghost xbtn-icon" onClick={resetForm} title="Cancel edit">
                    <Icon d="M18 6L6 18M6 6l12 12" size={13} />
                  </button>
                )}
              </div>

              <div className="mup-panel-body">
                <form onSubmit={submit} className="mup-form">
                  <div className="mup-field">
                    <label className="mup-field-label">Username</label>
                    <input className="mup-input" value={form.username} placeholder="e.g. john.doe" required
                      onChange={e => setForm(s => ({ ...s, username: e.target.value }))} />
                  </div>

                  <div className="mup-field">
                    <label className="mup-field-label">Email</label>
                    <input className="mup-input" type="email" value={form.email} placeholder="john@example.com"
                      onChange={e => setForm(s => ({ ...s, email: e.target.value }))} />
                  </div>

                  <div className="mup-field">
                    <label className="mup-field-label">
                      Password
                      {isEditing && (
                        <span style={{ fontWeight: 400, textTransform: "none", letterSpacing: 0, marginLeft: 4, color: "var(--muted2)", fontSize: 10 }}>
                          leave blank to keep
                        </span>
                      )}
                    </label>
                    <input className="mup-input" type="password" value={form.password}
                      placeholder={isEditing ? "Unchanged" : "Set a strong password"}
                      required={!isEditing}
                      onChange={e => setForm(s => ({ ...s, password: e.target.value }))} />
                  </div>

                  <div className="mup-field">
                    <label className="mup-field-label">Role</label>
                    <select className="mup-input" value={form.role_id ?? ""} required
                      onChange={e => setForm(s => ({ ...s, role_id: Number(e.target.value) || null }))}>
                      <option value="">Select a role...</option>
                      {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                    </select>
                  </div>

                  <label className="mup-toggle-row"
                    onClick={() => setForm(s => ({ ...s, is_active: !s.is_active }))}>
                    <span className="mup-toggle-label">Active account</span>
                    <label className="mup-switch" onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={form.is_active}
                        onChange={e => setForm(s => ({ ...s, is_active: e.target.checked }))} />
                      <span className="mup-switch-track" />
                    </label>
                  </label>

                  <div className="mup-form-footer">
                    <button className="xbtn xbtn-primary" type="submit" disabled={submitting} style={{ flex: 1 }}>
                      {submitting ? (
                        <>
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth="2.5"
                            style={{ animation: "spin 0.7s linear infinite" }}>
                            <path d="M21 12a9 9 0 11-6.22-8.56" />
                          </svg>
                          Saving...
                        </>
                      ) : (
                        <>
                          <Icon d={isEditing ? "M20 6L9 17l-5-5" : "M12 5v14M5 12h14"} />
                          {isEditing ? "Save Changes" : "Create User"}
                        </>
                      )}
                    </button>
                    <button className="xbtn xbtn-ghost" type="button" onClick={resetForm}>
                      Clear
                    </button>
                  </div>

                  {selectedRole && (
                    <div className="mup-perms-block">
                      <div className="mup-perms-title">Role permissions</div>
                      <div className="mup-perms-wrap">
                        {selectedRole.permissions.map(p => (
                          <span className="mup-perm-chip" key={p}>{p}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </form>
              </div>
            </div>

            {/* ── Table Panel ── */}
            <div className="mup-panel">
              <div className="mup-panel-head">
                <div className="mup-panel-head-title">
                  <span className="mup-panel-head-dot" />
                  All Users
                </div>
                <div className="mup-search-wrap">
                  <span className="mup-search-icon">
                    <Icon d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" size={13} />
                  </span>
                  <input className="mup-search-input" placeholder="Search users..."
                    value={search} onChange={e => setSearch(e.target.value)} />
                </div>
              </div>

              {loading ? (
                <div className="mup-empty">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" strokeWidth="2"
                    style={{ animation: "spin 0.7s linear infinite", display: "inline-block" }}>
                    <path d="M21 12a9 9 0 11-6.22-8.56" />
                  </svg>
                  <div style={{ marginTop: 8 }}>Loading users...</div>
                </div>
              ) : (
                <div className="mup-table-wrap">
                  <table className="mup-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>User</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Permissions</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map(t => (
                        <tr key={t.id}>
                          <td><span className="mup-cell-id">#{t.id}</span></td>
                          <td>
                            <div className="mup-cell-user">
                              <div className="mup-cell-avatar">
                                {t.username.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <div className="mup-cell-name">{t.username}</div>
                                {t.email && <div className="mup-cell-email">{t.email}</div>}
                              </div>
                            </div>
                          </td>
                          <td>
                            <select className="mup-role-select"
                              value={t.role_ids[0] ?? ""}
                              onChange={e => onRoleChange(t.id, Number(e.target.value))}>
                              {roles.map(r => (
                                <option key={r.id} value={r.id}>{r.name}</option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <span className={`mup-badge ${t.is_active ? "mup-badge-active" : "mup-badge-inactive"}`}>
                              <span className="mup-badge-dot" />
                              {t.is_active ? "Active" : "Inactive"}
                            </span>
                          </td>
                          <td>
                            <div className="mup-perms-wrap">
                              {t.permissions.map(p => (
                                <span className="mup-perm-chip" key={p}>{p}</span>
                              ))}
                            </div>
                          </td>
                          <td>
                            <div className="mup-actions">
                              <button className="xbtn xbtn-ghost xbtn-icon" title="Edit user"
                                onClick={() => startEdit(t)}>
                                <Icon d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" size={13} />
                              </button>
                              <button
                                className={`xbtn xbtn-icon ${t.is_active ? "xbtn-ghost" : "xbtn-success"}`}
                                title={t.is_active ? "Deactivate" : "Activate"}
                                onClick={() => onToggle(t)}>
                                <Icon d={t.is_active
                                  ? "M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636"
                                  : "M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3"}
                                  size={13} />
                              </button>
                              <button className="xbtn xbtn-danger xbtn-icon" title="Delete user"
                                onClick={() => onDelete(t.id, t.username)}>
                                <Icon d="M3 6h18M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6M10 11v6M14 11v6M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" size={13} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {filtered.length === 0 && (
                        <tr>
                          <td colSpan={6}>
                            <div className="mup-empty">
                              {search ? `No users matching "${search}"` : "No users found"}
                            </div>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

          </div>
        </div>
      </div>
    </>
  );
};

export default ManageUsersPage;