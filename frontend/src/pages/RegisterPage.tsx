// src/pages/RegisterPage.tsx

import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api/client";

export default function Register() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (password.length < 6)  { setError("Password must be at least 6 characters."); return; }
    setLoading(true);
    try {
      await api.register(username, email, password);
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2200);
    } catch (err: any) {
      setError(err.message ?? "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{CSS}</style>
      <div className="auth-wrapper">
        <div className="auth-grid-bg" />
        <div className="auth-top-accent" />
        <div className="auth-glow" />

        <div className="auth-card auth-card-wide">
          <div className="auth-logo-wrap">
            <img src="/logo.webp" alt="NTT Data" className="auth-logo" />
          </div>
          <div className="auth-divider-line" />

          <div className="auth-header">
            <div className="auth-eyebrow">AI Project Intelligence</div>
            <h1 className="auth-title">Create Account</h1>
            <p className="auth-subtitle">Join the platform to monitor your projects</p>
          </div>

          {success ? (
            <div className="auth-success">
              <div className="auth-success-icon">✓</div>
              <div>
                <div className="auth-success-title">Account created!</div>
                <div className="auth-success-sub">Redirecting to login…</div>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="auth-row">
                <div className="auth-field">
                  <label className="auth-label">Username</label>
                  <input className="auth-input" type="text" placeholder="e.g. imane"
                    value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
                </div>
                <div className="auth-field">
                  <label className="auth-label">Email</label>
                  <input className="auth-input" type="email" placeholder="you@company.com"
                    value={email} onChange={(e) => setEmail(e.target.value)} required />
                </div>
              </div>

              <div className="auth-field">
                <label className="auth-label">Password</label>
                <input className="auth-input" type="password" placeholder="Minimum 6 characters"
                  value={password} onChange={(e) => setPassword(e.target.value)} required />
                {password.length > 0 && (
                  <div className="auth-strength-wrap">
                    {[1,2,3,4].map(i => (
                      <div key={i} className="auth-strength-bar"
                        style={{ background: strengthColor(password, i) }} />
                    ))}
                    <span className="auth-strength-label" style={{ color: strengthColor(password, 0) }}>
                      {strengthText(password)}
                    </span>
                  </div>
                )}
              </div>

              <div className="auth-field">
                <label className="auth-label">Confirm Password</label>
                <input
                  className="auth-input"
                  type="password"
                  placeholder="Repeat your password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  style={{
                    borderColor: confirm.length > 0
                      ? confirm === password ? "rgba(0,203,93,0.6)" : "rgba(255,122,0,0.6)"
                      : undefined
                  }}
                />
              </div>

              {error && (
                <div className="auth-error">
                  <span className="auth-error-icon">⚠</span><span>{error}</span>
                </div>
              )}

              <button type="submit" disabled={loading} className={`auth-btn${loading ? " auth-btn-loading" : ""}`}>
                {loading ? <><span className="auth-spinner" /> Creating account…</> : "Create Account →"}
              </button>
            </form>
          )}

          <div className="auth-footer">
            Already have an account?{" "}
            <Link to="/login" className="auth-link">Sign in</Link>
          </div>
        </div>

        <div className="auth-bottom-note">
          © {new Date().getFullYear()} NTT Data · AI Project Intelligence Platform
        </div>
      </div>
    </>
  );
}

function strengthScore(pw: string): number {
  let s = 0;
  if (pw.length >= 6) s++;
  if (pw.length >= 10) s++;
  if (/[A-Z]/.test(pw) || /[0-9]/.test(pw)) s++;
  if (/[^a-zA-Z0-9]/.test(pw)) s++;
  return s;
}
function strengthColor(pw: string, bar: number): string {
  const s = strengthScore(pw);
  const colors = ["#FF7A00","#FF7A00","#FFC400","#19A3FC","#00CB5D"];
  if (bar === 0) return colors[s] ?? "#FF7A00";
  return bar <= s ? (colors[s] ?? "#FF7A00") : "rgba(107,122,141,0.2)";
}
function strengthText(pw: string): string {
  return ["","Weak","Fair","Good","Strong"][strengthScore(pw)] || "Weak";
}

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Source+Sans+3:wght@300;400;600&display=swap');

:root {
  --auth-bg:       #070F26;
  --auth-card:     rgba(10,21,48,0.97);
  --auth-border:   rgba(0,114,188,0.3);
  --auth-blue:     #0072BC;
  --auth-blue-l:   #19A3FC;
  --auth-cyan:     #00DFED;
  --auth-text:     #E8E8E8;
  --auth-muted:    rgba(232,232,232,0.45);
  --auth-input-bg: rgba(0,114,188,0.08);
  --auth-shadow:   0 24px 60px rgba(0,0,0,0.55);
  --auth-logo-filter: brightness(0) invert(1);
}
@media (prefers-color-scheme: light) {
  :root {
    --auth-bg:       #F4F6FA;
    --auth-card:     #FFFFFF;
    --auth-border:   rgba(0,114,188,0.2);
    --auth-text:     #070F26;
    --auth-muted:    #6B7A8D;
    --auth-input-bg: rgba(0,114,188,0.05);
    --auth-shadow:   0 12px 40px rgba(7,15,38,0.1);
    --auth-logo-filter: brightness(0) saturate(100%) invert(27%) sepia(90%) saturate(700%) hue-rotate(185deg) brightness(95%);
  }
}

*, *::before, *::after { box-sizing: border-box; }

.auth-wrapper {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--auth-bg);
  font-family: 'Source Sans 3', sans-serif;
  position: relative;
}
.auth-grid-bg {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(0,114,188,0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,114,188,0.07) 1px, transparent 1px);
  background-size: 44px 44px;
  pointer-events: none;
}
@media (prefers-color-scheme: light) {
  .auth-grid-bg {
    background-image:
      linear-gradient(rgba(0,114,188,0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,114,188,0.05) 1px, transparent 1px);
  }
}
.auth-top-accent {
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #0072BC 0%, #00DFED 55%, transparent 100%);
}
.auth-glow {
  position: absolute; top: -120px; left: 50%; transform: translateX(-50%);
  width: 700px; height: 320px;
  background: radial-gradient(ellipse, rgba(0,114,188,0.1) 0%, transparent 70%);
  pointer-events: none;
}
.auth-card {
  position: relative;
  z-index: 1;
  width: 100%; max-width: 420px;
  background: var(--auth-card);
  border: 1px solid var(--auth-border);
  border-radius: 6px;
  padding: 2rem 2.25rem 1.75rem;
  box-shadow: var(--auth-shadow);
  animation: authFadeUp 0.4s ease both;
}
.auth-card-wide { max-width: 500px; }

@keyframes authFadeUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}
.auth-logo-wrap {
  display: flex; justify-content: center;
  margin-bottom: 1.25rem;
}
.auth-logo {
  height: 36px; width: auto;
  filter: var(--auth-logo-filter);
}
.auth-divider-line {
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--auth-blue) 30%, var(--auth-cyan) 65%, transparent 100%);
  opacity: 0.45;
  margin-bottom: 1.4rem;
}
.auth-header { text-align: center; margin-bottom: 1.4rem; }
.auth-eyebrow {
  font-family: 'Rajdhani', sans-serif;
  font-size: 0.65rem; font-weight: 600;
  letter-spacing: 0.25em; text-transform: uppercase;
  color: var(--auth-blue); margin-bottom: 0.3rem;
}
.auth-title {
  font-family: 'Rajdhani', sans-serif;
  font-size: 1.9rem; font-weight: 700;
  color: var(--auth-text); margin: 0 0 0.25rem;
  letter-spacing: -0.01em; line-height: 1.1;
}
.auth-subtitle { font-size: 0.83rem; color: var(--auth-muted); margin: 0; }

.auth-form { display: flex; flex-direction: column; gap: 0.85rem; }
.auth-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.9rem; }
@media (max-width: 480px) { .auth-row { grid-template-columns: 1fr; } }

.auth-field { display: flex; flex-direction: column; gap: 0.3rem; }
.auth-label {
  font-size: 0.68rem; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--auth-muted);
}
.auth-input {
  background: var(--auth-input-bg);
  border: 1px solid var(--auth-border);
  border-radius: 3px; color: var(--auth-text);
  padding: 0.58rem 0.9rem;
  font-size: 0.9rem; font-family: 'Source Sans 3', sans-serif;
  outline: none; width: 100%;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.auth-input::placeholder { color: var(--auth-muted); opacity: 0.7; }
.auth-input:focus {
  border-color: var(--auth-blue-l);
  box-shadow: 0 0 0 3px rgba(25,163,252,0.1);
}

.auth-strength-wrap {
  display: flex; align-items: center; gap: 4px; margin-top: 0.35rem;
}
.auth-strength-bar {
  height: 3px; flex: 1; border-radius: 2px;
  transition: background 0.3s;
}
.auth-strength-label {
  font-size: 0.63rem; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  margin-left: 0.5rem; min-width: 36px;
  transition: color 0.3s;
}

.auth-error {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.6rem 0.9rem;
  border: 1px solid rgba(255,122,0,0.4); border-radius: 3px;
  background: rgba(255,122,0,0.06);
  color: #FF7A00; font-size: 0.83rem;
}
.auth-error-icon { flex-shrink: 0; }

.auth-btn {
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
  width: 100%; background: var(--auth-blue); border: none; border-radius: 3px;
  color: #fff; font-family: 'Source Sans 3', sans-serif;
  font-size: 0.83rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
  padding: 0.72rem; cursor: pointer; margin-top: 0.15rem;
  transition: background 0.2s, transform 0.1s;
}
.auth-btn:hover:not(:disabled) { background: var(--auth-blue-l); transform: translateY(-1px); }
.auth-btn:active:not(:disabled) { transform: translateY(0); }
.auth-btn-loading, .auth-btn:disabled {
  background: rgba(0,114,188,0.4); cursor: not-allowed;
  color: rgba(255,255,255,0.5); transform: none;
}
.auth-spinner {
  width: 13px; height: 13px;
  border: 2px solid rgba(255,255,255,0.25);
  border-top-color: #fff; border-radius: 50%;
  animation: authSpin 0.7s linear infinite;
  display: inline-block; flex-shrink: 0;
}
@keyframes authSpin { to { transform: rotate(360deg); } }

.auth-success {
  display: flex; align-items: center; gap: 1rem;
  padding: 1.1rem;
  border: 1px solid rgba(0,203,93,0.4); border-radius: 4px;
  background: rgba(0,203,93,0.06); margin-bottom: 0.5rem;
}
.auth-success-icon {
  width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
  background: rgba(0,203,93,0.15); border: 1px solid rgba(0,203,93,0.4);
  color: #00CB5D; display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; font-weight: 700;
}
.auth-success-title {
  font-family: 'Rajdhani', sans-serif;
  font-size: 1.05rem; font-weight: 700; color: #00CB5D; letter-spacing: 0.05em;
}
.auth-success-sub { font-size: 0.8rem; color: var(--auth-muted); margin-top: 0.2rem; }

.auth-footer {
  margin-top: 1.25rem; padding-top: 1rem;
  border-top: 1px solid var(--auth-border);
  text-align: center; font-size: 0.82rem; color: var(--auth-muted);
}
.auth-link {
  color: var(--auth-blue-l); text-decoration: none;
  font-weight: 600; transition: color 0.2s;
}
.auth-link:hover { color: var(--auth-cyan); }

.auth-bottom-note {
  position: absolute;
  bottom: 1.25rem;
  font-size: 0.67rem; color: rgba(107,122,141,0.5);
  letter-spacing: 0.08em; text-align: center;
  z-index: 1;
}
`;