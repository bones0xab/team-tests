import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules
from components.ai_analysis import show_ai_analysis

st.set_page_config(
    page_title="NTT DATA | Project Intelligence",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        display: block !important;
        visibility: visible !important;
        width: 250px !important;
    }
    [data-testid="collapsedControl"] {
        display: block !important;
    }
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Source+Sans+3:wght@300;400;600&display=swap');

    /* ── LIGHT MODE (default) ── */
    :root {
        --smart-navy:      #070F26;
        --future-blue:     #0072BC;
        --future-blue-50:  #19A3FC;
        --future-blue-150: #005B96;
        --turquoise:       #00DFED;
        --green:           #00CB5D;
        --yellow:          #FFC400;
        --orange:          #FF7A00;
        --white:           #FFFFFF;
        --grey-50:         #E8E8E8;

        /* semantic */
        --bg-primary:      #F4F6FA;
        --bg-secondary:    #FFFFFF;
        --bg-card:         #FFFFFF;
        --bg-sidebar:      #070F26;
        --text-primary:    #070F26;
        --text-secondary:  #2E404D;
        --text-muted:      #6B7A8D;
        --border-color:    rgba(0,114,188,0.2);
        --kpi-bg:          #FFFFFF;
        --kpi-hover:       #F0F5FF;
        --chart-paper:     rgba(255,255,255,0);
        --chart-plot:      rgba(255,255,255,0);
        --chart-grid:      rgba(0,114,188,0.1);
        --chart-line:      rgba(0,114,188,0.2);
        --chart-tick:      rgba(46,64,77,0.5);
        --chart-text:      #2E404D;
        --table-bg:        #FFFFFF;
        --section-border:  var(--turquoise);
    }

    /* ── DARK MODE ── */
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-primary:    #070F26;
            --bg-secondary:  #0A1530;
            --bg-card:       rgba(7,15,38,0.95);
            --bg-sidebar:    #050D20;
            --text-primary:  #E8E8E8;
            --text-secondary:#C8D0DC;
            --text-muted:    rgba(232,232,232,0.45);
            --border-color:  rgba(0,114,188,0.3);
            --kpi-bg:        rgba(7,15,38,0.95);
            --kpi-hover:     rgba(0,114,188,0.08);
            --chart-paper:   rgba(0,0,0,0);
            --chart-plot:    rgba(0,0,0,0);
            --chart-grid:    rgba(0,114,188,0.15);
            --chart-line:    rgba(0,114,188,0.3);
            --chart-tick:    rgba(232,232,232,0.4);
            --chart-text:    #E8E8E8;
            --table-bg:      rgba(7,15,38,0.8);
        }
    }

    /* ── STREAMLIT THEME OVERRIDE (respects Streamlit's own dark/light toggle) ── */
    [data-theme="dark"] {
        --bg-primary:    #070F26;
        --bg-secondary:  #0A1530;
        --bg-card:       rgba(7,15,38,0.95);
        --bg-sidebar:    #050D20;
        --text-primary:  #E8E8E8;
        --text-secondary:#C8D0DC;
        --text-muted:    rgba(232,232,232,0.45);
        --border-color:  rgba(0,114,188,0.3);
        --kpi-bg:        rgba(7,15,38,0.95);
        --kpi-hover:     rgba(0,114,188,0.08);
        --chart-paper:   rgba(0,0,0,0);
        --chart-plot:    rgba(0,0,0,0);
        --chart-grid:    rgba(0,114,188,0.15);
        --chart-line:    rgba(0,114,188,0.3);
        --chart-tick:    rgba(232,232,232,0.4);
        --chart-text:    #E8E8E8;
        --table-bg:      rgba(7,15,38,0.8);
    }

    [data-theme="light"] {
        --bg-primary:    #F4F6FA;
        --bg-secondary:  #FFFFFF;
        --bg-card:       #FFFFFF;
        --bg-sidebar:    #070F26;
        --text-primary:  #070F26;
        --text-secondary:#2E404D;
        --text-muted:    #6B7A8D;
        --border-color:  rgba(0,114,188,0.2);
        --kpi-bg:        #FFFFFF;
        --kpi-hover:     #F0F5FF;
        --chart-paper:   rgba(255,255,255,0);
        --chart-plot:    rgba(255,255,255,0);
        --chart-grid:    rgba(0,114,188,0.1);
        --chart-line:    rgba(0,114,188,0.2);
        --chart-tick:    rgba(46,64,77,0.5);
        --chart-text:    #2E404D;
        --table-bg:      #FFFFFF;
    }

    /* ── GLOBAL ── */
    html, body, [class*="css"] {
        font-family: 'Source Sans 3', sans-serif;
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }

    .main .block-container {
        background-color: var(--bg-primary);
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* ── HEADER ── */
    .ntt-header {
        border-top: 4px solid var(--future-blue);
        background: var(--bg-primary);
        padding: 2.5rem 0 1.5rem 0;
        margin-bottom: 2rem;
        position: relative;
    }

    .ntt-header::after {
        content: '';
        position: absolute;
        bottom: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, var(--future-blue) 0%, var(--turquoise) 50%, transparent 100%);
    }

    .ntt-logo-line {
        font-family: 'Rajdhani', sans-serif;
        font-size: .85rem;
        font-weight: 600;
        letter-spacing: .2em;
        color: var(--future-blue);
        text-transform: uppercase;
        margin-bottom: .5rem;
    }

    .ntt-title {
        font-family: 'Rajdhani', sans-serif;
        font-size: 2.8rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.1;
        margin-bottom: .4rem;
    }

    .ntt-title span { color: var(--future-blue); }

    .ntt-subtitle {
        font-size: 1rem;
        font-weight: 300;
        color: var(--text-muted);
        letter-spacing: .05em;
    }

    /* ── SECTION LABELS ── */
    .ntt-section {
        font-family: 'Rajdhani', sans-serif;
        font-size: 1.4rem;
        font-weight: 600;
        color: var(--text-primary);
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-top: 2.5rem;
        margin-bottom: 1rem;
        padding-left: .75rem;
        border-left: 3px solid var(--turquoise);
    }

    /* ── KPI GRID ── */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1px;
        background: var(--border-color);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 2rem;
    }

    .kpi-card {
        background: var(--kpi-bg);
        padding: 1.5rem 1.8rem;
        position: relative;
        transition: background .2s;
    }

    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
    }

    .kpi-card.blue::before   { background: var(--future-blue); }
    .kpi-card.cyan::before   { background: var(--turquoise); }
    .kpi-card.green::before  { background: var(--green); }
    .kpi-card.yellow::before { background: var(--yellow); }
    .kpi-card:hover          { background: var(--kpi-hover); }

    .kpi-label {
        font-size: .75rem;
        font-weight: 600;
        letter-spacing: .15em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: .5rem;
    }

    .kpi-value {
        font-family: 'Rajdhani', sans-serif;
        font-size: 2.6rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
        margin-bottom: .3rem;
    }

    .kpi-delta          { font-size: .8rem; color: var(--text-muted); }
    .kpi-delta.positive { color: var(--green); }
    .kpi-delta.negative { color: var(--orange); }
    .kpi-delta.neutral  { color: var(--future-blue); }

    /* ── HEALTH BANNER ── */
    .health-banner {
        display: flex;
        align-items: center;
        gap: 1.5rem;
        padding: 1.2rem 2rem;
        border-radius: 4px;
        margin-bottom: 1.5rem;
        border: 1px solid;
        background: var(--bg-secondary);
    }

    .health-banner.HEALTHY { border-color: var(--green);  background: rgba(0,203,93,.06); }
    .health-banner.WATCH   { border-color: var(--yellow); background: rgba(255,196,0,.06); }
    .health-banner.AT_RISK { border-color: var(--orange); background: rgba(255,122,0,.06); }
    .health-banner.UNKNOWN { border-color: var(--border-color); }

    .health-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
    .health-banner.HEALTHY .health-dot { background: var(--green);  box-shadow: 0 0 8px var(--green); }
    .health-banner.WATCH   .health-dot { background: var(--yellow); box-shadow: 0 0 8px var(--yellow); }
    .health-banner.AT_RISK .health-dot { background: var(--orange); box-shadow: 0 0 8px var(--orange); }
    .health-banner.UNKNOWN .health-dot { background: var(--text-muted); }

    .health-label {
        font-size: .75rem;
        font-weight: 600;
        letter-spacing: .15em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: .2rem;
    }

    .health-status {
        font-family: 'Rajdhani', sans-serif;
        font-size: 1.3rem;
        font-weight: 700;
        letter-spacing: .08em;
    }

    .health-banner.HEALTHY .health-status { color: var(--green); }
    .health-banner.WATCH   .health-status { color: var(--yellow); }
    .health-banner.AT_RISK .health-status { color: var(--orange); }
    .health-banner.UNKNOWN .health-status { color: var(--text-muted); }

    .health-meta {
        margin-left: auto;
        font-size: .8rem;
        color: var(--text-muted);
        letter-spacing: .05em;
    }

    /* ── BUTTONS ── */
    .stDownloadButton button {
        background: transparent !important;
        border: 1px solid var(--future-blue) !important;
        color: var(--future-blue) !important;
        border-radius: 2px !important;
        font-family: 'Source Sans 3', sans-serif !important;
        font-size: .85rem !important;
        font-weight: 600 !important;
        letter-spacing: .08em !important;
        text-transform: uppercase !important;
        padding: .6rem 1rem !important;
        transition: all .2s !important;
    }

    .stDownloadButton button:hover {
        background: var(--future-blue) !important;
        color: #FFFFFF !important;
    }

    .stButton > button {
        background: var(--future-blue) !important;
        border: none !important;
        color: #FFFFFF !important;
        border-radius: 2px !important;
        font-family: 'Source Sans 3', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: .06em !important;
        transition: all .2s !important;
    }

    .stButton > button:hover { background: var(--future-blue-50) !important; }

    /* ── SIDEBAR ── */
    section[data-testid="stSidebar"] {
        background: var(--bg-sidebar) !important;
        border-right: 1px solid rgba(0,114,188,.3);
    }

    section[data-testid="stSidebar"] > div { padding-top: 1.5rem; }

    .sidebar-logo {
        font-family: 'Rajdhani', sans-serif;
        font-size: 1.3rem;
        font-weight: 700;
        color: #FFFFFF;
        letter-spacing: .1em;
        padding: 0 1rem 1.5rem 1rem;
        border-bottom: 1px solid rgba(0,114,188,.3);
        margin-bottom: 1.5rem;
    }

    .sidebar-logo span { color: var(--turquoise); }

    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p {
        color: var(--grey-50) !important;
        font-size: .85rem !important;
    }

    section[data-testid="stSidebar"] h3 {
        color: var(--turquoise) !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-size: .75rem !important;
        font-weight: 600 !important;
        letter-spacing: .2em !important;
        text-transform: uppercase !important;
    }

    section[data-testid="stSidebar"] hr {
        border-color: rgba(0,114,188,.2) !important;
    }

    section[data-testid="stSidebar"] input {
        background: rgba(0,114,188,.1) !important;
        border: 1px solid rgba(0,114,188,.3) !important;
        border-radius: 2px !important;
        color: #FFFFFF !important;
    }

    /* ── ALERTS ── */
    .risk-item {
        padding: .6rem 1rem;
        margin-bottom: .4rem;
        border-left: 3px solid var(--orange);
        background: rgba(255,122,0,.06);
        font-size: .9rem;
        color: var(--text-secondary);
        border-radius: 0 2px 2px 0;
    }

    /* ── DATA TABLE ── */
    .stDataFrame {
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
    }

    /* ── MISC ── */
    .stAlert {
        background: rgba(0,114,188,.08) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 2px !important;
    }

    div[data-testid="stMetric"] {
        background: transparent !important;
        padding: 0 !important;
        box-shadow: none !important;
    }

    /* ── FOOTER ── */
    .ntt-footer {
        margin-top: 4rem;
        padding-top: 1.5rem;
        border-top: 1px solid var(--border-color);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .ntt-footer-brand {
        font-family: 'Rajdhani', sans-serif;
        font-size: 1rem;
        font-weight: 700;
        color: var(--text-muted);
        letter-spacing: .1em;
    }

    .ntt-footer-info {
        font-size: .75rem;
        color: var(--text-muted);
        letter-spacing: .05em;
    }

    /* ── COUNTER LABEL ── */
    .count-label {
        font-size: .78rem;
        color: var(--text-muted);
        margin-top: .5rem;
        letter-spacing: .05em;
    }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    [data-testid="stHeader"] { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

# ── COLOUR PALETTE ──
NTT_COLORS = ["#0072BC","#00DFED","#00CB5D","#19A3FC","#FFC400","#FF7A00","#005B96","#009AA4"]


def apply_chart_theme(fig: go.Figure, title_text: str = "", height: int = 340,
                      dark: bool = False) -> go.Figure:
    """Apply NTT DATA brand theme. Adapts grid/text colours for dark vs light."""
    text_col   = "#E8E8E8" if dark else "#2E404D"
    grid_col   = "rgba(0,114,188,0.15)" if dark else "rgba(0,114,188,0.10)"
    line_col   = "rgba(0,114,188,0.30)" if dark else "rgba(0,114,188,0.20)"
    tick_col   = "rgba(232,232,232,0.4)" if dark else "rgba(46,64,77,0.5)"
    legend_bg  = "rgba(7,15,38,0.85)"   if dark else "rgba(255,255,255,0.90)"
    legend_bdr = "rgba(0,114,188,0.3)"  if dark else "rgba(0,114,188,0.2)"

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        font=dict(family="Source Sans 3", color=text_col, size=12),
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(bgcolor=legend_bg, bordercolor=legend_bdr, borderwidth=1,
                    font=dict(color=text_col)),
    )
    fig.update_xaxes(gridcolor=grid_col, linecolor=line_col, tickcolor=tick_col,
                     tickfont=dict(color=text_col))
    fig.update_yaxes(gridcolor=grid_col, linecolor=line_col, tickcolor=tick_col,
                     tickfont=dict(color=text_col))
    if title_text:
        fig.update_layout(
            title=dict(text=title_text,
                       font=dict(size=13, color=text_col, family="Source Sans 3"))
        )
    return fig


# ── DETECT DARK MODE via Streamlit's theme ──
# Streamlit exposes the theme via st.get_option since v1.17
try:
    _theme_base = st.get_option("theme.base")
    IS_DARK = (_theme_base == "dark")
except Exception:
    IS_DARK = False   # safe default: light

# ════════════════════════════════════════
#  HEADER
# ════════════════════════════════════════
# Place refresh button in top-right near Deploy
st.markdown("""
<style>
.refresh-top-btn {
    position: fixed;
    top: 0.75rem;
    right: 6rem;
    z-index: 999;
}
</style>
""", unsafe_allow_html=True)

with st.container():
    col_refresh = st.columns([10, 1])[1]
    with col_refresh:
        if st.button("↺ Refresh", key="top_refresh"):
            st.cache_data.clear()
            st.rerun()

# Then the header alone
st.markdown("""
<div class="ntt-header">
    <div class="ntt-logo-line">NTT DATA &nbsp;·&nbsp; Project Intelligence Platform</div>
    <div class="ntt-title">AI <span>Project Monitor</span></div>
    <div class="ntt-subtitle">Real-time Jira health monitoring powered by LangChain agents &amp; Ollama</div>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="sidebar-logo">NTT <span>DATA</span></div>', unsafe_allow_html=True)
    st.markdown("### Configuration")
    st.markdown("---")
    st.markdown("### Project")
    project_key = st.text_input("Project Key", value="KAN")
    st.markdown("---")
    st.markdown("### Time Range")
    date_option = st.radio("Analysis period",
                           ["Last 7 days", "Last 30 days", "Last 90 days", "Custom range"],
                           index=1)
    if date_option == "Custom range":
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("From", datetime.now() - timedelta(days=30))
        with c2:
            end_date = st.date_input("To", datetime.now())
        days_back = (datetime.now().date() - start_date).days
    else:
        days_back = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}[date_option]
    st.markdown("---")
    st.markdown("### Alerts")
    enable_alerts = st.checkbox("Enable automatic alerts", value=True)
    alert_threshold = st.select_slider("Alert sensitivity",
                                       options=["HEALTHY", "WATCH", "AT_RISK"],
                                       value="WATCH")
    st.markdown("---")
    st.markdown("### About")
    st.markdown(
        f'<div style="font-size:.78rem;color:rgba(232,232,232,.45);line-height:1.8;">'
        f'Version 2.0<br>LangChain · Ollama<br>{datetime.now().strftime("%Y-%m-%d %H:%M")}</div>',
        unsafe_allow_html=True
    )

# ════════════════════════════════════════
#  FETCH DATA
# ════════════════════════════════════════
jql    = f"project={project_key} AND updated >= -{days_back}d"
fields = ["summary", "status", "assignee", "updated", "priority", "created"]


@st.cache_data(ttl=300)
def fetch_and_analyze(jql, fields):
    issues = list(search_issues(jql, fields))
    data   = [normalize_issue(i) for i in issues]
    if data:
        metrics = compute_signals(data)
        rules   = evaluate_rules(metrics)
        return issues, data, metrics, rules
    return [], [], {}, {}


with st.spinner("Fetching project data…"):
    issues, data, metrics, rules = fetch_and_analyze(jql, fields)

# ════════════════════════════════════════
#  MAIN CONTENT
# ════════════════════════════════════════
if data:
    df             = pd.DataFrame(data)
    project_health = rules.get("project_health", "UNKNOWN")
    completion     = metrics['done_ratio'] * 100
    wip_pct        = metrics['wip_ratio']  * 100
    stale          = metrics.get('stale_in_progress_count', 0)

    # ── HEALTH BANNER ──
    st.markdown(f"""
    <div class="health-banner {project_health}">
        <div class="health-dot"></div>
        <div>
            <div class="health-label">Project Health Status</div>
            <div class="health-status">{project_health.replace('_', ' ')}</div>
        </div>
        <div class="health-meta">
            {project_key} &nbsp;·&nbsp; Last {days_back} days &nbsp;·&nbsp; {len(data)} issues
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── ALERTS ──
    if enable_alerts:
        alert_levels = {"HEALTHY": 0, "WATCH": 1, "AT_RISK": 2}
        if alert_levels.get(project_health, 0) >= alert_levels.get(alert_threshold, 1):
            with st.expander(f"⚠  Active Alerts — {project_health}", expanded=True):
                for risk in rules.get("risks", []):
                    st.markdown(f'<div class="risk-item">{risk}</div>',
                                unsafe_allow_html=True)

    # ── KPI CARDS ──
    st.markdown('<div class="ntt-section">Key Performance Indicators</div>',
                unsafe_allow_html=True)
    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card blue">
            <div class="kpi-label">Total Issues</div>
            <div class="kpi-value">{metrics['total']:,}</div>
            <div class="kpi-delta neutral">{metrics['total'] - metrics.get('done', 0)} active</div>
        </div>
        <div class="kpi-card cyan">
            <div class="kpi-label">Completion Rate</div>
            <div class="kpi-value">{completion:.1f}<span style="font-size:1.2rem">%</span></div>
            <div class="kpi-delta {'positive' if completion>=50 else 'negative'}">
                {'▲' if completion>=50 else '▼'} {abs(completion-50):.1f}% vs 50% target
            </div>
        </div>
        <div class="kpi-card green">
            <div class="kpi-label">Work In Progress</div>
            <div class="kpi-value">{wip_pct:.1f}<span style="font-size:1.2rem">%</span></div>
            <div class="kpi-delta neutral">{metrics['wip']} issues active</div>
        </div>
        <div class="kpi-card yellow">
            <div class="kpi-label">Stale Issues</div>
            <div class="kpi-value">{stale}</div>
            <div class="kpi-delta {'negative' if stale>0 else 'positive'}">
                {'Needs attention' if stale>0 else 'All up to date'}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── AI ANALYSIS ──
    st.markdown('<div class="ntt-section">AI Risk Analysis</div>', unsafe_allow_html=True)
    show_ai_analysis(rules)

    # ── CHARTS ──
    st.markdown('<div class="ntt-section">Analytics</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        status_counts = df['status_name'].value_counts()
        fig1 = go.Figure(data=[go.Bar(
            x=status_counts.index,
            y=status_counts.values,
            marker=dict(color=NTT_COLORS[:len(status_counts)],
                        line=dict(color="rgba(0,0,0,0)", width=0)),
            text=status_counts.values,
            textposition='outside',
            textfont=dict(color="#E8E8E8" if IS_DARK else "#2E404D", size=11),
        )])
        fig1 = apply_chart_theme(fig1, "Issues by Status", 340, IS_DARK)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        df["assignee_display"] = df["assignee"].fillna("Unassigned")
        assignee_counts = df["assignee_display"].value_counts()
        fig2 = go.Figure(data=[go.Pie(
            labels=assignee_counts.index,
            values=assignee_counts.values,
            hole=0.55,
            marker=dict(colors=NTT_COLORS,
                        line=dict(color=["#070F26" if IS_DARK else "#FFFFFF"] * len(assignee_counts),
                                  width=2)),
            textfont=dict(color="#E8E8E8" if IS_DARK else "#2E404D", size=11),
        )])
        fig2 = apply_chart_theme(fig2, "Issues by Assignee", 340, IS_DARK)
        st.plotly_chart(fig2, use_container_width=True)

    # ── TIMELINE ──
    df['date'] = pd.to_datetime(df['updated_at']).dt.date
    timeline   = df.groupby("date").size().reset_index(name="count")
    fig3       = go.Figure()
    fig3.add_trace(go.Scatter(
        x=timeline["date"], y=timeline["count"],
        mode='lines+markers', name='Updates',
        line=dict(color="#0072BC", width=2.5),
        marker=dict(size=6, color="#00DFED", line=dict(color="#0072BC", width=1.5)),
        fill='tozeroy', fillcolor='rgba(0,114,188,0.08)',
    ))
    fig3 = apply_chart_theme(fig3, "Daily Update Activity", 280, IS_DARK)
    fig3.update_layout(hovermode='x unified')
    st.plotly_chart(fig3, use_container_width=True)

    # ── HEATMAP ──
    st.markdown('<div class="ntt-section">Team Activity Heatmap</div>', unsafe_allow_html=True)
    df['assignee_clean'] = df['assignee'].fillna('Unassigned')
    heatmap_data = df.groupby(['assignee_clean', 'date']).size().reset_index(name='activity')
    pivot = heatmap_data.pivot(index='assignee_clean', columns='date',
                               values='activity').fillna(0)
    if pivot.empty or pivot.values.sum() == 0:
        st.info("ℹ️ Not enough activity data spread across dates to display heatmap.")
    elif not pivot.empty:
        fig_heat = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[str(d) for d in pivot.columns],
            y=pivot.index,
            colorscale=[[0.0,"#070F26"],[0.3,"#005B96"],
                        [0.6,"#0072BC"],[0.8,"#00DFED"],[1.0,"#00CB5D"]],
            text=pivot.values,
            texttemplate="%{text:.0f}",
            textfont=dict(size=10, color="white"),
            colorbar=dict(title=dict(text="Updates",
                                    font=dict(color="#E8E8E8" if IS_DARK else "#2E404D")),
                        tickfont=dict(color="#E8E8E8" if IS_DARK else "#2E404D"),
                        thickness=12, len=0.8),
        ))
        fig_heat = apply_chart_theme(fig_heat, "Daily Activity by Team Member",
                                     280 + len(pivot.index) * 28, IS_DARK)
        st.plotly_chart(fig_heat, use_container_width=True)

    # ── EXPORT ──
    st.markdown('<div class="ntt-section">Export & Reports</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4, gap="small")

    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="↓  CSV", data=csv,
            file_name=f"nttdata_{project_key}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv", use_container_width=True)

    with col2:
        report_data = {
            "project": project_key,
            "generated_at": datetime.now().isoformat(),
            "analysis_period_days": days_back,
            "project_health": project_health,
            "metrics": metrics, "rules": rules,
            "issues": df.to_dict('records'),
        }
        st.download_button(
            label="↓  JSON", data=json.dumps(report_data, indent=2, default=str),
            file_name=f"nttdata_{project_key}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json", use_container_width=True)

    with col3:
        def generate_pdf():
            buf    = BytesIO()
            doc    = SimpleDocTemplate(buf, pagesize=letter)
            styles = getSampleStyleSheet()
            story  = [
                Paragraph("<b>NTT DATA — Project Intelligence Report</b>", styles['Title']),
                Spacer(1, 12),
                Paragraph(f"Project: {project_key}", styles['Normal']),
                Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']),
                Paragraph(f"Period: Last {days_back} days", styles['Normal']),
                Paragraph(f"Health: {project_health}", styles['Normal']),
                Spacer(1, 16),
                Paragraph("<b>Key Metrics</b>", styles['Heading2']),
                Paragraph(f"Total Issues: {metrics['total']}", styles['Normal']),
                Paragraph(f"Completion Rate: {completion:.1f}%", styles['Normal']),
                Paragraph(f"WIP: {metrics['wip']} ({wip_pct:.1f}%)", styles['Normal']),
                Paragraph(f"Stale Issues: {stale}", styles['Normal']),
            ]
            if rules.get('risks'):
                story += [Spacer(1,12), Paragraph("<b>Identified Risks</b>", styles['Heading2'])]
                story += [Paragraph(f"• {r}", styles['Normal']) for r in rules['risks']]
            if rules.get('actions'):
                story += [Spacer(1,12), Paragraph("<b>Recommended Actions</b>", styles['Heading2'])]
                story += [Paragraph(f"• {a}", styles['Normal']) for a in rules['actions']]
            doc.build(story)
            buf.seek(0)
            return buf

        st.download_button(
            label="↓  PDF", data=generate_pdf(),
            file_name=f"nttdata_{project_key}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf", use_container_width=True)

    with col4:
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_excel = df.copy()
            if 'updated_at' in df_excel.columns:
                df_excel['updated_at'] = df_excel['updated_at'].apply(
                    lambda x: x.replace(tzinfo=None) if hasattr(x,'tzinfo') and x.tzinfo else x)
            df_excel.to_excel(writer, sheet_name='Issues', index=False)
            pd.DataFrame([metrics]).to_excel(writer, sheet_name='Metrics', index=False)
        excel_buffer.seek(0)
        st.download_button(
            label="↓  Excel", data=excel_buffer,
            file_name=f"nttdata_{project_key}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)

    # ── SNAPSHOTS ──
    st.markdown('<div class="ntt-section">Project Snapshots</div>', unsafe_allow_html=True)
    colA, colB = st.columns([5, 1])
    with colB:
        if st.button("Save Snapshot", use_container_width=True):
            if 'snapshots' not in st.session_state:
                st.session_state.snapshots = []
            st.session_state.snapshots.append({
                "timestamp": datetime.now().isoformat(), "project": project_key,
                "health": project_health, "metrics": metrics, "rules": rules,
            })
            st.success("Snapshot saved.")

    if 'snapshots' in st.session_state and st.session_state.snapshots:
        snap_df = pd.DataFrame([{
            "Date": s['timestamp'][:19], "Health": s['health'],
            "Issues": s['metrics']['total'], "WIP": s['metrics']['wip'],
            "WIP %": f"{s['metrics']['wip_ratio']:.1%}",
            "Risks": len(s['rules']['risks']),
        } for s in st.session_state.snapshots])
        st.dataframe(snap_df, use_container_width=True, hide_index=True)

        health_map = {"HEALTHY": 1, "WATCH": 2, "AT_RISK": 3}
        snap_df['health_score'] = snap_df['Health'].map(health_map)
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=snap_df['Date'], y=snap_df['health_score'],
            mode='lines+markers', name='Health',
            line=dict(color="#0072BC", width=2.5),
            marker=dict(size=10, color="#00DFED")))
        fig_trend = apply_chart_theme(fig_trend, "Project Health Trend", 280, IS_DARK)
        fig_trend.update_yaxes(tickmode='array', tickvals=[1,2,3],
                               ticktext=['HEALTHY','WATCH','AT RISK'])
        st.plotly_chart(fig_trend, use_container_width=True)

    # ── ISSUE TABLE ──
    st.markdown('<div class="ntt-section">Issue Details</div>', unsafe_allow_html=True)
    c1, c2, _ = st.columns([2, 2, 6])
    with c1:
        status_filter = st.selectbox("Filter by Status", ["All"] + list(df["status_name"].unique()))
    with c2:
        sort_by = st.selectbox("Sort by", ["Days Since Update", "Status", "Assignee"])

    filtered_df = df if status_filter == "All" else df[df["status_name"] == status_filter]
    if sort_by == "Days Since Update":
        filtered_df = filtered_df.sort_values('days_since_update', ascending=False)
    elif sort_by == "Status":
        filtered_df = filtered_df.sort_values('status_name')
    else:
        filtered_df = filtered_df.sort_values('assignee')

    display_df = filtered_df[['key','summary','status_name','assignee','days_since_update']].copy()
    display_df.columns = ['Key','Summary','Status','Assignee','Days Inactive']
    display_df['Assignee'] = display_df['Assignee'].fillna('Unassigned')
    row_height = 35
    header_height = 38
    min_height = 100
    max_height = 400
    dynamic_height = max(min_height, min(header_height + len(display_df) * row_height, max_height))
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=dynamic_height)
    st.markdown(f'<div class="count-label">Showing {len(filtered_df)} of {len(df)} issues</div>',
                unsafe_allow_html=True)

else:
    st.markdown("""
    <div style="padding:3rem;border:1px solid var(--border-color);border-radius:4px;
                text-align:center;margin-top:2rem;background:var(--bg-secondary);">
        <div style="font-family:'Rajdhani',sans-serif;font-size:2rem;font-weight:700;
                    color:var(--text-muted);margin-bottom:1rem;">No Data Found</div>
        <div style="color:var(--text-muted);font-size:.9rem;line-height:2;">
            Check your project key · Expand the date range · Verify Jira connection
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── FOOTER ──
st.markdown("""
<div class="ntt-footer">
    <div class="ntt-footer-brand">NTT DATA</div>
    <div class="ntt-footer-info">
        Project Intelligence Platform v2.0 &nbsp;·&nbsp; LangChain · Ollama &nbsp;·&nbsp; © 2026 NTT DATA
    </div>
</div>
""", unsafe_allow_html=True)