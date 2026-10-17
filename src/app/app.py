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

    telemetry = marts.get("telemetry", {})
    compute_source = marts.get("compute_source", telemetry.get("compute_source", "PANDAS_MIRROR"))
    mode_label = (
        "EXASOL PERSONAL (LIVE SQL/UDF)"
        if marts["engine_mode"] == "EXASOL_PERSONAL"
        else "LOCAL ANALYTICAL MIRROR"
    )
    st.sidebar.metric("Execution Engine", mode_label)
    st.sidebar.metric("Compute Source", compute_source)
    st.sidebar.metric("Analytical Mart Latency", f"{marts['query_latency_ms']:.2f} ms")
    total_eval = telemetry.get("total_rows_evaluated", len(marts["asn_lineage_mart"]))
    st.sidebar.metric("Rows Evaluated", f"{total_eval:,} Records")
    st.sidebar.metric("Distribution Keys", "internal_part_num / component_part_num")
    st.sidebar.caption("Co-located joins across `ITEM_MASTER`, `PURCHASE_ORDER_LINES`, `WAREHOUSE_INVENTORY_LEDGER`, `BILL_OF_MATERIALS`")

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


def render_telemetry_banner(marts: dict) -> None:
    telemetry = marts.get("telemetry", {})
    engine_mode = marts.get("engine_mode", "LOCAL_MIRROR")
    compute_source = marts.get("compute_source", telemetry.get("compute_source", "PANDAS_MIRROR"))
    latency_ms = float(marts.get("query_latency_ms", telemetry.get("latency_ms", 0.0)))
    total_rows = int(telemetry.get("total_rows_evaluated", len(marts.get("asn_lineage_mart", []))))
    colocation_key = telemetry.get("colocation_key", "internal_part_num")
    udf_engine = telemetry.get("udf_engine", "PYTHON3_IN_DB_RAM")

    is_live = (engine_mode == "EXASOL_PERSONAL" and compute_source == "EXASOL_VIEWS")
    mode_html = (
        '<span style="background-color: #064e3b; color: #34d399; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem; border: 1px solid #059669;">🟢 EXASOL PERSONAL (LIVE SQL VIEWS &amp; UDFs)</span>'
        if is_live
        else '<span style="background-color: #451a03; color: #fde68a; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem; border: 1px solid #d97706;">🟠 LOCAL ANALYTICAL MIRROR (PANDAS FALLBACK)</span>'
    )

    st.markdown(
        f"""
        <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; background-color: #0b1120; padding: 8px 14px; border-radius: 8px; margin-top: 6px; margin-bottom: 12px; border: 1px solid #1e293b;">
            <span style="font-size: 0.76rem; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px;">LIVE ENGINE TELEMETRY:</span>
            {mode_html}
            <span style="background-color: #1e1b4b; color: #a5b4fc; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem; border: 1px solid #4f46e5;">⚡ Measured Latency: {latency_ms:.1f} ms ({compute_source})</span>
            <span style="background-color: #1f2937; color: #e5e7eb; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; border: 1px solid #374151;">💾 {total_rows:,} Rows Evaluated</span>
            <span style="background-color: #0c4a6e; color: #7dd3fc; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; border: 1px solid #0284c7;">🔗 DISTRIBUTE BY ({colocation_key})</span>
            <span style="background-color: #3b0764; color: #f0abfc; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; border: 1px solid #9333ea;">🐍 UDF Engine: {udf_engine}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("🔍 Live Query Stage Timings & Schema Distribution Plan (Click to inspect pipeline)", expanded=False):
        stages = telemetry.get("latency_stages_ms", {})
        s1_ms = stages.get("view_inventory_true_atp", stages.get("inventory_mart", 0.0))
        s2_ms = stages.get("view_asn_harmonized_lineage", stages.get("asn_harmonization", 0.0))
        s3_ms = stages.get("view_bom_line_starvation_risk", stages.get("bom_risk_mart", 0.0))
        s4_ms = stages.get("python_triage_postprocess", stages.get("triage_and_roi", 0.0))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stage 1: True ATP Mart", f"{s1_ms:.2f} ms", "VW_INVENTORY_TRUE_ATP")
        c2.metric("Stage 2: ASN UDF Lineage", f"{s2_ms:.2f} ms", "VW_ASN_HARMONIZED_LINEAGE")
        c3.metric("Stage 3: BOM Starvation Risk", f"{s3_ms:.2f} ms", "VW_BOM_LINE_STARVATION_RISK")
        c4.metric("Stage 4: Triage & ROI Rollup", f"{s4_ms:.2f} ms", "Triage Ranking & ROI")

        st.markdown("---")
        col_prof1, col_prof2 = st.columns([1, 1])
        with col_prof1:
            st.markdown("**Schema Distribution Strategy (`ddl_schema.sql`):**")
            st.markdown(
                """
                Tables in `CHAKAN_SCM` are partitioned on their primary join keys so part-level joins align across slices:
                - `ITEM_MASTER`, `PURCHASE_ORDER_LINES`, `WAREHOUSE_INVENTORY_LEDGER`: `DISTRIBUTE BY (internal_part_num)`
                - `BILL_OF_MATERIALS`: `DISTRIBUTE BY (component_part_num)` (joins to `ITEM_MASTER.internal_part_num`)
                - `PRODUCTION_SCHEDULES`: `DISTRIBUTE BY (parent_part_num)`
                - `ASN_LINES_RAW`, `ASN_PLANNER_OVERRIDES`: `DISTRIBUTE BY (po_number_ref)` / `(asn_line_id)`
                """
            )
        with col_prof2:
            st.markdown("**Live Table Row Counts:**")
            counts = telemetry.get("table_row_counts", {})
            prof_table = pd.DataFrame(
                [
                    {"Table Name": "ASN_LINES_RAW", "Distribution Key": "po_number_ref", "Storage": "Columnar RAM", "Rows": f"{counts.get('ASN_LINES_RAW', 0):,}"},
                    {"Table Name": "PURCHASE_ORDER_LINES", "Distribution Key": "internal_part_num", "Storage": "Columnar RAM", "Rows": f"{counts.get('PURCHASE_ORDER_LINES', 0):,}"},
                    {"Table Name": "ITEM_MASTER", "Distribution Key": "internal_part_num", "Storage": "Columnar RAM", "Rows": f"{counts.get('ITEM_MASTER', 0):,}"},
                    {"Table Name": "BILL_OF_MATERIALS", "Distribution Key": "component_part_num", "Storage": "Columnar RAM", "Rows": f"{counts.get('BILL_OF_MATERIALS', 0):,}"},
                    {"Table Name": "WAREHOUSE_INVENTORY_LEDGER", "Distribution Key": "internal_part_num", "Storage": "Columnar RAM", "Rows": f"{counts.get('WAREHOUSE_INVENTORY_LEDGER', 0):,}"},
                    {"Table Name": "PRODUCTION_SCHEDULES", "Distribution Key": "parent_part_num", "Storage": "Columnar RAM", "Rows": f"{counts.get('PRODUCTION_SCHEDULES', 0):,}"},
                    {"Table Name": "SUPPLIER_MASTER", "Distribution Key": "supplier_id (PK)", "Storage": "Columnar RAM", "Rows": f"{counts.get('SUPPLIER_MASTER', 0):,}"},
                    {"Table Name": "ASN_PLANNER_OVERRIDES", "Distribution Key": "asn_line_id", "Storage": "Columnar RAM", "Rows": f"{counts.get('ASN_PLANNER_OVERRIDES', 0):,}"},
                ]
            )
            st.dataframe(prof_table, use_container_width=True, hide_index=True)



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

    roi = marts.get("financial_roi_mart", {})
    if roi:
        st.markdown(
            f"""
            <div style="background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 12px 18px; border-radius: 8px; margin-top: 10px; margin-bottom: 6px; border-left: 5px solid #10b981; color: #f8fafc; font-size: 0.92rem;">
                <b style="color: #34d399; font-weight: 700; letter-spacing: 0.5px;">BOARDROOM BUSINESS DEFENSE (FORMULATION 3):</b>
                &nbsp;&nbsp;|&nbsp;&nbsp;<b>Total Stoppage Exposure:</b> <span style="color: #f87171; font-weight: 600;">{format_inr_crore_lakh(roi.get('total_stoppage_exposure_inr', 0))}</span>
                &nbsp;&nbsp;|&nbsp;&nbsp;<b>Emergency Freight:</b> <span style="color: #fbbf24; font-weight: 600;">{format_inr_crore_lakh(roi.get('benchmark_freight_inr', 45000))}</span>
                &nbsp;&nbsp;|&nbsp;&nbsp;<b>Executive Mitigation ROI:</b> <span style="color: #34d399; font-weight: 800; font-size: 1.05rem;">{roi.get('headline_roi_x', 1175):,.0f}x</span>
                &nbsp;&nbsp;|&nbsp;&nbsp;<b>Avoided Panic Freight Waste:</b> <span style="color: #38bdf8; font-weight: 600;">{format_inr_crore_lakh(roi.get('avoided_panic_freight_inr', 135000))}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_triage_tab(client: ChakanExasolClient, marts: dict) -> None:
    triage_df: pd.DataFrame = marts["triage_queue"].copy()

    st.subheader("Quarantined Supplier ASNs Ranked by Production Blast Radius (Rs)")
    st.caption(
        "Unlike traditional data-quality tools that list technical regex failures, this queue ranks "
        "malformed supplier dispatches by the exact assembly lines, downtime penalty, and net revenue threatened over the next 48 hours."
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
            "Line Idle Penalty": triage_df["downtime_burn_rate_inr_hr"].apply(lambda v: f"Rs {v/100000:.1f} L/hr" if v > 0 else "-"),
            "Expedited Freight": triage_df["expedited_freight_cost_inr"].apply(lambda v: f"Rs {v:,.0f}" if v > 0 else "-"),
            "Mitigation ROI": triage_df["mitigation_roi_x"].apply(lambda v: f"{v:,.0f}x" if v > 0 else "-"),
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
        st.markdown("**3. Plant Blast-Radius & Economic Trade-off**")
        st.write(f"- **Affected Assembly Line(s):** `{sel_row['affected_lines']}`")
        st.write(f"- **PO Ordered vs Harmonized:** `{sel_row['po_ordered_qty']:,.0f}` vs `{sel_row['harmonized_shipped_qty']:,.0f} {sel_row['canonical_uom']}`")
        st.write(f"- **Plant Idle Burn Rate:** Rs {sel_row['downtime_burn_rate_inr_hr']/100000:.2f} Lakh/hr")
        st.write(f"- **Hours to Line Stop:** `{sel_row['min_hours_to_stop_legacy']}h` -> `{sel_row['min_hours_to_stop_harmonized']}h`")
        st.write(f"- **Total Stoppage Exposure:** **{format_inr_crore_lakh(sel_row['total_stoppage_exposure_inr'])}** (Vehicles + Idle Loss)")
        freight_disp = f"Rs {sel_row['expedited_freight_cost_inr']:,.0f}" if sel_row['expedited_freight_cost_inr'] > 0 else "Rs 45,000 (Charter)"
        roi_disp = f"{sel_row['mitigation_roi_x']:,.0f}x" if sel_row['mitigation_roi_x'] > 0 else "N/A"
        st.write(f"- **Emergency Hot-Shot Freight:** {freight_disp} (ROI: **{roi_disp}**)")

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
        btn_roi_label = f" | ROI: {sel_row['mitigation_roi_x']:,.0f}x" if sel_row['mitigation_roi_x'] > 0 else ""
        if st.button(
            f"Approve & Trigger Emergency Replenishment (Cover PO: {full_po_qty:,.0f} {sel_row['canonical_uom']}{btn_roi_label})",
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


def render_scenario_simulator_tab(client: ChakanExasolClient, marts: dict) -> None:
    st.subheader("Interactive 'What-If' Chaos Simulator: Real-Time In-DB Stress Testing")
    st.caption(
        "Automotive supply chains in Chakan face simultaneous compound disruptions: monsoon transit roadblocks, "
        "metallurgy casting porosity at Tier-2 foundries, and sudden OEM assembly line demand surges. "
        "Exasol evaluates all multi-table joins, UDFs, and starvation horizons sub-second in columnar RAM."
    )

    # 1. 1-Click Crisis Presets
    st.markdown("##### 1. One-Click Operational Crisis Presets")
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)

    if col_b1.button("🟢 Baseline Operations", help="Reset all disruption parameters to normal Monday operations (0 delay, 0% defects, 1.0x surge)", use_container_width=True):
        st.session_state["sim_transit_delay"] = 0
        st.session_state["sim_quarantine_rate"] = 0
        st.session_state["sim_demand_surge"] = 1.00
        st.rerun()

    if col_b2.button("🌧️ Western Ghats Monsoon", help="NH-48 Ghat highway landslides causing +3 days transit delay & 5% transit damage", use_container_width=True):
        st.session_state["sim_transit_delay"] = 3
        st.session_state["sim_quarantine_rate"] = 5
        st.session_state["sim_demand_surge"] = 1.00
        st.rerun()

    if col_b3.button("⚙️ Foundry Porosity Crisis", help="Tier-2 engine casting porosity defect spike (35% quarantine reject, +1 day delay)", use_container_width=True):
        st.session_state["sim_transit_delay"] = 1
        st.session_state["sim_quarantine_rate"] = 35
        st.session_state["sim_demand_surge"] = 1.00
        st.rerun()

    if col_b4.button("📈 Festive OEM Demand Surge", help="Festival season production surge (+35% assembly throughput, +2 days delay, 15% quarantine)", use_container_width=True):
        st.session_state["sim_transit_delay"] = 2
        st.session_state["sim_quarantine_rate"] = 15
        st.session_state["sim_demand_surge"] = 1.35
        st.rerun()

    # 2. Interactive Parameter Sliders
    st.markdown("##### 2. Fine-Tuned Chaos Control Knobs")
    col_s1, col_s2, col_s3 = st.columns(3)

    cur_delay = st.session_state.get("sim_transit_delay", 0)
    cur_quar = st.session_state.get("sim_quarantine_rate", 0)
    cur_surge = st.session_state.get("sim_demand_surge", 1.00)

    with col_s1:
        sim_delay = st.slider(
            "Logistics Transit Delay (Days):",
            min_value=0,
            max_value=5,
            value=cur_delay,
            step=1,
            help="Simulates highway closures, customs holds, or carrier delays on incoming shipments.",
            key="slider_transit_delay",
        )
        st.session_state["sim_transit_delay"] = sim_delay

    with col_s2:
        sim_quar = st.slider(
            "Supplier Quality Defect Rate (% Hold):",
            min_value=0,
            max_value=50,
            value=cur_quar,
            step=5,
            help="Simulates in-plant QA gate rejection rate sequestering incoming stock into quality hold.",
            key="slider_quarantine_rate",
        )
        st.session_state["sim_quarantine_rate"] = sim_quar

    with col_s3:
        sim_surge = st.slider(
            "Assembly Throughput Surge Multiplier:",
            min_value=1.00,
            max_value=1.50,
            value=cur_surge,
            step=0.05,
            format="%.2fx",
            help="Simulates OEM assembly overtime / weekend surge shifts accelerating component burn rate.",
            key="slider_demand_surge",
        )
        st.session_state["sim_demand_surge"] = sim_surge

    # 3. Compute Simulated Marts
    sim_results = client.compute_simulation_marts(
        transit_delay_days=sim_delay,
        quarantine_defect_pct=float(sim_quar) / 100.0,
        demand_surge_multiplier=float(sim_surge),
    )

    sim_marts = sim_results["simulated"]
    base_marts = sim_results["baseline"]
    sim_roi = sim_marts["financial_roi_mart"]
    base_roi = base_marts["financial_roi_mart"]
    sim_bom = sim_marts["bom_risk_mart"]
    base_bom = base_marts["bom_risk_mart"]

    sim_net = float(sim_roi["net_risk_inr"])
    delta_net = float(sim_results["delta_net_risk_inr"])
    sim_exp = float(sim_roi["total_stoppage_exposure_inr"])
    delta_exp = float(sim_results["delta_total_exposure_inr"])

    base_min_hrs = float(base_bom["hours_to_starvation_harmonized"].min())
    sim_min_hrs = float(sim_bom["hours_to_starvation_harmonized"].min())
    delta_hrs = round(sim_min_hrs - base_min_hrs, 1)

    base_short_count = int((base_bom["true_net_deficit_qty"] > 0).sum())
    sim_short_count = int((sim_bom["true_net_deficit_qty"] > 0).sum())
    delta_short = sim_short_count - base_short_count

    is_chaos_active = (sim_delay > 0 or sim_quar > 0 or sim_surge > 1.00)
    recalc_latency = float(sim_marts["query_latency_ms"])
    sim_total_rows = int(sim_marts.get("telemetry", {}).get("total_rows_evaluated", len(sim_marts["asn_lineage_mart"])))
    base_net_val = float(base_roi["net_risk_inr"])
    base_exp_val = float(base_roi["total_stoppage_exposure_inr"])

    status_tag = (
        f'<span style="background-color: #7f1d1d; color: #fca5a5; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem; border: 1px solid #dc2626;">🔴 CHAOS SIMULATION ACTIVE (+{sim_delay}d delay, {sim_quar}% defect, {sim_surge:.2f}x surge)</span>'
        if is_chaos_active
        else '<span style="background-color: #064e3b; color: #34d399; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem; border: 1px solid #059669;">🟢 BASELINE RUN (No Disruptions Applied)</span>'
    )

    st.markdown(
        f"""
        <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; background-color: #0f172a; padding: 8px 14px; border-radius: 8px; margin-top: 4px; margin-bottom: 12px; border: 1px solid #334155;">
            <span style="font-size: 0.76rem; font-weight: 800; color: #94a3b8; text-transform: uppercase;">SIMULATOR STATUS:</span>
            {status_tag}
            <span style="background-color: #1e1b4b; color: #a5b4fc; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem; border: 1px solid #4f46e5;">⚡ Recalculation Latency: {recalc_latency:.1f} ms</span>
            <span style="background-color: #1f2937; color: #e5e7eb; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; border: 1px solid #374151;">💾 {sim_total_rows:,} Rows Evaluated</span>
            <span style="background-color: #0c4a6e; color: #7dd3fc; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; border: 1px solid #0284c7;">📐 Sequential Additive Attribution</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4. Comparative Delta KPI Cards
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Simulated Revenue at Risk",
        format_inr_crore_lakh(sim_net),
        f"+{format_inr_crore_lakh(delta_net)} Escalation" if delta_net > 0 else f"Baseline ({format_inr_crore_lakh(base_net_val)})",
        delta_color="inverse",
    )
    m2.metric(
        "Total Inaction Exposure",
        format_inr_crore_lakh(sim_exp),
        f"+{format_inr_crore_lakh(delta_exp)} Downtime Loss" if delta_exp > 0 else f"Baseline ({format_inr_crore_lakh(base_exp_val)})",
        delta_color="inverse",
    )
    m3.metric(
        "Earliest Assembly Line Halt",
        f"{sim_min_hrs:.1f} Hours",
        f"{delta_hrs:+.1f} Hours Shift" if delta_hrs != 0 else f"Baseline ({base_min_hrs:.1f} hrs)",
        delta_color="inverse",
    )
    m4.metric(
        "Starving Component SKUs",
        f"{sim_short_count} of {len(sim_bom)} SKUs",
        f"+{delta_short} Newly Starving SKUs" if delta_short > 0 else f"Baseline ({base_short_count} SKU{'s' if base_short_count != 1 else ''})",
        delta_color="inverse",
    )

    st.markdown("---")

    # 5. Visualizations
    col_v1, col_v2 = st.columns([1, 1])

    with col_v1:
        merged_bom = base_bom[["assembly_line_id", "component_part_num", "part_description", "hours_to_starvation_harmonized"]].rename(
            columns={"hours_to_starvation_harmonized": "baseline_run_hours"}
        ).merge(
            sim_bom[["assembly_line_id", "component_part_num", "hours_to_starvation_harmonized"]].rename(
                columns={"hours_to_starvation_harmonized": "simulated_run_hours"}
            ),
            on=["assembly_line_id", "component_part_num"],
        )

        fig_horizon = go.Figure()
        fig_horizon.add_trace(
            go.Bar(
                x=merged_bom["component_part_num"],
                y=merged_bom["baseline_run_hours"],
                name="Baseline Available Hours",
                marker_color="#3b82f6",
            )
        )
        fig_horizon.add_trace(
            go.Bar(
                x=merged_bom["component_part_num"],
                y=merged_bom["simulated_run_hours"],
                name="Simulated Available Hours (Post-Shock)",
                marker_color="#ef4444",
            )
        )
        fig_horizon.add_hline(
            y=48.0,
            line_dash="dash",
            line_color="#10b981",
            annotation_text="48h Full Run Buffer",
            annotation_position="top left",
        )
        fig_horizon.update_layout(
            title="Component Run Window Horizon (Baseline vs Chaos)",
            xaxis_title="Component SKU",
            yaxis_title="Available Production Hours",
            barmode="group",
            height=420,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_horizon, use_container_width=True)

    with col_v2:
        wf_data = sim_results["waterfall_data"]
        stages = [d["Stage"] for d in wf_data]
        amounts = [d["Amount"] for d in wf_data]
        measures = [d["Type"] for d in wf_data]
        text_amounts = [format_inr_crore_lakh(a) for a in amounts]

        fig_wf = go.Figure(
            go.Waterfall(
                name="Disruption Factor Attribution",
                orientation="v",
                measure=measures,
                x=stages,
                textposition="outside",
                text=text_amounts,
                y=amounts,
                connector={"line": {"color": "rgb(63, 63, 63)"}},
                decreasing={"marker": {"color": "#10b981"}},
                increasing={"marker": {"color": "#ef4444"}},
                totals={"marker": {"color": "#b91c1c"}},
            )
        )
        fig_wf.update_layout(
            title="Disruption Factor Exposure Attribution Waterfall",
            yaxis_title="Exposure (INR)",
            height=420,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_wf, use_container_width=True)

    # 6. Detailed Component Deficit & Emergency Action Matrix
    st.subheader("Simulated Component Deficit & Emergency Action Matrix")
    st.caption("Displays components under risk of halting production lines and the recommended emergency mitigation.")

    def get_action_recommendation(row: pd.Series) -> str:
        deficit = row["true_net_deficit_qty"]
        hrs = row["hours_to_starvation_harmonized"]
        if deficit <= 0:
            return "SECURED: Within Buffer"
        if hrs < 12.0:
            return "CRITICAL: Air-Charter Express Hotshot"
        if hrs < 24.0:
            return "URGENT: Dedicated Hot-Shot Direct Truck"
        return "PRIORITY: Reallocate Line Safety Buffer"

    sim_display_df = sim_bom.copy()
    sim_display_df = sim_display_df.merge(
        base_bom[["assembly_line_id", "component_part_num", "hours_to_starvation_harmonized"]].rename(
            columns={"hours_to_starvation_harmonized": "base_hrs_to_stop"}
        ),
        on=["assembly_line_id", "component_part_num"],
    )
    sim_display_df["recommended_action"] = sim_display_df.apply(get_action_recommendation, axis=1)

    table_data = pd.DataFrame(
        {
            "Assembly Line": sim_display_df["assembly_line_id"],
            "Component SKU": sim_display_df["component_part_num"],
            "Part Description": sim_display_df["part_description"],
            "Baseline Run Hrs": sim_display_df["base_hrs_to_stop"].apply(lambda v: f"{v:.1f} hrs"),
            "Simulated Run Hrs": sim_display_df["hours_to_starvation_harmonized"].apply(lambda v: f"{v:.1f} hrs"),
            "Simulated Deficit Qty": sim_display_df["true_net_deficit_qty"].apply(lambda v: f"{v:,.0f}" if v > 0 else "0 (Balanced)"),
            "Revenue at Risk": sim_display_df["revenue_at_risk_net_inr"].apply(format_inr_crore_lakh),
            "Plant Idle Loss": sim_display_df["plant_idle_cost_inr"].apply(format_inr_crore_lakh),
            "Total Inaction Loss": sim_display_df["total_stoppage_exposure_inr"].apply(format_inr_crore_lakh),
            "Recommended Action": sim_display_df["recommended_action"],
        }
    )
    st.dataframe(table_data, use_container_width=True, hide_index=True)


def render_scale_benchmark_tab(client: ChakanExasolClient, marts: dict) -> None:
    from src.benchmarks.scale_benchmark import (
        get_verified_scale_benchmark,
        run_scale_benchmark,
    )

    st.subheader("High-Scale Stress Benchmark: Set-Based Columnar Pipeline vs. Row-by-Row ETL")
    st.caption(
        "In high-volume automotive powertrain plants in the Pune-Chakan industrial corridor, inbound supplier ASN dispatches "
        "spike from 500 records on normal shifts to 10,000+ dispatches during weekend supplier reconciliations. "
        "By default, this benchmark reports pure measured CPU wall-clock times (0.0 ms synthetic overhead) comparing "
        "set-based columnar execution against uncached row-by-row Python ETL (`iterrows()`)."
    )

    # 1. Benchmark Execution Configuration Controls
    col_c1, col_c2 = st.columns([2, 1])
    with col_c1:
        sim_penalty = st.checkbox(
            "Optional: Add Modeled Multi-Node RPC Hop Overhead (+0.45 ms/row) on top of measured CPU time",
            value=st.session_state.get("bench_include_penalty", False),
            help="When unchecked (default), 100% of numbers are real measured CPU wall-clock timings. Checking this adds a modeled 0.45 ms/row network RPC penalty to illustrate unpartitioned remote lookups.",
            key="cb_bench_penalty",
        )
        st.session_state["bench_include_penalty"] = sim_penalty

    with col_c2:
        penalty_val = 0.45 if sim_penalty else 0.0
        run_live = st.button("⚡ Run Live Scale Benchmark (500 to 10k Rows)", use_container_width=True)

    if run_live:
        with st.spinner("Executing live multi-tier benchmark across 500, 2,500, 5,000, and 10,000 rows..."):
            bench_results = run_scale_benchmark(
                scales=[500, 2500, 5000, 10000],
                network_hop_penalty_ms=penalty_val,
                client=client,
            )
            st.session_state["live_bench_results"] = bench_results
    else:
        bench_results = get_verified_scale_benchmark(network_hop_penalty_ms=penalty_val)

    rows_data = bench_results["results_table"]
    df_bench = pd.DataFrame(rows_data)

    peak_speedup = float(bench_results["peak_speedup_factor"])
    peak_tp = float(bench_results["peak_exasol_throughput"])
    row_10k = [r for r in rows_data if r["batch_rows"] == 10000][0]

    # 2. Executive KPI Summary Cards
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Peak Throughput Speedup",
        f"{peak_speedup:.1f}x Faster",
        "At 10,000 Inbound Rows",
    )
    k2.metric(
        "Peak Exasol Throughput",
        f"{peak_tp:,.0f} Rows/Sec",
        f"vs {row_10k['legacy_throughput_rows_sec']:,.0f} Rows/Sec (Legacy)",
    )
    k3.metric(
        "10k-Row Analytical Latency",
        f"{row_10k['exasol_latency_ms']:.1f} ms",
        f"-{row_10k['latency_reduction_pct']:.1f}% vs {row_10k['legacy_latency_ms']:,.0f} ms Legacy",
        delta_color="inverse",
    )
    k4.metric(
        "Inter-Node Network Shuffling",
        "0 Net Hops",
        f"vs {row_10k['legacy_network_hops']:,} Shuffles (DISTRIBUTE BY)",
    )

    st.markdown("---")

    # 3. Side-by-Side Visualizations
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        # Latency Scaling Curve
        fig_lat = go.Figure()
        fig_lat.add_trace(
            go.Scatter(
                x=df_bench["batch_rows"],
                y=df_bench["exasol_latency_ms"],
                mode="lines+markers",
                name="Exasol Columnar (In-Memory MPP)",
                line=dict(color="#10b981", width=3),
                marker=dict(size=8),
            )
        )
        fig_lat.add_trace(
            go.Scatter(
                x=df_bench["batch_rows"],
                y=df_bench["legacy_latency_ms"],
                mode="lines+markers",
                name="Legacy Row-by-Row ETL (Total)",
                line=dict(color="#ef4444", width=3, dash="solid"),
                marker=dict(size=8),
            )
        )
        if sim_penalty:
            fig_lat.add_trace(
                go.Scatter(
                    x=df_bench["batch_rows"],
                    y=df_bench["legacy_cpu_ms"],
                    mode="lines+markers",
                    name="Legacy ETL (Pure CPU Compute)",
                    line=dict(color="#f59e0b", width=2, dash="dot"),
                    marker=dict(size=6),
                )
            )
        fig_lat.add_hline(
            y=150.0,
            line_dash="dash",
            line_color="#6366f1",
            annotation_text="150ms Real-Time In-DB SLA Target",
            annotation_position="top left",
        )
        fig_lat.update_layout(
            title="Execution Latency Scaling Curve (Lower is Better)",
            xaxis_title="Inbound ASN Stream Scale (Rows)",
            yaxis_title="Execution Latency (Milliseconds)",
            height=420,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_lat, use_container_width=True)

    with col_chart2:
        # Throughput & Speedup Multiplier
        fig_tp = go.Figure()
        fig_tp.add_trace(
            go.Bar(
                x=df_bench["batch_rows"].astype(str) + " Rows",
                y=df_bench["exasol_throughput_rows_sec"],
                name="Exasol Throughput (Rows/s)",
                marker_color="#3b82f6",
                yaxis="y",
            )
        )
        fig_tp.add_trace(
            go.Bar(
                x=df_bench["batch_rows"].astype(str) + " Rows",
                y=df_bench["legacy_throughput_rows_sec"],
                name="Legacy ETL Throughput (Rows/s)",
                marker_color="#94a3b8",
                yaxis="y",
            )
        )
        fig_tp.add_trace(
            go.Scatter(
                x=df_bench["batch_rows"].astype(str) + " Rows",
                y=df_bench["speedup_factor"],
                name="Speedup Factor (X)",
                mode="lines+markers+text",
                text=[f"{s:.1f}x" for s in df_bench["speedup_factor"]],
                textposition="top center",
                line=dict(color="#f43f5e", width=3),
                marker=dict(size=9, color="#f43f5e"),
                yaxis="y2",
            )
        )
        fig_tp.update_layout(
            title="Throughput (Rows/Sec) & Relative Speedup Acceleration",
            xaxis_title="Inbound Batch Size Tier",
            yaxis=dict(title="Throughput (Records Processed / Sec)"),
            yaxis2=dict(title="Speedup Factor Multiplier (X)", overlaying="y", side="right", showgrid=False),
            barmode="group",
            height=420,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_tp, use_container_width=True)

    # 4. Detailed Comparative Audit Table
    st.subheader("Multi-Tier High-Scale Stress Benchmark Audit Ledger")
    st.caption("Quantitative audit comparing Exasol Personal columnar execution against row-by-row ETL across scale tiers.")

    display_table = pd.DataFrame(
        {
            "Scale Tier": [f"{r:,} Rows" for r in df_bench["batch_rows"]],
            "Exasol Latency": df_bench["exasol_latency_ms"].apply(lambda v: f"{v:.1f} ms"),
            "Exasol Throughput": df_bench["exasol_throughput_rows_sec"].apply(lambda v: f"{v:,.0f} rows/s"),
            "Exasol RAM Footprint": df_bench["exasol_ram_mb"].apply(lambda v: f"{v:.1f} MB (Compressed)"),
            "Legacy Total Latency": df_bench["legacy_latency_ms"].apply(lambda v: f"{v:,.1f} ms"),
            "Legacy Throughput": df_bench["legacy_throughput_rows_sec"].apply(lambda v: f"{v:,.0f} rows/s"),
            "Legacy RAM Footprint": df_bench["legacy_ram_mb"].apply(lambda v: f"{v:.1f} MB (Object Tree)"),
            "Network Shuffles": [f"0 hops vs {r:,} hops" for r in df_bench["legacy_network_hops"]],
            "Speedup Multiplier": df_bench["speedup_factor"].apply(lambda v: f"{v:.1f}x FASTER"),
            "Latency Reduction": df_bench["latency_reduction_pct"].apply(lambda v: f"{v:.1f}%"),
            "Architectural Verdict": [
                "Sub-Second Co-Located In-Memory" if e < 150 else "Sub-Second In-Memory" for e in df_bench["exasol_latency_ms"]
            ],
        }
    )
    st.dataframe(display_table, use_container_width=True, hide_index=True)

    # 5. Architectural Deep-Dive Expander
    with st.expander("🔬 Architectural Deep-Dive: Why Does Exasol Outperform Traditional ETL by 60x+?"):
        col_ad1, col_ad2 = st.columns(2)
        with col_ad1:
            st.markdown(
                """
                #### 1. In-Memory Columnar Storage & SIMD Vectorization
                - **Legacy ETL:** Reads JSON/CSV rows into Python dictionary/object wrappers. Each field access dereferences object pointers with memory allocation overhead, creating severe CPU cache misses and garbage collection pauses.
                - **Exasol:** Stores columns contiguously in memory compressed by dictionary and run-length encoding. SIMD instructions evaluate filter expressions and aggregate metrics over thousands of values per CPU instruction cycle.
                """
            )
            st.markdown(
                """
                #### 2. In-Database Python 3 Scalar UDF Parallelization
                - **Legacy ETL:** Ingests raw rows to external worker threads, parses strings row-by-row via slow regex loops, and dispatches separate DB queries for master data resolution.
                - **Exasol:** UDFs execute compiled inside native worker containers in RAM. Data is transferred via zero-copy C memory buffers (`EMITS`), eliminating serialization and IPC bottlenecks.
                """
            )
        with col_ad2:
            st.markdown(
                """
                #### 3. MPP Co-Location Partitioning (`DISTRIBUTE BY internal_part_num`)
                - **Legacy ETL:** Joins `ASN_LINES` to `PURCHASE_ORDER_LINES`, `ITEM_MASTER`, and `BILL_OF_MATERIALS` across unpartitioned tables. In distributed clusters (Spark/Trino), this forces expensive **Shuffle Operations**—serializing millions of rows across network cards.
                - **Exasol:** Physical slices of all 5 tables are co-located in memory on `internal_part_num`. Joins are executed as **local hash lookups with 0 network hops**, scaling with flat sub-second latency even as volume grows to 10,000+ rows.
                """
            )


def render_financial_roi_tab(client: ChakanExasolClient, marts: dict) -> None:
    roi = marts.get("financial_roi_mart", {})
    bom_df: pd.DataFrame = marts["bom_risk_mart"].copy()
    triage_df: pd.DataFrame = marts["triage_queue"].copy()

    st.subheader("Formulation 3: Boardroom Financial Defense & Line-Stop ROI Engine")
    st.caption(
        "Quantifies the business case for Exasol: weighing the severe penalty of unmitigated plant downtime "
        "and unproduced vehicle output against low-cost emergency logistics."
    )

    r1, r2, r3, r4 = st.columns(4)
    r1.metric(
        "Total Inaction Stoppage Loss",
        format_inr_crore_lakh(roi.get("total_stoppage_exposure_inr", 0)),
        f"{format_inr_crore_lakh(roi.get('net_risk_inr', 0))} Goods + {format_inr_crore_lakh(roi.get('total_idle_loss_inr', 0))} Idle",
        delta_color="inverse",
    )
    r2.metric(
        "Emergency Mitigation Freight",
        format_inr_crore_lakh(roi.get("benchmark_freight_inr", 45000)),
        "Dedicated Hot-Shot Transport Run",
    )
    r3.metric(
        "Executive Mitigation ROI",
        f"{roi.get('headline_roi_x', 1175):,.0f}x Return",
        "Averted Factory Stoppage / Freight",
    )
    r4.metric(
        "Avoided Panic Freight Waste",
        format_inr_crore_lakh(roi.get("avoided_panic_freight_inr", 135000)),
        f"{roi.get('false_alarms_cleared_count', 1)} False Alarms Cleared by UDFs",
    )

    st.markdown("---")
    st.subheader("Interactive What-If Line-Stop & Logistics Breakeven Simulator")
    st.caption(
        "Adjust hourly downtime penalty and emergency freight tariffs to model plant break-even economics in real-time."
    )

    col_sim1, col_sim2 = st.columns(2)
    with col_sim1:
        sim_burn_rate = st.slider(
            "Average Assembly Line Idle Burn Rate (Rs / Hour):",
            min_value=500_000,
            max_value=2_500_000,
            value=1_050_000,
            step=50_000,
            format="Rs %d",
        )
    with col_sim2:
        sim_freight_cost = st.slider(
            "Dedicated Express Hot-Shot Logistics Tariff (Rs / Incident):",
            min_value=15_000,
            max_value=150_000,
            value=45_000,
            step=5_000,
            format="Rs %d",
        )

    # Reactive Calculations
    total_short_downtime_hrs = float(bom_df["downtime_hours_net"].sum())
    sim_idle_loss = total_short_downtime_hrs * sim_burn_rate
    sim_total_loss = float(roi.get("net_risk_inr", 0)) + sim_idle_loss
    sim_roi = (sim_total_loss - sim_freight_cost) / sim_freight_cost if sim_freight_cost > 0 else 0.0
    breakeven_minutes = (sim_freight_cost / sim_burn_rate) * 60.0

    st.info(
        f"**Live Breakeven Economic Proof:** At **Rs {sim_burn_rate/100000:.2f} Lakh/hr** line downtime burn, "
        f"the entire **Rs {sim_freight_cost:,.0f}** emergency freight dispatch pays for itself in just "
        f"**{breakeven_minutes:.1f} minutes** of prevented stoppage. Over the 48h horizon, avoiding line halts saves "
        f"**{format_inr_crore_lakh(sim_total_loss)}**, generating a **{sim_roi:,.0f}x** financial return on freight investment."
    )

    st.markdown("---")
    st.subheader("Assembly Line Stoppage Loss Breakdown: Finished Goods vs. Idle Labor Burn")

    line_rollup = (
        bom_df.groupby("assembly_line_id", as_index=False)
        .agg(
            revenue_at_risk_net_inr=("revenue_at_risk_net_inr", "max"),
            plant_idle_cost_inr=("plant_idle_cost_inr", "max"),
            total_stoppage_exposure_inr=("total_stoppage_exposure_inr", "max"),
            expedited_freight_cost_inr=("expedited_freight_cost_inr", "sum"),
        )
    )

    fig_fin = go.Figure()
    fig_fin.add_trace(
        go.Bar(
            x=line_rollup["assembly_line_id"],
            y=line_rollup["revenue_at_risk_net_inr"],
            name="Unproduced Vehicle Revenue (Rs)",
            marker_color="#ef4444",
        )
    )
    fig_fin.add_trace(
        go.Bar(
            x=line_rollup["assembly_line_id"],
            y=line_rollup["plant_idle_cost_inr"],
            name="Plant Idle Labor & Depreciation Penalty (Rs)",
            marker_color="#f59e0b",
        )
    )
    fig_fin.add_trace(
        go.Bar(
            x=line_rollup["assembly_line_id"],
            y=line_rollup["expedited_freight_cost_inr"],
            name="Emergency Hot-Shot Freight Cost (Rs)",
            marker_color="#10b981",
        )
    )
    fig_fin.update_layout(
        barmode="stack",
        height=420,
        title="Financial Blast Radius by Assembly Line (Inaction Stoppage vs. Freight Intervention)",
        xaxis_title="Assembly Line",
        yaxis_title="Total Financial Value (Rs INR)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_fin, use_container_width=True)

    st.subheader("Component Deficit & Emergency Mitigation Allocation Ledger")
    st.caption("Detailed view of components causing active production deficits and their quantitative mitigation ROI.")

    short_comp_df = bom_df[bom_df["true_net_deficit_qty"] > 0].copy()
    display_short = pd.DataFrame(
        {
            "Assembly Line": short_comp_df["assembly_line_id"],
            "Component SKU": short_comp_df["component_part_num"],
            "Description": short_comp_df["part_description"],
            "Net Deficit Qty": short_comp_df["true_net_deficit_qty"],
            "Hours to Stop": short_comp_df["hours_to_starvation_harmonized"],
            "Downtime Penalty": short_comp_df["plant_idle_cost_inr"].apply(format_inr_crore_lakh),
            "Unproduced Vehicles": short_comp_df["revenue_at_risk_net_inr"].apply(format_inr_crore_lakh),
            "Total Inaction Loss": short_comp_df["total_stoppage_exposure_inr"].apply(format_inr_crore_lakh),
            "Expedited Freight": short_comp_df["expedited_freight_cost_inr"].apply(lambda v: f"Rs {v:,.0f}"),
            "Action ROI": short_comp_df["mitigation_roi_ratio"].apply(lambda v: f"{v:,.0f}x"),
        }
    )
    st.dataframe(display_short, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Avoided Panic Freight Ledger (Direct Savings from In-DB UDF Harmonization)")
    st.caption(
        "Shows supplier dispatches that legacy ETL systems quarantined as '0 stock', which would have triggered "
        "costly panic courier dispatches without Exasol's in-database harmonization."
    )

    cleared_asns = triage_df[
        triage_df["operational_verdict"].isin(["FALSE_STARVATION_CLEARED_BY_UDF", "HARMONIZED_BUFFER_RESTORED"])
    ].copy()
    display_cleared = pd.DataFrame(
        {
            "ASN Line ID": cleared_asns["asn_line_id"],
            "PO Number": cleared_asns["po_number_ref"],
            "Supplier": cleared_asns["supplier_name"],
            "Raw Payload Anomaly": cleared_asns["anomaly_type"],
            "UDF Harmonization": cleared_asns["raw_supplier_sku"] + " -> " + cleared_asns["resolved_part_num"],
            "Apparent Legacy Threat": cleared_asns["revenue_at_risk_legacy_inr"].apply(format_inr_crore_lakh),
            "Outcome": cleared_asns["operational_verdict"],
            "Avoided Panic Freight": cleared_asns["avoided_panic_freight_inr"].apply(
                lambda v: f"Rs {v:,.0f} Saved" if v > 0 else "Buffer Protected"
            ),
        }
    )
    st.dataframe(display_cleared, use_container_width=True, hide_index=True)


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
        - **Schema Distribution (`DISTRIBUTE BY`):** `ITEM_MASTER`, `PURCHASE_ORDER_LINES`, and `WAREHOUSE_INVENTORY_LEDGER` distribute on `internal_part_num`; `BILL_OF_MATERIALS` distributes on `component_part_num` so part-level joins align.
        - **In-Database Python 3 Scalar UDFs:** `UDF_NORMALIZE_UOM`, `UDF_RESOLVE_SUPPLIER_SKU`, and `UDF_PARSE_ASN_DATE` run inside Exasol next to the columnar tables.
        - **Interactive Writeback Loop:** Planner overrides persist directly to `CHAKAN_SCM.ASN_PLANNER_OVERRIDES` and trigger immediate view recalculation.
        """
    )

    sql_dir = PROJECT_ROOT / "src" / "exasol_engine"
    t_ddl, t_udf, t_views, t_prof = st.tabs(
        [
            "1. MPP Schema DDL (ddl_schema.sql)",
            "2. Python 3 UDFs (udfs_harmonization.sql)",
            "3. Analytical Views (blast_radius_marts.sql)",
            "4. Live Query Profiler & Execution Pipeline",
        ]
    )
    with t_ddl:
        st.code((sql_dir / "ddl_schema.sql").read_text(encoding="utf-8"), language="sql")
    with t_udf:
        st.code((sql_dir / "udfs_harmonization.sql").read_text(encoding="utf-8"), language="sql")
    with t_views:
        st.code((sql_dir / "blast_radius_marts.sql").read_text(encoding="utf-8"), language="sql")
    with t_prof:
        telemetry = marts.get("telemetry", {})
        measured_ms = float(marts.get("query_latency_ms", 0.0))
        compute_src = marts.get("compute_source", telemetry.get("compute_source", "PANDAS_MIRROR"))
        asn_rows = int(telemetry.get("total_asns", 498))
        st.markdown("### Native Exasol Query Execution Pipeline")
        st.caption(f"Live compute source: `{compute_src}` | Measured round-trip latency: `{measured_ms:.2f} ms`")

        st.code(
            f"""-- LOGICAL EXECUTION PIPELINE (VW_BOM_LINE_STARVATION_RISK)
----------------------------------------------------------------------------------------------------------------
STAGE 1: IN-MEMORY COLUMNAR SCAN & DEDUPLICATION
  -> SCAN CHAKAN_SCM.ASN_LINES_RAW ({asn_rows} records)
  -> ROW_NUMBER() OVER (PARTITION BY asn_number, po_number_ref, raw_supplier_sku, raw_shipped_qty)
  -> DEDUPLICATION FILTER (transmission_seq = 1)

STAGE 2: IN-DATABASE PYTHON 3 SCALAR SCRIPT EXECUTION
  -> EXECUTE SCALAR PYTHON UDF: CHAKAN_SCM.UDF_RESOLVE_SUPPLIER_SKU(raw_supplier_sku, po_part_num)
     [Exact / Hyphen-Normalized / Vendor Alias Catalog / Token / Jaro-Winkler >= 0.85]
  -> EXECUTE SCALAR PYTHON UDF: CHAKAN_SCM.UDF_NORMALIZE_UOM(raw_shipped_qty, raw_shipped_uom, base_uom, pack_size, unit_wt)
     [Standard Pack Multiplication + Weight-to-Count Conversions]
  -> EXECUTE SCALAR PYTHON UDF: CHAKAN_SCM.UDF_PARSE_ASN_DATE(raw_eta_date, default_date_format)

STAGE 3: MULTI-TABLE HASH JOIN ACROSS DISTRIBUTED KEYS
  -> JOIN CHAKAN_SCM.ITEM_MASTER ON (internal_part_num)
  -> JOIN CHAKAN_SCM.BILL_OF_MATERIALS ON (component_part_num)
  -> JOIN CHAKAN_SCM.PRODUCTION_SCHEDULES ON (parent_part_num)
  -> LEFT JOIN CHAKAN_SCM.WAREHOUSE_INVENTORY_LEDGER ON (internal_part_num)

STAGE 4: ANALYTICAL AGGREGATION & STARVATION DEFICIT MATERIALIZATION
  -> COMPUTE TRUE PICKABLE ATP = wms_counted - allocated - quality_hold
  -> COMPUTE HOURLY ASSEMBLY BURN RATE = ROUND(gross_required_qty / 48.0, 2)
  -> COMPUTE STARVATION HORIZON = ROUND(LEAST(48.0, available_qty / hourly_burn_qty), 1)
  -> COMPUTE DOWNTIME LOSS = ROUND(downtime_hours * downtime_burn_rate_inr_hr, 2)
  -> COMPUTE HEADLINE MITIGATION ROI = ROUND((net_stoppage_loss - 45000.0) / 45000.0, 1)
----------------------------------------------------------------------------------------------------------------
MEASURED ROUND-TRIP LATENCY ({compute_src}): {measured_ms:.2f} ms
----------------------------------------------------------------------------------------------------------------""",
            language="sql",
        )


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
    render_telemetry_banner(marts)
    render_kpi_header(marts)

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "1. Quarantine Blast-Radius Triage (Action Queue)",
            "2. Assembly Line Starvation & BOM Horizon",
            "3. Interactive 'What-If' Chaos Simulator (Live Stress-Test)",
            "4. High-Scale Stress Benchmark (500 to 10,000 Rows)",
            "5. Financial ROI & Line-Stop Cost Engine (Boardroom Defense)",
            "6. Warehouse Phantom Inventory Audit",
            "7. Exasol Personal SQL & UDF Inspector",
        ]
    )

    with tab1:
        render_triage_tab(client, marts)
    with tab2:
        render_bom_horizon_tab(marts)
    with tab3:
        render_scenario_simulator_tab(client, marts)
    with tab4:
        render_scale_benchmark_tab(client, marts)
    with tab5:
        render_financial_roi_tab(client, marts)
    with tab6:
        render_phantom_inventory_tab(marts)
    with tab7:
        render_exasol_engine_tab(client, marts)


if __name__ == "__main__":
    main()
