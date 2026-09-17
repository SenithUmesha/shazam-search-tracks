import unittest

from shazam_client import normalize_hit, normalize_query, parse_tracks, safe_external_url


class ShazamClientTests(unittest.TestCase):
    def test_query_normalization(self):
        self.assertEqual(normalize_query("  Daft Punk  "), "Daft Punk")
        self.assertEqual(normalize_query(None), "")

    def test_external_url_validation(self):
        self.assertEqual(
            safe_external_url("https://www.shazam.com/track/123"),
            "https://www.shazam.com/track/123",
        )
        self.assertEqual(safe_external_url("javascript:alert(1)"), None)
        self.assertEqual(safe_external_url("/relative/path"), None)

    def test_normalizes_a_track_without_assuming_nested_fields_exist(self):
        hit = {
            "track": {
                "key": "123",
                "title": "Digital Love",
                "subtitle": "Daft Punk",
                "images": {"coverart": "https://example.com/cover.jpg"},
                "url": "https://www.shazam.com/track/123",
                "hub": {
                    "actions": [
                        {"name": "apple", "uri": "https://music.example.com/song"}
                    ]
                },
            }
        }

        track = normalize_hit(hit)
        self.assertIsNotNone(track)
        self.assertEqual(track.key, "123")
        self.assertEqual(track.title, "Digital Love")
        self.assertEqual(track.artist, "Daft Punk")
        self.assertEqual(track.image_url, "https://example.com/cover.jpg")
        self.assertEqual(track.listen_url, "https://music.example.com/song")

    def test_rejects_malformed_hits(self):
        self.assertIsNone(normalize_hit(None))
        self.assertIsNone(normalize_hit({}))
        self.assertIsNone(normalize_hit({"track": "bad"}))

    def test_parse_tracks_handles_missing_payload_and_deduplicates(self):
        self.assertEqual(parse_tracks(None), [])
        self.assertEqual(parse_tracks({}), [])

        payload = {
            "tracks": {
                "hits": [
                    {"track": {"key": "1", "title": "One", "subtitle": "Artist"}},
                    {"track": {"key": "1", "title": "One duplicate", "subtitle": "Artist"}},
                    {"track": {"key": "2", "title": "Two"}},
                    None,
                ]
            }
        }

        tracks = parse_tracks(payload)
        self.assertEqual([track.key for track in tracks], ["1", "2"])
        self.assertEqual(tracks[1].artist, "Unknown artist")

    def test_unsafe_action_urls_are_not_returned(self):
        track = normalize_hit(
            {
                "track": {
                    "key": "x",
                    "title": "Track",
                    "hub": {"actions": [{"uri": "javascript:alert(1)"}]},
                }
            }
        )
        self.assertIsNotNone(track)
        self.assertIsNone(track.listen_url)


if __name__ == "__main__":
    unittest.main()
