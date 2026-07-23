import mne
import pandas as pd
import os
import glob
import warnings
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

OUTPUT_FILE = "Master_Metadata_Summary.xlsx"

PLOT_MODE = 'save' 
PLOT_OUTPUT_DIR = "QC_Plots_CHBMP"

if PLOT_MODE == 'save' and not os.path.exists(PLOT_OUTPUT_DIR):
    os.makedirs(PLOT_OUTPUT_DIR)

master_metadata = []

SEPARATOR_ROW = {
    "Database_Name": "---", "Subject_ID": "", "Gender": "", "Age": "", 
    "Segment_ID": "", "Condition": "", "Onset_sec": "", "Duration_sec": "", 
    "Total_Channels": "", "Sampling_Rate": "", "BandPass_Filter": "", 
    "Channel_Names": "", "Discontinuity_Status": ""
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
                print(f" [!] Demographics not found for CHBMP ID: {clean_id}")
                demo = {'age': 'N/A', 'gender': 'N/A'}

            try:
                events_df = pd.read_csv(tsv_file, sep='\t')
                segments = []
                ec_active = False
                start_time = 0.0
                has_disc = "No"
                bad_segments_for_plot = [] 
                
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
                        if duration > 0:
                            bad_segments_for_plot.append({'onset': onset, 'duration': duration})
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
                        elif PLOT_MODE == 'show':
                            fig.show()
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
                        "Channel_Names": ch_names_str,
                        "Discontinuity_Status": seg['status']
                    })
                    
                count_chbmp += 1
                action_text = "and saved interactive plot" if PLOT_MODE == 'save' else ""
                print(f"Processed CHBMP: {display_id} | Extracted {len(segments)} segment(s) {action_text}.")
            except Exception as e:
                print(f"Error processing CHBMP {display_id}: {e}")

        if count_chbmp > 0:
            master_metadata.append(SEPARATOR_ROW)

# ==============================================================================
# 4. PROCESSING DATABASE 2: DORTMUND (DS005385)
# ==============================================================================
print("\n--- Processing Dortmund (ds005385) Database ---")
if os.path.exists(BASE_DIR_DORT):
    dort_files = sorted(glob.glob(os.path.join(BASE_DIR_DORT, "**", "*EyesClosed*.edf"), recursive=True))
    count_dort = 0
    dort_seg_counter = {}

    for file_path in dort_files:
        if count_dort >= 10:
            break
            
        file_name = os.path.basename(file_path)
        raw_sub_id = file_name.split('_')[0]
        sub_id = raw_sub_id.lower()
        if not sub_id.startswith('sub-'):
            sub_id = f"sub-{sub_id}"
            
        demo = demo_dict['dortmund'].get(sub_id)
        if not demo:
            print(f" [!] Demographics not found for Dortmund ID: {sub_id}")
            demo = {'age': 'N/A', 'gender': 'N/A'}

        try:
            raw = mne.io.read_raw_edf(file_path, preload=False, verbose=False)
            duration_sec = raw.n_times / raw.info['sfreq'] if raw.info['sfreq'] else 0
            
            ch_names_str = f"[{', '.join(raw.ch_names)}]"

            dort_seg_counter[raw_sub_id] = dort_seg_counter.get(raw_sub_id, 0) + 1
            current_seg_id = f"seg_{dort_seg_counter[raw_sub_id]:02d}"

            master_metadata.append({
                "Database_Name": "Dortmund", "Subject_ID": raw_sub_id,
                "Gender": demo['gender'], "Age": demo['age'],
                "Segment_ID": current_seg_id, "Condition": "eyes closed",
                "Onset_sec": 0.0, "Duration_sec": round(duration_sec, 2),
                "Total_Channels": len(raw.ch_names), 
                "Sampling_Rate": raw.info['sfreq'],
                "BandPass_Filter": get_bandpass_str(raw.info), 
                "Channel_Names": ch_names_str,
                "Discontinuity_Status": "Clean" 
            })
            count_dort += 1
            print(f"Processed Dortmund: {file_name} | Extracted {current_seg_id}")
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
            print(f" [!] Demographics not found for Leipzig ID: {clean_id}")
            demo = {'age': 'N/A', 'gender': 'N/A'}

        try:
            raw = mne.io.read_raw_eeglab(file_path, preload=False, verbose=False)
            sfreq = raw.info['sfreq']
            total_duration_sec = raw.n_times / sfreq if sfreq else 0
            
            ch_names_str = f"[{', '.join(raw.ch_names)}]"

            # -------------------------------------------------------------
            # BOUNDARY (KESİNTİ) KONTROLÜ - Çalışan MNE Olay (Event) Mantığı
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
                pass 

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

            # Toplanan segmentleri status ekleyerek master metadata'ya yaz
            for i, seg in enumerate(segments_list):
                if len(segments_list) == 1:
                    status = "Clean"
                elif len(segments_list) == 2:
                    status = "Before_Gap" if i == 0 else "After_Gap"
                else:
                    if i == 0: status = "Before_Gap"
                    elif i == len(segments_list) - 1: status = "After_Gap"
                    else: status = "Between_Gaps"

                master_metadata.append({
                    "Database_Name": "MPILMBB", "Subject_ID": subject_id,
                    "Gender": demo['gender'], "Age": demo['age'],
                    "Segment_ID": f"seg_{i+1:02d}", "Condition": "EC",
                    "Onset_sec": round(seg['onset'], 2), "Duration_sec": round(seg['duration'], 2),
                    "Total_Channels": len(raw.ch_names), 
                    "Sampling_Rate": sfreq,
                    "BandPass_Filter": get_bandpass_str(raw.info), 
                    "Channel_Names": ch_names_str,
                    "Discontinuity_Status": status
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

    # Channel_Names Discontinuity_Status'un hemen öncesinde (sağdan 2.)
    columns_order = [
        "Database_Name", "Subject_ID", "Gender", "Age", "Segment_ID",
        "Condition", "Onset_sec", "Duration_sec", "Total_Channels",
        "Sampling_Rate", "BandPass_Filter", "Channel_Names", "Discontinuity_Status"
    ]
    df = df[columns_order]
        
    try:
        def highlight_separator(row):
            return ['background-color: #0070C0; color: #0070C0'] * len(row) if row['Database_Name'] == '---' else [''] * len(row)
        
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