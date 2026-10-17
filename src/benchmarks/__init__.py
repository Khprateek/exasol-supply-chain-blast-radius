"""High-Scale Benchmarking & Throughput Verification Suite for Chakan SCM."""

__all__ = [
    "benchmark_exasol_columnar",
    "benchmark_legacy_row_by_row",
    "get_verified_scale_benchmark",
    "run_scale_benchmark",
]


def __getattr__(name: str):
    if name in __all__:
        from . import scale_benchmark

        return getattr(scale_benchmark, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
