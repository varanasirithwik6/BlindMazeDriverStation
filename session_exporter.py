"""
session_exporter.py — Session log and match analytics exporter (CSV & TXT reports).
"""

from __future__ import annotations

import os
from datetime import datetime


class SessionExporter:
    """Exports session summary reports to files."""

    @staticmethod
    def export_report(logs: list[str], match_time_str: str) -> str:
        os.makedirs("assets/reports", exist_ok=True)
        filename = f"match_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join("assets/reports", filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("==================================================\n")
            f.write("   BLIND MAZE DRIVER STATION — MATCH REPORT\n")
            f.write("==================================================\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Session Duration: {match_time_str}\n\n")
            f.write("SYSTEM LOG HISTORY:\n")
            f.write("--------------------------------------------------\n")
            for log in logs:
                f.write(f"{log}\n")

        return filepath
