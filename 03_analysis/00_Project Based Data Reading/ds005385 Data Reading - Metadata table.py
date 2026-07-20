import mne
import pandas as pd
import os
import glob

# 1. File Paths and Output Configuration
BASE_DIR = r"D:\project-healthyageing\02_data\00_download\ds005385-1.0.2"
OUTPUT_FILE = "ds005385_EDF_Metadata_Summary.xlsx"

# 2. Load Global Demographic Data from participants.tsv
participants_file = os.path.join(BASE_DIR, "ds005385_participants.tsv")
demographics = {}

if os.path.exists(participants_file):
    print("Loading demographic data from participants.tsv...")
    try:
        df_parts = pd.read_csv(participants_file, sep='\t')
        # Normalize column names to lowercase for safe matching
        df_parts.columns = [str(c).lower() for c in df_parts.columns]
        
        for _, row in df_parts.iterrows():
            p_id = str(row['participant_id']) if 'participant_id' in df_parts.columns else ""
            if p_id:
                # Ensure the ID format matches 'sub-XXX'
                if not p_id.startswith('sub-'):
                    p_id = f"sub-{p_id}"
                
                demographics[p_id] = {
                    'age': row.get('age', 'N/A'),
                    'sex': row.get('sex', 'N/A')
                }
        print(f"Successfully cached demographics for {len(demographics)} participants.")
    except Exception as e:
        print(f"Warning: Failed to parse participants.tsv: {e}")
else:
    print("WARNING: participants.tsv not found in BASE_DIR! Age and Sex will default to N/A.")

# 3. Find All EDF Files Directly (Replacing the hardcoded subject_list)
# Searches through all sub-folders and finds every matching EDF file, sorting them alphabetically.
search_pattern = os.path.join(BASE_DIR, "sub-*", "**", "eeg", "*task-EyesClosed*.edf")
edf_files = sorted(glob.glob(search_pattern, recursive=True))

metadata_list = []

print(f"\nFound {len(edf_files)} EDF files. Starting metadata extraction for the first 10...")

for file_path in edf_files:
    try:
        file_name = os.path.basename(file_path)
        
        # Extract Subject ID from the filename (e.g., 'sub-001')
        sub_id = file_name.split('_')[0] if "sub-" in file_name else "Unknown"
        
        # Session Tracking
        session = "ses-1" if "ses-1" in file_name else "ses-2" if "ses-2" in file_name else "Unknown"
        
        print(f"Processing: {file_name}")
        
        # Fetch demographic data from the global pre-loaded dictionary
        sub_demo = demographics.get(sub_id, {'age': 'N/A', 'sex': 'N/A'})
        age = sub_demo['age']
        sex = sub_demo['sex']
        
        # Read EDF technical details
        raw = mne.io.read_raw_edf(file_path, preload=False, verbose=False)
        info = raw.info
        
        sfreq = info['sfreq']
        
        # Channel Names & "Status" Exclusion
        ch_names = raw.ch_names
        if "Status" in ch_names:
            ch_names.remove("Status")
            
        n_channels = len(ch_names)
        ch_names_str = ", ".join(ch_names)
        
        # Band-pass Filter Settings
        highpass = info.get('highpass', 'N/A')
        lowpass = info.get('lowpass', 'N/A')
        
        # File Length & Samples
        n_samples = raw.n_times
        length_sec = n_samples / sfreq if sfreq else 'N/A'
        
        # Append collected metadata
        metadata_list.append({
            "Subject_ID": sub_id,
            "Session": session,
            "File_Name": file_name,
            "Sex": sex,
            "Age": age,
            "Electrode_Set_Channels": n_channels,
            "Channel_Names": ch_names_str,
            "Sampling_Freq_Hz": sfreq,
            "Total_Samples": n_samples,
            "File_Length_sec": round(length_sec, 2) if isinstance(length_sec, float) else length_sec,
            "Highpass_Hz": highpass,
            "Lowpass_Hz": lowpass
        })
        
        # --- 4. Single Stop Condition ---
        #if len(metadata_list) == 10:
        #    print("\nSuccessfully processed 10 files. Stopping extraction.")
        #    break
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

# 5. Export Data to Excel
if metadata_list:
    df = pd.DataFrame(metadata_list)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSuccess! Clean metadata exported to: {os.path.abspath(OUTPUT_FILE)}")
else:
    print("\nNo matching files found. Please verify directory paths and task patterns.")