import awswrangler as wr
import boto3
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="SW London Property Market",
    page_icon="🏠",
    layout="wide",
)

# ---------------------------------------------------------------------------
# AWS session — credentials from st.secrets
# ---------------------------------------------------------------------------

session = boto3.Session(
    aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
    aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
    region_name="us-east-1",
)

S3_BUCKET = st.secrets["aws"]["s3_bucket"]
ATHENA_OUTPUT = f"s3://{S3_BUCKET}/athena-results/"
DATABASE = "property_data"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_current_properties():
    return wr.athena.read_sql_query(
        "SELECT * FROM gold_current_properties",
        database=DATABASE,
        s3_output=ATHENA_OUTPUT,
        boto3_session=session,
    )


@st.cache_data(ttl=3600)
def load_property_fact():
    return wr.athena.read_sql_query(
        "SELECT * FROM gold_property_fact",
        database=DATABASE,
        s3_output=ATHENA_OUTPUT,
        boto3_session=session,
    )


@st.cache_data(ttl=3600)
def load_area_dim():
    return wr.athena.read_sql_query(
        "SELECT * FROM gold_area_dim WHERE area_code != 'all'",
        database=DATABASE,
        s3_output=ATHENA_OUTPUT,
        boto3_session=session,
    )


@st.cache_data(ttl=3600)
def load_spy_prices():
    return wr.athena.read_sql_query(
        "SELECT * FROM silver_spy_prices ORDER BY date",
        database=DATABASE,
        s3_output=ATHENA_OUTPUT,
        boto3_session=session,
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

current = load_current_properties()
fact = load_property_fact()
area_dim = load_area_dim()
spy = load_spy_prices()

last_updated = current["date"].max()

st.title("South West London Property Market")
st.caption(f"2-bed rentals from rightmove.com · Last updated: {last_updated}")

tab1, tab2 = st.tabs(["Current Market", "Trends Analysis"])

# ---------------------------------------------------------------------------
# Tab 1 — Current Market
# ---------------------------------------------------------------------------

with tab1:
    col1, col2 = st.columns(2)
    col1.metric("Properties", f"{len(current):,}")
    col2.metric("Median Price", f"£{current['price'].median():,.0f} pcm")

    st.divider()

    map_col, table_col = st.columns([2, 1])

    with map_col:
        fig_map = px.scatter_map(
            current,
            lat="latitude",
            lon="longitude",
            color="price",
            color_continuous_scale="YlOrRd",
            hover_name="address",
            hover_data={"price": ":,", "area_code": True, "latitude": False, "longitude": False},
            zoom=10,
            height=500,
        )
        fig_map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, coloraxis_colorbar_title="Price (£)")
        st.plotly_chart(fig_map, use_container_width=True)

    with table_col:
        latest_fact = fact[fact["area_code"] != "all"].copy()
        latest_fact = latest_fact.sort_values("date").groupby("area_code").last().reset_index()
        latest_fact = latest_fact.merge(area_dim, on="area_code")
        display = latest_fact[["district", "avg_price", "median_price", "num_properties"]].rename(columns={
            "district": "District",
            "avg_price": "Avg £",
            "median_price": "Median £",
            "num_properties": "Count",
        }).sort_values("Median £", ascending=False)
        st.dataframe(display, use_container_width=True, hide_index=True, height=480)

    st.divider()
    st.subheader("Price Distribution")
    fig_hist = px.histogram(
        current,
        x="price",
        nbins=40,
        labels={"price": "Price (£ pcm)", "count": "Number of Properties"},
        color_discrete_sequence=["steelblue"],
    )
    fig_hist.update_layout(bargap=0.05, showlegend=False)
    st.plotly_chart(fig_hist, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 2 — Trends Analysis
# ---------------------------------------------------------------------------

with tab2:
    st.subheader("Average Price Over Time")

    area_options = sorted(fact[fact["area_code"] != "all"]["area_code"].unique())
    selected_areas = st.multiselect(
        "Area codes",
        options=area_options,
        default=area_options[:5],
    )

    filtered_fact = fact[fact["area_code"].isin(selected_areas)]
    fig_trend = px.line(
        filtered_fact.sort_values("date"),
        x="date",
        y="avg_price",
        color="area_code",
        labels={"date": "Date", "avg_price": "Avg Price (£ pcm)", "area_code": "Area"},
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    st.divider()
    st.subheader("Financial Indicators")

    spy_col, _ = st.columns([1, 1])
    with spy_col:
        st.caption("SPDR S&P 500 ETF (SPY)")
        fig_spy = px.line(
            spy,
            x="date",
            y="close",
            labels={"date": "Date", "close": "Close Price (USD)"},
            color_discrete_sequence=["steelblue"],
        )
        st.plotly_chart(fig_spy, use_container_width=True)
