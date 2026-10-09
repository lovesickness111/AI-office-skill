from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import workflow  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def modern_audience_profile(*, avoid_terms: list[str] | None = None) -> dict[str, object]:
    return {
        "primary_groups": [
            {
                "id": "general-viewers",
                "label": "General viewers",
                "need": "Understand why a review decision can silently become stale.",
                "assumed_knowledge": [],
            }
        ],
        "secondary_groups": [],
        "shared_need": "A concrete explanation without process jargon.",
        "shared_baseline": "Viewers know that teams review work, but not the tooling vocabulary.",
        "desired_takeaway": "Bind an approval to the exact artifact revision.",
        "do_not_assume": ["software delivery ceremonies"],
        "avoid_terms": list(avoid_terms or ["retrospective"]),
        "language": "en",
        "tone": ["direct", "plain-language"],
        "term_policy": "plain_first",
    }


def modern_hook_brief(*, max_words: int = 18) -> dict[str, object]:
    return {
        "section_id": "segment-01",
        "opening_move": "State the quiet-edit risk immediately.",
        "title_alignment": "Confirm that the video explains approval gates.",
        "viewer_payoff": "Show the safeguard in plain language.",
        "curiosity_gap": "How can yesterday's approval stop being current?",
        "body_handoff": "Move from the risk to the artifact hash safeguard.",
        "target_seconds": 6,
        "max_seconds": 8,
        "max_words": max_words,
        "delivery_wpm": 150,
        "avoid": ["greeting", "long setup", "unexplained jargon"],
    }


class WorkflowFixture:
    def __init__(self, root: Path):
        self.root = root
        workflow.init_run(root, source_url="https://youtu.be/abcdefghijk")

    def research(self) -> None:
        research = self.root / "research"
        research.mkdir(parents=True, exist_ok=True)
        (research / "full_transcript.md").write_text(
            "[00:00] A verified technical claim and its explanation.\n", encoding="utf-8"
        )
        write_json(
            research / "source_analysis.json",
            {
                "schema_version": "1.0",
                "source": {
                    "title": "Fixture",
                    "kind": "youtube",
                    "locator": "https://youtu.be/abcdefghijk",
                    "language": "en",
                },
                "topic": "Testing workflows",
                "core_thesis": "Approval hashes make review explicit.",
                "audience": "Technical creators",
                "hook": {
                    "type": "pain_point",
                    "timestamp": "00:00",
                    "why_it_works": "It exposes a hidden review risk.",
                    "reusable_pattern": "Hidden mutation followed by a concrete safeguard.",
                },
                "flow": [
                    {
                        "id": "source-beat-01",
                        "t_start": "00:00",
                        "purpose": "State the risk.",
                        "technique": "Concrete warning.",
                        "key_claim": "Approvals need immutable identity.",
                    }
                ],
                "key_facts": [{"claim": "A verified claim", "evidence": "00:00"}],
            },
        )
        (research / "source_playbook.md").write_text("# Source Playbook\n\nUseful notes.\n", encoding="utf-8")
        write_json(
            research / "claim_ledger.json",
            {
                "schema_version": "1.0",
                "claims": [
                    {
                        "id": "claim-001",
                        "text": "A verified claim",
                        "kind": "source_claim",
                        "evidence": [{"timestamp": "00:00", "detail": "Spoken in source"}],
                        "verification_status": "supported",
                        "confidence": "high",
                        "must_keep": True,
                        "usage_note": "Attribute this claim to the source.",
                    }
                ],
            },
        )
        workflow.register_stage(self.root, "research")

    def scope(self, *, audience_profile: dict[str, object] | None = None) -> None:
        data: dict[str, object] = {
                "schema_version": "1.0",
                "format": "single_video",
                "title": "Approval gates",
                "thesis": "Hash-bound approval prevents silent changes.",
                "audience": "Technical creators",
                "creator_goal": "Teach a repeatable review workflow.",
                "viewer_promise": "Recognize and prevent stale approvals.",
                "rationale": "The source supports one focused explanation.",
                "included_claim_ids": ["claim-001"],
                "deferred_claim_ids": [],
                "word_budget": {"min": 8, "target": 20, "max": 80},
                "target_duration_seconds": 45,
                "knowledge_units": [
                    {
                        "id": "unit-01",
                        "question": "Why can an approval become stale?",
                        "claim_ids": ["claim-001"],
                    }
                ],
                "parts": [],
                "tradeoffs": [],
                "open_questions": [],
                "success_criteria": ["The viewer can explain hash-bound approval."],
            }
        if audience_profile is not None:
            data["audience_profile"] = audience_profile
        write_json(self.root / "editorial" / "scope_proposal.json", data)
        workflow.register_stage(self.root, "scope")

    def outline(self, *, hook_brief: dict[str, object] | None = None) -> None:
        data: dict[str, object] = {
                "schema_version": "1.0",
                "title": "Approval gates",
                "word_budget": {"min": 8, "target": 20, "max": 80},
                "hook_strategy": "Reveal a harmless-looking edit that invalidates approval.",
                "sections": [
                    {
                        "id": "segment-01",
                        "title": "The hidden risk",
                        "purpose": "Introduce the problem and explain the evidence.",
                        "summary": "Show why review must bind to an immutable artifact revision.",
                        "claim_ids": ["claim-001"],
                        "knowledge_unit_ids": ["unit-01"],
                        "estimated_words": 20,
                        "transition_in": "Start with the surprise.",
                        "transition_out": "Move from risk to solution.",
                    }
                ],
            }
        if hook_brief is not None:
            data["hook_brief"] = hook_brief
        write_json(self.root / "editorial" / "outline.json", data)
        workflow.register_stage(self.root, "outline")

    def script(
        self,
        *,
        hook: dict[str, object] | None = None,
        modern_quality: bool = False,
        text: str = "A quiet edit can invalidate yesterday's approval, so bind every decision to the artifact hash.",
        target_duration_seconds: int = 45,
    ) -> None:
        quality: dict[str, object] = {
            "fact_pass": {"status": "passed", "summary": "All claims map to evidence."},
            "continuity_pass": {"status": "passed", "summary": "The single segment is coherent."},
            "originality_pass": {"status": "passed", "summary": "No source expression was copied."},
        }
        if modern_quality:
            quality.update(
                {
                    "audience_fit_pass": {
                        "status": "passed",
                        "summary": "The explanation uses the approved audience baseline.",
                    },
                    "spoken_language_pass": {
                        "status": "passed",
                        "summary": "The copy is plain and natural when read aloud.",
                    },
                    "hook_pass": {
                        "status": "passed",
                        "word_count": 15,
                        "estimated_seconds": 6.0,
                        "summary": "The opening states the risk inside the approved budget.",
                    },
                }
            )
        data: dict[str, object] = {
                "schema_version": "1.0",
                "title": "Approval gates",
                "word_budget": {"min": 8, "target": 20, "max": 80},
                "target_duration_seconds": target_duration_seconds,
                "segments": [
                    {
                        "id": "segment-01",
                        "heading": "The hidden risk",
                        "text": text,
                        "claim_ids": ["claim-001"],
                        "producer_notes": {
                            "delivery": "Pause after quiet edit.",
                            "camera": "Medium shot.",
                            "evidence": ["claim-001 at 00:00"],
                        },
                    }
                ],
                "quality": quality,
            }
        if hook is not None:
            data["hook"] = hook
        write_json(self.root / "script" / "final.json", data)
        workflow.materialize_script_teleprompter(self.root)
        workflow.register_stage(self.root, "script")

    def storyboard(self) -> None:
        text = "A quiet edit can invalidate yesterday's approval, so bind every decision to the artifact hash."
        write_json(
            self.root / "storyboard" / "storyboard.json",
            {
                "schema_version": "1.0",
                "project": {"ratio": "16:9", "fps": 30, "theme": "dark"},
                "segments": [
                    {
                        "id": "segment-01",
                        "text": text,
                        "cues": [{"id": "cue-01", "phrase": "artifact hash"}],
                    }
                ],
                "shots": [
                    {
                        "id": "shot-01",
                        "segment_id": "segment-01",
                        "lane": "support_right",
                        "intent": "Show the approval digest locking into place.",
                        "enter": {"cue_id": "cue-01", "offset_ms": -150},
                        "renderer": {"kind": "component", "entry": "assets/approval-lock/index.html"},
                        "duration_ms": 2500,
                    }
                ],
                "assets": [],
            },
        )
        workflow.register_stage(self.root, "storyboard")


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.temp.name) / "run"
        self.fixture = WorkflowFixture(self.run_dir)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _prepare_modern_outline(self, *, hook_brief: dict[str, object] | None = None) -> None:
        self.fixture.research()
        self.fixture.scope(audience_profile=modern_audience_profile())
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline(hook_brief=hook_brief or modern_hook_brief())
        workflow.approve_stage(self.run_dir, "outline")

    def _prepare_storyboard(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        workflow.approve_stage(self.run_dir, "outline")
        self.fixture.script()
        workflow.approve_stage(self.run_dir, "script")
        self.fixture.storyboard()

    def test_legacy_contract_remains_valid_without_audience_profile(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        scope_result = workflow.validate_stage(self.run_dir, "scope")
        self.assertTrue(scope_result.valid)
        self.assertEqual(scope_result.warnings, [])

        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        outline_result = workflow.validate_stage(self.run_dir, "outline")
        self.assertTrue(outline_result.valid)
        self.assertEqual(outline_result.warnings, [])

        workflow.approve_stage(self.run_dir, "outline")
        self.fixture.script(target_duration_seconds=6)
        script_result = workflow.validate_stage(self.run_dir, "script")
        self.assertTrue(script_result.valid)
        self.assertEqual(script_result.warnings, [])
        self.assertNotIn("hook_word_count", script_result.metrics)

    def test_modern_audience_hook_and_spoken_language_contract_is_valid(self) -> None:
        self._prepare_modern_outline()
        self.fixture.script(
            hook={"segment_id": "segment-01", "end_phrase": "artifact hash."},
            modern_quality=True,
        )

        result = workflow.validate_stage(self.run_dir, "script")
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.metrics["hook_word_count"], 15)
        self.assertEqual(result.metrics["hook_estimated_seconds"], 6.0)

    def test_hook_contract_activates_without_audience_profile(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline(hook_brief=modern_hook_brief())
        workflow.approve_stage(self.run_dir, "outline")

        with self.assertRaises(workflow.ArtifactValidationError):
            self.fixture.script(
                hook={"segment_id": "segment-01", "end_phrase": "artifact hash."},
                modern_quality=False,
            )
        result = workflow.validate_stage(self.run_dir, "script")
        self.assertFalse(result.valid)
        self.assertTrue(any("quality.hook_pass" in error for error in result.errors))

    def test_hook_pass_metrics_must_match_measured_prefix(self) -> None:
        self._prepare_modern_outline()
        self.fixture.script(
            hook={"segment_id": "segment-01", "end_phrase": "artifact hash."},
            modern_quality=True,
        )
        script_path = self.run_dir / "script" / "final.json"
        script = json.loads(script_path.read_text(encoding="utf-8"))
        script["quality"]["hook_pass"]["word_count"] = 99
        script["quality"]["hook_pass"]["estimated_seconds"] = 99
        write_json(script_path, script)

        result = workflow.validate_stage(self.run_dir, "script")
        self.assertFalse(result.valid)
        self.assertTrue(any("word_count must equal" in error for error in result.errors))
        self.assertTrue(any("estimated_seconds must equal" in error for error in result.errors))

    def test_scope_rejects_incomplete_audience_profile(self) -> None:
        self.fixture.research()
        with self.assertRaises(workflow.ArtifactValidationError):
            self.fixture.scope(audience_profile={"primary_groups": []})

        result = workflow.validate_stage(self.run_dir, "scope")
        self.assertFalse(result.valid)
        self.assertTrue(any("primary_groups" in error for error in result.errors))
        self.assertTrue(any("shared_need" in error for error in result.errors))

    def test_profiled_outline_requires_hook_brief(self) -> None:
        self.fixture.research()
        self.fixture.scope(audience_profile=modern_audience_profile())
        workflow.approve_stage(self.run_dir, "scope")

        with self.assertRaises(workflow.ArtifactValidationError):
            self.fixture.outline()
        result = workflow.validate_stage(self.run_dir, "outline")
        self.assertFalse(result.valid)
        self.assertTrue(any("hook_brief is required" in error for error in result.errors))

    def test_profiled_script_requires_hook_locator_and_quality_passes(self) -> None:
        self._prepare_modern_outline()

        with self.assertRaises(workflow.ArtifactValidationError):
            self.fixture.script()
        result = workflow.validate_stage(self.run_dir, "script")
        self.assertFalse(result.valid)
        self.assertTrue(any("script.hook is required" in error for error in result.errors))
        for name in ("audience_fit_pass", "spoken_language_pass", "hook_pass"):
            self.assertTrue(any(name in error for error in result.errors), name)

    def test_profiled_script_rejects_avoid_term_in_spoken_text(self) -> None:
        self._prepare_modern_outline()
        with self.assertRaises(workflow.ArtifactValidationError):
            self.fixture.script(
                hook={"segment_id": "segment-01", "end_phrase": "artifact hash."},
                modern_quality=True,
                text=(
                    "Retrospective can hide a quiet edit, so bind every approval "
                    "to the exact artifact hash."
                ),
            )

        result = workflow.validate_stage(self.run_dir, "script")
        self.assertFalse(result.valid)
        self.assertTrue(any("audience-blocked term 'retrospective'" in error for error in result.errors))

    def test_profiled_script_rejects_hook_over_approved_budget(self) -> None:
        self._prepare_modern_outline(hook_brief=modern_hook_brief(max_words=5))
        with self.assertRaises(workflow.ArtifactValidationError):
            self.fixture.script(
                hook={"segment_id": "segment-01", "end_phrase": "artifact hash."},
                modern_quality=True,
            )

        result = workflow.validate_stage(self.run_dir, "script")
        self.assertFalse(result.valid)
        self.assertTrue(any("above the approved maximum 5" in error for error in result.errors))

    def test_gates_require_scope_approval_but_not_research_approval(self) -> None:
        self.fixture.research()
        self.assertEqual(workflow.inspect_stage(self.run_dir, "research")["approval_status"], "not_required")
        self.fixture.scope()
        with self.assertRaises(workflow.GateError):
            self.fixture.outline()
        workflow.approve_stage(self.run_dir, "scope", approved_by="test")
        self.fixture.outline()
        self.assertEqual(workflow.inspect_stage(self.run_dir, "outline")["state"], "registered")

    def test_approval_is_stale_after_artifact_changes(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        scope_path = self.run_dir / "editorial" / "scope_proposal.json"
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        scope["title"] = "Changed after approval"
        write_json(scope_path, scope)
        info = workflow.inspect_stage(self.run_dir, "scope")
        self.assertEqual(info["state"], "modified")
        self.assertEqual(info["approval_status"], "stale")
        with self.assertRaises(workflow.GateError):
            self.fixture.outline()

    def test_scope_contract_rejects_missing_editorial_decisions(self) -> None:
        self.fixture.research()
        write_json(
            self.run_dir / "editorial" / "scope_proposal.json",
            {
                "schema_version": "1.0",
                "format": "single_video",
                "title": "Incomplete scope",
                "thesis": "A title and thesis are not enough to approve production.",
                "included_claim_ids": ["claim-001"],
                "deferred_claim_ids": [],
                "target_duration_seconds": 45,
                "word_budget": {"min": 8, "target": 20, "max": 80},
            },
        )
        result = workflow.validate_stage(self.run_dir, "scope")
        self.assertFalse(result.valid)
        self.assertTrue(any("viewer_promise" in error for error in result.errors))
        self.assertTrue(any("knowledge_units" in error for error in result.errors))

    def test_upstream_change_keeps_downstream_approval_stale_after_reregister(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        transcript = self.run_dir / "research" / "full_transcript.md"
        transcript.write_text("[00:00] Revised source evidence with a material change.\n", encoding="utf-8")
        workflow.register_stage(self.run_dir, "research")
        self.assertEqual(workflow.inspect_stage(self.run_dir, "scope")["approval_status"], "stale")
        workflow.register_stage(self.run_dir, "scope")
        self.assertEqual(workflow.inspect_stage(self.run_dir, "scope")["approval_status"], "stale")

    def test_storyboard_rejects_missing_cue_phrase_and_unsafe_entry(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        workflow.approve_stage(self.run_dir, "outline")
        self.fixture.script()
        workflow.approve_stage(self.run_dir, "script")
        write_json(
            self.run_dir / "storyboard" / "storyboard.json",
            {
                "schema_version": "1.0",
                "project": {"ratio": "16:9", "fps": 30},
                "segments": [
                    {"id": "segment-01", "text": "Only real words live here.", "cues": [{"id": "cue-01", "phrase": "not here"}]}
                ],
                "shots": [
                    {
                        "id": "shot-01",
                        "segment_id": "segment-01",
                        "intent": "Explain",
                        "enter": {"cue_id": "cue-01"},
                        "renderer": {"kind": "html", "entry": "../escape.html"},
                    }
                ],
                "assets": [],
            },
        )
        result = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertFalse(result.valid)
        self.assertTrue(any("does not occur" in error for error in result.errors))
        self.assertTrue(any("safe relative path" in error for error in result.errors))

    def test_storyboard_accepts_implicit_support_top_on_vertical_project(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"].update({"ratio": "9:16", "width": 432, "height": 768})
        storyboard["shots"][0].pop("lane")
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertTrue(result.valid, result.errors)

    def test_storyboard_accepts_legacy_16_9_with_explicit_non_top_lane(self) -> None:
        self._prepare_storyboard()

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertTrue(result.valid, result.errors)

    def test_storyboard_accepts_additive_editorial_plan(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["editorial_plan"] = {
            "hook_segment_id": "segment-01",
            "hook_beats": [
                {
                    "id": "beat-title",
                    "cue_id": "cue-01",
                    "purpose": "title",
                    "coverage": "shot",
                    "shot_ids": ["shot-01"],
                },
                {
                    "id": "beat-promise",
                    "cue_id": "cue-01",
                    "purpose": "payoff",
                    "coverage": "host_only",
                    "shot_ids": [],
                },
            ],
            "title_treatment": {
                "mode": "integrated_hook",
                "shot_id": "shot-01",
                "screen_text": "Approval gates that stay valid",
            },
            "ending": {
                "mode": "visual_cta",
                "shot_id": "shot-01",
                "screen_text": "Follow Dev Xịn",
            },
        }
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertTrue(result.valid, result.errors)

    def test_editorial_plan_binds_hook_and_spoken_cta_to_approved_script(self) -> None:
        self._prepare_storyboard()
        script_path = self.run_dir / "script" / "final.json"
        script = json.loads(script_path.read_text(encoding="utf-8"))
        script["hook"] = {"segment_id": "segment-01", "end_phrase": "artifact hash."}
        write_json(script_path, script)

        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["editorial_plan"] = {
            "hook_segment_id": "segment-01",
            "hook_beats": [
                {
                    "id": "beat-payoff",
                    "cue_id": "cue-01",
                    "purpose": "payoff",
                    "coverage": "shot",
                    "shot_ids": ["shot-01"],
                }
            ],
            "title_treatment": {
                "mode": "integrated_hook",
                "shot_id": "shot-01",
                "screen_text": "Bind every approval",
            },
            "ending": {
                "mode": "spoken_cta",
                "shot_id": "shot-01",
                "screen_text": "Bind the decision",
                "spoken_phrase": "bind every decision to the artifact hash",
            },
        }
        write_json(storyboard_path, storyboard)

        valid_result = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertTrue(valid_result.valid, valid_result.errors)

        storyboard["editorial_plan"]["ending"].pop("spoken_phrase")
        write_json(storyboard_path, storyboard)
        missing_phrase_result = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertTrue(
            any("spoken_phrase is required for spoken_cta" in error for error in missing_phrase_result.errors),
            missing_phrase_result.errors,
        )

        storyboard["editorial_plan"]["ending"]["spoken_phrase"] = (
            "bind every decision to the artifact hash"
        )
        storyboard["editorial_plan"]["hook_segment_id"] = "segment-missing"
        write_json(storyboard_path, storyboard)
        hook_result = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertTrue(
            any("must match script.hook.segment_id" in error for error in hook_result.errors),
            hook_result.errors,
        )

        storyboard["editorial_plan"]["hook_segment_id"] = "segment-01"
        storyboard["editorial_plan"]["ending"]["spoken_phrase"] = "Follow Dev Xịn"
        write_json(storyboard_path, storyboard)
        phrase_result = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertTrue(
            any("spoken_phrase must occur exactly once" in error for error in phrase_result.errors),
            phrase_result.errors,
        )

        storyboard["editorial_plan"]["ending"]["mode"] = "visual_cta"
        write_json(storyboard_path, storyboard)
        visual_result = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertTrue(
            any("spoken_phrase must be omitted for visual_cta" in error for error in visual_result.errors),
            visual_result.errors,
        )

    def test_storyboard_rejects_malformed_editorial_plan(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["shots"].append(
            {
                "id": "shot-02",
                "segment_id": "segment-01",
                "lane": "support_right",
                "intent": "Hold the final state.",
                "enter": {"cue_id": "cue-01"},
                "renderer": {"kind": "image"},
                "duration_ms": 1000,
            }
        )
        storyboard["editorial_plan"] = {
            "hook_segment_id": "segment-01",
            "hook_beats": [
                {
                    "id": "beat-duplicate",
                    "cue_id": "cue-01",
                    "purpose": "title",
                    "coverage": "shot",
                    "shot_ids": ["shot-missing"],
                },
                {
                    "id": "beat-duplicate",
                    "cue_id": "cue-missing",
                    "purpose": "summary",
                    "coverage": "host_only",
                    "shot_ids": ["shot-01"],
                },
            ],
            "title_treatment": {
                "mode": "lower_third",
                "shot_id": "shot-missing",
                "screen_text": "",
            },
            "ending": {
                "mode": "visual_cta",
                "shot_id": "shot-01",
                "screen_text": "",
            },
        }
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("Duplicate editorial hook beat id" in error for error in result.errors))
        self.assertTrue(any("shot_ids[0] references an unknown shot" in error for error in result.errors))
        self.assertTrue(any("shot_ids must be omitted or empty" in error for error in result.errors))
        self.assertTrue(any("title_treatment.mode must be one of" in error for error in result.errors))
        self.assertTrue(any("ending.shot_id must reference the final" in error for error in result.errors))
        self.assertTrue(any("ending.screen_text is required" in error for error in result.errors))

    def test_storyboard_rejects_implicit_support_top_on_non_vertical_project(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["shots"][0].pop("lane")
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("ratio must be '9:16'" in error for error in result.errors))

    def test_storyboard_rejects_missing_support_top_dimensions(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"]["ratio"] = "9:16"
        storyboard["shots"][0]["lane"] = "support_top"
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("project.width must be 432" in error for error in result.errors))
        self.assertTrue(any("project.height must be 768" in error for error in result.errors))

    def test_storyboard_rejects_wrong_support_top_dimensions(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"].update({"ratio": "9:16", "width": 1080, "height": 1920})
        storyboard["shots"][0]["lane"] = "support_top"
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("project.width must be 432" in error for error in result.errors))
        self.assertTrue(any("project.height must be 768" in error for error in result.errors))

    def test_explicit_segment_support_top_requires_vertical_project_even_when_shot_overrides_it(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["segments"][0]["host_layout"] = "support_top"
        storyboard["shots"][0]["lane"] = "explainer_full"
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("ratio must be '9:16'" in error for error in result.errors))

    def test_explicit_project_support_top_requires_vertical_project_even_when_segment_overrides_it(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"]["default_host_layout"] = "support_top"
        storyboard["segments"][0]["host_layout"] = "support_right"
        storyboard["shots"][0]["lane"] = "explainer_full"
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("ratio must be '9:16'" in error for error in result.errors))

    def test_storyboard_accepts_modern_layout_and_visual_options(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"].update({"ratio": "9:16", "width": 432, "height": 768})
        storyboard["project"]["default_host_layout"] = "host_only"
        storyboard["segments"][0]["host_layout"] = "support_top"
        storyboard["shots"][0].update(
            {
                "lane": "explainer_full",
                "visual_options": [
                    {
                        "id": "option-code",
                        "modality": "code_native",
                        "treatment": "Animate the approval digest locking into place.",
                        "why": "The state change is easier to understand as motion.",
                        "source_plan": "Build a deterministic local HTML component.",
                        "rights_note": "Original code-native visual; no third-party media.",
                    },
                    {
                        "id": "option-static",
                        "modality": "static_graphic",
                        "treatment": "Show a before-and-after approval card.",
                        "why": "Provides a low-motion fallback for the same explanation.",
                        "source_plan": "Create an original SVG in the run directory.",
                        "rights_note": "Original production asset.",
                    },
                ],
                "selected_option_id": "option-code",
            }
        )
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertTrue(result.valid, result.errors)

    def test_storyboard_rejects_invalid_host_layout_and_lane(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"]["default_host_layout"] = "sidebar"
        storyboard["segments"][0]["host_layout"] = "floating"
        storyboard["shots"][0]["lane"] = "host_only"
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("project.default_host_layout" in error for error in result.errors))
        self.assertTrue(any("segments[0].host_layout" in error for error in result.errors))
        self.assertTrue(any("shots[0].lane" in error for error in result.errors))

    def test_storyboard_rejects_empty_and_malformed_visual_options(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["shots"][0]["visual_options"] = []
        storyboard["shots"][0]["selected_option_id"] = "option-code"
        write_json(storyboard_path, storyboard)

        empty_result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(empty_result.valid)
        self.assertTrue(any("visual_options must be a non-empty array" in error for error in empty_result.errors))

        storyboard["shots"][0]["visual_options"] = [
            {},
            {
                "id": "option-code",
                "modality": "unknown",
                "treatment": "",
                "why": "",
                "source_plan": "",
                "rights_note": "",
            },
            {
                "id": "option-code",
                "modality": "code_native",
                "treatment": "Animate the approval digest.",
                "why": "It makes the state transition concrete.",
                "source_plan": "Build original local HTML.",
                "rights_note": "Original production asset.",
            },
        ]
        write_json(storyboard_path, storyboard)

        malformed_result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(malformed_result.valid)
        self.assertTrue(any("visual_options[0].id is required" in error for error in malformed_result.errors))
        self.assertTrue(any("visual_options[1].modality" in error for error in malformed_result.errors))
        self.assertTrue(any("visual_options[1].treatment is required" in error for error in malformed_result.errors))
        self.assertTrue(any("Duplicate visual option id" in error for error in malformed_result.errors))

    def test_storyboard_rejects_unknown_visual_option_selection(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["shots"][0].update(
            {
                "visual_options": [
                    {
                        "id": "option-code",
                        "modality": "code_native",
                        "treatment": "Animate the approval digest.",
                        "why": "It makes the state transition concrete.",
                        "source_plan": "Build original local HTML.",
                        "rights_note": "Original production asset.",
                    }
                ],
                "selected_option_id": "option-missing",
            }
        )
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("selected_option_id references an unknown visual option" in error for error in result.errors))

    def test_storyboard_rejects_host_only_as_selected_shot_option(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["shots"][0].update(
            {
                "visual_options": [
                    {
                        "id": "option-host",
                        "modality": "host_only",
                        "treatment": "Keep the Host on camera without an inserted visual.",
                        "why": "The line depends on direct human delivery.",
                        "source_plan": "Use the recorded Host take.",
                        "rights_note": "Original production footage.",
                    }
                ],
                "selected_option_id": "option-host",
            }
        )
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(
            any("selected_option_id cannot select a host_only visual option" in error for error in result.errors)
        )

    def test_outline_rejects_full_spoken_copy(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        outline_path = self.run_dir / "editorial" / "outline.json"
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
        outline["sections"][0]["voiceover"] = "This full speech belongs in the script stage."
        write_json(outline_path, outline)

        result = workflow.validate_stage(self.run_dir, "outline")
        self.assertFalse(result.valid)
        self.assertTrue(any("not allowed in the structural outline" in error for error in result.errors))

    def test_materialize_script_requires_outline_approval_and_leaves_no_preview(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()

        with self.assertRaises(workflow.GateError):
            self.fixture.script()
        self.assertFalse((self.run_dir / "script" / "teleprompter-script.md").exists())

    def test_materialize_script_rejects_legacy_voiceover_field(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        workflow.approve_stage(self.run_dir, "outline")
        write_json(
            self.run_dir / "script" / "final.json",
            {
                "schema_version": "1.0",
                "title": "Legacy field",
                "segments": [
                    {
                        "id": "segment-01",
                        "heading": "Legacy",
                        "voiceover": "This field must be migrated to text.",
                        "claim_ids": ["claim-001"],
                    }
                ],
            },
        )

        with self.assertRaises(workflow.WorkflowError):
            workflow.materialize_script_teleprompter(self.run_dir)
        self.assertFalse((self.run_dir / "script" / "teleprompter-script.md").exists())

    def test_package_separates_clean_and_producer_scripts(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        workflow.approve_stage(self.run_dir, "outline")
        self.fixture.script()
        workflow.approve_stage(self.run_dir, "script")
        self.fixture.storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"].update({"ratio": "9:16", "width": 432, "height": 768})
        storyboard["project"]["karaoke_caption"] = {"enabled": True}
        write_json(storyboard_path, storyboard)
        workflow.register_stage(self.run_dir, "storyboard")
        workflow.approve_stage(self.run_dir, "storyboard")

        package = workflow.package_creator_pack(self.run_dir, words_per_minute=222)
        review_teleprompter_bytes = (self.run_dir / "script" / "teleprompter-script.md").read_bytes()
        clean_path = self.run_dir / package["outputs"]["teleprompter_clean"]
        teleprompter_path = self.run_dir / package["outputs"]["teleprompter"]
        teleprompter_bytes = teleprompter_path.read_bytes()
        teleprompter = teleprompter_bytes.decode("utf-8")
        producer = (self.run_dir / package["outputs"]["producer_script"]).read_text(encoding="utf-8")
        karaoke = json.loads(
            (self.run_dir / package["outputs"]["karaoke_captions"]).read_text(encoding="utf-8")
        )
        report = json.loads((self.run_dir / package["outputs"]["quality_report"]).read_text(encoding="utf-8"))
        self.assertNotIn("approval digest locking", teleprompter)
        self.assertNotIn("Medium shot", teleprompter)
        self.assertEqual(review_teleprompter_bytes, clean_path.read_bytes())
        self.assertNotEqual(review_teleprompter_bytes, teleprompter_bytes)
        self.assertIn("## Cảnh 01", teleprompter)
        self.assertEqual(teleprompter.count("[BẤM NEXT →]"), 1)
        self.assertEqual(karaoke["scene_count"], 2)
        self.assertEqual(karaoke["reading_wpm"], 150)
        self.assertEqual(karaoke["scenes"][0]["advance_indicator"], "NEXT →")
        self.assertIsNone(karaoke["scenes"][-1]["advance_indicator"])
        self.assertTrue(karaoke["scenes"][0]["host_only"])
        self.assertEqual(
            "".join(scene["text"] for scene in karaoke["scenes"]),
            "A quiet edit can invalidate yesterday's approval, so bind every decision to the artifact hash.",
        )
        self.assertIn("approval digest locking", producer)
        self.assertIn("Medium shot", producer)
        self.assertTrue(report["passed"])
        self.assertTrue(report["spoken_projection"]["exact_match"])
        self.assertTrue(report["spoken_projection"]["normalized_match"])
        for name, digest in report["output_hashes"].items():
            self.assertEqual(workflow.sha256_file(self.run_dir / package["outputs"][name]), digest)

    def test_scene_projection_covers_sixteen_ordered_shots_exactly(self) -> None:
        phrases = [f"Mốc-{index:02d}" for index in range(1, 17)]
        text = " ".join(f"{phrase} trình bày ý số {index}." for index, phrase in enumerate(phrases, 1))
        script = {
            "title": "Mười sáu cảnh",
            "segments": [{"id": "segment-01", "text": text}],
        }
        storyboard = {
            "segments": [
                {
                    "id": "segment-01",
                    "text": text,
                    "cues": [
                        {"id": f"cue-{index:02d}", "phrase": phrase}
                        for index, phrase in enumerate(phrases, 1)
                    ],
                }
            ],
            "shots": [
                {
                    "id": f"shot-{index:02d}",
                    "segment_id": "segment-01",
                    "enter": {"cue_id": f"cue-{index:02d}"},
                }
                for index in range(1, 17)
            ],
        }

        canonical, scenes = workflow._build_scene_projection(script, storyboard)
        recording = workflow._render_recording_teleprompter(
            script, scenes, end_indicator="NEXT →"
        )

        self.assertEqual(len(scenes), 16)
        self.assertEqual([scene["shot_id"] for scene in scenes], [f"shot-{i:02d}" for i in range(1, 17)])
        self.assertEqual(
            "".join(scene["text"] for scene in scenes),
            canonical,
        )
        self.assertEqual(recording.count("## Cảnh "), 16)
        self.assertEqual(recording.count("[BẤM NEXT →]"), 15)
        config = workflow._karaoke_configuration(
            {
                "project": {
                    "width": 432,
                    "height": 768,
                    "karaoke_caption": {"enabled": True},
                }
            },
            fallback_wpm=999,
        )
        captions = workflow._build_karaoke_captions(scenes, config)
        self.assertTrue(all(scene["advance_indicator"] == "NEXT →" for scene in captions["scenes"][:-1]))
        self.assertIsNone(captions["scenes"][-1]["advance_indicator"])
        self.assertEqual(captions["scenes"][1]["chunks"][0]["words"][0]["start_ms"], 0)

    def test_karaoke_timings_include_punctuation_and_scene_end_pauses(self) -> None:
        scenes = [
            {
                "scene_id": "scene-01",
                "scene_number": 1,
                "shot_id": "shot-01",
                "segment_id": "segment-01",
                "enter_cue_id": "cue-01",
                "text": "Một, hai: ba; bốn. Năm?",
            }
        ]
        config = workflow._karaoke_configuration(
            {
                "project": {
                    "width": 432,
                    "height": 768,
                    "karaoke_caption": {"enabled": True},
                }
            },
            fallback_wpm=150,
        )

        captions = workflow._build_karaoke_captions(scenes, config)
        words = [word for chunk in captions["scenes"][0]["chunks"] for word in chunk["words"]]

        self.assertEqual(captions["word_duration_ms"], 400)
        self.assertEqual([word["punctuation_pause_ms"] for word in words], [250, 400, 400, 650, 650])
        self.assertEqual([word["scene_end_pause_ms"] for word in words], [0, 0, 0, 0, 900])
        self.assertEqual(captions["total_estimated_ms"], 5250)
        self.assertEqual([chunk["text"] for chunk in captions["scenes"][0]["chunks"]], [
            "Một,", "hai:", "ba;", "bốn.", "Năm?"
        ])
        self.assertEqual([word["text"] for word in words], ["Một,", "hai:", "ba;", "bốn.", "Năm?"])

        decimal_scene = [{**scenes[0], "text": "Giá trị 3.14 và 3,14 vẫn là hai số."}]
        decimal_captions = workflow._build_karaoke_captions(decimal_scene, config)
        decimal_words = [
            word for chunk in decimal_captions["scenes"][0]["chunks"] for word in chunk["words"]
        ]
        decimal_by_text = {word["text"]: word for word in decimal_words}
        self.assertEqual(decimal_by_text["3.14"]["punctuation_pause_ms"], 0)
        self.assertEqual(decimal_by_text["3,14"]["punctuation_pause_ms"], 0)

    def test_karaoke_project_configuration_overrides_timing_defaults(self) -> None:
        config = workflow._karaoke_configuration(
            {
                "project": {
                    "width": 432,
                    "height": 768,
                    "karaoke_caption": {
                        "enabled": True,
                        "placement": "capture_stage_bottom",
                        "bottom_margin_px": 72,
                        "max_lines": 1,
                        "reading_wpm": 120,
                        "pause_ms": {
                            "comma": 110,
                            "clause": 220,
                            "sentence": 330,
                            "scene_end": 440,
                        },
                        "scene_advance": "manual",
                        "end_indicator": "TIẾP →",
                    }
                }
            },
            fallback_wpm=150,
        )
        scenes = [
            {
                "scene_id": "scene-01",
                "scene_number": 1,
                "shot_id": "shot-01",
                "segment_id": "segment-01",
                "enter_cue_id": "cue-01",
                "text": "Một, hai.",
            }
        ]

        captions = workflow._build_karaoke_captions(scenes, config)

        self.assertEqual(captions["bottom_margin_px"], 72)
        self.assertEqual(captions["max_lines"], 1)
        self.assertEqual(captions["reading_wpm"], 120)
        self.assertEqual(captions["word_duration_ms"], 500)
        self.assertEqual(captions["pause_ms"], {
            "comma": 110, "clause": 220, "sentence": 330, "scene_end": 440
        })
        self.assertEqual(captions["end_indicator"], "TIẾP →")
        self.assertEqual(captions["total_estimated_ms"], 1880)

    def test_karaoke_config_is_strict_and_default_wpm_does_not_follow_package_wpm(self) -> None:
        defaulted = workflow._karaoke_configuration({"project": {}}, fallback_wpm=777)
        self.assertFalse(defaulted["enabled"])
        self.assertEqual(defaulted["reading_wpm"], 150)

        invalid_cases = [
            ({"project": {"karaoke_caption": None}}, "must be an object when present"),
            (
                {"project": {"karaoke_caption": {"enabled": False, "typo": 1}}},
                "has unknown field: typo",
            ),
            (
                {"project": {"karaoke_caption": {"enabled": False, "pause_ms": {"typo": 1}}}},
                "pause_ms has unknown field: typo",
            ),
            (
                {"project": {"height": 768, "karaoke_caption": {"enabled": False, "bottom_margin_px": 768}}},
                "bottom_margin_px must be an integer from 0 to 767",
            ),
            (
                {"project": {"karaoke_caption": {"enabled": False, "max_lines": 3}}},
                "max_lines must be 1 or 2",
            ),
            (
                {"project": {"karaoke_caption": {"enabled": False, "reading_wpm": 59}}},
                "reading_wpm must be an integer from 60 to 1000",
            ),
            (
                {"project": {"karaoke_caption": {"enabled": False, "pause_ms": {"comma": 10001}}}},
                "pause_ms.comma must be an integer from 0 to 10000",
            ),
            (
                {"project": {"karaoke_caption": {"enabled": False, "end_indicator": "[NEXT]"}}},
                "end_indicator must be a single-line string",
            ),
            (
                {"project": {"width": 431, "height": 768, "karaoke_caption": {"enabled": True}}},
                "enabled=true requires the 432 x 768",
            ),
        ]
        for storyboard, message in invalid_cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(workflow.WorkflowError, message):
                    workflow._karaoke_configuration(storyboard, fallback_wpm=150)

        rounded_config = workflow._karaoke_configuration(
            {
                "project": {
                    "width": 432,
                    "height": 768,
                    "karaoke_caption": {"enabled": True, "reading_wpm": 192},
                }
            },
            fallback_wpm=150,
        )
        rounded = workflow._build_karaoke_captions(
            [
                {
                    "scene_id": "scene-01",
                    "scene_number": 1,
                    "shot_id": "shot-01",
                    "segment_id": "segment-01",
                    "enter_cue_id": "cue-01",
                    "text": "Một.",
                }
            ],
            rounded_config,
        )
        self.assertEqual(rounded["word_duration_ms"], 313)

    def test_storyboard_rejects_invalid_karaoke_caption_configuration(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"]["karaoke_caption"] = {
            "enabled": True,
            "reading_wpm": 0,
        }
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("karaoke_caption.reading_wpm must be an integer from 60 to 1000" in error for error in result.errors))

    def test_manual_scene_navigation_rejects_mid_sentence_next_boundaries(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["project"]["scene_navigation"] = {
            "mode": "manual",
            "boundary_policy": "sentence_start",
            "intra_sentence_changes": "component_state",
        }
        storyboard["segments"][0]["cues"][0]["phrase"] = "A quiet edit"
        storyboard["shots"][0]["enter"] = {"cue_id": "cue-01", "offset_ms": 0}
        write_json(storyboard_path, storyboard)

        valid = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertTrue(valid.valid, valid.errors)
        self.assertEqual(valid.metrics["scene_navigation"]["boundary_policy"], "sentence_start")

        storyboard["segments"][0]["cues"][0]["phrase"] = "artifact hash"
        write_json(storyboard_path, storyboard)
        invalid = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertFalse(invalid.valid)
        self.assertTrue(
            any("manual Next boundaries must start a complete sentence" in error for error in invalid.errors)
        )

        storyboard["segments"][0]["cues"][0]["phrase"] = "A quiet edit"
        storyboard["shots"][0]["enter"]["offset_ms"] = 100
        write_json(storyboard_path, storyboard)
        offset = workflow.validate_stage(self.run_dir, "storyboard")
        self.assertFalse(offset.valid)
        self.assertTrue(any("enter.offset_ms must be 0" in error for error in offset.errors))

    def test_scene_navigation_contract_is_strict_and_sentence_detection_handles_quotes(self) -> None:
        config = workflow._scene_navigation_configuration(
            {"project": {"scene_navigation": {}}}
        )
        self.assertEqual(config, workflow.DEFAULT_SCENE_NAVIGATION)
        self.assertTrue(workflow._is_sentence_start("Câu một. Câu hai.", 0))
        self.assertTrue(
            workflow._is_sentence_start("Câu một.” Câu hai.", len("Câu một.” "))
        )
        self.assertFalse(
            workflow._is_sentence_start("Câu một, rồi tiếp tục.", len("Câu một, "))
        )
        with self.assertRaisesRegex(workflow.WorkflowError, "unknown field: typo"):
            workflow._scene_navigation_configuration(
                {"project": {"scene_navigation": {"typo": True}}}
            )

    def test_storyboard_renderer_variant_must_be_a_safe_token(self) -> None:
        self._prepare_storyboard()
        storyboard_path = self.run_dir / "storyboard" / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        storyboard["shots"][0]["renderer"]["variant"] = "not safe"
        write_json(storyboard_path, storyboard)

        result = workflow.validate_stage(self.run_dir, "storyboard")

        self.assertFalse(result.valid)
        self.assertTrue(any("renderer.variant must be a safe token" in error for error in result.errors))

    def test_scene_projection_groups_coincident_shots_and_rejects_reordered_anchors(self) -> None:
        text = "Mốc đầu. Mốc giữa. Mốc cuối."
        script = {"title": "Drift", "segments": [{"id": "segment-01", "text": text}]}
        segment = {
            "id": "segment-01",
            "text": text,
            "cues": [
                {"id": "cue-first", "phrase": "Mốc đầu"},
                {"id": "cue-middle", "phrase": "Mốc giữa"},
                {"id": "cue-last", "phrase": "Mốc cuối"},
            ],
        }
        storyboard = {
            "segments": [segment],
            "shots": [
                {"id": "shot-last", "segment_id": "segment-01", "enter": {"cue_id": "cue-last"}},
                {"id": "shot-first", "segment_id": "segment-01", "enter": {"cue_id": "cue-first"}},
            ],
        }

        with self.assertRaisesRegex(workflow.WorkflowError, "non-decreasing anchors"):
            workflow._build_scene_projection(script, storyboard)

        storyboard["shots"] = [
            {"id": "shot-a", "segment_id": "segment-01", "enter": {"cue_id": "cue-middle"}},
            {"id": "shot-b", "segment_id": "segment-01", "enter": {"cue_id": "cue-middle"}},
        ]
        canonical, scenes = workflow._build_scene_projection(script, storyboard)
        self.assertEqual(len(scenes), 2)
        self.assertTrue(scenes[0]["host_only"])
        self.assertEqual(scenes[0]["scene_id"], "scene-01-host-only")
        self.assertEqual(scenes[0]["shot_ids"], [])
        self.assertEqual(scenes[1]["shot_id"], "shot-a")
        self.assertEqual(scenes[1]["shot_ids"], ["shot-a", "shot-b"])
        self.assertEqual("".join(scene["text"] for scene in scenes), canonical)
        self.assertTrue(scenes[0]["text"].endswith(" "))

    def test_scene_projection_without_shots_is_one_exact_host_only_scene(self) -> None:
        text = "Host tự dẫn toàn bộ phần này. Không cần bấm chuyển cảnh."
        script = {"title": "Host-only", "segments": [{"id": "segment-01", "text": text}]}
        storyboard = {
            "segments": [{"id": "segment-01", "text": text, "cues": []}],
            "shots": [],
        }

        canonical, scenes = workflow._build_scene_projection(script, storyboard)
        recording = workflow._render_recording_teleprompter(
            script, scenes, end_indicator="NEXT →"
        )

        self.assertEqual(canonical, text)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["scene_id"], "scene-01-host-only")
        self.assertEqual(scenes[0]["kind"], "host_only")
        self.assertIsNone(scenes[0]["shot_id"])
        self.assertEqual(scenes[0]["shot_ids"], [])
        self.assertEqual(scenes[0]["text"], canonical)
        self.assertIn("## Cảnh 01 — HOST-ONLY", recording)
        self.assertNotIn("[BẤM NEXT →]", recording)

    def test_package_keeps_karaoke_disabled_when_project_config_is_absent(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        workflow.approve_stage(self.run_dir, "outline")
        self.fixture.script()
        workflow.approve_stage(self.run_dir, "script")
        self.fixture.storyboard()
        workflow.approve_stage(self.run_dir, "storyboard")

        package = workflow.package_creator_pack(self.run_dir, words_per_minute=222)

        self.assertNotIn("karaoke_captions", package["outputs"])
        self.assertFalse((self.run_dir / "creator-pack" / "karaoke_captions.json").exists())
        self.assertTrue((self.run_dir / package["outputs"]["teleprompter_clean"]).is_file())
        recording = (self.run_dir / package["outputs"]["teleprompter"]).read_text(encoding="utf-8")
        self.assertIn("## Cảnh 01", recording)
        self.assertFalse(package["quality_report"]["karaoke_caption"]["enabled"])
        self.assertEqual(
            package["quality_report"]["karaoke_caption"]["configuration"]["reading_wpm"],
            150,
        )

    def test_producer_script_keeps_visual_cues_without_optional_notes(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        workflow.approve_stage(self.run_dir, "outline")
        self.fixture.script()
        script_path = self.run_dir / "script" / "final.json"
        script = json.loads(script_path.read_text(encoding="utf-8"))
        script["segments"][0].pop("producer_notes")
        write_json(script_path, script)
        workflow.materialize_script_teleprompter(self.run_dir)
        workflow.register_stage(self.run_dir, "script")
        workflow.approve_stage(self.run_dir, "script")
        self.fixture.storyboard()
        workflow.approve_stage(self.run_dir, "storyboard")

        package = workflow.package_creator_pack(self.run_dir)
        producer = (self.run_dir / package["outputs"]["producer_script"]).read_text(encoding="utf-8")
        self.assertIn("approval digest locking", producer)

    def test_script_gate_exposes_clean_teleprompter_and_rejects_drift(self) -> None:
        self.fixture.research()
        self.fixture.scope()
        workflow.approve_stage(self.run_dir, "scope")
        self.fixture.outline()
        workflow.approve_stage(self.run_dir, "outline")
        self.fixture.script()

        teleprompter_path = self.run_dir / "script" / "teleprompter-script.md"
        teleprompter_bytes = teleprompter_path.read_bytes()
        teleprompter = teleprompter_bytes.decode("utf-8")
        self.assertEqual(
            (
                "# Approval gates\n\n"
                "A quiet edit can invalidate yesterday's approval, so bind every decision to the artifact hash.\n"
            ).encode("utf-8"),
            teleprompter_bytes,
        )
        self.assertEqual(workflow.build_status(self.run_dir)["next_action"], "approve:script")
        workflow.approve_stage(self.run_dir, "script")

        teleprompter_path.write_bytes(teleprompter.replace("\n", "\r\n").encode("utf-8"))
        info = workflow.inspect_stage(self.run_dir, "script")
        self.assertEqual(info["state"], "modified")
        self.assertEqual(info["approval_status"], "stale")
        result = workflow.validate_stage(self.run_dir, "script")
        self.assertFalse(result.valid)
        self.assertTrue(any("differs from the spoken text" in error for error in result.errors))

    def test_cli_rejects_unknown_arguments(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "workflow.py"),
                "status",
                "--run-dir",
                str(self.run_dir),
                "--typo-flag",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("unrecognized arguments", completed.stderr)


if __name__ == "__main__":
    unittest.main()
