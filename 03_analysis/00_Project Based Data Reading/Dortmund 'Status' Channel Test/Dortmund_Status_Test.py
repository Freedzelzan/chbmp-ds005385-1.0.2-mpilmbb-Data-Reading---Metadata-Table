import argparse
import os
import warnings
from pathlib import Path

import mne
import numpy as np

warnings.filterwarnings("ignore")


def find_dataset_root() -> Path:
    candidates = [
        Path(r"E:\project-healthyageing\02_data\00_download\ds005385-1.0.2"),
        Path(__file__).resolve().parent / "02_data" / "00_download" / "ds005385-1.0.2",
        Path(__file__).resolve().parent / "02_data" / "00_download" / "ds005385-1.0.2".replace("/", "\\"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def extract_status_info(file_path: Path, max_rows: int = 10000):
    raw = mne.io.read_raw_edf(file_path, preload=False, verbose=False)
    ch_names = raw.ch_names

    if "Status" not in ch_names:
        return None

    status_idx = ch_names.index("Status")
    sfreq = float(raw.info["sfreq"])
    n_times = int(raw.n_times)

    data = raw.get_data(picks=[status_idx], start=0, stop=n_times)[0]
    finite_data = data[np.isfinite(data)]
    unique_vals = np.unique(finite_data)

    rows = []
    export_limit = min(max_rows, n_times)
    for i in range(export_limit):
        value = data[i]
        if np.isfinite(value):
            if float(value) != 0.0:
                rows.append(f"{Path(file_path).name}\t{i}\t{round(i / sfreq, 6)}\t{value}")
        else:
            rows.append(f"{Path(file_path).name}\t{i}\t{round(i / sfreq, 6)}\tNaN")

    return {
        "file": str(file_path),
        "sfreq": sfreq,
        "n_times": n_times,
        "unique_values": [str(v) for v in unique_vals],
        "rows": rows,
    }


def write_output(output_path: Path, dataset_root: Path, results, max_rows: int):
    lines = []
    lines.append("Dortmund Status Channel Export")
    lines.append(f"Dataset Root: {dataset_root}")
    lines.append(f"Exported Rows Per File: {max_rows}")
    lines.append("")

    if not results:
        lines.append("No Status channel found in any matching file.")
    else:
        for item in results:
            lines.append(f"=== {Path(item['file']).name} ===")
            lines.append(f"Sampling Rate: {item['sfreq']}")
            lines.append(f"Sample Count: {item['n_times']}")
            lines.append(f"Unique Values: {', '.join(item['unique_values']) if item['unique_values'] else 'None'}")
            lines.append("Name\tsample_index\ttime_sec\tvalue")
            lines.extend(item["rows"])
            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Export completed: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Export Dortmund Status channel values to a txt file")
    parser.add_argument("--root", type=str, default=None, help="Dataset root directory")
    parser.add_argument("--output", type=str, default="Dortmund_Status_Export.txt", help="Output txt file")
    parser.add_argument("--limit", type=int, default=10000, help="How many samples to export per file")
    args = parser.parse_args()

    dataset_root = Path(args.root).expanduser() if args.root else find_dataset_root()
    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parent / output_path

    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset root not found: {dataset_root}")

    edf_files = sorted(dataset_root.rglob("*task-EyesClosed_acq-pre_eeg.edf"))
    if not edf_files:
        raise FileNotFoundError(f"No matching EDF files found under: {dataset_root}")

    results = []
    for file_path in edf_files:
        try:
            item = extract_status_info(file_path, max_rows=args.limit)
            if item is not None:
                results.append(item)
        except Exception as exc:
            print(f"Skipped {file_path.name}: {exc}")

    write_output(output_path, dataset_root, results, args.limit)


if __name__ == "__main__":
    main()
