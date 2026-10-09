from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import youtube_to_content as research  # noqa: E402


TRANSCRIPT = "[00:00] This is the complete timestamped transcript.\n"
ANALYSIS = {
    "schema_version": "1.0",
    "source": {
        "title": "Source",
        "author": "Author",
        "kind": "youtube",
        "locator": "https://youtu.be/abcdefghijk",
        "duration": "01:00",
        "language": "en",
    },
    "topic": "Cache-safe research",
    "core_thesis": "A fingerprint must describe every material input.",
    "audience": "Creators",
    "hook": {
        "type": "pain_point",
        "timestamp": "00:00-00:05",
        "why_it_works": "Specific risk",
        "reusable_pattern": "Expose a hidden cache failure, then promise a deterministic fix.",
    },
    "flow": [
        {
            "id": "source-beat-01",
            "beat": "problem",
            "t_start": "00:00",
            "t_end": "00:20",
            "purpose": "Define the failure mode.",
            "technique": "Concrete counterexample.",
            "key_claim": "File existence alone is not a cache key.",
            "source_example": "A model change reuses an old artifact.",
        }
    ],
    "pacing": {"total_duration": "01:00", "avg_seconds_per_beat": 0, "pattern_interrupts": []},
    "rhetorical_devices": [],
    "key_facts": [
        {"claim": "Fingerprints include configuration", "evidence": "At 00:15 the source lists inputs", "confidence": "high"}
    ],
    "visual_moments": [],
    "weaknesses": [],
}


class ResearchCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.temp.name) / "run"
        self.url = "https://youtu.be/abcdefghijk"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_second_identical_run_uses_cache_without_client_or_api(self) -> None:
        calls: list[str] = []

        def fake_generate(*args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs["label"])
            return TRANSCRIPT if kwargs["label"] == "transcript" else json.dumps(ANALYSIS)

        with patch.object(research, "generate_content", side_effect=fake_generate):
            first = research.run_research(
                url=self.url,
                run_dir=self.run_dir,
                model="model-a",
                config={"language": "auto", "detail": "full"},
                retries=1,
                client_factory=lambda: object(),
            )
        self.assertEqual(calls, ["transcript", "source analysis"])
        self.assertEqual(first["cache"], {"transcript": False, "analysis": False})

        def forbidden_client():
            raise AssertionError("A cache hit must not request GEMINI_API_KEY or create a client")

        with patch.object(research, "generate_content", side_effect=AssertionError("API should not run")):
            second = research.run_research(
                url=self.url,
                run_dir=self.run_dir,
                model="model-a",
                config={"language": "auto", "detail": "full"},
                retries=1,
                client_factory=forbidden_client,
            )
        self.assertEqual(second["cache"], {"transcript": True, "analysis": True})
        self.assertNotIn("approve the research stage", second["next_action"])

    def test_config_or_model_change_invalidates_fingerprint(self) -> None:
        with patch.object(
            research,
            "generate_content",
            side_effect=[TRANSCRIPT, json.dumps(ANALYSIS)],
        ):
            research.run_research(
                url=self.url,
                run_dir=self.run_dir,
                model="model-a",
                config={"language": "auto"},
                retries=1,
                client_factory=lambda: object(),
            )

        with self.assertRaises(AssertionError):
            research.run_research(
                url=self.url,
                run_dir=self.run_dir,
                model="model-b",
                config={"language": "auto"},
                retries=1,
                client_factory=lambda: (_ for _ in ()).throw(AssertionError("cache invalidated")),
            )

    def test_cli_parser_is_strict(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            research.build_parser().parse_args(
                ["research", "--url", self.url, "--run-dir", str(self.run_dir), "--unknown"]
            )
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
