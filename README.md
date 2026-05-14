## File Descriptions

### 1. EDF Data Reading - Metadata table.py
Designed specifically for the **Dortmund (ds005385)** dataset. 
* Navigates through nested BIDS directory structures (`sub-XXX/ses-X/eeg/`).
* Extracts technical metadata (sampling frequency, channel count) and demographic data (age, sex) from EDF headers.
* Includes a dual-loop stop condition to halt execution safely after processing a specific number of records.

### 2. FIF Data Reading - Metadata table.py
Designed specifically for the **Cuba (CHBMP)** dataset.
* Processes flat directory structures where all `.fif` files are located in a single main folder.
* Includes a critical safety net to handle files where the `subject_info` attribute is completely missing (`NoneType`), preventing extraction crashes.
* Extracts and formats metadata, exporting the clean data directly into an Excel summary table.
