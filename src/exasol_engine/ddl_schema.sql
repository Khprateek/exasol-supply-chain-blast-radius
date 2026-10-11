-- Exasol Personal DDL Schema for Pune-Chakan Powertrain Supply Chain & Inbound ASN Lineage
-- Target Schema: CHAKAN_SCM

CREATE SCHEMA IF NOT EXISTS CHAKAN_SCM;
OPEN SCHEMA CHAKAN_SCM;

-- 1. Supplier Registry (Tier-1 Integrators & Tier-2/3 MSME Vendors)
CREATE OR REPLACE TABLE SUPPLIER_MASTER (
    supplier_id             VARCHAR(24) UTF8 NOT NULL,
    supplier_name           VARCHAR(120) UTF8 NOT NULL,
    tier_level              VARCHAR(12) UTF8 NOT NULL,
    industrial_cluster      VARCHAR(60) UTF8 NOT NULL,
    state_code              VARCHAR(10) UTF8 NOT NULL,
    integration_channel     VARCHAR(30) UTF8 NOT NULL,
    default_date_format     VARCHAR(20) UTF8 NOT NULL,
    historical_otd_rate     DECIMAL(5, 4) NOT NULL,
    avg_lead_time_drift_days DECIMAL(6, 2) NOT NULL,
    CONSTRAINT pk_supplier_master PRIMARY KEY (supplier_id) ENABLE
);

-- 2. Internal Material Master (Finished Assemblies, Sub-Assemblies & Raw Components)
CREATE OR REPLACE TABLE ITEM_MASTER (
    internal_part_num       VARCHAR(40) UTF8 NOT NULL,
    part_description        VARCHAR(160) UTF8 NOT NULL,
    part_category           VARCHAR(40) UTF8 NOT NULL,
    base_uom                VARCHAR(12) UTF8 NOT NULL,
    standard_pack_size_ea   DECIMAL(12, 2) NOT NULL,
    unit_weight_kg          DECIMAL(12, 4) NOT NULL,
    standard_cost_inr       DECIMAL(14, 2) NOT NULL,
    safety_stock_qty        DECIMAL(14, 2) NOT NULL,
    planned_lead_time_days  DECIMAL(6, 1) NOT NULL,
    criticality_class       VARCHAR(4) UTF8 NOT NULL,
    CONSTRAINT pk_item_master PRIMARY KEY (internal_part_num) ENABLE,
    DISTRIBUTE BY internal_part_num
);

-- 3. Multi-Level Bill of Materials (Parent Assembly -> Component SKU)
CREATE OR REPLACE TABLE BILL_OF_MATERIALS (
    bom_id                  VARCHAR(32) UTF8 NOT NULL,
    parent_part_num         VARCHAR(40) UTF8 NOT NULL,
    component_part_num      VARCHAR(40) UTF8 NOT NULL,
    qty_per_assembly        DECIMAL(12, 4) NOT NULL,
    scrap_allowance_pct     DECIMAL(6, 4) NOT NULL,
    bom_level               DECIMAL(3, 0) NOT NULL,
    assembly_station_code   VARCHAR(24) UTF8 NOT NULL,
    CONSTRAINT pk_bom PRIMARY KEY (bom_id) ENABLE,
    DISTRIBUTE BY component_part_num
);

-- 4. Commercial Purchase Orders (Header + Line Combined for High-Throughput Joins)
CREATE OR REPLACE TABLE PURCHASE_ORDER_LINES (
    po_line_id              VARCHAR(40) UTF8 NOT NULL,
    po_number               VARCHAR(28) UTF8 NOT NULL,
    line_number             DECIMAL(5, 0) NOT NULL,
    supplier_id             VARCHAR(24) UTF8 NOT NULL,
    internal_part_num       VARCHAR(40) UTF8 NOT NULL,
    ordered_qty             DECIMAL(14, 2) NOT NULL,
    ordered_uom             VARCHAR(12) UTF8 NOT NULL,
    unit_price_inr          DECIMAL(14, 2) NOT NULL,
    order_date              DATE NOT NULL,
    promised_delivery_date  DATE NOT NULL,
    po_line_status          VARCHAR(20) UTF8 NOT NULL,
    CONSTRAINT pk_po_lines PRIMARY KEY (po_line_id) ENABLE,
    DISTRIBUTE BY internal_part_num
);

-- 5. Inbound Supplier Advance Shipping Notices (Raw + Quarantine Lineage Preserved)
CREATE OR REPLACE TABLE ASN_LINES_RAW (
    asn_line_id             VARCHAR(40) UTF8 NOT NULL,
    asn_number              VARCHAR(32) UTF8 NOT NULL,
    supplier_id             VARCHAR(24) UTF8 NOT NULL,
    po_number_ref           VARCHAR(28) UTF8 NOT NULL,
    po_line_number_ref      DECIMAL(5, 0),
    raw_supplier_sku        VARCHAR(80) UTF8 NOT NULL,
    raw_shipped_qty         DECIMAL(16, 4) NOT NULL,
    raw_shipped_uom         VARCHAR(24) UTF8 NOT NULL,
    raw_shipment_date       VARCHAR(40) UTF8 NOT NULL,
    raw_eta_date            VARCHAR(40) UTF8 NOT NULL,
    carrier_name            VARCHAR(60) UTF8 NOT NULL,
    vehicle_lorry_no        VARCHAR(30) UTF8 NOT NULL,
    source_format           VARCHAR(30) UTF8 NOT NULL,
    legacy_etl_status       VARCHAR(24) UTF8 NOT NULL,
    anomaly_type            VARCHAR(50) UTF8 NOT NULL,
    ingested_at             TIMESTAMP NOT NULL,
    CONSTRAINT pk_asn_lines_raw PRIMARY KEY (asn_line_id) ENABLE,
    DISTRIBUTE BY po_number_ref
);

-- 6. Warehouse Inventory Ledger (Reconciling Central ERP vs. Physical WMS Bins)
CREATE OR REPLACE TABLE WAREHOUSE_INVENTORY_LEDGER (
    ledger_id               VARCHAR(36) UTF8 NOT NULL,
    facility_code           VARCHAR(24) UTF8 NOT NULL,
    storage_bin_id          VARCHAR(24) UTF8 NOT NULL,
    internal_part_num       VARCHAR(40) UTF8 NOT NULL,
    erp_system_on_hand_qty  DECIMAL(14, 2) NOT NULL,
    wms_physical_counted_qty DECIMAL(14, 2) NOT NULL,
    allocated_to_prod_qty   DECIMAL(14, 2) NOT NULL,
    quality_hold_qty        DECIMAL(14, 2) NOT NULL,
    last_cycle_count_ts     TIMESTAMP NOT NULL,
    CONSTRAINT pk_warehouse_ledger PRIMARY KEY (ledger_id) ENABLE,
    DISTRIBUTE BY internal_part_num
);

-- 7. Plant Production Schedules (Assembly Line Execution Windows & Revenue Value)
CREATE OR REPLACE TABLE PRODUCTION_SCHEDULES (
    schedule_id             VARCHAR(32) UTF8 NOT NULL,
    assembly_line_id        VARCHAR(20) UTF8 NOT NULL,
    assembly_line_name      VARCHAR(80) UTF8 NOT NULL,
    parent_part_num         VARCHAR(40) UTF8 NOT NULL,
    scheduled_start_ts      TIMESTAMP NOT NULL,
    scheduled_end_ts        TIMESTAMP NOT NULL,
    planned_output_units    DECIMAL(12, 0) NOT NULL,
    finished_unit_value_inr DECIMAL(14, 2) NOT NULL,
    downtime_burn_rate_inr_hr DECIMAL(14, 2) NOT NULL,
    schedule_status         VARCHAR(20) UTF8 NOT NULL,
    CONSTRAINT pk_prod_schedules PRIMARY KEY (schedule_id) ENABLE,
    DISTRIBUTE BY parent_part_num
);

-- 8. Planner Resolution Overrides (Interactive Writeback Audit Log)
CREATE OR REPLACE TABLE ASN_PLANNER_OVERRIDES (
    asn_line_id             VARCHAR(40) UTF8 NOT NULL,
    resolved_part_num       VARCHAR(40) UTF8 NOT NULL,
    normalized_qty          DECIMAL(14, 2) NOT NULL,
    normalized_uom          VARCHAR(12) UTF8 NOT NULL,
    normalized_eta_date     DATE NOT NULL,
    resolution_action       VARCHAR(30) UTF8 NOT NULL,
    resolved_by             VARCHAR(60) UTF8 NOT NULL,
    resolved_at             TIMESTAMP NOT NULL,
    CONSTRAINT pk_asn_overrides PRIMARY KEY (asn_line_id) ENABLE
);
