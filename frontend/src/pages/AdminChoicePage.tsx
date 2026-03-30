import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { CurrentUser } from "../api/client";

interface Props {
  user: CurrentUser;
  onLogout: () => void;
}

interface Module {
  to: string;
  icon: React.ReactNode;
  accent: string;
  accentRgb: string;
  title: string;
  sub: string;
  tag: string;
  stat: string;
  statLabel: string;
}

const AdminChoicePage: React.FC<Props> = ({ user, onLogout }) => {
  const canViewDashboard = user.permissions.includes("dashboard:view");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 60);
    return () => clearTimeout(t);
  }, []);

  const modules: Module[] = [
    canViewDashboard && {
      to: "/dashboard",
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1.5"/>
          <rect x="14" y="3" width="7" height="7" rx="1.5"/>
          <rect x="3" y="14" width="7" height="7" rx="1.5"/>
          <rect x="14" y="14" width="7" height="7" rx="1.5"/>
        </svg>
      ),
      accent: "#0072BC",
      accentRgb: "0,114,188",
      title: "Analytics Dashboard",
      sub: "Real-time project health metrics, KPI tracking, issue velocity and team performance insights across all active workstreams.",
      tag: "Analytics",
      stat: "Live",
      statLabel: "Data stream",
    },
    {
      to: "/manage-users",
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
        </svg>
      ),
      accent: "#00DFED",
      accentRgb: "0,223,237",
      title: "User Management",
      sub: "Provision accounts, configure role-based access controls, manage activation states and audit permission assignments.",
      tag: "Administration",
      stat: "RBAC",
      statLabel: "Access control",
    },
canViewDashboard && {
  to: "/ai",
  icon: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a6 6 0 016 6v3a4 4 0 01-4 4h-1v3h-2v-3h-1a4 4 0 01-4-4V8a6 6 0 016-6z"/>
      <circle cx="9" cy="10" r="1"/>
      <circle cx="15" cy="10" r="1"/>
      <path d="M9 14h6"/>
    </svg>
  ),
  accent: "#7C3AED",
  accentRgb: "124,58,237",
  title: "AI Intelligence",
  sub: "Generate automated project risk analysis, predictive health insights and strategic recommendations powered by AI.",
  tag: "AI",
  stat: "Smart",
  statLabel: "Insights",
},
canViewDashboard && {
  to: "/jira-explorer",
  icon: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/>
      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  ),
  accent: "#FFC400",
  accentRgb: "255,196,0",
  title: "Jira Explorer",
  sub: "Query, filter, and analyze Jira issues natively using dynamic JQL, multi-select criteria, and fast table views.",
  tag: "Integration",
  stat: "Live",
  statLabel: "Data",
},
canViewDashboard && {
  to: "/team-scorecard",
  icon: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
    </svg>
  ),
  accent: "#00CB5D",
  accentRgb: "0,203,93",
  title: "Team Scorecard",
  sub: "Individual developer metrics, AI performance scores and velocity trends per sprint.",
  tag: "TEAM",
  stat: "PERFORMANCE",
  statLabel: "INSIGHTS",
}
  ].filter(Boolean) as Module[];

  // const now = new Date();
  // const timeStr = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=DM+Mono:wght@400;500&family=Outfit:wght@300;400;500;600&display=swap');

        /* ── TOKENS ─────────────────────────────────────── */
        .acp-root {
          /* Brand */
          --navy:         #070F26;
          --navy-mid:     #0D1630;
          --navy-light:   #111E3A;
          --navy-rim:     #172448;
          --future-blue:  #0072BC;
          --future-50:    #19A3FC;
          --future-150:   #005B96;
          --turquoise:    #00DFED;
          --green:        #00CB5D;
          --yellow:       #FFC400;
          --orange:       #FF7A00;
          --red:          #E42600;
          --grey-50:      #E8E8E8;
          --text-grey:    #2E404D;
          --white:        #FFFFFF;

          /* Semantic */
          --bg:           var(--navy);
          --surface:      var(--navy-mid);
          --surface2:     var(--navy-light);
          --border:       rgba(0,114,188,0.18);
          --border2:      rgba(255,255,255,0.06);
          --text:         var(--white);
          --text2:        rgba(255,255,255,0.60);
          --text3:        rgba(255,255,255,0.35);
          --mono:         'DM Mono', monospace;

          min-height: 100vh;
          overflow: hidden;
          background: var(--bg);
          font-family: 'Outfit', sans-serif;
          color: var(--text);
          display: flex;
          flex-direction: column;
          overflow-x: hidden;
        }

        /* ── LIGHT MODE ─────────────────────────────────── */
        [data-theme="light"] .acp-root {
          --bg:       #F0F4F8;
          --surface:  #FFFFFF;
          --surface2: #EEF2F8;
          --border:   rgba(0,114,188,0.14);
          --border2:  rgba(7,15,38,0.06);
          --text:     #070F26;
          --text2:    rgba(7,15,38,0.55);
          --text3:    rgba(7,15,38,0.30);
        }
        [data-theme="light"] .acp-bg-grid { opacity: 0.04 !important; }
        [data-theme="light"] .acp-nav { background: #FFFFFF !important; border-bottom-color: rgba(0,114,188,0.15) !important; }
        [data-theme="light"] .acp-hero-bg { opacity: 0.03 !important; }
        [data-theme="light"] .acp-card { background: #FFFFFF !important; border-color: rgba(7,15,38,0.08) !important; }
        [data-theme="light"] .acp-statusbar { background: rgba(240,244,248,0.8) !important; border-color: rgba(7,15,38,0.08) !important; }
        [data-theme="light"] .acp-nav-title { color: #070F26; }
        [data-theme="light"] .acp-nav-eyebrow { color: #0072BC; }
        [data-theme="light"] .acp-logout-btn { color: rgba(7,15,38,0.42); border-color: rgba(7,15,38,0.08); }
        [data-theme="light"] .acp-logout-btn:hover { background: rgba(228,38,0,0.09); color: #E42600; border-color: rgba(228,38,0,0.3); }
        
      
        /* ── BACKGROUND GRID ────────────────────────────── */
        .acp-bg-grid {
          position: fixed;
          inset: 0;
          pointer-events: none;
          z-index: 0;
          opacity: 0.07;
          background-image:
            linear-gradient(rgba(0,114,188,0.6) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,114,188,0.6) 1px, transparent 1px);
          background-size: 48px 48px;
        }

        /* ── NAV ─────────────────────────────────────────── */
        .acp-nav {
          position: sticky;
          top: 0;
          z-index: 100;
          height: 64px;
          background: rgba(7,15,38,0.92);
          backdrop-filter: blur(14px);
          -webkit-backdrop-filter: blur(14px);
          border-bottom: 1px solid rgba(0,114,188,0.25);
          display: flex;
          align-items: center;
          padding: 0 2.5rem;
          gap: 0;
          flex-shrink: 0;
        }

        /* Blue top accent line */
        .acp-nav::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 2px;
          background: linear-gradient(90deg, #0072BC 0%, #00DFED 50%, #0072BC 100%);
        }

        .acp-nav-brand {
          display: flex;
          align-items: center;
          gap: 0;
          flex-shrink: 0;
          margin-right: 2rem;
        }

        .acp-nav-logo {
          height: 52px;
          width: auto;
          display: block;
          object-fit: contain;
        }

        .acp-nav-sep {
          width: 1px;
          height: 22px;
          background: rgba(0,114,188,0.4);
          margin: 0 1.5rem;
        }

        .acp-nav-context {
          display: flex;
          flex-direction: column;
          gap: 1px;
        }

        .acp-nav-eyebrow {
          font-family: var(--mono);
          font-size: 0.6rem;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: var(--turquoise);
          opacity: 0.8;
        }

        .acp-nav-title {
          font-family: 'Rajdhani', sans-serif;
          font-size: 1rem;
          font-weight: 700;
          color: var(--white);
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }


        .acp-nav-right {
          margin-left: auto;
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        /* Clock */
        .acp-nav-clock {
          font-family: var(--mono);
          font-size: 0.72rem;
          color: var(--text3);
          letter-spacing: 0.06em;
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          line-height: 1.3;
        }

        .acp-nav-clock-time {
          color: var(--text2);
          font-size: 0.78rem;
        }

        /* User pill */
        .acp-user-pill {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.3rem 0.7rem 0.3rem 0.4rem;
          border: 1px solid rgba(0,114,188,0.35);
          background: rgba(0,114,188,0.08);
          border-radius: 2rem;
        }

        .acp-user-avatar {
          width: 26px; height: 26px;
          border-radius: 50%;
          background: linear-gradient(135deg, #0072BC, #00DFED);
          display: grid; place-items: center;
          font-family: 'Rajdhani', sans-serif;
          font-weight: 700;
          font-size: 11px;
          color: #fff;
          flex-shrink: 0;
        }

        .acp-user-name {
          font-size: 0.75rem;
          font-weight: 500;
          color: var(--text2);
          letter-spacing: 0.04em;
        }

        .acp-user-dot {
          width: 6px; height: 6px;
          border-radius: 50%;
          background: var(--green);
          box-shadow: 0 0 7px var(--green);
          margin-left: 2px;
        }

        /* Logout btn */
        .acp-logout-btn {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 0 12px;
          height: 30px;
          border-radius: 6px;
          font-family: 'Outfit', sans-serif;
          font-size: 12px;
          font-weight: 500;
          letter-spacing: 0.01em;
          cursor: pointer;
          background: transparent;
          color: rgba(255,255,255,0.42);
          border: 1px solid rgba(255,255,255,0.08);
          transition: all 0.15s ease;
        }

        .acp-logout-btn:hover {
          background: rgba(228,38,0,0.09);
          color: #E42600;
          border-color: rgba(228,38,0,0.3);
        }


        /* ── HERO ─────────────────────────────────────────── */
        .acp-hero {
          position: relative;
          padding: 2rem 2.5rem 1.5rem;
          z-index: 1;
          overflow: hidden;
          flex-shrink: 0;
        }

        .acp-hero-bg {
          position: absolute;
          inset: 0;
          pointer-events: none;
          opacity: 0.06;
          background:
            radial-gradient(ellipse 60% 80% at 80% 50%, #0072BC 0%, transparent 70%),
            radial-gradient(ellipse 40% 60% at 20% 80%, #00DFED 0%, transparent 70%);
        }

        .acp-hero-inner {
          max-width: 860px;
          margin: 0 auto;
          position: relative;
        }

        .acp-hero-tag {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          font-family: var(--mono);
          font-size: 0.65rem;
          letter-spacing: 0.2em;
          text-transform: uppercase;
          color: var(--turquoise);
          margin-bottom: 1rem;
          opacity: 0;
          transform: translateY(8px);
          transition: opacity 0.5s ease, transform 0.5s ease;
        }

        .acp-hero-tag.visible { opacity: 1; transform: translateY(0); }

        .acp-hero-tag-line {
          width: 24px; height: 1px;
          background: var(--turquoise);
          opacity: 0.6;
        }

        .acp-hero-heading {
          font-family: 'Rajdhani', sans-serif;
          font-size: clamp(1.8rem, 4vw, 2.6rem);
          font-weight: 700;
          line-height: 1.05;
          letter-spacing: -0.01em;
          color: var(--text);
          margin-bottom: 0.5rem;
          opacity: 0;
          transform: translateY(12px);
          transition: opacity 0.5s ease 0.1s, transform 0.5s ease 0.1s;
        }

        .acp-hero-heading.visible { opacity: 1; transform: translateY(0); }

        .acp-hero-heading em {
          font-style: normal;
          color: var(--future-blue);
        }


        .acp-hero-sub {
          font-size: 0.95rem;
          color: var(--text2);
          max-width: 520px;
          line-height: 1.65;
          opacity: 0;
          transform: translateY(8px);
          transition: opacity 0.5s ease 0.2s, transform 0.5s ease 0.2s;
        }

        .acp-hero-sub.visible { opacity: 1; transform: translateY(0); }

        /* ── DIVIDER ─────────────────────────────────────── */
        .acp-divider {
          height: 1px;
          background: linear-gradient(90deg, #0072BC 0%, #00DFED 35%, transparent 80%);
          opacity: 0.35;
          max-width: 860px;
          margin: 0 auto 1.25rem;
          position: relative;
          z-index: 1;
        }

        /* ── MAIN ─────────────────────────────────────────── */
        .acp-main {
         
          padding: 0 2.5rem 0;
          position: relative;
          z-index: 1;
          display: flex;
          flex-direction: column;
        }

        .acp-main-inner {
          max-width: 860px;
          margin: 0 auto;
          width: 100%;
          display: flex;
          flex-direction: column;
            }

        /* ── MODULE GRID ─────────────────────────────────── */
        .acp-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 1.25rem;
          margin-bottom: 1rem;
        }


        /* ── CARD ─────────────────────────────────────────── */
        .acp-card {
          text-decoration: none;
          background: rgba(13,22,48,0.7);
          border: 1px solid var(--border2);
          border-radius: 6px;
          padding: 1.4rem 1.6rem;
          display: flex;
          flex-direction: column;
          position: relative;
          overflow: hidden;
          cursor: pointer;
          opacity: 0;
          height: auto;
          transform: translateY(16px);
          transition:
            opacity 0.5s ease,
            transform 0.5s ease,
            border-color 0.25s ease,
            box-shadow 0.25s ease,
            background 0.25s ease;
        }


        .acp-card.visible { opacity: 1; transform: translateY(0); }

        /* Top accent bar */
        .acp-card::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 2px;
          background: linear-gradient(90deg,
            rgba(var(--card-rgb), 0.8) 0%,
            rgba(var(--card-rgb), 0.3) 100%
          );
          opacity: 0;
          transition: opacity 0.25s ease;
        }

        /* Glow bg on hover */
        .acp-card::after {
          content: '';
          position: absolute;
          inset: 0;
          background: radial-gradient(
            ellipse 70% 60% at 20% 30%,
            rgba(var(--card-rgb), 0.06) 0%,
            transparent 70%
          );
          opacity: 0;
          transition: opacity 0.3s ease;
          pointer-events: none;
        }

        .acp-card:hover {
          border-color: rgba(var(--card-rgb), 0.45);
          box-shadow:
            0 0 0 1px rgba(var(--card-rgb), 0.12),
            0 8px 32px rgba(var(--card-rgb), 0.12),
            0 2px 8px rgba(0,0,0,0.3);
          transform: translateY(-3px);
        }

        .acp-card.visible:hover { transform: translateY(-3px); }

        .acp-card:hover::before { opacity: 1; }
        .acp-card:hover::after  { opacity: 1; }

        /* Card top row */
        .acp-card-top {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          margin-bottom: 1.4rem;
        }

        /* Icon box */
        .acp-card-icon {
          width: 48px; height: 48px;
          border-radius: 6px;
          display: grid; place-items: center;
          background: rgba(var(--card-rgb), 0.10);
          border: 1px solid rgba(var(--card-rgb), 0.20);
          color: rgba(var(--card-rgb), 1);
          flex-shrink: 0;
          transition: background 0.2s, border-color 0.2s;
        }

        .acp-card:hover .acp-card-icon {
          background: rgba(var(--card-rgb), 0.18);
          border-color: rgba(var(--card-rgb), 0.35);
        }

        /* Tag badge */
        .acp-card-badge {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 3px;
        }

        .acp-card-tag {
          font-family: var(--mono);
          font-size: 0.6rem;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          color: rgba(var(--card-rgb), 0.7);
          padding: 0.2rem 0.55rem;
          border: 1px solid rgba(var(--card-rgb), 0.25);
          border-radius: 2px;
          background: rgba(var(--card-rgb), 0.06);
        }

        .acp-card-stat {
          font-family: 'Rajdhani', sans-serif;
          font-size: 0.65rem;
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--text3);
        }

        .acp-card-stat strong {
          color: rgba(var(--card-rgb), 0.8);
          font-weight: 700;
        }

        /* Title */
        .acp-card-title {
          font-family: 'Rajdhani', sans-serif;
          font-size: 1.55rem;
          font-weight: 700;
          color: var(--text);
          letter-spacing: 0.03em;
          margin-bottom: 0.5rem;
          line-height: 1.1;
        }

        /* Description */
        .acp-card-desc {
          font-size: 0.85rem;
          color: var(--text2);
          line-height: 1.65;
          flex: 1;
          margin-bottom: 1.5rem;
        }

        /* Footer CTA */
        .acp-card-cta {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .acp-card-cta-text {
          display: flex;
          align-items: center;
          gap: 0.45rem;
          font-family: 'Rajdhani', sans-serif;
          font-size: 0.8rem;
          font-weight: 600;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: rgba(var(--card-rgb), 0.6);
          transition: color 0.2s ease;
        }

        .acp-card-cta-text svg {
          transition: transform 0.2s ease;
        }

        .acp-card:hover .acp-card-cta-text {
          color: rgba(var(--card-rgb), 1);
        }

        .acp-card:hover .acp-card-cta-text svg {
          transform: translateX(4px);
        }

        .acp-card-cta-line {
          height: 1px;
          flex: 1;
          margin: 0 1rem;
          background: rgba(var(--card-rgb), 0.12);
        }

        /* ── STATUS BAR ──────────────────────────────────── */
        .acp-statusbar {
          display: flex;
          align-items: center;
          gap: 1.25rem;
          padding: 0.55rem 1.25rem;
          border: 1px solid var(--border2);
          border-radius: 4px;
          background: rgba(13,22,48,0.5);
          opacity: 0;
          transform: translateY(8px);
          transition: opacity 0.5s ease 0.5s, transform 0.5s ease 0.5s;
          flex-shrink: 0;
          margin-bottom: 0.75rem;
        }



        .acp-statusbar.visible { opacity: 1; transform: translateY(0); }

        .acp-status-dot {
          width: 8px; height: 8px;
          border-radius: 50%;
          background: var(--green);
          box-shadow: 0 0 8px var(--green);
          flex-shrink: 0;
          animation: pulse 2.5s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 6px var(--green); }
          50%       { box-shadow: 0 0 14px var(--green), 0 0 20px rgba(0,203,93,0.3); }
        }

        .acp-status-item {
          font-family: var(--mono);
          font-size: 0.7rem;
          color: var(--text3);
          letter-spacing: 0.06em;
          white-space: nowrap;
        }

        .acp-status-item strong { color: var(--text2); font-weight: 500; }
        .acp-status-item .hi    { color: var(--future-50); }
        .acp-status-item .ok    { color: var(--green); }

        .acp-status-sep {
          width: 1px; height: 14px;
          background: var(--border2);
          flex-shrink: 0;
        }

        /* ── FOOTER ──────────────────────────────────────── */
        .acp-footer-bar {
          position: relative;
          z-index: 1;
          border-top: 1px solid rgba(0,114,188,0.12);
          background: rgba(7,15,38,0.6);
          padding: 0.55rem 2.5rem;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          flex-shrink: 0;
        }

        .acp-footer-copy {
          font-family: var(--mono);
          font-size: 0.62rem;
          color: var(--text3);
          letter-spacing: 0.08em;
        }

        .acp-footer-copy strong { color: var(--future-blue); font-weight: 500; }

        .acp-footer-version {
          font-family: var(--mono);
          font-size: 0.62rem;
          color: var(--text3);
          letter-spacing: 0.08em;
        }
      `}</style>

      <div className="acp-root">
        {/* BG grid */}
        <div className="acp-bg-grid" />

        {/* ── Nav ── */}
        <nav className="acp-nav">
          <div className="acp-nav-brand">
            <img src="/logo.webp" alt="NTT DATA" className="acp-nav-logo" />
          </div>

          <div className="acp-nav-sep" />

          <div className="acp-nav-context">
            <span className="acp-nav-eyebrow">Admin Console</span>
            <span className="acp-nav-title">Platform Administration</span>
          </div>

          <div className="acp-nav-right">
            {canViewDashboard && (
              <Link
                to="/dashboard"
                style={{
                  fontFamily: "var(--mono)",
                  fontSize: "0.72rem",
                  letterSpacing: "0.08em",
                  color: "var(--turquoise)",
                  textDecoration: "none",
                  opacity: 0.8,
                  padding: "0 0.5rem",
                }}
              >
                ← Dashboard
              </Link>
            )}
            <button className="acp-logout-btn" onClick={onLogout}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
              </svg>
              Sign out
            </button>
          </div>
        </nav>

        {/* ── Hero ── */}
        <section className="acp-hero">
          <div className="acp-hero-bg" />
          <div className="acp-hero-inner">
            <div className={`acp-hero-tag ${mounted ? "visible" : ""}`}>
              <span className="acp-hero-tag-line" />
              Secure Administration Portal
              <span className="acp-hero-tag-line" />
            </div>
            <h1 className={`acp-hero-heading ${mounted ? "visible" : ""}`}>
              Welcome back,&nbsp;<em>{user.username}</em>
            </h1>
            <p className={`acp-hero-sub ${mounted ? "visible" : ""}`}>
              Select a module below to manage your platform. All activity within this console
              is logged and subject to compliance review.
            </p>
          </div>
        </section>

        <div className="acp-divider" />

        {/* ── Main ── */}
        <main className="acp-main">
          <div className="acp-main-inner">

            {/* Module cards */}
            <div className="acp-grid">
              {modules.map((mod, i) => (
                <Link
                  key={mod.to}
                  className={`acp-card ${mounted ? "visible" : ""}`}
                  to={mod.to}
                  style={{
                    ["--card-rgb" as string]: mod.accentRgb,
                    transitionDelay: mounted ? `${0.25 + i * 0.1}s` : "0s",
                  }}
                >
                  <div className="acp-card-top">
                    <div className="acp-card-icon">{mod.icon}</div>
                    <div className="acp-card-badge">
                      <span className="acp-card-tag">{mod.tag}</span>
                      <span className="acp-card-stat">
                        <strong>{mod.stat}</strong> · {mod.statLabel}
                      </span>
                    </div>
                  </div>

                  <div className="acp-card-title">{mod.title}</div>
                  <div className="acp-card-desc">{mod.sub}</div>

                  <div className="acp-card-cta">
                    <span className="acp-card-cta-text">
                      Open Module
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12"/>
                        <polyline points="12 5 19 12 12 19"/>
                      </svg>
                    </span>
                    <span className="acp-card-cta-line" />
                  </div>
                </Link>
              ))}
            </div>

            {/* Status bar */}
            <div className={`acp-statusbar ${mounted ? "visible" : ""}`}>
              <span className="acp-status-dot" />
              <span className="acp-status-item">
                System <strong className="ok">Operational</strong>
              </span>
              <span className="acp-status-sep" />
              <span className="acp-status-item">
                Operator&nbsp;<strong className="hi">{user.username}</strong>
              </span>
              <span className="acp-status-sep" />
              <span className="acp-status-item">
                Modules available&nbsp;<strong>{modules.length}</strong>
              </span>
              <span className="acp-status-sep" />
              <span className="acp-status-item">
                Session&nbsp;<strong className="ok">Active</strong>
              </span>
            </div>

          </div>
        </main>



      </div>
    </>
  );
};

export default AdminChoicePage;