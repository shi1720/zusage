"""Validate the public submission paths on a clean checkout."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
project = root / "track_2a"
required = ["README.md", "technical_report.md", "Makefile", "src", "data", "docs", "Dockerfile"]
for path in required:
    assert (project / path).exists(), f"Missing template path: track_2a/{path}"
for track in ["track_1a", "track_1b", "track_2b"]:
    assert not (root / track).exists(), f"Unused track must be removed: {track}"
size = sum(p.stat().st_size for p in (project / "data").rglob("*") if p.is_file())
assert size < 100_000_000, f"data exceeds the 100 MB limit: {size} bytes"
report = (project / "technical_report.md").read_text()
for number, section in enumerate(["Summary", "Architecture", "Use of Apertus", "Data", "Evaluation", "Limitations", "Reproducibility", "Next steps"], 1):
    assert f"## {number}. {section}" in report, f"Missing report section: {section}"
for doc in [root / "README.md", project / "README.md", project / "technical_report.md", project / "docs/OVERVIEW.md"]:
    for link in re.findall(r"\]\(([^)]+)\)", doc.read_text()):
        if "://" not in link and not link.startswith("#"):
            assert (doc.parent / link.split("#")[0]).exists(), f"Broken link in {doc.name}: {link}"
print(f"Template paths, report sections and links verified; data size {size:,} bytes < 100 MB.")
