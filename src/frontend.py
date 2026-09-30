import asyncio
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scrapper import scrape

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Book Scraper Dashboard",
    page_icon="📚",
    layout="wide",
)

st.title("📚 Book Scraper Dashboard")
st.caption("Scrapes the top N books from books.toscrape.com and visualises the results.")

PRODUCTS_PATH = Path(__file__).parent / "products.json"

# ── Sidebar controls ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
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

# ── State ──────────────────────────────────────────────────────────────────────
if "products" not in st.session_state:
    st.session_state.products = None

# ── Run scraper ────────────────────────────────────────────────────────────────
if run_scraper:
    with st.spinner(f"Scraping {target_count} books… this may take a minute."):
        try:
            products = asyncio.run(scrape(limit=target_count))
            # Persist to disk
            with open(PRODUCTS_PATH, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            st.session_state.products = products
            st.success(f"✅ Scraped {len(products)} books successfully!")
        except Exception as e:
            st.error(f"Scraper failed: {e}")

# ── Load from disk ─────────────────────────────────────────────────────────────
if load_existing:
    if PRODUCTS_PATH.exists():
        with open(PRODUCTS_PATH, encoding="utf-8") as f:
            st.session_state.products = json.load(f)
        st.success(f"✅ Loaded {len(st.session_state.products)} books from saved results.")
    else:
        st.warning("No saved results found. Run the scraper first.")

# ── Dashboard ──────────────────────────────────────────────────────────────────
products = st.session_state.products

if products:
    df = pd.DataFrame(products)

    # Clean price column: strip currency symbol and convert to float
    df["price_clean"] = (
        df["price"]
        .str.replace(r"[^\d.]", "", regex=True)
        .pipe(pd.to_numeric, errors="coerce")
    )

    # Drop rows where we couldn't parse price or rating
    df_valid = df.dropna(subset=["price_clean", "rating"]).copy()
    df_valid["rating"] = df_valid["rating"].astype(int)

    # ── Metrics row ───────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total books", len(df))
    col2.metric("Avg price", f"£{df_valid['price_clean'].mean():.2f}" if not df_valid.empty else "—")
    col3.metric("Avg rating", f"{df_valid['rating'].mean():.1f} / 5" if not df_valid.empty else "—")
    col4.metric("Books with full data", len(df_valid))

    st.divider()

    # ── Charts ────────────────────────────────────────────────────────────────
    chart_col1, chart_col2 = st.columns(2)

    # Chart 1: Price vs Rating (scatter)
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

    # Chart 2: Distribution of books by rating (pie / donut)
    with chart_col2:
        st.subheader("⭐ Books by Rating")
        if df_valid.empty:
            st.info("No rating data available.")
        else:
            rating_counts = (
                df_valid.groupby("rating")
                .size()
                .reset_index(name="count")
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
                hovertemplate="<b>%{label}</b><br>Books: %{value}<br>Share: %{customdata[0]:.1f}%<extra></extra>",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # ── Data table ────────────────────────────────────────────────────────────
    st.subheader("📋 Raw Data")

    # Render star symbols for display
    display_df = df[["name", "price", "rating"]].copy()
    display_df["rating"] = display_df["rating"].apply(
        lambda r: ("★" * int(r) + "☆" * (5 - int(r))) if pd.notna(r) else "—"
    )
    display_df.columns = ["Title", "Price", "Rating"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("👈 Use the sidebar to run the scraper or load previously saved results.")
