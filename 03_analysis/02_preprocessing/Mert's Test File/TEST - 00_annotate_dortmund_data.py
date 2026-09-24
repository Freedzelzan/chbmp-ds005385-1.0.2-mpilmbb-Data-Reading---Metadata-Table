import mne
import pandas as pd
import os
import glob
import re
import warnings
import matplotlib

# Changed from the previous default backend so the script behaves like the
# notebook's `%matplotlib qt` cell and opens interactive Qt windows.
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt

# Suppress warning messages so the interactive annotation
warnings.filterwarnings('ignore')

from src.config import DIR_DATA, BASE_DIR_CHBMP, BASE_DIR_DORT, BASE_DIR_MPI
# These paths come from the project's shared configuration.
# BASE_DIR_DORT is the downloaded Dortmund dataset, while DIR_DATA is the
# project's general data directory.
# Local test setting: this test file reads the Dortmund data from the E: drive.
# This overrides the imported project default only for this local test script.
BASE_DIR_DORT = r"E:\project-healthyageing\02_data\00_download\ds005385-1.0.2"
## Define the output directory for the csv files with annotations
# Save test results on the current user's Desktop instead of the project data
# folder, making the generated annotation CSV files easy to find locally.
output_dir = os.path.join(
    os.path.expanduser("~"),
    "Desktop",
    "00_dortmund_annotations_artifacts",
)
# Build the folder where annotation CSV files are intended
# to be written. Creating it now means later save operations can use it safely.
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

#please script:
## 1. read in one Dortmund (ds005385) file after another

#BASE_DIR_DORT = r"D:\project-healthyageing\02_data\00_download\ds005385-1.0.2"
# The pattern looks below every subject folder for EEG EDF
# files whose task name is EyesClosed. The recursive search also handles any
# additional directory level between the subject and the EEG folder.
search_pattern = os.path.join(BASE_DIR_DORT, "sub-*", "**", "eeg", "*task-EyesClosed*.edf")
edf_files = sorted(glob.glob(search_pattern, recursive=True))
# Sorting makes the processing order deterministic, so the
# first file selected below is predictable between runs.
print(f"\nFound {len(edf_files)} EDF files.")

# Ask where the previous annotation session ended so the script can resume
# with the next subject instead of opening all recordings from the beginning.
while True:
    try:
        last_checked_subject = int(
            input("What is the subject number of the last file you checked? ")
        )
        if last_checked_subject < 0:
            raise ValueError
        break
    except ValueError:
        print("Please enter a non-negative whole number.")


def get_subject_number(file_path):
    match = re.search(r"[\\/]sub-(\d+)(?:[\\/]|$)", file_path)
    return int(match.group(1)) if match else None


# Keep only subjects after the number entered above. For example, entering 39
# starts the workflow at sub-040, including all matching sessions/acquisitions.
edf_files = [
    file_path
    for file_path in edf_files
    if (subject_number := get_subject_number(file_path)) is not None
    and subject_number > last_checked_subject
]
selected_subjects = sorted(
    {get_subject_number(file_path) for file_path in edf_files}
)
print(f"Starting with subjects after sub-{last_checked_subject:03d}: ")
print(", ".join(f"sub-{subject:03d}" for subject in selected_subjects))

# Stop with a useful message instead of failing later at edf_files[0] when the
# data folder is missing or contains no matching EyesClosed recordings.
if not edf_files:
    raise FileNotFoundError(
        f"No EyesClosed EDF files were found below: {BASE_DIR_DORT}"
    )

# The following code block is commented out because it was the original version 
# that only opened the first EDF file. The new version below it loops through all
# found files, allowing for annotation of each one in turn.
"""for file_path in edf_files:
    raw = mne.io.read_raw_edf(file_path, preload=True)
    ## 2. plot it with matplotlib qt as an interactive window
    raw.plot()"""

# Changed from opening only edf_files[0]: Gesine's notes require
# every recording to be handled, one after another.
for file_path in edf_files:
    print(f"\nOpening: {file_path}")

    # preload=True loads the signal into memory, which allows MNE to display
    # and interact with the data in the annotation window.
    raw = mne.io.read_raw_edf(file_path, preload=True)

    # block=True keeps this file's window open until the annotator closes it.
    # Only then does the loop continue and open the next EEG file.
    raw.plot(block=True)

    # Save the annotations made in the closed plot using the EDF filename, so
    # every recording gets its own unambiguous CSV output file.
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    annotation_file = os.path.join(output_dir, f"{file_name}_annotations.csv")
    # MNE's to_data_frame() does not accept index=False; that option belongs to
    # pandas' to_csv() method below.
    raw.annotations.to_data_frame().to_csv(annotation_file, index=False)
    print(f"Annotations saved to: {annotation_file}")

## 3. Fred + Gesine will annotate the data in the interactive window

## 4. save the annotations in a .csv file

## open next file and repeat the process until all files are annotated
# These final steps are currently instructions only; the
# script does not yet save annotations or loop through the remaining files.