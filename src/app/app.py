from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.data_generator.generate_all import generate_dataset
from src.exasol_engine.db_client import ChakanExasolClient


def format_inr_crore_lakh(amount_inr: float) -> str:
    val = float(amount_inr or 0.0)
    if val >= 10_000_000:
        return f"Rs {val / 10_000_000:.2f} Cr"
    if val >= 100_000:
        return f"Rs {val / 100_000:.2f} L"
    return f"Rs {val:,.0f}"


def get_client() -> ChakanExasolClient:
    if "exasol_client" not in st.session_state:
        client = ChakanExasolClient()
        client.connect()
        st.session_state["exasol_client"] = client
    return st.session_state["exasol_client"]


def render_sidebar(client: ChakanExasolClient, marts: dict) -> None:
    st.sidebar.markdown("### Exasol Platform Control")
    st.sidebar.caption("Schema: `CHAKAN_SCM` | DSN: `localhost:8563`")

    mode_label = (
        "EXASOL PERSONAL (LIVE MPP)"
        if marts["engine_mode"] == "EXASOL_PERSONAL"
        else "LOCAL ANALYTICAL MIRROR"
    )
    st.sidebar.metric("Execution Engine", mode_label)
    st.sidebar.metric("Analytical Mart Latency", f"{marts['query_latency_ms']:.2f} ms")
    st.sidebar.metric("Total Inbound ASN Rows", f"{len(marts['asn_lineage_mart']):,}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Live Demo Workflow")

    if st.sidebar.button("1. Sync Monday ASN Batch (500 Rows)", use_container_width=True):
        generate_dataset(output_dir=str(client.data_dir), extra_asns=480)
        client.bootstrap_exasol_schema_and_data()
        st.rerun()

    if st.sidebar.button("2. Stress-Test Batch (5,000 ASN Rows)", use_container_width=True):
        generate_dataset(output_dir=str(client.data_dir), extra_asns=4982)
        client.bootstrap_exasol_schema_and_data()
        st.rerun()

    if st.sidebar.button("3. Reset Planner Overrides", use_container_width=True):
        client.reset_planner_overrides()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Problem Context:** Sub-tier MSME suppliers submit dispatch notices in conflicting units "
        "(`BAG_250`, `CRATE_50`, `MT`), vendor SKU aliases (`6204ZZ`), and mixed dates. "
        "Instead of dropping malformed rows into a dead-letter table, Exasol Personal harmonizes "
        "them in-database and ranks every anomaly by **Rs Production Output at Risk**."
    )


def render_kpi_header(marts: dict) -> None:
    sched_df = get_client().tables["PRODUCTION_SCHEDULES"]
    inv_df = marts["inventory_mart"]
    bom_df = marts["bom_risk_mart"]
    triage_df = marts["triage_queue"]

    total_scheduled_val = float((sched_df["planned_output_units"] * sched_df["finished_unit_value_inr"]).sum())
    legacy_risk_val = float(bom_df["revenue_at_risk_legacy_inr"].sum())
    net_risk_val = float(bom_df["revenue_at_risk_net_inr"].sum())
    cleared_by_udf_val = max(0.0, legacy_risk_val - net_risk_val)
    phantom_val = float(inv_df["phantom_inventory_value_inr"].sum())
    phantom_units = int(inv_df["phantom_inventory_qty"].sum())
    pending_count = int((triage_df["harmonization_state"] == "UDF_HARMONIZED_PENDING_APPROVAL").sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "48h Scheduled Output",
        format_inr_crore_lakh(total_scheduled_val),
        f"{int(sched_df['planned_output_units'].sum())} Assemblies (4 Lines)",
    )
    c2.metric(
        "Legacy ETL Blind-Spot Risk",
        format_inr_crore_lakh(legacy_risk_val),
        f"{len(triage_df)} Quarantined Active ASNs",
        delta_color="inverse",
    )
    c3.metric(
        "Risk Cleared by Exasol UDFs",
        format_inr_crore_lakh(cleared_by_udf_val),
        "In-DB SKU / UOM / Date Harmonization",
    )
    c4.metric(
        "True Net Shortage Exposed",
        format_inr_crore_lakh(net_risk_val),
        f"{pending_count} Pending Planner Action",
        delta_color="inverse" if net_risk_val > 0 else "normal",
    )
    c5.metric(
        "Phantom Inventory Detected",
        format_inr_crore_lakh(phantom_val),
        f"{phantom_units:,} Unpickable Ledger Units",
        delta_color="inverse",
    )


def render_triage_tab(client: ChakanExasolClient, marts: dict) -> None:
    triage_df: pd.DataFrame = marts["triage_queue"].copy()

    st.subheader("Quarantined Supplier ASNs Ranked by Production Blast Radius (Rs)")
    st.caption(
        "Unlike traditional data-quality tools that list technical regex failures, this queue ranks "
        "malformed supplier dispatches by the exact assembly lines and revenue threatened over the next 48 hours."
    )

    display_df = pd.DataFrame(
        {
            "ASN Line ID": triage_df["asn_line_id"],
            "PO Number": triage_df["po_number_ref"],
            "Supplier": triage_df["supplier_name"] + " (" + triage_df["tier_level"] + ")",
            "Raw SKU -> UDF Resolved SKU": triage_df["raw_supplier_sku"] + " -> " + triage_df["resolved_part_num"],
            "Raw Qty/UOM": triage_df["raw_shipped_qty"].astype(str) + " " + triage_df["raw_shipped_uom"],
            "UDF Harmonized Qty": triage_df["harmonized_shipped_qty"].round(1).astype(str) + " " + triage_df["canonical_uom"],
            "PO Ordered Qty": triage_df["po_ordered_qty"].round(0).astype(str) + " " + triage_df["canonical_uom"],
            "Affected Line(s)": triage_df["affected_lines"],
            "Operational Verdict": triage_df["operational_verdict"],
            "Legacy Risk (Rs)": triage_df["revenue_at_risk_legacy_inr"].apply(format_inr_crore_lakh),
            "True Net Risk (Rs)": triage_df["revenue_at_risk_net_inr"].apply(format_inr_crore_lakh),
            "State": triage_df["harmonization_state"],
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Interactive Planner Resolution & Emergency Replenishment Workbench")

    options = triage_df["asn_line_id"].tolist()
    selected_id = st.selectbox(
        "Select Quarantined ASN Record to Inspect & Resolve:",
        options=options,
        format_func=lambda x: (
            f"{x} | PO: {triage_df.loc[triage_df['asn_line_id'] == x, 'po_number_ref'].values[0]} | "
            f"Raw SKU: {triage_df.loc[triage_df['asn_line_id'] == x, 'raw_supplier_sku'].values[0]} -> "
            f"{triage_df.loc[triage_df['asn_line_id'] == x, 'resolved_part_num'].values[0]} | "
            f"Verdict: {triage_df.loc[triage_df['asn_line_id'] == x, 'operational_verdict'].values[0]}"
        ),
    )

    sel_row = triage_df[triage_df["asn_line_id"] == selected_id].iloc[0]

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**1. Raw Supplier Payload (Quarantined)**")
        st.write(f"- **Supplier:** {sel_row['supplier_name']} (`{sel_row['supplier_id']}`)")
        st.write(f"- **Channel:** `{sel_row['source_format']}` | **Lorry:** `{sel_row['vehicle_lorry_no']}`")
        st.write(f"- **Raw SKU String:** `{sel_row['raw_supplier_sku']}`")
        st.write(f"- **Raw Shipped Quantity:** `{sel_row['raw_shipped_qty']} {sel_row['raw_shipped_uom']}`")
        st.write(f"- **Raw ETA String:** `{sel_row['raw_eta_date']}` (`{sel_row['anomaly_type']}`)")

    with col_b:
        st.markdown("**2. Exasol In-DB Python UDF Output**")
        st.write(f"- **Resolved Internal SKU:** `{sel_row['resolved_part_num']}`")
        st.write(f"- **SKU Match Method:** `{sel_row['sku_match_method']}` (Confidence: `{sel_row['sku_confidence']:.2f}`)")
        st.write(f"- **Normalized Quantity:** `{sel_row['harmonized_shipped_qty']:,.1f} {sel_row['canonical_uom']}`")
        st.write(f"- **Normalized ETA Date:** `{sel_row['harmonized_eta_date']}`")
        st.write(f"- **Current State:** `{sel_row['harmonization_state']}`")

    with col_c:
        st.markdown("**3. Plant Blast-Radius & Line Impact**")
        st.write(f"- **Affected Assembly Line(s):** `{sel_row['affected_lines']}`")
        st.write(f"- **PO Ordered vs Harmonized:** `{sel_row['po_ordered_qty']:,.0f}` vs `{sel_row['harmonized_shipped_qty']:,.0f} {sel_row['canonical_uom']}`")
        st.write(f"- **Warehouse Phantom Stock Loss:** `{sel_row['phantom_inventory_qty']:,.0f} {sel_row['canonical_uom']}`")
        st.write(f"- **Hours to Line Stop (Legacy -> Harmonized):** `{sel_row['min_hours_to_stop_legacy']}h` -> `{sel_row['min_hours_to_stop_harmonized']}h`")
        st.write(f"- **Net Production Risk:** **{format_inr_crore_lakh(sel_row['revenue_at_risk_net_inr'])}**")

    b1, b2 = st.columns(2)
    with b1:
        if st.button(
            f"Approve UDF Harmonization ({sel_row['harmonized_shipped_qty']:,.0f} {sel_row['canonical_uom']})",
            use_container_width=True,
        ):
            write_ms = client.approve_harmonization_override(
                asn_line_id=str(sel_row["asn_line_id"]),
                resolved_part_num=str(sel_row["resolved_part_num"]),
                normalized_qty=float(sel_row["harmonized_shipped_qty"]),
                normalized_uom=str(sel_row["canonical_uom"]),
                normalized_eta_date=str(sel_row["harmonized_eta_date"]),
                action="PLANNER_APPROVED_UDF",
            )
            st.success(f"Committed UDF harmonization to Exasol in {write_ms:.2f} ms.")
            st.rerun()

    with b2:
        full_po_qty = float(sel_row["po_ordered_qty"])
        if st.button(
            f"Approve & Trigger Emergency Replenishment (Cover Full PO: {full_po_qty:,.0f} {sel_row['canonical_uom']})",
            type="primary",
            use_container_width=True,
        ):
            write_ms = client.approve_harmonization_override(
                asn_line_id=str(sel_row["asn_line_id"]),
                resolved_part_num=str(sel_row["resolved_part_num"]),
                normalized_qty=full_po_qty,
                normalized_uom=str(sel_row["canonical_uom"]),
                normalized_eta_date=str(sel_row["harmonized_eta_date"]),
                action="EXPEDITED_SHORTFALL_COVERED",
            )
            st.success(f"Authorized emergency shortfall cover and updated Exasol in {write_ms:.2f} ms.")
            st.rerun()


def render_bom_horizon_tab(marts: dict) -> None:
    bom_df: pd.DataFrame = marts["bom_risk_mart"].copy()
    bom_df["line_component_label"] = bom_df["assembly_line_id"] + " | " + bom_df["component_part_num"]

    st.subheader("48-Hour Assembly Station Starvation Horizon (Before vs. After Exasol Harmonization)")
    st.caption(
        "Any component bar falling below the 48-hour scheduled run window indicates an impending line stoppage."
    )

    chart_df = bom_df.sort_values("hours_to_starvation_legacy", ascending=True)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=chart_df["line_component_label"],
            x=chart_df["hours_to_starvation_legacy"],
            name="Legacy ETL (Quarantined ASNs = 0 Stock)",
            orientation="h",
            marker_color="#d9534f",
        )
    )
    fig.add_trace(
        go.Bar(
            y=chart_df["line_component_label"],
            x=chart_df["hours_to_starvation_harmonized"],
            name="Exasol UDF Harmonized + Planner Overrides",
            orientation="h",
            marker_color="#00a878",
        )
    )
    fig.add_vline(x=48.0, line_dash="dash", line_color="#1f2937", annotation_text="48h Full Run Target")
    fig.update_layout(
        barmode="group",
        height=520,
        xaxis_title="Hours Until Assembly Station Starvation (Max 48h)",
        yaxis_title="Assembly Line & Component SKU",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("BOM Explosion & Component Deficit Matrix")
    bom_table = pd.DataFrame(
        {
            "Assembly Line": bom_df["assembly_line_id"],
            "Parent Assembly": bom_df["parent_part_num"],
            "Station": bom_df["assembly_station_code"],
            "Component SKU": bom_df["component_part_num"],
            "Description": bom_df["part_description"],
            "48h Gross Req": bom_df["gross_required_qty"],
            "True Pickable ATP": bom_df["true_pickable_atp_qty"],
            "Legacy Inbound": bom_df["legacy_inbound_qty"],
            "Harmonized Inbound": bom_df["harmonized_inbound_qty"],
            "Vendor Short-Shipped": bom_df["supplier_short_shipped_qty"],
            "Net Line Deficit": bom_df["true_net_deficit_qty"],
            "Hrs to Stop (Legacy)": bom_df["hours_to_starvation_legacy"],
            "Hrs to Stop (Harmonized)": bom_df["hours_to_starvation_harmonized"],
            "Net Revenue at Risk": bom_df["revenue_at_risk_net_inr"].apply(format_inr_crore_lakh),
        }
    )
    st.dataframe(bom_table, use_container_width=True, hide_index=True)


def render_phantom_inventory_tab(marts: dict) -> None:
    inv_df: pd.DataFrame = marts["inventory_mart"].copy().sort_values(
        "phantom_inventory_value_inr", ascending=False
    )

    st.subheader("Warehouse Phantom Inventory Audit (`VW_INVENTORY_TRUE_ATP`)")
    st.caption(
        "Reconciles Central ERP ledger balances against physical WMS cycle counts and quality-hold bins "
        "at Chakan Plant-1 Stores (`CHAKAN-PLT1-STORE`)."
    )

    fig_inv = px.bar(
        inv_df,
        x="internal_part_num",
        y=["true_pickable_atp_qty", "phantom_inventory_qty", "allocated_to_prod_qty", "quality_hold_qty"],
        title="Component Stock Breakdown: True Pickable ATP vs. Phantom Ledger Drift",
        labels={"value": "Units in Base UOM", "internal_part_num": "Component SKU", "variable": "Stock Category"},
        barmode="group",
        height=440,
    )
    st.plotly_chart(fig_inv, use_container_width=True)

    inv_table = pd.DataFrame(
        {
            "Storage Bin": inv_df["storage_bin_id"],
            "Component SKU": inv_df["internal_part_num"],
            "Part Description": inv_df["part_description"],
            "UOM": inv_df["base_uom"],
            "ERP On-Hand (Ledger)": inv_df["erp_system_on_hand_qty"],
            "WMS Physical Count": inv_df["wms_physical_counted_qty"],
            "Allocated to Prod": inv_df["allocated_to_prod_qty"],
            "Quality Hold": inv_df["quality_hold_qty"],
            "True Pickable ATP": inv_df["true_pickable_atp_qty"],
            "Phantom Inventory Qty": inv_df["phantom_inventory_qty"],
            "Phantom Capital Distortion": inv_df["phantom_inventory_value_inr"].apply(format_inr_crore_lakh),
        }
    )
    st.dataframe(inv_table, use_container_width=True, hide_index=True)


def render_exasol_engine_tab(client: ChakanExasolClient, marts: dict) -> None:
    st.subheader("Exasol Personal Architecture & In-Database UDF Definitions")
    st.markdown(
        """
        This solution uses **Exasol Personal** (`CHAKAN_SCM` schema) as the core analytical and data-harmonization platform:
        - **MPP Co-Located Joins (`DISTRIBUTE BY`):** `ITEM_MASTER`, `BILL_OF_MATERIALS`, `PURCHASE_ORDER_LINES`, and `WAREHOUSE_INVENTORY_LEDGER` are distributed on `internal_part_num` so joins execute locally without network redistribution.
        - **In-Database Python 3 Scalar UDFs:** `UDF_NORMALIZE_UOM`, `UDF_RESOLVE_SUPPLIER_SKU`, and `UDF_PARSE_ASN_DATE` run inside Exasol next to the columnar tables.
        - **Interactive Writeback Loop:** Planner overrides persist directly to `CHAKAN_SCM.ASN_PLANNER_OVERRIDES` and trigger sub-second view recalculation.
        """
    )

    sql_dir = PROJECT_ROOT / "src" / "exasol_engine"
    t_ddl, t_udf, t_views = st.tabs(
        ["1. MPP Schema DDL (ddl_schema.sql)", "2. Python 3 UDFs (udfs_harmonization.sql)", "3. Analytical Views (blast_radius_marts.sql)"]
    )
    with t_ddl:
        st.code((sql_dir / "ddl_schema.sql").read_text(encoding="utf-8"), language="sql")
    with t_udf:
        st.code((sql_dir / "udfs_harmonization.sql").read_text(encoding="utf-8"), language="sql")
    with t_views:
        st.code((sql_dir / "blast_radius_marts.sql").read_text(encoding="utf-8"), language="sql")


def main() -> None:
    st.set_page_config(
        page_title="Chakan ASN Blast-Radius Cockpit | Exasol Personal",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Chakan Plant-1: Inbound ASN Harmonization & Line-Starvation Cockpit")
    st.markdown(
        "**Persona:** Lead Inbound Materials & Line-Feed Planner | "
        "**Facility:** Pune-Chakan Powertrain Assembly Plant | "
        "**Data Platform:** Exasol Personal (`CHAKAN_SCM`)"
    )

    client = get_client()
    marts = client.compute_analytical_marts()

    render_sidebar(client, marts)
    render_kpi_header(marts)

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "1. Quarantine Blast-Radius Triage (Action Queue)",
            "2. Assembly Line Starvation & BOM Horizon",
            "3. Warehouse Phantom Inventory Audit",
            "4. Exasol Personal SQL & UDF Inspector",
        ]
    )

    with tab1:
        render_triage_tab(client, marts)
    with tab2:
        render_bom_horizon_tab(marts)
    with tab3:
        render_phantom_inventory_tab(marts)
    with tab4:
        render_exasol_engine_tab(client, marts)


if __name__ == "__main__":
    main()
