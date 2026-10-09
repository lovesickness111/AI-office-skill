#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research-only YouTube ingestion for the Human Host workflow.

The creative stages intentionally do not live here. This command produces the
timestamped transcript, source analysis/playbook, and claim ledger, then
registers only the ``research`` stage in ``run_manifest.json``.

Examples:
  python youtube_to_content.py research --url URL --run-dir RUN_DIR
  python youtube_to_content.py transcript --url URL --run-dir RUN_DIR
  python youtube_to_content.py analyze --url URL --run-dir RUN_DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import workflow
except ModuleNotFoundError:  # Makes importlib-based tests independent of cwd.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import workflow


TRANSCRIPT_PROMPT_VERSION = "2.0"
TRANSCRIPT_SCHEMA_VERSION = "1.0"
ANALYSIS_PROMPT_VERSION = "2.1"
ANALYSIS_SCHEMA_VERSION = "1.0"
CACHE_SCHEMA_VERSION = "1.0"
DEFAULT_MODEL = "gemini-2.5-flash"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()

TRANSCRIPT_PROMPT = """
Bạn là chuyên gia transcription. Hãy nghe toàn bộ video YouTube và xuất bản
transcript đầy đủ theo thời gian.

Yêu cầu bắt buộc:
1. Không tóm tắt hoặc bỏ qua lập luận, ví dụ, tên công cụ và thuật ngữ.
2. Giữ ngôn ngữ gốc của người nói.
3. Mỗi đoạn bắt đầu bằng mốc [MM:SS] hoặc [HH:MM:SS].
4. Khi slide, demo, sơ đồ hoặc terminal quan trọng xuất hiện, thêm một dòng
   [VISUAL: mô tả ngắn].
5. Chỉ trả transcript, không thêm lời mở đầu hoặc kết luận của trợ lý.
""".strip()

ANALYSIS_PROMPT = """
Bạn là biên tập viên nghiên cứu video công nghệ. Hãy đọc transcript và quan sát
video để lập một bản phân tích có thể kiểm chứng. Đây chỉ là giai đoạn nghiên
cứu; không viết kịch bản mới và không đề xuất scene sáng tạo.

Trả về đúng một JSON object, không bọc markdown, theo cấu trúc:
{
  "schema_version": "1.0",
  "source": {
    "title": "...", "author": "...", "kind": "youtube",
    "locator": "URL video", "duration": "...", "language": "..."
  },
  "topic": "chủ đề trong một câu",
  "core_thesis": "luận điểm trung tâm",
  "audience": "khán giả mục tiêu",
  "hook": {
    "timestamp": "MM:SS-MM:SS",
    "type": "pain_point | question | story | demo_first | bold_promise | myth_bust | other",
    "verbatim_excerpt": "trích dẫn ngắn",
    "why_it_works": "cơ chế giữ chân",
    "reusable_pattern": "công thức trình bày trừu tượng"
  },
  "flow": [{
    "id": "source-beat-01",
    "beat": "hook | problem | stakes | reveal | explain | demo | proof | objection | recap | cta",
    "t_start": "MM:SS",
    "t_end": "MM:SS",
    "purpose": "vai trò của beat",
    "technique": "thủ pháp trình bày",
    "key_claim": "luận điểm",
    "source_example": "ví dụ thật trong nguồn"
  }],
  "pacing": {
    "total_duration": "...",
    "avg_seconds_per_beat": 0,
    "pattern_interrupts": ["mốc thời gian + mô tả"]
  },
  "rhetorical_devices": ["..."],
  "key_facts": [{
    "claim": "fact hoặc phát biểu kỹ thuật cần giữ chính xác",
    "evidence": "mốc thời gian và bằng chứng trong nguồn",
    "confidence": "high | medium | low",
    "must_keep": true
  }],
  "visual_moments": [{"t": "MM:SS", "description": "..."}],
  "weaknesses": ["điểm thiếu hoặc cần kiểm chứng thêm"]
}

Chỉ ghi những gì có trong nguồn. Không bịa số liệu. Nếu chưa đủ bằng chứng,
đánh confidence thấp và nói rõ khoảng trống trong evidence.
""".strip()

TIMESTAMP_VALUE_RE = re.compile(r"(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?!\d)")


class ResearchError(RuntimeError):
    """A user-correctable research phase error."""


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}") + 1
        if start < 0 or end <= start:
            raise ResearchError("Gemini response did not contain a JSON object")
        try:
            value = json.loads(cleaned[start:end])
        except json.JSONDecodeError as exc:
            raise ResearchError(f"Gemini returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ResearchError("Gemini analysis must be a JSON object")
    return value


def make_client() -> Any:
    """Create Gemini client lazily; callers must first exhaust cache checks."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ResearchError("GEMINI_API_KEY is required because this phase is not cached")
    try:
        from google import genai
    except ImportError as exc:
        raise ResearchError("Install the 'google-genai' package to call Gemini") from exc
    return genai.Client(api_key=api_key)


def generate_content(
    client: Any,
    *,
    model: str,
    parts: list[dict[str, Any]],
    json_mode: bool,
    label: str,
    retries: int,
) -> str:
    """Call one explicit model; changing the model always changes the cache key."""
    try:
        from google.genai import types
    except ImportError as exc:
        raise ResearchError("Install the 'google-genai' package to call Gemini") from exc
    config = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(model=model, contents=parts, config=config)
            text = getattr(response, "text", None)
            if text:
                return str(text)
            last_error = ResearchError("Gemini returned an empty response")
        except Exception as exc:  # noqa: BLE001 - retried then surfaced with context
            last_error = exc
        if attempt < retries:
            time.sleep(min(2**attempt, 8))
    raise ResearchError(f"{label} failed after {retries} attempt(s): {last_error}")


def video_part(url: str) -> dict[str, Any]:
    return {"file_data": {"file_uri": url, "mime_type": "video/mp4"}}


class LazyClient:
    def __init__(self, factory: Callable[[], Any] = make_client):
        self.factory = factory
        self.client: Any | None = None

    def get(self) -> Any:
        if self.client is None:
            self.client = self.factory()
        return self.client


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_fingerprint(
    *,
    stage: str,
    url: str,
    model: str,
    prompt_text: str,
    prompt_version: str,
    schema_version: str,
    config: Mapping[str, Any],
    upstream_sha256: str,
) -> tuple[str, dict[str, Any]]:
    payload = {
        "stage": stage,
        "url": url,
        "model": model,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "config": dict(config),
        "upstream_sha256": upstream_sha256,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest(), payload


def cache_path(run_dir: Path) -> Path:
    return run_dir / "research" / "research_cache.json"


def load_cache(run_dir: Path) -> dict[str, Any]:
    path = cache_path(run_dir)
    if not path.is_file():
        return {"schema_version": CACHE_SCHEMA_VERSION, "stages": {}}
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": CACHE_SCHEMA_VERSION, "stages": {}}
    if not isinstance(cache, dict) or cache.get("schema_version") != CACHE_SCHEMA_VERSION:
        return {"schema_version": CACHE_SCHEMA_VERSION, "stages": {}}
    if not isinstance(cache.get("stages"), dict):
        cache["stages"] = {}
    return cache


def save_cache(run_dir: Path, cache: Mapping[str, Any]) -> None:
    workflow.atomic_write_json(cache_path(run_dir), dict(cache))


def _artifact_hashes(run_dir: Path, relative_paths: Sequence[str]) -> dict[str, str] | None:
    hashes: dict[str, str] = {}
    for relative in relative_paths:
        path = run_dir / relative
        if not path.is_file():
            return None
        hashes[relative] = workflow.sha256_file(path)
    return hashes


def cache_hit(
    run_dir: Path,
    cache: Mapping[str, Any],
    *,
    stage: str,
    fingerprint: str,
    artifacts: Sequence[str],
) -> bool:
    entry = cache.get("stages", {}).get(stage, {})
    if not isinstance(entry, dict) or entry.get("fingerprint") != fingerprint:
        return False
    hashes = _artifact_hashes(run_dir, artifacts)
    return hashes is not None and hashes == entry.get("artifacts")


def update_cache_entry(
    run_dir: Path,
    cache: dict[str, Any],
    *,
    stage: str,
    fingerprint: str,
    fingerprint_payload: Mapping[str, Any],
    artifacts: Sequence[str],
) -> None:
    hashes = _artifact_hashes(run_dir, artifacts)
    if hashes is None:
        raise ResearchError(f"Cannot cache stage '{stage}': an artifact is missing")
    cache.setdefault("stages", {})[stage] = {
        "fingerprint": fingerprint,
        "fingerprint_payload": dict(fingerprint_payload),
        "artifacts": hashes,
        "completed_at": workflow.utc_now(),
    }
    save_cache(run_dir, cache)


def _validate_transcript_text(text: str) -> None:
    stripped = text.strip()
    if not stripped:
        raise ResearchError("Transcript is empty")
    if not workflow.TIMESTAMP_RE.search(stripped):
        raise ResearchError("Transcript must contain timestamp anchors such as [00:15]")


def render_playbook(analysis: Mapping[str, Any]) -> str:
    source = analysis.get("source", {}) if isinstance(analysis.get("source"), dict) else {}
    hook = analysis.get("hook", {}) if isinstance(analysis.get("hook"), dict) else {}
    lines = [
        f"# Source Playbook — {source.get('title', 'Untitled source')}",
        "",
        f"- **Author:** {source.get('author', 'Unknown')}",
        f"- **Duration:** {source.get('duration', 'Unknown')}",
        f"- **Topic:** {analysis.get('topic', '')}",
        f"- **Core thesis:** {analysis.get('core_thesis', '')}",
        f"- **Audience:** {analysis.get('audience', '')}",
        "",
        "## Hook",
        "",
        f"- **Type:** `{hook.get('type', '')}`",
        f"- **Timestamp:** {hook.get('timestamp', '')}",
        f"- **Why it works:** {hook.get('why_it_works', '')}",
        f"- **Reusable pattern:** {hook.get('reusable_pattern', '')}",
        "",
        "## Presentation flow",
        "",
        "| # | Beat | Time | Purpose | Technique | Claim |",
        "|---:|---|---|---|---|---|",
    ]
    flow = analysis.get("flow", [])
    if isinstance(flow, list):
        for index, beat in enumerate(flow, 1):
            if not isinstance(beat, dict):
                continue
            cells = [
                beat.get("beat", ""),
                f"{beat.get('t_start', '')}–{beat.get('t_end', '')}",
                beat.get("purpose", ""),
                beat.get("technique", ""),
                beat.get("key_claim", ""),
            ]
            safe_cells = [str(cell).replace("|", "/").replace("\n", " ") for cell in cells]
            lines.append(f"| {index} | " + " | ".join(safe_cells) + " |")
    lines.extend(["", "## Rhetorical devices", ""])
    devices = analysis.get("rhetorical_devices", [])
    if isinstance(devices, list):
        lines.extend(f"- {item}" for item in devices)
    lines.extend(["", "## Facts and evidence", ""])
    facts = analysis.get("key_facts", [])
    if isinstance(facts, list):
        for fact in facts:
            if isinstance(fact, dict):
                lines.append(
                    f"- {fact.get('claim', '')} _(evidence: {fact.get('evidence', '')}; "
                    f"confidence: {fact.get('confidence', 'unspecified')})_"
                )
    lines.extend(["", "## Weaknesses and research gaps", ""])
    weaknesses = analysis.get("weaknesses", [])
    if isinstance(weaknesses, list):
        lines.extend(f"- {item}" for item in weaknesses)
    return "\n".join(lines).rstrip() + "\n"


def build_claim_ledger(analysis: Mapping[str, Any], *, url: str) -> dict[str, Any]:
    facts = analysis.get("key_facts", [])
    claims: list[dict[str, Any]] = []
    if isinstance(facts, list):
        for index, fact in enumerate(facts, 1):
            if not isinstance(fact, dict):
                continue
            text = str(fact.get("claim", "")).strip()
            if not text:
                continue
            raw_evidence = str(fact.get("evidence", "")).strip()
            timestamps = TIMESTAMP_VALUE_RE.findall(raw_evidence)
            evidence: list[dict[str, str]] = []
            if timestamps:
                evidence.extend(
                    {"timestamp": stamp, "detail": raw_evidence, "source_url": url}
                    for stamp in dict.fromkeys(timestamps)
                )
            else:
                evidence.append(
                    {
                        "detail": raw_evidence or "Reported in source analysis; timestamp unavailable",
                        "source_url": url,
                    }
                )
            confidence = str(fact.get("confidence", "medium")).lower()
            if confidence not in {"high", "medium", "low"}:
                confidence = "medium"
            claims.append(
                {
                    "id": f"claim-{index:03d}",
                    "text": text,
                    "kind": "source_claim",
                    "evidence": evidence,
                    "verification_status": "supported",
                    "confidence": confidence,
                    "must_keep": bool(fact.get("must_keep", True)),
                    "usage_note": "Attribute this as a source claim unless independently verified elsewhere.",
                }
            )
    return {"schema_version": ANALYSIS_SCHEMA_VERSION, "source_url": url, "claims": claims}


def _analysis_has_minimum_fields(analysis: Mapping[str, Any]) -> None:
    if analysis.get("schema_version") != ANALYSIS_SCHEMA_VERSION:
        raise ResearchError(f"Analysis schema_version must be {ANALYSIS_SCHEMA_VERSION!r}")
    missing = [key for key in ("topic", "core_thesis", "hook", "flow", "key_facts") if key not in analysis]
    if missing:
        raise ResearchError("Analysis is missing required fields: " + ", ".join(missing))
    if not isinstance(analysis.get("flow"), list) or not isinstance(analysis.get("key_facts"), list):
        raise ResearchError("Analysis flow and key_facts must be arrays")


def _write_analysis_artifacts(run_dir: Path, analysis: Mapping[str, Any], *, url: str) -> None:
    research_dir = run_dir / "research"
    workflow.atomic_write_json(research_dir / "source_analysis.json", dict(analysis))
    workflow.atomic_write_text(research_dir / "source_playbook.md", render_playbook(analysis))
    workflow.atomic_write_json(research_dir / "claim_ledger.json", build_claim_ledger(analysis, url=url))


def _repair_derived_artifacts_from_cache(
    run_dir: Path,
    cache: dict[str, Any],
    *,
    fingerprint: str,
    fingerprint_payload: Mapping[str, Any],
    url: str,
) -> None:
    """Rebuild deterministic playbook/ledger without spending another API call."""
    entry = cache.get("stages", {}).get("analysis", {})
    if not isinstance(entry, dict) or entry.get("fingerprint") != fingerprint:
        return
    analysis_path = run_dir / "research" / "source_analysis.json"
    recorded = entry.get("artifacts", {})
    expected_analysis_hash = recorded.get("research/source_analysis.json") if isinstance(recorded, dict) else None
    if not analysis_path.is_file() or workflow.sha256_file(analysis_path) != expected_analysis_hash:
        return
    playbook_path = run_dir / "research" / "source_playbook.md"
    ledger_path = run_dir / "research" / "claim_ledger.json"
    if playbook_path.is_file() and ledger_path.is_file():
        return
    try:
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(analysis, dict):
        return
    _write_analysis_artifacts(run_dir, analysis, url=url)
    update_cache_entry(
        run_dir,
        cache,
        stage="analysis",
        fingerprint=fingerprint,
        fingerprint_payload=fingerprint_payload,
        artifacts=(
            "research/source_analysis.json",
            "research/source_playbook.md",
            "research/claim_ledger.json",
        ),
    )


def run_transcript_phase(
    *,
    url: str,
    run_dir: Path,
    model: str,
    config: Mapping[str, Any],
    retries: int,
    force: bool,
    lazy_client: LazyClient,
) -> dict[str, Any]:
    cache = load_cache(run_dir)
    fingerprint, payload = build_fingerprint(
        stage="transcript",
        url=url,
        model=model,
        prompt_text=TRANSCRIPT_PROMPT,
        prompt_version=TRANSCRIPT_PROMPT_VERSION,
        schema_version=TRANSCRIPT_SCHEMA_VERSION,
        config=config,
        upstream_sha256=EMPTY_SHA256,
    )
    artifact = "research/full_transcript.md"
    if not force and cache_hit(run_dir, cache, stage="transcript", fingerprint=fingerprint, artifacts=(artifact,)):
        text = (run_dir / artifact).read_text(encoding="utf-8")
        _validate_transcript_text(text)
        return {"cache_hit": True, "fingerprint": fingerprint, "text": text}

    prompt = TRANSCRIPT_PROMPT
    language = config.get("language")
    if language and language != "auto":
        prompt += f"\n6. Ngôn ngữ transcript mong muốn: {language}."
    text = generate_content(
        lazy_client.get(),
        model=model,
        parts=[{"text": prompt}, video_part(url)],
        json_mode=False,
        label="transcript",
        retries=retries,
    ).strip()
    _validate_transcript_text(text)
    workflow.atomic_write_text(run_dir / artifact, text + "\n")
    cache = load_cache(run_dir)
    update_cache_entry(
        run_dir,
        cache,
        stage="transcript",
        fingerprint=fingerprint,
        fingerprint_payload=payload,
        artifacts=(artifact,),
    )
    return {"cache_hit": False, "fingerprint": fingerprint, "text": text}


def run_analysis_phase(
    *,
    url: str,
    run_dir: Path,
    model: str,
    config: Mapping[str, Any],
    retries: int,
    force: bool,
    lazy_client: LazyClient,
) -> dict[str, Any]:
    transcript_path = run_dir / "research" / "full_transcript.md"
    if not transcript_path.is_file():
        raise ResearchError("Run the transcript phase first; research/full_transcript.md is missing")
    transcript = transcript_path.read_text(encoding="utf-8")
    _validate_transcript_text(transcript)
    upstream_hash = workflow.sha256_file(transcript_path)
    fingerprint, payload = build_fingerprint(
        stage="analysis",
        url=url,
        model=model,
        prompt_text=ANALYSIS_PROMPT,
        prompt_version=ANALYSIS_PROMPT_VERSION,
        schema_version=ANALYSIS_SCHEMA_VERSION,
        config=config,
        upstream_sha256=upstream_hash,
    )
    artifacts = (
        "research/source_analysis.json",
        "research/source_playbook.md",
        "research/claim_ledger.json",
    )
    cache = load_cache(run_dir)
    if not force:
        _repair_derived_artifacts_from_cache(
            run_dir, cache, fingerprint=fingerprint, fingerprint_payload=payload, url=url
        )
        cache = load_cache(run_dir)
        if cache_hit(run_dir, cache, stage="analysis", fingerprint=fingerprint, artifacts=artifacts):
            analysis = json.loads((run_dir / artifacts[0]).read_text(encoding="utf-8"))
            _analysis_has_minimum_fields(analysis)
            return {"cache_hit": True, "fingerprint": fingerprint, "analysis": analysis}

    prompt = f"{ANALYSIS_PROMPT}\n\n=== TRANSCRIPT ===\n{transcript}\n=== END TRANSCRIPT ==="
    raw = generate_content(
        lazy_client.get(),
        model=model,
        parts=[{"text": prompt}, video_part(url)],
        json_mode=True,
        label="source analysis",
        retries=retries,
    )
    analysis = parse_json_text(raw)
    analysis["schema_version"] = ANALYSIS_SCHEMA_VERSION
    source = analysis.setdefault("source", {})
    if not isinstance(source, dict):
        raise ResearchError("Analysis source must be an object")
    source.setdefault("kind", "youtube")
    source.setdefault("locator", url)
    _analysis_has_minimum_fields(analysis)
    _write_analysis_artifacts(run_dir, analysis, url=url)
    cache = load_cache(run_dir)
    update_cache_entry(
        run_dir,
        cache,
        stage="analysis",
        fingerprint=fingerprint,
        fingerprint_payload=payload,
        artifacts=artifacts,
    )
    return {"cache_hit": False, "fingerprint": fingerprint, "analysis": analysis}


def ensure_run(run_dir: Path, *, url: str) -> None:
    workflow.init_run(run_dir, source_url=url)


def register_research(
    run_dir: Path,
    *,
    transcript_fingerprint: str | None,
    analysis_fingerprint: str,
    model: str,
) -> dict[str, Any]:
    metadata = {
        "model": model,
        "transcript_fingerprint": transcript_fingerprint,
        "analysis_fingerprint": analysis_fingerprint,
        "prompt_versions": {"transcript": TRANSCRIPT_PROMPT_VERSION, "analysis": ANALYSIS_PROMPT_VERSION},
        "schema_versions": {"transcript": TRANSCRIPT_SCHEMA_VERSION, "analysis": ANALYSIS_SCHEMA_VERSION},
    }
    return workflow.register_stage(run_dir, "research", metadata=metadata)


def run_research(
    *,
    url: str,
    run_dir: Path,
    model: str,
    config: Mapping[str, Any],
    retries: int = 3,
    force_transcript: bool = False,
    force_analysis: bool = False,
    client_factory: Callable[[], Any] = make_client,
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    ensure_run(run_dir, url=url)
    lazy_client = LazyClient(client_factory)
    transcript = run_transcript_phase(
        url=url,
        run_dir=run_dir,
        model=model,
        config=config,
        retries=retries,
        force=force_transcript,
        lazy_client=lazy_client,
    )
    analysis = run_analysis_phase(
        url=url,
        run_dir=run_dir,
        model=model,
        config=config,
        retries=retries,
        force=force_analysis,
        lazy_client=lazy_client,
    )
    registration = register_research(
        run_dir,
        transcript_fingerprint=transcript["fingerprint"],
        analysis_fingerprint=analysis["fingerprint"],
        model=model,
    )
    return {
        "stage": "research",
        "run_dir": str(run_dir),
        "cache": {"transcript": transcript["cache_hit"], "analysis": analysis["cache_hit"]},
        "fingerprints": {"transcript": transcript["fingerprint"], "analysis": analysis["fingerprint"]},
        "artifact_sha256": registration["artifact_sha256"],
        "next_action": "Review the research artifacts, then create and register editorial/scope_proposal.json.",
    }


def _json_argument(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    candidate = Path(value)
    try:
        text = candidate.read_text(encoding="utf-8") if candidate.is_file() else value
        parsed = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise argparse.ArgumentTypeError(f"Expected a JSON object or a JSON file path: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("Expected a JSON object")
    return parsed


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", required=True, help="YouTube URL")
    parser.add_argument("--run-dir", required=True, type=Path, help="Explicit output directory for this run")
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--language", default="auto", help="Transcript language, or 'auto'")
    parser.add_argument("--config-json", type=_json_argument, default={}, help="Extra fingerprinted research config")
    parser.add_argument("--retries", type=int, default=3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YouTube research phase for Human Host content")
    subparsers = parser.add_subparsers(dest="command", required=True)

    research_parser = subparsers.add_parser("research", help="Run transcript + analysis and register research")
    _add_common_arguments(research_parser)
    research_parser.add_argument("--force", action="store_true", help="Refresh both API-backed phases")
    research_parser.add_argument("--force-transcript", action="store_true")
    research_parser.add_argument("--force-analysis", action="store_true")

    transcript_parser = subparsers.add_parser("transcript", help="Run only the timestamped transcript phase")
    _add_common_arguments(transcript_parser)
    transcript_parser.add_argument("--force", action="store_true")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze an existing transcript and register research")
    _add_common_arguments(analyze_parser)
    analyze_parser.add_argument("--force", action="store_true")
    return parser


def _merged_config(args: argparse.Namespace) -> dict[str, Any]:
    config = dict(args.config_json)
    config["language"] = args.language
    return config


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.retries < 1:
        parser.error("--retries must be at least 1")
    run_dir = args.run_dir.expanduser().resolve()
    config = _merged_config(args)
    try:
        ensure_run(run_dir, url=args.url)
        lazy_client = LazyClient()
        if args.command == "research":
            output = run_research(
                url=args.url,
                run_dir=run_dir,
                model=args.model,
                config=config,
                retries=args.retries,
                force_transcript=args.force or args.force_transcript,
                force_analysis=args.force or args.force_analysis,
            )
        elif args.command == "transcript":
            result = run_transcript_phase(
                url=args.url,
                run_dir=run_dir,
                model=args.model,
                config=config,
                retries=args.retries,
                force=args.force,
                lazy_client=lazy_client,
            )
            output = {
                "stage": "transcript",
                "run_dir": str(run_dir),
                "cache_hit": result["cache_hit"],
                "fingerprint": result["fingerprint"],
                "artifact": "research/full_transcript.md",
                "next_action": "Run the analyze phase; transcript alone is not a registrable research stage.",
            }
        elif args.command == "analyze":
            result = run_analysis_phase(
                url=args.url,
                run_dir=run_dir,
                model=args.model,
                config=config,
                retries=args.retries,
                force=args.force,
                lazy_client=lazy_client,
            )
            transcript_cache = load_cache(run_dir).get("stages", {}).get("transcript", {})
            registration = register_research(
                run_dir,
                transcript_fingerprint=transcript_cache.get("fingerprint") if isinstance(transcript_cache, dict) else None,
                analysis_fingerprint=result["fingerprint"],
                model=args.model,
            )
            output = {
                "stage": "research",
                "run_dir": str(run_dir),
                "cache_hit": result["cache_hit"],
                "fingerprint": result["fingerprint"],
                "artifact_sha256": registration["artifact_sha256"],
                "next_action": "Review and approve research before registering scope.",
            }
        else:  # pragma: no cover - argparse enforces this
            parser.error(f"Unknown command: {args.command}")
            return 2
    except (ResearchError, workflow.WorkflowError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
