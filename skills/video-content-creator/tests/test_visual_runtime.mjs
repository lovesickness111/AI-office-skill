import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

import {
  buildKaraokeTimeline,
  calculatePreviewScale,
  deriveKaraokeSceneExcerpts,
  isSentenceStart,
  normalizeKaraokeCaptionConfig,
  normalizeSceneNavigationConfig,
  validateStoryboard,
} from "../scripts/render_web_asset.mjs";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const skillDir = path.resolve(testDir, "..");
const renderer = path.join(skillDir, "scripts", "render_web_asset.mjs");
const starter = path.join(skillDir, "assets", "animation-starter", "index.html");

function fixture() {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "prepare-content-visual-test-"));
  const runDir = path.join(tempRoot, "run");
  const storyboardDir = path.join(runDir, "storyboard");
  const shotDir = path.join(runDir, "assets", "shot-01");
  fs.mkdirSync(storyboardDir, { recursive: true });
  fs.mkdirSync(shotDir, { recursive: true });
  fs.copyFileSync(starter, path.join(shotDir, "index.html"));
  fs.writeFileSync(path.join(runDir, "run_manifest.json"), "{}\n", "utf8");
  const storyboardPath = path.join(storyboardDir, "storyboard.json");
  const storyboard = {
    schema_version: "1.0",
    project: { ratio: "9:16", width: 432, height: 768, fps: 30 },
    segments: [{
      id: "segment-01",
      text: "The architecture splits here and the result becomes visible.",
      cues: [{ id: "cue-split", phrase: "splits here" }],
    }],
    shots: [
      {
        id: "shot-01",
        segment_id: "segment-01",
        intent: "Show one system separating into clear responsibilities.",
        enter: { cue_id: "cue-split" },
        duration_ms: 2000,
        renderer: { kind: "component", entry: "assets/shot-01/index.html", variant: "overview" },
      },
      {
        id: "shot-02",
        segment_id: "segment-01",
        intent: "Reserve a real-world context shot for later sourcing.",
        enter: { cue_id: "cue-split" },
        duration_ms: 1200,
        renderer: { kind: "stock" },
      },
    ],
    assets: [],
  };
  fs.writeFileSync(storyboardPath, `${JSON.stringify(storyboard, null, 2)}\n`, "utf8");
  return { tempRoot, runDir, storyboardPath, storyboard };
}

function cleanup(tempRoot) {
  assert.equal(path.dirname(tempRoot), path.resolve(os.tmpdir()));
  assert.match(path.basename(tempRoot), /^prepare-content-visual-test-/);
  fs.rmSync(tempRoot, { recursive: true, force: true });
}

function writeStoryboard(data) {
  fs.writeFileSync(data.storyboardPath, `${JSON.stringify(data.storyboard, null, 2)}\n`, "utf8");
}

function validVisualOptions() {
  return [
    {
      id: "option-code-native",
      modality: "code_native",
      treatment: "Animate the responsibility handoff with deterministic SVG shapes.",
      why: "The changing ownership is easier to understand as motion than as a still card.",
      source_plan: "Build a local standalone HTML component after storyboard approval.",
      rights_note: "Original code-native artwork; no external media rights required.",
    },
    {
      id: "option-host-only",
      modality: "host_only",
      treatment: "Keep the Human Host on camera and use hand gestures for the contrast.",
      why: "The spoken explanation may already be sufficient for a familiar audience.",
      source_plan: "Use the approved Human Host recording without supplementary media.",
      rights_note: "Creator-owned Host footage; confirm release before publication.",
    },
  ];
}

function validEditorialPlan() {
  return {
    hook_segment_id: "segment-01",
    hook_beats: [
      {
        id: "beat-title",
        cue_id: "cue-split",
        purpose: "title",
        coverage: "shot",
        shot_ids: ["shot-01"],
      },
      {
        id: "beat-promise",
        cue_id: "cue-split",
        purpose: "payoff",
        coverage: "host_only",
        shot_ids: [],
      },
    ],
    title_treatment: {
      mode: "integrated_hook",
      shot_id: "shot-01",
      screen_text: "See the architecture split",
    },
    ending: {
      mode: "visual_cta",
      shot_id: "shot-02",
      screen_text: "Follow Dev Xịn",
    },
  };
}

function bootAnimationStarterRuntime() {
  const html = fs.readFileSync(starter, "utf8");
  const inlineScripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
  assert.equal(inlineScripts.length, 1, "animation starter must ship one inline runtime script");

  const createNode = () => ({
    style: {},
    textContent: "",
    attributes: new Map(),
    setAttribute(name, value) {
      this.attributes.set(name, String(value));
    },
  });
  const selectedNodes = new Map([
    ["#mono", createNode()],
    ["#services", createNode()],
    ["#connections", createNode()],
    ["#packets", createNode()],
    ["#captionTitle", createNode()],
    ["#captionCopy", createNode()],
    ["#progressBar", createNode()],
  ]);
  const serviceNodes = [createNode(), createNode(), createNode()];
  const packetNodes = [createNode(), createNode()];
  const documentElement = { dataset: {} };
  const document = {
    documentElement,
    querySelector(selector) {
      const node = selectedNodes.get(selector);
      assert.ok(node, `unexpected querySelector in starter runtime: ${selector}`);
      return node;
    },
    querySelectorAll(selector) {
      if (selector === ".service") return serviceNodes;
      if (selector === ".packet") return packetNodes;
      assert.fail(`unexpected querySelectorAll in starter runtime: ${selector}`);
    },
  };

  let nextFrameId = 1;
  const pendingFrames = new Map();
  const requestAnimationFrame = (callback) => {
    const id = nextFrameId;
    nextFrameId += 1;
    pendingFrames.set(id, callback);
    return id;
  };
  const cancelAnimationFrame = (id) => pendingFrames.delete(id);
  const window = {};
  const sandbox = {
    window,
    document,
    performance: { now: () => 0 },
    requestAnimationFrame,
    cancelAnimationFrame,
  };

  vm.runInNewContext(inlineScripts[0][1], sandbox, {
    filename: starter,
    timeout: 1000,
  });

  return {
    api: window.__hyperframe,
    documentElement,
    pendingFrameCount: () => pendingFrames.size,
    runNextFrame(now) {
      const iterator = pendingFrames.entries().next();
      assert.equal(iterator.done, false, "expected one scheduled animation frame");
      const [id, callback] = iterator.value;
      pendingFrames.delete(id);
      callback(now);
    },
  };
}

test("animation starter uses the light editorial fallback", () => {
  const html = fs.readFileSync(starter, "utf8");
  assert.match(html, /:root\s*\{[^}]*color-scheme:\s*light/s);
  assert.match(html, /linear-gradient\(165deg,\s*#ffffff/);
  assert.match(html, /h1\s*\{[^}]*color:\s*#0f172a/s);
});

test("preview scale never upscales and honors both viewport constraints", () => {
  assert.equal(
    calculatePreviewScale(432, 768, 1200, 1200),
    1,
    "a large desktop viewport must keep the recording stage at its real size",
  );
  assert.equal(
    calculatePreviewScale(432, 768, 216, 1000),
    0.5,
    "a narrow viewport must fit by available width",
  );
  assert.equal(
    calculatePreviewScale(432, 768, 1000, 384),
    0.5,
    "a short viewport must fit by available height",
  );
  assert.equal(
    calculatePreviewScale(432, 768, 300, 192),
    0.25,
    "the tighter of width and height must win",
  );
});

test("animation starter exposes the fixed support_top desktop-capture regions", () => {
  const html = fs.readFileSync(starter, "utf8");
  assert.match(
    html,
    /<main\b[^>]*class="frame"[^>]*data-capture-stage="0,0,432,768"[^>]*>/s,
    "the starter must declare the complete 432 x 768 recording stage",
  );
  assert.match(
    html,
    /<section\b[^>]*class="visual-frame"[^>]*data-visual-frame="0,0,432,432"[^>]*>/s,
    "the illustration must live in the upper 432 x 432 region",
  );
  assert.match(
    html,
    /\.visual-frame\s*\{[^}]*width:\s*432px[^}]*height:\s*432px[^}]*overflow:\s*hidden/s,
    "the upper illustration region must clip visual overflow",
  );
  assert.match(
    html,
    /<section\b[^>]*class="host-frame"[^>]*data-host-frame="0,432,432,336"[^>]*>/s,
    "the lower 432 x 336 region must remain an explicit Host/camera slot",
  );
  assert.match(
    html,
    /\.diagram\s*\{[^}]*top:\s*106px[^}]*width:\s*432px[^}]*height:\s*220px/s,
    "the diagram must occupy its own fixed zone below the headline",
  );
  assert.match(html, /<svg\b[^>]*viewBox="0 0 432 220"/s);
  assert.doesNotMatch(
    html,
    /font-size\s*:[^;}]*\b(?:vw|vh|vmin|vmax)\b/i,
    "fixed-stage typography must not grow with the outer browser viewport",
  );
});

test("animation starter autoplay reaches the final frame and holds", () => {
  const html = fs.readFileSync(starter, "utf8");
  assert.doesNotMatch(
    html,
    /\(\s*now\s*-\s*playStarted\s*\)\s*%\s*durationMs/,
    "autoplay must not wrap elapsed time back to the first frame",
  );
  assert.match(
    html,
    /pausedAt\s*=\s*(?:Math\.min\(\s*durationMs\s*,\s*Math\.max\(\s*0\s*,\s*now\s*-\s*playStarted\s*\)\s*\)|clamp\(\s*now\s*-\s*playStarted\s*,\s*0\s*,\s*durationMs\s*\))/,
    "autoplay must clamp elapsed time at durationMs",
  );
  assert.match(
    html,
    /if\s*\(\s*pausedAt\s*<\s*durationMs\s*\)\s*scheduleTick\(\)\s*;\s*else\s+manual\s*=\s*true/,
    "autoplay must schedule frames only before completion and stop at the final frame",
  );
  assert.match(
    html,
    /function\s+seek\([^)]*\)\s*\{[\s\S]*?manualLocked\s*=\s*true\s*;[\s\S]*?cancelScheduledFrame\(\)/,
    "the first manual seek must cancel autoplay and lock the component in manual mode",
  );
  assert.match(
    html,
    /function\s+play\(\)\s*\{\s*if\s*\(\s*manualLocked\s*\|\|\s*pausedAt\s*>=\s*durationMs\s*\)\s*return/,
    "play must not silently restart after a manual seek or completed autoplay",
  );
});

test("animation starter one-shot contract holds at runtime", () => {
  const autoplay = bootAnimationStarterRuntime();
  assert.equal(autoplay.pendingFrameCount(), 1);
  autoplay.runNextFrame(autoplay.api.durationMs + 250);
  assert.equal(autoplay.documentElement.dataset.hyperframeTime, String(autoplay.api.durationMs));
  assert.equal(autoplay.documentElement.dataset.hyperframeComplete, "true");
  assert.equal(autoplay.pendingFrameCount(), 0, "completed autoplay must leave no RAF pending");

  autoplay.api.play();
  assert.equal(autoplay.pendingFrameCount(), 0, "play() must not restart a completed animation");
  assert.equal(autoplay.documentElement.dataset.hyperframeTime, String(autoplay.api.durationMs));

  const manual = bootAnimationStarterRuntime();
  assert.equal(manual.pendingFrameCount(), 1);
  manual.api.seek(1500);
  assert.equal(manual.pendingFrameCount(), 0, "seek() must cancel the scheduled autoplay frame");
  assert.equal(manual.documentElement.dataset.hyperframeTime, "1500");
  assert.equal(manual.documentElement.dataset.hyperframeComplete, "false");
  manual.api.play();
  assert.equal(manual.pendingFrameCount(), 0, "play() must not escape manual seek mode");
  assert.equal(manual.documentElement.dataset.hyperframeTime, "1500");
});

test("karaoke excerpts cover globally ordered segment text exactly", () => {
  const storyboard = {
    segments: [
      {
        id: "segment-a",
        text: "Mở máy, rồi chạy thử. Kết quả ổn định.",
        cues: [
          { id: "cue-run", phrase: "chạy thử" },
          { id: "cue-result", phrase: "Kết quả" },
        ],
      },
      {
        id: "segment-b",
        text: "Cuối cùng: bấm theo dõi.",
        cues: [{ id: "cue-final", phrase: "Cuối cùng:" }],
      },
    ],
    shots: [
      { id: "shot-a", enter: { cue_id: "cue-run" } },
      { id: "shot-b", enter: { cue_id: "cue-result" } },
      { id: "shot-c", enter: { cue_id: "cue-final" } },
    ],
  };

  const result = deriveKaraokeSceneExcerpts(storyboard);
  assert.equal(result.script_text, "Mở máy, rồi chạy thử. Kết quả ổn định. Cuối cùng: bấm theo dõi.");
  assert.equal(result.scenes.map((scene) => scene.text).join(""), result.script_text);
  assert.deepEqual(result.scenes[0].shot_ids, [], "spoken text before the first cue must become a Host-only scene");
  assert.equal(result.scenes[0].text, "Mở máy, rồi ");
  assert.equal(result.scenes[1].text, "chạy thử. ");
  assert.equal(result.scenes[2].text, "Kết quả ổn định. ");
  assert.equal(result.scenes[3].text, "Cuối cùng: bấm theo dõi.");
});

test("duplicate enter anchors form one scene without overlapping or repeated spoken text", () => {
  const result = deriveKaraokeSceneExcerpts({
    segments: [{
      id: "segment",
      text: "Mở đầu rồi bắt đầu phần chính.",
      cues: [{ id: "cue-main", phrase: "bắt đầu phần chính" }],
    }],
    shots: [
      { id: "shot-a", enter: { cue_id: "cue-main" } },
      { id: "shot-b", enter: { cue_id: "cue-main" } },
    ],
  });
  assert.equal(result.scenes.map((scene) => scene.text).join(""), result.script_text);
  assert.equal(result.scenes[0].text, "Mở đầu rồi ");
  assert.equal(result.scenes[1].text, "bắt đầu phần chính.");
  assert.deepEqual(result.scenes[1].shot_ids, ["shot-a", "shot-b"]);
  assert.ok(result.scenes.every((scene) => scene.text.length > 0));
});

test("karaoke timing applies WPM plus punctuation and scene-end pauses", () => {
  const config = normalizeKaraokeCaptionConfig({
    enabled: true,
    reading_wpm: 120,
    pause_ms: { comma: 250, clause: 400, sentence: 650, scene_end: 900 },
  });
  const timeline = buildKaraokeTimeline("Một, hai; ba.", config);

  assert.deepEqual(timeline.words.map((word) => word.start_ms), [0, 750, 1650]);
  assert.deepEqual(timeline.words.map((word) => word.punctuation_pause_ms), [250, 400, 650]);
  assert.equal(timeline.spoken_complete_ms, 2800);
  assert.equal(timeline.duration_ms, 3700);

  const rounded = buildKaraokeTimeline("một hai", normalizeKaraokeCaptionConfig({
    enabled: true,
    reading_wpm: 137,
    pause_ms: { comma: 0, clause: 0, sentence: 0, scene_end: 0 },
  }));
  assert.equal(rounded.words[1].start_ms, Math.round(60_000 / 137));
});

test("karaoke config defaults are explicit and malformed contracts fail", () => {
  assert.deepEqual(normalizeKaraokeCaptionConfig({ enabled: true }), {
    enabled: true,
    placement: "capture_stage_bottom",
    bottom_margin_px: 100,
    max_lines: 2,
    reading_wpm: 150,
    pause_ms: { comma: 250, clause: 400, sentence: 650, scene_end: 900 },
    scene_advance: "manual",
    end_indicator: "NEXT →",
  });
  assert.equal(normalizeKaraokeCaptionConfig(undefined), null);
  assert.throws(
    () => normalizeKaraokeCaptionConfig({ enabled: true, max_lines: 3 }),
    /max_lines must be 1 or 2/,
  );
  assert.throws(
    () => normalizeKaraokeCaptionConfig({ enabled: true, scene_advance: "automatic" }),
    /scene_advance must be "manual"/,
  );
  assert.throws(
    () => normalizeKaraokeCaptionConfig({ enabled: true, pause_ms: { typo: 1 } }),
    /pause_ms has unknown field: typo/,
  );
  assert.throws(
    () => normalizeKaraokeCaptionConfig({ enabled: true, reading_wpm: 137.5 }),
    /reading_wpm must be an integer from 60 to 1000/,
  );
  assert.throws(
    () => normalizeKaraokeCaptionConfig({ enabled: true, end_indicator: "]\n<script>" }),
    /end_indicator must be a single-line string of 1 to 32 safe characters/,
  );
});

test("manual scene navigation accepts only sentence-start entries and keeps intra-sentence changes inside components", () => {
  assert.deepEqual(normalizeSceneNavigationConfig({}), {
    mode: "manual",
    boundary_policy: "sentence_start",
    intra_sentence_changes: "component_state",
  });
  assert.equal(isSentenceStart("Câu một. Câu hai.", 0), true);
  assert.equal(isSentenceStart("Câu một. Câu hai.", "Câu một. ".length), true);
  assert.equal(isSentenceStart("Câu một, rồi tiếp tục.", "Câu một, ".length), false);

  const data = fixture();
  try {
    data.storyboard.project.scene_navigation = {};
    writeStoryboard(data);
    assert.throws(
      () => validateStoryboard(data.storyboardPath, data.runDir),
      /manual Next boundaries must start a complete sentence/,
    );

    data.storyboard.segments[0].cues[0].phrase = "The architecture";
    writeStoryboard(data);
    const model = validateStoryboard(data.storyboardPath, data.runDir);
    assert.equal(model.sceneNavigation.boundary_policy, "sentence_start");
    assert.equal(model.navigationScenes.length, 1);
    assert.equal(model.karaokeScenes, null, "scene projection must not depend on karaoke visibility");

    data.storyboard.shots[0].enter.offset_ms = 100;
    writeStoryboard(data);
    assert.throws(
      () => validateStoryboard(data.storyboardPath, data.runDir),
      /enter\.offset_ms must be 0 when project\.scene_navigation is manual/,
    );
  } finally {
    cleanup(data.tempRoot);
  }
});

test("CLI infers the run directory and produces an honest preview", () => {
  const data = fixture();
  try {
    const validate = spawnSync(process.execPath, [renderer, "validate", "--storyboard", data.storyboardPath], {
      encoding: "utf8",
      windowsHide: true,
    });
    assert.equal(validate.status, 0, validate.stderr);
    const validation = JSON.parse(validate.stdout);
    assert.equal(validation.run_dir, data.runDir);
    assert.equal(validation.project.theme, "light-editorial");
    assert.equal(validation.project.ratio, "9:16");
    assert.equal(validation.project.width, 432);
    assert.equal(validation.project.height, 768);
    assert.deepEqual(validation.layout_geometries.support_top.canvas, {
      x: 0, y: 0, width: 432, height: 768,
    });
    assert.deepEqual(validation.layout_geometries.support_top.visual, {
      x: 0, y: 0, width: 432, height: 432,
    });
    assert.deepEqual(validation.layout_geometries.support_top.host, {
      x: 0, y: 432, width: 432, height: 336,
    });

    const preview = spawnSync(process.execPath, [renderer, "preview", "--storyboard", data.storyboardPath], {
      encoding: "utf8",
      windowsHide: true,
    });
    assert.equal(preview.status, 0, preview.stderr);
    const previewPath = path.join(data.runDir, "creator-pack", "hyperframes_preview.html");
    const html = fs.readFileSync(previewPath, "utf8");
    assert.match(html, /UNRENDERED · stock/);
    assert.match(html, /assets\/shot-01\/index\.html/);
    assert.match(html, /data-prev/);
    assert.match(html, /data-next/);
    assert.match(html, /ArrowRight/);
    assert.match(html, /light-editorial/);
    assert.match(html, /desktop capture 432 x 768/);
    assert.match(html, /visual 432 x 432 at \(0, 0\)/);
    assert.match(html, /blank host\/camera frame 432 x 336 at \(0, 432\)/);
    assert.match(html, /data-capture-stage="0,0,432,768"/);
    assert.match(html, /data-visual-frame="0,0,432,432"/);
    assert.match(html, /data-host-frame="0,432,432,336"/);
    assert.match(
      html,
      /srcdoc="[^"]*Content-Security-Policy[^"]*"[^>]*sandbox="allow-scripts"/,
      "every preview component must use the runtime-isolated srcdoc sandbox",
    );
    assert.match(html, /__hyperframeContext/);
    assert.match(html, /&quot;variant&quot;:&quot;overview&quot;/);
    assert.doesNotMatch(html, /sandbox="allow-scripts allow-same-origin"/);
    assert.match(
      html,
      /\.capture-viewport\{[^}]*height:100vh[^}]*place-items:center[^}]*overflow:hidden/s,
      "the first viewport must be reserved for the centered capture stage",
    );
    assert.match(html, /data-capture-viewport/);
    assert.match(html, /data-review-panel/);
    assert.match(html, /data-shot-detail-index="0"/);
    assert.match(html, /data-reload="0"/);
    assert.ok(
      html.indexOf('data-capture-viewport') < html.indexOf('data-review-panel'),
      "the capture-only fold must precede every piece of review chrome",
    );
    assert.match(html, /const availableWidth = captureViewport\?\.clientWidth \|\| window\.innerWidth/);
    assert.match(html, /const availableHeight = captureViewport\?\.clientHeight \|\| window\.innerHeight/);
    assert.match(html, /stage\.style\.width = scaledWidth \+ 'px'/);
    assert.match(html, /stage\.style\.height = scaledHeight \+ 'px'/);
    assert.match(html, /stage\.dataset\.previewScale = String\(scale\)/);
    assert.doesNotMatch(html, /trailingHeight/);
    assert.match(html, /window\.addEventListener\('resize', fitFrames\)/);
    assert.doesNotMatch(html, /data-karaoke-surface/, "disabled legacy previews must not gain a caption overlay");
  } finally {
    cleanup(data.tempRoot);
  }
});

test("enabled karaoke preview is escaped, positioned, synchronized, and manual", () => {
  const data = fixture();
  try {
    data.storyboard.project.karaoke_caption = {
      enabled: true,
      placement: "capture_stage_bottom",
      bottom_margin_px: 100,
      max_lines: 2,
      reading_wpm: 150,
      pause_ms: { comma: 250, clause: 400, sentence: 650, scene_end: 900 },
      scene_advance: "manual",
      end_indicator: "NEXT →",
    };
    data.storyboard.segments[0].text = "Đọc <script>alert(1)</script> rồi the architecture splits here and the result becomes visible.";
    writeStoryboard(data);

    const preview = spawnSync(process.execPath, [
      renderer,
      "preview",
      "--storyboard",
      data.storyboardPath,
      "--karaoke-overlay",
      "visible",
    ], {
      encoding: "utf8",
      windowsHide: true,
    });
    assert.equal(preview.status, 0, preview.stderr || preview.stdout);
    const html = fs.readFileSync(path.join(data.runDir, "creator-pack", "hyperframes_preview.html"), "utf8");
    assert.match(html, /data-karaoke-surface/);
    assert.match(html, /data-karaoke-caption style="bottom:100px;--karaoke-max-lines:2"/);
    assert.doesNotMatch(html, /karaokeEndIndicator/);
    assert.doesNotMatch(html, /data-karaoke-status/);
    assert.match(html, /dataset\.karaokeVisible/);
    assert.match(html, /classList\.toggle\('is-current', wordIndex === activeWord\)/);
    assert.doesNotMatch(html, /classList\.toggle\('is-spoken'/);
    assert.match(html, /connect-src &#39;none&#39;/);
    assert.match(html, /hyperframe-preview-bridge/);
    assert.match(html, /Timed out after 10000ms waiting for sandboxed __hyperframe\.ready bridge/);
    assert.match(html, /sandbox="allow-scripts"/);
    assert.doesNotMatch(html, /sandbox="allow-scripts allow-same-origin"/);
    assert.doesNotMatch(html, /load-event-fallback/);
    assert.match(html, /data-shot-id="host-only-prefix"/);
    assert.match(html, /data-shot-ids="shot-01 shot-02"/);
    assert.match(html, /restartKaraoke\(active, reloadFrameAndWait/);
    assert.match(html, /event\.code === 'Space'/);
    assert.match(html, /event\.key\.toLowerCase\(\) === 'r'/);
    assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
    assert.match(html, /\\u003cscript\\u003ealert\(1\)\\u003c\/script\\u003e/);

    const hiddenPreview = spawnSync(process.execPath, [
      renderer,
      "preview",
      "--storyboard",
      data.storyboardPath,
    ], {
      encoding: "utf8",
      windowsHide: true,
    });
    assert.equal(hiddenPreview.status, 0, hiddenPreview.stderr || hiddenPreview.stdout);
    assert.equal(JSON.parse(hiddenPreview.stdout).karaoke_overlay, "hidden", "karaoke overlay must default to hidden");
    const hiddenHtml = fs.readFileSync(path.join(data.runDir, "creator-pack", "hyperframes_preview.html"), "utf8");
    assert.doesNotMatch(hiddenHtml, /data-karaoke-surface/);
    assert.doesNotMatch(hiddenHtml, /const karaokeScenes/);
    assert.match(hiddenHtml, /data-karaoke-scene-id=/, "scene navigation must remain aligned with the teleprompter");
    assert.match(hiddenHtml, /karaoke hidden/);
  } finally {
    cleanup(data.tempRoot);
  }
});

test("CLI rejects unknown options", () => {
  const data = fixture();
  try {
    const result = spawnSync(
      process.execPath,
      [renderer, "validate", "--storyboard", data.storyboardPath, "--typo-flag", "yes"],
      { encoding: "utf8", windowsHide: true },
    );
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Unknown option/);
  } finally {
    cleanup(data.tempRoot);
  }
});

test("ambiguous cue phrases fail validation", () => {
  const data = fixture();
  try {
    data.storyboard.segments[0].text = "repeat this, then repeat this once more";
    data.storyboard.segments[0].cues[0].phrase = "repeat this";
    fs.writeFileSync(data.storyboardPath, `${JSON.stringify(data.storyboard, null, 2)}\n`, "utf8");
    assert.throws(
      () => validateStoryboard(data.storyboardPath, data.runDir),
      /occurs 2 times/,
    );
  } finally {
    cleanup(data.tempRoot);
  }
});

test("additive editorial plan validates hook coverage, title treatment, and final CTA", () => {
  const data = fixture();
  try {
    data.storyboard.editorial_plan = validEditorialPlan();
    writeStoryboard(data);

    const model = validateStoryboard(data.storyboardPath, data.runDir);

    assert.equal(model.storyboard.editorial_plan.ending.shot_id, "shot-02");

    data.storyboard.editorial_plan.ending = {
      mode: "spoken_cta",
      shot_id: "shot-02",
      screen_text: "Follow Dev Xịn",
      spoken_phrase: "Follow Dev Xịn",
    };
    writeStoryboard(data);
    assert.equal(
      validateStoryboard(data.storyboardPath, data.runDir).storyboard.editorial_plan.ending.spoken_phrase,
      "Follow Dev Xịn",
    );
  } finally {
    cleanup(data.tempRoot);
  }
});

test("malformed editorial plans fail with focused errors", () => {
  const cases = [
    {
      mutate: (plan) => { plan.hook_segment_id = "segment-missing"; },
      expected: /hook_segment_id references an unknown segment/,
    },
    {
      mutate: (plan) => { plan.hook_beats.push({ ...plan.hook_beats[0] }); },
      expected: /Duplicate editorial hook beat id/,
    },
    {
      mutate: (plan) => { plan.hook_beats[0].cue_id = "cue-missing"; },
      expected: /cue_id references an unknown cue/,
    },
    {
      mutate: (plan) => { plan.hook_beats[0].purpose = "summary"; },
      expected: /purpose must be one of/,
    },
    {
      mutate: (plan) => { plan.hook_beats[1].shot_ids = ["shot-01"]; },
      expected: /shot_ids must be omitted or empty for host_only/,
    },
    {
      mutate: (plan) => { plan.title_treatment.shot_id = "shot-missing"; },
      expected: /title_treatment\.shot_id references an unknown shot/,
    },
    {
      mutate: (plan) => { plan.ending.shot_id = "shot-01"; },
      expected: /ending\.shot_id must reference the final storyboard shot/,
    },
    {
      mutate: (plan) => { plan.ending = { mode: "spoken_cta", shot_id: "shot-02", screen_text: "Follow" }; },
      expected: /ending\.spoken_phrase is required for spoken_cta/,
    },
    {
      mutate: (plan) => { plan.ending.spoken_phrase = "Follow Dev Xịn"; },
      expected: /ending\.spoken_phrase must be omitted for visual_cta/,
    },
    {
      mutate: (plan) => { plan.ending = { mode: "host_only", spoken_phrase: "Follow" }; },
      expected: /ending\.spoken_phrase must be omitted for host_only/,
    },
    {
      mutate: (plan) => { plan.ending = { mode: "none", spoken_phrase: "Follow" }; },
      expected: /ending\.spoken_phrase must be omitted for none/,
    },
  ];

  for (const { mutate, expected } of cases) {
    const data = fixture();
    try {
      data.storyboard.editorial_plan = validEditorialPlan();
      mutate(data.storyboard.editorial_plan);
      writeStoryboard(data);
      assert.throws(() => validateStoryboard(data.storyboardPath, data.runDir), expected);
    } finally {
      cleanup(data.tempRoot);
    }
  }
});

test("optional composition fields and visual options validate with explicit precedence", () => {
  const data = fixture();
  try {
    data.storyboard.project.default_host_layout = "host_only";
    data.storyboard.segments[0].host_layout = "support_right";
    data.storyboard.shots[0].lane = "explainer_full";
    data.storyboard.shots[0].visual_options = validVisualOptions();
    data.storyboard.shots[0].selected_option_id = "option-code-native";

    data.storyboard.segments.push({
      id: "segment-02",
      text: "The second composition begins at this moment.",
      cues: [{ id: "cue-second", phrase: "begins at this moment" }],
    });
    data.storyboard.shots.push({
      id: "shot-03",
      segment_id: "segment-02",
      intent: "Exercise the project-level composition default.",
      enter: { cue_id: "cue-second" },
      duration_ms: 1000,
      renderer: { kind: "image" },
    });
    writeStoryboard(data);

    let model = validateStoryboard(data.storyboardPath, data.runDir);
    assert.equal(model.shots[0].composition, "explainer_full");
    assert.equal(model.shots[1].composition, "support_right");
    assert.equal(model.shots[2].composition, "host_only");

    const preview = spawnSync(process.execPath, [renderer, "preview", "--storyboard", data.storyboardPath], {
      encoding: "utf8",
      windowsHide: true,
    });
    assert.equal(preview.status, 0, preview.stderr);
    const html = fs.readFileSync(path.join(data.runDir, "creator-pack", "hyperframes_preview.html"), "utf8");
    assert.match(html, /composition: explainer_full/);
    assert.match(html, /composition: support_right/);
    assert.match(html, /composition: host_only/);

    delete data.storyboard.project.default_host_layout;
    writeStoryboard(data);
    model = validateStoryboard(data.storyboardPath, data.runDir);
    assert.equal(model.shots[2].composition, "support_top");
  } finally {
    cleanup(data.tempRoot);
  }
});

test("invalid project, segment, and shot composition enums fail validation", () => {
  const cases = [
    {
      mutate: (storyboard) => { storyboard.project.default_host_layout = "side_by_side"; },
      expected: /project\.default_host_layout must be one of/,
    },
    {
      mutate: (storyboard) => { storyboard.segments[0].host_layout = "picture_in_picture"; },
      expected: /Segment segment-01\.host_layout must be one of/,
    },
    {
      mutate: (storyboard) => { storyboard.shots[0].lane = "host_only"; },
      expected: /Shot shot-01\.lane must be one of/,
    },
  ];

  for (const { mutate, expected } of cases) {
    const data = fixture();
    try {
      mutate(data.storyboard);
      writeStoryboard(data);
      assert.throws(() => validateStoryboard(data.storyboardPath, data.runDir), expected);
    } finally {
      cleanup(data.tempRoot);
    }
  }
});

test("implicit support_top uses the fixed 9:16 canvas and exposes its regions", () => {
  const data = fixture();
  try {
    const model = validateStoryboard(data.storyboardPath, data.runDir);
    assert.deepEqual(model.project, {
      ratio: "9:16",
      width: 432,
      height: 768,
      fps: 30,
      theme: "light-editorial",
    });
    assert.equal(model.shots[0].composition, "support_top");
    assert.deepEqual(model.shots[0].compositionGeometry, {
      ratio: "9:16",
      canvas: { x: 0, y: 0, width: 432, height: 768 },
      visual: { x: 0, y: 0, width: 432, height: 432 },
      host: { x: 0, y: 432, width: 432, height: 336 },
    });
    assert.deepEqual(model.layoutGeometries.support_top, model.shots[0].compositionGeometry);
  } finally {
    cleanup(data.tempRoot);
  }
});

test("implicit support_top rejects a 16:9 project", () => {
  const data = fixture();
  try {
    data.storyboard.project.ratio = "16:9";
    writeStoryboard(data);
    assert.throws(
      () => validateStoryboard(data.storyboardPath, data.runDir),
      /Shot shot-01 uses support_top, which requires project\.ratio "9:16"/,
    );
  } finally {
    cleanup(data.tempRoot);
  }
});

test("support_top rejects provided dimensions other than the 432 x 768 capture stage", () => {
  const data = fixture();
  try {
    Object.assign(data.storyboard.project, { width: 434, height: 768 });
    writeStoryboard(data);
    assert.throws(
      () => validateStoryboard(data.storyboardPath, data.runDir),
      /Shot shot-01 uses support_top, which requires explicit project\.width 432 and project\.height 768 for the desktop-capture canvas/,
    );
  } finally {
    cleanup(data.tempRoot);
  }
});

test("support_top requires explicit desktop-capture dimensions", () => {
  const data = fixture();
  try {
    delete data.storyboard.project.width;
    delete data.storyboard.project.height;
    writeStoryboard(data);
    assert.throws(
      () => validateStoryboard(data.storyboardPath, data.runDir),
      /Shot shot-01 uses support_top, which requires explicit project\.width 432 and project\.height 768/,
    );
  } finally {
    cleanup(data.tempRoot);
  }
});

test("explicit project or segment support_top requires vertical geometry even when shots override it", () => {
  for (const configure of [
    (storyboard) => {
      storyboard.project.default_host_layout = "support_top";
      storyboard.shots.forEach((shot) => { shot.lane = "support_right"; });
    },
    (storyboard) => {
      storyboard.project.default_host_layout = "host_only";
      storyboard.segments[0].host_layout = "support_top";
      storyboard.shots.forEach((shot) => { shot.lane = "support_right"; });
    },
  ]) {
    const data = fixture();
    try {
      data.storyboard.project.ratio = "16:9";
      configure(data.storyboard);
      writeStoryboard(data);
      assert.throws(
        () => validateStoryboard(data.storyboardPath, data.runDir),
        /uses support_top, which requires project\.ratio "9:16"/,
      );
    } finally {
      cleanup(data.tempRoot);
    }
  }
});

test("visual option contracts reject empty, duplicate, incomplete, or unselected choices", () => {
  const cases = [
    {
      mutate: (shot) => {
        shot.visual_options = [];
        shot.selected_option_id = "option-code-native";
      },
      expected: /visual_options must be a non-empty array/,
    },
    {
      mutate: (shot) => {
        shot.visual_options = validVisualOptions();
        shot.visual_options[1].id = shot.visual_options[0].id;
        shot.selected_option_id = "option-code-native";
      },
      expected: /duplicate visual option id/,
    },
    {
      mutate: (shot) => {
        shot.visual_options = validVisualOptions();
        shot.visual_options[0].modality = "ai_generated_video";
        shot.selected_option_id = "option-code-native";
      },
      expected: /modality must be one of/,
    },
    {
      mutate: (shot) => {
        shot.visual_options = validVisualOptions();
        shot.visual_options[0].rights_note = "  ";
        shot.selected_option_id = "option-code-native";
      },
      expected: /rights_note must be a non-empty string/,
    },
    {
      mutate: (shot) => {
        shot.visual_options = validVisualOptions();
        shot.selected_option_id = "option-missing";
      },
      expected: /selected_option_id must reference a visual_options id/,
    },
    {
      mutate: (shot) => {
        shot.visual_options = validVisualOptions();
        shot.selected_option_id = "option-host-only";
      },
      expected: /cannot select a host_only visual option; omit the shot instead/,
    },
    {
      mutate: (shot) => {
        shot.visual_options = validVisualOptions();
      },
      expected: /selected_option_id must reference a visual_options id/,
    },
    {
      mutate: (shot) => {
        shot.selected_option_id = "option-code-native";
      },
      expected: /selected_option_id requires visual_options/,
    },
  ];

  for (const { mutate, expected } of cases) {
    const data = fixture();
    try {
      mutate(data.storyboard.shots[0]);
      writeStoryboard(data);
      assert.throws(() => validateStoryboard(data.storyboardPath, data.runDir), expected);
    } finally {
      cleanup(data.tempRoot);
    }
  }
});
