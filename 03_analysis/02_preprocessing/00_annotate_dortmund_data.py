import mne
import pandas as pd
import os
import glob
import warnings
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

from src.config import DIR_DATA, BASE_DIR_CHBMP, BASE_DIR_DORT, BASE_DIR_MPI
## Define the output directory for the csv files with annotations
output_dir = os.path.join(DIR_DATA.joinpath('01_prepdata').joinpath('00_dortmund_annotations_artifacts'))
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

#please script:
## 1. read in one Dortmund (ds005385) file after another

#BASE_DIR_DORT = r"D:\project-healthyageing\02_data\00_download\ds005385-1.0.2"
search_pattern = os.path.join(BASE_DIR_DORT, "sub-*", "**", "eeg", "*task-EyesClosed*.edf")
edf_files = sorted(glob.glob(search_pattern, recursive=True))
print(f"\nFound {len(edf_files)} EDF files.")

"""for file_path in edf_files:
    raw = mne.io.read_raw_edf(file_path, preload=True)
    ## 2. plot it with matplotlib qt as an interactive window
    raw.plot()"""

raw = mne.io.read_raw_edf(edf_files[0], preload=True)
raw.plot()

## 3. Fred + Gesine will annotate the data in the interactive window

## 4. save the annotations in a .csv file

## open next file and repeat the process until all files are annotated