# Plex Media Library Organizer

**THIS README WAS WRITEN BY AI SO IT'S NOT LEGALLY BINDING**

### See a sample of the data this produces [here](https://docs.google.com/spreadsheets/d/1aS3vE4cL0EKVV0CHE_XSWkSnuO1hEA92cxnj5be6vYY/edit?usp=sharing)

This Python script is designed to help organize media files for use with Plex Media Server. The script categorizes, renames, and moves media files into appropriate directories following Plex's naming conventions. It also reorganizes existing media files into sensible collections and subgroupings, making it easier to manage large libraries.

## Features

- **Categorizes media files** using the OpenAI API.
- **Fetches metadata** from The Movie Database (TMDb) API for movies and TV shows.
- **Renames files** according to Plex naming conventions.
- **Moves files** and sidecar files to appropriate directories.
- **Supports dry-run mode** to preview changes without modifying files.
- **Caches metadata** to optimize subsequent runs, avoiding unnecessary API calls.
- **Reorganizes existing media** into sensible groupings and collections.

## Requirements

- Python 3.7+
- `pip` for managing Python packages
- Accounts and API keys for OpenAI and TMDb

## Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/kridsdale/media_rescue.git
    cd media_rescue
    ```

2. **Install required Python packages:**

    ```bash
    pip install -r requirements.txt
    ```

3. **Set up environment variables:**

    You need to set up environment variables for your API keys:

    - `OPENAI_API_KEY`: Your OpenAI API key.
    - `TMDB_API_KEY`: Your TMDb API key.

    You can set these in your terminal session, `.env` file, or directly in your shell profile:

    ```bash
    export OPENAI_API_KEY="your-openai-api-key"
    export TMDB_API_KEY="your-tmdb-api-key"
    ```

## Usage

1. **Dry Run Mode:**

    Before making any changes, you can run the script in dry-run mode to preview the actions that would be taken:

    ```bash
    python organize_media.py --dry-run
    ```

2. **Actual Run:**

    To perform the actual organization, run the script without the `--dry-run` flag:

    ```bash
    python organize_media.py
    ```

3. **Skipping Cache:**

    If you want to skip using the cache and force the script to re-fetch metadata:

    ```bash
    python organize_media.py --no-cache
    ```

## Configuration

### Directory Structure

**You will need to edit the code to match your specific filesystem.**

- **Orphaned Files:** The script expects media files that need organizing to be located in the `ORPHANED_PATH` directory (`/Volumes/HDD_RAID/Orphaned/` by default). 
- **Shared Media:** Organized files will be moved to the `SHARED_MEDIA_PATH` directory (`/Volumes/HDD_RAID/Shared Media/` by default).

You can customize these paths in the script by modifying the `ORPHANED_PATH` and `SHARED_MEDIA_PATH` variables.

### Caching

- **Cache File:** The script maintains a cache in `media_cache.csv` to store metadata and avoid repeated API calls. The cache is updated incrementally as files are processed.
- **Cache Management:** The script automatically purges cache entries for files that no longer exist in the source directory.

## Error Handling

- **Logging:** The script logs all operations and errors. Errors such as missing metadata or failed API requests are logged, and the script will continue processing the remaining files.

## Development

### Testing

The script includes unit tests to validate its logic. You can run the tests using:

```bash
python -m unittest discover
```

### License

This project is licensed under the Apache 2.0 License. See the LICENSE file for details.

### Acknowledgments

- OpenAI GPT-4 for content categorization.
- TMDb for metadata fetching.

### Disclaimer

This script is not affiliated with or endorsed by Plex, OpenAI, or TMDb. It is a personal project developed to assist with media organization tasks.
