from pathlib import Path

def define_dir(root, *names):
    """Creates a directory and ensures it exists."""
    path = root
    for name in names:
        path = path / name  # use pathlib's '/' operator to join paths
    path.mkdir(parents=True, exist_ok=True)
    return path

# Get the current directory where the script is executed
DIR_PROJ = Path(__file__).parent.parent

# Define the paths for 'logs' and 'results' directories
# insert the raw_data under DIR_RAWDATA
DIR_DATA = define_dir(DIR_PROJ, "02_data")

# Define subdirectories under DIR_DATA
DIR_DOWNLOAD = define_dir(DIR_DATA, "00_download")

# Downloaded Data Directories
BASE_DIR_CHBMP = DIR_DOWNLOAD.joinpath("chbmp")
BASE_DIR_DORT = DIR_DOWNLOAD.joinpath("ds005385-1.0.2")
BASE_DIR_MPI = DIR_DOWNLOAD.joinpath("mpilmbb") / "preprocessed"

# Updated Demographic File Paths
DEMO_CHBMP = DIR_DOWNLOAD.joinpath("chbmp").joinpath("chbmp_Demographic_data.csv")
DEMO_DORT = DIR_DOWNLOAD.joinpath("ds005385-1.0.2").joinpath("ds005385_participants.tsv")
DEMO_MPI = DIR_DOWNLOAD.joinpath("mpilmbb").joinpath("META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv")

# Define additional subdirectories under DIR_DATA
DIR_PREPDATA = define_dir(DIR_DATA, "01_prepdata")
DIR_METADATA = define_dir(DIR_DATA, "02_metadata")

# Define the path for the '03_analysis' directory
DIR_SCRIPTS = define_dir(DIR_PROJ, "03_analysis")
DIR_RESULTS = define_dir(DIR_PROJ, "04_results")