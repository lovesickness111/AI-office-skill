# Visual Strategy and Storyboard Contract

Read this reference only after the current script is approved. Plan visuals from communication intent, bind them to spoken cue anchors, obtain storyboard approval, and only then build or render assets. Before comparing modalities or sourcing external material for a meaningful beat, read [visual-sourcing.md](visual-sourcing.md).

## Start with intent, not a template

For each script segment, first ask what the viewer must see that the Host's words alone cannot communicate efficiently. A segment may have one or several shots.

### Visual Policy: Never choose full-screen Human Host (`host_only` prohibited)

Tech and educational content requires continuous visual anchoring to sustain viewer engagement and reinforce comprehension. **Never choose full-screen `host_only`**. Every scene and semantic beat—including the hook, personal anecdotes, problem descriptions, and transitions—must be supported by an active visual lane (`support_top`, `support_right`, or `explainer_full`).

### Visual Asset Priorities: Screenshots, Real Photos, and Official App Logos

When selecting and creating visual illustrations, strictly follow this hierarchy:
1. **Priority 1: Real Screenshots (`web_screenshot`, `repo_screenshot`, app UI):** Real software interfaces, IDEs, terminals, code snippets, workflow configurations, and error logs provide the highest authenticity, credibility, and practical value for tech audiences.
2. **Priority 2: Official App Logos & Real Evidence:** Use official application logos (e.g., Gmail, Google Docs, Calendar, Telegram, GitHub, Gemini, Python) to clearly illustrate workflows, integrations, and ecosystem connections.
3. **Priority 3: Code-native Components & Interactive Diagrams:** Deterministic HTML/SVG/CSS diagrams for state transitions, matrices, and comparisons.
4. **Lowest Priority: AI-Generated Illustrations:** Only use AI image generation when depicting purely abstract psychological states or metaphors (e.g., prompt fatigue) that lack real-world interfaces. Never use generic AI images to replace software UI, code, or architecture diagrams.

## Compare viable treatments before selecting a renderer

For each meaningful visual beat, generate two to four useful `visual_options` before selecting a renderer whenever genuinely different treatments are viable. Do not pad the list with decorative variants that communicate the same thing. If only one treatment is responsible or practical, record that constraint instead of inventing weak alternatives.

The allowed option modalities are:

```text
host_only | code_native | licensed_video | screen_recording |
web_screenshot | repo_screenshot | web_image | static_graphic
```

Each option records a stable `id`, its `modality`, a concrete `treatment`, `why` it helps this exact beat, a `source_plan`, and a `rights_note`. `selected_option_id` must resolve to one option on the same shot. Compare explanatory value, credibility, source fitness, rights, production cost, and continuity; do not default to code-native motion merely because it is easy to generate.

Treat `host_only` as a composition decision before creating a shot. If the Host is the best visual for the beat, create no shot. While comparing treatments, a shot may retain `host_only` as an unselected alternative, but once a supporting visual is selected, place that selected non-host treatment and the other useful alternatives directly on the shot:

```json
{
  "id": "shot-stable-id",
  "segment_id": "segment-stable-id",
  "intent": "What the viewer must understand at this beat",
  "visual_options": [
    {
      "id": "option-code-native",
      "modality": "code_native",
      "treatment": "A deterministic comparison that changes with the narration",
      "why": "Makes the changing relationship faster to understand than speech alone",
      "source_plan": "Build from verified claim values already in the ledger",
      "rights_note": "Original code-native treatment; source facts retain their citations"
    },
    {
      "id": "option-static",
      "modality": "static_graphic",
      "treatment": "A still comparison with the same verified values",
      "why": "Preserves clarity when motion would not add meaning",
      "source_plan": "Compose locally from the verified claim ledger",
      "rights_note": "Original static treatment; source facts retain their citations"
    }
  ],
  "selected_option_id": "option-code-native"
}
```

Although `host_only` belongs to the overall modality vocabulary, never select it inside `shots[].visual_options`. If it wins the comparison, omit the shot instead; the Human Host remains the visual.

After selection, map the treatment to the existing renderer contract: `code_native` normally becomes `component`, `html`, or `mermaid`; `licensed_video` becomes a cleared local `stock` asset; `screen_recording` remains `screen_recording`; screenshots, web images, and static graphics normally become local `image` assets. Choose `html` for a still only when deterministic composition adds real value, not to bypass provenance.

## Canonical storyboard schema

`storyboard/storyboard.json` uses this exact snake_case contract. Do not introduce aliases such as `segmentId`, `cueId`, or `sourceUrl`.

```json
{
  "schema_version": "1.0",
  "project": {
    "ratio": "9:16",
    "fps": 30,
    "width": 432,
    "height": 768,
    "theme": "light-editorial",
    "default_host_layout": "support_top",
    "scene_navigation": {
      "mode": "manual",
      "boundary_policy": "sentence_start",
      "intra_sentence_changes": "component_state"
    },
    "karaoke_caption": {
      "enabled": true,
      "placement": "capture_stage_bottom",
      "bottom_margin_px": 100,
      "max_lines": 2,
      "reading_wpm": 150,
      "pause_ms": {
        "comma": 250,
        "clause": 400,
        "sentence": 650,
        "scene_end": 900
      },
      "scene_advance": "manual",
      "end_indicator": "NEXT →"
    }
  },
  "editorial_plan": {
    "hook_segment_id": "segment-stable-id",
    "hook_beats": [
      {
        "id": "beat-hook-title",
        "cue_id": "cue-stable-id",
        "purpose": "title | pain | consequence | reversal | promise | payoff | roadmap",
        "coverage": "shot | host_only",
        "shot_ids": ["shot-stable-id"]
      }
    ],
    "title_treatment": {
      "mode": "dedicated_scene | integrated_hook",
      "shot_id": "shot-stable-id",
      "screen_text": "Readable title or faithful shortened title"
    },
    "ending": {
      "mode": "visual_cta | spoken_cta | host_only | none",
      "shot_id": "final-shot-stable-id",
      "screen_text": "Follow Dev Xịn"
    }
  },
  "segments": [
    {
      "id": "segment-stable-id",
      "text": "Exact approved spoken text for this segment",
      "host_layout": "support_top",
      "cues": [
        {
          "id": "cue-stable-id",
          "phrase": "Exact unique phrase from segment text"
        }
      ]
    }
  ],
  "shots": [
    {
      "id": "shot-stable-id",
      "segment_id": "segment-stable-id",
      "lane": "support_top | support_right | explainer_full",
      "intent": "What this shot helps the viewer understand",
      "enter": {
        "cue_id": "cue-stable-id",
        "offset_ms": 0
      },
      "exit": {
        "cue_id": "cue-stable-id",
        "offset_ms": 0
      },
      "visual_options": [
        {
          "id": "option-code-native",
          "modality": "code_native",
          "treatment": "Deterministic animated comparison",
          "why": "Motion reveals the changing relationship",
          "source_plan": "Build locally from verified claim values",
          "rights_note": "Original implementation; facts retain their citations"
        },
        {
          "id": "option-static",
          "modality": "static_graphic",
          "treatment": "Still editorial comparison",
          "why": "A lower-cost fallback that preserves the explanation",
          "source_plan": "Compose locally from verified claim values",
          "rights_note": "Original design; facts retain their citations"
        }
      ],
      "selected_option_id": "option-code-native",
      "renderer": {
        "kind": "component | html | mermaid | stock | image | screen_recording",
        "entry": "optional run-relative implementation path",
        "variant": "optional safe state token when one component serves several sentence-level scenes"
      },
      "duration_ms": 2400
    }
  ],
  "assets": [
    {
      "id": "asset-stable-id",
      "path": "optional run-relative local path",
      "source_url": "optional provenance URL",
      "creator": "optional creator or origin",
      "license": "optional license or rights status",
      "sha256": "optional local content hash"
    }
  ]
}
```

For every new storyboard, explicitly materialize `project.ratio`, `project.width`, `project.height`, `project.theme`, `project.default_host_layout`, `project.scene_navigation`, and `editorial_plan`; do not rely on renderer fallbacks for an approval artifact. The default desktop-capture preset is exactly `ratio: "9:16"`, `width: 432`, `height: 768`, `theme: "light-editorial"`, and `default_host_layout: "support_top"`. New or materially revised Human Host storyboards use `scene_navigation: {mode: "manual", boundary_policy: "sentence_start", intra_sentence_changes: "component_state"}`. This separates a manual recording scene from the finer visual beats inside it. `project.karaoke_caption` is optional and applies only to the interactive Human Host desktop-capture preview/carousel and scene teleprompter workflow. It is not automatically burned into per-shot MP4 renders. When enabled with no explicit overrides, use exactly `placement: "capture_stage_bottom"`, `bottom_margin_px: 100`, `max_lines: 2`, `reading_wpm: 150`, `pause_ms: {comma: 250, clause: 400, sentence: 650, scene_end: 900}`, `scene_advance: "manual"`, and `end_indicator: "NEXT →"`; `clause` covers colon and semicolon pauses. `end_indicator` is teleprompter/package metadata only and must never be rendered inside the capture stage. The preview hides this estimated karaoke overlay by default; pass `--karaoke-overlay visible` only for an explicit rehearsal. Hiding it must not alter scene count, scene text, or manual navigation. Absence or `enabled: false` means no karaoke overlay or karaoke package artifact. These dimensions define the real HTML/stage that the Human Host records directly on a desktop with dedicated recording software. They are not a reduced preview of a larger master, and this contract does not assume a later export or upscaling step. Older artifacts with no effective `support_top` composition may omit dimensions for backward compatibility, in which case the renderer may derive them from the ratio. An effective `support_top` composition always requires explicit `width: 432` and `height: 768`. `segments[].host_layout` is an optional per-segment override, but selecting `support_top` at project, segment, or shot level commits the entire stage to the `9:16`, `432x768` geometry described below. `shot.lane`, `enter.offset_ms`, `exit`, `exit.offset_ms`, `renderer.entry`, `renderer.variant`, and `duration_ms` are optional only for legacy artifacts or when their absence remains unambiguous. A safe `renderer.variant` lets several sentence-level shots reuse one component implementation while selecting different authored states through `window.__hyperframeContext.variant`; it is not a substitute for a mid-sentence Next boundary. New or revised shots carry `visual_options` and `selected_option_id`. A shot without `exit` must have a usable duration. A web shot must have a valid `renderer.entry`.

Storyboard invariants:

- Every `segments[].id` matches a current `script/final.json` segment, and `segments[].text` exactly matches its approved spoken text.
- `editorial_plan.hook_segment_id` resolves to the approved hook segment. Its `hook_beats` are unique, enter through cues from that segment, and make every declared opening beat auditable as either `shot` coverage or an intentional `host_only` choice. Shot coverage has one or more same-segment shot IDs; Host-only coverage has no shot IDs.
- `editorial_plan.title_treatment` resolves to a shot in the hook segment and carries readable screen text. `integrated_hook` may reuse a shot that also covers another opening beat; `dedicated_scene` names a distinct title-led shot.
- `editorial_plan.ending` is explicit. `visual_cta` and `spoken_cta` resolve to the final storyboard shot and carry screen text; `host_only` and `none` do not invent a decorative shot. `spoken_cta` additionally carries `spoken_phrase`, which must occur exactly once in the approved canonical script segment owned by the ending shot. Every other ending mode omits `spoken_phrase`, so a visual-only CTA cannot silently imply new Host speech.
- Each cue ID is unique in the storyboard. Its phrase appears verbatim and resolves unambiguously within that segment. If a short phrase repeats, choose a longer anchor instead of guessing an occurrence.
- Every shot has a unique ID, references an existing segment, states a concrete intent, and enters on a cue from that same segment. Under `project.scene_navigation`, each distinct entry cue is a manual Next boundary and therefore starts at character zero of the segment or immediately after terminal punctuation (`.`, `?`, `!`, `…`), with `offset_ms: 0`. A comma, colon, semicolon, conjunction, preposition, or clause fragment is not a safe boundary. Visual changes inside a sentence are states in the current component and may still use non-entry cue anchors.
- Every new or revised shot contains two to four genuinely viable `visual_options` when alternatives exist and has a `selected_option_id` resolving to a non-`host_only` option within that shot.
- `exit.cue_id`, when present, resolves to a valid cue in the same segment. Otherwise `duration_ms` defines the planned shot length.
- `renderer.kind` is one of the six values shown above. For `component` and `html`, `renderer.entry` resolves to a run-contained local `.html` entry point.
- An active shot lane is `support_top`, `support_right`, or `explainer_full`. Timeline gaps with no active shot are `host_only`; do not create a decorative `host_only` shot.
- Whenever `support_top` appears as the project default, a segment override, or an active shot lane, the project fields are exactly `ratio: "9:16"`, `width: 432`, and `height: 768`; do not combine `support_top` with a horizontal, implicit, or larger-master stage.
- When `project.karaoke_caption.enabled` is true, its placement, pauses, reading rate, line limit, manual scene advance, and teleprompter-only end indicator are explicit and deterministic. The plan may remain packaged while the preview overlay is hidden. If explicitly shown, the capture overlay displays bounded phrase groups, highlights exactly one current word, removes prior groups, and hides during pauses and after completion; it never displays transport prompts. This recording aid does not authorize publishing burned-in captions or changing canonical spoken prose.
- The storyboard may contain no shots for a segment. It may also contain parallel shots distinguished by lane when the production plan genuinely needs layers.
- Asset paths are local and contained within the run directory. Remote URLs are provenance, not runtime dependencies.

## Compose around the Human Host

Use supporting visual composition modes consistently:

- `support_top` (**Primary Default**): the real desktop-recording stage is vertical `9:16` at `432x768`. The upper illustration frame is the exact square `(x=0, y=0, width=432, height=432)`. The lower rectangle `(x=0, y=432, width=432, height=336)` stays blank so the Human Host can place their own camera feed there in the recording software. Karaoke is hidden by default; when the creator explicitly makes it visible, its declared capture-stage-bottom placement is the sole allowed intentional overlay exception and the creator must position their camera feed and face around it. Clip or contain every illustration pixel inside the upper `1:1` frame, and forbid every other overlay from entering the Host frame. This stage is not a preview of a larger master, and no later video-export step is assumed. This is the planning default for all video content.
- `support_right`: the Host remains on the left while the visual occupies the right. Use it only when the creator, project, filming composition, or needs of a specific beat explicitly call for it.
- `explainer_full`: the visual temporarily owns the full stage because the mechanism or evidence needs more space. On the default vertical desktop-capture preset it may use the full `432x768` stage; return deliberately to `support_top` afterward.
- `host_only` (**Prohibited as full-screen default**): Never leave the Human Host alone on a blank full screen. Every scene must have active supporting visuals in the top or right frame to reinforce spoken information and hold viewer attention.

`project.default_host_layout` stores the planning default (`support_top`), while `segments[].host_layout` may override it for a segment. Shot `lane` records the actual active composition (`support_top`, `support_right`, or `explainer_full`). If any segment or shot does use `support_top`, normalize the whole project to its vertical desktop-capture contract. Defaults never authorize placing visuals over the Host's face, captions, or essential gestures.

## Cue timing and recorded audio

Before the Host records audio, cues are semantic anchors, not fabricated absolute timecodes. Separate two jobs: a shot-entry cue creates a manual scene boundary and must start a complete sentence with zero offset, while cues inside that sentence may trigger states within the already visible component. Never create another Next page solely because an icon, label, diagram node, screenshot crop, or emphasis changes mid-sentence. Do not estimate authoritative sync from word count or reading speed.

The packaged recording teleprompter derives scenes from canonical text position zero and the safe ordered shot-entry cues. If the first entry cue is later than the start, an initial Host-only scene owns that exact prefix. Each distinct entry starts one subsequent scene; coincident shots share it. With no shots, one Host-only scene owns all text. Scene boundaries consume no characters, and concatenating scene text must reproduce canonical punctuation, whitespace, and wording exactly. The preview uses these scenes whether karaoke is visible or hidden. Before audio exists, optional `reading_wpm` plus punctuation pauses provides rehearsal timing only. When explicitly visible, the capture overlay replaces bounded phrase groups as speech advances, highlights only the current word, hides during configured punctuation/scene pauses, and stays hidden after the scene completes. It never shows `NEXT`, `END`, `HẾT`, or a transport button. Karaoke never auto-advances; `end_indicator` remains only in the scene-divided teleprompter and package metadata. If the preview implements keyboard capture controls, use `Space` for pause/resume, `R` to restart the current scene, and `ArrowRight` for manual Next; on the final scene, `ArrowRight` is a no-op.

After recorded audio is available, run forced alignment against the exact `segments[].text`. Forced-alignment timestamps override rehearsal estimates for captions and visual sync. Resolve cue phrases to measured word timestamps, then derive shot enter and exit times with their offsets. Keep the editorial storyboard and its cue IDs stable; store measured timing in the render/alignment output. If text diverges, a cue is ambiguous, or alignment confidence is low, stop and request correction rather than silently guessing.

## Continuity across shots

Treat the visual sequence as one explanation, not unrelated cards:

- Reuse project-specific typography, color semantics, spacing, icon style, and motion grammar.
- Carry important entities and spatial positions forward when the explanation revisits them.
- Make each shot answer the segment's stated `intent`; remove labels and decoration that do not help that intent.
- Use producer-script notes to coordinate camera and B-roll handoffs without placing those notes in the teleprompter.
- Check that visual setup and payoff follow the approved outline transitions.

No brand palette, watermark, CTA, slogan, topic, aspect ratio, or visual motif is universal. Derive them from the current project and user choices. The only creator-specific CTA preference currently established here is a visual-only `Follow Dev Xịn` ending for Dev Xịn work when no explicit project or user choice overrides it; do not apply it to unrelated brands, and do not turn it into spoken copy without script approval. When neither the user nor an established brand provides a visual direction, use the restrained **`light-editorial`** default: light neutral canvas, dark readable type, one or two accessible accents, and minimal decoration. The navy/cyan language used by any one project is project-specific and must never become this skill's default.

## Motion design: Instant Base and Speech-Paced Focus Animations

Animation must guide viewer attention without lagging behind speech:

1. **Prohibit Global Scene Fade-In (Instant Base Layout):**
   - When the Host presses Next into a new scene, the headline, eyebrow, container layout, grid, and screenshots must be **100% visible immediately at millisecond 0 (`opacity: 1`, `transform: none`)**.
   - Never fade in the overall scene over 300ms–800ms. Global fade-in makes visuals feel delayed compared to speech and gives viewers an impression of slow responsiveness.
2. **Focus Animations on Speech Progress (Speech-Paced Dynamics):**
   - **Progressive Reveal:** Show sub-blocks, checklist items, or secondary cards sequentially as the narration introduces them.
   - **Active Highlight & Glow Borders:** Add a vibrant active border (e.g. `2px solid #2563eb`), glowing box-shadow, or color pop to the exact card or block being discussed while keeping background elements stable.
   - **Subtle Focus Zoom-In (Punch-In):** Apply a gentle scale-up (`scale(1.025) – scale(1.04)`) to the screenshot or active card to draw the viewer's eye directly to the focal proof point.

## Route sourcing decisions to the focused contract

Use [visual-sourcing.md](visual-sourcing.md) for modality selection, source capture, primary evidence, website and repository screenshots, privacy, licensing, and asset registration. In all cases, runtime files are local immutable copies; remote URLs record provenance and are never hotlinked. Unknown rights remain an explicit blocker and must not be represented as publication-ready.

## Deterministic web component contract

The reusable starter lives at `assets/animation-starter/index.html`. Adapt it only after storyboard approval. Each `component` or `html` entry must expose:

```js
window.__hyperframe = {
  durationMs,
  ready,
  seek(ms) { /* render the exact frame for absolute time ms */ }
};
```

Required behavior:

- `durationMs` is finite and positive.
- `ready` may be a value, a Promise, or a zero-argument function returning either. It must resolve truthy within the renderer's 10-second readiness timeout, and only after all local fonts, images, and layout dependencies are ready.
- The preview and renderer expose a read-only scene hint at `window.__hyperframeContext` with `shotId`, `sceneId`, and optional `variant`. A reusable component may select its authored initial/state sequence from `variant`; it must still expose the same deterministic API and must not infer semantic behavior from wall-clock time or remote state.
- `seek(ms)` is absolute, idempotent, and deterministic: the same input produces the same pixels regardless of prior calls.
- Clamp out-of-range time safely. Rendered state after `seek(ms)` must not depend on wall-clock time, network timing, `Date.now()`, or unseeded randomness. Browser-preview autoplay may use a clock, but it must run exactly once from the start through `durationMs`, render the clamped final frame, stop, and remain on that frame. Looping is forbidden unless the creator explicitly requests it for that specific shot. An explicit restart control or page reload may replay from the start. The first manual `seek(ms)` cancels autoplay and permanently switches the component to deterministic manual mode.
- Render the composite at the storyboard dimensions and fps. For `support_top`, either author the visual as a `432x432` component placed at `(0,0)` or render on the full `432x768` stage with a hard clip to that same square; both approaches must leave the Host frame completely unpainted except for a karaoke overlay that the creator explicitly made visible for rehearsal. Use local assets and fonts; layout must not depend on a live CDN.
- Treat those dimensions as a fixed canvas. Responsive preview containers may scale the whole canvas uniformly, but must not cause text, line breaks, or geometry to reflow differently from the rendered frame.
- Treat the first browser viewport of a carousel or review page as a capture-only fold. When that viewport is at least as wide and tall as the fixed stage, center the stage at its exact `432x768` CSS-pixel size without scaling. Place the review chrome—including the page title, project metadata, shot title and cue, intent, Restart, Previous/Next, status, and scene dots—after that fold so none of it competes with or shrinks the recording surface. The scale calculation may use only the capture fold's available width and height; never subtract header, metadata, intent, controls, dots, or other trailing document content from the stage's height budget, and never try to fit stage plus review chrome into the same viewport. Only a viewport smaller than the fixed stage may uniformly downscale the stage to fit; never upscale it. Compute any fallback scale from both available width and height and cap it at `1`.
- Size typography and internal zones from the fixed component coordinate system, not from the outer browser viewport. In particular, do not use `vw`, `vh`, `vmin`, or `vmax` for text inside a `432x432` `support_top` visual. Give the headline, diagram, and caption separate bounded regions; if source text does not fit, shorten or redesign it instead of allowing overlap or shrinking it below readable size.
- A `file://` preview must preserve access to run-contained relative images, fonts, and other local assets without enabling network dependencies. Configure the trusted local iframe accordingly or bundle the asset into the component, then verify every required image reports non-zero natural dimensions in the preview itself; validating the image file separately is not sufficient.
- Run the interactive preview in a runtime network-isolated CSP sandbox. Keep run-contained local assets usable, but block remote loads and runtime network APIs. Use a parent-child bridge to wait for each component's `ready` contract, fail visibly after 10 seconds, and never treat a timed-out component as capture-ready.
- Escape source-derived text before inserting it into markup. Do not use `eval`, dynamically fetched code, remote embeds, or runtime network APIs.

## Safe validation, preview, and render

`scripts/render_web_asset.mjs` has three roles:

- `validate` checks the storyboard, cue references, path containment, renderer entries, asset provenance fields, and deterministic web contract.
- `preview` writes `creator-pack/hyperframes_preview.html`. Web shots use their actual local entry in an iframe; unsupported or not-yet-built non-web modalities remain explicit `UNRENDERED` cards rather than misleading static substitutes. Karaoke is hidden by default; `--karaoke-overlay visible` is an explicit rehearsal-only opt-in and `--karaoke-overlay hidden` may be supplied for clarity.
- `render` renders web shots frame by frame and writes `creator-pack/assets/<shot-id>.mp4` plus `render_manifest.json` when Playwright and ffmpeg are available.

Use its storyboard input and optional run-directory resolution; use an explicit Playwright module override only when needed by the environment. The renderer must resolve all paths inside the run directory, block network requests, wait for `ready`, call `seek(ms)` for every frame, encode through ffmpeg without a shell, and fail visibly if a dependency or frame is invalid. It must not silently fall back to a screenshot or claim an MP4 exists when rendering did not complete.

Before approval or packaging, perform runtime QA at the actual project dimensions:

- verify every declared opening beat in `editorial_plan` has its intended visible state or a documented Host-only decision, the title treatment is readable early in the opening, and the declared ending is actually the final timeline treatment;
- inspect the start, at least one middle state, and the final state for clipping, overlap, safe areas, contrast, and readable labels;
- at those states, compare computed bounds for the headline, diagram, caption, and visual frame; require every region to stay contained and require adjacent regions not to intersect, then repeat the check with an outer browser viewport wider than the fixed stage;
- seek to the same timestamp from different prior states and confirm identical pixels; test negative and over-duration seek values for safe clamping;
- verify browser-preview autoplay runs once, reaches the clamped final frame, and remains there without looping; verify an explicit restart or reload may replay it, and the first manual `seek()` stops autoplay and permanently enters deterministic manual mode;
- preview fixed canvases by uniformly scaling a wrapper or iframe to fit while preserving aspect ratio and a fixed transform origin; never shrink the browser viewport and let responsive CSS invent a different composition;
- on representative desktop viewports, verify the active stage remains entirely within the first viewport and is exactly `432x768` whenever at least that much viewport space is available; verify all review chrome begins at or below the first viewport boundary, changing the amount of metadata does not change stage dimensions, the computed scale never exceeds `1`, and every local image has loaded successfully inside the actual preview iframe;
- validate every manual scene transition against the spoken projection: the next scene starts at a sentence boundary, the previous scene does not end on a comma, conjunction, preposition, or unfinished clause, and intra-sentence visual changes remain inside one component; treat unusually short scenes (under roughly 8 spoken words) or long scenes (over roughly 70) as review warnings rather than automatic failures;
- for `support_top`, verify the real desktop-recording stage is exactly `432x768`, the illustration is clipped to `(0,0,432,432)`, and no visual pixel appears inside the blank Host frame `(0,432,432,336)`. With the default hidden overlay, confirm there is no karaoke DOM inside the capture stage and that scene count/navigation still matches `teleprompter-script.md`. If the overlay is explicitly visible, verify the Host can be positioned around it, every displayed phrase fits the configured line limit without clipping, exactly one active word is highlighted, prior phrase groups disappear, the caption hides during pauses and after scene completion, no transport prompt appears in the capture stage, and manual Next is still required;
- verify support lanes leave the promised Host space clear and that timeline gaps return to `host_only`; when `host_only` is explicitly active, verify the Host may reclaim the full stage, and when `explainer_full` is active on the vertical preset, verify the visual may use the full `432x768` stage.

Preview and rendered media are derived artifacts. Changing component code, a local asset, dimensions, fps, or timing invalidates the affected preview/render outputs and package report, while leaving approved editorial artifacts intact unless their semantic contract changed.
