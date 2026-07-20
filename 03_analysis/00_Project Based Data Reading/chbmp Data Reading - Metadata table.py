import mne
import pandas as pd
import os

# 1. File Paths and Output Configuration
BASE_DIR = r"D:\project-healthyageing\02_data\00_download\chbmp\rs"
PARTICIPANTS_FILE = r"D:\project-healthyageing\02_data\00_download\chbmp\chbmp_Demographic_data.csv"
OUTPUT_FILE = "CHBMP_Metadata_Summary_Complete.xlsx"

# 2. Load Global Demographic Data
demographics = {}
if os.path.exists(PARTICIPANTS_FILE):
    print("Loading demographic data...")
    try:
        # Skip the first useless header row (skiprows=1)
        df_parts = pd.read_csv(PARTICIPANTS_FILE, skiprows=1)
        df_parts = df_parts.dropna(axis=1, how='all')
            
        # Normalize column names to lowercase and strip spaces (e.g., 'Code' -> 'code')
        df_parts.columns = [str(c).lower().strip() for c in df_parts.columns]
        
        # Extract direct column values
        for _, row in df_parts.iterrows():
            # Get the 'code' column (e.g., cbm00001)
            raw_id = str(row.get('code', '')).strip().lower()
            
            if not raw_id or raw_id == 'nan':
                continue
                
            # Clean 'sub-' prefix to ensure pure ID matching
            clean_id = raw_id.replace('sub-', '') if raw_id.startswith('sub-') else raw_id
            
            # Fetch relevant data directly
            demographics[clean_id] = {
                'age': row.get('age', 'N/A'),
                'gender': row.get('gender', 'N/A')
            }
        print(f"Successfully cached metadata for {len(demographics)} participants.")
    except Exception as e:
        print(f"Warning: Failed to parse CSV file: {e}")
else:
    print("WARNING: Demographic CSV file not found!")

# 3. Find and Process FIF Files
fif_files = sorted([f for f in os.listdir(BASE_DIR) if f.endswith('.fif')])
metadata_list = []

print(f"\nProcessing FIF files...")

for file_name in fif_files:
    try:
        file_path = os.path.join(BASE_DIR, file_name)
        
        # Extract full subject ID from filename (e.g., 'sub-cbm00001')
        full_sub_id = file_name.split('_')[0].lower()
        
        # Clean 'sub-' prefix from the filename ID for exact CSV matching (e.g., 'cbm00001')
        match_id = full_sub_id.replace('sub-', '')
        
        print(f"Processing: {file_name}")
        
        # Read the FIF file headers
        raw = mne.io.read_raw_fif(file_path, preload=False, verbose=False)
        info = raw.info
        
        # Fetch matching Demographic Data, default to 'N/A' if missing
        sub_demo = demographics.get(match_id, {'age': 'N/A', 'gender': 'N/A'})
        
        # Technical Details & Channel Processing
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
        
        # Append target metadata columns
        metadata_list.append({
            "Subject_ID": full_sub_id, 
            "File_Name": file_name,
            "Gender": sub_demo['gender'],
            "Age": sub_demo['age'],
            "Electrode_Set_Channels": n_channels,
            "Channel_Names": ch_names_str,
            "Sampling_Freq_Hz": sfreq,
            "Total_Samples": n_samples,
            "File_Length_sec": round(length_sec, 2) if isinstance(length_sec, float) else length_sec,
            "Highpass_Hz": highpass,
            "Lowpass_Hz": lowpass
        })

        # --- Stop Condition ---
        #if len(metadata_list) == 10:
        #    print("\nSuccessfully processed 10 files. Stopping extraction.")
        #    break

    except Exception as e:
        print(f"Error processing {file_name}: {e}")

# 4. Export to Excel
if metadata_list:
    df = pd.DataFrame(metadata_list)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSuccess! Clean metadata exported to: {os.path.abspath(OUTPUT_FILE)}")
else:
    print("\nNo metadata could be extracted. Please check the paths.")