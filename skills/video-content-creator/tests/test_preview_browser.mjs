import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const skillDir = path.resolve(testDir, "..");
const repoRoot = path.resolve(skillDir, "..", "..", "..");
const renderer = path.join(skillDir, "scripts", "render_web_asset.mjs");

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const candidates = [
    process.env.PREPARE_CONTENT_PLAYWRIGHT_MODULE,
    path.join(repoRoot, "tools", "ai-video-workflow-cli", "node_modules", "playwright"),
    "playwright",
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      const loaded = require(candidate);
      if (loaded?.chromium) return loaded;
    } catch {
      // Try the next explicit or conventional location.
    }
  }
  return null;
}

function writeFixture({ karaoke = false, grouped = false, readyDelayMs = 0, probeUrl = "" } = {}) {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "prepare-content-preview-browser-"));
  const runDir = path.join(tempRoot, "run");
  const storyboardDir = path.join(runDir, "storyboard");
  const componentDir = path.join(storyboardDir, "components", "shot-01");
  const assetDir = path.join(storyboardDir, "assets");
  fs.mkdirSync(componentDir, { recursive: true });
  fs.mkdirSync(assetDir, { recursive: true });
  fs.writeFileSync(
    path.join(assetDir, "pixel.png"),
    Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64"),
  );
  const networkProbe = probeUrl
    ? `globalThis["fet"+"ch"]("ht"+"tp://${probeUrl.slice("http://".length)}").catch(()=>{});`
    : "";
  const readyValue = readyDelayMs > 0
    ? `() => new Promise((resolve) => setTimeout(() => resolve(true), ${readyDelayMs}))`
    : "true";
  fs.writeFileSync(path.join(componentDir, "index.html"), `<!doctype html>
<html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{width:100%;height:100%;margin:0;overflow:hidden;background:#030712}
main{width:432px;height:768px;background:#030712;color:white;display:grid;place-items:center}
img{width:64px;height:64px;image-rendering:pixelated}
</style></head><body><main><img src="../../assets/pixel.png" alt="local fixture"></main><script>
${networkProbe}
window.__hyperframe={durationMs:1000,ready:${readyValue},seek(ms){document.documentElement.dataset.time=String(Math.max(0,Math.min(1000,ms)))}};
</script></body></html>`, "utf8");

  const storyboardPath = path.join(storyboardDir, "storyboard.json");
  const project = {
    ratio: "9:16",
    width: 432,
    height: 768,
    fps: 30,
    theme: "light-editorial",
    default_host_layout: "support_top",
  };
  if (karaoke) {
    project.karaoke_caption = {
      enabled: true,
      placement: "capture_stage_bottom",
      bottom_margin_px: 100,
      max_lines: 2,
      reading_wpm: 600,
      pause_ms: { comma: 10, clause: 20, sentence: 30, scene_end: 40 },
      scene_advance: "manual",
      end_indicator: "NEXT →",
    };
  }
  const shot = (id) => ({
    id,
    segment_id: "segment-01",
    lane: "support_top",
    intent: id === "shot-02"
      ? "Long review metadata must stay below the capture fold and must never reduce the stage height. ".repeat(24)
      : `Preview ${id} at the fixed capture size.`,
    enter: { cue_id: grouped || id === "shot-02" ? "cue-02" : "cue-01", offset_ms: 0 },
    duration_ms: 1000,
    renderer: { kind: "component", entry: "storyboard/components/shot-01/index.html" },
  });
  fs.writeFileSync(storyboardPath, `${JSON.stringify({
    schema_version: "1.0",
    project,
    segments: [{
      id: "segment-01",
      text: "The capture stage now carries a deliberately longer caption phrase across several readable groups before it starts here again.",
      host_layout: "support_top",
      cues: [
        { id: "cue-01", phrase: "The capture stage" },
        { id: "cue-02", phrase: "starts here" },
      ],
    }],
    shots: [shot("shot-01"), shot("shot-02")],
    assets: [],
  }, null, 2)}\n`, "utf8");

  const previewArgs = [renderer, "preview", "--storyboard", storyboardPath];
  if (karaoke) previewArgs.push("--karaoke-overlay", "visible");
  const preview = spawnSync(process.execPath, previewArgs, {
    encoding: "utf8",
    windowsHide: true,
  });
  assert.equal(preview.status, 0, preview.stderr || preview.stdout);
  return {
    tempRoot,
    previewPath: path.join(runDir, "creator-pack", "hyperframes_preview.html"),
  };
}

function cleanup(tempRoot) {
  assert.equal(path.dirname(tempRoot), path.resolve(os.tmpdir()));
  assert.match(path.basename(tempRoot), /^prepare-content-preview-browser-/);
  fs.rmSync(tempRoot, { recursive: true, force: true });
}

async function assertCaptureFirstFold(page, expectedIndex) {
  await page.waitForFunction((index) => {
    const active = document.querySelector('.shot.is-active');
    return active?.dataset.shotIndex === String(index)
      && active.querySelector('[data-stage]')?.dataset.previewScale;
  }, expectedIndex);

  const metrics = await page.evaluate(() => {
    const rect = (selector) => {
      const value = document.querySelector(selector)?.getBoundingClientRect();
      return value && {
        top: value.top,
        right: value.right,
        bottom: value.bottom,
        left: value.left,
        width: value.width,
        height: value.height,
      };
    };
    const stage = document.querySelector('.shot.is-active [data-stage]');
    return {
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      capture: rect('[data-capture-viewport]'),
      stage: rect('.shot.is-active [data-stage]'),
      review: rect('[data-review-panel]'),
      hero: rect('.hero'),
      detail: rect('.shot-detail.is-active'),
      controls: rect('.controls'),
      dots: rect('.dots'),
      scale: Number(stage?.dataset.previewScale),
    };
  });

  assert.equal(metrics.scale, 1);
  assert.ok(Math.abs(metrics.stage.width - 432) < 0.5, JSON.stringify(metrics));
  assert.ok(Math.abs(metrics.stage.height - 768) < 0.5, JSON.stringify(metrics));
  assert.ok(metrics.stage.top >= -0.5, JSON.stringify(metrics));
  assert.ok(metrics.stage.left >= -0.5, JSON.stringify(metrics));
  assert.ok(metrics.stage.right <= metrics.innerWidth + 0.5, JSON.stringify(metrics));
  assert.ok(metrics.stage.bottom <= metrics.innerHeight + 0.5, JSON.stringify(metrics));
  assert.ok(Math.abs(metrics.capture.height - metrics.innerHeight) < 0.5, JSON.stringify(metrics));
  for (const key of ["review", "hero", "detail", "controls", "dots"]) {
    assert.ok(metrics[key].top >= metrics.innerHeight - 0.5, `${key} leaked into the capture fold: ${JSON.stringify(metrics)}`);
  }

  const frameHandle = await page.locator('.shot.is-active iframe').elementHandle();
  const frame = await frameHandle.contentFrame();
  await frame.waitForLoadState("load");
  await frame.waitForFunction(() => {
    const image = document.querySelector("img");
    return image?.complete && image.naturalWidth > 0;
  });
}

const playwright = loadPlaywright();

test("browser preview keeps the real stage in the first fold and review chrome below it", {
  skip: playwright ? false : "Playwright is not installed; set PREPARE_CONTENT_PLAYWRIGHT_MODULE",
}, async () => {
  const fixture = writeFixture();
  const browser = await playwright.chromium.launch({ headless: true });
  try {
    for (const viewport of [
      { width: 1366, height: 768 },
      { width: 1536, height: 864 },
      { width: 1920, height: 1080 },
    ]) {
      const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
      const page = await context.newPage();
      const runtimeErrors = [];
      page.on("pageerror", (error) => runtimeErrors.push(error.message));
      page.on("console", (message) => {
        if (message.type() === "error") runtimeErrors.push(message.text());
      });
      await page.goto(pathToFileURL(fixture.previewPath).href, { waitUntil: "load" });
      await assertCaptureFirstFold(page, 0);
      await page.keyboard.press("ArrowRight");
      await assertCaptureFirstFold(page, 1);
      assert.deepEqual(runtimeErrors, []);
      await context.close();
    }
  } finally {
    await browser.close();
    cleanup(fixture.tempRoot);
  }
});

test("karaoke pages flow, highlight one word, disappear, and advance scenes only manually", {
  skip: playwright ? false : "Playwright is not installed; set PREPARE_CONTENT_PLAYWRIGHT_MODULE",
}, async () => {
  const fixture = writeFixture({ karaoke: true });
  const browser = await playwright.chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    const runtimeErrors = [];
    page.on("pageerror", (error) => runtimeErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") runtimeErrors.push(message.text());
    });
    await page.goto(pathToFileURL(fixture.previewPath).href, { waitUntil: "load" });
    await assertCaptureFirstFold(page, 0);
    await page.waitForTimeout(200);
    assert.deepEqual(runtimeErrors, [], "karaoke preview must boot without script errors");
    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokeTime);
    assert.equal(
      await page.locator('.shot.is-active [data-karaoke-surface]').getAttribute('data-karaoke-ready-mode'),
      "bridge-ready",
      "sandboxed srcdoc must report __hyperframe.ready through postMessage",
    );

    const placement = await page.evaluate(() => {
      const stage = document.querySelector('.shot.is-active [data-stage]').getBoundingClientRect();
      const caption = document.querySelector('.shot.is-active [data-karaoke-caption]').getBoundingClientRect();
      return {
        stageBottom: stage.bottom,
        captionBottom: caption.bottom,
        captionLines: getComputedStyle(document.querySelector('.shot.is-active [data-karaoke-caption]')).getPropertyValue('--karaoke-max-lines'),
      };
    });
    assert.ok(Math.abs((placement.stageBottom - placement.captionBottom) - 100) < 0.5, JSON.stringify(placement));
    assert.equal(placement.captionLines.trim(), "2");

    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokeVisible === "true");
    const firstPage = await page.evaluate(() => {
      const capture = document.querySelector('[data-capture-viewport]');
      const layer = document.querySelector('.shot.is-active [data-karaoke-surface]');
      const words = layer?.querySelector('[data-karaoke-words]');
      return {
        page: layer?.dataset.karaokePage,
        activeWord: layer?.dataset.karaokeActiveWord,
        activeCount: words?.querySelectorAll('.karaoke-word.is-current').length,
        text: words?.textContent,
        fits: Boolean(words && words.scrollHeight <= words.clientHeight + 0.5),
        hasCapturePrompt: /NEXT|HẾT/u.test(capture?.textContent || ''),
        hasStatusNode: Boolean(layer?.querySelector('[data-karaoke-status]')),
      };
    });
    assert.equal(firstPage.activeCount, 1, JSON.stringify(firstPage));
    assert.equal(firstPage.fits, true, JSON.stringify(firstPage));
    assert.equal(firstPage.hasCapturePrompt, false, JSON.stringify(firstPage));
    assert.equal(firstPage.hasStatusNode, false, JSON.stringify(firstPage));

    await page.waitForFunction((initialPage) => {
      const layer = document.querySelector('.shot.is-active [data-karaoke-surface]');
      return layer?.dataset.karaokeVisible === "true" && layer.dataset.karaokePage !== initialPage;
    }, firstPage.page);
    const nextPage = await page.evaluate(() => {
      const layer = document.querySelector('.shot.is-active [data-karaoke-surface]');
      const words = layer?.querySelector('[data-karaoke-words]');
      return {
        activeCount: words?.querySelectorAll('.karaoke-word.is-current').length,
        text: words?.textContent,
        fits: Boolean(words && words.scrollHeight <= words.clientHeight + 0.5),
      };
    });
    assert.equal(nextPage.activeCount, 1, JSON.stringify(nextPage));
    assert.equal(nextPage.fits, true, JSON.stringify(nextPage));
    assert.notEqual(nextPage.text, firstPage.text, "the prior caption group must be replaced");

    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokeEnded === "true");
    assert.equal(await page.locator('.shot.is-active').getAttribute('data-shot-index'), "0", "caption completion must not auto-advance");
    assert.equal(await page.locator('.shot.is-active [data-karaoke-surface]').getAttribute('data-karaoke-visible'), "false");
    await page.waitForFunction(() => getComputedStyle(
      document.querySelector('.shot.is-active [data-karaoke-caption]'),
    ).visibility === "hidden");

    await page.keyboard.press("ArrowRight");
    await assertCaptureFirstFold(page, 1);
    await page.waitForFunction(() => {
      const layer = document.querySelector('.shot.is-active [data-karaoke-surface]');
      return layer?.dataset.karaokeEnded === "false" && Number(layer.dataset.karaokeTime) >= 0;
    });
    await page.keyboard.press("Space");
    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokePaused === "true");
    const pausedAt = await page.locator('.shot.is-active [data-karaoke-surface]').getAttribute('data-karaoke-time');
    await page.waitForTimeout(120);
    assert.equal(
      await page.locator('.shot.is-active [data-karaoke-surface]').getAttribute('data-karaoke-time'),
      pausedAt,
      "Space must freeze karaoke time",
    );
    await page.keyboard.press("Space");
    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokePaused === "false");
    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokeEnded === "true");
    assert.equal(await page.locator('.shot.is-active [data-karaoke-surface]').getAttribute('data-karaoke-visible'), "false");

    const finalTime = await page.locator('.shot.is-active [data-karaoke-surface]').getAttribute('data-karaoke-time');
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(100);
    assert.equal(await page.locator('.shot.is-active').getAttribute('data-shot-index'), "1");
    assert.equal(
      await page.locator('.shot.is-active [data-karaoke-surface]').getAttribute('data-karaoke-time'),
      finalTime,
      "ArrowRight on the final scene must not restart it",
    );

    await page.keyboard.press("r");
    await page.waitForFunction(() => {
      const layer = document.querySelector('.shot.is-active [data-karaoke-surface]');
      return layer?.dataset.karaokeEnded === "false" && Number(layer.dataset.karaokeTime) < 100;
    });
    assert.equal(await page.locator('.shot.is-active').getAttribute('data-shot-index'), "1");
    assert.deepEqual(runtimeErrors, []);
    await context.close();
  } finally {
    await browser.close();
    cleanup(fixture.tempRoot);
  }
});

test("karaoke bridge waits for delayed ready functions", {
  skip: playwright ? false : "Playwright is not installed; set PREPARE_CONTENT_PLAYWRIGHT_MODULE",
}, async () => {
  const fixture = writeFixture({ karaoke: true, readyDelayMs: 300 });
  const browser = await playwright.chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    await page.goto(pathToFileURL(fixture.previewPath).href, { waitUntil: "load" });
    await assertCaptureFirstFold(page, 0);
    await page.waitForTimeout(80);
    const pending = await page.evaluate(() => {
      const layer = document.querySelector('.shot.is-active [data-karaoke-surface]');
      const caption = layer?.querySelector('[data-karaoke-caption]');
      return {
        hasStatusNode: Boolean(layer?.querySelector('[data-karaoke-status]')),
        captionVisibility: caption ? getComputedStyle(caption).visibility : null,
        time: layer?.dataset.karaokeTime,
      };
    });
    assert.equal(pending.hasStatusNode, false);
    assert.equal(pending.captionVisibility, "hidden");
    assert.equal(pending.time, undefined, "caption timing must not start before delayed ready resolves");
    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokeReadyMode === "bridge-ready");
    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokeTime);
    await context.close();
  } finally {
    await browser.close();
    cleanup(fixture.tempRoot);
  }
});

test("sandboxed preview CSP blocks an obfuscated runtime network request", {
  skip: playwright ? false : "Playwright is not installed; set PREPARE_CONTENT_PLAYWRIGHT_MODULE",
}, async () => {
  let requestCount = 0;
  const server = http.createServer((request, response) => {
    requestCount += 1;
    response.writeHead(204);
    response.end();
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const fixture = writeFixture({ karaoke: false, probeUrl: `http://127.0.0.1:${address.port}/probe` });
  const browser = await playwright.chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    await page.goto(pathToFileURL(fixture.previewPath).href, { waitUntil: "load" });
    await assertCaptureFirstFold(page, 0);
    await page.waitForTimeout(250);
    assert.equal(requestCount, 0, "CSP must block the request before it reaches the local probe server");
    const frame = await (await page.locator('.shot.is-active iframe').elementHandle()).contentFrame();
    assert.ok(await frame.locator('img').evaluate((image) => image.complete && image.naturalWidth > 0), "inlined local image must still load");
    await context.close();
  } finally {
    await browser.close();
    cleanup(fixture.tempRoot);
    await new Promise((resolve) => server.close(resolve));
  }
});

test("host-only prefix and coincident shots use distinct karaoke pages", {
  skip: playwright ? false : "Playwright is not installed; set PREPARE_CONTENT_PLAYWRIGHT_MODULE",
}, async () => {
  const fixture = writeFixture({ karaoke: true, grouped: true });
  const browser = await playwright.chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    await page.goto(pathToFileURL(fixture.previewPath).href, { waitUntil: "load" });
    await page.waitForFunction(() => document.querySelector('.shot.is-active')?.dataset.shotId === "host-only-prefix");
    await page.waitForFunction(() => document.querySelector('.shot.is-active [data-karaoke-surface]')?.dataset.karaokeTime);
    assert.equal(await page.locator('[data-current]').textContent(), "1");
    assert.equal(await page.locator('.scene-status').textContent(), "1 / 2");
    await page.keyboard.press("ArrowRight");
    await assertCaptureFirstFold(page, 1);
    assert.equal(await page.locator('.shot.is-active').getAttribute('data-shot-ids'), "shot-01 shot-02");
    assert.equal(await page.locator('[data-current]').textContent(), "2");
    await context.close();
  } finally {
    await browser.close();
    cleanup(fixture.tempRoot);
  }
});
