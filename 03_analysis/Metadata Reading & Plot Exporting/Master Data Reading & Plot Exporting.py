import mne
import pandas as pd
import os
import glob
import warnings
import plotly.graph_objects as go 

warnings.filterwarnings('ignore')

# ==============================================================================
# 1. DIRECTORY CONFIGURATIONS & PARAMETERS
# ==============================================================================
BASE_DIR_CHBMP = r"E:\project-healthyageing\02_data\00_download\chbmp"
BASE_DIR_DORT = r"E:\project-healthyageing\02_data\00_download\ds005385-1.0.2"
BASE_DIR_MPI = r"E:\project-healthyageing\02_data\00_download\mpilmbb\preprocessed"

DEMO_CHBMP = r"E:\project-healthyageing\02_data\00_download\chbmp\chbmp_Demographic_data.csv"
DEMO_DORT = r"E:\project-healthyageing\02_data\00_download\ds005385-1.0.2\ds005385_participants.tsv"
DEMO_MPI = r"E:\project-healthyageing\02_data\00_download\mpilmbb\META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv"

OUTPUT_FILE = "Master_Metadata_Summary.xlsx"

PLOT_MODE = 'save' 
PLOT_OUTPUT_DIR = "QC_Plots_CHBMP"

if PLOT_MODE == 'save' and not os.path.exists(PLOT_OUTPUT_DIR):
    os.makedirs(PLOT_OUTPUT_DIR)

master_metadata = []

SEPARATOR_ROW = {
    "Database_Name": "---", "Subject_ID": "", "Gender": "", "Age": "", 
    "Segment_ID": "", "Condition": "", "Onset_sec": "", "Duration_sec": "", 
    "Total_Channels": "", "Sampling_Rate": "", "BandPass_Filter": "", "Discontinuity_Status": ""
}

# ==============================================================================
# 2. LOAD DEMOGRAPHICS DATA
# ==============================================================================
demo_dict = {'chbmp': {}, 'dortmund': {}, 'mpi': {}}

print("Loading demographic databases...")

if os.path.exists(DEMO_CHBMP):
    try:
        df_chbmp = pd.read_csv(DEMO_CHBMP, skiprows=1).dropna(axis=1, how='all')
        df_chbmp.columns = [str(c).lower().strip() for c in df_chbmp.columns]
        for _, row in df_chbmp.iterrows():
            raw_id = str(row.get('code', '')).strip().lower()
            if raw_id and raw_id != 'nan':
                demo_dict['chbmp'][raw_id.replace('sub-', '')] = {
                    'age': str(row.get('age', 'N/A')).strip(),
                    'gender': str(row.get('gender', 'N/A')).strip()
                }
    except Exception as e:
        print(f"Error loading CHBMP demo: {e}")

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

if os.path.exists(DEMO_MPI):
    try:
        df_mpi = pd.read_csv(DEMO_MPI)
        id_col = next((c for c in df_mpi.columns if 'id' in str(c).lower() or 'sub' in str(c).lower()), 'ID')
        for _, row in df_mpi.iterrows():
            raw_id = str(row.get(id_col, '')).strip().lower()
            if raw_id and raw_id != 'nan':
                gender_raw = row.get('Gender_ 1=female_2=male', None)
                gender_val = 'F' if gender_raw in [1, 1.0, '1', '1.0'] else ('M' if gender_raw in [2, 2.0, '2', '2.0'] else 'N/A')
                demo_dict['mpi'][raw_id.replace('sub-', '')] = {
                    'age': str(row.get('Age', 'N/A')).strip(),
                    'gender': gender_val
                }
    except Exception as e:
        print(f"Error loading MPI demo: {e}")

def get_bandpass_str(info):
    hp, lp = info.get('highpass', 'N/A'), info.get('lowpass', 'N/A')
    return f"{hp} - {lp} Hz" if hp != 'N/A' and lp != 'N/A' else "N/A"

# ==============================================================================
# 3. PROCESSING CHBMP (CUBAN) DATASET
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
            bad_segments = []
            
            current_ec_start = None
            current_disc_start = None
            t_end_limit = None
            
            for _, row in events_df.iterrows():
                tt = str(row.get('trial_type', '')).lower().strip()
                onset = float(row.get('onset', 0))

                if tt in ['eyes closed', 'ojos cerrados']:
                    if current_disc_start is not None:
                        bad_segments.append({'onset': current_disc_start, 'duration': onset - current_disc_start})
                        current_disc_start = None
                    current_ec_start = onset
                
                elif tt == 'discontinuity':
                    if current_ec_start is not None:
                        segments.append({'onset': current_ec_start, 'duration': onset - current_ec_start, 'status': 'Clean'})
                        current_ec_start = None
                    if current_disc_start is None:
                        current_disc_start = onset
                        
                elif tt in ['eyes opened', 'ojos abiertos']:
                    if current_ec_start is not None:
                        segments.append({'onset': current_ec_start, 'duration': onset - current_ec_start, 'status': 'Clean'})
                        current_ec_start = None
                    if current_disc_start is not None:
                        bad_segments.append({'onset': current_disc_start, 'duration': onset - current_disc_start})
                        current_disc_start = None
                    t_end_limit = onset
                    break 

            if not segments:
                continue
            
            should_preload = bool(PLOT_MODE)
            raw = mne.io.read_raw_edf(edf_file, preload=should_preload, verbose=False)
            
            if os.path.exists(channels_file):
                ch_df = pd.read_csv(channels_file, sep='\t')
                emap = {k: v for k, v in zip(raw.ch_names, ch_df.iloc[:, 0].astype(str).tolist())}
                mne.rename_channels(raw.info, emap, allow_duplicates=False, verbose=False)
            
            if PLOT_MODE:
                ch_names = [ch for ch in raw.ch_names if ch.upper() in ['O1', 'O2']]
                if ch_names:
                    t_start = segments[0]['onset']
                    t_end = t_end_limit if t_end_limit is not None else (segments[-1]['onset'] + segments[-1]['duration'])
                    
                    if t_end_limit is None and bad_segments:
                        t_end = max(t_end, bad_segments[-1]['onset'] + bad_segments[-1]['duration'])
                        
                    sfreq = raw.info['sfreq']
                    idx_start = int(t_start * sfreq)
                    idx_end = min(int(t_end * sfreq), raw.n_times)
                    
                    data = raw.get_data(picks=ch_names, start=idx_start, stop=idx_end)
                    times = raw.times[idx_start:idx_end]

                    fig = go.Figure()
                    colors = ['black', 'blue']
                    
                    for idx, ch_name in enumerate(ch_names):
                        fig.add_trace(go.Scatter(
                            x=times, y=data[idx], mode='lines', name=ch_name,
                            line=dict(color=colors[idx % len(colors)], width=1), opacity=0.8
                        ))

                    for seg in segments:
                        fig.add_vrect(x0=seg['onset'], x1=seg['onset'] + seg['duration'], fillcolor="gray", opacity=0.2, layer="below", line_width=0)
                        
                    for bseg in bad_segments:
                        if bseg['duration'] > 0:
                            fig.add_vrect(x0=bseg['onset'], x1=bseg['onset'] + bseg['duration'], fillcolor="red", opacity=0.3, layer="below", line_width=0)
                        else:
                            fig.add_vline(x=bseg['onset'], line_width=2, line_dash="dash", line_color="red")

                    fig.update_layout(
                        title=f"Eyes Closed EEG Traces: {file_name.split('_')[0]}",
                        xaxis_title="Time [s]", yaxis_title="Amplitude",
                        xaxis=dict(range=[t_start, t_end]),
                        template="plotly_white", hovermode="x unified"
                    )
                    
                    if PLOT_MODE == 'save':
                        fig.write_html(os.path.join(PLOT_OUTPUT_DIR, f"{file_name.split('_')[0]}_QC.html"), auto_open=False)
                    elif PLOT_MODE == 'show':
                        fig.show()
                else:
                    print(f" [!] Plotting skipped for {file_name}: O1/O2 channels not found.")

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
# 4. PROCESSING DORTMUND (DS005385) DATASET
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
# 5. PROCESSING LEIPZIG (MPI / LEMON) DATASET
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
# 6. EXPORTING MASTER EXCEL FILE
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
        return ['background-color: #0070C0; color: #0070C0'] * len(row) if row['Database_Name'] == '---' else [''] * len(row)
    
    try:
        styled_df = df.style.apply(highlight_separator, axis=1)
        styled_df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print("\n" + "="*60)
        print(f"SUCCESS! Master Metadata extracted to: {os.path.abspath(OUTPUT_FILE)}")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\nStyling export failed. Saving raw format: {e}")
        df.to_excel(OUTPUT_FILE, index=False)
else:
    print("\nNo metadata could be extracted. Please check the paths.")