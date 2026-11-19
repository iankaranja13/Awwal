"""Benchmark end-to-end behaviour."""

from pathlib import Path

from benchmark.run_benchmark import main


def test_benchmark_passes_with_zero_under_triage(tmp_path: Path) -> None:
    """Run the benchmark and require full core agreement."""
    db_url = f"sqlite:///{tmp_path / 'bench.db'}"
    output_dir = tmp_path / "reports"
    summary = main(
        ["--output-dir", str(output_dir), "--variants", "20", "--db-url", db_url, "--quiet"]
    )
    assert summary["core_matched"] == 10
    assert summary["under_triage"] == 0
    assert summary["clear_violations"] == 0
    assert summary["mono_violations"] == 0
    assert summary["failures"] == []
    assert (output_dir / "report.json").exists()
    assert (output_dir / "report.md").exists()
