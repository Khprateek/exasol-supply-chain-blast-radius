-- Exasol Personal In-Database Python 3 Scalar UDFs for Multi-Supplier ASN Harmonization
-- Target Schema: CHAKAN_SCM

OPEN SCHEMA CHAKAN_SCM;

-- 1. In-Database UOM & Bulk-Pack Quantity Normalization UDF
-- Converts BOX_100, BAG_250, CRATE_40, CRATE_50, MT, and LB into canonical ITEM_MASTER base_uom
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT CHAKAN_SCM.UDF_NORMALIZE_UOM(
    raw_qty DOUBLE,
    raw_uom VARCHAR(24) UTF8,
    target_uom VARCHAR(12) UTF8,
    pack_size_ea DOUBLE,
    unit_weight_kg DOUBLE
) RETURNS DOUBLE AS
import re

def run(ctx):
    if ctx.raw_qty is None:
        return 0.0
    qty = float(ctx.raw_qty)
    src = (ctx.raw_uom or "").strip().upper()
    tgt = (ctx.target_uom or "EA").strip().upper()

    if src == tgt:
        return round(qty, 2)

    pack_match = re.match(r"^(?:BOX|BAG|CRATE|PACK|PALLET)_(\d+)$", src)
    if pack_match and tgt == "EA":
        return round(qty * float(pack_match.group(1)), 2)

    if src in ("BOX", "BAG", "CRATE", "PACK") and tgt == "EA":
        mult = float(ctx.pack_size_ea) if ctx.pack_size_ea and ctx.pack_size_ea > 0 else 1.0
        return round(qty * mult, 2)

    if src == "MT" and tgt == "KG":
        return round(qty * 1000.0, 2)

    if src == "MT" and tgt == "EA" and ctx.unit_weight_kg and ctx.unit_weight_kg > 0:
        return round((qty * 1000.0) / float(ctx.unit_weight_kg), 2)

    if src == "KG" and tgt == "EA" and ctx.unit_weight_kg and ctx.unit_weight_kg > 0:
        return round(qty / float(ctx.unit_weight_kg), 2)

    if src in ("LB", "LBS") and tgt == "KG":
        return round(qty * 0.45359237, 2)

    return round(qty, 2)
/

-- 2. In-Database Supplier SKU Drift & Alias Resolution UDF
-- Emits resolved internal_part_num, match_method, and confidence score
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT CHAKAN_SCM.UDF_RESOLVE_SUPPLIER_SKU(
    raw_sku VARCHAR(80) UTF8,
    po_part_num VARCHAR(40) UTF8
) EMITS (
    resolved_part_num VARCHAR(40) UTF8,
    sku_match_method VARCHAR(30) UTF8,
    sku_confidence DOUBLE
) AS
import re

ALIASES = {
    "6204ZZ": "ENG-BRG-6204-01",
    "FBD6204ZZ": "ENG-BRG-6204-01",
    "M12X15HT109": "ENG-BLT-M12-109",
    "42CRCONROD04": "ENG-CRD-42CR-04",
    "HSRHEL34": "TRN-GER-HEL-34",
    "DUCHUB14": "AXL-HUB-DUC-14",
    "FKM85SEAL": "AXL-SEL-FKM-85",
    "STALAM01SIL": "EVC-STA-LAM-01",
    "CUHAIRPIN04": "EVC-WND-CU-04",
    "42CRMO4BILLET": "RAW-STL-42CR-B",
}

def _jaro_winkler(s1, s2, prefix_weight=0.1):
    a = (s1 or "").strip().upper()
    b = (s2 or "").strip().upper()
    if a == b:
        return 1.0 if a else 0.0
    len_a, len_b = len(a), len(b)
    if len_a == 0 or len_b == 0:
        return 0.0
    match_dist = max(0, max(len_a, len_b) // 2 - 1)
    a_matches = [False] * len_a
    b_matches = [False] * len_b
    matches = 0
    for i in range(len_a):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, len_b)
        for j in range(start, end):
            if b_matches[j] or a[i] != b[j]:
                continue
            a_matches[i] = True
            b_matches[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    transpositions = 0
    k = 0
    for i in range(len_a):
        if not a_matches[i]:
            continue
        while not b_matches[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1
    jaro = ((matches / len_a) + (matches / len_b) + ((matches - transpositions / 2.0) / matches)) / 3.0
    prefix = 0
    for ch_a, ch_b in zip(a[:4], b[:4]):
        if ch_a == ch_b:
            prefix += 1
        else:
            break
    return round(min(1.0, jaro + prefix * prefix_weight * (1.0 - jaro)), 4)

def run(ctx):
    cleaned_raw = (ctx.raw_sku or "").strip().upper()
    cleaned_po = (ctx.po_part_num or "").strip().upper()

    if cleaned_po and cleaned_raw == cleaned_po:
        ctx.emit(cleaned_po, "EXACT_MATCH", 1.00)
        return

    alnum_raw = re.sub(r"[^A-Z0-9]", "", cleaned_raw)
    alnum_po = re.sub(r"[^A-Z0-9]", "", cleaned_po)

    if alnum_po and alnum_raw == alnum_po:
        ctx.emit(cleaned_po, "HYPHEN_NORMALIZED", 0.98)
        return

    if alnum_raw in ALIASES:
        ctx.emit(ALIASES[alnum_raw], "VENDOR_CATALOG_ALIAS", 0.95)
        return

    if cleaned_po:
        po_tokens = [t for t in cleaned_po.split("-") if len(t) >= 2]
        matched = sum(1 for tok in po_tokens if tok in alnum_raw)
        if po_tokens and matched >= max(1, len(po_tokens) - 1):
            ctx.emit(cleaned_po, "PO_TOKEN_SIMILARITY", 0.89)
            return

        jw_po = _jaro_winkler(alnum_raw, alnum_po)
        if jw_po >= 0.85:
            ctx.emit(cleaned_po, "JARO_WINKLER_FUZZY", round(jw_po, 2))
            return

    if alnum_raw:
        best_alias_sku = None
        best_jw = 0.0
        for alias_key, canonical_sku in ALIASES.items():
            score = _jaro_winkler(alnum_raw, alias_key)
            if score > best_jw:
                best_jw = score
                best_alias_sku = canonical_sku
        if best_alias_sku and best_jw >= 0.85:
            ctx.emit(best_alias_sku, "JARO_WINKLER_FUZZY", round(best_jw, 2))
            return

    if cleaned_po:
        ctx.emit(cleaned_po, "PO_LINEAGE_FALLBACK", 0.82)
        return

    ctx.emit(cleaned_raw, "UNRESOLVED", 0.00)
/

-- 3. In-Database Multi-Format Date Harmonization UDF
-- Disambiguates DD/MM/YYYY, MM/DD/YYYY, ISO YYYY-MM-DD, and Unix Epoch strings
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT CHAKAN_SCM.UDF_PARSE_ASN_DATE(
    raw_date_str VARCHAR(40) UTF8,
    supplier_date_fmt VARCHAR(20) UTF8
) RETURNS DATE AS
-- NOTE: do NOT write `from datetime import datetime` here. Exasol's UDF wrapper uses the
-- module name `datetime` in the same global namespace to convert the DATE return value,
-- so shadowing it raises "type object 'datetime.datetime' has no attribute 'datetime'".
import datetime as _dt
import re

_DEFAULT = _dt.date(2026, 10, 12)

def run(ctx):
    val = (ctx.raw_date_str or "").strip()
    if not val:
        return _DEFAULT

    if re.fullmatch(r"\d{9,10}", val):
        d = _dt.datetime.fromtimestamp(int(val), tz=_dt.timezone.utc).date()
        return d if d.year == 2026 else _DEFAULT

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", val):
        return _dt.datetime.strptime(val, "%Y-%m-%d").date()

    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", val)
    if slash_match:
        first = int(slash_match.group(1))
        second = int(slash_match.group(2))
        year = int(slash_match.group(3))
        fmt_pref = (ctx.supplier_date_fmt or "DD/MM/YYYY").strip().upper()
        if first > 12:
            return _dt.date(year, second, first)
        if second > 12:
            return _dt.date(year, first, second)
        if fmt_pref == "MM/DD/YYYY":
            return _dt.date(year, first, second)
        return _dt.date(year, second, first)

    for fmt in ("%d-%b-%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return _dt.datetime.strptime(val, fmt).date()
        except ValueError:
            continue

    return _DEFAULT
/

