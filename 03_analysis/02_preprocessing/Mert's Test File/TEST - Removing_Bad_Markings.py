import mne
import pandas as pd
import os
import glob
import warnings

# Suppress warning messages from MNE and pandas so the processing output stays
# focused on the status messages printed below.
warnings.filterwarnings('ignore')

BASE_DIR_DORT = r"E:\project-healthyageing\02_data\00_download\ds005385-1.0.2"
annotations_dir = r"C:\Users\merte\Desktop\annotation csv"

# Save the cleaned EEG segments in a separate folder on the current user's
# Desktop.
output_dir = r"C:\Users\merte\Desktop\cleaned_segments"

# Create the output folder before processing so each segment can be saved there.
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

MIN_DURATION_SEC = 60.0

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

# Process each EDF file and its corresponding annotation CSV to remove bad segments
for file_path in edf_files:
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    annotation_file = os.path.join(
        annotations_dir,
        f"{file_name}_annotations.csv",
    )

    # Skip recordings that do not have a matching annotation CSV.
    if not os.path.exists(annotation_file):
        continue

    print(f"\nProcessing: {file_name}")

    # Read the bad-segment onset and duration values from the annotation CSV.
    annotation_df = pd.read_csv(annotation_file)

    # Preloading makes the EEG data available for filtering and channel removal.
    raw = mne.io.read_raw_edf(file_path, preload=True, verbose=False)
    # Get the total duration of the recording in seconds for later use.
    total_duration = raw.times[-1]

    # Remove the Status channel when it is present in the recording.
    if 'Status' in raw.ch_names:
        raw.drop_channels(['Status'])
        print("  -> Dropped 'Status' channel.")

    # Apply the same 0.5 to 40 Hz band-pass filter to each recording.
    raw.filter(l_freq=0.5, h_freq=40.0, fir_design='firwin', verbose=False)
    print("  -> Applied 0.5 - 40 Hz band-pass filter.")

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

            duration = float(row['duration'])
            bad_segments.append((onset, duration))
        bad_segments.sort(key=lambda segment: segment[0])

    # Save only clean intervals that meet the minimum required duration.
    current_time = 0.0
    segment_counter = 1
    segment_saved = False

    for onset, duration in bad_segments:
        # The interval before this bad segment is clean when its onset is after
        # the end of the previously processed bad segment.
        if onset > current_time:
            clean_duration = onset - current_time

            if clean_duration >= MIN_DURATION_SEC:
                clean_chunk = raw.copy().crop(tmin=current_time, tmax=onset)
                output_file = os.path.join(
                    output_dir,
                    f"{file_name}_seg-{segment_counter:02d}.fif",
                )
                clean_chunk.save(output_file, overwrite=True, verbose=False)
                segment_saved = True
                print(
                    f"  -> Saved segment {segment_counter:02d} "
                    f"({clean_duration:.1f}s) to: {output_file}"
                    )
                segment_counter += 1

        # Move the start of the next clean interval to the end of this bad
        # segment, while keeping the furthest end when bad segments overlap.
        current_time = max(current_time, onset + duration)

    # Check the clean interval after the final bad segment separately.
    if current_time < total_duration:
        clean_duration = total_duration - current_time

        if clean_duration >= MIN_DURATION_SEC:
            clean_chunk = raw.copy().crop(tmin=current_time, tmax=total_duration)
            output_file = os.path.join(
                output_dir,
                f"{file_name}_seg-{segment_counter:02d}.fif",
            )
            clean_chunk.save(output_file, overwrite=True, verbose=False)
            segment_saved = True
            print(
                f"  -> Saved segment {segment_counter:02d} "
                f"({clean_duration:.1f}s) to: {output_file}"
            )

    if not segment_saved:
        print("  -> No clean segments found. No files saved.")