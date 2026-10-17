-- Exasol Personal Analytical Views: Phantom Inventory, ASN Lineage & BOM Blast-Radius Engine
-- Target Schema: CHAKAN_SCM

OPEN SCHEMA CHAKAN_SCM;

-- 1. True Available-to-Promise (ATP) & Phantom Inventory Reconciliation View
CREATE OR REPLACE VIEW CHAKAN_SCM.VW_INVENTORY_TRUE_ATP AS
SELECT
    w.ledger_id,
    w.facility_code,
    w.storage_bin_id,
    w.internal_part_num,
    i.part_description,
    i.part_category,
    i.base_uom,
    i.standard_cost_inr,
    i.safety_stock_qty,
    w.erp_system_on_hand_qty,
    w.wms_physical_counted_qty,
    w.allocated_to_prod_qty,
    w.quality_hold_qty,
    (w.erp_system_on_hand_qty - w.wms_physical_counted_qty) AS phantom_inventory_qty,
    ROUND((w.erp_system_on_hand_qty - w.wms_physical_counted_qty) * i.standard_cost_inr, 2) AS phantom_inventory_value_inr,
    GREATEST(0, w.erp_system_on_hand_qty - w.allocated_to_prod_qty) AS erp_apparent_atp_qty,
    GREATEST(0, w.wms_physical_counted_qty - w.allocated_to_prod_qty - w.quality_hold_qty) AS true_pickable_atp_qty,
    w.last_cycle_count_ts
FROM CHAKAN_SCM.WAREHOUSE_INVENTORY_LEDGER w
JOIN CHAKAN_SCM.ITEM_MASTER i
    ON w.internal_part_num = i.internal_part_num;

-- 2. In-Database UDF Harmonized ASN Lineage View (With Deduplication & Planner Overrides)
CREATE OR REPLACE VIEW CHAKAN_SCM.VW_ASN_HARMONIZED_LINEAGE AS
WITH deduplicated_asn AS (
    SELECT
        a.*,
        ROW_NUMBER() OVER (
            PARTITION BY a.asn_number, a.po_number_ref, a.raw_supplier_sku, a.raw_shipped_qty
            ORDER BY a.ingested_at ASC
        ) AS transmission_seq
    FROM CHAKAN_SCM.ASN_LINES_RAW a
),
sku_resolved AS (
    SELECT
        d.asn_line_id,
        d.asn_number,
        d.supplier_id,
        d.po_number_ref,
        d.po_line_number_ref,
        d.raw_supplier_sku,
        d.raw_shipped_qty,
        d.raw_shipped_uom,
        d.raw_shipment_date,
        d.raw_eta_date,
        d.carrier_name,
        d.vehicle_lorry_no,
        d.source_format,
        d.legacy_etl_status,
        d.anomaly_type,
        d.ingested_at,
        d.transmission_seq,
        p.internal_part_num AS po_part_num,
        p.ordered_qty AS po_ordered_qty,
        p.ordered_uom AS po_ordered_uom,
        s.supplier_name,
        s.tier_level,
        s.default_date_format,
        CHAKAN_SCM.UDF_RESOLVE_SUPPLIER_SKU(d.raw_supplier_sku, p.internal_part_num)
    FROM deduplicated_asn d
    LEFT JOIN CHAKAN_SCM.PURCHASE_ORDER_LINES p
        ON d.po_number_ref = p.po_number
       AND COALESCE(d.po_line_number_ref, 1) = p.line_number
    LEFT JOIN CHAKAN_SCM.SUPPLIER_MASTER s
        ON d.supplier_id = s.supplier_id
)
SELECT
    sr.asn_line_id,
    sr.asn_number,
    sr.supplier_id,
    sr.supplier_name,
    sr.tier_level,
    sr.po_number_ref,
    COALESCE(ov.resolved_part_num, sr.resolved_part_num) AS internal_part_num,
    sr.raw_supplier_sku,
    sr.sku_match_method,
    sr.sku_confidence,
    COALESCE(ov.resolved_part_num, sr.resolved_part_num) AS resolved_part_num,
    sr.transmission_seq,
    sr.po_line_number_ref,
    sr.default_date_format,
    sr.raw_shipped_qty,
    sr.raw_shipped_uom,
    im.base_uom AS canonical_uom,
    CASE
        WHEN sr.transmission_seq > 1 THEN 0.0
        WHEN ov.normalized_qty IS NOT NULL THEN ov.normalized_qty
        ELSE CHAKAN_SCM.UDF_NORMALIZE_UOM(
            sr.raw_shipped_qty,
            sr.raw_shipped_uom,
            im.base_uom,
            im.standard_pack_size_ea,
            im.unit_weight_kg
        )
    END AS harmonized_shipped_qty,
    CASE
        WHEN sr.legacy_etl_status = 'ACCEPTED' AND sr.transmission_seq = 1 THEN sr.raw_shipped_qty
        ELSE 0.0
    END AS legacy_visible_qty,
    sr.raw_shipment_date,
    sr.raw_eta_date,
    COALESCE(
        ov.normalized_eta_date,
        CHAKAN_SCM.UDF_PARSE_ASN_DATE(sr.raw_eta_date, sr.default_date_format)
    ) AS harmonized_eta_date,
    sr.carrier_name,
    sr.vehicle_lorry_no,
    sr.source_format,
    sr.legacy_etl_status,
    CASE
        WHEN sr.transmission_seq > 1 THEN 'DUPLICATE_SUPPRESSED'
        WHEN ov.resolution_action IS NOT NULL THEN ov.resolution_action
        WHEN sr.legacy_etl_status = 'ACCEPTED' THEN 'CLEAN_INGESTED'
        ELSE 'UDF_HARMONIZED_PENDING_APPROVAL'
    END AS harmonization_state,
    sr.anomaly_type,
    sr.ingested_at
FROM sku_resolved sr
LEFT JOIN CHAKAN_SCM.ITEM_MASTER im
    ON COALESCE(sr.resolved_part_num, sr.po_part_num) = im.internal_part_num
LEFT JOIN CHAKAN_SCM.ASN_PLANNER_OVERRIDES ov
    ON sr.asn_line_id = ov.asn_line_id;

-- 3. BOM Explosion & Assembly Line Starvation Risk View
CREATE OR REPLACE VIEW CHAKAN_SCM.VW_BOM_LINE_STARVATION_RISK AS
WITH po_asn_rollup AS (
    SELECT
        p.po_number,
        p.internal_part_num,
        p.supplier_id,
        p.ordered_qty,
        p.ordered_uom,
        p.promised_delivery_date,
        COALESCE(SUM(h.legacy_visible_qty), 0.0) AS legacy_inbound_qty,
        COALESCE(SUM(h.harmonized_shipped_qty), 0.0) AS harmonized_inbound_qty,
        COUNT(h.asn_line_id) AS asn_shipment_count
    FROM CHAKAN_SCM.PURCHASE_ORDER_LINES p
    LEFT JOIN CHAKAN_SCM.VW_ASN_HARMONIZED_LINEAGE h
        ON p.po_number = h.po_number_ref
    WHERE p.po_line_status = 'OPEN'
    GROUP BY
        p.po_number,
        p.internal_part_num,
        p.supplier_id,
        p.ordered_qty,
        p.ordered_uom,
        p.promised_delivery_date
),
base_bom AS (
    SELECT
        ps.schedule_id,
        ps.assembly_line_id,
        ps.assembly_line_name,
        ps.parent_part_num,
        ps.planned_output_units,
        ps.finished_unit_value_inr,
        ps.downtime_burn_rate_inr_hr,
        b.component_part_num,
        b.component_part_num AS internal_part_num,
        im.part_description AS part_description,
        im.part_description AS component_description,
        inv.phantom_inventory_value_inr,
        im.base_uom,
        im.unit_weight_kg,
        im.standard_cost_inr,
        b.assembly_station_code,
        b.qty_per_assembly,
        ROUND(ps.planned_output_units * b.qty_per_assembly * (1.0 + b.scrap_allowance_pct), 2) AS gross_required_qty,
        ROUND(ROUND(ps.planned_output_units * b.qty_per_assembly * (1.0 + b.scrap_allowance_pct), 2) / 48.0, 2) AS hourly_burn_qty,
        inv.erp_apparent_atp_qty,
        inv.true_pickable_atp_qty,
        inv.phantom_inventory_qty,
        pa.po_number,
        pa.supplier_id,
        pa.ordered_qty AS po_ordered_qty,
        COALESCE(pa.legacy_inbound_qty, 0.0) AS legacy_inbound_qty,
        COALESCE(pa.harmonized_inbound_qty, 0.0) AS harmonized_inbound_qty,
        GREATEST(0.0, pa.ordered_qty - COALESCE(pa.harmonized_inbound_qty, 0.0)) AS supplier_short_shipped_qty,
        (inv.true_pickable_atp_qty + COALESCE(pa.legacy_inbound_qty, 0.0)) AS legacy_total_available_qty,
        (inv.true_pickable_atp_qty + COALESCE(pa.harmonized_inbound_qty, 0.0)) AS harmonized_total_available_qty
    FROM CHAKAN_SCM.PRODUCTION_SCHEDULES ps
    JOIN CHAKAN_SCM.BILL_OF_MATERIALS b
        ON ps.parent_part_num = b.parent_part_num
       AND b.bom_level = 1
    JOIN CHAKAN_SCM.ITEM_MASTER im
        ON b.component_part_num = im.internal_part_num
    LEFT JOIN CHAKAN_SCM.VW_INVENTORY_TRUE_ATP inv
        ON b.component_part_num = inv.internal_part_num
    LEFT JOIN po_asn_rollup pa
        ON b.component_part_num = pa.internal_part_num
),
core AS (
    SELECT
        bb.*,
        ROUND(GREATEST(0.0, bb.gross_required_qty - bb.legacy_total_available_qty), 2) AS legacy_deficit_qty,
        ROUND(GREATEST(0.0, bb.gross_required_qty - bb.harmonized_total_available_qty), 2) AS true_net_deficit_qty,
        ROUND(LEAST(48.0, bb.legacy_total_available_qty / NULLIF(bb.hourly_burn_qty, 0)), 1) AS hours_to_starvation_legacy,
        ROUND(LEAST(48.0, bb.harmonized_total_available_qty / NULLIF(bb.hourly_burn_qty, 0)), 1) AS hours_to_starvation_harmonized,
        LEAST(bb.planned_output_units, CEIL(ROUND(GREATEST(0.0, bb.gross_required_qty - bb.legacy_total_available_qty), 2) / bb.qty_per_assembly)) AS starved_parent_units_legacy,
        LEAST(bb.planned_output_units, CEIL(ROUND(GREATEST(0.0, bb.gross_required_qty - bb.harmonized_total_available_qty), 2) / bb.qty_per_assembly)) AS starved_parent_units_net,
        ROUND(LEAST(bb.planned_output_units, CEIL(ROUND(GREATEST(0.0, bb.gross_required_qty - bb.legacy_total_available_qty), 2) / bb.qty_per_assembly)) * bb.finished_unit_value_inr, 2) AS revenue_at_risk_legacy_inr,
        ROUND(LEAST(bb.planned_output_units, CEIL(ROUND(GREATEST(0.0, bb.gross_required_qty - bb.harmonized_total_available_qty), 2) / bb.qty_per_assembly)) * bb.finished_unit_value_inr, 2) AS revenue_at_risk_net_inr,
        ROUND(GREATEST(0.0, 48.0 - ROUND(LEAST(48.0, bb.harmonized_total_available_qty / NULLIF(bb.hourly_burn_qty, 0)), 1)), 1) AS downtime_hours_net,
        CASE
            WHEN ROUND(GREATEST(0.0, bb.gross_required_qty - bb.harmonized_total_available_qty), 2) > 0
            THEN ROUND(LEAST(75000.0, GREATEST(25000.0, 25000.0 + ROUND(GREATEST(0.0, bb.gross_required_qty - bb.harmonized_total_available_qty), 2) * bb.unit_weight_kg * 4.5)), 2)
            ELSE 0.0
        END AS expedited_freight_cost_inr
    FROM base_bom bb
)
SELECT
    core.*,
    ROUND(core.downtime_hours_net * core.downtime_burn_rate_inr_hr, 2) AS plant_idle_cost_inr,
    ROUND(core.revenue_at_risk_net_inr + ROUND(core.downtime_hours_net * core.downtime_burn_rate_inr_hr, 2), 2) AS total_stoppage_exposure_inr,
    CASE
        WHEN core.expedited_freight_cost_inr > 0
        THEN ROUND((core.revenue_at_risk_net_inr - core.expedited_freight_cost_inr) / core.expedited_freight_cost_inr, 1)
        ELSE 0.0
    END AS mitigation_roi_ratio
FROM core;

-- 4. Financial ROI & Plant Downtime Loss Summary View
CREATE OR REPLACE VIEW CHAKAN_SCM.VW_FINANCIAL_ROI_SUMMARY AS
SELECT
    SUM(revenue_at_risk_legacy_inr) AS legacy_pipeline_risk_inr,
    SUM(revenue_at_risk_net_inr) AS net_starvation_risk_inr,
    SUM(revenue_at_risk_legacy_inr) - SUM(revenue_at_risk_net_inr) AS false_alarm_value_cleared_inr,
    SUM(plant_idle_cost_inr) AS plant_idle_overhead_at_risk_inr,
    SUM(revenue_at_risk_net_inr) + SUM(plant_idle_cost_inr) AS total_plant_loss_exposure_inr,
    SUM(expedited_freight_cost_inr) AS total_mitigation_cost_inr,
    ROUND((SUM(revenue_at_risk_net_inr) - 45000.0) / 45000.0, 1) AS headline_mitigation_roi_x,
    ROUND((SUM(revenue_at_risk_net_inr) - SUM(expedited_freight_cost_inr)) / NULLIF(SUM(expedited_freight_cost_inr), 0), 1) AS all_lines_mitigation_roi_x,
    135000.0 AS panic_freight_avoided_inr
FROM CHAKAN_SCM.VW_BOM_LINE_STARVATION_RISK;
