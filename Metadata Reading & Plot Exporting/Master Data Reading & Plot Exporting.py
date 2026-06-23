import mne
import pandas as pd
import os
import glob
import warnings
import plotly.graph_objects as go  # Matplotlib yerine Plotly kullanıyoruz

# Hide MNE and Pandas warnings to keep the terminal clean
warnings.filterwarnings('ignore')

# ==============================================================================
# 1. DIRECTORY CONFIGURATIONS & OUTPUT FILE
# ==============================================================================
BASE_DIR_CHBMP = r"D:\project-healthyageing\02_data\00_download\chbmp"
BASE_DIR_DORT = r"D:\project-healthyageing\02_data\00_download\ds005385-1.0.2"
BASE_DIR_MPI = r"D:\project-healthyageing\02_data\00_download\mpilmbb\preprocessed"

# Updated Demographic File Paths
DEMO_CHBMP = r"D:\project-healthyageing\02_data\00_download\chbmp\chbmp_Demographic_data.csv"
DEMO_DORT = r"D:\project-healthyageing\02_data\00_download\ds005385-1.0.2\ds005385_participants.tsv"
DEMO_MPI = r"D:\project-healthyageing\02_data\00_download\mpilmbb\META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv"

OUTPUT_FILE = "Master_Metadata_Summary.xlsx"

# ==============================================================================
# PLOTTING CONFIGURATION
# ==============================================================================
# Options: 
# 'show' -> Opens interactive graphs in browser immediately (halts script)
# 'save' -> Saves interactive HTML files in the background without halting
# None   -> Disables plotting completely (fastest)
PLOT_MODE = 'save' 

PLOT_OUTPUT_DIR = "QC_Plots_CHBMP"
if PLOT_MODE == 'save' and not os.path.exists(PLOT_OUTPUT_DIR):
    os.makedirs(PLOT_OUTPUT_DIR)

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
        df_chbmp = df_chbmp.dropna(axis=1, how='all')
        df_chbmp.columns = [str(c).lower().strip() for c in df_chbmp.columns]
        
        for _, row in df_chbmp.iterrows():
            raw_id = str(row.get('code', '')).strip().lower()
            if not raw_id or raw_id == 'nan':
                continue
            clean_id = raw_id.replace('sub-', '')
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
# 3. PROCESSING DATABASE 1: CUBAN (CHBMP) WITH INTERACTIVE PLOTTING
# ==============================================================================
print("\n--- Processing CHBMP (Cuban) Database ---")
if os.path.exists(BASE_DIR_CHBMP):
    chbmp_edf_files = sorted(glob.glob(os.path.join(BASE_DIR_CHBMP, "**", "*_eeg.edf"), recursive=True))
    count_chbmp = 0

    for edf_file in chbmp_edf_files:
        if count_chbmp >= 10:  
            break

        file_name = os.path.basename(edf_file)
        
        tsv_file = edf_file.replace("_eeg.edf", "_events.tsv")
        channels_file = edf_file.replace("_eeg.edf", "_channels.tsv")

        if not os.path.exists(tsv_file):
            continue
        
        clean_id = file_name.split('_')[0].lower().replace('sub-', '').strip()
        demo = demo_dict['chbmp'].get(clean_id)
        
        if not demo:
            print(f" [!] Demographics not found for CHBMP ID: {clean_id}")
            demo = {'age': 'N/A', 'gender': 'N/A'}

        try:
            events_df = pd.read_csv(tsv_file, sep='\t')
            segments = []
            discontinuities = [] 
            
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
                    discontinuities.append(onset) 
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
            
            should_preload = bool(PLOT_MODE)
            raw = mne.io.read_raw_edf(edf_file, preload=should_preload, verbose=False)
            
            # --- CHANNEL RENAMING LOGIC ---
            if os.path.exists(channels_file):
                ch_df = pd.read_csv(channels_file, sep='\t')
                chans = ch_df.iloc[:, 0].astype(str).tolist()
                
                emap = {k: v for k, v in zip(raw.ch_names, chans)}
                mne.rename_channels(raw.info, emap, allow_duplicates=False, verbose=False)
            
            # --- PLOTLY INTERACTIVE HTML EXPORT ---
            if PLOT_MODE:
                ch_names = [ch for ch in raw.ch_names if ch.upper() in ['O1', 'O2']]
                if len(ch_names) > 0:
                    t_start = segments[0]['onset']
                    t_end = segments[-1]['onset'] + segments[-1]['duration']
                    
                    sfreq = raw.info['sfreq']
                    idx_start = int(t_start * sfreq)
                    idx_end = min(int(t_end * sfreq), raw.n_times)
                    
                    data = raw.get_data(picks=ch_names, start=idx_start, stop=idx_end)
                    times = raw.times[idx_start:idx_end]

                    # Create Plotly Figure
                    fig = go.Figure()
                    colors = ['black', 'blue']
                    
                    # Add EEG lines
                    for idx, ch_name in enumerate(ch_names):
                        fig.add_trace(go.Scatter(
                            x=times, y=data[idx],
                            mode='lines',
                            name=ch_name,
                            line=dict(color=colors[idx % len(colors)], width=1),
                            opacity=0.8
                        ))

                    # Add Discontinuities (Red Dashed Lines)
                    for idx, t_disc in enumerate(discontinuities):
                        if t_start <= t_disc <= t_end:
                            fig.add_vline(x=t_disc, line_width=2, line_dash="dash", line_color="red",
                                          annotation_text="Discontinuity" if idx==0 else "", annotation_position="top right")
                    
                    # Add Valid Segments (Gray Shaded Areas)
                    for idx, seg in enumerate(segments):
                        t_on = seg['onset']
                        t_off = seg['onset'] + seg['duration']
                        fig.add_vrect(x0=t_on, x1=t_off, fillcolor="gray", opacity=0.2, layer="below", line_width=0,
                                      annotation_text="Valid Segment" if idx==0 else "")

                    # Layout Formatting
                    fig.update_layout(
                        title=f"Interactive Eyes Closed EEG Traces: {file_name.split('_')[0]}",
                        xaxis_title="Time [s]",
                        yaxis_title="Amplitude",
                        xaxis=dict(range=[t_start, t_end]),
                        template="plotly_white",
                        hovermode="x unified" # Shows values for both O1 and O2 simultaneously on hover
                    )
                    
                    if PLOT_MODE == 'save':
                        save_path = os.path.join(PLOT_OUTPUT_DIR, f"{file_name.split('_')[0]}_QC.html")
                        fig.write_html(save_path, auto_open=False) # Saves as standalone HTML file
                    elif PLOT_MODE == 'show':
                        fig.show() # Opens in browser immediately
                else:
                    print(f" [!] Plotting skipped for {file_name}: O1/O2 channels not found.")
            # ----------------------------------

            for i, seg in enumerate(segments):
                master_metadata.append({
                    "Database_Name": "CHBMP", "Subject_ID": file_name.split('_')[0],
                    "Gender": demo['gender'], "Age": demo['age'],
                    "Segment_ID": f"seg_{i+1:02d}", "Condition": "eyes closed",
                    "Onset_sec": round(seg['onset'], 2), "Duration_sec": round(seg['duration'], 2),
                    "Total_Channels": len(raw.ch_names), "Sampling_Rate": raw.info['sfreq'],
                    "BandPass_Filter": get_bandpass_str(raw.info), "Discontinuity_Status": seg['status']
                })
                
            count_chbmp += 1
            action_text = "and saved interactive plot" if PLOT_MODE == 'save' else ""
            print(f"Processed CHBMP: {file_name.split('_')[0]} | Extracted {len(segments)} segment(s) {action_text}.")
        except Exception as e:
            print(f"Error processing CHBMP {file_name}: {e}")

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
        if count_dort >= 10:
            break
            
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
        if count_mpi >= 10:
            break
            
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
    
    def highlight_separator(row):
        if row['Database_Name'] == '---':
            return ['background-color: #0070C0; color: #0070C0'] * len(row)
        return [''] * len(row)
    
    try:
        styled_df = df.style.apply(highlight_separator, axis=1)
        styled_df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print("\n" + "="*60)
        print(f"SUCCESS! Master Metadata extracted to:")
        print(f"{os.path.abspath(OUTPUT_FILE)}")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\nStyling export failed. Saving raw format: {e}")
        df.to_excel(OUTPUT_FILE, index=False)
else:
    print("\nNo metadata could be extracted. Please check the paths.")