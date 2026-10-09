#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""State, approval gates, validation, and packaging for a Human Host run.

This module deliberately uses only the Python standard library.  Every command
requires an explicit run directory, so the skill can be copied outside of the
repository without changing path assumptions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


MANIFEST_VERSION = 1
SCHEMA_VERSION = "1.0"
MANIFEST_NAME = "run_manifest.json"
STAGES = ("research", "scope", "outline", "script", "storyboard")
APPROVAL_STAGES = ("scope", "outline", "script", "storyboard")
PREDECESSOR = {
    "research": None,
    "scope": "research",
    "outline": "scope",
    "script": "outline",
    "storyboard": "script",
}
CANONICAL_ARTIFACTS: dict[str, dict[str, str]] = {
    "research": {
        "transcript": "research/full_transcript.md",
        "analysis": "research/source_analysis.json",
        "playbook": "research/source_playbook.md",
        "claims": "research/claim_ledger.json",
    },
    "scope": {"scope": "editorial/scope_proposal.json"},
    "outline": {"outline": "editorial/outline.json"},
    "script": {
        "script": "script/final.json",
        "teleprompter": "script/teleprompter-script.md",
    },
    "storyboard": {"storyboard": "storyboard/storyboard.json"},
}

TIMESTAMP_RE = re.compile(r"\[(?:\d{1,2}:)?\d{1,2}:\d{2}\]")
ARTICLE_LOCATOR_RE = re.compile(r"\[(?:section|paragraph|para|p)\s*[:#]\s*[^\]]+\]", re.IGNORECASE)
WORD_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HOST_LAYOUTS = frozenset({"host_only", "support_top", "support_right", "explainer_full"})
SHOT_LANES = frozenset({"support_top", "support_right", "explainer_full"})
SUPPORT_TOP_RATIO = "9:16"
SUPPORT_TOP_WIDTH = 432
SUPPORT_TOP_HEIGHT = 768
VISUAL_OPTION_MODALITIES = frozenset(
    {
        "host_only",
        "code_native",
        "licensed_video",
        "screen_recording",
        "web_screenshot",
        "repo_screenshot",
        "web_image",
        "static_graphic",
    }
)
EDITORIAL_HOOK_PURPOSES = frozenset(
    {"title", "pain", "consequence", "reversal", "promise", "payoff", "roadmap"}
)
EDITORIAL_HOOK_COVERAGE = frozenset({"shot", "host_only"})
EDITORIAL_TITLE_MODES = frozenset({"dedicated_scene", "integrated_hook"})
EDITORIAL_ENDING_MODES = frozenset({"visual_cta", "spoken_cta", "host_only", "none"})
DEFAULT_KARAOKE_CAPTION: dict[str, Any] = {
    "enabled": False,
    "placement": "capture_stage_bottom",
    "bottom_margin_px": 100,
    "max_lines": 2,
    "reading_wpm": 150,
    "pause_ms": {
        "comma": 250,
        "clause": 400,
        "sentence": 650,
        "scene_end": 900,
    },
    "scene_advance": "manual",
    "end_indicator": "NEXT →",
}
KARAOKE_CONFIG_KEYS = frozenset(
    {
        "enabled",
        "placement",
        "bottom_margin_px",
        "max_lines",
        "reading_wpm",
        "pause_ms",
        "scene_advance",
        "end_indicator",
    }
)
KARAOKE_PAUSE_KEYS = frozenset({"comma", "clause", "sentence", "scene_end"})
SCENE_NAVIGATION_KEYS = frozenset({"mode", "boundary_policy", "intra_sentence_changes"})
DEFAULT_SCENE_NAVIGATION: dict[str, str] = {
    "mode": "manual",
    "boundary_policy": "sentence_start",
    "intra_sentence_changes": "component_state",
}


class WorkflowError(RuntimeError):
    """A user-correctable workflow error."""


class GateError(WorkflowError):
    """A stage was attempted before its approval gate was satisfied."""


class ArtifactValidationError(WorkflowError):
    """Artifacts did not meet the canonical contract."""

    def __init__(self, stage: str, errors: Sequence[str]):
        self.stage = stage
        self.errors = list(errors)
        super().__init__(f"Stage '{stage}' is invalid: " + "; ".join(self.errors))


@dataclass
class ValidationResult:
    stage: str
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def error(self, message: str) -> None:
        self.errors.append(message)
        self.valid = False

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    tmp_name = ""
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        )
        tmp_name = handle.name
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None
        os.replace(tmp_name, path)
    finally:
        if handle is not None:
            handle.close()
        if tmp_name:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass


def atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def manifest_path(run_dir: Path | str) -> Path:
    return Path(run_dir).expanduser().resolve() / MANIFEST_NAME


def canonical_paths(run_dir: Path | str, stage: str) -> dict[str, Path]:
    _require_stage(stage)
    root = Path(run_dir).expanduser().resolve()
    return {name: root / rel for name, rel in CANONICAL_ARTIFACTS[stage].items()}


def _require_stage(stage: str) -> None:
    if stage not in STAGES:
        raise WorkflowError(f"Unknown stage '{stage}'. Expected one of: {', '.join(STAGES)}")


def init_run(
    run_dir: Path | str,
    *,
    source_url: str | None = None,
    configuration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / MANIFEST_NAME
    requested_config = dict(configuration or {})
    if path.exists():
        manifest = load_manifest(root)
        existing_url = manifest.get("source", {}).get("url")
        if source_url and existing_url and source_url != existing_url:
            raise WorkflowError(
                f"Run already belongs to a different source URL: {existing_url!r} (requested {source_url!r})"
            )
        existing_config = manifest.get("configuration", {})
        if requested_config and existing_config and requested_config != existing_config:
            raise WorkflowError("Run already exists with a different configuration")
        changed = False
        if source_url and not existing_url:
            manifest.setdefault("source", {})["url"] = source_url
            changed = True
        if requested_config and not existing_config:
            manifest["configuration"] = requested_config
            changed = True
        if changed:
            save_manifest(root, manifest)
        return manifest

    now = utc_now()
    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "run_id": root.name,
        "created_at": now,
        "updated_at": now,
        "source": {"url": source_url} if source_url else {},
        "configuration": requested_config,
        "stages": {},
        "approvals": {},
    }
    atomic_write_json(path, manifest)
    return manifest


def load_manifest(run_dir: Path | str) -> dict[str, Any]:
    path = manifest_path(run_dir)
    manifest = read_json(path)
    if not isinstance(manifest, dict):
        raise WorkflowError(f"Manifest must be a JSON object: {path}")
    version = manifest.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise WorkflowError(
            f"Unsupported manifest_version {version!r}; this workflow supports {MANIFEST_VERSION}"
        )
    return manifest


def save_manifest(run_dir: Path | str, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = utc_now()
    atomic_write_json(manifest_path(run_dir), manifest)


def artifact_snapshot(run_dir: Path | str, stage: str) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    files: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for name, rel in CANONICAL_ARTIFACTS[stage].items():
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        files[name] = {
            "path": rel,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    aggregate = None
    if not missing:
        aggregate = sha256_json({name: entry["sha256"] for name, entry in sorted(files.items())})
    return {"files": files, "missing": missing, "artifact_sha256": aggregate}


def _load_json_object(path: Path, result: ValidationResult) -> dict[str, Any] | None:
    if not path.is_file():
        result.error(f"Missing canonical artifact: {path.name}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.error(f"{path.name} is invalid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        result.error(f"{path.name} must contain a JSON object")
        return None
    return data


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _list_of_strings(value: Any) -> bool:
    return isinstance(value, list) and all(_nonempty_string(item) for item in value)


def _read_json_mapping(path: Path) -> dict[str, Any] | None:
    """Read an optional JSON object without adding validation side effects."""
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _scope_audience_profile(run_dir: Path) -> dict[str, Any] | None:
    data = _read_json_mapping(run_dir / CANONICAL_ARTIFACTS["scope"]["scope"])
    if not isinstance(data, dict):
        return None
    value = data.get("audience_profile")
    return value if isinstance(value, dict) else None


def _uses_audience_contract(run_dir: Path) -> bool:
    """Enable the additive contract only when a scope explicitly opts into it."""
    data = _read_json_mapping(run_dir / CANONICAL_ARTIFACTS["scope"]["scope"])
    return isinstance(data, dict) and "audience_profile" in data


def _outline_hook_brief(run_dir: Path) -> dict[str, Any] | None:
    data = _read_json_mapping(run_dir / CANONICAL_ARTIFACTS["outline"]["outline"])
    if not isinstance(data, dict):
        return None
    value = data.get("hook_brief")
    return value if isinstance(value, dict) else None


def _uses_hook_contract(run_dir: Path) -> bool:
    data = _read_json_mapping(run_dir / CANONICAL_ARTIFACTS["outline"]["outline"])
    return isinstance(data, dict) and "hook_brief" in data


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _phrase_matches(text: str, phrase: str) -> list[re.Match[str]]:
    candidate = phrase.strip()
    if not candidate:
        return []
    pattern = re.compile(rf"(?<!\w){re.escape(candidate)}(?!\w)", flags=re.IGNORECASE)
    return list(pattern.finditer(text))


def _contains_term(text: str, term: str) -> bool:
    """Match an explicit audience-blocked term without matching inside another word."""
    candidate = term.strip()
    if not candidate:
        return False
    pattern = re.compile(rf"(?<!\w){re.escape(candidate)}(?!\w)", flags=re.IGNORECASE)
    return pattern.search(text) is not None


def _claim_ids(run_dir: Path) -> set[str]:
    path = run_dir / CANONICAL_ARTIFACTS["research"]["claims"]
    if not path.is_file():
        return set()
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    claims = ledger.get("claims", []) if isinstance(ledger, dict) else []
    return {str(item.get("id")) for item in claims if isinstance(item, dict) and item.get("id")}


def _must_keep_claim_ids(run_dir: Path) -> set[str]:
    path = run_dir / CANONICAL_ARTIFACTS["research"]["claims"]
    if not path.is_file():
        return set()
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    claims = ledger.get("claims", []) if isinstance(ledger, dict) else []
    return {
        str(item.get("id"))
        for item in claims
        if isinstance(item, dict) and item.get("id") and item.get("must_keep") is True
    }


def _scope_knowledge_unit_ids(run_dir: Path) -> set[str]:
    path = run_dir / CANONICAL_ARTIFACTS["scope"]["scope"]
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    units = data.get("knowledge_units", []) if isinstance(data, dict) else []
    return {str(item.get("id")) for item in units if isinstance(item, dict) and item.get("id")}


def _outline_section_ids(run_dir: Path) -> list[str]:
    path = run_dir / CANONICAL_ARTIFACTS["outline"]["outline"]
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    sections = data.get("sections", []) if isinstance(data, dict) else []
    return [str(item.get("id")) for item in sections if isinstance(item, dict) and item.get("id")]


def _scope_claim_ids(run_dir: Path) -> set[str]:
    path = run_dir / CANONICAL_ARTIFACTS["scope"]["scope"]
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    values = data.get("included_claim_ids", []) if isinstance(data, dict) else []
    return {str(item) for item in values if _nonempty_string(item)}


def _read_budget(data: Mapping[str, Any]) -> tuple[int | None, int | None, int | None]:
    budget = data.get("word_budget")
    if isinstance(budget, int):
        return budget, budget, budget
    if not isinstance(budget, dict):
        return None, None, None
    low = budget.get("min")
    high = budget.get("max")
    target = budget.get("target")
    return (
        low if isinstance(low, int) and not isinstance(low, bool) else None,
        high if isinstance(high, int) and not isinstance(high, bool) else None,
        target if isinstance(target, int) and not isinstance(target, bool) else None,
    )


def _validate_budget(data: Mapping[str, Any], result: ValidationResult) -> None:
    low, high, target = _read_budget(data)
    if "word_budget" in data and low is None and high is None and target is None:
        result.error("word_budget must be an integer or an object with integer min/max/target")
        return
    for label, value in (("min", low), ("max", high), ("target", target)):
        if value is not None and value <= 0:
            result.error(f"word_budget.{label} must be positive")
    if low is not None and high is not None and low > high:
        result.error("word_budget.min cannot exceed word_budget.max")
    if target is not None and low is not None and target < low:
        result.error("word_budget.target cannot be below min")
    if target is not None and high is not None and target > high:
        result.error("word_budget.target cannot exceed max")


def validate_research(run_dir: Path) -> ValidationResult:
    result = ValidationResult("research")
    paths = canonical_paths(run_dir, "research")
    transcript_path = paths["transcript"]
    if not transcript_path.is_file():
        result.error("Missing canonical artifact: full_transcript.md")
    else:
        transcript = transcript_path.read_text(encoding="utf-8").strip()
        if not transcript:
            result.error("Transcript is empty")
        elif not (TIMESTAMP_RE.search(transcript) or ARTICLE_LOCATOR_RE.search(transcript)):
            result.error(
                "Source text needs stable anchors such as [00:15] for video or [section: Heading] for an article"
            )
        result.metrics["transcript_words"] = count_words(transcript)

    analysis = _load_json_object(paths["analysis"], result)
    if analysis is not None:
        if analysis.get("schema_version") != SCHEMA_VERSION:
            result.error(f"source_analysis.schema_version must be {SCHEMA_VERSION!r}")
        for key in ("topic", "core_thesis", "audience"):
            if not _nonempty_string(analysis.get(key)):
                result.error(f"source_analysis.{key} is required")
        source = analysis.get("source")
        if not isinstance(source, dict):
            result.error("source_analysis.source must be an object")
        else:
            for key in ("title", "kind", "locator", "language"):
                if not _nonempty_string(source.get(key)):
                    result.error(f"source_analysis.source.{key} is required")
        hook = analysis.get("hook")
        if not isinstance(hook, dict):
            result.error("source_analysis.hook must be an object")
        else:
            if not _nonempty_string(hook.get("type")):
                result.error("source_analysis.hook.type is required")
            if not (_nonempty_string(hook.get("timestamp")) or _nonempty_string(hook.get("source_locator"))):
                result.error("source_analysis.hook needs timestamp or source_locator")
            if not (_nonempty_string(hook.get("why_it_works")) or _nonempty_string(hook.get("mechanism"))):
                result.error("source_analysis.hook needs why_it_works or mechanism")
            if not _nonempty_string(hook.get("reusable_pattern")):
                result.error("source_analysis.hook.reusable_pattern is required")
        flow = analysis.get("flow")
        if not isinstance(flow, list) or not flow:
            result.error("source_analysis.flow must be a non-empty array")
        else:
            flow_ids: set[str] = set()
            for index, beat in enumerate(flow):
                prefix = f"source_analysis.flow[{index}]"
                if not isinstance(beat, dict):
                    result.error(f"{prefix} must be an object")
                    continue
                beat_id = beat.get("id")
                if not _nonempty_string(beat_id):
                    result.error(f"{prefix}.id is required")
                elif beat_id in flow_ids:
                    result.error(f"Duplicate source flow id: {beat_id}")
                else:
                    flow_ids.add(str(beat_id))
                for key in ("purpose", "technique", "key_claim"):
                    if not _nonempty_string(beat.get(key)):
                        result.error(f"{prefix}.{key} is required")
                if not (
                    _nonempty_string(beat.get("source_locator"))
                    or _nonempty_string(beat.get("t_start"))
                ):
                    result.error(f"{prefix} needs source_locator or t_start")
        if not isinstance(analysis.get("key_facts"), list):
            result.error("source_analysis.key_facts must be an array")

    playbook_path = paths["playbook"]
    if not playbook_path.is_file() or not playbook_path.read_text(encoding="utf-8").strip():
        result.error("source_playbook.md is missing or empty")

    ledger = _load_json_object(paths["claims"], result)
    if ledger is not None:
        if ledger.get("schema_version") != SCHEMA_VERSION:
            result.error(f"claim_ledger.schema_version must be {SCHEMA_VERSION!r}")
        claims = ledger.get("claims")
        if not isinstance(claims, list):
            result.error("claim_ledger.claims must be an array")
        else:
            ids: set[str] = set()
            for index, claim in enumerate(claims):
                prefix = f"claim_ledger.claims[{index}]"
                if not isinstance(claim, dict):
                    result.error(f"{prefix} must be an object")
                    continue
                claim_id = claim.get("id")
                if not _nonempty_string(claim_id):
                    result.error(f"{prefix}.id is required")
                elif claim_id in ids:
                    result.error(f"Duplicate claim id: {claim_id}")
                else:
                    ids.add(claim_id)
                if not _nonempty_string(claim.get("text")):
                    result.error(f"{prefix}.text is required")
                if claim.get("kind") not in {
                    "source_claim",
                    "independently_verified",
                    "creator_interpretation",
                    "open_uncertainty",
                }:
                    result.error(f"{prefix}.kind is invalid")
                if claim.get("verification_status") not in {
                    "supported",
                    "disputed",
                    "unverified",
                    "not_applicable",
                }:
                    result.error(f"{prefix}.verification_status is invalid")
                if claim.get("confidence") not in {"high", "medium", "low"}:
                    result.error(f"{prefix}.confidence is invalid")
                if not isinstance(claim.get("must_keep"), bool):
                    result.error(f"{prefix}.must_keep must be a boolean")
                if not _nonempty_string(claim.get("usage_note")):
                    result.error(f"{prefix}.usage_note is required")
                evidence = claim.get("evidence")
                if not isinstance(evidence, list) or not evidence:
                    result.error(f"{prefix}.evidence must be a non-empty array")
                elif not any(
                    isinstance(item, dict)
                    and (_nonempty_string(item.get("timestamp")) or _nonempty_string(item.get("detail")))
                    for item in evidence
                ):
                    result.error(f"{prefix}.evidence needs a timestamp or detail")
            result.metrics["claim_count"] = len(claims)
    return result


def validate_scope(run_dir: Path) -> ValidationResult:
    result = ValidationResult("scope")
    data = _load_json_object(canonical_paths(run_dir, "scope")["scope"], result)
    if data is None:
        return result
    if data.get("schema_version") != SCHEMA_VERSION:
        result.error(f"scope.schema_version must be {SCHEMA_VERSION!r}")
    mode = data.get("format")
    if mode not in {"single_video", "series"}:
        result.error("scope.format must be 'single_video' or 'series'")
    if not _nonempty_string(data.get("title")):
        result.error("scope.title is required")
    if not _nonempty_string(data.get("thesis")):
        result.error("scope.thesis is required")
    for key in ("audience", "creator_goal", "viewer_promise", "rationale"):
        if not _nonempty_string(data.get(key)):
            result.error(f"scope.{key} is required")
    if "audience_profile" in data:
        profile = data.get("audience_profile")
        if not isinstance(profile, dict):
            result.error("scope.audience_profile must be an object")
        else:
            group_ids: set[str] = set()
            for collection_name, required in (("primary_groups", True), ("secondary_groups", False)):
                groups = profile.get(collection_name)
                if not isinstance(groups, list) or (required and not groups):
                    qualifier = "a non-empty array" if required else "an array"
                    result.error(f"scope.audience_profile.{collection_name} must be {qualifier}")
                    groups = []
                for index, group in enumerate(groups):
                    prefix = f"scope.audience_profile.{collection_name}[{index}]"
                    if not isinstance(group, dict):
                        result.error(f"{prefix} must be an object")
                        continue
                    group_id = group.get("id")
                    if not _nonempty_string(group_id):
                        result.error(f"{prefix}.id is required")
                    elif str(group_id) in group_ids:
                        result.error(f"Duplicate audience group id: {group_id}")
                    else:
                        group_ids.add(str(group_id))
                    for key in ("label", "need"):
                        if not _nonempty_string(group.get(key)):
                            result.error(f"{prefix}.{key} is required")
                    if not _list_of_strings(group.get("assumed_knowledge")):
                        result.error(f"{prefix}.assumed_knowledge must be an array of strings")
            for key in ("shared_need", "shared_baseline", "desired_takeaway", "language"):
                if not _nonempty_string(profile.get(key)):
                    result.error(f"scope.audience_profile.{key} is required")
            for key in ("do_not_assume", "avoid_terms", "tone"):
                value = profile.get(key)
                if not _list_of_strings(value):
                    result.error(f"scope.audience_profile.{key} must be an array of strings")
                elif key == "tone" and not value:
                    result.error("scope.audience_profile.tone must contain at least one tone")
            if profile.get("term_policy") not in {
                "plain_first",
                "define_on_first_use",
                "expert_shorthand",
            }:
                result.error(
                    "scope.audience_profile.term_policy must be 'plain_first', "
                    "'define_on_first_use', or 'expert_shorthand'"
                )
            result.metrics["audience_group_count"] = len(group_ids)
    for key in ("tradeoffs", "open_questions", "success_criteria"):
        if not isinstance(data.get(key), list):
            result.error(f"scope.{key} must be an array")
    included = data.get("included_claim_ids")
    deferred = data.get("deferred_claim_ids", [])
    if not _list_of_strings(included):
        result.error("scope.included_claim_ids must be an array of IDs")
        included = []
    elif not included:
        result.error("scope.included_claim_ids must contain at least one supported claim")
    if not _list_of_strings(deferred):
        result.error("scope.deferred_claim_ids must be an array of IDs")
        deferred = []
    overlap = set(included) & set(deferred)
    if overlap:
        result.error("Claims cannot be both included and deferred: " + ", ".join(sorted(overlap)))
    known = _claim_ids(run_dir)
    unknown = (set(included) | set(deferred)) - known
    if unknown:
        result.error("Scope references unknown claim IDs: " + ", ".join(sorted(unknown)))
    unassigned_must_keep = _must_keep_claim_ids(run_dir) - (set(included) | set(deferred))
    if unassigned_must_keep:
        result.error("Scope does not decide must-keep claims: " + ", ".join(sorted(unassigned_must_keep)))
    units = data.get("knowledge_units")
    unit_ids: set[str] = set()
    if not isinstance(units, list) or not units:
        result.error("scope.knowledge_units must be a non-empty array")
        units = []
    for index, unit in enumerate(units):
        prefix = f"scope.knowledge_units[{index}]"
        if not isinstance(unit, dict):
            result.error(f"{prefix} must be an object")
            continue
        unit_id = unit.get("id")
        if not _nonempty_string(unit_id):
            result.error(f"{prefix}.id is required")
        elif unit_id in unit_ids:
            result.error(f"Duplicate knowledge unit id: {unit_id}")
        else:
            unit_ids.add(str(unit_id))
        if not _nonempty_string(unit.get("question")):
            result.error(f"{prefix}.question is required")
        unit_claims = unit.get("claim_ids", [])
        if not _list_of_strings(unit_claims):
            result.error(f"{prefix}.claim_ids must be an array of IDs")
        elif set(unit_claims) - known:
            result.error(f"{prefix} references unknown claim IDs: " + ", ".join(sorted(set(unit_claims) - known)))
    _validate_budget(data, result)
    duration = data.get("target_duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        result.error("scope.target_duration_seconds must be positive")
    if mode == "series":
        parts = data.get("parts")
        if not isinstance(parts, list) or len(parts) < 2:
            result.error("A series scope needs at least two parts")
            parts = []
        part_ids: set[str] = set()
        for index, part in enumerate(parts):
            prefix = f"scope.parts[{index}]"
            if not isinstance(part, dict):
                result.error(f"{prefix} must be an object")
                continue
            part_id = part.get("id")
            if not _nonempty_string(part_id):
                result.error(f"{prefix}.id is required")
            elif part_id in part_ids:
                result.error(f"Duplicate part id: {part_id}")
            else:
                part_ids.add(str(part_id))
            if not _nonempty_string(part.get("promise")):
                result.error(f"{prefix}.promise is required")
            part_units = part.get("knowledge_unit_ids", [])
            if not _list_of_strings(part_units):
                result.error(f"{prefix}.knowledge_unit_ids must be an array of IDs")
            elif set(part_units) - unit_ids:
                result.error(f"{prefix} references unknown knowledge unit IDs")
    elif "parts" in data and not isinstance(data.get("parts"), list):
        result.error("scope.parts must be an array")
    result.metrics.update({"included_claims": len(included), "deferred_claims": len(deferred)})
    return result


def validate_outline(run_dir: Path) -> ValidationResult:
    result = ValidationResult("outline")
    data = _load_json_object(canonical_paths(run_dir, "outline")["outline"], result)
    if data is None:
        return result
    if data.get("schema_version") != SCHEMA_VERSION:
        result.error(f"outline.schema_version must be {SCHEMA_VERSION!r}")
    if not _nonempty_string(data.get("title")):
        result.error("outline.title is required")
    if not _nonempty_string(data.get("hook_strategy")):
        result.error("outline.hook_strategy is required")
    _validate_budget(data, result)
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        result.error("outline.sections must be a non-empty array")
        return result
    audience_contract = _uses_audience_contract(run_dir)
    hook_contract = "hook_brief" in data
    if audience_contract and not hook_contract:
        result.error("outline.hook_brief is required when scope.audience_profile is present")
    if hook_contract:
        hook_brief = data.get("hook_brief")
        if not isinstance(hook_brief, dict):
            result.error("outline.hook_brief must be an object")
        else:
            for key in (
                "section_id",
                "opening_move",
                "title_alignment",
                "viewer_payoff",
                "curiosity_gap",
                "body_handoff",
            ):
                if not _nonempty_string(hook_brief.get(key)):
                    result.error(f"outline.hook_brief.{key} is required")
            avoid = hook_brief.get("avoid")
            if not _list_of_strings(avoid) or not avoid:
                result.error("outline.hook_brief.avoid must be a non-empty array of strings")
            max_words = hook_brief.get("max_words")
            if not isinstance(max_words, int) or isinstance(max_words, bool) or max_words <= 0:
                result.error("outline.hook_brief.max_words must be a positive integer")
            target_seconds = hook_brief.get("target_seconds")
            max_seconds = hook_brief.get("max_seconds")
            delivery_wpm = hook_brief.get("delivery_wpm")
            for key, value in (
                ("target_seconds", target_seconds),
                ("max_seconds", max_seconds),
                ("delivery_wpm", delivery_wpm),
            ):
                if not _positive_number(value):
                    result.error(f"outline.hook_brief.{key} must be positive")
            if _positive_number(target_seconds) and _positive_number(max_seconds):
                if float(target_seconds) > float(max_seconds):
                    result.error("outline.hook_brief.target_seconds cannot exceed max_seconds")
            if (
                isinstance(max_words, int)
                and not isinstance(max_words, bool)
                and max_words > 0
                and _positive_number(max_seconds)
                and _positive_number(delivery_wpm)
            ):
                if max_words / float(delivery_wpm) * 60 > float(max_seconds) + 1e-9:
                    result.error(
                        "outline.hook_brief.max_words exceeds max_seconds at the configured delivery_wpm"
                    )
            first_section = sections[0] if isinstance(sections[0], dict) else {}
            if (
                _nonempty_string(hook_brief.get("section_id"))
                and hook_brief.get("section_id") != first_section.get("id")
            ):
                result.error("outline.hook_brief.section_id must match the first outline section")
            if isinstance(max_words, int) and not isinstance(max_words, bool) and max_words > 0:
                result.metrics["hook_max_words"] = max_words
            if _positive_number(max_seconds):
                result.metrics["hook_max_seconds"] = max_seconds
    known_claims = _claim_ids(run_dir)
    known_units = _scope_knowledge_unit_ids(run_dir)
    ids: set[str] = set()
    covered: set[str] = set()
    estimated_words = 0
    for index, section in enumerate(sections):
        prefix = f"outline.sections[{index}]"
        if not isinstance(section, dict):
            result.error(f"{prefix} must be an object")
            continue
        section_id = section.get("id")
        if not _nonempty_string(section_id):
            result.error(f"{prefix}.id is required")
        elif section_id in ids:
            result.error(f"Duplicate outline section id: {section_id}")
        else:
            ids.add(section_id)
        if not (_nonempty_string(section.get("title")) or _nonempty_string(section.get("heading"))):
            result.error(f"{prefix}.title is required")
        if not _nonempty_string(section.get("purpose")):
            result.error(f"{prefix}.purpose is required")
        if not _nonempty_string(section.get("summary")):
            result.error(f"{prefix}.summary is required")
        for forbidden in ("text", "voiceover", "producer_notes"):
            if forbidden in section:
                result.error(
                    f"{prefix}.{forbidden} is not allowed in the structural outline; "
                    "write full Human Host speech only after outline approval"
                )
        claim_ids = section.get("claim_ids", [])
        if not _list_of_strings(claim_ids):
            result.error(f"{prefix}.claim_ids must be an array of IDs")
            claim_ids = []
        covered.update(claim_ids)
        unknown = set(claim_ids) - known_claims
        if unknown:
            result.error(f"{prefix} references unknown claims: {', '.join(sorted(unknown))}")
        unit_ids = section.get("knowledge_unit_ids", [])
        if not _list_of_strings(unit_ids):
            result.error(f"{prefix}.knowledge_unit_ids must be an array of IDs")
        elif set(unit_ids) - known_units:
            result.error(f"{prefix} references unknown knowledge units: {', '.join(sorted(set(unit_ids) - known_units))}")
        words = section.get("estimated_words")
        if words is not None:
            if not isinstance(words, int) or isinstance(words, bool) or words <= 0:
                result.error(f"{prefix}.estimated_words must be a positive integer")
            else:
                estimated_words += words
        if index > 0 and not _nonempty_string(section.get("transition_in")):
            result.error(f"{prefix}.transition_in is required to preserve continuity")
        if index < len(sections) - 1 and not _nonempty_string(section.get("transition_out")):
            result.error(f"{prefix}.transition_out is required to preserve continuity")
    expected = _scope_claim_ids(run_dir)
    missing = expected - covered
    if missing:
        result.error("Outline does not cover included scope claims: " + ", ".join(sorted(missing)))
    if estimated_words:
        low, high, _ = _read_budget(data)
        if low is not None and estimated_words < low:
            result.error(f"Outline estimates {estimated_words} words, below budget minimum {low}")
        if high is not None and estimated_words > high:
            result.error(f"Outline estimates {estimated_words} words, above budget maximum {high}")
    result.metrics.update(
        {"section_count": len(sections), "covered_claims": len(covered), "estimated_words": estimated_words or None}
    )
    return result


def _script_segments(data: Mapping[str, Any]) -> list[Any]:
    value = data.get("segments")
    return value if isinstance(value, list) else []


def _segment_text(segment: Mapping[str, Any]) -> str:
    value = segment.get("text", "")
    return str(value).strip() if value is not None else ""


def validate_script(run_dir: Path) -> ValidationResult:
    result = ValidationResult("script")
    paths = canonical_paths(run_dir, "script")
    data = _load_json_object(paths["script"], result)
    if data is None:
        return result
    teleprompter_path = paths["teleprompter"]
    if not teleprompter_path.is_file():
        result.error("Missing canonical artifact: teleprompter-script.md")
    if data.get("schema_version") != SCHEMA_VERSION:
        result.error(f"script.schema_version must be {SCHEMA_VERSION!r}")
    if not _nonempty_string(data.get("title")):
        result.error("script.title is required")
    target_duration = data.get("target_duration_seconds")
    if not isinstance(target_duration, (int, float)) or isinstance(target_duration, bool) or target_duration <= 0:
        result.error("script.target_duration_seconds must be positive")
    _validate_budget(data, result)
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        result.error("script.segments must be a non-empty array")
        return result
    audience_contract = _uses_audience_contract(run_dir)
    audience_profile = _scope_audience_profile(run_dir) if audience_contract else None
    hook_contract = _uses_hook_contract(run_dir)
    hook_brief = _outline_hook_brief(run_dir) if hook_contract else None
    ids: set[str] = set()
    covered: set[str] = set()
    total_words = 0
    known_claims = _claim_ids(run_dir)
    for index, segment in enumerate(segments):
        prefix = f"script.segments[{index}]"
        if not isinstance(segment, dict):
            result.error(f"{prefix} must be an object")
            continue
        segment_id = segment.get("id")
        if not _nonempty_string(segment_id):
            result.error(f"{prefix}.id is required")
        elif segment_id in ids:
            result.error(f"Duplicate script segment id: {segment_id}")
        else:
            ids.add(segment_id)
        if not (_nonempty_string(segment.get("heading")) or _nonempty_string(segment.get("title"))):
            result.error(f"{prefix}.heading is required")
        if "voiceover" in segment:
            result.error(f"{prefix}.voiceover is not supported; put canonical spoken text in .text")
        text = _segment_text(segment)
        if not text:
            result.error(f"{prefix}.text is required")
        total_words += count_words(text)
        claim_ids = segment.get("claim_ids", [])
        if not _list_of_strings(claim_ids):
            result.error(f"{prefix}.claim_ids must be an array of IDs")
            claim_ids = []
        covered.update(claim_ids)
        unknown = set(claim_ids) - known_claims
        if unknown:
            result.error(f"{prefix} references unknown claims: {', '.join(sorted(unknown))}")
        if index < len(segments) - 1 and not _nonempty_string(segment.get("transition")):
            result.error(f"{prefix}.transition is required before the next segment")
        if "producer_notes" in segment and not isinstance(segment.get("producer_notes"), dict):
            result.error(f"{prefix}.producer_notes must be an object")
    outline_ids = _outline_section_ids(run_dir)
    script_ids = [str(item.get("id")) for item in segments if isinstance(item, dict) and item.get("id")]
    if outline_ids and script_ids != outline_ids:
        result.error("Script segment IDs and order must match the approved outline sections")
    if hook_contract:
        hook = data.get("hook")
        if not isinstance(hook, dict):
            result.error("script.hook is required when outline.hook_brief is present")
        else:
            segment_id = hook.get("segment_id")
            end_phrase = hook.get("end_phrase")
            if not _nonempty_string(segment_id):
                result.error("script.hook.segment_id is required")
            if not _nonempty_string(end_phrase):
                result.error("script.hook.end_phrase is required")
            if _nonempty_string(segment_id) and script_ids and segment_id != script_ids[0]:
                result.error("script.hook.segment_id must match the first script segment")
            if isinstance(hook_brief, dict) and _nonempty_string(hook_brief.get("section_id")):
                if segment_id != hook_brief.get("section_id"):
                    result.error("script.hook.segment_id must match outline.hook_brief.section_id")
            elif hook_brief is None:
                result.error("script hook cannot be validated because outline.hook_brief is missing or invalid")

            target_segment = next(
                (
                    item
                    for item in segments
                    if isinstance(item, dict)
                    and _nonempty_string(segment_id)
                    and item.get("id") == segment_id
                ),
                None,
            )
            if _nonempty_string(segment_id) and target_segment is None:
                result.error(f"script.hook.segment_id references an unknown segment: {segment_id}")
            if isinstance(target_segment, dict) and _nonempty_string(end_phrase):
                target_text = _segment_text(target_segment)
                matches = _phrase_matches(target_text, str(end_phrase))
                if len(matches) != 1:
                    result.error("script.hook.end_phrase must occur exactly once in the hook segment text")
                else:
                    hook_text = target_text[: matches[0].end()]
                    hook_words = count_words(hook_text)
                    result.metrics["hook_word_count"] = hook_words
                    if isinstance(hook_brief, dict):
                        max_words = hook_brief.get("max_words")
                        delivery_wpm = hook_brief.get("delivery_wpm")
                        max_seconds = hook_brief.get("max_seconds")
                        if isinstance(max_words, int) and not isinstance(max_words, bool) and max_words > 0:
                            if hook_words > max_words:
                                result.error(
                                    f"Script hook has {hook_words} words, above the approved maximum {max_words}"
                                )
                        if _positive_number(delivery_wpm):
                            raw_hook_seconds = hook_words / float(delivery_wpm) * 60
                            hook_seconds = round(raw_hook_seconds, 1)
                            result.metrics["hook_estimated_seconds"] = hook_seconds
                            if _positive_number(max_seconds) and raw_hook_seconds > float(max_seconds) + 1e-9:
                                result.error(
                                    f"Script hook is about {hook_seconds:.1f}s, above the approved maximum "
                                    f"{float(max_seconds):g}s"
                                )

    if isinstance(audience_profile, dict):
        avoid_terms = audience_profile.get("avoid_terms", [])
        if _list_of_strings(avoid_terms):
            for index, segment in enumerate(segments):
                if not isinstance(segment, dict):
                    continue
                text = _segment_text(segment)
                for term in avoid_terms:
                    if _contains_term(text, term):
                        result.error(
                            f"script.segments[{index}].text uses audience-blocked term {term!r}"
                        )
    low, high, _ = _read_budget(data)
    if low is not None and total_words < low:
        result.error(f"Script has {total_words} words, below budget minimum {low}")
    if high is not None and total_words > high:
        result.error(f"Script has {total_words} words, above budget maximum {high}")
    expected = _scope_claim_ids(run_dir)
    missing = expected - covered
    if missing:
        result.error("Script metadata does not map included claims: " + ", ".join(sorted(missing)))
    quality = data.get("quality")
    if not isinstance(quality, dict):
        result.error("script.quality must record fact, continuity, and originality passes")
    else:
        required_quality_passes = ["fact_pass", "continuity_pass", "originality_pass"]
        if audience_contract:
            required_quality_passes.extend(["audience_fit_pass", "spoken_language_pass"])
        if hook_contract:
            required_quality_passes.append("hook_pass")
        for name in required_quality_passes:
            check = quality.get(name)
            if not isinstance(check, dict):
                result.error(f"script.quality.{name} must be an object")
                continue
            if check.get("status") != "passed":
                result.error(f"script.quality.{name}.status must be 'passed'")
            if not _nonempty_string(check.get("summary")):
                result.error(f"script.quality.{name}.summary is required")
        if hook_contract and isinstance(quality.get("hook_pass"), dict):
            hook_pass = quality["hook_pass"]
            reported_words = hook_pass.get("word_count")
            if not isinstance(reported_words, int) or isinstance(reported_words, bool) or reported_words < 0:
                result.error("script.quality.hook_pass.word_count must be a non-negative integer")
            elif "hook_word_count" in result.metrics and reported_words != result.metrics["hook_word_count"]:
                result.error(
                    "script.quality.hook_pass.word_count must equal the measured hook word count "
                    f"({result.metrics['hook_word_count']})"
                )
            reported_seconds = hook_pass.get("estimated_seconds")
            if not _positive_number(reported_seconds):
                result.error("script.quality.hook_pass.estimated_seconds must be positive")
            elif (
                "hook_estimated_seconds" in result.metrics
                and abs(float(reported_seconds) - float(result.metrics["hook_estimated_seconds"])) > 0.05
            ):
                result.error(
                    "script.quality.hook_pass.estimated_seconds must equal the measured hook duration "
                    f"({result.metrics['hook_estimated_seconds']})"
                )
    estimated_duration = round(total_words / 150 * 60, 1)
    if isinstance(target_duration, (int, float)) and not isinstance(target_duration, bool) and target_duration > 0:
        deviation = abs(estimated_duration - float(target_duration)) / float(target_duration)
        if deviation > 0.25:
            result.warn(
                f"At 150 wpm the script is about {estimated_duration:.0f}s, far from target {target_duration}s"
            )
    result.metrics.update(
        {"segment_count": len(segments), "word_count": total_words, "estimated_duration_seconds_at_150_wpm": estimated_duration}
    )
    if teleprompter_path.is_file():
        expected_teleprompter = _render_teleprompter(data)
        if teleprompter_path.read_bytes() != expected_teleprompter.encode("utf-8"):
            result.error(
                "script/teleprompter-script.md differs from the spoken text in script/final.json; "
                "run materialize-script again"
            )
        else:
            result.metrics["teleprompter_words"] = count_words(expected_teleprompter)
    return result


def _relative_entry(value: Any) -> bool:
    if not _nonempty_string(value):
        return False
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not path.is_absolute() and ".." not in path.parts


def _validate_storyboard_editorial_plan(
    editorial_plan: Any,
    result: ValidationResult,
    *,
    segment_ids: set[str],
    cue_to_segment: Mapping[str, str],
    shot_segment_by_id: Mapping[str, str],
    final_shot_id: str | None,
    script_hook_segment_id: str | None,
    script_text_by_id: Mapping[str, str],
) -> None:
    """Validate the additive editorial coverage contract when it is present."""

    if not isinstance(editorial_plan, dict):
        result.error("storyboard.editorial_plan must be an object when present")
        return

    hook_segment_id = editorial_plan.get("hook_segment_id")
    if not _nonempty_string(hook_segment_id):
        result.error("storyboard.editorial_plan.hook_segment_id is required")
        hook_segment_id = None
    elif hook_segment_id not in segment_ids:
        result.error("storyboard.editorial_plan.hook_segment_id references an unknown segment")
    if script_hook_segment_id is not None and hook_segment_id != script_hook_segment_id:
        result.error(
            "storyboard.editorial_plan.hook_segment_id must match "
            "script.hook.segment_id from the approved canonical script"
        )

    hook_beats = editorial_plan.get("hook_beats")
    if not isinstance(hook_beats, list) or not hook_beats:
        result.error("storyboard.editorial_plan.hook_beats must be a non-empty array")
        hook_beats = []
    beat_ids: set[str] = set()
    for index, beat in enumerate(hook_beats):
        prefix = f"storyboard.editorial_plan.hook_beats[{index}]"
        if not isinstance(beat, dict):
            result.error(f"{prefix} must be an object")
            continue
        beat_id = beat.get("id")
        if not _nonempty_string(beat_id):
            result.error(f"{prefix}.id is required")
        elif beat_id in beat_ids:
            result.error(f"Duplicate editorial hook beat id: {beat_id}")
        else:
            beat_ids.add(str(beat_id))

        cue_id = beat.get("cue_id")
        if not _nonempty_string(cue_id):
            result.error(f"{prefix}.cue_id is required")
        elif cue_id not in cue_to_segment:
            result.error(f"{prefix}.cue_id references an unknown cue")
        elif hook_segment_id is not None and cue_to_segment[str(cue_id)] != hook_segment_id:
            result.error(f"{prefix}.cue_id must belong to editorial_plan.hook_segment_id")

        purpose = beat.get("purpose")
        if purpose not in EDITORIAL_HOOK_PURPOSES:
            result.error(
                f"{prefix}.purpose must be one of: "
                + ", ".join(sorted(EDITORIAL_HOOK_PURPOSES))
            )

        coverage = beat.get("coverage")
        if coverage not in EDITORIAL_HOOK_COVERAGE:
            result.error(
                f"{prefix}.coverage must be one of: "
                + ", ".join(sorted(EDITORIAL_HOOK_COVERAGE))
            )
            continue
        shot_ids = beat.get("shot_ids")
        if coverage == "host_only":
            if shot_ids not in (None, []):
                result.error(f"{prefix}.shot_ids must be omitted or empty for host_only coverage")
            continue
        if not isinstance(shot_ids, list) or not shot_ids:
            result.error(f"{prefix}.shot_ids must be a non-empty array for shot coverage")
            continue
        for shot_index, shot_id in enumerate(shot_ids):
            shot_prefix = f"{prefix}.shot_ids[{shot_index}]"
            if not _nonempty_string(shot_id):
                result.error(f"{shot_prefix} must be a non-empty shot id")
            elif shot_id not in shot_segment_by_id:
                result.error(f"{shot_prefix} references an unknown shot")
            elif hook_segment_id is not None and shot_segment_by_id[str(shot_id)] != hook_segment_id:
                result.error(f"{shot_prefix} must reference a shot in editorial_plan.hook_segment_id")

    title_treatment = editorial_plan.get("title_treatment")
    if not isinstance(title_treatment, dict):
        result.error("storyboard.editorial_plan.title_treatment must be an object")
    else:
        mode = title_treatment.get("mode")
        if mode not in EDITORIAL_TITLE_MODES:
            result.error(
                "storyboard.editorial_plan.title_treatment.mode must be one of: "
                + ", ".join(sorted(EDITORIAL_TITLE_MODES))
            )
        shot_id = title_treatment.get("shot_id")
        if not _nonempty_string(shot_id):
            result.error("storyboard.editorial_plan.title_treatment.shot_id is required")
        elif shot_id not in shot_segment_by_id:
            result.error("storyboard.editorial_plan.title_treatment.shot_id references an unknown shot")
        elif hook_segment_id is not None and shot_segment_by_id[str(shot_id)] != hook_segment_id:
            result.error(
                "storyboard.editorial_plan.title_treatment.shot_id must reference a shot in "
                "editorial_plan.hook_segment_id"
            )
        if not _nonempty_string(title_treatment.get("screen_text")):
            result.error("storyboard.editorial_plan.title_treatment.screen_text is required")

    ending = editorial_plan.get("ending")
    if not isinstance(ending, dict):
        result.error("storyboard.editorial_plan.ending must be an object")
        return
    ending_mode = ending.get("mode")
    if ending_mode not in EDITORIAL_ENDING_MODES:
        result.error(
            "storyboard.editorial_plan.ending.mode must be one of: "
            + ", ".join(sorted(EDITORIAL_ENDING_MODES))
        )
        return
    ending_shot_id = ending.get("shot_id")
    screen_text = ending.get("screen_text")
    if ending_mode in {"visual_cta", "spoken_cta"}:
        if not _nonempty_string(ending_shot_id):
            result.error(f"storyboard.editorial_plan.ending.shot_id is required for {ending_mode}")
        elif ending_shot_id not in shot_segment_by_id:
            result.error("storyboard.editorial_plan.ending.shot_id references an unknown shot")
        elif ending_shot_id != final_shot_id:
            result.error("storyboard.editorial_plan.ending.shot_id must reference the final storyboard shot")
        if not _nonempty_string(screen_text):
            result.error(f"storyboard.editorial_plan.ending.screen_text is required for {ending_mode}")
        if ending_mode == "spoken_cta":
            spoken_phrase = ending.get("spoken_phrase")
            if not _nonempty_string(spoken_phrase):
                result.error("storyboard.editorial_plan.ending.spoken_phrase is required for spoken_cta")
            elif _nonempty_string(ending_shot_id) and ending_shot_id in shot_segment_by_id:
                ending_segment_id = shot_segment_by_id[str(ending_shot_id)]
                script_text = script_text_by_id.get(ending_segment_id)
                if script_text is None:
                    result.error(
                        "storyboard.editorial_plan.ending.spoken_phrase cannot be verified because "
                        "the ending shot segment is missing from the approved canonical script"
                    )
                else:
                    occurrences = script_text.count(str(spoken_phrase))
                    if occurrences != 1:
                        result.error(
                            "storyboard.editorial_plan.ending.spoken_phrase must occur exactly once "
                            f"in approved script segment {ending_segment_id!r}; found {occurrences}"
                        )
        elif "spoken_phrase" in ending:
            result.error("storyboard.editorial_plan.ending.spoken_phrase must be omitted for visual_cta")
    else:
        if "shot_id" in ending:
            result.error(f"storyboard.editorial_plan.ending.shot_id must be omitted for {ending_mode}")
        if ending_mode == "host_only":
            if "screen_text" in ending and not _nonempty_string(screen_text):
                result.error(
                    "storyboard.editorial_plan.ending.screen_text must be non-empty when present "
                    "for host_only"
                )
        elif "screen_text" in ending:
            result.error("storyboard.editorial_plan.ending.screen_text must be omitted for none")
        if "spoken_phrase" in ending:
            result.error(f"storyboard.editorial_plan.ending.spoken_phrase must be omitted for {ending_mode}")


def _scene_navigation_configuration(storyboard: Mapping[str, Any]) -> dict[str, str] | None:
    project = storyboard.get("project")
    if not isinstance(project, Mapping):
        raise WorkflowError("storyboard.project must be an object before reading scene navigation")
    if "scene_navigation" not in project:
        return None
    raw = project.get("scene_navigation")
    if not isinstance(raw, Mapping):
        raise WorkflowError("storyboard.project.scene_navigation must be an object when present")
    unknown = sorted(set(raw) - SCENE_NAVIGATION_KEYS)
    if unknown:
        raise WorkflowError(
            "storyboard.project.scene_navigation has unknown field: " + unknown[0]
        )
    config = {**DEFAULT_SCENE_NAVIGATION, **raw}
    if config.get("mode") != "manual":
        raise WorkflowError('storyboard.project.scene_navigation.mode must be "manual"')
    if config.get("boundary_policy") != "sentence_start":
        raise WorkflowError(
            'storyboard.project.scene_navigation.boundary_policy must be "sentence_start"'
        )
    if config.get("intra_sentence_changes") != "component_state":
        raise WorkflowError(
            "storyboard.project.scene_navigation.intra_sentence_changes must be "
            '"component_state"'
        )
    return {key: str(config[key]) for key in DEFAULT_SCENE_NAVIGATION}


def _is_sentence_start(text: str, index: int) -> bool:
    if index < 0 or index > len(text):
        return False
    if index == 0:
        return True
    before = text[:index].rstrip()
    before = re.sub(r'''["'”’»）)\]}]+$''', "", before).rstrip()
    return bool(re.search(r"[.!?…。！？]$", before))


def validate_storyboard(run_dir: Path) -> ValidationResult:
    result = ValidationResult("storyboard")
    data = _load_json_object(canonical_paths(run_dir, "storyboard")["storyboard"], result)
    if data is None:
        return result
    if data.get("schema_version") != SCHEMA_VERSION:
        result.error(f"storyboard.schema_version must be {SCHEMA_VERSION!r}")
    project = data.get("project")
    default_host_layout: str | None = None
    support_top_geometry_required = False
    scene_navigation: dict[str, str] | None = None
    if not isinstance(project, dict):
        result.error("storyboard.project must be an object")
    else:
        if not _nonempty_string(project.get("ratio")):
            result.error("storyboard.project.ratio is required")
        fps = project.get("fps")
        if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0:
            result.error("storyboard.project.fps must be positive")
        if "default_host_layout" in project:
            candidate_default_host_layout = project.get("default_host_layout")
            if (
                not isinstance(candidate_default_host_layout, str)
                or candidate_default_host_layout not in HOST_LAYOUTS
            ):
                result.error(
                    "storyboard.project.default_host_layout must be one of: "
                    + ", ".join(sorted(HOST_LAYOUTS))
                )
            else:
                default_host_layout = candidate_default_host_layout
                if default_host_layout == "support_top":
                    support_top_geometry_required = True
        if "karaoke_caption" in project:
            try:
                _karaoke_configuration(data, fallback_wpm=150)
            except WorkflowError as exc:
                result.error(str(exc))
        if "scene_navigation" in project:
            try:
                scene_navigation = _scene_navigation_configuration(data)
            except WorkflowError as exc:
                result.error(str(exc))

    segments = data.get("segments")
    shots = data.get("shots")
    assets = data.get("assets", [])
    if not isinstance(segments, list) or not segments:
        result.error("storyboard.segments must be a non-empty array")
        segments = []
    if not isinstance(shots, list):
        result.error("storyboard.shots must be an array")
        shots = []
    if not isinstance(assets, list):
        result.error("storyboard.assets must be an array")
        assets = []

    script_path = canonical_paths(run_dir, "script")["script"]
    script_ids: set[str] = set()
    script_text_by_id: dict[str, str] = {}
    script_hook_segment_id: str | None = None
    script_data_object: dict[str, Any] | None = None
    if script_path.is_file():
        try:
            script_data = json.loads(script_path.read_text(encoding="utf-8"))
            if isinstance(script_data, dict):
                script_data_object = script_data
            script_ids = {
                str(item.get("id"))
                for item in _script_segments(script_data if isinstance(script_data, dict) else {})
                if isinstance(item, dict) and item.get("id")
            }
            script_text_by_id = {
                str(item.get("id")): _segment_text(item)
                for item in _script_segments(script_data if isinstance(script_data, dict) else {})
                if isinstance(item, dict) and item.get("id")
            }
            if isinstance(script_data, dict):
                script_hook = script_data.get("hook")
                if isinstance(script_hook, dict) and _nonempty_string(script_hook.get("segment_id")):
                    script_hook_segment_id = str(script_hook["segment_id"])
        except (json.JSONDecodeError, OSError):
            pass

    segment_ids: set[str] = set()
    segment_host_layouts: dict[str, str] = {}
    cue_to_segment: dict[str, str] = {}
    cue_details: dict[str, tuple[str, str, int]] = {}
    for index, segment in enumerate(segments):
        prefix = f"storyboard.segments[{index}]"
        if not isinstance(segment, dict):
            result.error(f"{prefix} must be an object")
            continue
        segment_id = segment.get("id")
        if not _nonempty_string(segment_id):
            result.error(f"{prefix}.id is required")
            continue
        if segment_id in segment_ids:
            result.error(f"Duplicate storyboard segment id: {segment_id}")
        segment_ids.add(segment_id)
        if "host_layout" in segment:
            host_layout = segment.get("host_layout")
            if not isinstance(host_layout, str) or host_layout not in HOST_LAYOUTS:
                result.error(f"{prefix}.host_layout must be one of: " + ", ".join(sorted(HOST_LAYOUTS)))
            else:
                segment_host_layouts[str(segment_id)] = host_layout
                if host_layout == "support_top":
                    support_top_geometry_required = True
        if script_ids and segment_id not in script_ids:
            result.error(f"Storyboard segment {segment_id!r} does not exist in script/final.json")
        text = segment.get("text")
        if not _nonempty_string(text):
            result.error(f"{prefix}.text is required")
            text = ""
        elif segment_id in script_text_by_id:
            board_text = " ".join(str(text).split())
            script_text = " ".join(script_text_by_id[str(segment_id)].split())
            if board_text != script_text:
                result.error(f"{prefix}.text must exactly match the approved script segment text")
        cues = segment.get("cues")
        if not isinstance(cues, list):
            result.error(f"{prefix}.cues must be an array")
            cues = []
        normalized_text = " ".join(str(text).casefold().split())
        for cue_index, cue in enumerate(cues):
            cue_prefix = f"{prefix}.cues[{cue_index}]"
            if not isinstance(cue, dict):
                result.error(f"{cue_prefix} must be an object")
                continue
            cue_id = cue.get("id")
            phrase = cue.get("phrase")
            if not _nonempty_string(cue_id):
                result.error(f"{cue_prefix}.id is required")
            elif cue_id in cue_to_segment:
                result.error(f"Duplicate cue id: {cue_id}")
            else:
                cue_to_segment[str(cue_id)] = str(segment_id)
            if not _nonempty_string(phrase):
                result.error(f"{cue_prefix}.phrase is required")
            else:
                normalized_phrase = " ".join(str(phrase).casefold().split())
                occurrences = normalized_text.count(normalized_phrase)
                if occurrences == 0:
                    result.error(f"Cue phrase {phrase!r} does not occur in segment {segment_id!r} text")
                elif occurrences > 1:
                    result.error(
                        f"Cue phrase {phrase!r} occurs {occurrences} times in segment {segment_id!r}; "
                        "use a longer unique phrase"
                    )
                else:
                    try:
                        position = _cue_phrase_start(
                            str(text), str(phrase), shot_id="scene-navigation", cue_id=str(cue_id)
                        )
                    except WorkflowError as exc:
                        result.error(str(exc))
                    else:
                        cue_details[str(cue_id)] = (str(segment_id), str(text), position)

    if script_ids:
        missing_segments = script_ids - segment_ids
        if missing_segments:
            result.error("Storyboard omits script segments: " + ", ".join(sorted(missing_segments)))

    allowed_renderers = {"component", "html", "mermaid", "stock", "image", "screen_recording"}
    shot_ids: set[str] = set()
    shot_segment_by_id: dict[str, str] = {}
    for index, shot in enumerate(shots):
        prefix = f"storyboard.shots[{index}]"
        if not isinstance(shot, dict):
            result.error(f"{prefix} must be an object")
            continue
        shot_id = shot.get("id")
        segment_id = shot.get("segment_id")
        if not _nonempty_string(shot_id):
            result.error(f"{prefix}.id is required")
        elif shot_id in shot_ids:
            result.error(f"Duplicate shot id: {shot_id}")
        else:
            shot_ids.add(shot_id)
            if _nonempty_string(segment_id):
                shot_segment_by_id[str(shot_id)] = str(segment_id)
        if segment_id not in segment_ids:
            result.error(f"{prefix}.segment_id references an unknown segment")
        if not _nonempty_string(shot.get("intent")):
            result.error(f"{prefix}.intent is required")
        shot_lane: str | None = None
        if "lane" in shot:
            lane = shot.get("lane")
            if not isinstance(lane, str) or lane not in SHOT_LANES:
                result.error(f"{prefix}.lane must be one of: " + ", ".join(sorted(SHOT_LANES)))
            else:
                shot_lane = lane
        effective_host_layout = (
            shot_lane
            or segment_host_layouts.get(str(segment_id))
            or default_host_layout
            or "support_top"
        )
        if effective_host_layout == "support_top":
            support_top_geometry_required = True
        if "visual_options" in shot:
            visual_options = shot.get("visual_options")
            if not isinstance(visual_options, list) or not visual_options:
                result.error(f"{prefix}.visual_options must be a non-empty array")
                visual_options = []
            option_ids: set[str] = set()
            option_modalities: dict[str, Any] = {}
            for option_index, option in enumerate(visual_options):
                option_prefix = f"{prefix}.visual_options[{option_index}]"
                if not isinstance(option, dict):
                    result.error(f"{option_prefix} must be an object")
                    continue
                option_id = option.get("id")
                modality = option.get("modality")
                if not _nonempty_string(option_id):
                    result.error(f"{option_prefix}.id is required")
                elif option_id in option_ids:
                    result.error(f"Duplicate visual option id in {prefix}: {option_id}")
                else:
                    option_ids.add(str(option_id))
                    option_modalities[str(option_id)] = modality
                if not isinstance(modality, str) or modality not in VISUAL_OPTION_MODALITIES:
                    result.error(
                        f"{option_prefix}.modality must be one of: "
                        + ", ".join(sorted(VISUAL_OPTION_MODALITIES))
                    )
                for field_name in ("treatment", "why", "source_plan", "rights_note"):
                    if not _nonempty_string(option.get(field_name)):
                        result.error(f"{option_prefix}.{field_name} is required")
            selected_option_id = shot.get("selected_option_id")
            if not _nonempty_string(selected_option_id):
                result.error(f"{prefix}.selected_option_id is required when visual_options is present")
            elif selected_option_id not in option_ids:
                result.error(f"{prefix}.selected_option_id references an unknown visual option")
            elif option_modalities.get(selected_option_id) == "host_only":
                result.error(
                    f"{prefix}.selected_option_id cannot select a host_only visual option; "
                    "host_only does not create a shot"
                )
        for boundary in ("enter", "exit"):
            trigger = shot.get(boundary)
            if boundary == "exit" and trigger is None:
                continue
            if not isinstance(trigger, dict):
                result.error(f"{prefix}.{boundary} must be an object")
                continue
            cue_id = trigger.get("cue_id")
            if cue_id not in cue_to_segment:
                result.error(f"{prefix}.{boundary}.cue_id references an unknown cue")
            elif cue_to_segment[str(cue_id)] != segment_id:
                result.error(f"{prefix}.{boundary}.cue_id belongs to a different segment")
            offset = trigger.get("offset_ms", 0)
            if not isinstance(offset, int) or isinstance(offset, bool):
                result.error(f"{prefix}.{boundary}.offset_ms must be an integer")
            if boundary == "enter" and scene_navigation is not None:
                detail = cue_details.get(str(cue_id))
                if detail is not None and not _is_sentence_start(detail[1], detail[2]):
                    result.error(
                        f"{prefix}.enter.cue_id {cue_id!r} is not at a sentence start; "
                        "manual Next boundaries must start a complete sentence and "
                        "intra-sentence changes belong inside the component"
                    )
                if offset != 0:
                    result.error(
                        f"{prefix}.enter.offset_ms must be 0 when "
                        "storyboard.project.scene_navigation is manual"
                    )
        renderer = shot.get("renderer")
        if not isinstance(renderer, dict):
            result.error(f"{prefix}.renderer must be an object")
        else:
            kind = renderer.get("kind")
            if kind not in allowed_renderers:
                result.error(f"{prefix}.renderer.kind is invalid")
            if kind in {"component", "html"} and not _relative_entry(renderer.get("entry")):
                result.error(f"{prefix}.renderer.entry must be a safe relative path for {kind}")
            variant = renderer.get("variant")
            if variant is not None and (
                not isinstance(variant, str)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", variant) is None
            ):
                result.error(
                    f"{prefix}.renderer.variant must be a safe token of 1 to 64 characters"
                )
        duration = shot.get("duration_ms")
        if duration is not None and (
            not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0
        ):
            result.error(f"{prefix}.duration_ms must be a positive integer")
        if shot.get("exit") is None and duration is None:
            result.error(f"{prefix} needs either exit or duration_ms")

    if "editorial_plan" in data:
        final_shot_id = None
        if shots and isinstance(shots[-1], dict) and _nonempty_string(shots[-1].get("id")):
            final_shot_id = str(shots[-1]["id"])
        _validate_storyboard_editorial_plan(
            data.get("editorial_plan"),
            result,
            segment_ids=segment_ids,
            cue_to_segment=cue_to_segment,
            shot_segment_by_id=shot_segment_by_id,
            final_shot_id=final_shot_id,
            script_hook_segment_id=script_hook_segment_id,
            script_text_by_id=script_text_by_id,
        )

    if support_top_geometry_required and isinstance(project, dict):
        if project.get("ratio") != SUPPORT_TOP_RATIO:
            result.error(
                f"storyboard.project.ratio must be {SUPPORT_TOP_RATIO!r} when support_top is effective"
            )
        for field_name, expected in (
            ("width", SUPPORT_TOP_WIDTH),
            ("height", SUPPORT_TOP_HEIGHT),
        ):
            value = project.get(field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value != expected:
                result.error(
                    f"storyboard.project.{field_name} must be {expected} when support_top is effective"
                )

    asset_ids: set[str] = set()
    for index, asset in enumerate(assets):
        prefix = f"storyboard.assets[{index}]"
        if not isinstance(asset, dict):
            result.error(f"{prefix} must be an object")
            continue
        asset_id = asset.get("id")
        if not _nonempty_string(asset_id):
            result.error(f"{prefix}.id is required")
        elif asset_id in asset_ids:
            result.error(f"Duplicate asset id: {asset_id}")
        else:
            asset_ids.add(asset_id)
        path = asset.get("path")
        if path is not None and not _relative_entry(path):
            result.error(f"{prefix}.path must be a safe relative path")
        digest = asset.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)):
            result.error(f"{prefix}.sha256 must be a lowercase SHA256 digest")
        if asset.get("source_url") and not (asset.get("creator") and asset.get("license")):
            result.error(f"{prefix} has an external source but incomplete creator/license provenance")

    scene_count: int | None = None
    if scene_navigation is not None and not result.errors and script_data_object is not None:
        try:
            _, projected_scenes = _build_scene_projection(script_data_object, data)
        except WorkflowError as exc:
            result.error(str(exc))
        else:
            scene_count = len(projected_scenes)
            for scene in projected_scenes:
                words = count_words(str(scene.get("text", "")))
                if words < 8:
                    result.warn(
                        f"{scene['scene_id']} has only {words} spoken words; confirm this manual "
                        "Next is a meaningful beat rather than a visual micro-change"
                    )
                elif words > 70:
                    result.warn(
                        f"{scene['scene_id']} has {words} spoken words; consider another safe "
                        "sentence-start scene if the visual cannot evolve for that long"
                    )

    result.metrics.update(
        {
            "segment_count": len(segments),
            "cue_count": len(cue_to_segment),
            "shot_count": len(shots),
            "asset_count": len(assets),
            "scene_navigation": scene_navigation,
            "scene_count": scene_count,
        }
    )
    return result


VALIDATORS = {
    "research": validate_research,
    "scope": validate_scope,
    "outline": validate_outline,
    "script": validate_script,
    "storyboard": validate_storyboard,
}


def validate_stage(run_dir: Path | str, stage: str) -> ValidationResult:
    _require_stage(stage)
    return VALIDATORS[stage](Path(run_dir).expanduser().resolve())


def _registered_digest(manifest: Mapping[str, Any], stage: str) -> str | None:
    entry = manifest.get("stages", {}).get(stage, {})
    return entry.get("artifact_sha256") if isinstance(entry, dict) else None


def inspect_stage(run_dir: Path | str, stage: str, manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    _require_stage(stage)
    root = Path(run_dir).expanduser().resolve()
    manifest = manifest or load_manifest(root)
    snapshot = artifact_snapshot(root, stage)
    registration = manifest.get("stages", {}).get(stage)
    approval = manifest.get("approvals", {}).get(stage)
    validation = validate_stage(root, stage)
    predecessor = PREDECESSOR[stage]

    if snapshot["missing"]:
        state = "not_ready"
    elif not isinstance(registration, dict):
        state = "unregistered"
    elif registration.get("artifact_sha256") != snapshot["artifact_sha256"]:
        state = "modified"
    elif not validation.valid:
        state = "invalid"
    else:
        state = "registered"

    dependency_state = None
    if predecessor is not None and isinstance(registration, dict):
        predecessor_info = inspect_stage(root, predecessor, manifest)
        expected = registration.get("input_artifact_sha256")
        current = predecessor_info.get("artifact_sha256")
        predecessor_ready = (
            predecessor_info.get("approval_status") == "approved"
            if predecessor in APPROVAL_STAGES
            else predecessor_info.get("state") == "registered"
        )
        if not predecessor_ready or expected != current:
            dependency_state = "stale"
            if state in {"registered", "invalid"}:
                state = "stale_dependency"
        else:
            dependency_state = "current"

    if stage not in APPROVAL_STAGES:
        approval_status = "not_required"
    elif not isinstance(approval, dict):
        approval_status = "pending"
    elif (
        state != "registered"
        or approval.get("artifact_sha256") != snapshot.get("artifact_sha256")
        or approval.get("input_artifact_sha256")
        != (registration.get("input_artifact_sha256") if isinstance(registration, dict) else None)
        or (predecessor is not None and dependency_state != "current")
    ):
        approval_status = "stale"
    else:
        approval_status = "approved"

    return {
        "stage": stage,
        "state": state,
        "artifact_sha256": snapshot["artifact_sha256"],
        "missing": snapshot["missing"],
        "registered_at": registration.get("registered_at") if isinstance(registration, dict) else None,
        "approval_status": approval_status,
        "approved_at": approval.get("approved_at") if isinstance(approval, dict) else None,
        "dependency": predecessor,
        "dependency_state": dependency_state,
        "validation": validation.to_dict(),
    }


def build_status(run_dir: Path | str) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest = load_manifest(root)
    stages = [inspect_stage(root, stage, manifest) for stage in STAGES]
    next_action = None
    for item in stages:
        if item["state"] != "registered":
            next_action = f"prepare_or_register:{item['stage']}"
            break
        if item["stage"] in APPROVAL_STAGES and item["approval_status"] != "approved":
            next_action = f"approve:{item['stage']}"
            break
    if next_action is None:
        next_action = "package"
    return {
        "manifest_version": manifest["manifest_version"],
        "run_id": manifest.get("run_id"),
        "source": manifest.get("source", {}),
        "updated_at": manifest.get("updated_at"),
        "next_action": next_action,
        "stages": stages,
    }


def require_current_approval(run_dir: Path | str, stage: str, manifest: Mapping[str, Any] | None = None) -> None:
    if stage not in APPROVAL_STAGES:
        raise GateError(f"Stage '{stage}' has no user approval gate")
    info = inspect_stage(run_dir, stage, manifest)
    if info["approval_status"] != "approved":
        raise GateError(
            f"Stage '{stage}' needs a current approval before continuing "
            f"(state={info['state']}, approval={info['approval_status']})"
        )


def register_stage(
    run_dir: Path | str,
    stage: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _require_stage(stage)
    root = Path(run_dir).expanduser().resolve()
    manifest = load_manifest(root)
    predecessor = PREDECESSOR[stage]
    predecessor_digest = None
    if predecessor:
        predecessor_info = inspect_stage(root, predecessor, manifest)
        if predecessor in APPROVAL_STAGES:
            require_current_approval(root, predecessor, manifest)
        elif predecessor_info["state"] != "registered":
            raise GateError(
                f"Stage '{predecessor}' must be current and registered before registering '{stage}'"
            )
        predecessor_digest = artifact_snapshot(root, predecessor)["artifact_sha256"]

    validation = validate_stage(root, stage)
    if not validation.valid:
        raise ArtifactValidationError(stage, validation.errors)
    snapshot = artifact_snapshot(root, stage)
    if snapshot["missing"] or not snapshot["artifact_sha256"]:
        raise ArtifactValidationError(stage, ["Missing canonical artifacts: " + ", ".join(snapshot["missing"])])
    previous = manifest.setdefault("stages", {}).get(stage)
    now = utc_now()
    entry: dict[str, Any] = {
        "status": "registered",
        "registered_at": (
            previous.get("registered_at")
            if isinstance(previous, dict) and previous.get("artifact_sha256") == snapshot["artifact_sha256"]
            else now
        ),
        "checked_at": now,
        "artifact_sha256": snapshot["artifact_sha256"],
        "artifacts": snapshot["files"],
        "input_stage": predecessor,
        "input_artifact_sha256": predecessor_digest,
        "validation": validation.to_dict(),
    }
    if metadata:
        entry["metadata"] = dict(metadata)
    manifest["stages"][stage] = entry
    save_manifest(root, manifest)
    return entry


def approve_stage(
    run_dir: Path | str,
    stage: str,
    *,
    approved_by: str = "user",
    note: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    _require_stage(stage)
    if stage not in APPROVAL_STAGES:
        raise GateError(f"Stage '{stage}' has no user approval gate")
    root = Path(run_dir).expanduser().resolve()
    manifest = load_manifest(root)
    info = inspect_stage(root, stage, manifest)
    if info["state"] != "registered":
        raise GateError(f"Cannot approve stage '{stage}' while its state is {info['state']!r}; register it first")
    digest = info["artifact_sha256"]
    if expected_sha256 and digest != expected_sha256:
        raise GateError(f"Artifact changed before approval: expected {expected_sha256}, current {digest}")
    approval: dict[str, Any] = {
        "status": "approved",
        "approved_at": utc_now(),
        "approved_by": approved_by,
        "artifact_sha256": digest,
        "input_artifact_sha256": manifest["stages"][stage].get("input_artifact_sha256"),
    }
    if note:
        approval["note"] = note
    manifest.setdefault("approvals", {})[stage] = approval
    save_manifest(root, manifest)
    return approval


def _load_script_and_storyboard(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    script = read_json(canonical_paths(run_dir, "script")["script"])
    storyboard = read_json(canonical_paths(run_dir, "storyboard")["storyboard"])
    if not isinstance(script, dict) or not isinstance(storyboard, dict):
        raise WorkflowError("Script and storyboard must be JSON objects")
    return script, storyboard


def _render_teleprompter(script: Mapping[str, Any]) -> str:
    lines = [f"# {script.get('title', 'Teleprompter')}", ""]
    for segment in _script_segments(script):
        if not isinstance(segment, dict):
            continue
        text = _segment_text(segment)
        if text:
            lines.extend([text, ""])
    return "\n".join(lines).rstrip() + "\n"


def materialize_script_teleprompter(run_dir: Path | str) -> dict[str, Any]:
    """Build the Human Host review view from canonical spoken text."""
    root = Path(run_dir).expanduser().resolve()
    manifest = load_manifest(root)
    require_current_approval(root, "outline", manifest)
    paths = canonical_paths(root, "script")
    script = read_json(paths["script"])
    if not isinstance(script, dict):
        raise WorkflowError("script/final.json must contain a JSON object")
    if not _nonempty_string(script.get("title")):
        raise WorkflowError("script/final.json needs a title before materializing the teleprompter")
    segments = script.get("segments")
    if not isinstance(segments, list) or not segments:
        raise WorkflowError("script/final.json needs at least one segment before materializing the teleprompter")
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise WorkflowError(f"script.segments[{index}] must be an object")
        if "voiceover" in segment:
            raise WorkflowError(
                f"script.segments[{index}].voiceover is not supported; use the canonical text field"
            )
        if not _nonempty_string(segment.get("text")):
            raise WorkflowError(f"script.segments[{index}].text is required before materializing")
    rendered = _render_teleprompter(script)
    atomic_write_text(paths["teleprompter"], rendered)
    return {
        "path": str(paths["teleprompter"].relative_to(root)).replace("\\", "/"),
        "sha256": sha256_file(paths["teleprompter"]),
        "word_count": count_words(
            " ".join(
                _segment_text(item) for item in _script_segments(script) if isinstance(item, dict)
            )
        ),
    }


def _render_producer_script(script: Mapping[str, Any], storyboard: Mapping[str, Any]) -> str:
    board_segments = {
        str(item.get("id")): item
        for item in storyboard.get("segments", [])
        if isinstance(item, dict) and item.get("id")
    }
    shots_by_segment: dict[str, list[dict[str, Any]]] = {}
    for shot in storyboard.get("shots", []):
        if isinstance(shot, dict) and shot.get("segment_id"):
            shots_by_segment.setdefault(str(shot["segment_id"]), []).append(shot)
    lines = [f"# Producer Script — {script.get('title', '')}", ""]
    for index, segment in enumerate(_script_segments(script), 1):
        if not isinstance(segment, dict):
            continue
        segment_id = str(segment.get("id", f"segment-{index:02d}"))
        heading = segment.get("heading") or segment.get("title") or f"Segment {index}"
        lines.extend([f"## {heading} `{segment_id}`", "", _segment_text(segment), ""])
        board_segment = board_segments.get(segment_id, {})
        cues = {
            str(item.get("id")): str(item.get("phrase", ""))
            for item in board_segment.get("cues", [])
            if isinstance(item, dict) and item.get("id")
        }
        segment_shots = shots_by_segment.get(segment_id, [])
        producer_notes = segment.get("producer_notes")
        if isinstance(producer_notes, dict) and producer_notes:
            lines.extend(["### Producer notes", ""])
            for category in ("delivery", "pronunciation", "camera", "evidence"):
                value = producer_notes.get(category)
                if isinstance(value, list):
                    note = "; ".join(str(item).strip() for item in value if str(item).strip())
                else:
                    note = str(value).strip() if value is not None else ""
                if note:
                    lines.append(f"- **{category.title()}:** {note}")
            lines.append("")
        if segment_shots:
            lines.extend(["### Visual cues", ""])
            for shot in segment_shots:
                enter = shot.get("enter", {}) if isinstance(shot.get("enter"), dict) else {}
                cue_id = str(enter.get("cue_id", ""))
                offset = int(enter.get("offset_ms", 0)) if isinstance(enter.get("offset_ms", 0), int) else 0
                renderer = shot.get("renderer", {}) if isinstance(shot.get("renderer"), dict) else {}
                offset_text = f" ({offset:+d} ms)" if offset else ""
                lines.append(
                    f"- On **\"{cues.get(cue_id, cue_id)}\"**{offset_text}: "
                    f"`{shot.get('id', '')}` · {renderer.get('kind', '')} · {shot.get('intent', '')}"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _normalize_spoken_text(text: str) -> str:
    return " ".join(str(text).split())


def _canonical_spoken_text(script: Mapping[str, Any]) -> str:
    return " ".join(
        _segment_text(segment).strip()
        for segment in _script_segments(script)
        if isinstance(segment, dict) and _segment_text(segment).strip()
    )


def _cue_phrase_start(text: str, phrase: str, *, shot_id: str, cue_id: str) -> int:
    parts = [part for part in re.split(r"\s+", phrase.strip()) if part]
    if not parts:
        raise WorkflowError(f"Shot {shot_id!r} enter cue {cue_id!r} has an empty phrase")
    pattern = r"\s+".join(re.escape(part) for part in parts)
    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
    if len(matches) != 1:
        raise WorkflowError(
            f"Shot {shot_id!r} enter cue {cue_id!r} must resolve exactly once in canonical "
            f"script text; found {len(matches)}"
        )
    return matches[0].start()


def _build_scene_projection(
    script: Mapping[str, Any], storyboard: Mapping[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    script_segments = [item for item in _script_segments(script) if isinstance(item, dict)]
    if not script_segments:
        raise WorkflowError("Cannot build scene-aware teleprompter without canonical script segments")

    canonical_parts: list[str] = []
    segment_offsets: dict[str, int] = {}
    segment_texts: dict[str, str] = {}
    segment_ranges: list[tuple[str, int, int]] = []
    cursor = 0
    for index, segment in enumerate(script_segments):
        segment_id = str(segment.get("id", "")).strip()
        text = _segment_text(segment).strip()
        if not segment_id or not text:
            raise WorkflowError(f"Canonical script segment {index + 1} needs a non-empty id and text")
        if segment_id in segment_offsets:
            raise WorkflowError(f"Duplicate canonical script segment id: {segment_id!r}")
        if canonical_parts:
            cursor += 1
        segment_offsets[segment_id] = cursor
        segment_texts[segment_id] = text
        canonical_parts.append(text)
        cursor += len(text)
        segment_ranges.append((segment_id, segment_offsets[segment_id], cursor))
    canonical = " ".join(canonical_parts)

    board_segments: dict[str, Mapping[str, Any]] = {}
    for item in storyboard.get("segments", []):
        if isinstance(item, dict) and _nonempty_string(item.get("id")):
            board_segments[str(item["id"])] = item
    shots = storyboard.get("shots")
    if not isinstance(shots, list):
        raise WorkflowError("storyboard.shots must be an array for scene-aware packaging")

    anchor_groups: list[dict[str, Any]] = []
    previous_anchor = -1
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise WorkflowError(f"storyboard.shots[{index}] must be an object")
        shot_id = str(shot.get("id", "")).strip()
        segment_id = str(shot.get("segment_id", "")).strip()
        enter = shot.get("enter")
        if not shot_id or segment_id not in segment_offsets or not isinstance(enter, dict):
            raise WorkflowError(
                f"Storyboard shot {index + 1} needs an id, canonical segment_id, and enter cue"
            )
        cue_id = str(enter.get("cue_id", "")).strip()
        board_segment = board_segments.get(segment_id)
        if not cue_id or not isinstance(board_segment, Mapping):
            raise WorkflowError(f"Shot {shot_id!r} enter cue cannot be resolved")
        cue_matches = [
            cue
            for cue in board_segment.get("cues", [])
            if isinstance(cue, dict) and str(cue.get("id", "")) == cue_id
        ]
        if len(cue_matches) != 1 or not _nonempty_string(cue_matches[0].get("phrase")):
            raise WorkflowError(
                f"Shot {shot_id!r} enter cue {cue_id!r} must identify one non-empty cue phrase"
            )
        phrase = str(cue_matches[0]["phrase"])
        local_anchor = _cue_phrase_start(
            segment_texts[segment_id], phrase, shot_id=shot_id, cue_id=cue_id
        )
        anchor = segment_offsets[segment_id] + local_anchor
        if anchor < previous_anchor:
            raise WorkflowError(
                "Storyboard shot enter cues must be globally ordered with non-decreasing anchors; "
                f"{shot_id!r} resolves to {anchor} after {previous_anchor}"
            )
        anchor_entry = {
            "shot_id": shot_id,
            "segment_id": segment_id,
            "enter_cue_id": cue_id,
            "enter_phrase": phrase,
            "anchor": anchor,
        }
        if anchor_groups and anchor == previous_anchor:
            group = anchor_groups[-1]
            group["shot_ids"].append(shot_id)
            group["segment_ids"].append(segment_id)
            group["enter_cue_ids"].append(cue_id)
            group["enter_phrases"].append(phrase)
        else:
            anchor_groups.append(
                {
                    **anchor_entry,
                    "shot_ids": [shot_id],
                    "segment_ids": [segment_id],
                    "enter_cue_ids": [cue_id],
                    "enter_phrases": [phrase],
                }
            )
        previous_anchor = anchor

    def range_segment_ids(start: int, end: int) -> list[str]:
        return [
            segment_id
            for segment_id, segment_start, segment_end in segment_ranges
            if segment_start < end and segment_end > start
        ]

    scene_specs: list[dict[str, Any]] = []
    if not anchor_groups:
        scene_specs.append(
            {
                "kind": "host_only",
                "host_only": True,
                "label": "Host-only · toàn bộ kịch bản không có cảnh minh họa",
                "start": 0,
                "end": len(canonical),
                "shot_id": None,
                "shot_ids": [],
                "segment_ids": [item[0] for item in segment_ranges],
                "enter_cue_id": None,
                "enter_cue_ids": [],
                "enter_phrase": None,
                "enter_phrases": [],
            }
        )
    else:
        first_anchor = int(anchor_groups[0]["anchor"])
        if first_anchor > 0:
            scene_specs.append(
                {
                    "kind": "host_only",
                    "host_only": True,
                    "label": "Host-only · mở đầu trước cảnh minh họa đầu tiên",
                    "start": 0,
                    "end": first_anchor,
                    "shot_id": None,
                    "shot_ids": [],
                    "segment_ids": range_segment_ids(0, first_anchor),
                    "enter_cue_id": None,
                    "enter_cue_ids": [],
                    "enter_phrase": None,
                    "enter_phrases": [],
                }
            )
        for index, anchor in enumerate(anchor_groups):
            start = int(anchor["anchor"])
            end = (
                int(anchor_groups[index + 1]["anchor"])
                if index + 1 < len(anchor_groups)
                else len(canonical)
            )
            scene_specs.append(
                {
                    "kind": "shot",
                    "host_only": False,
                    "label": f"Minh họa · {', '.join(anchor['shot_ids'])}",
                    "start": start,
                    "end": end,
                    "shot_id": anchor["shot_id"],
                    "shot_ids": list(anchor["shot_ids"]),
                    "segment_ids": range_segment_ids(start, end),
                    "enter_cue_id": anchor["enter_cue_id"],
                    "enter_cue_ids": list(anchor["enter_cue_ids"]),
                    "enter_phrase": anchor["enter_phrase"],
                    "enter_phrases": list(anchor["enter_phrases"]),
                }
            )

    scenes: list[dict[str, Any]] = []
    for index, spec in enumerate(scene_specs):
        start = int(spec["start"])
        end = int(spec["end"])
        text = canonical[start:end]
        if not text:
            raise WorkflowError(f"Scene {index + 1:02d} has no canonical spoken text")
        segment_ids = list(spec["segment_ids"])
        scene_id = f"scene-{index + 1:02d}"
        if spec["host_only"]:
            scene_id += "-host-only"
        scenes.append(
            {
                "scene_id": scene_id,
                "scene_number": index + 1,
                "kind": spec["kind"],
                "host_only": spec["host_only"],
                "label": spec["label"],
                "shot_id": spec["shot_id"],
                "shot_ids": list(spec["shot_ids"]),
                "segment_id": segment_ids[0] if segment_ids else None,
                "segment_ids": segment_ids,
                "enter_cue_id": spec["enter_cue_id"],
                "enter_cue_ids": list(spec["enter_cue_ids"]),
                "enter_phrase": spec["enter_phrase"],
                "enter_phrases": list(spec["enter_phrases"]),
                "text": text,
                "text_start": start,
                "text_end": end,
            }
        )

    projected = "".join(str(scene["text"]) for scene in scenes)
    if projected != canonical:
        raise WorkflowError(
            "Scene projection drifted from canonical spoken text byte-for-byte; packaging would "
            "omit, duplicate, or reorder characters"
        )
    return canonical, scenes


def _karaoke_configuration(storyboard: Mapping[str, Any], *, fallback_wpm: int) -> dict[str, Any]:
    project = storyboard.get("project")
    if not isinstance(project, Mapping):
        raise WorkflowError("storyboard.project must be an object before packaging")
    explicit = "karaoke_caption" in project
    raw = project.get("karaoke_caption") if explicit else {"enabled": False}
    if not isinstance(raw, Mapping):
        raise WorkflowError("storyboard.project.karaoke_caption must be an object when present")
    unknown = sorted(set(raw) - KARAOKE_CONFIG_KEYS)
    if unknown:
        raise WorkflowError(
            "storyboard.project.karaoke_caption has unknown field: " + unknown[0]
        )
    if "enabled" not in raw or not isinstance(raw.get("enabled"), bool):
        raise WorkflowError("storyboard.project.karaoke_caption.enabled must be a boolean")

    config = {
        **DEFAULT_KARAOKE_CAPTION,
        "pause_ms": dict(DEFAULT_KARAOKE_CAPTION["pause_ms"]),
    }
    _ = fallback_wpm  # Package narration WPM does not change karaoke's 150 WPM default.
    config.update({key: value for key, value in raw.items() if key != "pause_ms"})
    raw_pauses = raw.get("pause_ms", {})
    if not isinstance(raw_pauses, Mapping):
        raise WorkflowError(
            "storyboard.project.karaoke_caption.pause_ms must be an object when present"
        )
    unknown_pauses = sorted(set(raw_pauses) - KARAOKE_PAUSE_KEYS)
    if unknown_pauses:
        raise WorkflowError(
            "storyboard.project.karaoke_caption.pause_ms has unknown field: "
            + unknown_pauses[0]
        )
    config["pause_ms"].update(raw_pauses)

    if config.get("placement") != "capture_stage_bottom":
        raise WorkflowError(
            'storyboard.project.karaoke_caption.placement must be "capture_stage_bottom"'
        )
    if config.get("scene_advance") != "manual":
        raise WorkflowError('storyboard.project.karaoke_caption.scene_advance must be "manual"')

    project_height = project.get("height", SUPPORT_TOP_HEIGHT)
    if not isinstance(project_height, int) or isinstance(project_height, bool) or project_height <= 0:
        project_height = SUPPORT_TOP_HEIGHT
    bottom_margin = config.get("bottom_margin_px")
    if (
        not isinstance(bottom_margin, int)
        or isinstance(bottom_margin, bool)
        or bottom_margin < 0
        or bottom_margin >= project_height
    ):
        raise WorkflowError(
            "storyboard.project.karaoke_caption.bottom_margin_px must be an integer "
            f"from 0 to {project_height - 1}"
        )
    if config.get("max_lines") not in {1, 2} or isinstance(config.get("max_lines"), bool):
        raise WorkflowError("storyboard.project.karaoke_caption.max_lines must be 1 or 2")
    reading_wpm = config.get("reading_wpm")
    if (
        not isinstance(reading_wpm, int)
        or isinstance(reading_wpm, bool)
        or reading_wpm < 60
        or reading_wpm > 1000
    ):
        raise WorkflowError(
            "storyboard.project.karaoke_caption.reading_wpm must be an integer from 60 to 1000"
        )

    for key in KARAOKE_PAUSE_KEYS:
        value = config["pause_ms"].get(key)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            or value > 10_000
        ):
            raise WorkflowError(
                f"storyboard.project.karaoke_caption.pause_ms.{key} must be an integer "
                "from 0 to 10000"
            )

    end_indicator = config.get("end_indicator")
    if (
        not _nonempty_string(end_indicator)
        or len(str(end_indicator)) > 32
        or any(character in "[]<>" for character in str(end_indicator))
        or any(ord(character) < 32 or ord(character) == 127 for character in str(end_indicator))
    ):
        raise WorkflowError(
            "storyboard.project.karaoke_caption.end_indicator must be a single-line string "
            "of 1 to 32 safe characters"
        )

    if config["enabled"] and (
        project.get("width") != SUPPORT_TOP_WIDTH or project.get("height") != SUPPORT_TOP_HEIGHT
    ):
        raise WorkflowError(
            "storyboard.project.karaoke_caption enabled=true requires the 432 x 768 "
            "desktop-capture stage"
        )
    return config


def _render_recording_teleprompter(
    script: Mapping[str, Any], scenes: Sequence[Mapping[str, Any]], *, end_indicator: str
) -> str:
    lines = [f"# {script.get('title', 'Teleprompter')}", ""]
    for index, scene in enumerate(scenes):
        heading = f"## Cảnh {index + 1:02d}"
        if scene.get("host_only"):
            heading += " — HOST-ONLY"
        lines.extend([heading, "", str(scene["text"]), ""])
        if index + 1 < len(scenes):
            lines.extend([f"[BẤM {end_indicator}]", ""])
    return "\n".join(lines).rstrip() + "\n"


def _punctuation_pause(token: str, pauses: Mapping[str, int]) -> tuple[str | None, int]:
    if re.search(r'''[.!?…。！？]+["'”’)}\]]*$''', token):
        return "sentence", int(pauses["sentence"])
    if re.search(r'''[:;：；]["'”’)}\]]*$''', token):
        return "clause", int(pauses["clause"])
    if re.search(r'''[,，]["'”’)}\]]*$''', token):
        return "comma", int(pauses["comma"])
    return None, 0


def _build_karaoke_captions(
    scenes: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    reading_wpm = int(config["reading_wpm"])
    word_duration_ms = max(1, int(60_000 / reading_wpm + 0.5))
    pauses = config["pause_ms"]
    timeline_ms = 0
    rendered_scenes: list[dict[str, Any]] = []
    for scene_index, scene in enumerate(scenes):
        text = str(scene["text"])
        matches = list(re.finditer(r"\S+", text, flags=re.UNICODE))
        if not matches:
            raise WorkflowError(f"{scene['scene_id']} has no spoken words for karaoke timing")
        scene_start_ms = timeline_ms
        scene_cursor_ms = 0
        words: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []
        chunk_start_char = 0
        chunk_start_word = 0
        for word_index, match in enumerate(matches):
            next_start = matches[word_index + 1].start() if word_index + 1 < len(matches) else len(text)
            punctuation_kind, punctuation_ms = _punctuation_pause(match.group(0), pauses)
            scene_end_ms = int(pauses["scene_end"]) if word_index + 1 == len(matches) else 0
            word_start_ms = scene_cursor_ms
            spoken_end_ms = word_start_ms + word_duration_ms
            hold_end_ms = spoken_end_ms + punctuation_ms
            words.append(
                {
                    "index": word_index,
                    "text": match.group(0),
                    "start_ms": word_start_ms,
                    "end_ms": spoken_end_ms,
                    "spoken_end_ms": spoken_end_ms,
                    "hold_end_ms": hold_end_ms,
                    "punctuation": punctuation_kind,
                    "punctuation_pause_ms": punctuation_ms,
                    "scene_end_pause_ms": scene_end_ms,
                    "pause_after_ms": punctuation_ms + scene_end_ms,
                    "absolute_start_ms": scene_start_ms + word_start_ms,
                    "absolute_spoken_end_ms": scene_start_ms + spoken_end_ms,
                    "absolute_hold_end_ms": scene_start_ms + hold_end_ms,
                }
            )
            scene_cursor_ms = hold_end_ms
            if punctuation_kind is not None or word_index + 1 == len(matches):
                chunk_text = text[chunk_start_char:next_start].strip()
                if chunk_text:
                    chunks.append(
                        {
                            "chunk_id": f"{scene['scene_id']}-chunk-{len(chunks) + 1:02d}",
                            "text": chunk_text,
                            "start_ms": words[chunk_start_word]["start_ms"],
                            "end_ms": hold_end_ms + scene_end_ms,
                            "absolute_start_ms": (
                                scene_start_ms + words[chunk_start_word]["start_ms"]
                            ),
                            "absolute_end_ms": scene_start_ms + hold_end_ms + scene_end_ms,
                            "word_start_index": chunk_start_word,
                            "word_end_index": word_index,
                            "words": [dict(item) for item in words[chunk_start_word : word_index + 1]],
                        }
                    )
                chunk_start_char = next_start
                chunk_start_word = word_index + 1

        spoken_complete_ms = scene_cursor_ms
        scene_duration_ms = spoken_complete_ms + int(pauses["scene_end"])
        timeline_ms = scene_start_ms + scene_duration_ms

        rendered_scenes.append(
            {
                "scene_id": scene["scene_id"],
                "scene_number": scene["scene_number"],
                "kind": scene.get("kind", "shot"),
                "host_only": bool(scene.get("host_only", False)),
                "label": scene.get("label"),
                "shot_id": scene["shot_id"],
                "shot_ids": list(scene.get("shot_ids", [scene["shot_id"]])),
                "segment_id": scene["segment_id"],
                "segment_ids": list(scene.get("segment_ids", [scene["segment_id"]])),
                "enter_cue_id": scene["enter_cue_id"],
                "enter_cue_ids": list(scene.get("enter_cue_ids", [scene["enter_cue_id"]])),
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "start_ms": scene_start_ms,
                "end_ms": timeline_ms,
                "spoken_complete_ms": spoken_complete_ms,
                "duration_ms": scene_duration_ms,
                "advance_indicator": (
                    str(config["end_indicator"]) if scene_index + 1 < len(scenes) else None
                ),
                "chunks": chunks,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": True,
        "placement": config["placement"],
        "bottom_margin_px": config["bottom_margin_px"],
        "max_lines": config["max_lines"],
        "reading_wpm": reading_wpm,
        "word_duration_ms": word_duration_ms,
        "pause_ms": dict(pauses),
        "scene_advance": config["scene_advance"],
        "end_indicator": config["end_indicator"],
        "scene_count": len(rendered_scenes),
        "total_estimated_ms": timeline_ms,
        "scenes": rendered_scenes,
    }


def package_creator_pack(run_dir: Path | str, *, words_per_minute: int = 150) -> dict[str, Any]:
    if words_per_minute <= 0:
        raise WorkflowError("words_per_minute must be positive")
    root = Path(run_dir).expanduser().resolve()
    manifest = load_manifest(root)
    require_current_approval(root, "storyboard", manifest)
    validations = {stage: validate_stage(root, stage) for stage in STAGES}
    invalid = {stage: value.errors for stage, value in validations.items() if not value.valid}
    if invalid:
        flattened = [f"{stage}: {message}" for stage, messages in invalid.items() for message in messages]
        raise ArtifactValidationError("package", flattened)

    script, storyboard = _load_script_and_storyboard(root)
    pack = root / "creator-pack"
    teleprompter_clean_path = pack / "teleprompter-clean.md"
    teleprompter_path = pack / "teleprompter-script.md"
    karaoke_path = pack / "karaoke_captions.json"
    producer_path = pack / "producer-script.md"
    report_path = pack / "quality_report.json"
    script_teleprompter = canonical_paths(root, "script")["teleprompter"]
    canonical_bytes = script_teleprompter.read_bytes()
    canonical_text, scenes = _build_scene_projection(script, storyboard)
    karaoke_config = _karaoke_configuration(storyboard, fallback_wpm=words_per_minute)

    _atomic_write_bytes(teleprompter_clean_path, canonical_bytes)
    atomic_write_text(
        teleprompter_path,
        _render_recording_teleprompter(
            script, scenes, end_indicator=str(karaoke_config["end_indicator"])
        ),
    )
    atomic_write_text(producer_path, _render_producer_script(script, storyboard))
    karaoke_captions: dict[str, Any] | None = None
    if karaoke_config["enabled"]:
        karaoke_captions = _build_karaoke_captions(scenes, karaoke_config)
        atomic_write_json(karaoke_path, karaoke_captions)
    elif karaoke_path.exists():
        karaoke_path.unlink()

    projected_text = "".join(str(scene["text"]) for scene in scenes)
    if projected_text != canonical_text:
        raise WorkflowError(
            "Packaged scene text does not exactly cover canonical spoken text byte-for-byte"
        )
    if teleprompter_clean_path.read_bytes() != canonical_bytes:
        raise WorkflowError("teleprompter-clean.md is not an exact copy of the approved script gate")

    all_text = canonical_text
    word_count = count_words(all_text)
    status = build_status(root)
    pre_report_outputs = {
        "teleprompter_clean": str(teleprompter_clean_path.relative_to(root)).replace("\\", "/"),
        "teleprompter": str(teleprompter_path.relative_to(root)).replace("\\", "/"),
        "producer_script": str(producer_path.relative_to(root)).replace("\\", "/"),
    }
    if karaoke_captions is not None:
        pre_report_outputs["karaoke_captions"] = str(karaoke_path.relative_to(root)).replace("\\", "/")
    output_hashes = {
        name: sha256_file(root / rel) for name, rel in pre_report_outputs.items()
    }
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "run_id": manifest.get("run_id"),
        "passed": True,
        "metrics": {
            "word_count": word_count,
            "estimated_duration_seconds": round(word_count / words_per_minute * 60, 1),
            "words_per_minute": words_per_minute,
            "segment_count": len(_script_segments(script)),
            "shot_count": len(storyboard.get("shots", [])),
            "scene_count": len(scenes),
            "karaoke_total_estimated_ms": (
                karaoke_captions["total_estimated_ms"] if karaoke_captions is not None else None
            ),
        },
        "spoken_projection": {
            "exact_match": True,
            "normalized_match": True,
            "canonical_text_sha256": hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
            "scene_text_sha256": hashlib.sha256(
                "".join(str(scene["text"]) for scene in scenes).encode("utf-8")
            ).hexdigest(),
            "scene_count": len(scenes),
        },
        "karaoke_caption": {
            "enabled": bool(karaoke_config["enabled"]),
            "configuration": dict(karaoke_config),
        },
        "output_hashes": output_hashes,
        "validations": {stage: value.to_dict() for stage, value in validations.items()},
        "approvals": {
            item["stage"]: {
                "status": item["approval_status"],
                "artifact_sha256": item["artifact_sha256"],
            }
            for item in status["stages"]
        },
        "warnings": [warning for value in validations.values() for warning in value.warnings],
    }
    atomic_write_json(report_path, report)
    outputs = dict(pre_report_outputs)
    outputs["quality_report"] = str(report_path.relative_to(root)).replace("\\", "/")
    manifest["package"] = {
        "generated_at": report["generated_at"],
        "outputs": {
            name: {"path": rel, "sha256": sha256_file(root / rel)} for name, rel in outputs.items()
        },
    }
    save_manifest(root, manifest)
    return {"outputs": outputs, "quality_report": report}


def _json_argument(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    candidate = Path(value)
    try:
        text = candidate.read_text(encoding="utf-8") if candidate.is_file() else value
        parsed = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise argparse.ArgumentTypeError(f"Expected a JSON object or JSON file path: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("Expected a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive Human Host content workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a versioned run manifest")
    init_parser.add_argument("--run-dir", required=True, type=Path)
    init_parser.add_argument("--source-url")
    init_parser.add_argument("--config-json", type=_json_argument, default={})

    status_parser = subparsers.add_parser("status", help="Show gates, staleness, and the next action")
    status_parser.add_argument("--run-dir", required=True, type=Path)

    register_parser = subparsers.add_parser("register", help="Validate and register canonical stage artifacts")
    register_parser.add_argument("--run-dir", required=True, type=Path)
    register_parser.add_argument("--stage", required=True, choices=STAGES)
    register_parser.add_argument("--metadata-json", type=_json_argument, default={})

    approve_parser = subparsers.add_parser("approve", help="Approve the current artifact digest")
    approve_parser.add_argument("--run-dir", required=True, type=Path)
    approve_parser.add_argument("--stage", required=True, choices=APPROVAL_STAGES)
    approve_parser.add_argument("--approved-by", default="user")
    approve_parser.add_argument("--note")
    approve_parser.add_argument("--expected-sha256")

    validate_parser = subparsers.add_parser("validate", help="Validate one stage or all canonical artifacts")
    validate_parser.add_argument("--run-dir", required=True, type=Path)
    validate_parser.add_argument("--stage", choices=STAGES)

    materialize_parser = subparsers.add_parser(
        "materialize-script", help="Build the clean Human Host teleprompter view for script review"
    )
    materialize_parser.add_argument("--run-dir", required=True, type=Path)

    package_parser = subparsers.add_parser("package", help="Build clean teleprompter and producer outputs")
    package_parser.add_argument("--run-dir", required=True, type=Path)
    package_parser.add_argument("--words-per-minute", type=int, default=150)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Windows terminals commonly inherit a legacy code page such as cp1252.
    # Creator-pack output intentionally contains Vietnamese text and symbols
    # such as the manual scene marker (→), so keep the CLI boundary UTF-8.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            output = init_run(args.run_dir, source_url=args.source_url, configuration=args.config_json)
        elif args.command == "status":
            output = build_status(args.run_dir)
        elif args.command == "register":
            output = register_stage(args.run_dir, args.stage, metadata=args.metadata_json)
        elif args.command == "approve":
            output = approve_stage(
                args.run_dir,
                args.stage,
                approved_by=args.approved_by,
                note=args.note,
                expected_sha256=args.expected_sha256,
            )
        elif args.command == "validate":
            stages: Iterable[str] = (args.stage,) if args.stage else STAGES
            results = {stage: validate_stage(args.run_dir, stage).to_dict() for stage in stages}
            output = {"valid": all(item["valid"] for item in results.values()), "stages": results}
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if output["valid"] else 2
        elif args.command == "materialize-script":
            output = materialize_script_teleprompter(args.run_dir)
        elif args.command == "package":
            output = package_creator_pack(args.run_dir, words_per_minute=args.words_per_minute)
        else:  # pragma: no cover - argparse enforces the command
            parser.error(f"Unsupported command: {args.command}")
            return 2
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
