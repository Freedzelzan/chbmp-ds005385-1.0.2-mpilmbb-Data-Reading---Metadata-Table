import mne
import pandas as pd
import os
import glob
import warnings

warnings.filterwarnings('ignore')

from src.config import DIR_DATA, BASE_DIR_CHBMP, BASE_DIR_DORT, BASE_DIR_MPI

#please script:
## 1. read in all EEG files from the three datasets (CHBMP, DORT, MPI)
## 2. unify to 30 channels, 1-30 Hz band pass filtering, and convert the EEG data format to a common format (e.g., MNE Raw object)
## 3. save the unified EEG data in a common format (e.g., .fif files) in a specified output directory


## Define the output directory for the unified EEG data
output_dir = os.path.join(DIR_DATA.joinpath('01_prepdata').joinpath('01_unified_eeg_data_1-30Hz_30ch_fif'))
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

## Read In EEG files from the three datasets
# Use MNE BIDS package!