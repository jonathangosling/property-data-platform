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

@st.cache_data(ttl=86400)
def load_current_properties():
    return wr.athena.read_sql_query(
        "SELECT * FROM gold_current_properties",
        database=DATABASE,
        s3_output=ATHENA_OUTPUT,
        ctas_approach=False,
        boto3_session=session,
    )


@st.cache_data(ttl=86400)
def load_property_fact():
    return wr.athena.read_sql_query(
        "SELECT * FROM gold_property_fact",
        database=DATABASE,
        s3_output=ATHENA_OUTPUT,
        ctas_approach=False,
        boto3_session=session,
    )


@st.cache_data(ttl=86400)
def load_area_dim():
    return wr.athena.read_sql_query(
        "SELECT * FROM gold_area_dim WHERE area_code != 'all'",
        database=DATABASE,
        s3_output=ATHENA_OUTPUT,
        ctas_approach=False,
        boto3_session=session,
    )


@st.cache_data(ttl=86400)
def load_spy_prices():
    return wr.athena.read_sql_query(
        "SELECT * FROM silver_spy_prices ORDER BY date",
        database=DATABASE,
        s3_output=ATHENA_OUTPUT,
        ctas_approach=False,
        boto3_session=session,
    )


def sparkline(df, y):
    fig = px.line(df, x="date", y=y, color_discrete_sequence=["steelblue"])
    fig.update_layout(
        height=80,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

current = load_current_properties()
fact = load_property_fact()
area_dim = load_area_dim()
spy = load_spy_prices()

last_updated = current["date"].max()

# ---------------------------------------------------------------------------
# Build area table (used by both tabs)
# ---------------------------------------------------------------------------

latest_fact = fact[fact["area_code"] != "all"].copy()
latest_fact = latest_fact[latest_fact["date"] == latest_fact["date"].max()]
latest_fact = latest_fact.merge(area_dim, on="area_code")
display = (
    latest_fact[["area_code", "district", "avg_price", "median_price", "num_properties"]]
    .rename(columns={
        "area_code": "Area",
        "district": "District",
        "avg_price": "Avg £",
        "median_price": "Median £",
        "num_properties": "Count",
    })
    .sort_values("Median £", ascending=False)
    .reset_index(drop=True)
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("South West London Property Market")
st.caption(f"2-bed rentals from rightmove.com · Last updated: {last_updated}")

tab1, tab2 = st.tabs(["Current Market", "Trends Analysis"])

# ---------------------------------------------------------------------------
# Tab 1 — Current Market
# ---------------------------------------------------------------------------

with tab1:
    # Session state for area filter
    if "selected_areas" not in st.session_state:
        st.session_state.selected_areas = []

    selected_areas = st.session_state.selected_areas
    filtered_current = (
        current[current["area_code"].isin(selected_areas)]
        if selected_areas else current
    )

    # Metrics
    m1, m2, m3 = st.columns([1, 1, 2])
    m1.metric("Properties", f"{len(filtered_current):,}")
    m2.metric("Median Price", f"£{filtered_current['price'].median():,.0f} pcm")
    if selected_areas:
        with m3:
            st.markdown(f"**Filtered: {', '.join(selected_areas)}**")
            if st.button("Clear filter"):
                st.session_state.selected_areas = []
                st.rerun()

    st.divider()

    map_col, table_col = st.columns([2, 1])

    with map_col:
        fig_map = px.scatter_map(
            filtered_current,
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
        st.caption("Click a row to filter by area")
        event = st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            height=480,
            on_select="rerun",
            selection_mode="multi-row",
        )
        clicked_areas = display.iloc[event.selection.rows]["Area"].tolist()
        if clicked_areas != st.session_state.selected_areas:
            st.session_state.selected_areas = clicked_areas
            st.rerun()

    st.divider()
    st.subheader("Price Distribution")
    fig_hist = px.histogram(
        filtered_current,
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
    area_options = sorted(fact[fact["area_code"] != "all"]["area_code"].unique())
    default_areas = st.session_state.selected_areas if st.session_state.selected_areas else area_options[:5]
    trend_areas = st.multiselect(
        "Area codes",
        options=area_options,
        default=default_areas,
    )

    filtered_fact = fact[fact["area_code"].isin(trend_areas)].sort_values("date")

    agg = (
        filtered_fact.groupby("date", as_index=False)
        .agg(median_price=("median_price", "median"), num_properties=("num_properties", "sum"))
    )

    spark_col1, spark_col2 = st.columns(2)
    with spark_col1:
        st.caption("Median Price")
        st.plotly_chart(sparkline(agg, "median_price"), use_container_width=True)
    with spark_col2:
        st.caption("Properties Listed")
        st.plotly_chart(sparkline(agg, "num_properties"), use_container_width=True)

    st.divider()

    st.subheader("Average Price")
    fig_avg = px.line(
        filtered_fact,
        x="date",
        y="avg_price",
        color="area_code",
        labels={"date": "Date", "avg_price": "Avg Price (£ pcm)", "area_code": "Area"},
    )
    st.plotly_chart(fig_avg, use_container_width=True)

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
