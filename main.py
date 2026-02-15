import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from services.Fetch import search_issues
from services.Normalisation import normalize_issue
from orchestration.metrics import compute_signals
from orchestration.rules import evaluate_rules
from components.ai_analysis import show_ai_analysis

# ===== PAGE CONFIG =====
st.set_page_config(
    page_title="AI Project Monitor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== CUSTOM CSS FOR PROFESSIONAL DESIGN =====
st.markdown("""
<style>
    /* Main title styling */
    .main-title {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        font-size: 1.2rem;
        color: #6c757d;
        margin-bottom: 2rem;
    }
    
    /* Metric cards with hover effect */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
    }
    
    div[data-testid="stMetric"] label {
        color: white !important;
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: white !important;
        font-size: 2rem !important;
        font-weight: 700;
    }
    
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: rgba(255, 255, 255, 0.9) !important;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.8rem;
        font-weight: 600;
        color: #2c3e50;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #667eea;
    }
    
    /* Download buttons */
    .stDownloadButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .stDownloadButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Primary button */
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* Alert boxes */
    .stAlert {
        border-radius: 10px;
        border-left: 5px solid;
    }
    
    /* ===== SIDEBAR STYLING - MATCHED TO MAIN THEME ===== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    
    section[data-testid="stSidebar"] > div {
        padding-top: 2rem;
    }
    
    /* Sidebar text colors */
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] label {
        color: white !important;
    }
    
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: white !important;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    /* Sidebar dividers */
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.2);
        margin: 1.5rem 0;
    }
    
    /* ===== FIX: Sidebar input fields - TEXT VISIBLE ===== */
    section[data-testid="stSidebar"] input {
        background-color: rgba(255, 255, 255, 0.15) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 8px !important;
        color: black !important;
        font-weight: 500 !important;
        backdrop-filter: blur(10px);
    }
    
    section[data-testid="stSidebar"] input::placeholder {
        color: rgba(255, 255, 255, 0.6) !important;
    }
    
    /* Forcer le texte blanc dans tous les inputs du sidebar */
    section[data-testid="stSidebar"] [data-baseweb="input"] input {
        color: black !important;
    }
    
    section[data-testid="stSidebar"] .stTextInput input {
        color: black !important;
    }
    
    /* Sidebar select boxes */
    section[data-testid="stSidebar"] .stSelectbox > div,
    section[data-testid="stSidebar"] .stRadio > div {
        background-color: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        backdrop-filter: blur(10px);
    }
    
    /* Sidebar checkbox */
    section[data-testid="stSidebar"] .stCheckbox label {
        color: black !important;
    }
    
    /* Sidebar info box */
    section[data-testid="stSidebar"] .stAlert {
        background-color: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        backdrop-filter: blur(10px);
    }
    
    section[data-testid="stSidebar"] .stAlert p {
        color: white !important;
    }
    
    /* Chart containers */
    .plot-container {
        background: white;
        border-radius: 15px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
    }
    
    /* Dataframe styling */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Success message */
    .success-badge {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        font-weight: 600;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ===== HEADER =====
st.markdown('<h1 class="main-title">🤖 AI Project Intelligence Dashboard</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Real-time project health monitoring powered by AI agents and predictive analytics</p>', unsafe_allow_html=True)

# ===== SIDEBAR =====
with st.sidebar:
    st.markdown("## ⚙️ Configuration Panel")
    st.markdown("---")
    
    # Project settings
    st.markdown("### 📊 Project Settings")
    project_key = st.text_input("🔑 Project Key", value="KAN", help="Enter your Jira project key")
    
    st.markdown("---")
    
    # Date filter with icons
    st.markdown("### 📅 Time Range")
    date_option = st.radio(
        "Select analysis period:",
        ["Last 7 days", "Last 30 days", "Last 90 days", "Custom range"],
        index=1,
        help="Choose the time range for analysis"
    )
    
    if date_option == "Custom range":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("📅 From", datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("📅 To", datetime.now())
        days_back = (datetime.now().date() - start_date).days
    else:
        days_map = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
        days_back = days_map[date_option]
    
    st.markdown("---")
    
    # Alert settings
    st.markdown("### 🔔 Smart Alerts")
    enable_alerts = st.checkbox("🔔 Enable automatic alerts", value=True)
    alert_threshold = st.select_slider(
        "Alert sensitivity:",
        options=["HEALTHY", "WATCH", "AT_RISK"],
        value="WATCH",
        help="Choose when to trigger alerts"
    )
    
    st.markdown("---")
    
    # Refresh button
    if st.button("🔄 Refresh Dashboard", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📖 About")
    st.info("**Version:** 2.0\n\n**Powered by:** LangChain + Ollama\n\n**Last Updated:** " + datetime.now().strftime("%Y-%m-%d %H:%M"))

# ===== FETCH DATA =====
jql = f"project={project_key} AND updated >= -{days_back}d"
fields = ["summary", "status", "assignee", "updated", "priority", "created"]

@st.cache_data(ttl=300)
def fetch_and_analyze(jql, fields):
    issues = list(search_issues(jql, fields))
    data = [normalize_issue(i) for i in issues]
    if data:
        metrics = compute_signals(data)
        rules = evaluate_rules(metrics)
        return issues, data, metrics, rules
    return [], [], {}, {}

with st.spinner("🔍 Analyzing project data..."):
    issues, data, metrics, rules = fetch_and_analyze(jql, fields)

if data:
    df = pd.DataFrame(data)
    project_health = rules.get("project_health", "UNKNOWN")
    
    # ===== SUCCESS BADGE =====
    st.markdown('<div class="success-badge">✅ AI Analysis Complete - Model Ready</div>', unsafe_allow_html=True)
    
    # ===== AUTOMATIC ALERTS =====
    if enable_alerts:
        alert_levels = {"HEALTHY": 0, "WATCH": 1, "AT_RISK": 2}
        if alert_levels.get(project_health, 0) >= alert_levels.get(alert_threshold, 1):
            st.error(f"🚨 **CRITICAL ALERT**: Project status is **{project_health}**")
            with st.expander("⚠️ View Risk Details", expanded=True):
                for risk in rules.get("risks", []):
                    st.warning(f"• {risk}")
    
    # ===== KEY METRICS WITH GRADIENT CARDS =====
    st.markdown('<h2 class="section-header">📊 Key Performance Indicators</h2>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📈 Total Issues",
            value=f"{metrics['total']:,}",
            delta=f"+{metrics['total'] - metrics.get('done', 0)} active",
            help="Total number of issues in the selected timeframe"
        )
    
    with col2:
        completion = metrics['done_ratio'] * 100
        st.metric(
            label="✅ Completion Rate",
            value=f"{completion:.1f}%",
            delta=f"{completion - 50:.1f}% vs 50% target",
            delta_color="normal" if completion >= 50 else "inverse",
            help="Percentage of completed issues"
        )
    
    with col3:
        wip_pct = metrics['wip_ratio'] * 100
        wip_emoji = "🟢" if wip_pct < 50 else "🟡" if wip_pct < 70 else "🔴"
        st.metric(
            label=f"{wip_emoji} Work In Progress",
            value=f"{wip_pct:.1f}%",
            delta=f"{metrics['wip']} issues active",
            help="Current workload intensity"
        )
    
    with col4:
        stale = metrics.get('stale_in_progress_count', 0)
        stale_emoji = "✨" if stale == 0 else "⚠️"
        st.metric(
            label=f"{stale_emoji} Stale Issues",
            value=stale,
            delta=f"-{stale} need attention" if stale > 0 else "All fresh!",
            delta_color="inverse" if stale > 0 else "normal",
            help="Issues without recent updates"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== AI ANALYSIS SECTION =====
    st.markdown('<h2 class="section-header">🤖 AI Risk Analysis</h2>', unsafe_allow_html=True)
    show_ai_analysis(rules)
    
    # ===== EXPORT SECTION WITH STYLED BUTTONS =====
    st.markdown('<h2 class="section-header">📥 Export & Reports</h2>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Export CSV",
            data=csv,
            file_name=f"jira_report_{project_key}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Download raw data in CSV format"
        )
    
    with col2:
        report_data = {
            "project": project_key,
            "generated_at": datetime.now().isoformat(),
            "analysis_period_days": days_back,
            "project_health": project_health,
            "metrics": metrics,
            "rules": rules,
            "issues": df.to_dict('records')
        }
        json_str = json.dumps(report_data, indent=2, default=str)
        st.download_button(
            label="📊 Export JSON",
            data=json_str,
            file_name=f"ai_report_{project_key}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True,
            help="Download complete analysis report"
        )
    
    with col3:
        def generate_pdf():
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            title = Paragraph(f"<b>AI Project Intelligence Report</b><br/>{project_key}", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 20))
            
            story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            story.append(Paragraph(f"<b>Analysis Period:</b> Last {days_back} days", styles['Normal']))
            story.append(Paragraph(f"<b>Project Health:</b> {project_health}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            story.append(Paragraph("<b>Key Metrics:</b>", styles['Heading2']))
            story.append(Paragraph(f"• Total Issues: {metrics['total']}", styles['Normal']))
            story.append(Paragraph(f"• Completion Rate: {completion:.1f}%", styles['Normal']))
            story.append(Paragraph(f"• Work in Progress: {metrics['wip']} ({wip_pct:.1f}%)", styles['Normal']))
            story.append(Paragraph(f"• Stale Issues: {stale}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            if rules.get('risks'):
                story.append(Paragraph("<b>Identified Risks:</b>", styles['Heading2']))
                for risk in rules['risks']:
                    story.append(Paragraph(f"• {risk}", styles['Normal']))
                story.append(Spacer(1, 20))
            
            if rules.get('actions'):
                story.append(Paragraph("<b>Recommended Actions:</b>", styles['Heading2']))
                for action in rules['actions']:
                    story.append(Paragraph(f"• {action}", styles['Normal']))
            
            doc.build(story)
            buffer.seek(0)
            return buffer
        
        pdf_buffer = generate_pdf()
        st.download_button(
            label="📑 Export PDF",
            data=pdf_buffer,
            file_name=f"ai_report_{project_key}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            help="Download professional PDF report"
        )
    
    with col4:
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Issues', index=False)
            pd.DataFrame([metrics]).to_excel(writer, sheet_name='Metrics', index=False)
        excel_buffer.seek(0)
        
        st.download_button(
            label="📊 Export Excel",
            data=excel_buffer,
            file_name=f"jira_report_{project_key}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Download data in Excel format"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===== TEAM ACTIVITY HEATMAP =====
    st.markdown('<h2 class="section-header">🔥 Team Activity Heatmap</h2>', unsafe_allow_html=True)
    
    df['date'] = pd.to_datetime(df['updated_at']).dt.date
    df['assignee_clean'] = df['assignee'].fillna('🔹 Unassigned')
    
    heatmap_data = df.groupby(['assignee_clean', 'date']).size().reset_index(name='activity')
    pivot = heatmap_data.pivot(index='assignee_clean', columns='date', values='activity').fillna(0)
    
    if not pivot.empty:
        fig_heatmap = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[str(d) for d in pivot.columns],
            y=pivot.index,
            colorscale='RdYlGn',
            text=pivot.values,
            texttemplate="%{text}",
            textfont={"size": 10},
            colorbar=dict(title="Updates", thickness=15)
        ))
        
        fig_heatmap.update_layout(
            title={
                'text': "Daily Activity by Team Member",
                'font': {'size': 18, 'color': '#2c3e50'}
            },
            xaxis_title="Date",
            yaxis_title="Team Member",
            height=300 + (len(pivot.index) * 30),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.info("ℹ️ Not enough activity data to display heatmap")
    
    # ===== CHARTS ROW =====
    st.markdown('<h2 class="section-header">📈 Analytics Dashboard</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Status Distribution")
        status_counts = df['status_name'].value_counts()
        fig1 = go.Figure(data=[go.Bar(
            x=status_counts.index,
            y=status_counts.values,
            marker=dict(
                color=status_counts.values,
                colorscale='Viridis',
                showscale=False
            ),
            text=status_counts.values,
            textposition='auto',
        )])
        fig1.update_layout(
            showlegend=False,
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(title="Status"),
            yaxis=dict(title="Count")
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("#### 👥 Workload Distribution")
        df["assignee_display"] = df["assignee"].fillna("🔹 Unassigned")
        assignee_counts = df["assignee_display"].value_counts()
        fig2 = go.Figure(data=[go.Pie(
            labels=assignee_counts.index,
            values=assignee_counts.values,
            hole=.4,
            marker=dict(colors=px.colors.qualitative.Set3)
        )])
        fig2.update_layout(
            showlegend=True,
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # ===== ACTIVITY TIMELINE =====
    st.markdown("#### 📅 Activity Timeline")
    timeline = df.groupby("date").size().reset_index(name="count")
    
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=timeline["date"],
        y=timeline["count"],
        mode='lines+markers',
        name='Updates',
        line=dict(color='#667eea', width=3),
        marker=dict(size=8, color='#764ba2'),
        fill='tozeroy',
        fillcolor='rgba(102, 126, 234, 0.1)'
    ))
    fig3.update_layout(
        title={
            'text': "Daily Update Activity",
            'font': {'size': 18, 'color': '#2c3e50'}
        },
        xaxis_title="Date",
        yaxis_title="Number of Updates",
        height=350,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified'
    )
    st.plotly_chart(fig3, use_container_width=True)
    
    # ===== PROJECT SNAPSHOTS =====
    st.markdown('<h2 class="section-header">📸 Project Snapshots</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("💾 Save Snapshot", use_container_width=True, type="primary"):
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "project": project_key,
                "health": project_health,
                "metrics": metrics,
                "rules": rules
            }
            
            if 'snapshots' not in st.session_state:
                st.session_state.snapshots = []
            st.session_state.snapshots.append(snapshot)
            st.success("✅ Snapshot saved successfully!")
    
    if 'snapshots' in st.session_state and st.session_state.snapshots:
        st.markdown("#### 📊 Snapshot History")
        
        snapshot_df = pd.DataFrame([
            {
                "📅 Date": s['timestamp'][:19],
                "🎯 Health": s['health'],
                "📈 Issues": s['metrics']['total'],
                "🔄 WIP": s['metrics']['wip'],
                "📊 WIP %": f"{s['metrics']['wip_ratio']:.1%}",
                "⚠️ Risks": len(s['rules']['risks'])
            }
            for s in st.session_state.snapshots
        ])
        
        st.dataframe(snapshot_df, use_container_width=True, hide_index=True)
        
        # Health trend
        health_map = {"HEALTHY": 1, "WATCH": 2, "AT_RISK": 3}
        snapshot_df['health_score'] = snapshot_df['🎯 Health'].map(health_map)
        
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=snapshot_df['📅 Date'],
            y=snapshot_df['health_score'],
            mode='lines+markers',
            name='Health Trend',
            line=dict(color='#667eea', width=3),
            marker=dict(size=12, color='#764ba2')
        ))
        fig_trend.update_layout(
            title="Project Health Trend Over Time",
            xaxis_title="Date",
            yaxis=dict(
                tickmode='array',
                tickvals=[1, 2, 3],
                ticktext=['🟢 HEALTHY', '🟡 WATCH', '🔴 AT_RISK'],
                title="Health Status"
            ),
            height=350,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    
    # ===== ISSUE DETAILS TABLE =====
    st.markdown('<h2 class="section-header">📋 Issue Details</h2>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 2, 6])
    
    with col1:
        status_filter = st.selectbox(
            "🔍 Filter by Status",
            ["All Statuses"] + list(df["status_name"].unique())
        )
    
    with col2:
        sort_by = st.selectbox(
            "📊 Sort by",
            ["Days Since Update", "Status", "Assignee"]
        )
    
    # Apply filters
    if status_filter == "All Statuses":
        filtered_df = df
    else:
        filtered_df = df[df["status_name"] == status_filter]
    
    # Apply sorting
    if sort_by == "Days Since Update":
        filtered_df = filtered_df.sort_values('days_since_update', ascending=False)
    elif sort_by == "Status":
        filtered_df = filtered_df.sort_values('status_name')
    else:
        filtered_df = filtered_df.sort_values('assignee')
    
    # Display table with better formatting
    display_df = filtered_df[['key', 'summary', 'status_name', 'assignee', 'days_since_update']].copy()
    display_df.columns = ['🔑 Key', '📝 Summary', '📊 Status', '👤 Assignee', '⏰ Days Inactive']
    display_df['👤 Assignee'] = display_df['👤 Assignee'].fillna('🔹 Unassigned')
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    st.info(f"📊 Showing **{len(filtered_df)}** of **{len(df)}** total issues")

else:
    st.error("⚠️ **No Data Found**")
    st.info("""
        **Possible reasons:**
        - Invalid project key
        - No issues in the selected date range
        - Connection issues with Jira
        
        **Try:**
        - Checking your project key
        - Expanding the date range
        - Refreshing the dashboard
    """)

# ===== FOOTER =====
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6c757d; padding: 2rem;'>
    <p><strong>AI Project Intelligence Dashboard</strong> v2.0</p>
    <p>Powered by LangChain 🦜 • Ollama 🦙 • Streamlit ⚡</p>
    <p>© 2026 NTT DATA • Built by AI Agent Project Tracking Team</p>
</div>
""", unsafe_allow_html=True)