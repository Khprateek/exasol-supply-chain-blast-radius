from datetime import date
import pytest

from src.exasol_engine.db_client import (
    ChakanExasolClient,
    ExasolBootstrapError,
    ExasolWriteError,
)
from src.exasol_engine.harmonizer_core import (
    jaro_winkler_similarity,
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


def test_supplier_sku_drift_and_jaro_winkler_resolution() -> None:
    sku, method, conf = resolve_supplier_sku("6204ZZ", "ENG-BRG-6204-01")
    assert sku == "ENG-BRG-6204-01"
    assert method == "VENDOR_CATALOG_ALIAS"
    assert conf >= 0.90

    sku_h, method_h, _ = resolve_supplier_sku("ENGGSKMLS06", "ENG-GSK-MLS-06")
    assert sku_h == "ENG-GSK-MLS-06"
    assert method_h == "HYPHEN_NORMALIZED"

    # Genuine Jaro-Winkler similarity (>= 0.85 threshold) on OCR/typo SKUs
    assert jaro_winkler_similarity("FBD6204Z", "FBD6204ZZ") >= 0.90
    sku_jw, method_jw, conf_jw = resolve_supplier_sku("FBD6204Z", None)
    assert sku_jw == "ENG-BRG-6204-01"
    assert method_jw == "JARO_WINKLER_FUZZY"
    assert conf_jw >= 0.85


def test_multiformat_date_parsing() -> None:
    assert parse_asn_date("12/10/2026", "DD/MM/YYYY") == date(2026, 10, 12)
    assert parse_asn_date("10/12/2026", "MM/DD/YYYY") == date(2026, 10, 12)
    assert parse_asn_date("2026-10-12", "YYYY-MM-DD") == date(2026, 10, 12)


def test_blast_radius_analytical_marts(tmp_path) -> None:
    client = ChakanExasolClient(data_dir=str(tmp_path))
    marts = client.compute_analytical_marts(source="pandas")

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
    updated_marts = client.compute_analytical_marts(source="pandas")
    updated_net_risk = float(updated_marts["bom_risk_mart"]["revenue_at_risk_net_inr"].sum())
    assert updated_net_risk < initial_net_risk

    client.reset_planner_overrides()
    reset_marts = client.compute_analytical_marts(source="pandas")
    assert float(reset_marts["bom_risk_mart"]["revenue_at_risk_net_inr"].sum()) == initial_net_risk


def test_financial_roi_and_downtime_cost_engine(tmp_path) -> None:
    client = ChakanExasolClient(data_dir=str(tmp_path))
    marts = client.compute_analytical_marts(source="pandas")

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

    short_rows = bom_risk[bom_risk["true_net_deficit_qty"] > 0]
    assert len(short_rows) > 0
    assert (short_rows["expedited_freight_cost_inr"] > 0).all()
    assert (short_rows["plant_idle_cost_inr"] > 0).all()

    secured_rows = bom_risk[bom_risk["true_net_deficit_qty"] == 0]
    assert (secured_rows["expedited_freight_cost_inr"] == 0).all()
    assert (secured_rows["plant_idle_cost_inr"] == 0).all()

    triage = marts["triage_queue"]
    assert "mitigation_roi_x" in triage.columns
    assert "avoided_panic_freight_inr" in triage.columns


def test_telemetry_and_query_profiler(tmp_path) -> None:
    client = ChakanExasolClient(data_dir=str(tmp_path))
    marts = client.compute_analytical_marts(source="pandas")

    assert "telemetry" in marts
    telemetry = marts["telemetry"]

    assert telemetry["engine_mode"] in ("EXASOL_PERSONAL", "LOCAL_MIRROR")
    assert telemetry["compute_source"] in ("EXASOL_VIEWS", "PANDAS_MIRROR")
    assert telemetry["latency_ms"] > 0
    assert telemetry["total_rows_evaluated"] >= 500
    assert telemetry["colocation_key"] == "internal_part_num"
    assert "component_part_num" in telemetry["colocation_keys"]
    assert telemetry["colocation_status"] in ("CO_LOCATED_ACTIVE", "MIRROR_IN_PROCESS")
    assert telemetry["udf_engine"] in ("PYTHON3_IN_DB_RAM", "PYTHON_APP_PROCESS")

    stages = telemetry["latency_stages_ms"]
    assert len(stages) == 4
    for _, stage_latency in stages.items():
        assert stage_latency >= 0.0

    counts = telemetry["table_row_counts"]
    assert counts["ASN_LINES_RAW"] >= 400
    assert counts["ITEM_MASTER"] >= 15
    assert counts["BILL_OF_MATERIALS"] >= 15


def test_what_if_scenario_simulation_additive_waterfall(tmp_path) -> None:
    client = ChakanExasolClient(data_dir=str(tmp_path))

    # 1. Null Shock (Zero chaos parameters must equal baseline exactly)
    null_sim = client.compute_simulation_marts(
        transit_delay_days=0,
        quarantine_defect_pct=0.0,
        demand_surge_multiplier=1.0,
    )
    assert null_sim["delta_net_risk_inr"] == 0.0
    assert null_sim["delta_total_exposure_inr"] == 0.0
    assert null_sim["delta_min_hours_to_halt"] == 0.0

    # 2. Compound Disruption Shock (+3 days delay, 20% quarantine defect, 1.25x demand surge)
    shock_sim = client.compute_simulation_marts(
        transit_delay_days=3,
        quarantine_defect_pct=0.20,
        demand_surge_multiplier=1.25,
    )

    base_net = shock_sim["baseline"]["financial_roi_mart"]["net_risk_inr"]
    sim_net = shock_sim["simulated"]["financial_roi_mart"]["net_risk_inr"]
    assert sim_net > base_net
    assert shock_sim["delta_net_risk_inr"] > 0
    assert shock_sim["delta_total_exposure_inr"] > 0

    # Check Waterfall Stages AND strict additivity (sum of relative stages == total)
    wf = shock_sim["waterfall_data"]
    assert len(wf) == 5
    assert wf[0]["Stage"] == "1. Baseline True Shortage"
    assert wf[0]["Amount"] == base_net
    assert wf[4]["Stage"] == "Total Simulated Exposure"
    assert wf[4]["Amount"] == sim_net
    assert sum(step["Amount"] for step in wf[:4]) == pytest.approx(wf[4]["Amount"], abs=0.01)

    # Starvation run hours must be reduced or equal under shock
    base_hrs = shock_sim["baseline"]["bom_risk_mart"]["hours_to_starvation_harmonized"]
    sim_hrs = shock_sim["simulated"]["bom_risk_mart"]["hours_to_starvation_harmonized"]
    assert (sim_hrs <= base_hrs).all()


def test_scale_benchmark_suite() -> None:
    from src.benchmarks.scale_benchmark import (
        get_verified_scale_benchmark,
        run_scale_benchmark,
    )

    # 1. Pure Measured CPU Benchmark Integrity (0.0 ms synthetic network penalty)
    bench = get_verified_scale_benchmark(network_hop_penalty_ms=0.0)
    assert bench["max_scale_rows"] == 10000
    assert bench["network_hop_penalty_ms"] == 0.0
    assert bench["peak_cpu_speedup_factor"] >= 10.0
    assert len(bench["results_table"]) == 4

    for row in bench["results_table"]:
        assert row["legacy_network_ms"] == 0.0
        assert row["exasol_latency_ms"] < 250.0
        assert row["speedup_cpu_only"] >= 1.0

    row_10k = [r for r in bench["results_table"] if r["batch_rows"] == 10000][0]
    assert row_10k["speedup_cpu_only"] >= 10.0

    # 2. Live Dynamic Scaling Test (Fast subset 500 rows, zero synthetic penalty)
    live_res = run_scale_benchmark(scales=[500], network_hop_penalty_ms=0.0)
    assert len(live_res["results_table"]) == 1
    assert live_res["results_table"][0]["legacy_network_ms"] == 0.0
    assert live_res["results_table"][0]["exasol_latency_ms"] < 250.0


def test_broken_connection_raises_explicit_errors(tmp_path) -> None:
    class BrokenConn:
        def execute(self, *args, **kwargs):
            raise RuntimeError("Simulated database failure")

        def import_from_pandas(self, *args, **kwargs):
            raise RuntimeError("Simulated bulk import failure")

    client = ChakanExasolClient(data_dir=str(tmp_path))
    client.conn = BrokenConn()

    with pytest.raises(ExasolBootstrapError):
        client.bootstrap_exasol_schema_and_data()

    client.conn = BrokenConn()
    with pytest.raises(ExasolWriteError):
        client.approve_harmonization_override(
            asn_line_id="ASN-L-9011",
            resolved_part_num="AXL-HUB-DUC-14",
            normalized_qty=600.0,
            normalized_uom="EA",
            normalized_eta_date="2026-10-12",
        )


def test_exasol_views_match_pandas_mirror(tmp_path) -> None:
    client = ChakanExasolClient(data_dir=str(tmp_path))
    if not client.connect():
        pytest.skip("Exasol Personal container not reachable on localhost:8563")

    mode, _ = client.bootstrap_exasol_schema_and_data()
    assert mode == "EXASOL_PERSONAL"

    exa_marts = client.compute_analytical_marts(source="exasol")
    pan_marts = client.compute_analytical_marts(source="pandas")

    assert exa_marts["compute_source"] == "EXASOL_VIEWS"
    assert pan_marts["compute_source"] == "PANDAS_MIRROR"

    for kpi_key in (
        "total_scheduled_value_inr",
        "legacy_risk_inr",
        "net_risk_inr",
        "cleared_by_udf_inr",
        "total_idle_loss_inr",
        "total_stoppage_exposure_inr",
        "total_freight_cost_inr",
        "headline_roi_x",
        "false_alarms_cleared_count",
        "avoided_panic_freight_inr",
    ):
        assert exa_marts["financial_roi_mart"][kpi_key] == pytest.approx(
            pan_marts["financial_roi_mart"][kpi_key], abs=0.01
        ), f"Mismatch on {kpi_key}"





