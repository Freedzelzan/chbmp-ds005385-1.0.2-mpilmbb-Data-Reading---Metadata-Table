"""Preprocess Dortmund eyes-closed EEG recordings for microstate analysis.

Saves clean, annotated EDF intervals as FIF files.
"""

import mne
import os
import glob
import warnings

# Keep processing output focused on status messages.
warnings.filterwarnings('ignore')

from src.config import BASE_DIR_DORT, DIR_PREPDATA


# ---------------------------------------------------------------------------
# PARAMETERS
# ---------------------------------------------------------------------------

# Band-pass filter limits in Hz.
L_FREQ = 1.0
H_FREQ = 30.0

# Target sampling rate in Hz.
TARGET_SFREQ = 250.0

# Standard electrode layout.
MONTAGE_NAME = "standard_1005"


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

# Local data paths.
BASE_DIR_DORT = r"E:\project-healthyageing\02_data\00_download\ds005385-1.0.2"

# Include processing settings in the output folder name.
output_dir = DIR_PREPDATA / (
    f"02_microstate_prep_{L_FREQ:g}-{H_FREQ:g}Hz_"
    f"{TARGET_SFREQ:g}Hz_avgref_fif"
)
output_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# FIND THE RECORDINGS
# ---------------------------------------------------------------------------

# Find pre- and post-acquisition eyes-closed EDF recordings.
search_pattern = os.path.join(
    BASE_DIR_DORT,
    "sub-*",
    "**",
    "eeg",
    "*task-EyesClosed_acq-*_eeg.edf",
)
edf_files = sorted(glob.glob(search_pattern, recursive=True))

print(f"\nFound {len(edf_files)} EDF files.")

if not edf_files:
    raise FileNotFoundError(
        f"No EyesClosed EDF files were found below: {BASE_DIR_DORT}"
    )

saved_file_count = 0


# ---------------------------------------------------------------------------
# PROCESS EVERY RECORDING
# ---------------------------------------------------------------------------

for file_path in edf_files:
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    print(f"\nProcessing: {file_name}")

    # Load the raw EDF file.
    raw = mne.io.read_raw_edf(file_path, preload=True, verbose=False)

    # Remove the non-EEG trigger channel.
    if 'Status' in raw.ch_names:
        raw.drop_channels(['Status'])
        print("  -> Dropped 'Status' channel.")

    # Set electrode positions.
    raw.set_montage(MONTAGE_NAME, verbose=False)
    print(f"  -> Set montage '{MONTAGE_NAME}'.")

    # Filter the continuous recording before segmenting to avoid edge effects
    # at each clean interval.
    raw.filter(l_freq=L_FREQ, h_freq=H_FREQ, fir_design='firwin', verbose=False)
    print(f"  -> Applied {L_FREQ:g} - {H_FREQ:g} Hz band-pass filter.")

    # Resample after filtering.
    original_sfreq = raw.info['sfreq']
    raw.resample(TARGET_SFREQ, verbose=False)
    print(f"  -> Resampled from {original_sfreq:g} Hz to {TARGET_SFREQ:g} Hz.")

    # Apply the common average reference.
    raw.set_eeg_reference('average', verbose=False)
    print("  -> Applied common average reference.")

    # Save the preprocessed recording.
    output_file = os.path.join(output_dir, f"{file_name}.fif")
    raw.save(output_file, overwrite=True, verbose=False)
    print(f"  -> Saved to: {output_file}")
    saved_file_count += 1

print(f"\nSaved files: {saved_file_count}")
print(f"Output folder: {output_dir}")
