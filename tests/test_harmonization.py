from datetime import date

from src.exasol_engine.db_client import ChakanExasolClient
from src.exasol_engine.harmonizer_core import (
    normalize_uom_quantity,
    parse_asn_date,
    resolve_supplier_sku,
)


def test_uom_normalization_pack_and_weight_inversions() -> None:
    assert normalize_uom_quantity(22.0, "BOX_100", "EA") == 2200.0
    assert normalize_uom_quantity(26.0, "BAG_250", "EA") == 6500.0
    assert normalize_uom_quantity(12.0, "CRATE_50", "EA") == 600.0
    assert normalize_uom_quantity(3.15, "MT", "KG") == 3150.0
    assert normalize_uom_quantity(3.312, "MT", "EA", unit_weight_kg=18.4) == 180.0


def test_supplier_sku_drift_resolution() -> None:
    sku, method, conf = resolve_supplier_sku("6204ZZ", "ENG-BRG-6204-01")
    assert sku == "ENG-BRG-6204-01"
    assert method == "VENDOR_CATALOG_ALIAS"
    assert conf >= 0.90

    sku_h, method_h, _ = resolve_supplier_sku("ENGGSKMLS06", "ENG-GSK-MLS-06")
    assert sku_h == "ENG-GSK-MLS-06"
    assert method_h == "HYPHEN_NORMALIZED"


def test_multiformat_date_parsing() -> None:
    assert parse_asn_date("12/10/2026", "DD/MM/YYYY") == date(2026, 10, 12)
    assert parse_asn_date("10/12/2026", "MM/DD/YYYY") == date(2026, 10, 12)
    assert parse_asn_date("2026-10-12", "YYYY-MM-DD") == date(2026, 10, 12)


def test_blast_radius_analytical_marts(tmp_path) -> None:
    client = ChakanExasolClient(data_dir=str(tmp_path))
    marts = client.compute_analytical_marts()

    inv_df = marts["inventory_mart"]
    assert (inv_df["phantom_inventory_qty"] >= 0).all()
    assert inv_df["phantom_inventory_value_inr"].sum() > 0

    triage_df = marts["triage_queue"]
    assert len(triage_df) >= 10
    verdicts = set(triage_df["operational_verdict"].unique())
    assert "CRITICAL_SHORT_SHIPMENT_EXPOSED" in verdicts
    assert "FALSE_STARVATION_CLEARED_BY_UDF" in verdicts
    assert "DUPLICATE_PAYLOAD_SUPPRESSED" in verdicts

    initial_net_risk = float(marts["bom_risk_mart"]["revenue_at_risk_net_inr"].sum())
    assert initial_net_risk > 0

    client.approve_harmonization_override(
        asn_line_id="ASN-L-9011",
        resolved_part_num="AXL-HUB-DUC-14",
        normalized_qty=600.0,
        normalized_uom="EA",
        normalized_eta_date="2026-10-12",
        action="EXPEDITED_SHORTFALL_COVERED",
    )
    updated_marts = client.compute_analytical_marts()
    updated_net_risk = float(updated_marts["bom_risk_mart"]["revenue_at_risk_net_inr"].sum())
    assert updated_net_risk < initial_net_risk

    client.reset_planner_overrides()
    reset_marts = client.compute_analytical_marts()
    assert float(reset_marts["bom_risk_mart"]["revenue_at_risk_net_inr"].sum()) == initial_net_risk


def test_financial_roi_and_downtime_cost_engine(tmp_path) -> None:
    client = ChakanExasolClient(data_dir=str(tmp_path))
    marts = client.compute_analytical_marts()

    roi_mart = marts["financial_roi_mart"]
    assert roi_mart is not None
    assert roi_mart["headline_roi_x"] >= 1170.0  # Approx 1,175x ROI
    assert roi_mart["net_risk_inr"] > 50_000_000.0  # Rs 5.29 Cr
    assert roi_mart["total_idle_loss_inr"] > 20_000_000.0  # Rs 2.63 Cr
    assert roi_mart["total_stoppage_exposure_inr"] > 75_000_000.0  # Rs 7.92 Cr
    assert roi_mart["avoided_panic_freight_inr"] >= 135_000.0  # Rs 1.35 L

    bom_risk = marts["bom_risk_mart"]
    assert "downtime_hours_net" in bom_risk.columns
    assert "plant_idle_cost_inr" in bom_risk.columns
    assert "total_stoppage_exposure_inr" in bom_risk.columns
    assert "expedited_freight_cost_inr" in bom_risk.columns

    # Short components should have positive freight and downtime cost
    short_rows = bom_risk[bom_risk["true_net_deficit_qty"] > 0]
    assert len(short_rows) > 0
    assert (short_rows["expedited_freight_cost_inr"] > 0).all()
    assert (short_rows["plant_idle_cost_inr"] > 0).all()

    # Secured components should have 0 downtime loss and 0 freight cost
    secured_rows = bom_risk[bom_risk["true_net_deficit_qty"] == 0]
    assert (secured_rows["expedited_freight_cost_inr"] == 0).all()
    assert (secured_rows["plant_idle_cost_inr"] == 0).all()

    # Triage queue has mitigation_roi_x and avoided_panic_freight_inr
    triage = marts["triage_queue"]
    assert "mitigation_roi_x" in triage.columns
    assert "avoided_panic_freight_inr" in triage.columns


def test_telemetry_and_query_profiler(tmp_path) -> None:
    client = ChakanExasolClient(data_dir=str(tmp_path))
    marts = client.compute_analytical_marts()

    assert "telemetry" in marts
    telemetry = marts["telemetry"]

    assert telemetry["engine_mode"] in ("EXASOL_PERSONAL", "LOCAL_MIRROR")
    assert telemetry["latency_ms"] > 0
    assert telemetry["latency_sla_target_ms"] == 15.0
    assert telemetry["total_rows_evaluated"] >= 500
    assert telemetry["colocation_key"] == "internal_part_num"
    assert telemetry["colocation_status"] == "CO_LOCATED_ACTIVE"
    assert telemetry["mpp_network_hops"] == 0
    assert telemetry["udf_engine"] == "PYTHON3_IN_DB_RAM"

    stages = telemetry["latency_stages_ms"]
    assert len(stages) == 4
    for stage_name, stage_latency in stages.items():
        assert stage_latency >= 0.0

    counts = telemetry["table_row_counts"]
    assert counts["ASN_LINES_RAW"] >= 400
    assert counts["ITEM_MASTER"] >= 15
    assert counts["BILL_OF_MATERIALS"] >= 15



