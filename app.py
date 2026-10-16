"""Germany Power Pulse | interactive German wholesale electricity analytics."""
from datetime import date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from power_pulse.smard import load_market_data
from power_pulse.analytics import enrich, metrics, validation_report, insight
from power_pulse.config import GENERATION, RENEWABLE, SERIES, COLORS

st.set_page_config(page_title="Germany Power Pulse", page_icon="⚡", layout="wide")
st.markdown("""
<style>
.block-container{max-width:1320px;padding-top:2rem}
[data-testid=stMetric]{border:1px solid #2D4054;border-radius:14px;padding:17px;
background:#172438}
h1,h2,h3{letter-spacing:-.03em}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600, show_spinner=False)
def get_data(days):
    return load_market_data(days=days)

with st.sidebar:
    st.title("⚡ Power Pulse")
    st.caption("German electricity market intelligence")
    days = st.select_slider("Lookback period", options=[7, 14, 30], value=14)
    if st.button("Refresh official data", use_container_width=True):
        get_data.clear()
        st.rerun()
    st.divider()
    st.markdown("[Bundesnetzagentur SMARD](https://www.smard.de/en)")
    st.caption("All chart times are Europe/Berlin. Raw timestamps are UTC.")

st.caption("ENERGY INTELLIGENCE  /  GERMANY")
st.title("The power behind the price.")
st.write("Explore Germany's renewable generation, grid load and day-ahead wholesale "
         "electricity prices, using official data. Correlations are not causal explanations.")

with st.spinner("Fetching hourly observations from SMARD..."):
    raw, failures = get_data(days)

if raw.empty or not raw[list(SERIES)].notna().any().any():
    st.error("No observations available from SMARD. Please retry later.")
    if failures:
        with st.expander("Connection details"):
            st.json(failures)
    st.stop()
if failures:
    st.warning(f"{len(failures)} sources could not be loaded. Missing values are shown as gaps.")
    with st.expander("Technical details"):
        st.json(failures)

df = enrich(raw)
min_day, max_day = df["day"].min(), df["day"].max()
period = st.date_input("Explore dates", value=(min_day, max_day),
                       min_value=min_day, max_value=max_day, format="DD/MM/YYYY")
if isinstance(period, (tuple, list)) and len(period) == 2:
    start_day, end_day = period
else:
    start_day, end_day = min_day, max_day
selected = df[df["day"].between(start_day, end_day)].copy()
if selected.empty:
    st.info("No observations in the selected interval.")
    st.stop()

kpis = metrics(selected)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mean day-ahead price", f"€{kpis['average_price']:.1f}/MWh"
          if kpis["average_price"] is not None else "N/A")
c2.metric("Negative-price hours", kpis["negative_price_hours"]
          if kpis["negative_price_hours"] is not None else "N/A")
c3.metric("Renewable share of measured generation",
          f"{kpis['renewable_share']:.1f}%" if kpis["renewable_share"] is not None else "N/A")
c4.metric("Observed grid load", f"{kpis['grid_load_gwh']:,.0f} GWh"
          if kpis["grid_load_gwh"] is not None else "N/A")
st.caption("These are wholesale market prices, not household bills. Renewable share "
           "uses only hours with all 11 generation categories observed.")

t1, t2, t3, t4 = st.tabs(["Market trends", "Generation mix",
                           "Price calendar", "Data quality"])

with t1:
    st.subheader("Wholesale price by hour")
    fig = px.line(selected, x="local_time", y="price", labels={
        "local_time": "Date (Berlin)", "price": "Day-ahead price (€/MWh)"})
    fig.update_traces(line_color="#AD94FF")
    fig.add_hline(y=0, line_dash="dot", line_color="#8EA4B9")
    st.plotly_chart(fig, use_container_width=True)
    st.info(insight(selected))
    scatter = selected.dropna(subset=["wind_solar_mwh", "price", "grid_load"]).copy()
    if not scatter.empty:
        scatter["Wind + solar (GWh)"] = scatter["wind_solar_mwh"] / 1000
        scatter["Grid load (GWh)"] = scatter["grid_load"] / 1000
        fig = px.scatter(scatter, x="Wind + solar (GWh)", y="price",
                         color="Grid load (GWh)", color_continuous_scale="Tealgrn",
                         hover_data=["local_time"], opacity=.85,
                         labels={"price": "Price (€/MWh)"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Price/generation comparison needs complete observations.")

with t2:
    st.subheader("Electricity generation by source")
    tidy = selected.melt(id_vars="local_time", value_vars=list(GENERATION),
                         var_name="technology", value_name="MWh")
    tidy["Generation (GWh)"] = tidy["MWh"] / 1000
    tidy["technology"] = tidy["technology"].map({k: SERIES[k].label for k in GENERATION})
    palette = {SERIES[k].label: COLORS[k] for k in GENERATION}
    fig = px.area(tidy, x="local_time", y="Generation (GWh)",
                  color="technology", color_discrete_map=palette,
                  labels={"local_time": "Berlin time", "technology": "Source"})
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Pumped storage discharge is grouped separately and is not fossil generation.")

with t3:
    st.subheader("When was electricity cheaper or more expensive?")
    observed = selected.dropna(subset=["price"])
    if observed.empty:
        st.info("No price observations in selected period.")
    else:
        calendar = observed.pivot_table(index="day", columns="hour",
                                        values="price", aggfunc="mean")
        calendar = calendar.reindex(columns=range(24)).sort_index()
        heat = go.Figure(go.Heatmap(z=calendar.to_numpy(), x=list(calendar.columns),
            y=[str(d) for d in calendar.index], colorscale="RdBu_r",
            colorbar=dict(title="€/MWh")))
        heat.update_layout(xaxis_title="Local hour (Berlin)", yaxis_title="Date",
                           height=max(340, min(850, 32 * len(calendar) + 100)))
        heat.update_yaxes(autorange="reversed")
        st.plotly_chart(heat, use_container_width=True)
        st.caption("At the October clock change, repeated 02:00 hours are averaged "
                   "into one cell. Individual UTC records remain separate.")

with t4:
    st.subheader("Transparency and data completeness")
    st.dataframe(validation_report(selected), hide_index=True, use_container_width=True)
    st.caption(f"Price observations: {kpis['hours_with_price']} of {kpis['hours']} hourly "
               f"records. Complete generation mix: {kpis['hours_with_complete_generation']} hours.")
    st.dataframe(selected[["local_time", "price", "grid_load",
                            "wind_solar_mwh", "renewable_pct"]].tail(100),
                 hide_index=True, use_container_width=True)
    csv = selected.to_csv(index=False).encode("utf-8")
    st.download_button("Download selected observations (CSV)", csv,
                       file_name="germany-power-pulse.csv", mime="text/csv")

st.divider()
st.caption("Source: Bundesnetzagentur | SMARD.de, CC BY 4.0. Research portfolio. "
           "Observed data may be revised. Dashboard does not infer causation.")
