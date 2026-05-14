import mne
import pandas as pd
import os

# 1. File Paths and Output Configuration
BASE_DIR = r"D:\project-healthyageing\02_data\00_rawdata\chbmp_rs_ec"
OUTPUT_FILE = "CHBMP_Metadata_Summary_First10.xlsx"

# 2. Find All FIF Files Directly in the folder
# Scans the directory and creates a list of all files ending with '.fif'
fif_files = [f for f in os.listdir(BASE_DIR) if f.endswith('.fif')]

metadata_list = []

print(f"Found {len(fif_files)} FIF files. Starting metadata extraction...")

for file_name in fif_files:
    try:
        file_path = os.path.join(BASE_DIR, file_name)
        
        # Extract Subject ID from the filename (e.g., 'sub-CBM00167_seg_00_raw.fif' -> 'sub-CBM00167')
        sub_id = file_name.split('_')[0] if "sub-" in file_name else "Unknown"
        
        print(f"Processing: {file_name}")
        
        # Read the FIF file metadata without loading the heavy signal data into RAM
        raw = mne.io.read_raw_fif(file_path, preload=False, verbose=False)
        info = raw.info
        
        # --- 1. Technical Details ---
        sfreq = info['sfreq']
        n_channels = len(raw.ch_names)
        
        # --- 2. Demographic Data (with Safety Net) ---
        subject_info = info.get('subject_info')
        
        # CRITICAL FIX: If 'subject_info' is entirely missing (None), fallback to an empty dictionary
        # This prevents the "'NoneType' object has no attribute 'get'" error.
        if subject_info is None:
            subject_info = {}
            
        # Extract Sex Details (0: Unknown, 1: Male, 2: Female)
        sex_code = subject_info.get('sex', 0)
        sex_str = str(sex_code)
        
        # Calculate Age based on measurement date and birthday
        age = "N/A"
        birthday = subject_info.get('birthday', None)
        meas_date = info.get('meas_date', None)
        
        if birthday is not None and meas_date is not None:
            # MNE stores birthday as a tuple (year, month, day) or as a string 'YYYY-MM-DD'
            birth_year = birthday[0] if isinstance(birthday, tuple) else int(str(birthday).split('-')[0])
            meas_year = meas_date.year
            age = meas_year - birth_year
        
        # Append the successfully extracted metadata to our list
        metadata_list.append({
            "Subject_ID": sub_id,
            "File_Name": file_name,
            "Sex": sex_str,
            "Age": age,
            "Electrode_Set_Channels": n_channels,
            "Sampling_Freq_Hz": sfreq
        })
        
        # --- 3. Stop Condition ---
        # Stop the extraction loop once we have exactly 10 successful records
        #if len(metadata_list) == 10:
        #    print("\nSuccessfully processed 10 files. Stopping extraction.")
         #   break
            
    except Exception as e:
        print(f"Error processing {file_name}: {e}")

# 4. Exporting Data to Excel
if metadata_list:
    df = pd.DataFrame(metadata_list)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSuccess! Clean metadata exported to: {os.path.abspath(OUTPUT_FILE)}")
else:
    print("\nNo metadata could be extracted. Please check the files and directory path.")