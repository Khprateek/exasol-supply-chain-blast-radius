from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict
import numpy as np
import pandas as pd

from src.data_generator.erp_master_gen import REFERENCE_MONDAY


def generate_inbound_asn_chaos(
    erp_tables: Dict[str, pd.DataFrame],
    extra_batch_rows: int = 480,
    seed: int = 202610,
) -> pd.DataFrame:
    """
    Generates inbound Advance Shipping Notice (ASN) lines combining:
    1. Curated active Monday-morning dispatches with realistic MSME format anomalies
       (UOM inversion, SKU identifier drift, date ambiguity, split partial shipments,
       and duplicate transmissions) that legacy ETL pipelines quarantine.
    2. High-volume background ASN history for analytical benchmarking in Exasol.
    """
    rng = np.random.default_rng(seed)
    ingested_ts = REFERENCE_MONDAY - timedelta(minutes=35)

    curated_asns = [
        # 1. PO-2026-8801 (ENG-BRG-6204-01, Ordered 3000 EA)
        # Defect: SKU stripped to '6204ZZ' + UOM sent in 'BOX_100' (22 boxes = 2200 EA, short by 800 EA)
        (
            "ASN-L-9001", "ASN-FBD-7741", "SUP-T2-204", "PO-2026-8801", 1,
            "6204ZZ", 22.0, "BOX_100", "10/10/2026", "10/12/2026",
            "Delhivery Freight", "HR-38-AB-9012", "EMAIL_XLS_EXTRACT",
            "QUARANTINED", "SKU_DRIFT_AND_UOM_BOX", ingested_ts,
        ),
        # 2. PO-2026-8802 (ENG-BLT-M12-109, Ordered 10000 EA)
        # Defect: UOM sent in 'BAG_250' (26 bags = 6500 EA) + MM/DD/YYYY date string
        (
            "ASN-L-9002", "ASN-TLG-3310", "SUP-T2-203", "PO-2026-8802", 1,
            "M12X15-HT-109", 26.0, "BAG_250", "10/11/2026", "10/12/2026",
            "VRL Logistics", "MH-14-HG-2219", "EMAIL_XLS_EXTRACT",
            "QUARANTINED", "SKU_DRIFT_AND_UOM_BAG", ingested_ts,
        ),
        # 3. PO-2026-8803 (ENG-CRD-42CR-04, Ordered 2000 EA) - Split Shipment Part 1 of 2
        # Defect: Sent in 'CRATE_50' (12 crates = 600 EA) + DD/MM/YYYY date
        (
            "ASN-L-9003", "ASN-RJK-5501A", "SUP-T2-202", "PO-2026-8803", 1,
            "42CR-CONROD-04", 12.0, "CRATE_50", "10/10/2026", "12/10/2026",
            "TCI Freight", "GJ-03-BW-4410", "SFTP_CSV",
            "QUARANTINED", "SPLIT_PO_AND_UOM_CRATE", ingested_ts,
        ),
        # 4. PO-2026-8803 (ENG-CRD-42CR-04, Ordered 2000 EA) - Split Shipment Part 2 of 2
        # Defect: Second truck delayed + only 10 crates (500 EA). Total shipped = 1100 vs 2000 ordered!
        (
            "ASN-L-9004", "ASN-RJK-5501B", "SUP-T2-202", "PO-2026-8803", 1,
            "42CR-CONROD-04", 10.0, "CRATE_50", "11/10/2026", "13/10/2026",
            "TCI Freight", "GJ-03-BW-8821", "SFTP_CSV",
            "QUARANTINED", "SPLIT_PO_SHORT_SHIPMENT", ingested_ts,
        ),
        # 5. PO-2026-8804 (ENG-CRK-5140-01, Ordered 200 EA) - Clean Tier-1 EDI
        (
            "ASN-L-9005", "ASN-BFG-1009", "SUP-T1-101", "PO-2026-8804", 1,
            "ENG-CRK-5140-01", 200.0, "EA", "2026-10-11", "2026-10-12",
            "Mahindra Logistics", "MH-12-PQ-1102", "AS2_EDI",
            "ACCEPTED", "CLEAN", ingested_ts,
        ),
        # 6. PO-2026-8805 (ENG-GSK-MLS-06, Ordered 500 EA)
        # Defect: SKU stripped hyphens 'ENGGSKMLS06' + UOM 'BOX_100' (5 boxes = 500 EA)
        (
            "ASN-L-9006", "ASN-BHS-8120", "SUP-T2-201", "PO-2026-8805", 1,
            "ENGGSKMLS06", 5.0, "BOX_100", "11/10/2026", "12/10/2026",
            "Konduskar Tempo", "MH-12-TR-7650", "EMAIL_XLS_EXTRACT",
            "QUARANTINED", "SKU_HYPHEN_STRIPPED", ingested_ts,
        ),
        # 7. PO-2026-8806 (ENG-INJ-PZO-22, Ordered 1000 EA) - Clean Tier-2 CSV
        (
            "ASN-L-9007", "ASN-MNS-4012", "SUP-T2-206", "PO-2026-8806", 1,
            "ENG-INJ-PZO-22", 1000.0, "EA", "2026-10-10", "2026-10-12",
            "Safexpress", "HR-55-KL-3391", "SFTP_CSV",
            "ACCEPTED", "CLEAN", ingested_ts,
        ),
        # 8. PO-2026-8807 (TRN-GER-HEL-34, Ordered 1200 EA)
        # Defect: Vendor code 'HSR-HEL-34' + UOM 'CRATE_40' (18 crates = 720 EA, short by 480 gears!)
        (
            "ASN-L-9008", "ASN-HSR-6091", "SUP-T2-205", "PO-2026-8807", 1,
            "HSR-HEL-34", 18.0, "CRATE_40", "10/10/2026", "12/10/2026",
            "KPN Parcel", "TN-70-AX-5120", "SFTP_CSV",
            "QUARANTINED", "SKU_ALIAS_AND_SHORT_QTY", ingested_ts,
        ),
        # 9. PO-2026-8808 (TRN-SYN-BRS-02, Ordered 1500 EA)
        # Defect: Unix epoch timestamp in ETA + 'BOX_100' (15 boxes = 1500 EA)
        (
            "ASN-L-9009", "ASN-BHS-8125", "SUP-T2-201", "PO-2026-8808", 1,
            "TRN-SYN-BRS-02", 15.0, "BOX_100", "1791676800", "1791763200",
            "Konduskar Tempo", "MH-12-TR-7655", "EMAIL_XLS_EXTRACT",
            "QUARANTINED", "EPOCH_DATE_AND_UOM_BOX", ingested_ts,
        ),
        # 10. PO-2026-8809 (TRN-SHF-SPL-08, Ordered 300 EA) - Clean Tier-1 EDI
        (
            "ASN-L-9010", "ASN-BFG-1014", "SUP-T1-101", "PO-2026-8809", 1,
            "TRN-SHF-SPL-08", 300.0, "EA", "2026-10-11", "2026-10-12",
            "Mahindra Logistics", "MH-12-PQ-1188", "AS2_EDI",
            "ACCEPTED", "CLEAN", ingested_ts,
        ),
        # 11. PO-2026-8810 (AXL-HUB-DUC-14, Ordered 600 EA)
        # Defect: Vendor shipped in Metric Tons ('MT') on lorry bilty (3.312 MT = 180 hubs @ 18.4kg each, short by 420 hubs!)
        (
            "ASN-L-9011", "ASN-SND-2044", "SUP-T2-207", "PO-2026-8810", 1,
            "DUC-HUB-14", 3.312, "MT", "10/10/2026", "12/10/2026",
            "Gati KWE", "GJ-01-DT-9920", "EMAIL_XLS_EXTRACT",
            "QUARANTINED", "WEIGHT_MT_TO_EA_INVERSION", ingested_ts,
        ),
        # 12. PO-2026-8811 (AXL-PIN-20MC-09, Ordered 200 EA) - Clean
        (
            "ASN-L-9012", "ASN-HSR-6098", "SUP-T2-205", "PO-2026-8811", 1,
            "AXL-PIN-20MC-09", 200.0, "EA", "2026-10-10", "2026-10-12",
            "TVS Supply Chain", "TN-70-AX-9011", "SFTP_CSV",
            "ACCEPTED", "CLEAN", ingested_ts,
        ),
        # 13. PO-2026-8812 (AXL-SEL-FKM-85, Ordered 2000 EA)
        # Defect: OCR bilty scan with 'BOX_200' (10 boxes = 2000 EA) and stripped SKU 'FKM85SEAL'
        (
            "ASN-L-9013", "ASN-AMB-0912", "SUP-T3-302", "PO-2026-8812", 1,
            "FKM85SEAL", 10.0, "BOX_200", "10/10/2026", "10/12/2026",
            "Southern Roadways", "TN-04-M-4510", "PORTAL_BILTY_OCR",
            "QUARANTINED", "OCR_SKU_ALIAS_AND_BOX", ingested_ts,
        ),
        # 14. PO-2026-8813 (EVC-STA-LAM-01, Ordered 5000 KG)
        # Defect: Reported in 'MT' (3.15 MT = 3150 KG instead of 5000 KG) -> EV Line 4 shortage!
        (
            "ASN-L-9014", "ASN-CHK-7710", "SUP-T2-208", "PO-2026-8813", 1,
            "STA-LAM-01-SIL", 3.150, "MT", "11/10/2026", "12/10/2026",
            "Chakan Local Transport", "MH-14-CV-3011", "EMAIL_XLS_EXTRACT",
            "QUARANTINED", "UOM_MT_VS_KG_SHORTAGE", ingested_ts,
        ),
        # 15. PO-2026-8814 (EVC-WND-CU-04, Ordered 2000 KG)
        # Defect: Reported in 'MT' (1.20 MT = 1200 KG, short by 800 KG) + duplicate retransmission row below
        (
            "ASN-L-9015", "ASN-NSK-1180", "SUP-T3-303", "PO-2026-8814", 1,
            "CU-HAIRPIN-04", 1.200, "MT", "11/10/2026", "12/10/2026",
            "Nashik Express Cargo", "MH-15-EF-6701", "EMAIL_XLS_EXTRACT",
            "QUARANTINED", "UOM_MT_VS_KG_SHORTAGE", ingested_ts,
        ),
        # 16. Duplicate Retransmission of ASN-NSK-1180 (Should be deduplicated by Harmonizer)
        (
            "ASN-L-9016", "ASN-NSK-1180", "SUP-T3-303", "PO-2026-8814", 1,
            "CU-HAIRPIN-04", 1.200, "MT", "11/10/2026", "12/10/2026",
            "Nashik Express Cargo", "MH-15-EF-6701", "EMAIL_XLS_EXTRACT",
            "QUARANTINED", "DUPLICATE_ASN_RETRANSMIT", ingested_ts + timedelta(minutes=4),
        ),
        # 17. PO-2026-8815 (EVC-MAG-NDF-48, Ordered 2500 EA) - Clean Tier-1 EDI
        (
            "ASN-L-9017", "ASN-MND-4490", "SUP-T1-104", "PO-2026-8815", 1,
            "EVC-MAG-NDF-48", 2500.0, "EA", "2026-10-11", "2026-10-12",
            "BlueDart Industrial", "MH-14-AZ-9900", "AS2_EDI",
            "ACCEPTED", "CLEAN", ingested_ts,
        ),
        # 18. PO-2026-8816 (RAW-STL-42CR-B, Ordered 10000 KG)
        # Defect: Lorry bilty reported in 'MT' (10.0 MT = 10000 KG, full shipment but quarantined by unit check)
        (
            "ASN-L-9018", "ASN-KHD-0319", "SUP-T3-301", "PO-2026-8816", 1,
            "42CRMO4-BILLET", 10.000, "MT", "11/10/2026", "12/10/2026",
            "Sahyadri Heavy Lorries", "MH-12-HD-5599", "PORTAL_BILTY_OCR",
            "QUARANTINED", "UOM_MT_VS_KG_CLEAN_QTY", ingested_ts,
        ),
    ]

    po_df = erp_tables["PURCHASE_ORDER_LINES"]
    sup_df = erp_tables["SUPPLIER_MASTER"].set_index("supplier_id")
    carriers = [
        "Delhivery Freight", "VRL Logistics", "TCI Freight", "Mahindra Logistics",
        "Safexpress", "Gati KWE", "TVS Supply Chain", "Rivigo Fleet",
    ]
    anomaly_choices = [
        ("CLEAN", "ACCEPTED", 0.62),
        ("SKU_HYPHEN_STRIPPED", "QUARANTINED", 0.12),
        ("UOM_PACK_INVERSION", "QUARANTINED", 0.11),
        ("DATE_FORMAT_DRIFT", "QUARANTINED", 0.09),
        ("DUPLICATE_ASN_RETRANSMIT", "QUARANTINED", 0.06),
    ]
    labels = [a[0] for a in anomaly_choices]
    statuses = {a[0]: a[1] for a in anomaly_choices}
    probs = [a[2] for a in anomaly_choices]

    historical_rows = []
    for idx in range(extra_batch_rows):
        po_row = po_df.iloc[int(rng.integers(0, len(po_df)))]
        sup_id = str(po_row["supplier_id"])
        sup_info = sup_df.loc[sup_id]
        part_num = str(po_row["internal_part_num"])
        base_uom = str(po_row["ordered_uom"])
        ord_qty = float(po_row["ordered_qty"])

        chosen_anomaly = str(rng.choice(labels, p=probs))
        etl_status = statuses[chosen_anomaly]

        days_ago = int(rng.integers(3, 45))
        ship_dt = REFERENCE_MONDAY.date() - timedelta(days=days_ago)
        eta_dt = ship_dt + timedelta(days=int(rng.integers(1, 5)))

        raw_sku = part_num
        raw_qty = ord_qty
        raw_uom = base_uom
        raw_ship_str = ship_dt.strftime("%Y-%m-%d")
        raw_eta_str = eta_dt.strftime("%Y-%m-%d")

        if chosen_anomaly == "SKU_HYPHEN_STRIPPED":
            raw_sku = part_num.replace("-", "")
        elif chosen_anomaly == "UOM_PACK_INVERSION":
            if base_uom == "KG":
                raw_qty = round(ord_qty / 1000.0, 4)
                raw_uom = "MT"
            else:
                raw_qty = round(ord_qty / 100.0, 2)
                raw_uom = "BOX_100"
        elif chosen_anomaly == "DATE_FORMAT_DRIFT":
            raw_ship_str = ship_dt.strftime("%d/%m/%Y")
            raw_eta_str = eta_dt.strftime("%m/%d/%Y")

        hist_po_num = f"PO-2026-{7000 + (idx % 180)}"
        asn_line_id = f"ASN-H-{10000 + idx}"
        asn_num = f"ASN-HIST-{5000 + idx}"
        carrier = str(rng.choice(carriers))
        lorry = f"{sup_info['state_code']}-{int(rng.integers(10, 55)):02d}-TX-{int(rng.integers(1000, 9999))}"

        historical_rows.append(
            (
                asn_line_id,
                asn_num,
                sup_id,
                hist_po_num,
                1,
                raw_sku,
                raw_qty,
                raw_uom,
                raw_ship_str,
                raw_eta_str,
                carrier,
                lorry,
                str(sup_info["integration_channel"]),
                etl_status,
                chosen_anomaly,
                ingested_ts - timedelta(days=days_ago),
            )
        )

    columns = [
        "asn_line_id",
        "asn_number",
        "supplier_id",
        "po_number_ref",
        "po_line_number_ref",
        "raw_supplier_sku",
        "raw_shipped_qty",
        "raw_shipped_uom",
        "raw_shipment_date",
        "raw_eta_date",
        "carrier_name",
        "vehicle_lorry_no",
        "source_format",
        "legacy_etl_status",
        "anomaly_type",
        "ingested_at",
    ]
    return pd.DataFrame(curated_asns + historical_rows, columns=columns)
