# Reproducibility & Verification Runbook (`docs/run-guide.md`)

This guide walks through reproducing the **Chakan Plant-1 Inbound ASN Harmonization & Line-Starvation Cockpit** from a clean checkout, both in **Exasol Personal (Live SQL Views & Python 3 UDFs)** mode and in **Offline Pandas Mirror** mode.

---

## 1. Environment Setup (Windows PowerShell / Linux / macOS)

Create and activate an isolated Python 3.12+ virtual environment (`include-system-site-packages = false`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` (optional; defaults target `localhost:8563`):

```powershell
Copy-Item .env.example .env
```

---

## 2. Deterministic Synthetic ERP & ASN Chaos Generation

Regenerate all 7 synthetic ERP master tables and the 498-row inbound ASN chaos stream (`seed = 202610`):

```powershell
.\.venv\Scripts\python.exe -m src.data_generator.generate_all --extra-asns 480
```

### Verified Baseline Invariants (`seed = 202610`, 498 ASN rows)
- **48-Hour Scheduled Output**: `₹37.88 Cr` (`378,750,000.00 INR` across 4 assembly lines)
- **Pre-UDF Legacy Blind-Spot Risk**: `₹26.05 Cr` (`260,500,000.00 INR`)
- **False Alarms Cleared by In-DB Python 3 UDFs**: `₹20.76 Cr` (`207,595,000.00 INR`)
- **True Net Shortage Exposed**: `₹5.29 Cr` (`52,905,000.00 INR` on `AXL-HUB-DUC-14`)
- **Plant Idle Labor & Overhead Exposure**: `₹2.63 Cr` (`26,283,000.00 INR`)
- **Total Unmitigated Stoppage Exposure**: `₹7.92 Cr` (`79,188,000.00 INR`)
- **Warehouse Phantom Inventory Detected**: `₹1.18 Cr` (`11,813,950.00 INR` across `7,138` unpickable units)
- **Headline Emergency Freight ROI**: `1,174.7x` (`₹45,000` charter vs `₹5.29 Cr` net vehicle output protected)

---

## 3. Starting Exasol Personal (Port 8563) & Bootstrapping Schema

### Option A: Docker / Podman Single-Node Container
```powershell
docker run -d --name exasol-personal -p 8563:8563 --privileged --stop-timeout 120 exasol/docker-db:latest
Test-NetConnection -ComputerName localhost -Port 8563
```

### Option B: Bootstrap `CHAKAN_SCM` Schema, Python 3 UDFs, Views, and Tables
```powershell
.\.venv\Scripts\python.exe -c "from src.exasol_engine.db_client import ChakanExasolClient; c = ChakanExasolClient(); mode, ms = c.bootstrap_exasol_schema_and_data(); print(f'Engine: {mode} in {ms}ms')"
```

What `bootstrap_exasol_schema_and_data()` executes and verifies:
1. Creates schema `CHAKAN_SCM` and all 8 tables in [`src/exasol_engine/ddl_schema.sql`](../src/exasol_engine/ddl_schema.sql) with their `DISTRIBUTE BY` keys (`internal_part_num`, `component_part_num`, `parent_part_num`, `po_number_ref`, `asn_line_id`).
2. Compiles 3 Python 3 scalar UDF scripts in [`src/exasol_engine/udfs_harmonization.sql`](../src/exasol_engine/udfs_harmonization.sql):
   - `CHAKAN_SCM.UDF_NORMALIZE_UOM` (`RETURNS DOUBLE`)
   - `CHAKAN_SCM.UDF_RESOLVE_SUPPLIER_SKU` (`EMITS (resolved_part_num, sku_match_method, sku_confidence)` including Jaro-Winkler $\ge 0.85$ similarity)
   - `CHAKAN_SCM.UDF_PARSE_ASN_DATE` (`RETURNS DATE`)
3. Compiles 4 analytical views in [`src/exasol_engine/blast_radius_marts.sql`](../src/exasol_engine/blast_radius_marts.sql):
   - `VW_INVENTORY_TRUE_ATP`
   - `VW_ASN_HARMONIZED_LINEAGE`
   - `VW_BOM_LINE_STARVATION_RISK`
   - `VW_FINANCIAL_ROI_SUMMARY`
4. Bulk-imports all 7 CSV tables via `import_from_pandas` and verifies `SELECT COUNT(*)` on every table against the source DataFrame length (raising `ExasolBootstrapError` on any mismatch or SQL error).

---

## 4. Running the Automated Verification Suite (`pytest`)

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

The test suite in [`tests/test_harmonization.py`](../tests/test_harmonization.py) verifies:
1. `test_uom_normalization_pack_and_weight_inversions`: Pack multipliers (`BOX_100`, `BAG_250`, `CRATE_50`) and weight-to-piece conversions (`MT` $\to$ `KG`, `MT` $\to$ `EA`).
2. `test_supplier_sku_drift_and_jaro_winkler_resolution`: Exact, hyphen-normalized, vendor catalog alias, and Jaro-Winkler ($\ge 0.85$) fuzzy SKU resolution.
3. `test_multiformat_date_parsing`: `DD/MM/YYYY`, `MM/DD/YYYY`, ISO `YYYY-MM-DD`, and Unix epoch disambiguation.
4. `test_blast_radius_analytical_marts`: End-to-end mart calculation, planner override writeback (`ASN-L-9011`), and state idempotency on reset.
5. `test_financial_roi_and_downtime_cost_engine`: Downtime burn rates, freight costs, and ROI calculations.
6. `test_telemetry_and_query_profiler`: Stage timing instrumentation and distribution key metadata.
7. `test_what_if_scenario_simulation_additive_waterfall`: Verifies null shock (`0` delta) and confirms sequential waterfall stages sum identically to total simulated exposure.
8. `test_scale_benchmark_suite`: Verifies pure CPU benchmark (`network_hop_penalty_ms = 0.0`) across 500 to 10,000 rows.
9. `test_broken_connection_raises_explicit_errors`: Confirms broken DB connections raise `ExasolBootstrapError` / `ExasolWriteError` instead of silently passing.
10. `test_exasol_views_match_pandas_mirror`: Confirms `compute_analytical_marts(source="exasol")` and `compute_analytical_marts(source="pandas")` match to `0.00 INR` across all 10 financial KPIs.

---

## 5. Running the Scale Benchmark CLI (500 to 10,000 Rows)

```powershell
.\.venv\Scripts\python.exe -m src.benchmarks.scale_benchmark
```

By default (`--penalty 0.0`), the benchmark reports pure measured CPU wall-clock timings (`~35x` speedup at 10,000 rows: `~84 ms` columnar/set-based vs `~2,960 ms` uncached `iterrows()` row-by-row ETL) and real `memory_usage(deep=True)` footprints.

---

## 6. Launching the Materials Planner Cockpit UI

```powershell
.\.venv\Scripts\python.exe -m streamlit run src/app/app.py
```

Open `http://localhost:8501` in your browser. When Exasol Personal is active on `localhost:8563`, the telemetry banner displays `🟢 EXASOL PERSONAL (LIVE SQL VIEWS & UDFs)` and `Compute Source: EXASOL_VIEWS`.
