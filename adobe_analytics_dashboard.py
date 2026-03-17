"""
Adobe Analytics BigLake Dashboard powered by Claude AI
Ask natural language questions — Claude generates SQL, queries BigLake, and visualizes results.
"""

from __future__ import annotations

import json
import os
import anthropic
import pandas as pd
import plotly.express as px
import streamlit as st
from google.cloud import bigquery

# ── Config ────────────────────────────────────────────────────────────────────
BIGQUERY_PROJECT = os.environ.get("BIGQUERY_PROJECT", "your-gcp-project")
BIGQUERY_DATASET = os.environ.get("BIGQUERY_DATASET", "your_dataset")
BIGQUERY_TABLE   = os.environ.get("BIGQUERY_TABLE",   "adobe_hits")

FULL_TABLE_ID = f"`{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`"

# dotcom_web_data schema (mapped from sample row inspection)
TABLE_SCHEMA = """
Table: {table}

Key columns (dotcom_web_data — Solidigm Adobe Analytics):
  - string_field_42     STRING    Hit datetime (e.g. '2026-01-05 00:48:33')
  - string_field_47     STRING    Page name / title (e.g. 'solidigm d5-p5316 product brief')
  - string_field_48     STRING    Page URL (full URL of the page visited)
  - string_field_49     STRING    Referrer URL (where the visitor came from)
  - string_field_50     STRING    Referrer domain (e.g. 'google.com')
  - string_field_43     STRING    Referrer domain alternate
  - string_field_53     STRING    City (e.g. 'beijing')
  - string_field_54     STRING    Country code (e.g. 'chn', 'usa')
  - string_field_56     STRING    Region/state code
  - int64_field_51      INTEGER   Visit number
  - int64_field_52      INTEGER   Visitor ID high
  - int64_field_60      INTEGER   Page view count indicator (1 = page view)
  - int64_field_61      INTEGER   Hit timestamp (Unix epoch seconds)
  - int64_field_70      INTEGER   First hit timestamp (Unix epoch seconds)
  - int64_field_67      INTEGER   Visit page number
  - string_field_149    STRING    User agent (browser/OS string)
  - string_field_107    STRING    Site section / eVar
  - string_field_109    STRING    Site entry page URL
  - string_field_45     STRING    Event list (comma-separated event IDs)
  - int64_field_112     INTEGER   Browser window height (px)
  - int64_field_113     INTEGER   Browser window width (px)
  - string_field_161    STRING    Post page name
  - string_field_162    STRING    Post page URL
  - string_field_126    STRING    Post site section
  - string_field_139    STRING    Post referrer URL
  - string_field_140    STRING    Post referrer domain

Important query rules:
  1. Use TIMESTAMP_SECONDS(int64_field_61) to convert hit timestamps to readable dates
  2. Count unique visitors with COUNT(DISTINCT int64_field_52)
  3. Count page views with COUNT(*) or SUM(int64_field_60)
  4. Filter by date: DATE(TIMESTAMP_SECONDS(int64_field_61)) = '2026-01-05'
  5. For date ranges: DATE(TIMESTAMP_SECONDS(int64_field_61)) BETWEEN '2026-01-01' AND '2026-01-31'
  6. Page name is string_field_47, Page URL is string_field_48
  7. Country is string_field_54, City is string_field_53
  8. Referrer domain is string_field_50
""".format(table=FULL_TABLE_ID)

SYSTEM_PROMPT = f"""You are an expert Adobe Analytics and BigQuery SQL analyst.
You help users query an Adobe Analytics Data Feed stored in a GCP BigLake table.

{TABLE_SCHEMA}

When given a question:
1. Call the run_bigquery_sql tool with a valid BigQuery SQL query
2. After receiving results, provide a clear interpretation
3. Suggest what chart type best visualizes the data (bar, line, pie, scatter, table)

Always write efficient SQL — use LIMIT 1000 unless the user asks for aggregates only.
"""

# ── BigQuery client ───────────────────────────────────────────────────────────
@st.cache_resource
def get_bq_client():
    return bigquery.Client(project=BIGQUERY_PROJECT)


def run_bigquery_sql(sql: str) -> dict:
    """Execute SQL against BigLake and return results as a dict."""
    try:
        client = get_bq_client()
        df = client.query(sql).to_dataframe()
        return {
            "success": True,
            "row_count": len(df),
            "columns": list(df.columns),
            "data": df.head(500).to_dict(orient="records"),  # cap at 500 rows for Claude context
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Tool definition ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "run_bigquery_sql",
        "description": (
            "Execute a BigQuery SQL query against the Adobe Analytics BigLake table "
            "and return the results. Use this to answer user questions about web analytics data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Valid BigQuery SQL query to execute",
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie", "scatter", "area", "table"],
                    "description": "Recommended chart type to visualize the results",
                },
                "x_column": {
                    "type": "string",
                    "description": "Column name to use for the X axis (or labels for pie)",
                },
                "y_column": {
                    "type": "string",
                    "description": "Column name to use for the Y axis (or values for pie)",
                },
            },
            "required": ["sql", "chart_type"],
        },
    }
]


# ── Claude agentic loop ───────────────────────────────────────────────────────
def ask_claude(question: str, history: list[dict]) -> tuple[str, pd.DataFrame | None, dict | None]:
    """
    Send a question to Claude with tool use.
    Returns: (answer_text, dataframe_or_None, chart_config_or_None)
    """
    client = anthropic.Anthropic()

    messages = history + [{"role": "user", "content": question}]
    df_result = None
    chart_config = None

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Collect text blocks
        text_parts = [b.text for b in response.content if b.type == "text"]

        if response.stop_reason == "end_turn":
            return "\n".join(text_parts), df_result, chart_config

        if response.stop_reason != "tool_use":
            return "\n".join(text_parts) or "No response.", df_result, chart_config

        # Handle tool calls
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_input = block.input

            if block.name == "run_bigquery_sql":
                sql = tool_input["sql"]
                chart_config = {
                    "chart_type": tool_input.get("chart_type", "table"),
                    "x_column":   tool_input.get("x_column"),
                    "y_column":   tool_input.get("y_column"),
                    "sql":        sql,
                }

                with st.spinner(f"Running query…\n```sql\n{sql}\n```"):
                    result = run_bigquery_sql(sql)

                if result["success"] and result["data"]:
                    df_result = pd.DataFrame(result["data"])
                    tool_content = json.dumps({
                        "row_count": result["row_count"],
                        "columns": result["columns"],
                        "sample_data": result["data"][:20],  # first 20 rows for Claude
                    })
                else:
                    tool_content = json.dumps(result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_content,
                })

        messages.append({"role": "user", "content": tool_results})


# ── Chart rendering ───────────────────────────────────────────────────────────
def render_chart(df: pd.DataFrame, config: dict):
    chart_type = config.get("chart_type", "table")
    x = config.get("x_column")
    y = config.get("y_column")

    # Auto-detect columns if not specified
    if not x and len(df.columns) >= 1:
        x = df.columns[0]
    if not y and len(df.columns) >= 2:
        y = df.columns[1]

    try:
        if chart_type == "bar" and x and y:
            fig = px.bar(df, x=x, y=y, title=f"{y} by {x}")
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "line" and x and y:
            fig = px.line(df, x=x, y=y, title=f"{y} over {x}")
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "area" and x and y:
            fig = px.area(df, x=x, y=y, title=f"{y} over {x}")
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "pie" and x and y:
            fig = px.pie(df, names=x, values=y, title=f"{y} distribution")
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "scatter" and x and y:
            fig = px.scatter(df, x=x, y=y, title=f"{x} vs {y}")
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.warning(f"Could not render chart ({e}), showing table instead.")
        st.dataframe(df, use_container_width=True)


# ── Streamlit UI ──────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Adobe Analytics Dashboard",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 Adobe Analytics Dashboard")
    st.caption(f"Powered by Claude AI · BigLake: `{FULL_TABLE_ID}`")

    # Sidebar config
    with st.sidebar:
        st.header("Configuration")
        st.text_input("GCP Project",  value=BIGQUERY_PROJECT, key="project",  disabled=True)
        st.text_input("Dataset",      value=BIGQUERY_DATASET, key="dataset",  disabled=True)
        st.text_input("Table",        value=BIGQUERY_TABLE,   key="table",    disabled=True)

        st.divider()
        st.subheader("Example questions")
        examples = [
            "Show me daily page views for the last 30 days",
            "What are the top 10 most visited pages?",
            "Show unique visitors by country",
            "What is the bounce rate trend this month?",
            "Compare mobile vs desktop traffic",
            "Top 5 referrer domains this week",
        ]
        for q in examples:
            if st.button(q, key=q, use_container_width=True):
                st.session_state["pending_question"] = q

        if st.button("Clear chat", type="secondary", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state["chat_history"] = []
            st.rerun()

    # Session state init
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Replay chat
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "df" in msg and msg["df"] is not None:
                render_chart(msg["df"], msg.get("chart_config", {}))
                with st.expander("View raw data"):
                    st.dataframe(msg["df"], use_container_width=True)
            if "sql" in msg:
                with st.expander("View SQL"):
                    st.code(msg["sql"], language="sql")

    # Handle question (from input box or sidebar button)
    question = st.chat_input("Ask anything about your Adobe Analytics data…")
    if "pending_question" in st.session_state:
        question = st.session_state.pop("pending_question")

    if question:
        # Show user message
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state["messages"].append({"role": "user", "content": question})

        # Get Claude response
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                answer, df, chart_config = ask_claude(
                    question,
                    st.session_state["chat_history"],
                )

            st.markdown(answer)

            if df is not None and not df.empty:
                render_chart(df, chart_config or {})
                with st.expander("View raw data"):
                    st.dataframe(df, use_container_width=True)

            if chart_config and "sql" in chart_config:
                with st.expander("View SQL"):
                    st.code(chart_config["sql"], language="sql")

        # Persist
        st.session_state["messages"].append({
            "role": "assistant",
            "content": answer,
            "df": df,
            "chart_config": chart_config,
            "sql": chart_config.get("sql") if chart_config else None,
        })

        # Update Claude conversation history (without DataFrames)
        st.session_state["chat_history"].append({"role": "user", "content": question})
        st.session_state["chat_history"].append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
