import mne
import pandas as pd
import os
import glob
import warnings
import numpy as np
import plotly.graph_objects as go 
from pathlib import Path

# hiding MNE and Pandas warnings
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

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = SCRIPT_DIR / "Master_Metadata_Summary.xlsx"

PLOT_MODE = 'save' 
PLOT_OUTPUT_DIR = SCRIPT_DIR / "QC_Plots_CHBMP"

if PLOT_MODE == 'save' and not os.path.exists(PLOT_OUTPUT_DIR):
    os.makedirs(PLOT_OUTPUT_DIR)

master_metadata = []

# Empty row template for the blue separator. 
# Discontinuity_Status removed as requested.
SEPARATOR_ROW = {
    "Database_Name": "---", "Subject_ID": "", "Gender": "", "Age": "", 
    "Segment_ID": "", "Condition": "", "Onset_sec": "", "Duration_sec": "", 
    "Total_Channels": "", "Sampling_Rate": "", "BandPass_Filter": "", 
    "Channel_Names": ""
}

# ==============================================================================
# 2. DEMOGRAPHICS LOADING
# ==============================================================================
demo_dict = {'chbmp': {}, 'dortmund': {}, 'mpi': {}}

print("Loading demographic databases...")

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


def should_keep_status_channel(raw, channel_name='Status'):
    """Return True when a Status channel carries any non-trivial information."""
    if channel_name not in raw.ch_names:
        return False

    try:
        status_idx = raw.ch_names.index(channel_name)
        sample_count = min(10000, raw.n_times)
        if sample_count <= 1:
            return False

        data = raw.get_data(picks=[status_idx], start=0, stop=sample_count)[0]
        finite_data = data[np.isfinite(data)]
        if finite_data.size == 0:
            return False

        unique_vals = np.unique(finite_data)
        return unique_vals.size > 1
    except Exception:
        return False

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
            if count_chbmp >= 10:
                break

            folder_path = os.path.join(chbmp_raw_dir, sub_folder)
            edf_files = glob.glob(os.path.join(folder_path, "*.edf"))
            tsv_files = glob.glob(os.path.join(folder_path, "*events.tsv"))

            if not edf_files or not tsv_files:
                continue

            edf_file = edf_files[0]
            tsv_file = tsv_files[0]
            
            display_id = sub_folder.split('_')[0].replace('sub-', '').strip()
            clean_id = display_id.lower() 
            
            demo = demo_dict['chbmp'].get(clean_id)
            
            if not demo:
                demo = {'age': 'N/A', 'gender': 'N/A'}

            try:
                events_df = pd.read_csv(tsv_file, sep='\t')
                segments = []
                ec_active = False
                start_time = 0.0
                bad_segments_for_plot = [] 
                
                for _, row in events_df.iterrows():
                    tt = str(row.get('trial_type', '')).lower().strip()
                    onset = float(row.get('onset', 0))
                    duration = float(row.get('duration', 0))

                    if tt in ['eyes closed', 'ojos cerrados'] and not ec_active:
                        ec_active = True
                        start_time = onset
                    
                    elif 'discontinuity' in tt and ec_active:
                        segments.append({
                            'onset': start_time,
                            'duration': onset - start_time
                        })
                        if duration > 0:
                            bad_segments_for_plot.append({'onset': onset, 'duration': duration})
                        start_time = onset + duration 
                        
                    elif ('opened' in tt or 'abiertos' in tt):
                        if ec_active:
                            segments.append({
                                'onset': start_time,
                                'duration': onset - start_time
                            })
                            break 

                if not segments:
                    continue

                should_preload = bool(PLOT_MODE)
                raw = mne.io.read_raw_edf(edf_file, preload=should_preload, verbose=False)
                
                channels_files = glob.glob(os.path.join(folder_path, "*channels.tsv"))
                if channels_files:
                    ch_df = pd.read_csv(channels_files[0], sep='\t')
                    emap = {k: v for k, v in zip(raw.ch_names, ch_df.iloc[:, 0].astype(str).tolist())}
                    mne.rename_channels(raw.info, emap, allow_duplicates=False, verbose=False)

                ch_names_str = f"[{', '.join(raw.ch_names)}]"

                if PLOT_MODE:
                    ch_names = [ch for ch in raw.ch_names if ch.upper() in ['O1', 'O2']]
                    if ch_names:
                        t_start = segments[0]['onset']
                        t_end = segments[-1]['onset'] + segments[-1]['duration']
                        
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
                            
                        for bseg in bad_segments_for_plot:
                            if bseg['duration'] > 0:
                                fig.add_vrect(x0=bseg['onset'], x1=bseg['onset'] + bseg['duration'], fillcolor="red", opacity=0.3, layer="below", line_width=0)
                            else:
                                fig.add_vline(x=bseg['onset'], line_width=2, line_dash="dash", line_color="red")

                        fig.update_layout(
                            title=f"Eyes Closed EEG Traces: {display_id}",
                            xaxis_title="Time [s]", yaxis_title="Amplitude",
                            xaxis=dict(range=[t_start, t_end]),
                            template="plotly_white", hovermode="x unified"
                        )
                        
                        if PLOT_MODE == 'save':
                            fig.write_html(os.path.join(PLOT_OUTPUT_DIR, f"{display_id}_QC.html"), auto_open=False)
                    else:
                        print(f" [!] Plotting skipped for {display_id}: O1/O2 channels not found.")
                
                for i, seg in enumerate(segments):
                    master_metadata.append({
                        "Database_Name": "CHBMP", "Subject_ID": display_id, 
                        "Gender": demo['gender'], "Age": demo['age'],
                        "Segment_ID": f"seg_{i+1:02d}", "Condition": "eyes closed",
                        "Onset_sec": round(seg['onset'], 2), "Duration_sec": round(seg['duration'], 2),
                        "Total_Channels": len(raw.ch_names), "Sampling_Rate": raw.info['sfreq'],
                        "BandPass_Filter": get_bandpass_str(raw.info), 
                        "Channel_Names": ch_names_str
                    })
                    
                count_chbmp += 1
                print(f"Processed CHBMP: {display_id} | Extracted {len(segments)} segment(s).")
            except Exception as e:
                print(f"Error processing CHBMP {display_id}: {e}")

        if count_chbmp > 0:
            master_metadata.append(SEPARATOR_ROW)

# ==============================================================================
# 4. PROCESSING DATABASE 2: DORTMUND (DS005385)
# ==============================================================================
print("\n--- Processing Dortmund (ds005385) Database ---")
if os.path.exists(BASE_DIR_DORT):
    # Only process "acq-pre" files
    dort_files = sorted(glob.glob(os.path.join(BASE_DIR_DORT, "**", "*task-EyesClosed_acq-pre_eeg.edf"), recursive=True))
    count_dort = 0

    for file_path in dort_files:
        if count_dort >= 10:
            break
            
        file_name = os.path.basename(file_path)
        
        # Parse Subject ID and Session
        # Example filename: sub-001_ses-1_task-EyesClosed_acq-pre_eeg.edf
        parts = file_name.split('_')
        raw_sub_id = parts[0]
        session_id = parts[1] if len(parts) > 1 and parts[1].startswith('ses-') else 'ses-1'
        
        sub_id_lookup = raw_sub_id.lower()
        if not sub_id_lookup.startswith('sub-'):
            sub_id_lookup = f"sub-{sub_id_lookup}"
            
        demo = demo_dict['dortmund'].get(sub_id_lookup)
        if not demo:
            demo = {'age': 'N/A', 'gender': 'N/A'}
            
        # Format Subject ID as requested: Sub-001.Ses-001.Pre
        sub_num = raw_sub_id.replace('sub-', '')
        ses_num = session_id.replace('ses-', '').zfill(3)
        formatted_id = f"Sub-{sub_num}.Ses-{ses_num}.Pre"

        try:
            # Read EEG Data
            raw = mne.io.read_raw_edf(file_path, preload=False, verbose=False)
            sfreq = raw.info['sfreq']
            total_duration_sec = raw.n_times / sfreq if sfreq else 0
            
            # Keep the Status channel only if it carries non-trivial information.
            ch_names_clean = raw.ch_names.copy()
            if "Status" in ch_names_clean and not should_keep_status_channel(raw, "Status"):
                ch_names_clean.remove("Status")
                
            total_channels = len(ch_names_clean)
            ch_names_str = f"[{', '.join(ch_names_clean)}]"

            # Check for Discontinuities
            segments_list = []
            
            # 1. First, check MNE annotations
            boundary_times = []
            try:
                events, event_id = mne.events_from_annotations(raw, verbose=False)
                boundary_keys = [key for key in event_id.keys() if 'boundary' in key.lower() or 'bad' in key.lower() or 'discontinuity' in key.lower()]
                
                for b_key in boundary_keys:
                    b_id = event_id[b_key]
                    b_events = events[events[:, 2] == b_id]
                    for ev in b_events:
                        time_sec = ev[0] / sfreq
                        boundary_times.append(time_sec)
            except Exception:
                pass 
            
            # 2. Also check external TSV file if annotations were empty
            if not boundary_times:
                tsv_file = file_path.replace("_eeg.edf", "_events.tsv")
                if os.path.exists(tsv_file):
                    try:
                        events_df = pd.read_csv(tsv_file, sep='\t')
                        for _, row in events_df.iterrows():
                            tt = str(row.get('type', row.get('trial_type', ''))).lower()
                            if 'boundary' in tt or 'discontinuity' in tt:
                                boundary_times.append(float(row.get('onset', 0)))
                    except Exception:
                        pass
            
            boundary_times.sort()

            # Split into segments
            if not boundary_times:
                segments_list.append({"onset": 0.0, "duration": total_duration_sec})
            else:
                current_onset = 0.0
                for b_time in boundary_times:
                    seg_duration = b_time - current_onset
                    if seg_duration > 0:
                        segments_list.append({"onset": current_onset, "duration": seg_duration})
                    current_onset = b_time
                
                if total_duration_sec - current_onset > 0:
                    segments_list.append({"onset": current_onset, "duration": total_duration_sec - current_onset})

            # Append to master table
            for i, seg in enumerate(segments_list):
                master_metadata.append({
                    "Database_Name": "Dortmund", "Subject_ID": formatted_id,
                    "Gender": demo['gender'], "Age": demo['age'],
                    "Segment_ID": f"seg_{i+1:02d}", "Condition": "eyes closed",
                    "Onset_sec": round(seg['onset'], 2), "Duration_sec": round(seg['duration'], 2),
                    "Total_Channels": total_channels, 
                    "Sampling_Rate": sfreq,
                    "BandPass_Filter": get_bandpass_str(raw.info), 
                    "Channel_Names": ch_names_str
                })

            count_dort += 1
            print(f"Processed Dortmund: {file_name} | Extracted {len(segments_list)} segment(s)")
        except Exception as e:
            print(f"Error processing Dortmund {file_name}: {e}")

    if count_dort > 0:
        master_metadata.append(SEPARATOR_ROW)

# ==============================================================================
# 5. PROCESSING DATABASE 3: LEIPZIG (MPI / LEMON)
# ==============================================================================
print("\n--- Processing Leipzig (MPILMBB) Database ---")
if os.path.exists(BASE_DIR_MPI):
    mpi_files = sorted(glob.glob(os.path.join(BASE_DIR_MPI, "**", "*_EC.set"), recursive=True))
    count_mpi = 0

    for file_path in mpi_files:
        if count_mpi >= 10:
            break
            
        file_name = os.path.basename(file_path)
        subject_id = file_name.split('_')[0]
        clean_id = subject_id.lower().replace('sub-', '').strip()
        
        demo = demo_dict['mpi'].get(clean_id)
        if not demo:
            demo = {'age': 'N/A', 'gender': 'N/A'}

        try:
            raw = mne.io.read_raw_eeglab(file_path, preload=False, verbose=False)
            sfreq = raw.info['sfreq']
            total_duration_sec = raw.n_times / sfreq if sfreq else 0
            
            ch_names_str = f"[{', '.join(raw.ch_names)}]"

            # -------------------------------------------------------------
            # BOUNDARY (KESİNTİ) KONTROLÜ
            # -------------------------------------------------------------
            boundary_times = []
            try:
                events, event_id = mne.events_from_annotations(raw, verbose=False)
                # 'boundary' içeren etiketleri filtrele
                boundary_keys = [key for key in event_id.keys() if 'boundary' in key.lower()]
                
                for b_key in boundary_keys:
                    b_id = event_id[b_key]
                    b_events = events[events[:, 2] == b_id]
                    for ev in b_events:
                        time_sec = ev[0] / sfreq
                        boundary_times.append(time_sec)
            except Exception:
                pass # Eğer anotasyon yoksa hata vermeden geç

            # Zaman damgalarını küçükten büyüğe sırala
            boundary_times.sort()
            
            segments_list = []

            # Eğer hiç kesinti (boundary) yoksa, tüm dosyayı tek parça olarak ekle
            if not boundary_times:
                segments_list.append({
                    "onset": 0.0, 
                    "duration": total_duration_sec
                })
            else:
                current_onset = 0.0
                for b_time in boundary_times:
                    seg_duration = b_time - current_onset
                    
                    # 0 saniyelik sahte segmentleri önlemek için kontrol
                    if seg_duration > 0:
                        segments_list.append({
                            "onset": current_onset, 
                            "duration": seg_duration
                        })
                    current_onset = b_time
                
                # Son kesinti noktasından dosyanın sonuna kadar olan kısmı ekle
                if total_duration_sec - current_onset > 0:
                    segments_list.append({
                        "onset": current_onset, 
                        "duration": total_duration_sec - current_onset
                    })

            for i, seg in enumerate(segments_list):
                master_metadata.append({
                    "Database_Name": "MPILMBB", "Subject_ID": subject_id,
                    "Gender": demo['gender'], "Age": demo['age'],
                    "Segment_ID": f"seg_{i+1:02d}", "Condition": "EC",
                    "Onset_sec": round(seg['onset'], 2), "Duration_sec": round(seg['duration'], 2),
                    "Total_Channels": len(raw.ch_names), 
                    "Sampling_Rate": sfreq,
                    "BandPass_Filter": get_bandpass_str(raw.info), 
                    "Channel_Names": ch_names_str
                })

            count_mpi += 1
            print(f"Processed Leipzig: {file_name} | Extracted {len(segments_list)} segment(s)")
            
        except Exception as e:
            print(f"Error processing Leipzig {file_name}: {e}")

# ==============================================================================
# 6. EXPORTING MASTER EXCEL FILE WITH STYLING
# ==============================================================================
if master_metadata:
    df = pd.DataFrame(master_metadata)

    # Discontinuity_Status removed from column order
    columns_order = [
        "Database_Name", "Subject_ID", "Gender", "Age", "Segment_ID",
        "Condition", "Onset_sec", "Duration_sec", "Total_Channels",
        "Sampling_Rate", "BandPass_Filter", "Channel_Names"
    ]
    df = df[columns_order]
        
    try:
        def highlight_separator(row):
            return ['background-color: #0070C0; color: #0070C0'] * len(row) if row['Database_Name'] == '---' else [''] * len(row)
        
        styled_df = df.style.apply(highlight_separator, axis=1)
        styled_df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print("\n" + "="*60)
        print(f"SUCCESS! Master Metadata extracted to: {OUTPUT_FILE}")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\nStyling export failed. Saving raw format: {e}")
        df.to_excel(OUTPUT_FILE, index=False)
else:
    print("\nNo metadata could be extracted. Please check the paths.")