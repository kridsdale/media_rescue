#!/usr/bin/env python3
"""
Organize Media Files for Plex Media Server

This script organizes media files by categorizing, renaming, and moving them
into appropriate directories following Plex's naming conventions. It also
reorganizes existing media files into sensible collections and subgroupings.

Features:
- Categorizes media files using OpenAI GPT-4 API.
- Fetches metadata from The Movie Database (TMDb) API.
- Renames files according to Plex naming conventions.
- Moves files and sidecar files to appropriate directories.
- Supports dry-run mode to preview changes.
- Caches metadata to optimize subsequent runs.
- Reorganizes existing media into sensible groupings.
"""

import os
import re
import shutil
import requests
import openai
from openai import OpenAI

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
import csv
import argparse
import logging
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Any
import json  # Ensure json is imported

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Set your API keys
openai.api_key = os.getenv('OPENAI_API_KEY')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# Validate API keys
if not openai.api_key or not TMDB_API_KEY:
    logging.error("API keys for OpenAI and TMDb must be set as environment variables.")
    exit(1)

# Define paths
ORPHANED_PATH = '/Volumes/HDD_RAID/Orphaned/'
SHARED_MEDIA_PATH = '/Volumes/HDD_RAID/Shared Media/'

# Cache file path
CACHE_FILE = 'media_cache.csv'

# Categories
# CATEGORIES = ['Anime', 'Kids Movies', 'Kids TV', 'Movies', 'TV']
CATEGORIES = ['Anime']

# Video file extensions
VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv']


def is_video_file(filename: str) -> bool:
    """
    Check if a file is a video file based on its extension.
    """
    return any(filename.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)


def get_files_in_directory(directory: str) -> List[str]:
    """
    Get a list of all video files in the specified directory.
    """
    media_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.startswith('._'):
                continue
            if is_video_file(file):
                media_files.append(os.path.join(root, file))
    return media_files


def categorize_file(filename: str) -> Optional[Dict[str, Any]]:
    """
    Categorize a file using OpenAI's API and return metadata.
    """
    prompt = (
        f"Given the filename: \"{filename}\", determine the appropriate category from the following list:\n"
        f"{CATEGORIES}\n"
        "We will want to determine the name of the TV Show or Movie it represents. Likely this is in the filename. If you can't confidently identify the video file's identity, return empty data. Also, suggest any subfolder organizations if applicable. For subfolder names, do not be redundant with strings that match any other field. Aim to use them for sensible categorization and organization of a large library of movies and TV shows.\n\n"
        "Respond in strict JSON format only, with no explanation or additional text. If any field is unknown, use null as the value. Do not include comments or additional text in the response.\n\n"
        "{\n"
        "    \"category\": \"category name\",\n"
        "    \"subfolders\": [\"subfolder1\", \"subfolder2\", ...],\n"
        "    \"title\": \"cleaned movie or episode title\",\n"
        "    \"show_name\": \"name of tv show (if applicable)\",\n"
        "    \"year\": \"year of release (if known)\",\n"
        "    \"season\": \"season number (if applicable. At least 2 digits, including leading zeros)\",\n"
        "    \"episode\": \"episode number (if applicable. At least 2 digits, including leading zeros)\"\n"
        "}"
    )
    try:
        response = client.chat.completions.create(model='gpt-4o-mini',  # Adjust model if necessary
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=200,
            n=1,
            temperature=0.0) # Strict JSON
        # Access the content correctly
        result = response.choices[0].message.content
        metadata = json_safe_loads(result)
        if not isinstance(metadata, dict):
            raise ValueError("Invalid metadata format.")
        return metadata
    except Exception as e:
        logging.error(f"Error categorizing file {filename}: {e}")
        return None


def fetch_metadata_tmdb(title: str, year: Optional[str], is_tv: bool) -> Optional[Dict[str, Any]]:
    """
    Fetch metadata from TMDb API.
    """
    base_url = 'https://api.themoviedb.org/3'
    search_type = 'tv' if is_tv else 'movie'
    params = {
        'api_key': TMDB_API_KEY,
        'query': title,
    }
    if year is not None and str(year).isdigit():
        params['year'] = year
    try:
        response = requests.get(f"{base_url}/search/{search_type}", params=params)
        response.raise_for_status()
        results = response.json().get('results', [])
        if results:
            return results[0]
        else:
            logging.warning(f"No TMDb results for {title}")
            return None
    except requests.RequestException as e:
        logging.error(f"TMDb API request failed for {title}: {e}")
        return None


def rename_and_move_file(file_path: str, metadata: Dict[str, Any], dry_run: bool) -> Tuple[str, str]:
    """
    Rename and move a file to the appropriate directory.
    """
    category = metadata['category']
    subfolders = metadata.get('subfolders', [])
    title = metadata['title']
    year = metadata.get('year', '')
    season = metadata.get('season', '')
    episode = metadata.get('episode', '')

    # Build destination path
    dest_path = build_destination_path(category, subfolders, title, season, dry_run)

    # Generate new filename
    new_filename = generate_new_filename(file_path, category, title, year, season, episode)

    # Full destination path including filename
    dest_file = dest_path / new_filename

    if dry_run:
        logging.info(f"Dry run: Would move {file_path} to {dest_file}")
    else:
        move_file_and_sidecars(file_path, dest_file)

    return file_path, str(dest_file)

def build_destination_path(category: Optional[str], subfolders: List[str], title: Optional[str], season: Optional[str], dry_run: bool) -> Path:
    """
    Build the destination path based on category, subfolders, title, and season.
    """
    def dedupe_sequential(lst):
        if not lst:
            return []
        deduped_list = [lst[0]]
        for item in lst[1:]:
            if item != deduped_list[-1]:
                deduped_list.append(item)
        return deduped_list

    # Ensure category is not None
    if category is None:
        raise ValueError("Category cannot be None.")

    dest_path = Path(SHARED_MEDIA_PATH) / sanitize_filename(category)
    
    for subfolder in dedupe_sequential(subfolders):
        dest_path /= sanitize_filename(subfolder)

    if category in ['TV Shows', 'Kids TV', 'Anime'] and title:
        # Avoid duplicate title if subfolders exist
        if not subfolders:
            dest_path /= sanitize_filename(title)
        if season is not None and str(season).isdigit():
            dest_path /= f"Season {int(season):02d}"

    if not dry_run:
        dest_path.mkdir(parents=True, exist_ok=True)

    return dest_path


def generate_new_filename(file_path: str, category: str, title: str, year: str, season: str, episode: str) -> str:
    """
    Generate a new filename based on category and metadata.
    """
    file_ext = Path(file_path).suffix
    if category in ['Movies', 'Kids Movies']:
        new_filename = f"{year} - {sanitize_filename(title)}{file_ext}" if year else f"{sanitize_filename(title)}{file_ext}"
    elif category in ['TV Shows', 'Kids TV', 'Anime']:
        season_str = f"S{int(season):02d}" if season is not None and str(season).isdigit() else ""
        episode_str = f"E{int(episode):02d}" if episode is not None and str(episode).isdigit() else ""
        if season_str and episode_str:
            new_filename = f"{season_str}{episode_str} - {sanitize_filename(title)}{file_ext}"
        elif episode_str and not season_str:
            new_filename = f"{episode_str} - {sanitize_filename(title)}{file_ext}"
        else:
            new_filename = f"{sanitize_filename(title)}{file_ext}"
    else:
        new_filename = Path(file_path).name
    return new_filename


def move_file_and_sidecars(src_file: str, dest_file: Path) -> None:
    """
    Move the source file and its sidecar files to the destination.
    """
    try:
        src_dir = Path(src_file).parent
        src_stem = Path(src_file).stem
        for item in src_dir.iterdir():
            if item.stem == src_stem:
                shutil.move(str(item), dest_file.parent / item.name)
        logging.info(f"Moved {src_file} to {dest_file}")
    except Exception as e:
        logging.error(f"Error moving file {src_file} to {dest_file}: {e}")


def read_cache() -> Dict[str, Dict[str, Any]]:
    """
    Read the cache from the CSV file.
    """
    cache = {}
    expected_headers = ['original_path', 'new_path', 'category', 'title', 'show_name', 'year', 'season', 'episode']

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                # Check if headers are as expected
                if reader.fieldnames != expected_headers:
                    raise ValueError(f"Unexpected headers in {CACHE_FILE}. Expected: {expected_headers}, Got: {reader.fieldnames}")

                for row in reader:
                    cache[row['original_path']] = row
            logging.info(f"Loaded cache from {CACHE_FILE}")
        except Exception as e:
            logging.error(f"Error reading cache file {CACHE_FILE}: {e}")
    else:
        logging.info("No cache file found. Starting with an empty cache.")
    return cache

def write_cache_entry(cache_entry: Dict[str, Any]) -> None:
    """
    Write a single cache entry to the CSV file.
    """
    try:
        if not os.path.exists(CACHE_FILE):
            # Write header if file doesn't exist
            with open(CACHE_FILE, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['original_path', 'new_path', 'category', 'title', 'show_name', 'year', 'season', 'episode']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

        with open(CACHE_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['original_path', 'new_path', 'category', 'title', 'show_name', 'year', 'season', 'episode']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerow(cache_entry)

        logging.info(f"Cache entry written to {CACHE_FILE} for {cache_entry['original_path']}")
    except Exception as e:
        logging.error(f"Error writing cache entry for {cache_entry['original_path']}: {e}")


def process_files(media_files: List[str], cache: Dict[str, Dict[str, Any]], dry_run: bool) -> None:
    """
    Process media files: categorize, fetch metadata, rename, and move.
    """
    
    for file_path in media_files:
        logging.info(f"Processing {file_path}")
        if file_path in cache:
            metadata = cache[file_path]
            logging.info(f"Using cached metadata for {file_path}")
        else:
            metadata = categorize_file(Path(file_path).name)
            if metadata is None:
                logging.warning(f"Skipping {file_path} due to missing metadata.")
                continue

            # Fetch additional metadata from TMDb
            is_tv = metadata['category'] in ['TV Shows', 'Kids TV']
            if not is_tv:
                tmdb_data = fetch_metadata_tmdb(metadata['title'], metadata.get('year'), is_tv=is_tv)
                if tmdb_data:
                    metadata = update_metadata_with_tmdb(metadata, tmdb_data, is_tv)
                else:
                    logging.warning(f"No TMDb data for {metadata['title']}")

        try:
            original_path, new_path = rename_and_move_file(file_path, metadata, dry_run=dry_run)

            # Update cache
            cache_entry = {
                'original_path': original_path,
                'new_path': new_path,
                'category': metadata.get('category', ''),
                'title': metadata.get('title', ''),
                'show_name': metadata.get('show_name', ''),
                'year': metadata.get('year', ''),
                'season': metadata.get('season', ''),
                'episode': metadata.get('episode', ''),
            }
            cache[original_path] = cache_entry
            # Write the cache entry immediately
            write_cache_entry(cache_entry)
        except ValueError as e:
            logging.warning(f"Error moving file at original path {file_path}: {e}")

    # Purge cache entries for files not found in current scan
    purge_removed_files_from_cache(cache, media_files)


def update_metadata_with_tmdb(metadata: Dict[str, Any], tmdb_data: Dict[str, Any], is_tv: bool) -> Dict[str, Any]:
    """
    Update metadata with data fetched from TMDb.
    """
    date_key = 'first_air_date' if is_tv else 'release_date'
    metadata['year'] = tmdb_data.get(date_key, '')[:4]
    metadata['title'] = tmdb_data.get('name' if is_tv else 'title', metadata['title'])
    return metadata


def purge_removed_files_from_cache(cache: Dict[str, Dict[str, Any]], media_files: List[str]) -> None:
    """
    Remove cache entries for files that no longer exist.
    """
    cache_keys = set(cache.keys())
    media_files_set = set(media_files)
    removed_files = cache_keys - media_files_set
    for file_path in removed_files:
        logging.info(f"Removing {file_path} from cache as it no longer exists.")
        cache.pop(file_path, None)


def reorganize_shared_media(dry_run: bool) -> None:
    """
    Reorganize existing Shared Media directories to create sensible collections and subgroupings.
    """
    logging.info("Starting reorganization of Shared Media...")

    # Dictionary to store media files grouped by category
    media_catalog = collect_media_files()

    # Step 2: Use OpenAI API to suggest collections and subgroupings
    for category, files in media_catalog.items():
        logging.info(f"Analyzing {len(files)} files in category '{category}' for reorganization.")
        groupings = get_groupings_from_titles(category, files)
        if groupings:
            move_files_to_groupings(groupings, files, category, dry_run)

    logging.info("Reorganization of Shared Media completed.")


def collect_media_files() -> Dict[str, List[str]]:
    """
    Collect media files from the Shared Media directory.
    """
    media_catalog: Dict[str, List[str]] = defaultdict(list)
    for category in CATEGORIES:
        category_path = Path(SHARED_MEDIA_PATH) / category
        if category_path.exists() and category_path.is_dir():
            media_files = get_files_in_directory(str(category_path))
            media_catalog[category].extend(media_files)
    return media_catalog


def get_groupings_from_titles(category: str, files: List[str]) -> List[Dict[str, Any]]:
    """
    Get groupings of titles using OpenAI API.
    """
    max_files_to_think_of_at_once = 500
    titles = [Path(f).stem for f in files]
    title_chunks = [titles[i:i + max_files_to_think_of_at_once] for i in range(0, len(titles), max_files_to_think_of_at_once)]
    groupings = []
    for chunk in title_chunks:
        grouping_data = get_grouping_data_from_api(category, chunk)
        if grouping_data:
            groupings.extend(grouping_data.get('groupings', []))
    return groupings


def get_grouping_data_from_api(category: str, titles_chunk: List[str]) -> Optional[Dict[str, Any]]:
    """
    Call OpenAI API to get grouping data for a chunk of titles.
    """
    prompt = (
        f"Given the list of titles in the '{category}' category:\n"
        f"{titles_chunk}\n\n"
        "Group these titles into sensible collections or subgroupings based on their similarities,\n"
        "such as 'Disney Movies', 'Pixar Movies', or 'Science Fiction TV Shows'.\n\n"
        "Provide the result as a JSON object in the following format:\n"
        "Respond in strict JSON format only, with no explanation or additional text. If any field is unknown, use null as the value. Do not include comments or additional text in the response.\n\n"
        "{\n"
        "    \"groupings\": [\n"
        "        {\n"
        "            \"group_name\": \"Group Name\",\n"
        "            \"titles\": [\"Title1\", \"Title2\", ...]\n"
        "        },\n"
        "        ...\n"
        "    ]\n"
        "}"
    )
    try:
        response = client.chat.completions.create(model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=16384, # need this to be max size
            n=1,
            temperature=0.0) # Strict
        result = response.choices[0].message.content
        logging.info(f"Grouping raw data for '{category}': {result}")
        grouping_data = json_safe_loads(result)
        logging.info(f"Grouping response for '{category}': {grouping_data}")
        if not isinstance(grouping_data, dict):
            raise ValueError("Invalid grouping data format.")
        return grouping_data
    except Exception as e:
        logging.error(f"Error during grouping API call for category '{category}': {e}")
        return None


def move_files_to_groupings(groupings: List[Dict[str, Any]], files: List[str], category: str, dry_run: bool) -> None:
    """
    Move files into their respective groupings.
    """
    for group in groupings:
        group_name = group.get('group_name')
        group_titles = group.get('titles', [])
        if not group_name or not group_titles:
            continue

        # Create group subfolder under the category
        group_path = Path(SHARED_MEDIA_PATH) / category / sanitize_filename(group_name)
        if not dry_run:
            group_path.mkdir(parents=True, exist_ok=True)
        else:
            logging.info(f"Dry run: Would create directory {group_path}")

        # Move files into the group subfolder
        for title in group_titles:
            matched_files = [f for f in files if Path(f).stem == title]
            for file_path in matched_files:
                dest_file_path = group_path / Path(file_path).name
                if dry_run:
                    logging.info(f"Dry run: Would move {file_path} to {dest_file_path}")
                else:
                    try:
                        shutil.move(file_path, dest_file_path)
                        logging.info(f"Moved {file_path} to {dest_file_path}")
                    except Exception as e:
                        logging.error(f"Error moving {file_path} to {dest_file_path}: {e}")


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitize a string to be safe for use as a filename.
    If the filename is None, return an empty string.
    """
    if not isinstance(filename, str):
        return ""
    return re.sub(r'[<>:"/\\|?*]', '', filename)


def json_safe_loads(s: str) -> Any:
    """
    Safely parse a JSON string, handling common errors.
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        logging.error(f"JSON decoding error: {e}")
        return None


def main() -> None:
    """
    Main function to organize media files.
    """
    parser = argparse.ArgumentParser(description='Organize media files for Plex Media Server.')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run and output actions without modifying files.')
    parser.add_argument('--no-cache', action='store_true', help='Do not use the cache.')
    parser.add_argument('--rescue', action='store_true', help='Use LLM to rescue orphaned files and restore the library.')
    parser.add_argument('--reorganize', action='store_true', help='Use LLM to re-organize the existing library.')
    args = parser.parse_args()

    if args.rescue:
        media_files = get_files_in_directory(ORPHANED_PATH)
        if media_files:
            if args.no_cache:
                cache = {}
                logging.info('Cache usage disabled.')
            else:
                cache = read_cache()

            process_files(media_files, cache, dry_run=args.dry_run)

        else:
            logging.info('No media files found in the orphaned directory.')

    elif args.reorganize:
        # Run the reorganization function
        reorganize_shared_media(dry_run=args.dry_run)

    else:
        logging.error('Specify one, or both, of --rescue and --reorganize args.')


if __name__ == '__main__':
    main()