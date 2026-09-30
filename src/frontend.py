import asyncio
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scrapper import scrape
from agent import parse_question, answer_question

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Book Scraper Dashboard",
    page_icon="📚",
    layout="wide",
)

st.title("📚 Book Scraper Dashboard")

PRODUCTS_PATH = Path(__file__).parent / "products.json"

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_ask, tab_dashboard = st.tabs(["🤖 Ask a Question", "📊 Dashboard"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Natural Language Query
# ══════════════════════════════════════════════════════════════════════════════
with tab_ask:
    st.subheader("Ask anything about the books")
    st.caption(
        "Type a plain English question. The AI will figure out what data to scrape, "
        "fetch it, and answer your question."
    )

    example_questions = [
        "What is the average price of 5-star rated books?",
        "Which books cost less than £20?",
        "List the top 10 highest-rated books.",
        "What is the cheapest book available?",
        "Show me all books with a rating of 4 or 5 stars.",
    ]

    with st.expander("💡 Example questions"):
        for q in example_questions:
            st.markdown(f"- {q}")

    question = st.text_input(
        "Your question",
        placeholder="e.g. What are the most expensive books with a 5-star rating?",
        key="nl_question",
    )

    ask_col, clear_col = st.columns([3, 1])
    with ask_col:
        ask_btn = st.button("🔍 Ask", use_container_width=True, type="primary")
    with clear_col:
        if st.button("🗑️ Clear", use_container_width=True):
            for key in ("nl_answer", "nl_data", "nl_plan"):
                st.session_state.pop(key, None)
            st.rerun()

    # ── Run the agentic pipeline ───────────────────────────────────────────────
    if ask_btn and question.strip():

        # Step 1 — Parse question into a scraping plan
        plan_box   = st.empty()
        status_box = st.empty()

        with plan_box.status("🧠 Thinking about what to scrape…", expanded=True) as status:
            try:
                plan = parse_question(question)
                st.session_state["nl_plan"] = plan
                status.update(
                    label=f"✅ Plan ready — fields: {plan['fields']}, books: {plan['limit']}",
                    state="complete",
                    expanded=False,
                )
            except Exception as e:
                st.error(f"Agent failed to parse question: {e}")
                st.stop()

        # Step 2 — Scrape
        with status_box.status(
            f"🌐 Scraping {plan['limit']} books for: {', '.join(plan['fields'])}…",
            expanded=False,
        ) as scrape_status:
            try:
                data = asyncio.run(scrape(limit=plan["limit"], fields=plan["fields"]))
                st.session_state["nl_data"] = data
                scrape_status.update(
                    label=f"✅ Scraped {len(data)} books",
                    state="complete",
                    expanded=False,
                )
            except Exception as e:
                st.error(f"Scraper failed: {e}")
                st.stop()

        # Step 3 — Stream answer
        answer_placeholder = st.empty()
        full_answer = ""
        with st.spinner("💬 Generating answer…"):
            try:
                for chunk in answer_question(question, data):
                    full_answer += chunk
                    answer_placeholder.markdown(full_answer + "▌")
                answer_placeholder.markdown(full_answer)
                st.session_state["nl_answer"] = full_answer
            except Exception as e:
                st.error(f"Agent failed to answer: {e}")

    # ── Display cached results (after rerun) ──────────────────────────────────
    elif "nl_answer" in st.session_state:
        plan = st.session_state.get("nl_plan", {})
        if plan:
            st.info(
                f"🧠 Scraped **{plan['limit']}** books | "
                f"Fields: **{', '.join(plan['fields'])}** | "
                f"Reasoning: _{plan.get('reasoning', '')}_ "
            )

        st.markdown("### 💬 Answer")
        st.markdown(st.session_state["nl_answer"])

        data = st.session_state.get("nl_data", [])
        if data:
            with st.expander(f"📋 Raw scraped data ({len(data)} books)"):
                st.dataframe(
                    pd.DataFrame(data),
                    use_container_width=True,
                    hide_index=True,
                )

    elif ask_btn and not question.strip():
        st.warning("Please enter a question first.")

    else:
        st.info("Enter a question above and click **Ask** to get started.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Classic Dashboard
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    st.caption("Scrapes the top N books from books.toscrape.com and visualises the results.")

    # Sidebar controls (only relevant for dashboard tab)
    with st.sidebar:
        st.header("⚙️ Dashboard Settings")
        target_count = st.number_input(
            "Number of books to scrape",
            min_value=5,
            max_value=200,
            value=30,
            step=5,
        )
        run_scraper = st.button("🚀 Run Scraper", use_container_width=True)
        st.divider()
        load_existing = st.button("📂 Load saved results", use_container_width=True)

    # ── State ─────────────────────────────────────────────────────────────────
    if "products" not in st.session_state:
        st.session_state.products = None

    # ── Run scraper ───────────────────────────────────────────────────────────
    if run_scraper:
        with st.spinner(f"Scraping {target_count} books… this may take a minute."):
            try:
                products = asyncio.run(scrape(limit=target_count))
                with open(PRODUCTS_PATH, "w", encoding="utf-8") as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)
                st.session_state.products = products
                st.success(f"✅ Scraped {len(products)} books successfully!")
            except Exception as e:
                st.error(f"Scraper failed: {e}")

    # ── Load from disk ────────────────────────────────────────────────────────
    if load_existing:
        if PRODUCTS_PATH.exists():
            with open(PRODUCTS_PATH, encoding="utf-8") as f:
                st.session_state.products = json.load(f)
            st.success(
                f"✅ Loaded {len(st.session_state.products)} books from saved results."
            )
        else:
            st.warning("No saved results found. Run the scraper first.")

    # ── Dashboard ─────────────────────────────────────────────────────────────
    products = st.session_state.products

    if products:
        df = pd.DataFrame(products)

        df["price_clean"] = (
            df["price"]
            .str.replace(r"[^\d.]", "", regex=True)
            .pipe(pd.to_numeric, errors="coerce")
        )

        df_valid = df.dropna(subset=["price_clean", "rating"]).copy()
        df_valid["rating"] = df_valid["rating"].astype(int)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total books", len(df))
        col2.metric(
            "Avg price",
            f"£{df_valid['price_clean'].mean():.2f}" if not df_valid.empty else "—",
        )
        col3.metric(
            "Avg rating",
            f"{df_valid['rating'].mean():.1f} / 5" if not df_valid.empty else "—",
        )
        col4.metric("Books with full data", len(df_valid))

        st.divider()

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("💰 Price vs Rating")
            if df_valid.empty:
                st.info("No data with both price and rating available.")
            else:
                fig_scatter = px.scatter(
                    df_valid,
                    x="rating",
                    y="price_clean",
                    hover_name="name",
                    labels={"rating": "Star Rating", "price_clean": "Price (£)"},
                    color="rating",
                    color_continuous_scale="Viridis",
                    size_max=12,
                )
                fig_scatter.update_traces(marker=dict(size=10, opacity=0.8))
                fig_scatter.update_layout(
                    xaxis=dict(tickmode="linear", tick0=1, dtick=1),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

        with chart_col2:
            st.subheader("⭐ Books by Rating")
            if df_valid.empty:
                st.info("No rating data available.")
            else:
                rating_counts = (
                    df_valid.groupby("rating").size().reset_index(name="count")
                )
                rating_counts["label"] = rating_counts["rating"].apply(
                    lambda r: f"{'★' * r}{'☆' * (5 - r)}  ({r}/5)"
                )
                rating_counts["percentage"] = (
                    rating_counts["count"] / rating_counts["count"].sum() * 100
                ).round(1)

                fig_pie = px.pie(
                    rating_counts,
                    names="label",
                    values="count",
                    hole=0.45,
                    color_discrete_sequence=px.colors.sequential.Viridis_r,
                    custom_data=["percentage"],
                )
                fig_pie.update_traces(
                    textposition="outside",
                    textinfo="label+percent",
                    hovertemplate=(
                        "<b>%{label}</b><br>"
                        "Books: %{value}<br>"
                        "Share: %{customdata[0]:.1f}%<extra></extra>"
                    ),
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        st.subheader("📋 Raw Data")
        display_df = df[["name", "price", "rating"]].copy()
        display_df["rating"] = display_df["rating"].apply(
            lambda r: ("★" * int(r) + "☆" * (5 - int(r))) if pd.notna(r) else "—"
        )
        display_df.columns = ["Title", "Price", "Rating"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    else:
        st.info("👈 Use the sidebar to run the scraper or load previously saved results.")
