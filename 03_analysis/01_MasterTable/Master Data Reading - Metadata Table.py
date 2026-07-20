import mne
import pandas as pd
import os
import glob
import warnings

# hiding MNE and Pandas warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# 1. DIRECTORY CONFIGURATIONS & OUTPUT FILE
# ==============================================================================
from src.config import BASE_DIR_CHBMP, BASE_DIR_DORT, BASE_DIR_MPI, DEMO_CHBMP, DEMO_DORT, DEMO_MPI, DIR_RESULTS

OUTPUT_FILE = DIR_RESULTS / "Master_Metadata_Summary.xlsx"
master_metadata = []

# Empty row template for the blue separator
SEPARATOR_ROW = {
    "Database_Name": "---", "Subject_ID": "", "Gender": "", "Age": "", 
    "Segment_ID": "", "Condition": "", "Onset_sec": "", "Duration_sec": "", 
    "Total_Channels": "", "Sampling_Rate": "", "BandPass_Filter": "", "Discontinuity_Status": ""
}

# ==============================================================================
# 2. DEMOGRAPHICS LOADING (Strict Matching Logic)
# ==============================================================================
demo_dict = {'chbmp': {}, 'dortmund': {}, 'mpi': {}}

print("Loading demographic databases...")

# --- A. CHBMP Demographics ---
if os.path.exists(DEMO_CHBMP):
    try:
        df_chbmp = pd.read_csv(DEMO_CHBMP, skiprows=1)
        df_chbmp = df_chbmp.dropna(axis=1, how='all') #drop columns with NaN values
        df_chbmp.columns = [str(c).lower().strip() for c in df_chbmp.columns]
        
        for _, row in df_chbmp.iterrows():
            raw_id = str(row.get('code', '')).strip().lower()
            if not raw_id or raw_id == 'nan':
                continue
            # If the ID doesn't start with 'sub-', we will add it for consistency (e.g., sub-001)
            clean_id = raw_id.replace('sub-', '') ### what further information does this add? (Gesine)
            # It removes the 'sub-' prefix to ensure the ID exactly matches the keys used later when reading the data folders. (Mert)
            demo_dict['chbmp'][clean_id] = {
                'age': str(row.get('age', 'N/A')).strip(),
                'gender': str(row.get('gender', 'N/A')).strip()
            }
    except Exception as e:
        print(f"Error loading CHBMP demo: {e}")

# --- B. DORTMUND Demographics ---
if os.path.exists(DEMO_DORT):
    try:
        df_dort = pd.read_csv(DEMO_DORT, sep='\t')
        df_dort.columns = [str(c).lower() for c in df_dort.columns]
        
        for _, row in df_dort.iterrows():
            p_id = str(row.get('participant_id', '')).strip().lower()
            if p_id and p_id != 'nan':
                # Subject IDs in Dortmund are expected to be in the format 'sub-XXX', but we will ensure it for matching
                if not p_id.startswith('sub-'):
                    p_id = f"sub-{p_id}"
                demo_dict['dortmund'][p_id] = {
                    'age': str(row.get('age', 'N/A')).strip(),
                    'gender': str(row.get('sex', 'N/A')).strip()
                }
    except Exception as e:
        print(f"Error loading Dortmund demo: {e}")

# --- C. MPI (LEMON) Demographics ---
if os.path.exists(DEMO_MPI):
    try:
        df_mpi = pd.read_csv(DEMO_MPI)
        id_col = next((c for c in df_mpi.columns if 'id' in str(c).lower() or 'sub' in str(c).lower()), 'ID')
        
        for _, row in df_mpi.iterrows():
            raw_id = str(row.get(id_col, '')).strip().lower()
            if raw_id and raw_id != 'nan':
                # For MPI, we will store IDs without 'sub-' prefix for easier matching (e.g., 001, 002)
                clean_id = raw_id.replace('sub-', '')


                gender_raw = row.get('Gender_ 1=female_2=male', None)
                gender_val = "N/A"
                if gender_raw in [1, 1.0, '1', '1.0']: gender_val = 'F'
                elif gender_raw in [2, 2.0, '2', '2.0']: gender_val = 'M'
                
                demo_dict['mpi'][clean_id] = {
                    'age': str(row.get('Age', 'N/A')).strip(),
                    'gender': gender_val
                }
    except Exception as e:
        print(f"Error loading MPI demo: {e}")

def get_bandpass_str(info):
    hp = info.get('highpass', 'N/A')
    lp = info.get('lowpass', 'N/A')
    if hp != 'N/A' and lp != 'N/A':
        return f"{hp} - {lp} Hz"
    return "N/A"

# ==============================================================================
# 3. PROCESSING DATABASE 1: CUBAN (CHBMP)
# ==============================================================================
print("\n--- Processing CHBMP (Cuban) Database ---")
if os.path.exists(BASE_DIR_CHBMP):
    chbmp_raw_dir = os.path.join(BASE_DIR_CHBMP, "raw")
    if os.path.exists(chbmp_raw_dir):
        chbmp_subjects = sorted([d for d in os.listdir(chbmp_raw_dir) if os.path.isdir(os.path.join(chbmp_raw_dir, d))])
        count_chbmp = 0

        for sub_folder in chbmp_subjects:
            #if count_chbmp >= 10:
            #    break

            folder_path = os.path.join(chbmp_raw_dir, sub_folder)
            edf_files = glob.glob(os.path.join(folder_path, "*.edf"))
            tsv_files = glob.glob(os.path.join(folder_path, "*events.tsv"))

            if not edf_files or not tsv_files:
                continue

            edf_file = edf_files[0]
            tsv_file = tsv_files[0]
            clean_id = sub_folder.split('_')[0].lower().replace('sub-', '').strip()
            demo = demo_dict['chbmp'].get(clean_id)
            
            if not demo:
                print(f" [!] Demographics not found for CHBMP ID: {clean_id}")
                demo = {'age': 'N/A', 'gender': 'N/A'}

            try:
                events_df = pd.read_csv(tsv_file, sep='\t')
                segments = []
                ec_active = False
                start_time = 0.0
                has_disc = "No"
                
                for _, row in events_df.iterrows():
                    tt = str(row.get('trial_type', '')).lower().strip()
                    onset = float(row.get('onset', 0))
                    duration = float(row.get('duration', 0))

                    if tt in ['eyes closed', 'ojos cerrados'] and not ec_active:
                        ec_active = True
                        start_time = onset
                    
                    elif 'discontinuity' in tt and ec_active:
                        has_disc = "Yes"
                        segments.append({
                            'onset': start_time,
                            'duration': onset - start_time,
                            'status': 'Before_Gap' if len(segments) == 0 else 'Between_Gaps'
                        })
                        start_time = onset + duration 
                        
                    elif ('opened' in tt or 'abiertos' in tt):
                        if ec_active:
                            segments.append({
                                'onset': start_time,
                                'duration': onset - start_time,
                                'status': 'After_Gap' if has_disc == "Yes" else 'Clean'
                            })
                            break 

                if not segments:
                    continue

                raw = mne.io.read_raw_edf(edf_file, preload=False, verbose=False)
                
                for i, seg in enumerate(segments):
                    master_metadata.append({
                        "Database_Name": "CHBMP", "Subject_ID": sub_folder,
                        "Gender": demo['gender'], "Age": demo['age'],
                        "Segment_ID": f"seg_{i+1:02d}", "Condition": "eyes closed",
                        "Onset_sec": round(seg['onset'], 2), "Duration_sec": round(seg['duration'], 2),
                        "Total_Channels": len(raw.ch_names), "Sampling_Rate": raw.info['sfreq'],
                        "BandPass_Filter": get_bandpass_str(raw.info), "Discontinuity_Status": seg['status']
                    })
                    
                count_chbmp += 1
                print(f"Processed CHBMP: {sub_folder} | Extracted {len(segments)} segment(s).")
            except Exception as e:
                print(f"Error processing CHBMP {sub_folder}: {e}")

        if count_chbmp > 0:
            master_metadata.append(SEPARATOR_ROW)

# ==============================================================================
# 4. PROCESSING DATABASE 2: DORTMUND (ds005385)
# ==============================================================================
print("\n--- Processing Dortmund (ds005385) Database ---")
if os.path.exists(BASE_DIR_DORT):
    dort_files = sorted(glob.glob(os.path.join(BASE_DIR_DORT, "**", "*EyesClosed*.edf"), recursive=True))
    count_dort = 0

    for file_path in dort_files:
        #if count_dort >= 10:
        #    break
            
        file_name = os.path.basename(file_path)
        sub_id = file_name.split('_')[0].lower()
        if not sub_id.startswith('sub-'):
            sub_id = f"sub-{sub_id}"
            
        demo = demo_dict['dortmund'].get(sub_id)
        if not demo:
            print(f" [!] Demographics not found for Dortmund ID: {sub_id}")
            demo = {'age': 'N/A', 'gender': 'N/A'}

        try:
            raw = mne.io.read_raw_edf(file_path, preload=False, verbose=False)
            duration_sec = raw.n_times / raw.info['sfreq'] if raw.info['sfreq'] else 0

            master_metadata.append({
                "Database_Name": "Dortmund", "Subject_ID": file_name.split('_')[0],
                "Gender": demo['gender'], "Age": demo['age'],
                "Segment_ID": "seg_01", "Condition": "eyes closed",
                "Onset_sec": 0.0, "Duration_sec": round(duration_sec, 2),
                "Total_Channels": len(raw.ch_names), "Sampling_Rate": raw.info['sfreq'],
                "BandPass_Filter": get_bandpass_str(raw.info), "Discontinuity_Status": "Clean" 
            })
            count_dort += 1
            print(f"Processed Dortmund: {file_name}")
        except Exception as e:
            print(f"Error processing Dortmund {file_name}: {e}")

    if count_dort > 0:
        master_metadata.append(SEPARATOR_ROW)

# ==============================================================================
# 5. PROCESSING DATABASE 3: LEIPZIG (MPILMBB / LEMON)
# ==============================================================================
print("\n--- Processing Leipzig (MPILMBB) Database ---")
if os.path.exists(BASE_DIR_MPI):
    mpi_files = sorted(glob.glob(os.path.join(BASE_DIR_MPI, "**", "*_EC.set"), recursive=True))
    count_mpi = 0

    for file_path in mpi_files:
        #if count_mpi >= 10:
        #    break
            
        file_name = os.path.basename(file_path)
        clean_id = file_name.split('_')[0].lower().replace('sub-', '').strip()
        
        demo = demo_dict['mpi'].get(clean_id)
        if not demo:
            print(f" [!] Demographics not found for Leipzig ID: {clean_id}")
            demo = {'age': 'N/A', 'gender': 'N/A'}

        try:
            raw = mne.io.read_raw_eeglab(file_path, preload=False, verbose=False)
            duration_sec = raw.n_times / raw.info['sfreq'] if raw.info['sfreq'] else 0

            master_metadata.append({
                "Database_Name": "MPILMBB", "Subject_ID": file_name.split('_')[0],
                "Gender": demo['gender'], "Age": demo['age'],
                "Segment_ID": "seg_01", "Condition": "EC",
                "Onset_sec": 0.0, "Duration_sec": round(duration_sec, 2),
                "Total_Channels": len(raw.ch_names), "Sampling_Rate": raw.info['sfreq'],
                "BandPass_Filter": get_bandpass_str(raw.info), "Discontinuity_Status": "Clean" 
            })
            count_mpi += 1
            print(f"Processed Leipzig: {file_name}")
        except Exception as e:
            print(f"Error processing Leipzig {file_name}: {e}")

# ==============================================================================
# 6. EXPORTING MASTER EXCEL FILE WITH STYLING
# ==============================================================================
if master_metadata:
    df = pd.DataFrame(master_metadata)
    
    columns_order = [
        "Database_Name", "Subject_ID", "Gender", "Age", "Segment_ID", 
        "Condition", "Onset_sec", "Duration_sec", "Total_Channels", 
        "Sampling_Rate", "BandPass_Filter", "Discontinuity_Status"
    ]
    df = df[columns_order]
    
    try:
        pd.DataFrame.to_csv(df, sep=',', index=False, path_or_buf=OUTPUT_FILE.with_suffix('.csv'))
        print(f"\nRaw CSV exported to: {OUTPUT_FILE.with_suffix('.csv')}")
    except Exception as e:
        print(f"Error exporting CSV: {e}")
else:
    print("\nNo metadata could be extracted. Please check the paths.")
