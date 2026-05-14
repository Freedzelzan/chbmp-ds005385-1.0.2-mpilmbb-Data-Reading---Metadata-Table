import mne
import pandas as pd
import os
import glob

# 1. File Paths and Output Configuration
BASE_DIR = r"D:\project-healthyageing\02_data\00_rawdata\ds005385_rs_ec"
OUTPUT_FILE = "EEG_Metadata_Summary_First10.xlsx"

# 2. Subject List and Metadata Collection
subject_list = [f"sub-{str(i).zfill(3)}" for i in range(1, 11)]
metadata_list = []

print(f"Starting metadata extraction for {len(subject_list)} subjects...")

for sub in subject_list:
    sub_path = os.path.join(BASE_DIR, sub)
    
    if not os.path.exists(sub_path):
        print(f"Skipping {sub}: Directory not found.")
        continue

    # Search for EDF files matching the 'EyesClosed' task pattern within the subject's directory
    search_pattern = os.path.join(sub_path, "**", "eeg", "*task-EyesClosed*.edf")
    edf_files = glob.glob(search_pattern, recursive=True)

    for file_path in edf_files:
        try:
            file_name = os.path.basename(file_path)
            
            # Reading the EDF file with MNE to extract metadata without loading the entire data into memory
            print(f"Processing: {file_name}")
            raw = mne.io.read_raw_edf(file_path, preload=False, verbose=False)
            info = raw.info
            
            # --- 1. Technical Details ---
            sfreq = info['sfreq'] # Sampling frequency
            n_channels = len(raw.ch_names) # Number of channels
            
            # --- 2. DEMOGRAPHIC DATA (from subject_info) ---
            subject_info = info.get('subject_info', {}) # Safely get 'subject_info' or default to an empty dictionary if it's missing
            
            # Sex Details (0: Unknown, 1: Male, 2: Female)
            sex_code = subject_info.get('sex', 0)
            sex_map = {0: "0", 1: "1", 2: "2"}
            sex_str = sex_map.get(sex_code, "0")
            
            # Calculating the Age 
            age = "N/A"
            birthday = subject_info.get('birthday', None)
            meas_date = info.get('meas_date', None)
            
            if birthday is not None and meas_date is not None:
                # MNE stores birthday as a tuple (year, month, day) or as a string 'YYYY-MM-DD'
                birth_year = birthday[0] if isinstance(birthday, tuple) else int(str(birthday).split('-')[0])
                meas_year = meas_date.year
                age = meas_year - birth_year
            
            # Adding the collected metadata to the list
            metadata_list.append({
                "Subject_ID": sub,
                "File_Name": file_name,
                "Sex": sex_str,
                "Age": age,
                "Electrode_Set_Channels": n_channels,
                "Sampling_Freq_Hz": sfreq
            })
            
            # --- 3. Stop Condition (Inner Loop) ---
            # Stop the extraction loop once we have exactly 10 successful records
            if len(metadata_list) == 10:
                print("\nSuccessfully processed 10 files. Stopping file extraction.")
                break
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # --- 3. Stop Condition (Outer Loop) ---
    # Stop the subject search once we have collected metadata from 10 files
    if len(metadata_list) == 10:
        print("Stopping subject search.")
        break

# 4. Exporting the collected metadata to an Excel file
if metadata_list:
    df = pd.DataFrame(metadata_list)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSuccess! Clean metadata exported to: {os.path.abspath(OUTPUT_FILE)}")
else:
    print("\nNo matching files found.")