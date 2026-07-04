"""
Builds the self-contained interactive dashboard HTML by merging
output/dashboard_data.json (plus output/brief.txt, if present) into
templates/dashboard_template.html.
"""
import json
from datetime import datetime, timezone

from config import load_config, OUTPUT_DIR, TEMPLATES_DIR


def load_merged_data() -> dict:
    """Load the computed data, merging in the narrative brief if one exists.
    Shared by build_dashboard.py and build_report.py so both surfaces always
    show the same brief text.
    """
    with open(OUTPUT_DIR / "dashboard_data.json") as f:
        data = json.load(f)

    brief_path = OUTPUT_DIR / "brief.txt"
    if brief_path.exists():
        data["narrative_brief"] = brief_path.read_text().strip()
        data["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return data


def main(cfg: dict | None = None):
    cfg = cfg or load_config()
    data = load_merged_data()

    template = (TEMPLATES_DIR / "dashboard_template.html").read_text()
    html = template.replace("/*__DATA_JSON__*/", json.dumps(data))

    out_path = OUTPUT_DIR / "dashboard.html"
    out_path.write_text(html)
    print(f"Saved {out_path.name}")
    return out_path


if __name__ == "__main__":
    main()
