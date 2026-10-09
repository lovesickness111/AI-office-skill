#!/usr/bin/env node

/**
 * Validate, preview, and render deterministic web shots from storyboard v1.0.
 *
 * `validate` and `preview` use Node.js built-ins only. `render` loads Playwright
 * lazily and uses ffmpeg as a child process; neither dependency is vendored or
 * resolved from another project in the repository.
 */

import { spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_PATH = fileURLToPath(import.meta.url);
const WEB_KINDS = new Set(["component", "html"]);
const RENDERER_KINDS = new Set([
  "component",
  "html",
  "mermaid",
  "stock",
  "image",
  "screen_recording",
]);
const HOST_LAYOUTS = new Set(["host_only", "support_top", "support_right", "explainer_full"]);
const SHOT_LANES = new Set(["support_top", "support_right", "explainer_full"]);
const VISUAL_MODALITIES = new Set([
  "host_only",
  "code_native",
  "licensed_video",
  "screen_recording",
  "web_screenshot",
  "repo_screenshot",
  "web_image",
  "static_graphic",
]);
const EDITORIAL_HOOK_PURPOSES = new Set(["title", "pain", "consequence", "reversal", "promise", "payoff", "roadmap"]);
const EDITORIAL_HOOK_COVERAGE = new Set(["shot", "host_only"]);
const EDITORIAL_TITLE_MODES = new Set(["dedicated_scene", "integrated_hook"]);
const EDITORIAL_ENDING_MODES = new Set(["visual_cta", "spoken_cta", "host_only", "none"]);
const SCENE_NAVIGATION_KEYS = new Set(["mode", "boundary_policy", "intra_sentence_changes"]);
const SCENE_NAVIGATION_DEFAULTS = Object.freeze({
  mode: "manual",
  boundary_policy: "sentence_start",
  intra_sentence_changes: "component_state",
});
const RATIO_SIZES = Object.freeze({
  "9:16": { width: 1080, height: 1920 },
  "3:4": { width: 1080, height: 1440 },
  "1:1": { width: 1080, height: 1080 },
  "16:9": { width: 1920, height: 1080 },
});
const SUPPORT_TOP_GEOMETRY = Object.freeze({
  ratio: "9:16",
  canvas: Object.freeze({ x: 0, y: 0, width: 432, height: 768 }),
  visual: Object.freeze({ x: 0, y: 0, width: 432, height: 432 }),
  host: Object.freeze({ x: 0, y: 432, width: 432, height: 336 }),
});
const UNSAFE_SOURCE_PATTERNS = [
  [/<\s*(?:iframe|object|embed|base)\b/i, "embedded document/base elements are not allowed"],
  [/<\s*meta\b[^>]*http-equiv\s*=\s*["']?refresh/i, "meta refresh is not allowed"],
  [/<\s*script\b[^>]*\bsrc\s*=/i, "external script files are not allowed in a standalone shot"],
  [/<\s*link\b[^>]*\bhref\s*=/i, "external stylesheets/resources are not allowed in a standalone shot"],
  [/\b(?:https?|wss?):\/\//i, "network URLs are not allowed"],
  [/(?:["'(=]\s*)\/\/(?:[a-z0-9-]+\.)+[a-z]{2,}/i, "protocol-relative network URLs are not allowed"],
  [/\bfetch\s*\(/i, "fetch() is not allowed"],
  [/\bXMLHttpRequest\b/i, "XMLHttpRequest is not allowed"],
  [/\bWebSocket\b/i, "WebSocket is not allowed"],
  [/\bEventSource\b/i, "EventSource is not allowed"],
  [/\b(?:Shared)?Worker\s*\(/i, "web workers are not allowed"],
  [/\bserviceWorker\s*\./i, "service workers are not allowed"],
  [/\bsendBeacon\s*\(/i, "sendBeacon() is not allowed"],
  [/\bimportScripts\s*\(/i, "importScripts() is not allowed"],
  [/\bimport\s*\(/i, "dynamic import() is not allowed"],
  [/\beval\s*\(/i, "eval() is not allowed"],
  [/\bnew\s+Function\s*\(/i, "new Function() is not allowed"],
  [/\bMath\s*\.\s*random\s*\(/i, "unseeded Math.random() is not deterministic"],
  [/\bDate\s*\.\s*now\s*\(/i, "Date.now() is not deterministic"],
  [/\bnew\s+Date\s*\(/i, "new Date() is not deterministic"],
  [/\bcrypto\s*\.\s*(?:getRandomValues|randomUUID)\s*\(/i, "unseeded crypto randomness is not deterministic"],
  [/\b(?:window\s*\.\s*)?(?:parent|top)\s*\./i, "access to parent/top windows is not allowed"],
  [/\bwindow\s*\.\s*open\s*\(/i, "window.open() is not allowed"],
  [/\blocation\s*\.\s*(?:assign|replace)\s*\(/i, "location navigation is not allowed"],
];

function fail(message) {
  throw new Error(message);
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value) {
  return typeof value === "string" && Boolean(value.trim());
}

function htmlEscape(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function calculatePreviewScale(width, height, availableWidth, availableHeight) {
  return Math.min(1, availableWidth / width, availableHeight / height);
}

const KARAOKE_DEFAULTS = Object.freeze({
  placement: "capture_stage_bottom",
  bottom_margin_px: 100,
  max_lines: 2,
  reading_wpm: 150,
  pause_ms: Object.freeze({ comma: 250, clause: 400, sentence: 650, scene_end: 900 }),
  scene_advance: "manual",
  end_indicator: "NEXT →",
});
const KARAOKE_CONFIG_KEYS = new Set([
  "enabled", "placement", "bottom_margin_px", "max_lines", "reading_wpm",
  "pause_ms", "scene_advance", "end_indicator",
]);
const KARAOKE_PAUSE_KEYS = new Set(["comma", "clause", "sentence", "scene_end"]);

function inlineJson(value) {
  return JSON.stringify(value)
    .replaceAll("&", "\\u0026")
    .replaceAll("<", "\\u003c")
    .replaceAll(">", "\\u003e")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029");
}

export function normalizeKaraokeCaptionConfig(value, stageHeight = SUPPORT_TOP_GEOMETRY.canvas.height) {
  if (value === undefined) return null;
  if (!isPlainObject(value)) fail("project.karaoke_caption must be an object when present");
  for (const key of Object.keys(value)) {
    if (!KARAOKE_CONFIG_KEYS.has(key)) fail(`project.karaoke_caption has unknown field: ${key}`);
  }
  if (typeof value.enabled !== "boolean") fail("project.karaoke_caption.enabled must be a boolean");
  const placement = value.placement ?? KARAOKE_DEFAULTS.placement;
  if (placement !== KARAOKE_DEFAULTS.placement) {
    fail('project.karaoke_caption.placement must be "capture_stage_bottom"');
  }
  const bottomMargin = value.bottom_margin_px ?? KARAOKE_DEFAULTS.bottom_margin_px;
  if (!Number.isInteger(bottomMargin) || bottomMargin < 0 || bottomMargin >= stageHeight) {
    fail(`project.karaoke_caption.bottom_margin_px must be an integer from 0 to ${stageHeight - 1}`);
  }
  const maxLines = value.max_lines ?? KARAOKE_DEFAULTS.max_lines;
  if (!Number.isInteger(maxLines) || maxLines < 1 || maxLines > 2) {
    fail("project.karaoke_caption.max_lines must be 1 or 2");
  }
  const readingWpm = value.reading_wpm ?? KARAOKE_DEFAULTS.reading_wpm;
  if (!Number.isInteger(readingWpm) || readingWpm < 60 || readingWpm > 1000) {
    fail("project.karaoke_caption.reading_wpm must be an integer from 60 to 1000");
  }
  if (value.pause_ms !== undefined && !isPlainObject(value.pause_ms)) {
    fail("project.karaoke_caption.pause_ms must be an object when present");
  }
  for (const key of Object.keys(value.pause_ms || {})) {
    if (!KARAOKE_PAUSE_KEYS.has(key)) fail(`project.karaoke_caption.pause_ms has unknown field: ${key}`);
  }
  const pauseMs = {};
  for (const key of KARAOKE_PAUSE_KEYS) {
    const amount = value.pause_ms?.[key] ?? KARAOKE_DEFAULTS.pause_ms[key];
    if (!Number.isInteger(amount) || amount < 0 || amount > 10_000) {
      fail(`project.karaoke_caption.pause_ms.${key} must be an integer from 0 to 10000`);
    }
    pauseMs[key] = amount;
  }
  const sceneAdvance = value.scene_advance ?? KARAOKE_DEFAULTS.scene_advance;
  if (sceneAdvance !== KARAOKE_DEFAULTS.scene_advance) {
    fail('project.karaoke_caption.scene_advance must be "manual"');
  }
  const endIndicator = value.end_indicator ?? KARAOKE_DEFAULTS.end_indicator;
  if (
    !isNonEmptyString(endIndicator)
    || [...endIndicator].length > 32
    || /[\[\]<>]/u.test(endIndicator)
    || [...endIndicator].some((character) => {
      const point = character.codePointAt(0);
      return point < 32 || point === 127;
    })
  ) {
    fail("project.karaoke_caption.end_indicator must be a single-line string of 1 to 32 safe characters");
  }
  return {
    enabled: value.enabled,
    placement,
    bottom_margin_px: bottomMargin,
    max_lines: maxLines,
    reading_wpm: readingWpm,
    pause_ms: pauseMs,
    scene_advance: sceneAdvance,
    end_indicator: endIndicator,
  };
}

export function normalizeSceneNavigationConfig(value) {
  if (value === undefined) return null;
  if (!isPlainObject(value)) fail("project.scene_navigation must be an object when present");
  for (const key of Object.keys(value)) {
    if (!SCENE_NAVIGATION_KEYS.has(key)) fail(`project.scene_navigation has unknown field: ${key}`);
  }
  const resolved = { ...SCENE_NAVIGATION_DEFAULTS, ...value };
  if (resolved.mode !== SCENE_NAVIGATION_DEFAULTS.mode) {
    fail('project.scene_navigation.mode must be "manual"');
  }
  if (resolved.boundary_policy !== SCENE_NAVIGATION_DEFAULTS.boundary_policy) {
    fail('project.scene_navigation.boundary_policy must be "sentence_start"');
  }
  if (resolved.intra_sentence_changes !== SCENE_NAVIGATION_DEFAULTS.intra_sentence_changes) {
    fail('project.scene_navigation.intra_sentence_changes must be "component_state"');
  }
  return resolved;
}

function cuePhraseStart(text, phrase, owner) {
  const match = new RegExp(phrasePattern(String(phrase || "")), "iu").exec(String(text || ""));
  if (!match) fail(`${owner} phrase cannot be located in its segment text`);
  return match.index;
}

export function isSentenceStart(text, index) {
  if (!Number.isInteger(index) || index < 0 || index > String(text).length) return false;
  if (index === 0) return true;
  const before = String(text).slice(0, index).trimEnd().replace(/["'”’»）)\]}]+$/u, "").trimEnd();
  return /[.!?…。！？]$/u.test(before);
}

function phrasePattern(phrase) {
  return phrase.trim().split(/\s+/u)
    .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("\\s+");
}

export function deriveKaraokeSceneExcerpts(storyboard) {
  if (!isPlainObject(storyboard) || !Array.isArray(storyboard.segments) || !Array.isArray(storyboard.shots)) {
    fail("A storyboard with segments and shots is required to derive karaoke excerpts");
  }
  const cuePositions = new Map();
  let scriptText = "";
  for (const [segmentIndex, segment] of storyboard.segments.entries()) {
    const segmentText = String(segment.text || "").trim();
    if (segmentIndex) scriptText += " ";
    const segmentStart = scriptText.length;
    scriptText += segmentText;
    for (const cue of segment.cues || []) {
      const match = new RegExp(phrasePattern(String(cue.phrase || "")), "iu").exec(segmentText);
      if (!match) fail(`Cue ${cue.id} phrase cannot be located while deriving karaoke excerpts`);
      cuePositions.set(cue.id, segmentStart + match.index);
    }
  }
  const anchors = storyboard.shots.map((shot) => {
    const position = cuePositions.get(shot.enter?.cue_id);
    if (!Number.isInteger(position)) fail(`Shot ${shot.id} enter cue cannot be located while deriving karaoke excerpts`);
    return position;
  });
  for (let index = 1; index < anchors.length; index += 1) {
    if (anchors[index] < anchors[index - 1]) {
      fail(`Karaoke shot anchors must follow global script order: ${storyboard.shots[index].id}`);
    }
  }
  const groups = [];
  storyboard.shots.forEach((shot, index) => {
    const position = anchors[index];
    const previous = groups.at(-1);
    if (previous?.position === position) previous.shot_ids.push(shot.id);
    else groups.push({ position, shot_ids: [shot.id] });
  });
  const scenes = [];
  if (groups.length === 0) {
    if (scriptText) {
      scenes.push({ id: "host-only-prefix", shot_ids: [], host_only: true, start: 0, end: scriptText.length, text: scriptText });
    }
    return { script_text: scriptText, scenes };
  }
  if (groups[0].position > 0) {
    scenes.push({
      id: "host-only-prefix",
      shot_ids: [],
      host_only: true,
      start: 0,
      end: groups[0].position,
      text: scriptText.slice(0, groups[0].position),
    });
  }
  groups.forEach((group, index) => {
    const end = index + 1 < groups.length ? groups[index + 1].position : scriptText.length;
    scenes.push({
      id: `cue-scene-${String(index + 1).padStart(2, "0")}`,
      shot_ids: group.shot_ids,
      host_only: false,
      start: group.position,
      end,
      text: scriptText.slice(group.position, end),
    });
  });
  return { script_text: scriptText, scenes };
}

function punctuationPause(word, pauseMs) {
  if (/[.!?…。！？]+["'”’)}\]]*$/u.test(word)) return pauseMs.sentence;
  if (/[:;：；]["'”’)}\]]*$/u.test(word)) return pauseMs.clause;
  if (/[,，]["'”’)}\]]*$/u.test(word)) return pauseMs.comma;
  return 0;
}

function assignCaptionPages(words, maxLines) {
  // Keep each capture-stage caption comfortably inside its one/two-line box.
  // The browser still performs the real wrapping; this conservative budget
  // prevents a long unpunctuated phrase from being clipped before runtime QA.
  const characterLimit = maxLines * 24;
  let page = 0;
  let characters = 0;
  for (const word of words) {
    const addition = word.text.length + (characters ? 1 : 0);
    if (characters && characters + addition > characterLimit) {
      page += 1;
      characters = 0;
    }
    word.page = page;
    characters += word.text.length + (characters ? 1 : 0);
    if (punctuationPause(word.text, {
      comma: 1,
      clause: 1,
      sentence: 1,
    }) > 0) {
      page += 1;
      characters = 0;
    }
  }
}

export function buildKaraokeTimeline(text, config) {
  const resolved = config || {
    ...KARAOKE_DEFAULTS,
    pause_ms: { ...KARAOKE_DEFAULTS.pause_ms },
  };
  const baseWordMs = Math.round(60_000 / resolved.reading_wpm);
  let cursor = 0;
  const words = [...String(text).matchAll(/\S+/gu)].map((match, index) => {
    const value = match[0];
    const start = cursor;
    const spokenEnd = start + baseWordMs;
    const pause = punctuationPause(value, resolved.pause_ms);
    cursor = spokenEnd + pause;
    return {
      index,
      text: value,
      start_ms: start,
      spoken_end_ms: spokenEnd,
      hold_end_ms: cursor,
      punctuation_pause_ms: pause,
      page: 0,
    };
  });
  assignCaptionPages(words, resolved.max_lines);
  return {
    source_text: String(text),
    words,
    spoken_complete_ms: cursor,
    duration_ms: cursor + resolved.pause_ms.scene_end,
  };
}

function toPosix(value) {
  return value.split(path.sep).join("/");
}

function isWithin(parentPath, childPath) {
  const relative = path.relative(path.resolve(parentPath), path.resolve(childPath));
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

function assertExistingPathInside(runDir, candidate, label) {
  const runReal = fs.realpathSync.native(runDir);
  const candidateReal = fs.realpathSync.native(candidate);
  if (!isWithin(runReal, candidateReal)) {
    fail(`${label} escapes the run directory through a symlink: ${candidate}`);
  }
}

function assertWritablePathInside(runDir, candidate, label) {
  if (!isWithin(runDir, candidate)) fail(`${label} must stay inside the run directory: ${candidate}`);
  let existingAncestor = path.resolve(candidate);
  while (!fs.existsSync(existingAncestor)) {
    const parent = path.dirname(existingAncestor);
    if (parent === existingAncestor) fail(`${label} has no existing parent: ${candidate}`);
    existingAncestor = parent;
  }
  assertExistingPathInside(runDir, existingAncestor, label);
}

function resolveRunPath(runDir, relativePath, label, { mustExist = false } = {}) {
  if (typeof relativePath !== "string" || !relativePath.trim()) {
    fail(`${label} must be a non-empty run-relative path`);
  }
  const value = relativePath.trim();
  if (path.isAbsolute(value) || path.win32.isAbsolute(value) || value.includes("\0")) {
    fail(`${label} must be run-relative: ${relativePath}`);
  }
  const resolved = path.resolve(runDir, value);
  if (!isWithin(runDir, resolved)) {
    fail(`${label} escapes the run directory: ${relativePath}`);
  }
  if (mustExist && !fs.existsSync(resolved)) {
    fail(`${label} does not exist: ${relativePath}`);
  }
  if (fs.existsSync(resolved)) {
    assertExistingPathInside(runDir, resolved, label);
  }
  return resolved;
}

function inferRunDir(storyboardPath) {
  let cursor = path.dirname(storyboardPath);
  while (true) {
    if (fs.existsSync(path.join(cursor, "run_manifest.json"))) return cursor;
    if (path.basename(cursor).toLowerCase() === "storyboard") return path.dirname(cursor);
    if (path.basename(cursor).toLowerCase() === "creator-pack") {
      return path.dirname(cursor);
    }
    const parent = path.dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }
  return path.dirname(storyboardPath);
}

function readJson(jsonPath, label) {
  let raw;
  try {
    raw = fs.readFileSync(jsonPath, "utf8");
  } catch (error) {
    fail(`Cannot read ${label} at ${jsonPath}: ${error.message}`);
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    fail(`${label} is not valid JSON: ${error.message}`);
  }
}

function projectDimensions(project) {
  const ratio = project.ratio || "16:9";
  const defaults = RATIO_SIZES[ratio];
  const width = project.width ?? defaults?.width;
  const height = project.height ?? defaults?.height;
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 2 || height < 2 || width > 4096 || height > 4096) {
    fail(`project.width and project.height must be even-sized integers between 2 and 4096 (known ratios: ${Object.keys(RATIO_SIZES).join(", ")})`);
  }
  if (width % 2 || height % 2) {
    fail("project.width and project.height must be even so ffmpeg can encode yuv420p video");
  }
  return { ratio, width, height };
}

function implicitHostLayout() {
  return "support_top";
}

function assertSupportTopGeometry(project, dimensions, owner) {
  if (dimensions.ratio !== SUPPORT_TOP_GEOMETRY.ratio) {
    fail(`${owner} uses support_top, which requires project.ratio "9:16"`);
  }
  if (
    project.width !== SUPPORT_TOP_GEOMETRY.canvas.width
    || project.height !== SUPPORT_TOP_GEOMETRY.canvas.height
  ) {
    fail(`${owner} uses support_top, which requires explicit project.width 432 and project.height 768 for the desktop-capture canvas`);
  }
}

function validateVisualOptions(shot) {
  if (shot.visual_options === undefined) {
    if (shot.selected_option_id !== undefined) {
      fail(`Shot ${shot.id}.selected_option_id requires visual_options`);
    }
    return;
  }
  if (!Array.isArray(shot.visual_options) || shot.visual_options.length === 0) {
    fail(`Shot ${shot.id}.visual_options must be a non-empty array`);
  }

  const optionIds = new Set();
  for (const [index, option] of shot.visual_options.entries()) {
    const prefix = `Shot ${shot.id}.visual_options[${index}]`;
    if (!isPlainObject(option)) fail(`${prefix} must be an object`);
    if (typeof option.id !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(option.id)) {
      fail(`${prefix}.id is invalid`);
    }
    if (optionIds.has(option.id)) fail(`Shot ${shot.id} has duplicate visual option id: ${option.id}`);
    optionIds.add(option.id);
    if (!VISUAL_MODALITIES.has(option.modality)) {
      fail(`${prefix}.modality must be one of: ${[...VISUAL_MODALITIES].join(", ")}`);
    }
    for (const field of ["treatment", "why", "source_plan", "rights_note"]) {
      if (typeof option[field] !== "string" || !option[field].trim()) {
        fail(`${prefix}.${field} must be a non-empty string`);
      }
    }
  }

  if (typeof shot.selected_option_id !== "string" || !optionIds.has(shot.selected_option_id)) {
    fail(`Shot ${shot.id}.selected_option_id must reference a visual_options id`);
  }
  const selectedOption = shot.visual_options.find((option) => option.id === shot.selected_option_id);
  if (selectedOption.modality === "host_only") {
    fail(`Shot ${shot.id} cannot select a host_only visual option; omit the shot instead`);
  }
}

function collectLocalReferences(source) {
  const values = [];
  const attributePattern = /\b(?:src|srcset|poster|href|xlink:href)\s*=\s*(["'])(.*?)\1/gis;
  const cssUrlPattern = /url\(\s*(["']?)(.*?)\1\s*\)/gis;
  for (const match of source.matchAll(attributePattern)) {
    const raw = match[0].toLowerCase().includes("srcset")
      ? match[2].split(",").map((item) => item.trim().split(/\s+/, 1)[0])
      : [match[2].trim()];
    values.push(...raw);
  }
  for (const match of source.matchAll(cssUrlPattern)) values.push(match[2].trim());
  return values;
}

function validateLocalReference(reference, htmlPath, runDir) {
  if (!reference || reference.startsWith("#") || /^(?:data|blob|about):/i.test(reference)) return;
  if (/^(?:https?|wss?):/i.test(reference) || reference.startsWith("//")) {
    fail(`${path.basename(htmlPath)} contains a network reference: ${reference}`);
  }
  const withoutQuery = reference.split(/[?#]/, 1)[0];
  if (!withoutQuery) return;
  let resolved;
  if (/^file:/i.test(withoutQuery)) {
    try {
      resolved = fileURLToPath(withoutQuery);
    } catch {
      fail(`${path.basename(htmlPath)} contains an invalid file URL: ${reference}`);
    }
  } else {
    if (path.isAbsolute(withoutQuery) || path.win32.isAbsolute(withoutQuery)) {
      fail(`${path.basename(htmlPath)} contains an absolute local reference: ${reference}`);
    }
    resolved = path.resolve(path.dirname(htmlPath), withoutQuery);
  }
  if (!isWithin(runDir, resolved)) {
    fail(`${path.basename(htmlPath)} references a file outside the run directory: ${reference}`);
  }
  if (!fs.existsSync(resolved)) {
    fail(`${path.basename(htmlPath)} references a missing local file: ${reference}`);
  }
  assertExistingPathInside(runDir, resolved, `Local reference in ${path.basename(htmlPath)}`);
}

export function validateShotHtml(htmlPath, runDir) {
  const source = fs.readFileSync(htmlPath, "utf8");
  for (const [pattern, message] of UNSAFE_SOURCE_PATTERNS) {
    if (pattern.test(source)) fail(`${path.basename(htmlPath)}: ${message}`);
  }
  if (!/window\s*\.\s*__hyperframe\s*=/i.test(source)) {
    fail(`${path.basename(htmlPath)} must assign window.__hyperframe`);
  }
  for (const member of ["durationMs", "ready", "seek"]) {
    if (!new RegExp(`\\b${member}\\b`).test(source)) {
      fail(`${path.basename(htmlPath)} is missing __hyperframe.${member}`);
    }
  }
  for (const reference of collectLocalReferences(source)) {
    validateLocalReference(reference, htmlPath, runDir);
  }
  return { bytes: Buffer.byteLength(source), sha256: crypto.createHash("sha256").update(source).digest("hex") };
}

function validateEditorialPlan(editorialPlan, { segmentIds, cueOwners, shotSegments, finalShotId }) {
  if (!isPlainObject(editorialPlan)) fail("editorial_plan must be an object when present");

  const hookSegmentId = editorialPlan.hook_segment_id;
  if (!isNonEmptyString(hookSegmentId)) fail("editorial_plan.hook_segment_id is required");
  if (!segmentIds.has(hookSegmentId)) fail("editorial_plan.hook_segment_id references an unknown segment");

  if (!Array.isArray(editorialPlan.hook_beats) || editorialPlan.hook_beats.length === 0) {
    fail("editorial_plan.hook_beats must be a non-empty array");
  }
  const beatIds = new Set();
  for (const [index, beat] of editorialPlan.hook_beats.entries()) {
    const prefix = `editorial_plan.hook_beats[${index}]`;
    if (!isPlainObject(beat)) fail(`${prefix} must be an object`);
    if (!isNonEmptyString(beat.id)) fail(`${prefix}.id is required`);
    if (beatIds.has(beat.id)) fail(`Duplicate editorial hook beat id: ${beat.id}`);
    beatIds.add(beat.id);
    if (!isNonEmptyString(beat.cue_id)) fail(`${prefix}.cue_id is required`);
    if (!cueOwners.has(beat.cue_id)) fail(`${prefix}.cue_id references an unknown cue`);
    if (cueOwners.get(beat.cue_id) !== hookSegmentId) {
      fail(`${prefix}.cue_id must belong to editorial_plan.hook_segment_id`);
    }
    if (!EDITORIAL_HOOK_PURPOSES.has(beat.purpose)) {
      fail(`${prefix}.purpose must be one of: ${[...EDITORIAL_HOOK_PURPOSES].join(", ")}`);
    }
    if (!EDITORIAL_HOOK_COVERAGE.has(beat.coverage)) {
      fail(`${prefix}.coverage must be one of: ${[...EDITORIAL_HOOK_COVERAGE].join(", ")}`);
    }
    if (beat.coverage === "host_only") {
      if (beat.shot_ids !== undefined && (!Array.isArray(beat.shot_ids) || beat.shot_ids.length !== 0)) {
        fail(`${prefix}.shot_ids must be omitted or empty for host_only coverage`);
      }
      continue;
    }
    if (!Array.isArray(beat.shot_ids) || beat.shot_ids.length === 0) {
      fail(`${prefix}.shot_ids must be a non-empty array for shot coverage`);
    }
    for (const [shotIndex, shotId] of beat.shot_ids.entries()) {
      const shotPrefix = `${prefix}.shot_ids[${shotIndex}]`;
      if (!isNonEmptyString(shotId)) fail(`${shotPrefix} must be a non-empty shot id`);
      if (!shotSegments.has(shotId)) fail(`${shotPrefix} references an unknown shot`);
      if (shotSegments.get(shotId) !== hookSegmentId) {
        fail(`${shotPrefix} must reference a shot in editorial_plan.hook_segment_id`);
      }
    }
  }

  const titleTreatment = editorialPlan.title_treatment;
  if (!isPlainObject(titleTreatment)) fail("editorial_plan.title_treatment must be an object");
  if (!EDITORIAL_TITLE_MODES.has(titleTreatment.mode)) {
    fail(`editorial_plan.title_treatment.mode must be one of: ${[...EDITORIAL_TITLE_MODES].join(", ")}`);
  }
  if (!isNonEmptyString(titleTreatment.shot_id)) fail("editorial_plan.title_treatment.shot_id is required");
  if (!shotSegments.has(titleTreatment.shot_id)) {
    fail("editorial_plan.title_treatment.shot_id references an unknown shot");
  }
  if (shotSegments.get(titleTreatment.shot_id) !== hookSegmentId) {
    fail("editorial_plan.title_treatment.shot_id must reference a shot in editorial_plan.hook_segment_id");
  }
  if (!isNonEmptyString(titleTreatment.screen_text)) {
    fail("editorial_plan.title_treatment.screen_text is required");
  }

  const ending = editorialPlan.ending;
  if (!isPlainObject(ending)) fail("editorial_plan.ending must be an object");
  if (!EDITORIAL_ENDING_MODES.has(ending.mode)) {
    fail(`editorial_plan.ending.mode must be one of: ${[...EDITORIAL_ENDING_MODES].join(", ")}`);
  }
  if (ending.mode === "visual_cta" || ending.mode === "spoken_cta") {
    if (!isNonEmptyString(ending.shot_id)) fail(`editorial_plan.ending.shot_id is required for ${ending.mode}`);
    if (!shotSegments.has(ending.shot_id)) fail("editorial_plan.ending.shot_id references an unknown shot");
    if (ending.shot_id !== finalShotId) {
      fail("editorial_plan.ending.shot_id must reference the final storyboard shot");
    }
    if (!isNonEmptyString(ending.screen_text)) {
      fail(`editorial_plan.ending.screen_text is required for ${ending.mode}`);
    }
    if (ending.mode === "spoken_cta") {
      if (!isNonEmptyString(ending.spoken_phrase)) {
        fail("editorial_plan.ending.spoken_phrase is required for spoken_cta");
      }
    } else if (Object.hasOwn(ending, "spoken_phrase")) {
      fail("editorial_plan.ending.spoken_phrase must be omitted for visual_cta");
    }
    return;
  }
  if (Object.hasOwn(ending, "shot_id")) {
    fail(`editorial_plan.ending.shot_id must be omitted for ${ending.mode}`);
  }
  if (ending.mode === "host_only") {
    if (Object.hasOwn(ending, "screen_text") && !isNonEmptyString(ending.screen_text)) {
      fail("editorial_plan.ending.screen_text must be non-empty when present for host_only");
    }
  } else if (Object.hasOwn(ending, "screen_text")) {
    fail("editorial_plan.ending.screen_text must be omitted for none");
  }
  if (Object.hasOwn(ending, "spoken_phrase")) {
    fail(`editorial_plan.ending.spoken_phrase must be omitted for ${ending.mode}`);
  }
}

export function validateStoryboard(storyboardPath, runDir) {
  const resolvedStoryboard = path.resolve(storyboardPath);
  const resolvedRunDir = path.resolve(runDir);
  if (!fs.existsSync(resolvedRunDir) || !fs.statSync(resolvedRunDir).isDirectory()) {
    fail(`Run directory does not exist: ${resolvedRunDir}`);
  }
  if (!isWithin(resolvedRunDir, resolvedStoryboard)) {
    fail(`Storyboard must be located inside the run directory: ${resolvedStoryboard}`);
  }
  assertExistingPathInside(resolvedRunDir, resolvedStoryboard, "Storyboard");
  const storyboard = readJson(resolvedStoryboard, "storyboard");
  if (!isPlainObject(storyboard)) fail("Storyboard root must be an object");
  if (storyboard.schema_version !== "1.0") fail('storyboard.schema_version must be "1.0"');
  if (!isPlainObject(storyboard.project)) fail("storyboard.project must be an object");
  const dimensions = projectDimensions(storyboard.project);
  const karaokeCaption = normalizeKaraokeCaptionConfig(storyboard.project.karaoke_caption, dimensions.height);
  const sceneNavigation = normalizeSceneNavigationConfig(storyboard.project.scene_navigation);
  if (karaokeCaption?.enabled && (
    dimensions.width !== SUPPORT_TOP_GEOMETRY.canvas.width
    || dimensions.height !== SUPPORT_TOP_GEOMETRY.canvas.height
  )) {
    fail("project.karaoke_caption requires the 432 x 768 desktop-capture stage");
  }
  if (storyboard.project.default_host_layout !== undefined && !HOST_LAYOUTS.has(storyboard.project.default_host_layout)) {
    fail(`project.default_host_layout must be one of: ${[...HOST_LAYOUTS].join(", ")}`);
  }
  if (storyboard.project.default_host_layout === "support_top") {
    assertSupportTopGeometry(storyboard.project, dimensions, "project.default_host_layout");
  }
  const fallbackHostLayout = implicitHostLayout();
  const fps = storyboard.project.fps;
  if (!Number.isInteger(fps) || fps < 1 || fps > 120) fail("storyboard.project.fps must be an integer from 1 to 120");
  if (!Array.isArray(storyboard.segments) || storyboard.segments.length === 0) fail("storyboard.segments must be a non-empty array");
  if (!Array.isArray(storyboard.shots)) fail("storyboard.shots must be an array");
  if (storyboard.assets !== undefined && !Array.isArray(storyboard.assets)) fail("storyboard.assets must be an array when present");

  const segmentIds = new Set();
  const segmentHostLayouts = new Map();
  const cueOwners = new Map();
  const cueDetails = new Map();
  for (const [index, segment] of storyboard.segments.entries()) {
    if (!isPlainObject(segment)) fail(`segments[${index}] must be an object`);
    if (typeof segment.id !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(segment.id)) fail(`segments[${index}].id is invalid`);
    if (segmentIds.has(segment.id)) fail(`Duplicate segment id: ${segment.id}`);
    segmentIds.add(segment.id);
    if (segment.host_layout !== undefined && !HOST_LAYOUTS.has(segment.host_layout)) {
      fail(`Segment ${segment.id}.host_layout must be one of: ${[...HOST_LAYOUTS].join(", ")}`);
    }
    if (segment.host_layout === "support_top") {
      assertSupportTopGeometry(storyboard.project, dimensions, `Segment ${segment.id}.host_layout`);
    }
    segmentHostLayouts.set(segment.id, segment.host_layout);
    if (typeof segment.text !== "string" || !segment.text.trim()) fail(`Segment ${segment.id} needs non-empty text`);
    if (!Array.isArray(segment.cues)) fail(`Segment ${segment.id}.cues must be an array`);
    for (const [cueIndex, cue] of segment.cues.entries()) {
      if (!isPlainObject(cue) || typeof cue.id !== "string" || !cue.id.trim()) fail(`Segment ${segment.id} cue ${cueIndex} needs an id`);
      if (cueOwners.has(cue.id)) fail(`Duplicate cue id: ${cue.id}`);
      if (typeof cue.phrase !== "string" || !cue.phrase.trim()) fail(`Cue ${cue.id} needs a phrase`);
      const normalizedText = segment.text.trim().toLocaleLowerCase().replace(/\s+/g, " ");
      const normalizedPhrase = cue.phrase.trim().toLocaleLowerCase().replace(/\s+/g, " ");
      const occurrences = normalizedText.split(normalizedPhrase).length - 1;
      if (occurrences === 0) fail(`Cue ${cue.id} phrase does not occur in segment ${segment.id}`);
      if (occurrences > 1) fail(`Cue ${cue.id} phrase occurs ${occurrences} times in segment ${segment.id}; use a longer unique phrase`);
      cueOwners.set(cue.id, segment.id);
      cueDetails.set(cue.id, {
        segmentId: segment.id,
        phrase: cue.phrase,
        text: segment.text,
        position: cuePhraseStart(segment.text, cue.phrase, `Cue ${cue.id}`),
      });
    }
  }

  const assetIds = new Set();
  for (const [index, asset] of (storyboard.assets || []).entries()) {
    if (!isPlainObject(asset) || typeof asset.id !== "string" || !asset.id.trim()) fail(`assets[${index}] needs an id`);
    if (assetIds.has(asset.id)) fail(`Duplicate asset id: ${asset.id}`);
    assetIds.add(asset.id);
    let assetPath = null;
    if (asset.path !== undefined) {
      assetPath = resolveRunPath(resolvedRunDir, asset.path, `Asset ${asset.id}.path`, { mustExist: true });
    }
    if (asset.sha256 !== undefined && !/^[a-f0-9]{64}$/i.test(asset.sha256)) fail(`Asset ${asset.id}.sha256 must be a 64-character hex digest`);
    if (assetPath && asset.sha256 !== undefined) {
      const actual = crypto.createHash("sha256").update(fs.readFileSync(assetPath)).digest("hex");
      if (actual !== asset.sha256.toLowerCase()) fail(`Asset ${asset.id}.sha256 does not match its local file`);
    }
    if (asset.source_url && (!asset.creator || !asset.license)) {
      fail(`Asset ${asset.id} has an external source but incomplete creator/license provenance`);
    }
  }

  const shotIds = new Set();
  const shotSegments = new Map();
  const shots = [];
  for (const [index, shot] of storyboard.shots.entries()) {
    if (!isPlainObject(shot)) fail(`shots[${index}] must be an object`);
    if (typeof shot.id !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(shot.id)) fail(`shots[${index}].id is invalid`);
    if (shotIds.has(shot.id)) fail(`Duplicate shot id: ${shot.id}`);
    shotIds.add(shot.id);
    shotSegments.set(shot.id, shot.segment_id);
    if (!segmentIds.has(shot.segment_id)) fail(`Shot ${shot.id} references unknown segment_id: ${shot.segment_id}`);
    if (shot.lane !== undefined && !SHOT_LANES.has(shot.lane)) {
      fail(`Shot ${shot.id}.lane must be one of: ${[...SHOT_LANES].join(", ")}`);
    }
    validateVisualOptions(shot);
    if (typeof shot.intent !== "string" || !shot.intent.trim()) fail(`Shot ${shot.id} needs a non-empty intent`);
    if (!isPlainObject(shot.enter) || typeof shot.enter.cue_id !== "string") fail(`Shot ${shot.id}.enter.cue_id is required`);
    if (cueOwners.get(shot.enter.cue_id) !== shot.segment_id) fail(`Shot ${shot.id} enter cue must belong to segment ${shot.segment_id}`);
    if (sceneNavigation) {
      const detail = cueDetails.get(shot.enter.cue_id);
      if (detail && !isSentenceStart(detail.text, detail.position)) {
        fail(
          `Shot ${shot.id} enter cue ${shot.enter.cue_id} is not at a sentence start; `
          + "manual Next boundaries must start a complete sentence and intra-sentence changes belong inside the component",
        );
      }
      if ((shot.enter?.offset_ms ?? 0) !== 0) {
        fail(`Shot ${shot.id}.enter.offset_ms must be 0 when project.scene_navigation is manual`);
      }
    }
    if (shot.exit !== undefined) {
      if (!isPlainObject(shot.exit) || typeof shot.exit.cue_id !== "string") fail(`Shot ${shot.id}.exit.cue_id is invalid`);
      if (cueOwners.get(shot.exit.cue_id) !== shot.segment_id) fail(`Shot ${shot.id} exit cue must belong to segment ${shot.segment_id}`);
    }
    for (const [label, anchor] of [["enter", shot.enter], ["exit", shot.exit]]) {
      if (anchor?.offset_ms !== undefined && (!Number.isInteger(anchor.offset_ms) || Math.abs(anchor.offset_ms) > 3_600_000)) {
        fail(`Shot ${shot.id}.${label}.offset_ms must be an integer within one hour`);
      }
    }
    if (shot.duration_ms !== undefined && (!Number.isInteger(shot.duration_ms) || shot.duration_ms <= 0 || shot.duration_ms > 3_600_000)) {
      fail(`Shot ${shot.id}.duration_ms must be a positive integer no greater than one hour`);
    }
    if (shot.exit === undefined && shot.duration_ms === undefined) {
      fail(`Shot ${shot.id} needs either exit or duration_ms`);
    }
    if (!isPlainObject(shot.renderer) || !RENDERER_KINDS.has(shot.renderer.kind)) {
      fail(`Shot ${shot.id}.renderer.kind must be one of: ${[...RENDERER_KINDS].join(", ")}`);
    }
    if (
      shot.renderer.variant !== undefined
      && (typeof shot.renderer.variant !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(shot.renderer.variant))
    ) {
      fail(`Shot ${shot.id}.renderer.variant must be a safe token of 1 to 64 characters`);
    }

    let entryPath = null;
    let sourceInfo = null;
    if (WEB_KINDS.has(shot.renderer.kind)) {
      entryPath = resolveRunPath(resolvedRunDir, shot.renderer.entry, `Shot ${shot.id}.renderer.entry`, { mustExist: true });
      if (path.extname(entryPath).toLowerCase() !== ".html") fail(`Shot ${shot.id}.renderer.entry must be an HTML file`);
      sourceInfo = validateShotHtml(entryPath, resolvedRunDir);
    }
    const composition = shot.lane
      ?? segmentHostLayouts.get(shot.segment_id)
      ?? storyboard.project.default_host_layout
      ?? fallbackHostLayout;
    if (composition === "support_top") {
      assertSupportTopGeometry(storyboard.project, dimensions, `Shot ${shot.id}`);
    }
    const compositionGeometry = composition === "support_top" ? SUPPORT_TOP_GEOMETRY : null;
    shots.push({ ...shot, entryPath, sourceInfo, composition, compositionGeometry });
  }

  if (Object.hasOwn(storyboard, "editorial_plan")) {
    validateEditorialPlan(storyboard.editorial_plan, {
      segmentIds,
      cueOwners,
      shotSegments,
      finalShotId: storyboard.shots.at(-1)?.id ?? null,
    });
  }

  let navigationScenes = null;
  let karaokeScenes = null;
  if (sceneNavigation || karaokeCaption?.enabled) {
    const excerpts = deriveKaraokeSceneExcerpts(storyboard);
    navigationScenes = excerpts.scenes;
    if (karaokeCaption?.enabled) {
    karaokeScenes = excerpts.scenes.map((scene) => ({
      id: scene.id,
      shot_ids: scene.shot_ids,
      host_only: scene.host_only,
      ...buildKaraokeTimeline(scene.text, karaokeCaption),
    }));
    }
  }

  return {
    storyboard,
    storyboardPath: resolvedStoryboard,
    runDir: resolvedRunDir,
    project: { ...dimensions, fps, theme: storyboard.project.theme || "light-editorial" },
    karaokeCaption,
    sceneNavigation,
    navigationScenes,
    karaokeScenes,
    layoutGeometries: { support_top: SUPPORT_TOP_GEOMETRY },
    shots,
    renderableShots: shots.filter((shot) => WEB_KINDS.has(shot.renderer.kind)),
  };
}

const PREVIEW_MIME_TYPES = Object.freeze({
  ".avif": "image/avif",
  ".gif": "image/gif",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".mp3": "audio/mpeg",
  ".mp4": "video/mp4",
  ".wav": "audio/wav",
  ".webm": "video/webm",
});

function localReferenceDataUrl(reference, htmlPath, runDir) {
  const value = String(reference || "").trim();
  if (!value || value.startsWith("#") || /^(?:data|blob|about):/i.test(value)) return value;
  if (/^(?:https?|wss?|file):/i.test(value) || value.startsWith("//")) {
    fail(`${path.basename(htmlPath)} cannot inline non-local preview reference: ${value}`);
  }
  const suffixIndex = value.search(/[?#]/);
  const pathname = suffixIndex >= 0 ? value.slice(0, suffixIndex) : value;
  const suffix = suffixIndex >= 0 ? value.slice(suffixIndex) : "";
  const resolved = path.resolve(path.dirname(htmlPath), decodeURIComponent(pathname));
  if (!isWithin(runDir, resolved) || !fs.existsSync(resolved)) {
    fail(`${path.basename(htmlPath)} cannot inline missing/out-of-run preview asset: ${value}`);
  }
  assertExistingPathInside(runDir, resolved, `Preview asset in ${path.basename(htmlPath)}`);
  const mime = PREVIEW_MIME_TYPES[path.extname(resolved).toLowerCase()] || "application/octet-stream";
  return `data:${mime};base64,${fs.readFileSync(resolved).toString("base64")}${suffix}`;
}

function inlinePreviewAssets(source, htmlPath, runDir) {
  let derived = source.replace(
    /\b(src|poster|href|xlink:href)\s*=\s*(["'])(.*?)\2/gis,
    (whole, attribute, quote, reference) => {
      const inlined = localReferenceDataUrl(reference, htmlPath, runDir);
      return `${attribute}=${quote}${inlined}${quote}`;
    },
  );
  derived = derived.replace(/\bsrcset\s*=\s*(["'])(.*?)\1/gis, (whole, quote, value) => {
    const inlined = value.split(",").map((candidate) => {
      const parts = candidate.trim().split(/\s+/);
      const reference = parts.shift();
      return [localReferenceDataUrl(reference, htmlPath, runDir), ...parts].join(" ");
    }).join(", ");
    return `srcset=${quote}${inlined}${quote}`;
  });
  return derived.replace(/url\(\s*(["']?)(.*?)\1\s*\)/gis, (whole, quote, reference) => {
    const inlined = localReferenceDataUrl(reference, htmlPath, runDir);
    const wrapper = quote || '"';
    return `url(${wrapper}${inlined}${wrapper})`;
  });
}

function previewBridgeScript(bridgeId) {
  return `<script>(()=>{"use strict";const bridgeId=${inlineJson(bridgeId)};const channel="hyperframe-preview-bridge";let state={status:"pending"};const send=()=>parent.postMessage({channel,bridgeId,...state},"*");addEventListener("message",event=>{if(event.data?.channel===channel&&event.data?.bridgeId===bridgeId&&event.data?.type==="ready-request")send()});const timeout=(message)=>new Promise((_,reject)=>setTimeout(()=>reject(new Error(message)),10000));const findApi=()=>new Promise((resolve,reject)=>{const started=performance.now();const poll=()=>{if(window.__hyperframe)return resolve(window.__hyperframe);if(performance.now()-started>=10000)return reject(new Error("Timed out after 10000ms waiting for window.__hyperframe"));requestAnimationFrame(poll)};poll()});addEventListener("load",async()=>{try{const api=await Promise.race([findApi(),timeout("Timed out after 10000ms waiting for window.__hyperframe")]);const source=typeof api.ready==="function"?api.ready.call(api):api.ready;const ready=await Promise.race([Promise.resolve(source),timeout("Timed out after 10000ms waiting for __hyperframe.ready")]);if(!ready)throw new Error("__hyperframe.ready resolved false");state={status:"ready"};send()}catch(error){state={status:"error",error:error instanceof Error?error.message:String(error)};send()}},{once:true})})();<\/script>`;
}

function sandboxedPreviewDocument(entryPath, runDir, bridgeId, componentContext) {
  const source = inlinePreviewAssets(fs.readFileSync(entryPath, "utf8"), entryPath, runDir);
  const policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; frame-src 'none'; child-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
  const contextScript = `<script>Object.defineProperty(window,"__hyperframeContext",{configurable:false,enumerable:true,writable:false,value:Object.freeze(${inlineJson(componentContext)})});<\/script>`;
  const csp = `<meta http-equiv="Content-Security-Policy" content="${policy}">${contextScript}`;
  const withCsp = /<head(?:\s[^>]*)?>/i.test(source)
    ? source.replace(/<head(?:\s[^>]*)?>/i, (head) => `${head}${csp}`)
    : `${csp}${source}`;
  const bridge = previewBridgeScript(bridgeId);
  if (/<\/body\s*>/i.test(withCsp)) return withCsp.replace(/<\/body\s*>/i, `${bridge}</body>`);
  return `${withCsp}${bridge}`;
}

function previewDocument(model, outputPath, { karaokeOverlay = "hidden" } = {}) {
  const previewDir = path.dirname(outputPath);
  const karaokePlanned = Boolean(model.karaokeCaption?.enabled);
  const karaokeEnabled = karaokePlanned && karaokeOverlay === "visible";
  const navigationPlanned = Array.isArray(model.navigationScenes);
  const karaokeLayer = karaokeEnabled
    ? `<div class="karaoke-surface" data-karaoke-surface aria-live="off" style="width:${model.project.width}px;height:${model.project.height}px">
          <div class="karaoke-caption is-hidden" data-karaoke-caption style="bottom:${model.karaokeCaption.bottom_margin_px}px;--karaoke-max-lines:${model.karaokeCaption.max_lines}">
            <div class="karaoke-words" data-karaoke-words></div>
          </div>
        </div>`
    : "";
  const shotById = new Map(model.shots.map((shot) => [shot.id, shot]));
  const previewItems = navigationPlanned
    ? model.navigationScenes.map((scene, index) => {
      const groupedShots = scene.shot_ids.map((shotId) => shotById.get(shotId)).filter(Boolean);
      const primary = groupedShots[0] || null;
      return {
        id: scene.host_only ? "host-only-prefix" : scene.id,
        scene,
        groupedShots,
        primary,
        composition: primary?.composition || "host_only",
        compositionGeometry: primary?.compositionGeometry || SUPPORT_TOP_GEOMETRY,
        index,
      };
    })
    : model.shots.map((shot, index) => ({
      id: shot.id,
      scene: null,
      groupedShots: [shot],
      primary: shot,
      composition: shot.composition,
      compositionGeometry: shot.compositionGeometry,
      index,
    }));
  const shotStages = previewItems.map((item, index) => {
    const shot = item.primary;
    const groupedLabel = item.groupedShots.map((member) => member.id).join(" + ");
    const title = `${String(index + 1).padStart(2, "0")} · ${groupedLabel || "Host-only prefix"}`;
    const geometryAttributes = item.compositionGeometry
      ? ' data-capture-stage="0,0,432,768" data-visual-frame="0,0,432,432" data-host-frame="0,432,432,336"'
      : "";
    const groupAttributes = navigationPlanned
      ? ` data-karaoke-scene-id="${htmlEscape(item.id)}" data-shot-ids="${htmlEscape(item.scene.shot_ids.join(" "))}"`
      : "";
    if (!shot) {
      return `<article class="shot host-only-shot" data-shot-id="host-only-prefix" data-shot-index="${index}" data-composition="host_only"${geometryAttributes}${groupAttributes}>
        <div class="stage" data-stage data-width="${model.project.width}" data-height="${model.project.height}" style="width:${model.project.width}px;height:${model.project.height}px"><div class="host-only-surface" data-stage-surface style="width:${model.project.width}px;height:${model.project.height}px"></div>${karaokeLayer}</div>
      </article>`;
    }
    if (shot.entryPath) {
      const relative = toPosix(path.relative(previewDir, shot.entryPath));
      const bridgeId = `scene-${index}-${shot.id}`;
      const componentContext = {
        shotId: shot.id,
        sceneId: item.id,
        variant: shot.renderer.variant ?? null,
      };
      const source = `srcdoc="${htmlEscape(sandboxedPreviewDocument(shot.entryPath, model.runDir, bridgeId, componentContext))}" data-component-src="${htmlEscape(relative)}" data-bridge-id="${htmlEscape(bridgeId)}" sandbox="allow-scripts"`;
      return `<article class="shot web-shot" data-shot-id="${htmlEscape(shot.id)}" data-shot-index="${index}" data-composition="${htmlEscape(item.composition)}"${geometryAttributes}${groupAttributes}>
        <div class="stage" data-stage data-width="${model.project.width}" data-height="${model.project.height}" style="width:${model.project.width}px;height:${model.project.height}px"><iframe data-stage-surface title="${htmlEscape(title)}" ${source} width="${model.project.width}" height="${model.project.height}" loading="lazy"></iframe>${karaokeLayer}</div>
      </article>`;
    }
    return `<article class="shot unrendered" data-shot-id="${htmlEscape(shot.id)}" data-shot-index="${index}" data-composition="${htmlEscape(item.composition)}"${geometryAttributes}${groupAttributes}>
      <div class="stage" data-stage data-width="${model.project.width}" data-height="${model.project.height}" style="width:${model.project.width}px;height:${model.project.height}px"><div class="placeholder" data-stage-surface style="width:${model.project.width}px;height:${model.project.height}px"><span>${htmlEscape(shot.renderer.kind.replaceAll("_", " "))}</span><small>This modality needs its own capture or licensed source asset.</small></div>${karaokeLayer}</div>
    </article>`;
  }).join("\n");

  const shotDetails = previewItems.map((item, index) => {
    const shot = item.primary;
    const groupedLabel = item.groupedShots.map((member) => member.id).join(" + ");
    const title = `${String(index + 1).padStart(2, "0")} · ${groupedLabel || "Host-only prefix"}`;
    const cue = shot ? `${shot.enter.cue_id}${shot.exit?.cue_id ? ` → ${shot.exit.cue_id}` : ""}` : "before first visual cue";
    const composition = item.compositionGeometry
      ? "composition: support_top · desktop capture 432 x 768 · visual 432 x 432 at (0, 0) · blank host/camera frame 432 x 336 at (0, 432)"
      : `composition: ${item.composition}`;
    const action = shot?.entryPath
      ? `<button type="button" data-reload="${index}">Restart</button>`
      : shot ? `<b>UNRENDERED · ${htmlEscape(shot.renderer.kind)}</b>` : `<b>HOST ONLY</b>`;
    const intents = item.groupedShots.length
      ? item.groupedShots.map((member) => `${member.id}: ${member.intent}`).join(" · ")
      : "Host-only spoken prefix before the first visual cue.";
    return `<article class="shot-detail" data-shot-detail-index="${index}">
      <header><div><strong>${htmlEscape(title)}</strong><span>${htmlEscape(shot?.renderer.kind || "host_only")} · ${htmlEscape(composition)} · ${htmlEscape(cue)}</span></div>${action}</header>
      <p>${htmlEscape(intents)}</p>
    </article>`;
  }).join("\n");

  const dots = previewItems.map((item, index) =>
    `<button type="button" class="dot" data-go="${index}" aria-label="Go to scene ${index + 1}: ${htmlEscape(item.id)}"></button>`,
  ).join("");

  const karaokeCss = karaokeEnabled ? `.host-only-surface{position:absolute;left:0;top:0;display:block;background:linear-gradient(180deg,#101b2a,#080f19);transform-origin:top left}.karaoke-surface{position:absolute;left:0;top:0;z-index:5;pointer-events:none;transform-origin:top left}.karaoke-caption{position:absolute;left:50%;width:calc(100% - 36px);max-width:396px;padding:10px 14px;overflow:hidden;transform:translateX(-50%);border:1px solid #ffffff33;border-radius:14px;background:rgba(3,10,20,.78);box-shadow:0 9px 28px #0008;text-align:center;color:#fff;opacity:1;visibility:visible;backdrop-filter:blur(7px);transition:opacity .12s ease,visibility 0s linear}.karaoke-caption.is-hidden,.karaoke-caption.is-ended{opacity:0;visibility:hidden;transition:opacity .12s ease,visibility 0s linear .12s}.karaoke-words{max-height:calc(var(--karaoke-max-lines) * 1.32em);overflow:hidden;font-size:20px;line-height:1.32;font-weight:850;letter-spacing:-.015em;white-space:normal;overflow-wrap:anywhere;text-wrap:balance}.karaoke-word{display:inline;color:#f8fafc}.karaoke-word.is-current{color:#ffe071;text-shadow:0 0 12px #ffda6670}.karaoke-caption.is-paused{border-color:#ffd47a80}` : "";
  const karaokeRuntime = karaokeEnabled ? `
    const karaokeScenes = ${inlineJson(model.karaokeScenes)};
    let karaokeFrame = null;
    let karaokeGeneration = 0;
    let karaokeStartedAt = 0;
    let karaokeElapsed = 0;
    let karaokePaused = false;
    let karaokeRunningIndex = -1;

    function karaokeElements(index) {
      const layer = shots[index]?.querySelector('[data-karaoke-surface]');
      return {
        layer,
        caption: layer?.querySelector('[data-karaoke-caption]'),
        words: layer?.querySelector('[data-karaoke-words]'),
      };
    }

    function setKaraokeState(index, { ended = false, paused = false, visible = false } = {}) {
      const elements = karaokeElements(index);
      if (!elements.layer) return;
      elements.caption.classList.toggle('is-ended', ended);
      elements.caption.classList.toggle('is-paused', paused);
      elements.caption.classList.toggle('is-hidden', !visible);
    }

    function activeKaraokeWord(scene, time) {
      for (let index = 0; index < scene.words.length; index += 1) {
        const word = scene.words[index];
        if (time >= word.start_ms && time < word.spoken_end_ms) return index;
        if (time < word.start_ms) break;
      }
      return -1;
    }

    function renderKaraoke(index, milliseconds) {
      const scene = karaokeScenes[index];
      const elements = karaokeElements(index);
      if (!scene || !elements.layer) return;
      const time = Math.max(0, Math.min(scene.duration_ms, Number(milliseconds) || 0));
      const activeWord = activeKaraokeWord(scene, time);
      const page = activeWord >= 0 ? scene.words[activeWord].page : -1;
      if (activeWord >= 0 && elements.words.dataset.page !== String(page)) {
        elements.words.replaceChildren();
        let first = true;
        for (const word of scene.words) {
          if (word.page !== page) continue;
          if (!first) elements.words.append(document.createTextNode(' '));
          const span = document.createElement('span');
          span.className = 'karaoke-word';
          span.dataset.wordIndex = String(word.index);
          span.textContent = word.text;
          elements.words.append(span);
          first = false;
        }
        elements.words.dataset.page = String(page);
      }
      elements.words.querySelectorAll('[data-word-index]').forEach((node) => {
        const wordIndex = Number(node.dataset.wordIndex);
        node.classList.toggle('is-current', wordIndex === activeWord);
      });
      const ended = time >= scene.duration_ms;
      const visible = activeWord >= 0 && !ended;
      elements.layer.dataset.karaokeTime = String(Math.round(time));
      elements.layer.dataset.karaokeEnded = String(ended);
      elements.layer.dataset.karaokePaused = String(karaokePaused);
      elements.layer.dataset.karaokeVisible = String(visible);
      elements.layer.dataset.karaokeActiveWord = activeWord >= 0 ? String(activeWord) : '';
      elements.layer.dataset.karaokePage = page >= 0 ? String(page) : '';
      setKaraokeState(index, { ended, paused: karaokePaused, visible });
    }

    function stopKaraokeFrame() {
      if (karaokeFrame !== null) cancelAnimationFrame(karaokeFrame);
      karaokeFrame = null;
    }

    function karaokeTick(now) {
      karaokeFrame = null;
      if (karaokePaused || karaokeRunningIndex !== active) return;
      const scene = karaokeScenes[karaokeRunningIndex];
      karaokeElapsed = Math.min(scene.duration_ms, Math.max(0, now - karaokeStartedAt));
      renderKaraoke(karaokeRunningIndex, karaokeElapsed);
      if (karaokeElapsed < scene.duration_ms) karaokeFrame = requestAnimationFrame(karaokeTick);
    }

    const bridgeChannel = 'hyperframe-preview-bridge';

    function waitForBridgeReady(frame) {
      if (!frame) return Promise.resolve('surface-ready');
      const bridgeId = frame.dataset.bridgeId;
      if (!bridgeId) return Promise.reject(new Error('Sandboxed scene is missing data-bridge-id'));
      return new Promise((resolve, reject) => {
        let settled = false;
        const finish = (callback, value) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeoutId);
          clearInterval(requestId);
          window.removeEventListener('message', onMessage);
          callback(value);
        };
        const onMessage = (event) => {
          if (event.source !== frame.contentWindow || event.data?.channel !== bridgeChannel || event.data?.bridgeId !== bridgeId) return;
          if (event.data.status === 'ready') finish(resolve, 'bridge-ready');
          if (event.data.status === 'error') finish(reject, new Error(event.data.error || 'Scene readiness bridge failed'));
        };
        const requestReady = () => {
          try {
            frame.contentWindow?.postMessage({ channel: bridgeChannel, bridgeId, type: 'ready-request' }, '*');
          } catch {
            // The next request runs after the child browsing context is available.
          }
        };
        const timeoutId = setTimeout(() => {
          finish(reject, new Error('Timed out after 10000ms waiting for sandboxed __hyperframe.ready bridge'));
        }, 10_000);
        const requestId = setInterval(requestReady, 50);
        window.addEventListener('message', onMessage);
        frame.addEventListener('load', requestReady, { once: true });
        requestReady();
      });
    }

    function waitForStageReady(shot) {
      return waitForBridgeReady(shot?.querySelector('iframe'));
    }

    function reloadFrameAndWait(shot) {
      const frame = shot?.querySelector('iframe');
      if (!frame) return Promise.resolve('surface-ready');
      const source = frame.getAttribute('srcdoc');
      const replacement = frame.cloneNode(false);
      replacement.removeAttribute('srcdoc');
      frame.replaceWith(replacement);
      const ready = waitForBridgeReady(replacement);
      replacement.srcdoc = source;
      return ready;
    }

    async function restartKaraoke(index, readyPromise) {
      karaokeGeneration += 1;
      const generation = karaokeGeneration;
      stopKaraokeFrame();
      karaokePaused = false;
      karaokeElapsed = 0;
      karaokeRunningIndex = index;
      const elements = karaokeElements(index);
      if (elements.words) {
        elements.words.replaceChildren();
        delete elements.words.dataset.page;
      }
      setKaraokeState(index);
      try {
        const readiness = await readyPromise;
        if (elements.layer) elements.layer.dataset.karaokeReadyMode = String(readiness);
      } catch (error) {
        if (generation === karaokeGeneration) {
          const layer = karaokeElements(index).layer;
          if (layer) layer.dataset.karaokeError = error instanceof Error ? error.message : String(error);
          setKaraokeState(index);
        }
        return;
      }
      if (generation !== karaokeGeneration || index !== active) return;
      renderKaraoke(index, 0);
      karaokeStartedAt = performance.now();
      karaokeFrame = requestAnimationFrame(karaokeTick);
    }

    function toggleKaraokePause() {
      if (karaokeRunningIndex !== active) return;
      const scene = karaokeScenes[active];
      if (!scene || karaokeElapsed >= scene.duration_ms) return;
      karaokePaused = !karaokePaused;
      if (karaokePaused) {
        stopKaraokeFrame();
        renderKaraoke(active, karaokeElapsed);
        return;
      }
      karaokeStartedAt = performance.now() - karaokeElapsed;
      renderKaraoke(active, karaokeElapsed);
      karaokeFrame = requestAnimationFrame(karaokeTick);
    }
  ` : "";

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>HyperFrames scene carousel</title>
  <style>
    :root{color-scheme:dark;--bg:#06101d;--card:#101d2e;--line:#2a3b52;--text:#f5f7fb;--muted:#9fb0c4;--accent:#54d8ff;--warn:#ffbd59}*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;min-height:100vh;overflow-x:hidden;background:radial-gradient(circle at 78% 0,#11304a 0,transparent 38rem),var(--bg);color:var(--text);font:15px/1.5 ui-sans-serif,system-ui,sans-serif}button{font:inherit}.capture-viewport{width:100%;height:100vh;display:grid;place-items:center;overflow:hidden;background:#06101d}.viewport{width:100%;height:100%;display:grid;place-items:center}.shot{display:none;width:100%;height:100%;place-items:center}.shot.is-active{display:grid}.stage{position:relative;background:#030712;overflow:hidden;box-shadow:0 22px 60px #0007}.stage iframe,.placeholder{position:absolute;inset:0 auto auto 0;display:block;transform-origin:top left}.stage iframe{border:0}.placeholder{display:grid;place-content:center;text-align:center;gap:8px;background:repeating-linear-gradient(135deg,#111827,#111827 18px,#0d1421 18px,#0d1421 36px);color:var(--warn);text-transform:uppercase;font-weight:900;letter-spacing:.12em}.placeholder small{max-width:28ch;color:var(--muted);font-weight:500;letter-spacing:0;text-transform:none}${karaokeCss}.review-panel{width:min(1320px,calc(100% - 28px));margin:auto;padding:26px 0 34px}.hero{display:flex;justify-content:space-between;gap:22px;align-items:end;margin-bottom:18px}.eyebrow{color:var(--accent);font-weight:800;letter-spacing:.14em;text-transform:uppercase}.hero h1{font-size:clamp(27px,4vw,52px);line-height:1;margin:.2em 0}.hero p,.shot-detail p{color:var(--muted)}.hero p{margin:.4em 0 0}.meta{padding:10px 14px;border:1px solid var(--line);border-radius:14px;background:#0a1626;white-space:nowrap}.shot-detail{display:none;background:linear-gradient(160deg,#111f32,#0b1524);border:1px solid var(--line);border-radius:20px;overflow:hidden;box-shadow:0 22px 60px #0007}.shot-detail.is-active{display:block}.shot-detail header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:13px 17px}.shot-detail header div{display:grid;gap:2px}.shot-detail header span{color:var(--muted);font-size:12px}.shot-detail header button,.nav-button{border:1px solid var(--line);background:#17283e;color:var(--text);border-radius:999px;padding:8px 14px;cursor:pointer}.shot-detail header button:hover,.nav-button:hover:not(:disabled){border-color:var(--accent);background:#1b314c}.shot-detail header b{color:var(--warn);font-size:11px;letter-spacing:.08em}.shot-detail p{margin:0;padding:13px 17px}.controls{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:18px;margin-top:16px}.scene-status{text-align:center;color:var(--muted);font-weight:700}.dots{display:flex;justify-content:center;flex-wrap:wrap;gap:8px;margin-top:13px}.dot{width:9px;height:9px;padding:0;border:0;border-radius:50%;background:#40536d;cursor:pointer}.dot.is-active{width:28px;border-radius:999px;background:var(--accent);box-shadow:0 0 18px #54d8ff80}@media(max-width:720px){.review-panel{width:min(100% - 16px,1320px);padding-top:14px}.hero{align-items:start;flex-direction:column}.meta{white-space:normal}.controls{grid-template-columns:1fr 1fr}.scene-status{grid-column:1/-1;grid-row:1}.nav-button{grid-row:2}}
  </style>
</head>
<body><main>
  <section class="capture-viewport" data-capture-viewport aria-label="Current HyperFrame capture stage">
    <div class="viewport">${shotStages || '<p>No shots in this storyboard.</p>'}</div>
  </section>
  <section class="review-panel" data-review-panel>
    <section class="hero"><div><div class="eyebrow">Storyboard v${htmlEscape(model.storyboard.schema_version)}</div><h1>HyperFrames carousel</h1><p>Use Previous / Next or the left and right arrow keys. Each scene restarts when selected.</p></div><div class="meta">${htmlEscape(model.project.theme)} · ${model.project.width} × ${model.project.height} · ${model.project.fps} fps · ${previewItems.length} scenes${karaokePlanned ? ` · karaoke ${karaokeEnabled ? "visible" : "hidden"}` : ""}</div></section>
    <section class="carousel" aria-label="Storyboard scene review controls">
      <div class="details">${shotDetails || '<p>No shot metadata in this storyboard.</p>'}</div>
    <nav class="controls" aria-label="Scene navigation"><button type="button" class="nav-button" data-prev>← Previous</button><div class="scene-status" aria-live="polite"><span data-current>1</span> / ${previewItems.length}</div><button type="button" class="nav-button" data-next>Next →</button></nav>
    <div class="dots" aria-label="Choose a scene">${dots}</div>
    </section>
  </section>
</main><script>
  (() => {
    const shots = [...document.querySelectorAll('[data-shot-index]')];
    const details = [...document.querySelectorAll('[data-shot-detail-index]')];
    const dots = [...document.querySelectorAll('[data-go]')];
    const previous = document.querySelector('[data-prev]');
    const next = document.querySelector('[data-next]');
    const current = document.querySelector('[data-current]');
    let active = 0;

    ${karaokeRuntime}

    ${calculatePreviewScale.toString()}

    function fitFrames() {
      const captureViewport = document.querySelector('[data-capture-viewport]');
      const availableWidth = captureViewport?.clientWidth || window.innerWidth;
      const availableHeight = captureViewport?.clientHeight || window.innerHeight;
      document.querySelectorAll('[data-stage]').forEach((stage) => {
        const surface = stage.querySelector('[data-stage-surface]');
        const width = Number(stage.dataset.width);
        const height = Number(stage.dataset.height);
        const shot = stage.closest('.shot');
        if (!surface || !width || !height || !shot?.classList.contains('is-active')) return;
        const scale = calculatePreviewScale(width, height, availableWidth, availableHeight);
        const scaledWidth = width * scale;
        const scaledHeight = height * scale;
        stage.style.width = scaledWidth + 'px';
        stage.style.height = scaledHeight + 'px';
        stage.dataset.previewScale = String(scale);
        surface.style.width = width + 'px';
        surface.style.height = height + 'px';
        surface.style.transform = 'scale(' + scale + ')';
        ${karaokeEnabled ? `stage.querySelectorAll('[data-karaoke-surface]').forEach((karaokeSurface) => {
          karaokeSurface.style.width = width + 'px';
          karaokeSurface.style.height = height + 'px';
          karaokeSurface.style.transform = 'scale(' + scale + ')';
        });` : ""}
      });
    }

    function restartFrame(shot) {
      const frame = shot?.querySelector('iframe');
      if (!frame) return;
      const source = frame.getAttribute('srcdoc');
      if (source === null) {
        frame.src = frame.getAttribute('src');
        return;
      }
      const replacement = frame.cloneNode(false);
      replacement.removeAttribute('srcdoc');
      frame.replaceWith(replacement);
      replacement.srcdoc = source;
    }

    function revealCapture() {
      document.querySelector('[data-capture-viewport]')?.scrollIntoView({ block: 'start' });
    }

    function show(index, restart = true) {
      if (!shots.length) return;
      active = Math.max(0, Math.min(shots.length - 1, index));
      shots.forEach((shot, shotIndex) => {
        const selected = shotIndex === active;
        shot.classList.toggle('is-active', selected);
        shot.setAttribute('aria-hidden', String(!selected));
      });
      details.forEach((detail, detailIndex) => {
        const selected = detailIndex === active;
        detail.classList.toggle('is-active', selected);
        detail.setAttribute('aria-hidden', String(!selected));
      });
      dots.forEach((dot, dotIndex) => dot.classList.toggle('is-active', dotIndex === active));
      previous.disabled = active === 0;
      next.disabled = active === shots.length - 1;
      current.textContent = String(active + 1);
      ${karaokeEnabled
        ? "if (restart) restartKaraoke(active, reloadFrameAndWait(shots[active])); else restartKaraoke(active, waitForStageReady(shots[active]));"
        : "if (restart) restartFrame(shots[active]);"}
      fitFrames();
    }

    document.querySelectorAll('[data-reload]').forEach((button) => button.addEventListener('click', () => {
      const index = Number(button.dataset.reload);
      ${karaokeEnabled
        ? "restartKaraoke(index, reloadFrameAndWait(shots[index]));"
        : "restartFrame(shots[index]);"}
      revealCapture();
    }));
    dots.forEach((dot) => dot.addEventListener('click', () => {
      show(Number(dot.dataset.go));
      revealCapture();
    }));
    previous.addEventListener('click', () => {
      show(active - 1);
      revealCapture();
    });
    next.addEventListener('click', () => {
      show(active + 1);
      revealCapture();
    });
    window.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowLeft') {
        show(active - 1);
        revealCapture();
      }
      if (event.key === 'ArrowRight') {
        if (active < shots.length - 1) { show(active + 1); revealCapture(); }
      }
      ${karaokeEnabled ? `
      const editable = /^(?:INPUT|TEXTAREA|SELECT|BUTTON)$/.test(event.target?.tagName || '') || event.target?.isContentEditable;
      if (!editable && !event.repeat && event.code === 'Space') {
        event.preventDefault();
        toggleKaraokePause();
      }
      if (!editable && !event.repeat && event.key.toLowerCase() === 'r') {
        event.preventDefault();
        restartKaraoke(active, reloadFrameAndWait(shots[active]));
        revealCapture();
      }` : ""}
    });
    window.addEventListener('resize', fitFrames);
    show(0, false);
  })();
</script></body></html>`;
}

export function writePreview(model, outputPath, options = {}) {
  const resolved = path.resolve(outputPath);
  assertWritablePathInside(model.runDir, resolved, "Preview output");
  fs.mkdirSync(path.dirname(resolved), { recursive: true });
  fs.writeFileSync(resolved, previewDocument(model, resolved, options), "utf8");
  return resolved;
}

function configuredModuleCandidates(configured) {
  if (!configured) return ["playwright"];
  if (!path.isAbsolute(configured) && !configured.startsWith(".")) return [configured];
  const resolved = path.resolve(configured);
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isDirectory()) return [pathToFileURL(resolved).href];
  const candidates = [];
  const packageJson = path.join(resolved, "package.json");
  if (fs.existsSync(packageJson)) {
    const manifest = readJson(packageJson, "Playwright package.json");
    if (typeof manifest.module === "string") candidates.push(pathToFileURL(path.join(resolved, manifest.module)).href);
    if (typeof manifest.main === "string") candidates.push(pathToFileURL(path.join(resolved, manifest.main)).href);
  }
  for (const entry of ["index.mjs", "index.js"]) {
    const candidate = path.join(resolved, entry);
    if (fs.existsSync(candidate)) candidates.push(pathToFileURL(candidate).href);
  }
  return candidates;
}

async function loadPlaywright(configured) {
  const errors = [];
  for (const candidate of configuredModuleCandidates(configured)) {
    try {
      const imported = await import(candidate);
      const chromium = imported.chromium || imported.default?.chromium;
      if (!chromium) throw new Error("module does not export chromium");
      return { chromium, source: candidate };
    } catch (error) {
      errors.push(`${candidate}: ${error.message}`);
    }
  }
  if (configured) {
    try {
      const require = createRequire(import.meta.url);
      const resolved = require.resolve(configured, { paths: [process.cwd()] });
      const imported = await import(pathToFileURL(resolved).href);
      const chromium = imported.chromium || imported.default?.chromium;
      if (chromium) return { chromium, source: resolved };
    } catch (error) {
      errors.push(`require.resolve(${configured}): ${error.message}`);
    }
  }
  fail(`Playwright is required for the render command and was not found. Install "playwright" or pass --playwright-module <module-or-path>. ${errors.join(" | ")}`);
}

function runProcess(command, args, label) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", (error) => reject(new Error(`${label} could not start: ${error.message}`)));
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(`${label} exited with code ${code}: ${(stderr || stdout).slice(-4000)}`));
    });
  });
}

function safeTempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "prepare-content-hyperframes-"));
}

function removeTempRoot(tempRoot) {
  const resolved = path.resolve(tempRoot);
  const tempParent = path.resolve(os.tmpdir());
  if (path.dirname(resolved) !== tempParent || !path.basename(resolved).startsWith("prepare-content-hyperframes-")) {
    fail(`Refusing to remove unexpected temporary path: ${resolved}`);
  }
  fs.rmSync(resolved, { recursive: true, force: true });
}

function outputFileName(shotId) {
  return `${shotId.replace(/[^A-Za-z0-9._-]/g, "_")}.mp4`;
}

async function runtimeContract(page, shot) {
  await page.waitForFunction(() => Boolean(window.__hyperframe), null, { timeout: 10_000 });
  return page.evaluate(async (shotId) => {
    const api = window.__hyperframe;
    if (!api || typeof api !== "object") throw new Error(`${shotId}: window.__hyperframe must be an object`);
    if (!Number.isFinite(api.durationMs) || api.durationMs <= 0) throw new Error(`${shotId}: __hyperframe.durationMs must be a positive finite number`);
    if (!("ready" in api)) throw new Error(`${shotId}: __hyperframe.ready is required`);
    if (typeof api.seek !== "function") throw new Error(`${shotId}: __hyperframe.seek must be a function`);
    const readiness = typeof api.ready === "function" ? api.ready() : api.ready;
    const readyValue = await Promise.race([
      Promise.resolve(readiness),
      new Promise((_, reject) => setTimeout(() => reject(new Error(`${shotId}: __hyperframe.ready timed out`)), 10_000)),
    ]);
    if (!readyValue) throw new Error(`${shotId}: __hyperframe.ready must resolve truthy`);
    return api.durationMs;
  }, shot.id);
}

async function renderShot({ browser, model, shot, outputDir, ffmpeg, tempRoot }) {
  const context = await browser.newContext({
    viewport: { width: model.project.width, height: model.project.height },
    deviceScaleFactor: 1,
    javaScriptEnabled: true,
    offline: true,
  });
  const frameDir = path.join(tempRoot, shot.id);
  fs.mkdirSync(frameDir, { recursive: true });
  try {
    await context.route("**/*", async (route) => {
      const url = route.request().url();
      try {
        const parsed = new URL(url);
        if (parsed.protocol === "file:") {
          const local = fileURLToPath(parsed);
          if (isWithin(model.runDir, local)) return route.continue();
        }
        if (["data:", "blob:", "about:"].includes(parsed.protocol)) return route.continue();
      } catch {
        // Invalid or non-local requests are blocked below.
      }
      return route.abort("blockedbyclient");
    });
    await context.addInitScript((componentContext) => {
      Object.defineProperty(window, "__hyperframeContext", {
        configurable: false,
        enumerable: true,
        writable: false,
        value: Object.freeze(componentContext),
      });
      const blocked = () => Promise.reject(new Error("Network access is disabled while rendering HyperFrames"));
      Object.defineProperty(window, "fetch", { configurable: false, value: blocked });
      for (const name of ["XMLHttpRequest", "WebSocket", "EventSource"]) {
        Object.defineProperty(window, name, { configurable: false, value: class NetworkDisabled { constructor() { throw new Error("Network access is disabled while rendering HyperFrames"); } } });
      }
      try { Object.defineProperty(navigator, "sendBeacon", { configurable: false, value: () => false }); } catch { /* browser-specific */ }
    }, {
      shotId: shot.id,
      sceneId: shot.id,
      variant: shot.renderer.variant ?? null,
    });
    const page = await context.newPage();
    page.setDefaultTimeout(15_000);
    await page.goto(pathToFileURL(shot.entryPath).href, { waitUntil: "load", timeout: 15_000 });
    const declaredDuration = await runtimeContract(page, shot);
    const durationMs = shot.duration_ms ?? Math.round(declaredDuration);
    if (durationMs > declaredDuration) {
      fail(`Shot ${shot.id}.duration_ms (${durationMs}) exceeds __hyperframe.durationMs (${declaredDuration})`);
    }
    const frameCount = Math.max(1, Math.ceil(durationMs * model.project.fps / 1000));
    for (let frame = 0; frame < frameCount; frame += 1) {
      const timeMs = Math.min(durationMs, frame * 1000 / model.project.fps);
      await page.evaluate(async (value) => {
        await Promise.resolve(window.__hyperframe.seek(value));
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      }, timeMs);
      const framePath = path.join(frameDir, `${String(frame).padStart(6, "0")}.png`);
      await page.screenshot({ path: framePath, type: "png", animations: "disabled" });
    }
    fs.mkdirSync(outputDir, { recursive: true });
    const outputPath = path.join(outputDir, outputFileName(shot.id));
    await runProcess(ffmpeg, [
      "-hide_banner", "-loglevel", "error", "-y",
      "-framerate", String(model.project.fps),
      "-i", path.join(frameDir, "%06d.png"),
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
      outputPath,
    ], `ffmpeg for shot ${shot.id}`);
    const digest = crypto.createHash("sha256").update(fs.readFileSync(outputPath)).digest("hex");
    return {
      id: shot.id,
      status: "rendered",
      renderer: shot.renderer.kind,
      source: toPosix(path.relative(model.runDir, shot.entryPath)),
      output: toPosix(path.relative(model.runDir, outputPath)),
      duration_ms: durationMs,
      fps: model.project.fps,
      frames: frameCount,
      width: model.project.width,
      height: model.project.height,
      sha256: digest,
    };
  } finally {
    await context.close();
  }
}

export async function renderStoryboard(model, options = {}) {
  if (model.renderableShots.length === 0) fail("Storyboard has no html/component shots to render");
  const outputDir = path.resolve(options.outputDir || path.join(model.runDir, "creator-pack", "assets"));
  const manifestPath = path.resolve(options.manifest || path.join(model.runDir, "creator-pack", "render_manifest.json"));
  assertWritablePathInside(model.runDir, outputDir, "Render output directory");
  assertWritablePathInside(model.runDir, manifestPath, "Render manifest");
  const { chromium, source: playwrightSource } = await loadPlaywright(options.playwrightModule);
  const browser = await chromium.launch({ headless: true });
  const tempRoot = safeTempRoot();
  const manifest = {
    schema_version: "1.0",
    storyboard: toPosix(path.relative(model.runDir, model.storyboardPath)),
    renderer: "render_web_asset.mjs",
    playwright: playwrightSource,
    ffmpeg: options.ffmpeg || "ffmpeg",
    shots: [],
  };
  try {
    for (const shot of model.renderableShots) {
      const rendered = await renderShot({
        browser,
        model,
        shot,
        outputDir,
        ffmpeg: options.ffmpeg || "ffmpeg",
        tempRoot,
      });
      manifest.shots.push(rendered);
    }
    fs.mkdirSync(path.dirname(manifestPath), { recursive: true });
    fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
    return { manifest, manifestPath };
  } catch (error) {
    manifest.error = error.message;
    fs.mkdirSync(path.dirname(manifestPath), { recursive: true });
    fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
    throw error;
  } finally {
    try {
      await browser.close();
    } finally {
      removeTempRoot(tempRoot);
    }
  }
}

function parseCli(argv) {
  const args = [...argv];
  const command = args.shift();
  const options = {};
  while (args.length) {
    const token = args.shift();
    if (token === "-h" || token === "--help") {
      options.help = true;
      continue;
    }
    if (!token.startsWith("--")) fail(`Unexpected argument: ${token}`);
    const equals = token.indexOf("=");
    const key = token.slice(2, equals === -1 ? undefined : equals).replaceAll("-", "_");
    const inline = equals === -1 ? undefined : token.slice(equals + 1);
    if (inline !== undefined) options[key] = inline;
    else {
      if (!args.length || args[0].startsWith("--")) fail(`Option --${key.replaceAll("_", "-")} requires a value`);
      options[key] = args.shift();
    }
  }
  return { command, options };
}

function validateCliOptions(command, options) {
  const common = new Set(["storyboard", "run_dir", "help"]);
  const allowed = new Set(common);
  if (command === "preview") {
    allowed.add("output");
    allowed.add("karaoke_overlay");
  }
  if (command === "render") {
    for (const name of ["output_dir", "manifest", "playwright_module", "ffmpeg"]) allowed.add(name);
  }
  const unknown = Object.keys(options).filter((name) => !allowed.has(name));
  if (unknown.length) fail(`Unknown option(s) for ${command}: ${unknown.map((name) => `--${name.replaceAll("_", "-")}`).join(", ")}`);
}

function usage() {
  return `Usage:
  node scripts/render_web_asset.mjs validate --storyboard <path> [--run-dir <path>]
  node scripts/render_web_asset.mjs preview  --storyboard <path> [--run-dir <path>] [--output <path>]
                                            [--karaoke-overlay visible|hidden]
  node scripts/render_web_asset.mjs render   --storyboard <path> [--run-dir <path>] [--output-dir <path>]
                                            [--manifest <path>] [--playwright-module <module-or-path>]
                                            [--ffmpeg <executable>]

The storyboard and every local asset must stay under the run directory. Web
shots use renderer.kind "html" or "component" and a run-relative
renderer.entry pointing to standalone HTML with window.__hyperframe.`;
}

async function main() {
  const { command, options } = parseCli(process.argv.slice(2));
  if (options.help || !command || command === "--help" || command === "-h") {
    console.log(usage());
    return;
  }
  if (!["validate", "preview", "render"].includes(command)) fail(`Unknown command: ${command}\n${usage()}`);
  validateCliOptions(command, options);
  if (!options.storyboard) fail(`--storyboard is required\n${usage()}`);
  const storyboardPath = path.resolve(options.storyboard);
  const runDir = path.resolve(options.run_dir || inferRunDir(storyboardPath));
  const model = validateStoryboard(storyboardPath, runDir);
  if (command === "validate") {
    console.log(JSON.stringify({
      ok: true,
      storyboard: model.storyboardPath,
      run_dir: model.runDir,
      shots: model.shots.length,
      renderable_shots: model.renderableShots.length,
      project: model.project,
      layout_geometries: model.layoutGeometries,
    }, null, 2));
    return;
  }
  if (command === "preview") {
    const karaokeOverlay = options.karaoke_overlay || "hidden";
    if (!["visible", "hidden"].includes(karaokeOverlay)) {
      fail('--karaoke-overlay must be either "visible" or "hidden"');
    }
    const output = writePreview(
      model,
      options.output || path.join(runDir, "creator-pack", "hyperframes_preview.html"),
      { karaokeOverlay },
    );
    console.log(JSON.stringify({
      ok: true,
      preview: output,
      shots: model.shots.length,
      karaoke_overlay: karaokeOverlay,
    }, null, 2));
    return;
  }
  const result = await renderStoryboard(model, {
    outputDir: options.output_dir,
    manifest: options.manifest,
    playwrightModule: options.playwright_module,
    ffmpeg: options.ffmpeg,
  });
  console.log(JSON.stringify({ ok: true, manifest: result.manifestPath, shots: result.manifest.shots.length }, null, 2));
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(SCRIPT_PATH)) {
  main().catch((error) => {
    console.error(`ERROR: ${error.message}`);
    process.exitCode = 1;
  });
}
