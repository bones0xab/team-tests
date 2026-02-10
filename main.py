import streamlit as st
import pandas as pd
import plotly.express as px
from services.Fetch import search_issues
from services.Normalisation import normalize_issue

st.set_page_config(page_title="AI Agent Dashboard", layout="wide")
st.title("AI Agent – Jira DevOps Dashboard")

# Query Jira
jql = "created >= -30 AND status != Done"
fields = ["summary", "status", "assignee", "updated"]

issues = search_issues(jql, fields)
data = [normalize_issue(i) for i in issues]

if data:
    df = pd.DataFrame(data)

    # ===== TABLE =====
    st.subheader("Tickets Overview")
    st.dataframe(df, use_container_width=True)

    # ===== FILTER =====
    status_filter = st.selectbox("Filter by status", df["status_name"].unique())
    filtered_df = df[df["status_name"] == status_filter]
    st.dataframe(filtered_df, use_container_width=True)

    # ===== GRAPH STATUS =====
    fig1 = px.bar(
        df,
        x="status_name",
        title="Tickets by Status",
        color="status_name",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    st.plotly_chart(fig1, use_container_width=True)

    # ===== GRAPH ASSIGNEE =====
    df["assignee"] = df["assignee"].fillna("Unassigned")
    fig2 = px.pie(
        df,
        names="assignee",
        title="Tickets Distribution by Assignee"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ===== TIMELINE =====
    df["date"] = pd.to_datetime(df["updated_at"]).dt.date
    timeline = df.groupby("date").size().reset_index(name="count")

    fig3 = px.line(
        timeline,
        x="date",
        y="count",
        markers=True,
        title="Activity Timeline"
    )
    st.plotly_chart(fig3, use_container_width=True)

else:
    st.warning("No Jira data found.")
