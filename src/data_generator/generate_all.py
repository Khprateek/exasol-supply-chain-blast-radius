from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict
import pandas as pd

from src.data_generator.erp_master_gen import build_all_erp_tables
from src.data_generator.chaos_injector import generate_inbound_asn_chaos


def generate_dataset(output_dir: str = "data/raw", seed: int = 202610, extra_asns: int = 480) -> Dict[str, pd.DataFrame]:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    tables = build_all_erp_tables(seed=seed)
    tables["ASN_LINES_RAW"] = generate_inbound_asn_chaos(tables, extra_batch_rows=extra_asns, seed=seed)
    tables["ASN_PLANNER_OVERRIDES"] = pd.DataFrame(
        columns=[
            "asn_line_id",
            "resolved_part_num",
            "normalized_qty",
            "normalized_uom",
            "normalized_eta_date",
            "resolution_action",
            "resolved_by",
            "resolved_at",
        ]
    )

    for table_name, df in tables.items():
        csv_file = out_path / f"{table_name.lower()}.csv"
        df.to_csv(csv_file, index=False)

    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Pune-Chakan supply chain & ASN chaos dataset.")
    parser.add_argument("--output-dir", default=os.getenv("DATA_OUTPUT_DIR", "data/raw"))
    parser.add_argument("--seed", type=int, default=int(os.getenv("RANDOM_SEED", "202610")))
    parser.add_argument("--extra-asns", type=int, default=480)
    args = parser.parse_args()

    tables = generate_dataset(output_dir=args.output_dir, seed=args.seed, extra_asns=args.extra_asns)
    for name, df in tables.items():
        print(f"{name:<28} : {len(df):>6} rows -> {args.output_dir}/{name.lower()}.csv")


if __name__ == "__main__":
    main()
