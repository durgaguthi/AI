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

# WEBSITE_STATS schema — Solidigm Adobe Analytics (3 months: Jan-Mar 2026)
TABLE_SCHEMA = """
Table: {table}
Data range: 2026-01-01 to 2026-03-26 | Total rows: ~1.8 million

Key columns:

-- TIME --
  - date_time           STRING    Hit datetime with timezone (e.g. '2026-03-25 19:21:30+00')
  - hit_time_gmt        STRING    Hit timestamp as Unix epoch string (cast to INT64 to use)
  - first_hit_time_gmt  STRING    First hit of visit timestamp (Unix epoch string)
  - last_hit_time_gmt   STRING    Last hit of visit timestamp (Unix epoch string)

-- PAGE --
  - pagename            STRING    Page name/title (e.g. 'd7-ps1010')
  - page_url            STRING    Full page URL
  - post_pagename       STRING    Post-processed page name (most reliable)
  - post_page_url       STRING    Post-processed page URL
  - prev_page           STRING    Previous page name
  - first_hit_pagename  STRING    First page of visit
  - first_hit_page_url  STRING    First page URL of visit
  - channel             STRING    Site channel/section
  - homepage            STRING    Homepage flag

-- VISITOR / VISIT --
  - post_visid_high     STRING    Visitor ID high (use with post_visid_low for unique visitor)
  - post_visid_low      STRING    Visitor ID low
  - mcvisid             STRING    Marketing Cloud Visitor ID
  - new_visit           STRING    '1' = new visit, '0' = return visit
  - daily_visitor       STRING    '1' = new daily visitor
  - monthly_visitor     STRING    '1' = new monthly visitor
  - hourly_visitor      STRING    '1' = new hourly visitor
  - duplicate_purchase  STRING    Duplicate purchase flag (filter = '0')
  - exclude_hit         STRING    Exclude flag (filter = '0' for valid hits)

-- GEOGRAPHY --
  - geo_city            STRING    City (e.g. 'guangzhou')
  - geo_country         STRING    Country code (e.g. 'chn', 'usa')
  - geo_region          STRING    Region/state code (e.g. 'gd', 'ca')
  - geo_zip             STRING    ZIP/postal code
  - geo_dma             STRING    DMA code
  - country             STRING    Country numeric ID
  - domain              STRING    ISP domain (e.g. 'tencent.com')

-- REFERRER / TRAFFIC SOURCE --
  - post_referrer       STRING    Referring URL
  - post_search_engine  STRING    Search engine name if organic search
  - paid_search         STRING    '1' = paid search hit
  - first_hit_referrer  STRING    First referrer of visit
  - first_hit_ref_type  STRING    Referrer type (1=URL, 2=inside, 3=news, 4=search, 6=direct)
  - first_hit_ref_domain STRING   First referrer domain

-- CAMPAIGN / MARKETING --
  - post_campaign       STRING    Full campaign string (e.g. 'direct|doit|productpage|campaign_name')
  - evar5               STRING    UTM channel (e.g. 'direct', 'organic')
  - evar6               STRING    UTM platform (e.g. 'google', 'doit')
  - evar7               STRING    UTM content (e.g. 'productpage')
  - evar9               STRING    UTM campaign name
  - evar4               STRING    Landing page URL with UTM params
  - campaign            STRING    Campaign tracking code

-- EVENTS / CONVERSIONS --
  - post_event_list     STRING    Comma-separated event IDs fired (e.g. '100,102,103')
  - event_list          STRING    Raw event list
  - page_event          STRING    Page event type (11=custom link, 101=download)

-- PRODUCT / CONTENT --
  - evar1               STRING    Product/page identifier (e.g. 'd7-ps1010')
  - post_evar1          STRING    Post-processed product identifier
  - evar11              STRING    Language (e.g. 'en', 'zh', 'de')
  - post_evar11         STRING    Post-processed language
  - evar3               STRING    Visitor ID / MCID
  - post_evar21         STRING    Date/time detail (e.g. 'year=2026 | month=March | date=25')
  - post_evar22         STRING    Visitor type ('New' or 'Return')
  - post_evar23         STRING    Visit number
  - post_evar24         STRING    Hit detail (e.g. 'first hit of visit')
  - post_evar20         STRING    Visitor IP address

-- CLICK TRACKING --
  - click_action        STRING    Clicked link URL
  - click_context       STRING    Page where click happened
  - post_clickmaplink   STRING    Clicked link text/ID
  - post_clickmapregion STRING    Page region of click (e.g. 'bodycopy2', 'header')
  - post_clickmappage   STRING    Page name of click

-- BROWSER / DEVICE --
  - browser             STRING    Browser ID
  - browser_height      STRING    Browser viewport height (px)
  - browser_width       STRING    Browser viewport width (px)
  - os                  STRING    Operating system ID
  - mobile_id           STRING    Mobile device ID ('0' = desktop)
  - connection_type     STRING    Connection type ID
  - color               STRING    Color depth
  - javascript          STRING    JavaScript version
  - java_enabled        STRING    Java enabled flag
  - accept_language     STRING    Browser language header
  - cookies             STRING    Cookies enabled flag

-- PROPS --
  - prop2 / post_prop2  STRING    Custom prop 2 (page URL truncated)
  - prop3 / post_prop3  STRING    Custom prop 3 (visitor ID)
  - prop4               STRING    Custom prop 4
  - prop5               STRING    Custom prop 5

Important query rules:
  1. Convert timestamps: TIMESTAMP_SECONDS(CAST(hit_time_gmt AS INT64))
  2. Filter date: DATE(TIMESTAMP_SECONDS(CAST(hit_time_gmt AS INT64)))
  3. Always filter valid hits: WHERE exclude_hit = '0'
  4. Count unique visitors: COUNT(DISTINCT CONCAT(post_visid_high, post_visid_low))
  5. Count visits: COUNT(DISTINCT CONCAT(post_visid_high, post_visid_low, new_visit))
  6. Count page views: COUNT(*) WHERE exclude_hit = '0' AND page_event = '0'
  7. Use post_pagename for page names (most reliable)
  8. Use post_campaign for full campaign breakdown
  9. Data range: '2026-01-01' to '2026-03-26'
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
