from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict
import numpy as np
import pandas as pd


REFERENCE_MONDAY = datetime(2026, 10, 12, 6, 0, 0)


def generate_supplier_master(rng: np.random.Generator) -> pd.DataFrame:
    suppliers = [
        ("SUP-T1-101", "Bharat Forge Drivetrain Systems Ltd", "TIER_1", "Pune-Mundhwa", "MH", "AS2_EDI", "YYYY-MM-DD", 0.9650, 0.4),
        ("SUP-T1-102", "Endurance Die Casting Technologies", "TIER_1", "Aurangabad-Waluj", "MH", "AS2_EDI", "YYYY-MM-DD", 0.9520, 0.6),
        ("SUP-T1-103", "Sundram Precision Fasteners Corp", "TIER_1", "Chennai-Padi", "TN", "SFTP_CSV", "YYYY-MM-DD", 0.9480, 0.8),
        ("SUP-T1-104", "Minda E-Drive Propulsion Ltd", "TIER_1", "Pune-Chakan", "MH", "AS2_EDI", "YYYY-MM-DD", 0.9390, 0.9),
        ("SUP-T2-201", "Shree Bhosari Auto Machinists Pvt Ltd", "TIER_2", "Pune-Bhosari MIDC", "MH", "EMAIL_XLS_EXTRACT", "DD/MM/YYYY", 0.8120, 3.8),
        ("SUP-T2-202", "Rajkot Crank & Conrod Forgings", "TIER_2", "Rajkot-Metoda GIDC", "GJ", "SFTP_CSV", "DD/MM/YYYY", 0.7850, 4.5),
        ("SUP-T2-203", "Talegaon High-Tensile Fasteners", "TIER_2", "Pune-Talegaon", "MH", "EMAIL_XLS_EXTRACT", "MM/DD/YYYY", 0.7940, 4.1),
        ("SUP-T2-204", "Faridabad Sintered Bearings Co", "TIER_2", "Faridabad-Sec24", "HR", "EMAIL_XLS_EXTRACT", "MM/DD/YYYY", 0.7680, 5.2),
        ("SUP-T2-205", "Hosur Precision Gear Works", "TIER_2", "Hosur-SIPCOT", "TN", "SFTP_CSV", "DD/MM/YYYY", 0.8310, 3.2),
        ("SUP-T2-206", "Manesar Piezo & Fuel Systems", "TIER_2", "Gurgaon-Manesar", "HR", "SFTP_CSV", "YYYY-MM-DD", 0.8450, 2.9),
        ("SUP-T2-207", "Sanand Alloy Castings & Hubs", "TIER_2", "Ahmedabad-Sanand", "GJ", "EMAIL_XLS_EXTRACT", "DD/MM/YYYY", 0.8010, 3.9),
        ("SUP-T2-208", "Chakan Electrical Laminations Pvt Ltd", "TIER_2", "Pune-Chakan Phase 2", "MH", "EMAIL_XLS_EXTRACT", "DD/MM/YYYY", 0.8240, 3.4),
        ("SUP-T3-301", "Khed-Shivapur Metallics & Bars", "TIER_3", "Pune-Khed", "MH", "PORTAL_BILTY_OCR", "DD/MM/YYYY", 0.7150, 6.8),
        ("SUP-T3-302", "Ambattur Seal & Elastomer Works", "TIER_3", "Chennai-Ambattur", "TN", "PORTAL_BILTY_OCR", "MM/DD/YYYY", 0.7320, 6.1),
        ("SUP-T3-303", "Nashik Copper Winding Conductors", "TIER_3", "Nashik-Satpur MIDC", "MH", "EMAIL_XLS_EXTRACT", "DD/MM/YYYY", 0.7490, 5.7),
        ("SUP-T3-304", "Kolhapur Foundry & Iron Castings", "TIER_3", "Kolhapur-Shiroli", "MH", "PORTAL_BILTY_OCR", "DD/MM/YYYY", 0.7080, 7.4),
    ]
    columns = [
        "supplier_id",
        "supplier_name",
        "tier_level",
        "industrial_cluster",
        "state_code",
        "integration_channel",
        "default_date_format",
        "historical_otd_rate",
        "avg_lead_time_drift_days",
    ]
    return pd.DataFrame(suppliers, columns=columns)


def generate_item_master() -> pd.DataFrame:
    items = [
        # Finished Parent Assemblies
        ("ASM-ENG-E6-450", "Euro-VI 6-Cyl Commercial Diesel Engine", "FINISHED_ASSEMBLY", "EA", 1, 485.0, 385000.00, 15, 5.0, "A"),
        ("ASM-TRN-AMT-6S", "6-Speed Automated Manual Transmission", "FINISHED_ASSEMBLY", "EA", 1, 195.0, 210000.00, 20, 5.0, "A"),
        ("ASM-AXL-HD-REAR", "Heavy-Duty Hypoid Rear Drive Axle", "FINISHED_ASSEMBLY", "EA", 1, 310.0, 165000.00, 18, 4.0, "A"),
        ("ASM-EVC-EDU-200", "200kW Commercial EV Electric Drive Unit", "FINISHED_ASSEMBLY", "EA", 1, 140.0, 420000.00, 12, 6.0, "A"),
        # Machined & Forged Powertrain Components
        ("ENG-BRG-6204-01", "High-Speed Deep Groove Bearing 6204-ZZ", "BEARINGS", "EA", 100, 0.145, 420.00, 1200, 7.0, "A"),
        ("ENG-BLT-M12-109", "High-Tensile Cylinder Head Bolt M12x1.5", "FASTENERS", "EA", 250, 0.085, 68.00, 6000, 5.0, "A"),
        ("ENG-CRD-42CR-04", "Forged 42CrMo4 Connecting Rod Machined", "FORGINGS", "EA", 50, 1.850, 2450.00, 900, 10.0, "A"),
        ("ENG-CRK-5140-01", "Induction-Hardened 6-Cyl Crankshaft", "FORGINGS", "EA", 10, 42.500, 28500.00, 120, 14.0, "A"),
        ("ENG-GSK-MLS-06", "Multi-Layer Steel Cylinder Head Gasket", "SEALS_GASKETS", "EA", 100, 0.320, 1150.00, 400, 6.0, "B"),
        ("ENG-INJ-PZO-22", "Common-Rail Piezo Fuel Injector 2200Bar", "FUEL_SYSTEMS", "EA", 25, 0.640, 8900.00, 600, 12.0, "A"),
        # Transmission & Axle Components
        ("TRN-GER-HEL-34", "Helical Pinion Gear 20MnCr5 Case-Hardened", "GEARS", "EA", 40, 3.200, 4100.00, 500, 9.0, "A"),
        ("TRN-SYN-BRS-02", "Molybdenum Coated Brass Synchronizer Ring", "TRANSMISSION", "EA", 100, 0.280, 780.00, 1000, 8.0, "B"),
        ("TRN-SHF-SPL-08", "Splined Input Transmission Shaft", "SHAFTS", "EA", 20, 6.800, 5600.00, 250, 10.0, "A"),
        ("AXL-HUB-DUC-14", "Ductile Iron Wheel Hub Machined Casting", "CASTINGS", "EA", 12, 18.400, 6200.00, 300, 8.0, "A"),
        ("AXL-PIN-20MC-09", "Matched Crown Wheel & Hypoid Pinion Set", "GEARS", "EA", 10, 24.000, 14800.00, 160, 11.0, "A"),
        ("AXL-SEL-FKM-85", "Fluoroelastomer Rotary Shaft Seal 85mm", "SEALS_GASKETS", "EA", 200, 0.060, 195.00, 1500, 5.0, "B"),
        # EV Drive & Raw Material Inputs
        ("EVC-STA-LAM-01", "Electrical Steel Stator Lamination Stack", "EV_CORE", "KG", 1000, 1.000, 310.00, 4500, 9.0, "A"),
        ("EVC-WND-CU-04", "Enamelled Flat Copper Hairpin Wire", "EV_CORE", "KG", 500, 1.000, 980.00, 2500, 10.0, "A"),
        ("EVC-MAG-NDF-48", "Sintered NdFeB Rotor Magnet Segment", "EV_CORE", "EA", 250, 0.045, 340.00, 3000, 15.0, "A"),
        ("RAW-STL-42CR-B", "42CrMo4 Alloy Forging Steel Billet", "RAW_METALS", "KG", 1000, 1.000, 118.00, 12000, 7.0, "B"),
    ]
    columns = [
        "internal_part_num",
        "part_description",
        "part_category",
        "base_uom",
        "standard_pack_size_ea",
        "unit_weight_kg",
        "standard_cost_inr",
        "safety_stock_qty",
        "planned_lead_time_days",
        "criticality_class",
    ]
    return pd.DataFrame(items, columns=columns)


def generate_bom() -> pd.DataFrame:
    bom_rows = [
        # Euro-VI Engine Block BOM
        ("BOM-101", "ASM-ENG-E6-450", "ENG-BRG-6204-01", 4.0, 0.0100, 1, "STN-ENG-02"),
        ("BOM-102", "ASM-ENG-E6-450", "ENG-BLT-M12-109", 24.0, 0.0150, 1, "STN-ENG-04"),
        ("BOM-103", "ASM-ENG-E6-450", "ENG-CRD-42CR-04", 6.0, 0.0050, 1, "STN-ENG-03"),
        ("BOM-104", "ASM-ENG-E6-450", "ENG-CRK-5140-01", 1.0, 0.0000, 1, "STN-ENG-01"),
        ("BOM-105", "ASM-ENG-E6-450", "ENG-GSK-MLS-06", 1.0, 0.0200, 1, "STN-ENG-04"),
        ("BOM-106", "ASM-ENG-E6-450", "ENG-INJ-PZO-22", 6.0, 0.0050, 1, "STN-ENG-06"),
        # 6-Speed AMT Gearbox BOM
        ("BOM-201", "ASM-TRN-AMT-6S", "TRN-GER-HEL-34", 6.0, 0.0100, 1, "STN-TRN-02"),
        ("BOM-202", "ASM-TRN-AMT-6S", "TRN-SYN-BRS-02", 6.0, 0.0150, 1, "STN-TRN-03"),
        ("BOM-203", "ASM-TRN-AMT-6S", "TRN-SHF-SPL-08", 2.0, 0.0050, 1, "STN-TRN-01"),
        ("BOM-204", "ASM-TRN-AMT-6S", "ENG-BRG-6204-01", 6.0, 0.0100, 1, "STN-TRN-02"),
        # Heavy-Duty Rear Axle BOM
        ("BOM-301", "ASM-AXL-HD-REAR", "AXL-HUB-DUC-14", 2.0, 0.0100, 1, "STN-AXL-02"),
        ("BOM-302", "ASM-AXL-HD-REAR", "AXL-PIN-20MC-09", 1.0, 0.0050, 1, "STN-AXL-01"),
        ("BOM-303", "ASM-AXL-HD-REAR", "AXL-SEL-FKM-85", 4.0, 0.0250, 1, "STN-AXL-03"),
        ("BOM-304", "ASM-AXL-HD-REAR", "ENG-BLT-M12-109", 16.0, 0.0150, 1, "STN-AXL-04"),
        # 200kW EV Drive Unit BOM
        ("BOM-401", "ASM-EVC-EDU-200", "EVC-STA-LAM-01", 38.0, 0.0200, 1, "STN-EVC-01"),
        ("BOM-402", "ASM-EVC-EDU-200", "EVC-WND-CU-04", 16.5, 0.0150, 1, "STN-EVC-02"),
        ("BOM-403", "ASM-EVC-EDU-200", "EVC-MAG-NDF-48", 48.0, 0.0100, 1, "STN-EVC-03"),
        ("BOM-404", "ASM-EVC-EDU-200", "ENG-BRG-6204-01", 2.0, 0.0100, 1, "STN-EVC-04"),
        # Tier-2 Sub-component dependency
        ("BOM-501", "ENG-CRD-42CR-04", "RAW-STL-42CR-B", 2.4, 0.0800, 2, "SUB-FORGE-01"),
    ]
    columns = [
        "bom_id",
        "parent_part_num",
        "component_part_num",
        "qty_per_assembly",
        "scrap_allowance_pct",
        "bom_level",
        "assembly_station_code",
    ]
    return pd.DataFrame(bom_rows, columns=columns)


def generate_production_schedules() -> pd.DataFrame:
    schedules = [
        (
            "SCH-20261012-L1",
            "LINE-01-EURO6",
            "Chakan Powertrain Line 1 (Euro-VI Diesel)",
            "ASM-ENG-E6-450",
            REFERENCE_MONDAY + timedelta(hours=2),
            REFERENCE_MONDAY + timedelta(hours=50),
            450,
            385000.00,
            1450000.00,
            "SCHEDULED_ACTIVE",
        ),
        (
            "SCH-20261012-L2",
            "LINE-02-AMT",
            "Chakan Transmission Line 2 (6-Speed AMT)",
            "ASM-TRN-AMT-6S",
            REFERENCE_MONDAY + timedelta(hours=4),
            REFERENCE_MONDAY + timedelta(hours=52),
            320,
            210000.00,
            880000.00,
            "SCHEDULED_ACTIVE",
        ),
        (
            "SCH-20261012-L3",
            "LINE-03-AXLE",
            "Chakan Heavy Axle Line 3 (Hypoid Rear)",
            "ASM-AXL-HD-REAR",
            REFERENCE_MONDAY + timedelta(hours=2),
            REFERENCE_MONDAY + timedelta(hours=50),
            380,
            165000.00,
            720000.00,
            "SCHEDULED_ACTIVE",
        ),
        (
            "SCH-20261012-L4",
            "LINE-04-EVDRIVE",
            "Chakan e-Mobility Line 4 (200kW EDU)",
            "ASM-EVC-EDU-200",
            REFERENCE_MONDAY + timedelta(hours=6),
            REFERENCE_MONDAY + timedelta(hours=54),
            180,
            420000.00,
            1150000.00,
            "SCHEDULED_ACTIVE",
        ),
    ]
    columns = [
        "schedule_id",
        "assembly_line_id",
        "assembly_line_name",
        "parent_part_num",
        "scheduled_start_ts",
        "scheduled_end_ts",
        "planned_output_units",
        "finished_unit_value_inr",
        "downtime_burn_rate_inr_hr",
        "schedule_status",
    ]
    return pd.DataFrame(schedules, columns=columns)


def generate_warehouse_inventory_ledger() -> pd.DataFrame:
    """
    Generates central ERP vs. physical WMS bin counts across Chakan Plant-1 stores.
    Includes realistic 'Phantom Inventory' variance where ERP overstates physical stock
    because weekend cycle-count shrinkage/damage holds failed to sync.
    """
    count_ts = REFERENCE_MONDAY - timedelta(hours=7)
    rows = [
        # Critical components with Phantom Inventory (ERP shows healthy stock, physical bin is much lower)
        ("INV-1001", "CHAKAN-PLT1-STORE", "BIN-A01-12", "ENG-BRG-6204-01", 4100.0, 2650.0, 400.0, 250.0, count_ts),
        ("INV-1002", "CHAKAN-PLT1-STORE", "BIN-A02-04", "ENG-BLT-M12-109", 16500.0, 10800.0, 1200.0, 600.0, count_ts),
        ("INV-1003", "CHAKAN-PLT1-STORE", "BIN-A03-08", "ENG-CRD-42CR-04", 2400.0, 1520.0, 220.0, 80.0, count_ts),
        ("INV-1004", "CHAKAN-PLT1-STORE", "BIN-A04-01", "ENG-CRK-5140-01", 480.0, 465.0, 10.0, 5.0, count_ts),
        ("INV-1005", "CHAKAN-PLT1-STORE", "BIN-A05-11", "ENG-GSK-MLS-06", 620.0, 590.0, 40.0, 10.0, count_ts),
        ("INV-1006", "CHAKAN-PLT1-STORE", "BIN-A06-03", "ENG-INJ-PZO-22", 2900.0, 2780.0, 80.0, 20.0, count_ts),
        ("INV-1007", "CHAKAN-PLT1-STORE", "BIN-B01-05", "TRN-GER-HEL-34", 1950.0, 1280.0, 180.0, 90.0, count_ts),
        ("INV-1008", "CHAKAN-PLT1-STORE", "BIN-B02-09", "TRN-SYN-BRS-02", 2400.0, 2250.0, 150.0, 0.0, count_ts),
        ("INV-1009", "CHAKAN-PLT1-STORE", "BIN-B03-02", "TRN-SHF-SPL-08", 740.0, 710.0, 40.0, 0.0, count_ts),
        ("INV-1010", "CHAKAN-PLT1-STORE", "BIN-C01-07", "AXL-HUB-DUC-14", 820.0, 510.0, 60.0, 40.0, count_ts),
        ("INV-1011", "CHAKAN-PLT1-STORE", "BIN-C02-01", "AXL-PIN-20MC-09", 440.0, 420.0, 20.0, 0.0, count_ts),
        ("INV-1012", "CHAKAN-PLT1-STORE", "BIN-C03-14", "AXL-SEL-FKM-85", 1900.0, 1820.0, 120.0, 0.0, count_ts),
        ("INV-1013", "CHAKAN-PLT1-STORE", "BIN-D01-02", "EVC-STA-LAM-01", 6800.0, 4200.0, 500.0, 300.0, count_ts),
        ("INV-1014", "CHAKAN-PLT1-STORE", "BIN-D02-06", "EVC-WND-CU-04", 3100.0, 2150.0, 200.0, 150.0, count_ts),
        ("INV-1015", "CHAKAN-PLT1-STORE", "BIN-D03-10", "EVC-MAG-NDF-48", 9200.0, 8950.0, 200.0, 0.0, count_ts),
        ("INV-1016", "CHAKAN-PLT1-STORE", "BIN-E01-01", "RAW-STL-42CR-B", 15000.0, 14400.0, 1000.0, 0.0, count_ts),
    ]
    columns = [
        "ledger_id",
        "facility_code",
        "storage_bin_id",
        "internal_part_num",
        "erp_system_on_hand_qty",
        "wms_physical_counted_qty",
        "allocated_to_prod_qty",
        "quality_hold_qty",
        "last_cycle_count_ts",
    ]
    return pd.DataFrame(rows, columns=columns)


def generate_purchase_orders() -> pd.DataFrame:
    base_day = date(2026, 10, 12)
    po_rows = [
        # Open POs critical for Monday-Wednesday assembly runs
        ("PO-2026-8801-1", "PO-2026-8801", 1, "SUP-T2-204", "ENG-BRG-6204-01", 3000.0, "EA", 420.00, base_day - timedelta(days=9), base_day, "OPEN"),
        ("PO-2026-8802-1", "PO-2026-8802", 1, "SUP-T2-203", "ENG-BLT-M12-109", 10000.0, "EA", 68.00, base_day - timedelta(days=7), base_day, "OPEN"),
        ("PO-2026-8803-1", "PO-2026-8803", 1, "SUP-T2-202", "ENG-CRD-42CR-04", 2000.0, "EA", 2450.00, base_day - timedelta(days=11), base_day, "OPEN"),
        ("PO-2026-8804-1", "PO-2026-8804", 1, "SUP-T1-101", "ENG-CRK-5140-01", 200.0, "EA", 28500.00, base_day - timedelta(days=14), base_day + timedelta(days=1), "OPEN"),
        ("PO-2026-8805-1", "PO-2026-8805", 1, "SUP-T2-201", "ENG-GSK-MLS-06", 500.0, "EA", 1150.00, base_day - timedelta(days=6), base_day, "OPEN"),
        ("PO-2026-8806-1", "PO-2026-8806", 1, "SUP-T2-206", "ENG-INJ-PZO-22", 1000.0, "EA", 8900.00, base_day - timedelta(days=12), base_day + timedelta(days=1), "OPEN"),
        ("PO-2026-8807-1", "PO-2026-8807", 1, "SUP-T2-205", "TRN-GER-HEL-34", 1200.0, "EA", 4100.00, base_day - timedelta(days=10), base_day, "OPEN"),
        ("PO-2026-8808-1", "PO-2026-8808", 1, "SUP-T2-201", "TRN-SYN-BRS-02", 1500.0, "EA", 780.00, base_day - timedelta(days=8), base_day + timedelta(days=1), "OPEN"),
        ("PO-2026-8809-1", "PO-2026-8809", 1, "SUP-T1-101", "TRN-SHF-SPL-08", 300.0, "EA", 5600.00, base_day - timedelta(days=10), base_day + timedelta(days=1), "OPEN"),
        ("PO-2026-8810-1", "PO-2026-8810", 1, "SUP-T2-207", "AXL-HUB-DUC-14", 600.0, "EA", 6200.00, base_day - timedelta(days=9), base_day, "OPEN"),
        ("PO-2026-8811-1", "PO-2026-8811", 1, "SUP-T2-205", "AXL-PIN-20MC-09", 200.0, "EA", 14800.00, base_day - timedelta(days=11), base_day + timedelta(days=1), "OPEN"),
        ("PO-2026-8812-1", "PO-2026-8812", 1, "SUP-T3-302", "AXL-SEL-FKM-85", 2000.0, "EA", 195.00, base_day - timedelta(days=6), base_day, "OPEN"),
        ("PO-2026-8813-1", "PO-2026-8813", 1, "SUP-T2-208", "EVC-STA-LAM-01", 5000.0, "KG", 310.00, base_day - timedelta(days=9), base_day, "OPEN"),
        ("PO-2026-8814-1", "PO-2026-8814", 1, "SUP-T3-303", "EVC-WND-CU-04", 2000.0, "KG", 980.00, base_day - timedelta(days=10), base_day, "OPEN"),
        ("PO-2026-8815-1", "PO-2026-8815", 1, "SUP-T1-104", "EVC-MAG-NDF-48", 2500.0, "EA", 340.00, base_day - timedelta(days=15), base_day + timedelta(days=1), "OPEN"),
        ("PO-2026-8816-1", "PO-2026-8816", 1, "SUP-T3-301", "RAW-STL-42CR-B", 10000.0, "KG", 118.00, base_day - timedelta(days=8), base_day, "OPEN"),
    ]
    columns = [
        "po_line_id",
        "po_number",
        "line_number",
        "supplier_id",
        "internal_part_num",
        "ordered_qty",
        "ordered_uom",
        "unit_price_inr",
        "order_date",
        "promised_delivery_date",
        "po_line_status",
    ]
    return pd.DataFrame(po_rows, columns=columns)


def build_all_erp_tables(seed: int = 202610) -> Dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    return {
        "SUPPLIER_MASTER": generate_supplier_master(rng),
        "ITEM_MASTER": generate_item_master(),
        "BILL_OF_MATERIALS": generate_bom(),
        "PRODUCTION_SCHEDULES": generate_production_schedules(),
        "WAREHOUSE_INVENTORY_LEDGER": generate_warehouse_inventory_ledger(),
        "PURCHASE_ORDER_LINES": generate_purchase_orders(),
    }
