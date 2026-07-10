from pathlib import Path

def define_dir(root, *names):
    """Creates a directory and ensures it exists."""
    path = root
    for name in names:
        path = path / name  # use pathlib's '/' operator to join paths
    path.mkdir(parents=True, exist_ok=True)
    return path

# Get the current directory where the script is executed
DIR_PROJ = Path.cwd().parent

# Define the paths for 'logs' and 'results' directories
# insert the raw_data under DIR_RAWDATA
DIR_DATA = define_dir(DIR_PROJ, "02_data")

DIR_DOWNLOAD = define_dir(DIR_DATA, "00_download")
DIR_RAWDATA = define_dir(DIR_DATA, "00_rawdata")
DIR_PREPDATA = define_dir(DIR_DATA, "01_prepdata")
DIR_METADATA = define_dir(DIR_DATA, "02_metadata")

DIR_SCRIPTS = define_dir(DIR_PROJ, "03_analysis")