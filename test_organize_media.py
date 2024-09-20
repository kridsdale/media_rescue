import unittest
from unittest.mock import patch, MagicMock
from organize_media import (
    is_video_file,
    categorize_file,
    fetch_metadata_tmdb,
    generate_new_filename,
    sanitize_filename,
    json_safe_loads,
    build_destination_path,
    update_metadata_with_tmdb,
)
from pathlib import Path


class TestOrganizeMedia(unittest.TestCase):

    def test_is_video_file(self):
        self.assertTrue(is_video_file('movie.mp4'))
        self.assertTrue(is_video_file('episode.mkv'))
        self.assertFalse(is_video_file('document.pdf'))
        self.assertFalse(is_video_file('image.jpg'))

    @patch('openai.resources.chat.Completions.create')
    def test_categorize_file(self, mock_openai):
        # Mock the OpenAI API response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"category": "Movies", "subfolders": [], "title": "Test Movie", "year": "2020", "season": "", "episode": ""}'
                )
            )
        ]
        mock_openai.return_value = mock_response

        filename = 'Test.Movie.2020.1080p.mkv'
        metadata = categorize_file(filename)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['category'], 'Movies')
        self.assertEqual(metadata['title'], 'Test Movie')
        self.assertEqual(metadata['year'], '2020')

    @patch('requests.get')
    def test_fetch_metadata_tmdb(self, mock_get):
        # Mock the TMDb API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [{
                'title': 'Test Movie',
                'release_date': '2020-01-01',
            }]
        }
        mock_get.return_value = mock_response

        metadata = fetch_metadata_tmdb('Test Movie', year='2020', is_tv=False)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['title'], 'Test Movie')
        self.assertEqual(metadata['release_date'], '2020-01-01')

    def test_generate_new_filename_movie(self):
        file_path = '/path/to/Test.Movie.2020.mkv'
        category = 'Movies'
        title = 'Test Movie'
        year = '2020'
        season = ''
        episode = ''
        new_filename = generate_new_filename(file_path, category, title, year, season, episode)
        self.assertEqual(new_filename, '2020 - Test Movie.mkv')

    def test_generate_new_filename_tv_show(self):
        file_path = '/path/to/Test.Show.S01E01.mkv'
        category = 'TV Shows'
        title = 'Test Show'
        year = ''
        season = '1'
        episode = '1'
        new_filename = generate_new_filename(file_path, category, title, year, season, episode)
        self.assertEqual(new_filename, 'S01E01 - Test Show.mkv')

    def test_sanitize_filename(self):
        dirty_filename = 'Test:/Movie*?<>|"'
        clean_filename = sanitize_filename(dirty_filename)
        self.assertEqual(clean_filename, 'TestMovie')

    def test_json_safe_loads_valid(self):
        json_str = '{"key": "value"}'
        data = json_safe_loads(json_str)
        self.assertEqual(data, {"key": "value"})

    def test_json_safe_loads_invalid(self):
        json_str = '{"key": "value"'
        with self.assertLogs(level='ERROR') as log:
            data = json_safe_loads(json_str)
            self.assertIsNone(data)
            self.assertIn('JSON decoding error', log.output[0])

    def test_build_destination_path_movie(self):
        category = 'Movies'
        subfolders = []
        title = 'Test Movie'
        season = ''
        dest_path = build_destination_path(category, subfolders, title, season, dry_run=1)
        expected_path = Path('/Volumes/HDD_RAID/Shared Media/Movies')
        self.assertEqual(dest_path, expected_path)

    def test_build_destination_path_tv_show(self):
        category = 'TV Shows'
        subfolders = []
        title = 'Test Show'
        season = '1'
        dest_path = build_destination_path(category, subfolders, title, season, dry_run=1)
        expected_path = Path('/Volumes/HDD_RAID/Shared Media/TV Shows/Test Show/Season 01')
        self.assertEqual(dest_path, expected_path)

    def test_build_destination_path_tv_show_1_subfolder(self):
        category = 'TV Shows'
        subfolders = ['FooBar']
        title = 'Test Show'
        season = '1'
        dest_path = build_destination_path(category, subfolders, title, season, dry_run=1)
        expected_path = Path('/Volumes/HDD_RAID/Shared Media/TV Shows/FooBar/Season 01')
        self.assertEqual(dest_path, expected_path)

    def test_build_destination_path_tv_show_2_subfolders(self):
        category = 'TV Shows'
        subfolders = ['FooBar', 'BazBoo']
        title = 'Test Show'
        season = '1'
        dest_path = build_destination_path(category, subfolders, title, season, dry_run=1)
        expected_path = Path('/Volumes/HDD_RAID/Shared Media/TV Shows/FooBar/BazBoo/Season 01')
        self.assertEqual(dest_path, expected_path)

    def test_build_destination_path_tv_show_2_sequential_subfolders(self):
        category = 'TV Shows'
        subfolders = ['FooBar', 'BazBoo', 'BazBoo']
        title = 'Test Show'
        season = '1'
        dest_path = build_destination_path(category, subfolders, title, season, dry_run=1)
        expected_path = Path('/Volumes/HDD_RAID/Shared Media/TV Shows/FooBar/BazBoo/Season 01')
        self.assertEqual(dest_path, expected_path)

    def test_update_metadata_with_tmdb_movie(self):
        metadata = {
            'category': 'Movies',
            'title': 'Test Movie',
            'year': '',
            'season': '',
            'episode': '',
        }
        tmdb_data = {
            'title': 'Test Movie',
            'release_date': '2020-01-01',
        }
        updated_metadata = update_metadata_with_tmdb(metadata, tmdb_data, is_tv=False)
        self.assertEqual(updated_metadata['title'], 'Test Movie')
        self.assertEqual(updated_metadata['year'], '2020')

    def test_update_metadata_with_tmdb_tv_show(self):
        metadata = {
            'category': 'TV Shows',
            'title': 'Test Show',
            'year': '',
            'season': '',
            'episode': '',
        }
        tmdb_data = {
            'name': 'Test Show',
            'first_air_date': '2019-05-15',
        }
        updated_metadata = update_metadata_with_tmdb(metadata, tmdb_data, is_tv=True)
        self.assertEqual(updated_metadata['title'], 'Test Show')
        self.assertEqual(updated_metadata['year'], '2019')


if __name__ == '__main__':
    unittest.main()
