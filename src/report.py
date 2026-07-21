from datetime import datetime
import pandas as pd

from src.config import OUTPUT_DIR


def export_report(results: list[dict]) -> str:
    df = pd.DataFrame(results)

    if df.empty:
        raise ValueError("No results to export.")

    df = df.sort_values("discovery_score", ascending=False)

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"discovery_scores_{today}.csv"

    df.to_csv(output_path, index=False)

    return str(output_path)