import mne
import pandas as pd
import os
import glob

# 1. File Paths and Output Configuration
BASE_DIR = r"D:\project-healthyageing\02_data\00_download\mpilmbb\preprocessed"
OUTPUT_FILE = "MPILMBB_Metadata_Summary.xlsx"

# 2. Find All EEGLAB (.set) Files
# Search for .set files. MNE automatically pairs them with their corresponding .fdt files.
search_pattern = os.path.join(BASE_DIR, "**", "*.set")
set_files = sorted(glob.glob(search_pattern, recursive=True))

metadata_list = []

print(f"Found {len(set_files)} .set files. Starting metadata extraction...")

for file_path in set_files:
    try:
        file_name = os.path.basename(file_path)
        
        # Extract Subject ID from the filename (e.g., 'sub-010002_rest.set' -> 'sub-010002')
        sub_id = file_name.split('_')[0] if "sub-" in file_name else "Unknown"
        
        print(f"Processing: {file_name}")
        
        # Read the .set file metadata using MNE
        # preload=False ensures we only read the header, saving massive amounts of RAM and time.
        raw = mne.io.read_raw_eeglab(file_path, preload=False, verbose=False)
        info = raw.info
        
        # --- Technical Details ---
        sfreq = info['sfreq']
        
        # Channel Names & Exclusion of Non-EEG channels (if necessary)
        ch_names = raw.ch_names
        n_channels = len(ch_names)
        ch_names_str = ", ".join(ch_names)
        
        # Filter Settings (If saved during preprocessing by the MPILMBB team)
        highpass = info.get('highpass', 'N/A')
        lowpass = info.get('lowpass', 'N/A')
        
        # File Length & Samples
        n_samples = raw.n_times
        length_sec = n_samples / sfreq if sfreq else 'N/A'
        
        # Append collected metadata
        # Demographics (Sex/Age) are set as 'Pending' assuming a participants.tsv will be provided later.
        metadata_list.append({
            "Subject_ID": sub_id,
            "File_Name": file_name,
            "Electrode_Set_Channels": n_channels,
            "Channel_Names": ch_names_str,
            "Sampling_Freq_Hz": sfreq,
            "Total_Samples": n_samples,
            "File_Length_sec": round(length_sec, 2) if isinstance(length_sec, float) else length_sec,
            "Highpass_Hz": highpass,
            "Lowpass_Hz": lowpass
        })
        

        # --- Single Stop Condition ---
        if len(metadata_list) == 10:
            print("\nSuccessfully processed 10 files. Stopping extraction.")
            break
            
    except Exception as e:
        print(f"Error processing {file_name}: {e}")

# 3. Exporting Data to Excel
if metadata_list:
    df = pd.DataFrame(metadata_list)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSuccess! Clean metadata exported to: {os.path.abspath(OUTPUT_FILE)}")
else:
    print("\nNo metadata could be extracted. Please check the directory path.")