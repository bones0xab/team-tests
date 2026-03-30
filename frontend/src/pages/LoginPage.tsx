
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, setToken } from "../api/client";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await api.login(username, password);
      setToken(data.access_token);
      const me = await api.getMe();


      // if (me.permissions.includes("manage:")) {
        if (me.permissions.includes("user:manage")) {
        navigate("/admin");
      } else if (me.permissions.includes("dashboard:view")) {
        navigate("/dashboard");
      } else {
        navigate("/");
      }
    } catch (err: any) {
      setError(err.message ?? "Login failed");
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

        <div className="auth-card">
          <div className="auth-logo-wrap">
            <img src="/logo.webp" alt="NTT DATA" className="auth-logo" loading="lazy" decoding="async" />
          </div>
          <div className="auth-divider-line" />

          <div className="auth-header">
            <div className="auth-eyebrow">AI Project Intelligence</div>
            <h1 className="auth-title">Welcome back</h1>
            <p className="auth-subtitle">Sign in to your account to continue</p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="auth-field">
              <label className="auth-label">Username</label>
              <input className="auth-input" type="text" placeholder="Enter your username"
                value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
            </div>
            <div className="auth-field">
              <label className="auth-label">Password</label>
              <input className="auth-input" type="password" placeholder="Enter your password"
                value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            </div>

            {error && (
              <div className="auth-error">
                <span className="auth-error-icon">⚠</span><span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading} className={`auth-btn${loading ? " auth-btn-loading" : ""}`}>
              {loading ? <><span className="auth-spinner" /> Signing in</> : "Sign In →"}
            </button>
          </form>

          <div className="auth-footer">
            Don't have an account?{" "}
            <Link to="/register" className="auth-link">Create one</Link>
          </div>
        </div>

        <div className="auth-bottom-note">
          © {new Date().getFullYear()} NTT Data · AI Project Intelligence Platform
        </div>
      </div>
    </>
  );
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
  width: 600px; height: 300px;
  background: radial-gradient(ellipse, rgba(0,114,188,0.1) 0%, transparent 70%);
  pointer-events: none;
}
.auth-card {
  position: relative;
  z-index: 1;
  width: 100%; max-width: 400px;
  background: var(--auth-card);
  border: 1px solid var(--auth-border);
  border-radius: 6px;
  padding: 2rem 2.25rem 1.75rem;
  box-shadow: var(--auth-shadow);
  animation: authFadeUp 0.4s ease both;
}
@keyframes authFadeUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}
.auth-logo-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 1.25rem;
}
.auth-logo {
  height: 30px; width: auto;
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
.auth-field { display: flex; flex-direction: column; gap: 0.3rem; }
.auth-label {
  font-size: 0.68rem; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--auth-muted);
}
.auth-input {
  background: var(--auth-input-bg);
  border: 1px solid var(--auth-border);
  border-radius: 3px;
  color: var(--auth-text);
  padding: 0.58rem 0.9rem;
  font-size: 0.9rem;
  font-family: 'Source Sans 3', sans-serif;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  width: 100%;
}
.auth-input::placeholder { color: var(--auth-muted); opacity: 0.7; }
.auth-input:focus {
  border-color: var(--auth-blue-l);
  box-shadow: 0 0 0 3px rgba(25,163,252,0.1);
}
.auth-error {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.6rem 0.9rem;
  border: 1px solid rgba(255,122,0,0.4);
  border-radius: 3px;
  background: rgba(255,122,0,0.06);
  color: #FF7A00; font-size: 0.83rem;
}
.auth-error-icon { flex-shrink: 0; }
.auth-btn {
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
  width: 100%;
  background: var(--auth-blue); border: none; border-radius: 3px;
  color: #fff;
  font-family: 'Source Sans 3', sans-serif;
  font-size: 0.83rem; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase;
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
  border-top-color: #fff;
  border-radius: 50%;
  animation: authSpin 0.7s linear infinite;
  display: inline-block; flex-shrink: 0;
}
@keyframes authSpin { to { transform: rotate(360deg); } }
.auth-footer {
  margin-top: 1.25rem; padding-top: 1rem;
  border-top: 1px solid var(--auth-border);
  text-align: center; font-size: 0.82rem; color: var(--auth-muted);
}
.auth-link { color: var(--auth-blue-l); text-decoration: none; font-weight: 600; transition: color 0.2s; }
.auth-link:hover { color: var(--auth-cyan); }
.auth-bottom-note {
  position: absolute;
  bottom: 1.25rem;
  font-size: 0.67rem; color: rgba(107,122,141,0.5);
  letter-spacing: 0.08em; text-align: center;
  z-index: 1;
}
`;