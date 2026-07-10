import mne
import pandas as pd
import os

# 1. File Paths and Output Configuration
BASE_DIR = r"D:\project-healthyageing\02_data\00_download\chbmp\rs"
PARTICIPANTS_FILE = r"D:\project-healthyageing\02_data\00_download\chbmp\participants.tsv"
OUTPUT_FILE = "CHBMP_Metadata_Summary_Complete_First10.xlsx"

# 2. Load Global Demographic and Clinical Data from participants.tsv
demographics = {}

if os.path.exists(PARTICIPANTS_FILE):
    print("Loading demographic and clinical data from participants.tsv...")
    try:
        df_parts = pd.read_csv(PARTICIPANTS_FILE, sep='\t')
        # Normalize column names to lowercase for safe and flexible matching
        df_parts.columns = [str(c).lower() for c in df_parts.columns]
        
        for _, row in df_parts.iterrows():
            p_id = str(row['participant_id']).strip() if 'participant_id' in df_parts.columns else ""
            if p_id:
                # Ensure the subject ID consistency (matches 'sub-CBMXXXXX' format)
                if not p_id.startswith('sub-'):
                    p_id = f"sub-{p_id}"
                
                # Cache all available clinical metrics mentioned by Gesine
                demographics[p_id.lower()] = {
                    'age': row.get('age', 'N/A'),
                    'sex': row.get('sex', 'N/A'),
                    'mmse': row.get('mmse', 'N/A'),
                    'wais_iii': row.get('wais_iii', row.get('wais', 'N/A'))
                }
        print(f"Successfully cached metadata for {len(demographics)} participants.")
    except Exception as e:
        print(f"Warning: Failed to parse participants.tsv: {e}")
else:
    print("WARNING: participants.tsv not found! Demographic columns will default to N/A.")

# 3. Find All FIF Files Directly in the folder
# Wrapped the list comprehension in sorted() to guarantee alphabetical processing
fif_files = sorted([f for f in os.listdir(BASE_DIR) if f.endswith('.fif')])
metadata_list = []

print(f"\nFound {len(fif_files)} FIF files. Starting metadata extraction for the first 10...")

for file_name in fif_files:
    try:
        file_path = os.path.join(BASE_DIR, file_name)
        
        # Extract Subject ID from the filename (e.g., 'sub-CBM00167_seg_00_raw.fif' -> 'sub-CBM00167')
        sub_id = file_name.split('_')[0] if "sub-" in file_name else "Unknown"
        
        print(f"Processing: {file_name}")
        
        # Read the FIF file metadata without loading the heavy signal data into RAM
        raw = mne.io.read_raw_fif(file_path, preload=False, verbose=False)
        info = raw.info
        
        # --- Technical Details ---
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
        
        # --- Match Demographic and Clinical Data from Cache ---
        sub_demo = demographics.get(sub_id.lower(), {'age': 'N/A', 'sex': 'N/A', 'mmse': 'N/A', 'wais_iii': 'N/A'})
        
        # Append the successfully extracted metadata to our list
        metadata_list.append({
            "Subject_ID": sub_id,
            "File_Name": file_name,
            "Sex": sub_demo['sex'],
            "Age": sub_demo['age'],
            "MMSE": sub_demo['mmse'],
            "WAIS_III": sub_demo['wais_iii'],
            "Electrode_Set_Channels": n_channels,
            "Channel_Names": ch_names_str,
            "Sampling_Freq_Hz": sfreq,
            "Total_Samples": n_samples,
            "File_Length_sec": round(length_sec, 2) if isinstance(length_sec, float) else length_sec,
            "Highpass_Hz": highpass,
            "Lowpass_Hz": lowpass
        })
        
        # --- 3. Stop Condition ---
        # Stop the extraction loop once we have exactly 10 successful records
        if len(metadata_list) == 10:
            print("\nSuccessfully processed 10 files. Stopping extraction.")
            break
            
    except Exception as e:
        print(f"Error processing {file_name}: {e}")

# 4. Exporting Data to Excel
if metadata_list:
    df = pd.DataFrame(metadata_list)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSuccess! Complete metadata exported to: {os.path.abspath(OUTPUT_FILE)}")
else:
    print("\nNo metadata could be extracted. Please check the files and directory path.")