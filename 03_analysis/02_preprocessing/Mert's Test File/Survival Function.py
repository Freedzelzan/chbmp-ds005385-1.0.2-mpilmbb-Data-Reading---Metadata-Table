import mne
import pandas as pd
import os
import glob
import re
import warnings
from openpyxl.chart import LineChart, Reference

# Suppress warning messages from MNE and pandas so the processing output stays
# focused on the status messages printed below.
warnings.filterwarnings('ignore')

BASE_DIR_DORT = r"E:\project-healthyageing\02_data\00_download\ds005385-1.0.2"
annotations_dir = r"C:\Users\merte\Desktop\annotation csv"

# Save the survival function table directly on the current user's Desktop.
output_file = r"C:\Users\merte\Desktop\survival_function.xlsx"

# Minimum clean segment durations to evaluate.
MIN_DURATION_VALUES = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]

# Search recursively for pre- and post-acquisition EyesClosed EDF files under
# each subject's EEG folder.
search_pattern = os.path.join(
    BASE_DIR_DORT,
    "sub-*",
    "**",
    "eeg",
    "*task-EyesClosed_acq-*_eeg.edf",
)
edf_files = sorted(glob.glob(search_pattern, recursive=True))

print(f"\nFound {len(edf_files)} EDF files.")

recording_rows = []
interval_rows = []
missing_annotation_count = 0

# Process each EDF file and its corresponding annotation CSV to find the clean
# intervals between bad segments.
for file_path in edf_files:
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    annotation_file = os.path.join(
        annotations_dir,
        f"{file_name}_annotations.csv",
    )

    # Skip recordings that do not have a matching annotation CSV.
    if not os.path.exists(annotation_file):
        missing_annotation_count += 1
        continue

    print(f"\nProcessing: {file_name}")

    # Read the bad-segment onset and duration values from the annotation CSV.
    annotation_df = pd.read_csv(annotation_file)

    # Only the header is needed here, because the clean intervals depend on the
    # recording duration and start time, not on the EEG samples.
    raw = mne.io.read_raw_edf(file_path, preload=False, verbose=False)
    # Get the total duration of the recording in seconds for later use.
    total_duration = raw.times[-1]

    # Convert the onset values in the annotation CSV to seconds relative to the
    # start of the recording, and store the bad segments in a list of tuples.
    bad_segments = []
    if not annotation_df.empty:
        for _, row in annotation_df.iterrows():
            onset_value = pd.to_numeric(row['onset'], errors="coerce")
            if pd.isna(onset_value):
                annotation_onset = pd.Timestamp(row['onset'])
                recording_start = raw.info['meas_date']
                if recording_start is None:
                    raise ValueError(
                        f"Cannot convert timestamp onset because the recording "
                        f"start time is unavailable: {file_path}"
                    )
                # Convert both timestamps to UTC and remove timezone information for
                # accurate subtraction.
                recording_start = pd.Timestamp(recording_start)
                if annotation_onset.tz is not None:
                    annotation_onset = annotation_onset.tz_convert(
                        "UTC"
                    ).tz_localize(None)
                if recording_start.tz is not None:
                    recording_start = recording_start.tz_convert(
                        "UTC"
                    ).tz_localize(None)
                onset = (annotation_onset - recording_start).total_seconds()
            else:
                onset = float(onset_value)

            # Convert the duration value to a float and store the bad segment as a tuple.
            duration = float(row['duration'])
            bad_segments.append((onset, duration))
        bad_segments.sort(key=lambda segment: segment[0])

    # Collect the clean intervals with the same logic used in the bad segment
    # removal script, without applying any minimum duration yet.
    clean_intervals = []
    current_time = 0.0

    for onset, duration in bad_segments:
        # The interval before this bad segment is clean when its onset is after
        # the end of the previously processed bad segment.
        if onset > current_time:
            clean_intervals.append((current_time, onset))

        # Move the start of the next clean interval to the end of this bad
        # segment, while keeping the furthest end when bad segments overlap.
        current_time = max(current_time, onset + duration)

    # Check the clean interval after the final bad segment separately.
    if current_time < total_duration:
        clean_intervals.append((current_time, total_duration))

    # Read the subject and acquisition labels from the BIDS file name.
    subject_match = re.search(r"sub-([^_]+)", file_name)
    acquisition_match = re.search(r"acq-([^_]+)", file_name)
    subject = subject_match.group(1) if subject_match else "unknown"
    acquisition = acquisition_match.group(1) if acquisition_match else "unknown"

    clean_durations = [end - start for start, end in clean_intervals]
    longest_clean = max(clean_durations) if clean_durations else 0.0

    recording_row = {
        "File": file_name,
        "Subject": subject,
        "Acquisition": acquisition,
        "Recording duration (s)": round(total_duration, 1),
        "Bad segments": len(bad_segments),
        "Clean intervals": len(clean_intervals),
        "Total clean duration (s)": round(sum(clean_durations), 1),
        "Longest clean interval (s)": round(longest_clean, 1),
    }

    # Count the segment files and the clean duration that each minimum
    # duration would keep for this recording.
    for threshold in MIN_DURATION_VALUES:
        kept_durations = [d for d in clean_durations if d >= threshold]
        recording_row[f"Segments >= {threshold:.0f}s"] = len(kept_durations)
        recording_row[f"Kept duration >= {threshold:.0f}s (s)"] = round(
            sum(kept_durations), 1
        )
    recording_rows.append(recording_row)

    # Store every clean interval so the individual values can be checked later.
    for interval_index, (start, end) in enumerate(clean_intervals, start=1):
        interval_rows.append({
            "File": file_name,
            "Subject": subject,
            "Acquisition": acquisition,
            "Interval": interval_index,
            "Start (s)": round(start, 1),
            "End (s)": round(end, 1),
            "Duration (s)": round(end - start, 1),
        })

    print(
        f"  -> Found {len(clean_intervals)} clean intervals "
        f"(longest {longest_clean:.1f}s)."
    )

if not recording_rows:
    raise SystemExit("\nNo recordings with annotation CSV files were found.")

recording_df = pd.DataFrame(recording_rows)
interval_df = pd.DataFrame(interval_rows)

total_recordings = len(recording_df)
total_subjects = recording_df['Subject'].nunique()
acquisitions = sorted(recording_df['Acquisition'].unique())
all_acquisitions_label = (
    f"Subjects with all acquisitions ({', '.join(acquisitions)})"
)

# Build the survival function: a recording survives a minimum duration when it
# keeps at least one clean segment of that length, and a subject survives when
# all of its acquisitions survive.
summary_rows = []
for threshold in MIN_DURATION_VALUES:
    segment_column = f"Segments >= {threshold:.0f}s"
    duration_column = f"Kept duration >= {threshold:.0f}s (s)"

    surviving_df = recording_df[recording_df[segment_column] > 0]
    acquisition_counts = surviving_df.groupby('Subject')['Acquisition'].nunique()
    subjects_with_all = int((acquisition_counts == len(acquisitions)).sum())

    summary_row = {
        "MIN_DURATION_SEC": threshold,
        "Surviving recordings": len(surviving_df),
        "Total recordings": total_recordings,
        "Recording survival (%)": round(
            100.0 * len(surviving_df) / total_recordings, 1
        ),
        "Saved segment files": int(recording_df[segment_column].sum()),
        "Kept clean duration (min)": round(
            recording_df[duration_column].sum() / 60.0, 1
        ),
        "Subjects with any recording": surviving_df['Subject'].nunique(),
        all_acquisitions_label: subjects_with_all,
        "Total subjects": total_subjects,
        "Subject survival (%)": round(100.0 * subjects_with_all / total_subjects, 1),
    }

    # Report the surviving recordings separately for each acquisition.
    for acquisition in acquisitions:
        summary_row[f"Surviving acq-{acquisition} recordings"] = int(
            (surviving_df['Acquisition'] == acquisition).sum()
        )
    summary_rows.append(summary_row)

summary_df = pd.DataFrame(summary_rows)

# Write the summary, the per-recording results and the clean intervals to
# separate sheets of the Excel file.
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    summary_df.to_excel(writer, sheet_name="Survival Function", index=False)
    recording_df.to_excel(writer, sheet_name="Per Recording", index=False)
    interval_df.to_excel(writer, sheet_name="Clean Intervals", index=False)

    # Add a line chart of surviving recordings and subjects to the summary sheet.
    summary_sheet = writer.sheets["Survival Function"]
    last_row = len(summary_df) + 1

    chart = LineChart()
    chart.title = "Survival Function"
    chart.x_axis.title = "MIN_DURATION_SEC"
    chart.y_axis.title = "Count"
    chart.height = 9
    chart.width = 18

    for column_name in ["Surviving recordings", all_acquisitions_label]:
        column_index = list(summary_df.columns).index(column_name) + 1
        data = Reference(
            summary_sheet,
            min_col=column_index,
            min_row=1,
            max_row=last_row,
        )
        chart.add_data(data, titles_from_data=True)

    categories = Reference(summary_sheet, min_col=1, min_row=2, max_row=last_row)
    chart.set_categories(categories)
    summary_sheet.add_chart(chart, f"A{last_row + 3}")

    # Widen each column to fit its header and values.
    for worksheet in writer.sheets.values():
        for column_cells in worksheet.columns:
            max_length = max(
                len(str(cell.value)) if cell.value is not None else 0
                for cell in column_cells
            )
            worksheet.column_dimensions[
                column_cells[0].column_letter
            ].width = max_length + 2

print(f"\nRecordings without annotation CSV: {missing_annotation_count}")
print(f"\n{summary_df.to_string(index=False)}")
print(f"\nSaved survival function to: {output_file}")