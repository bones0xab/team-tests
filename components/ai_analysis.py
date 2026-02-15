import streamlit as st

def show_ai_analysis(rules: dict):
    """Display AI-powered risk analysis with professional styling"""
    
    # Health Status with cleaner design
    health = rules.get("project_health", "UNKNOWN")
    
    # Professional color scheme (not generic AI colors)
    color_config = {
        "HEALTHY": {
            "emoji": "✓",
            "bg": "#f0f9f4",
            "border": "#10b981",
            "text": "#047857",
            "badge": "#10b981"
        },
        "WATCH": {
            "emoji": "!",
            "bg": "#fffbeb",
            "border": "#f59e0b",
            "text": "#b45309",
            "badge": "#f59e0b"
        },
        "AT_RISK": {
            "emoji": "×",
            "bg": "#fef2f2",
            "border": "#ef4444",
            "text": "#b91c1c",
            "badge": "#ef4444"
        }
    }
    
    config = color_config.get(health, color_config["HEALTHY"])
    
    # Compact header (no "AI Risk Analysis" title)
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Minimalist health badge
        st.markdown(
            f"""
            <div style='
                background: {config["bg"]};
                border: 2px solid {config["border"]};
                border-radius: 8px;
                padding: 20px;
                text-align: center;
            '>
                <div style='
                    font-size: 2.5em;
                    color: {config["text"]};
                    font-weight: 600;
                    margin-bottom: 8px;
                '>{config["emoji"]}</div>
                <div style='
                    font-size: 1.1em;
                    color: {config["text"]};
                    font-weight: 600;
                    letter-spacing: 0.5px;
                '>{health.replace("_", " ")}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        # Show rules that triggered (technical view)
        proof = rules.get("proof", [])
        if proof:
            st.markdown("**Analysis Breakdown:**")
            for p in proof:
                rule = p.get("rule", "").replace("_", " ").title()
                signal = p.get("signal", "")
                value = p.get("value", 0)
                threshold = p.get("threshold", 0)
                
                if isinstance(value, float) and value < 10:
                    metric_text = f"{signal}: **{value:.0%}** (threshold: {threshold:.0%})"
                else:
                    metric_text = f"{signal}: **{value}** (threshold: {threshold})"
                
                severity_emoji = "🔴" if p.get("severity") == "risk" else "🟡"
                st.caption(f"{severity_emoji} {rule} — {metric_text}")
        else:
            st.success("All metrics within normal ranges")
    
    # Risks & Actions (compact, no headers)
    risks = rules.get("risks", [])
    actions = rules.get("actions", [])
    
    if risks or actions:
        st.markdown("---")  # Subtle divider
        
        col1, col2 = st.columns(2)
        
        with col1:
            if risks:
                st.markdown("**⚠️ Identified Issues**")
                for risk in risks:
                    st.warning(risk, icon="⚠️")
        
        with col2:
            if actions:
                st.markdown("**💡 Recommendations**")
                for action in actions:
                    st.info(action, icon="💡")