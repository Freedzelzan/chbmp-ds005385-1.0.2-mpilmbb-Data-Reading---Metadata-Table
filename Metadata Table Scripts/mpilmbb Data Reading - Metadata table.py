import mne
import pandas as pd
import os
import glob

# 1. File Paths and Output Configuration
BASE_DIR = r"D:\project-healthyageing\02_data\00_download\mpilmbb\preprocessed"
PARTICIPANTS_FILE = r"D:\project-healthyageing\02_data\00_download\mpilmbb\META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv"
OUTPUT_FILE = "MPILMBB_Metadata_Summary.xlsx"

# 2. Load Global Demographic Data Dynamically
demographics = {}
if os.path.exists(PARTICIPANTS_FILE):
    print("Loading demographic data...")
    try:
        # Read the CSV file
        df_parts = pd.read_csv(PARTICIPANTS_FILE)
        
        # Drop junk columns like 'Unnamed: 0' that often come from Excel/Pandas exports
        df_parts = df_parts.loc[:, ~df_parts.columns.str.contains('^unnamed', case=False)]
        
        # Dynamically find the ID column (usually 'ID' in this dataset)
        id_col = next((c for c in df_parts.columns if 'id' in str(c).lower() or 'sub' in str(c).lower()), None)
        
        if id_col:
            for _, row in df_parts.iterrows():
                raw_id = str(row.get(id_col, '')).strip().lower()
                
                if not raw_id or raw_id == 'nan':
                    continue
                    
                # Clean 'sub-' prefix to ensure pure ID matching
                clean_id = raw_id.replace('sub-', '') if raw_id.startswith('sub-') else raw_id
                
                # Fetch all columns for this participant EXCEPT the ID column itself
                row_dict = row.drop(labels=[id_col]).to_dict()
                demographics[clean_id] = row_dict
                
            print(f"Successfully cached metadata for {len(demographics)} participants.")
        else:
            print("Warning: Could not identify the ID column in the CSV.")
            
    except Exception as e:
        print(f"Warning: Failed to parse CSV file: {e}")
else:
    print("WARNING: Demographic CSV file not found at the specified path!")


# 3. Find and Process .set Files
search_pattern = os.path.join(BASE_DIR, "**", "*.set")
set_files = sorted(glob.glob(search_pattern, recursive=True))

metadata_list = []

print(f"\nFound {len(set_files)} .set files. Starting metadata extraction...")

for file_path in set_files:
    try:
        file_name = os.path.basename(file_path)
        
        # Extract full subject ID from filename (e.g., 'sub-010002')
        full_sub_id = file_name.split('_')[0].lower()
        
        # Clean 'sub-' prefix for exact CSV matching (e.g., '010002')
        match_id = full_sub_id.replace('sub-', '')
        
        print(f"Processing: {file_name}")
        
        # Read the .set file metadata using MNE
        raw = mne.io.read_raw_eeglab(file_path, preload=False, verbose=False)
        info = raw.info
        
        # Fetch matching Demographic Data (will return an empty dict if subject not found)
        sub_demo = demographics.get(match_id, {})
        
        # --- Technical Details ---
        sfreq = info['sfreq']
        ch_names = raw.ch_names.copy()
        
        if "Status" in ch_names: 
            ch_names.remove("Status")
            
        n_channels = len(ch_names)
        ch_names_str = ", ".join(ch_names)
        
        highpass = info.get('highpass', 'N/A')
        lowpass = info.get('lowpass', 'N/A')
        n_samples = raw.n_times
        length_sec = n_samples / sfreq if sfreq else 'N/A'
        
        # --- Combine Technical and Demographic Data ---
        # The **sub_demo syntax automatically unpacks ALL demographic columns into this dictionary
        combined_metadata = {
            "Subject_ID": file_name.split('_')[0], # Keep original casing (e.g., sub-010002)
            "File_Name": file_name,
            **sub_demo, # Injects Age, Gender, Education, Handedness, DRUG, etc. automatically
            "Electrode_Set_Channels": n_channels,
            "Channel_Names": ch_names_str,
            "Sampling_Freq_Hz": sfreq,
            "Total_Samples": n_samples,
            "File_Length_sec": round(length_sec, 2) if isinstance(length_sec, float) else length_sec,
            "Highpass_Hz": highpass,
            "Lowpass_Hz": lowpass
        }
        
        metadata_list.append(combined_metadata)
        
        # --- Single Stop Condition ---
        if len(metadata_list) == 10:
            print("\nSuccessfully processed 10 files. Stopping extraction.")
            break
            
    except Exception as e:
        print(f"Error processing {file_name}: {e}")

# 4. Exporting Data to Excel
if metadata_list:
    # Pandas will automatically create columns for all the dynamic keys we injected!
    df = pd.DataFrame(metadata_list)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSuccess! Clean metadata exported to: {os.path.abspath(OUTPUT_FILE)}")
else:
    print("\nNo metadata could be extracted. Please check the directory path.")