import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from statfin_service import (
    MUNICIPALITIES,
    MUNICIPALITY_COLORS,
    fetch_population_data,
    fetch_employment_data,
    fetch_unemployment_data,
    fetch_dependency_ratio_data,
)


def main() -> None:
    st.set_page_config(page_title="Kuntien väestökehitys", layout="wide")
    st.title("Kaustisen seudun kehitysnäkymä")
    st.caption("Python-pohjainen dashboard Tilastokeskuksen StatFin-rajapinnasta")

    @st.cache_data(ttl=3600)
    def load_data():
        pop = fetch_population_data()
        emp = fetch_employment_data()
        unemp = fetch_unemployment_data()
        dep = fetch_dependency_ratio_data()
        return pop, emp, unemp, dep

    pop_df, emp_df, unemp_df, dep_df = load_data()

    if pop_df.empty:
        st.error("Väestödatan haku epäonnistui. Tarkista verkkoyhteys tai StatFinin saatavuus.")
        st.stop()

    all_years = sorted(pop_df["year"].unique().tolist())
    selected_year = st.sidebar.selectbox("Valitse vuosi", all_years, index=len(all_years) - 1)
    selected_muni = st.sidebar.multiselect("Valitse kunnat", MUNICIPALITIES, default=MUNICIPALITIES)

    if not selected_muni:
        st.warning("Valitse vähintään yksi kunta.")
        st.stop()

    filtered_pop = pop_df[(pop_df["municipality"].isin(selected_muni)) & (pop_df["year"] == selected_year)]
    current_total = int(filtered_pop["value"].sum())

    first_year = all_years[0]
    first_total = int(
        pop_df[(pop_df["municipality"].isin(selected_muni)) & (pop_df["year"] == first_year)]["value"].sum()
    )
    change_pct = ((current_total - first_total) / first_total * 100.0) if first_total else 0.0
    largest = filtered_pop.sort_values("value", ascending=False).iloc[0]["municipality"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Väestö yhteensä", f"{current_total:,}".replace(",", " "))
    c2.metric("Muutos %", f"{change_pct:.1f} %")
    c3.metric("Suurin kunta", largest)

    st.subheader("Väestökehitys")
    trend = pop_df[pop_df["municipality"].isin(selected_muni)]
    fig_line = px.line(
        trend,
        x="year",
        y="value",
        color="municipality",
        color_discrete_map=MUNICIPALITY_COLORS,
        markers=True,
    )
    fig_line.update_layout(legend_title_text="Kunta", yaxis_title="Asukkaat", xaxis_title="Vuosi")
    st.plotly_chart(fig_line, use_container_width=True)

    st.subheader(f"Keskeiset tunnusluvut ({selected_year})")

    def _latest(df):
        if df.empty:
            return {}
        current = df[df["year"] == selected_year]
        return {row["municipality"]: row["value"] for _, row in current.iterrows()}

    emp_map = _latest(emp_df)
    unemp_map = _latest(unemp_df)
    dep_map = _latest(dep_df)

    rows = []
    for muni in selected_muni:
        rows.append(
            {
                "Kunta": muni,
                "Väestö": int(filtered_pop[filtered_pop["municipality"] == muni]["value"].sum()),
                "Työllisyysaste %": emp_map.get(muni),
                "Työttömyysaste %": unemp_map.get(muni),
                "Väestöllinen huoltosuhde": dep_map.get(muni),
            }
        )

    st.dataframe(rows, use_container_width=True)

    st.subheader("Väestövertailu")
    bar_df = filtered_pop.sort_values("value", ascending=False)
    fig_bar = go.Figure()
    for _, row in bar_df.iterrows():
        fig_bar.add_trace(
            go.Bar(
                x=[row["municipality"]],
                y=[row["value"]],
                marker_color=MUNICIPALITY_COLORS.get(row["municipality"], "#3b82f6"),
                name=row["municipality"],
                showlegend=False,
            )
        )
    fig_bar.update_layout(xaxis_title="Kunta", yaxis_title="Asukkaat")
    st.plotly_chart(fig_bar, use_container_width=True)


if __name__ == "__main__":
    main()
