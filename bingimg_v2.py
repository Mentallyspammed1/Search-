import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from tqdm import tqdm
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)

# Colored Formatter for logging
class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": Fore.BLUE,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Back.WHITE + Style.BRIGHT,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        message = super().format(record)
        return f"{color}{message}"

# Logger setup
logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.handlers = [handler]
logger.setLevel(logging.INFO)

# Color Print Functions
def print_header(text):
    print(Fore.YELLOW + Style.BRIGHT + "\n" + "═" * 50)
    print(Fore.YELLOW + Style.BRIGHT + text)
    print(Fore.YELLOW + Style.BRIGHT + "═" * 50)

def print_success(text):
    print(Fore.GREEN + Style.BRIGHT + "✓ " + text)

def print_error(text):
    print(Fore.RED + Style.BRIGHT + "✗ " + text)

def print_info(text):
    print(Fore.CYAN + Style.NORMAL + "➤ " + text)

# Utility Functions
def validate_date(date_str):
    """Validates date strings in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        print_error(f"Invalid date format: {date_str}. Please use YYYY-MM-DD.")
        return False

def format_date_for_bing(date_str):
    """Formats date for Bing search URL."""
    if not validate_date(date_str):
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d")

def create_directory(path):
    """Creates directory with error handling."""
    try:
        os.makedirs(path, exist_ok=True)
        print_success(f"Directory created: {path}")
    except Exception as e:
        print_error(f"Failed to create directory {path}: {e}")
        sys.exit(1)

def rename_files(file_paths, query):
    """Renames files with progress tracking."""
    renamed_paths = []
    for idx, path in enumerate(tqdm(file_paths, desc=Fore.BLUE + " 🔄 Renaming Files", unit="file"), start=1):
        try:
            new_name = f"{query.replace(' ', '_')}_{idx}{os.path.splitext(path)[1]}"
            new_path = os.path.join(os.path.dirname(path), new_name)
            os.rename(path, new_path)
            renamed_paths.append(new_path)
        except Exception as e:
            print_error(f"Error renaming {path}: {e}")
    return renamed_paths

def apply_filters(**kwargs):
    """Generates Bing filter query parameters."""
    filters = []
    filter_map = {
        "date_filter": None,
        "location": "location:{}",
        "site": "site:{}",
        "file_type": "photo-{}",
    }
    for key, value in kwargs.items():
        if value:
            if key == "date_filter":
                filters.append(value)
            elif template := filter_map.get(key):
                filters.append(template.format(value.lower()))
    return "&qft=" + "+".join(filters) if filters else ""

# Core Functions
def download_images(query, output_dir, limit, timeout, adult_filter_off, filters):
    """Handles image downloading logic."""
    # Implement the downloading logic here
    pass

def get_image_metadata(url):
    """Fetches image metadata from headers."""
    # Implement the metadata fetching logic here
    pass

def save_metadata(metadata_list, output_dir):
    """Saves metadata to JSON file."""
    metadata_file = os.path.join(output_dir, "metadata.json")
    try:
        with open(metadata_file, "w") as f:
            json.dump(metadata_list, f, indent=4)
        print_success(f"Metadata saved to {metadata_file}")
    except Exception as e:
        print_error(f"Failed to save metadata: {e}")

# Main Application
def main():
    # Get user inputs with color prompts
    query = input(Fore.CYAN + "⌨  Search Query: " + Fore.WHITE).strip()
    output_dir = input(Fore.CYAN + "📁 Output Directory: " + Fore.WHITE).strip() or "downloads"
    output_dir = os.path.join(output_dir, query.replace(" ", "_"))
    create_directory(output_dir)

    # Numerical inputs
    try:
        limit = int(input(Fore.CYAN + "🔢 Max Images to Download: " + Fore.WHITE))
        timeout = int(input(Fore.CYAN + "⏳ Timeout (seconds): " + Fore.WHITE))
    except ValueError:
        print_error("Invalid numerical input")
        sys.exit(1)

    adult_filter_off = input(Fore.CYAN + "🔞 Disable adult filter? (y/n): " + Fore.WHITE).lower() == "y"
    filters = {
        "file_type": input(Fore.CYAN + "📁 File Type (jpg/png/gif): " + Fore.WHITE).strip(),
        "date_filter": input(Fore.CYAN + "📅 Date Range (YYYYMMDD..YYYYMMDD): " + Fore.WHITE).strip(),
    }
    filter_query = apply_filters(**filters)

    # Download images
    image_paths = download_images(query, output_dir, limit, timeout, adult_filter_off, filter_query)
    if not image_paths:
        print_error("No images downloaded. Check filters or try different keywords.")
        return

    renamed_paths = rename_files(image_paths, query)
    metadata = []
    for path in renamed_paths:
        metadata.append(get_image_metadata(path))
    save_metadata(metadata, output_dir)

    print_success("Operation completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("Operation cancelled by user!")
        sys.exit(1)
