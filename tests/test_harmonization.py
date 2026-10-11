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
