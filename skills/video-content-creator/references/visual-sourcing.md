# Visual Options, Sourcing, and Rights

Read this reference after script approval and before selecting a renderer or acquiring material for a meaningful visual beat. It complements [visual-strategy.md](visual-strategy.md): that file owns storyboard structure and composition; this file owns alternatives, source fitness, provenance, rights, privacy, and capture quality.

## Start with a visual decision, not a search query

State what the viewer must understand, then produce two to four useful options when genuinely different treatments are viable. Every option uses one modality:

```text
host_only | code_native | licensed_video | screen_recording |
web_screenshot | repo_screenshot | web_image | static_graphic
```

For every option record:

- `id`: stable within the storyboard;
- `treatment`: what will appear and how it changes during the beat;
- `why`: the explanatory or credibility gain over the Host alone;
- `source_plan`: exact material, page, repository, recording, data, or original build required;
- `rights_note`: ownership, license, permission, attribution, privacy review, or unresolved risk.

First decide whether the beat should remain `host_only`. If so, create no shot. If a supporting or full-frame visual is warranted, record the useful alternatives directly in `shots[].visual_options` and select one with that shot's `selected_option_id`. A `host_only` alternative may remain for comparison, but it cannot be selected on an existing shot; if it wins, omit the shot.

Select only after comparing explanatory value, credibility, continuity, production effort, rights, and privacy. Two crops of the same asset are not two meaningful options. When only one option is viable, state why instead of padding the decision.

## Modality guidance and asset hierarchy

### Hierarchy of Asset Sourcing: Real Proof Over Generic Decoration

Always prioritize authentic evidence in this order:
1. **Priority 1: Real Screenshots (`web_screenshot`, `repo_screenshot`, app UI):** When discussing software tools, features, terminals, or workflows, always capture the real application screen. Real screenshots provide concrete credibility and immediate practical understanding for tech viewers.
2. **Priority 2: Official Application Logos & Brand Marks:** When illustrating architectural flows, integration pipelines, or ecosystem options, always incorporate official high-resolution logos (e.g., Gmail, Google Docs, Calendar, Telegram, GitHub, Gemini, Python). Recognizable logos instantly orient the viewer.
3. **Priority 3: Code-Native Components (`code_native`):** Deterministic HTML/SVG/CSS diagrams for state transitions, matrices, and comparisons.
4. **Lowest Priority / Restricted: AI-Generated Images:** Only generate AI illustrations when expressing purely abstract psychological states or metaphors (e.g., morning prompt fatigue) that lack real-world user interfaces. Never substitute a generic AI drawing for software UI, code, or terminal commands.

### `host_only` (Prohibited as Full-Screen Default)

Never choose full-screen `host_only`. Every scene must pair the Human Host with an active supporting visual lane (`support_top`, `support_right`, or `explainer_full`).

### `code_native`

Use deterministic HTML, SVG, CSS, canvas, Mermaid, or another local code-native treatment for a changing state, comparison, sequence, or spatial relationship. Cite the underlying facts even when the drawing is original. A recreated chart must say it is recreated and preserve the source's units, population, period, uncertainty, and caveats.

Do not turn a credible primary artifact into a decorative mockup merely to keep the visual style uniform. When the page, chart, or product behavior itself is evidence, prefer an exact capture.

### `licensed_video`

Use only video that is user-owned, explicitly licensed for the intended publication, commissioned, or otherwise cleared. Record the owner or creator, source URL or delivery record, license or permission terms, required attribution, and any territory, platform, or time restrictions.

Do not download arbitrary online video, assume public availability means reusable, or label unknown rights as royalty-free. If rights cannot be verified, the option is not publication-ready.

### `screen_recording`

Record actual behavior with a rehearsed action plan. Use a clean account or fixture, hide browser profiles and notifications, and remove credentials, customer information, personal data, tokens, internal URLs, and unrelated tabs. Record the product, build or version, and capture date when behavior may change.

A screen recording demonstrates only the state actually captured. Do not edit it to imply an action, latency, or result that did not occur.

### `web_screenshot`

When the claim concerns a website, capture the exact page that supports it rather than a generic image of the brand or a recreated page. Record the canonical page URL, page title, creator or publisher, capture date, and the section or visible locator. Preserve enough context for the viewer to understand what the page is and what the highlighted evidence means.

Use a viewport and zoom that keep the relevant text legible. Hide account identity, cookies, notifications, saved data, and unrelated browser chrome. A screenshot may still require permission or a rights review; factual relevance does not automatically grant publication rights.

### `repo_screenshot`

For GitHub or another source repository, pin all of the following:

- repository owner and name;
- canonical repository URL;
- branch, tag, or ref;
- exact commit SHA;
- file path and relevant line range or UI location;
- capture date.

Prefer a clean public or fixture view. Hide signed-in account identity, private repository names, organization data, access tokens, secrets, email addresses, local paths, issue drafts, and unrelated tabs. Do not present a moving default branch as stable evidence without a commit pin.

### `web_image`

Treat image search engines, including Google Images, as discovery tools only. A search result, thumbnail URL, cache, or preview is never provenance and never proves a license.

Open the original page. Verify the actual creator or publisher, original asset URL when available, license or explicit permission, attribution requirements, and whether edits or commercial use are allowed. Store the selected image as a local immutable copy; never hotlink or render the search thumbnail.

### `static_graphic`

Use an original diagram, table, chart, annotated still, or editorial composition when motion does not add explanatory value. Keep source facts traceable. If derived from external material, distinguish the creator's design rights from the data or claim source and register both as needed.

## Evidence-first rules

### Numeric claims

Prefer the primary dataset, paper, report, or official page. When the published chart or table is itself useful evidence, capture that exact primary page with its labels and context. If recreating the number code-natively improves legibility, transcribe it from the primary source, independently verify the transcription, preserve units and caveats, label it as recreated, and keep the primary locator in the asset or producer record.

Do not source a number from a commentary page when the underlying primary source is available. Do not make a small or qualified result look universal through scale, cropping, animation, or missing denominators.

### Websites and products

Use the exact page or actual product flow relevant to the narration. A homepage, logo, generic dashboard, or stock laptop shot does not substantiate a claim about a specific feature or statement. Record capture date and version because web state can change.

### Repositories

Pin evidence to a commit. Record the repository, ref, and commit combination before capture, and keep the local capture or clone state immutable for the approved artifact. Never expose a developer's personal environment to make a repository shot feel authentic.

## Provenance and local asset registration

Before packaging, register every external, captured, or generated asset in storyboard `assets[]`:

- `id` is stable and unique;
- `path` points to the local immutable file used in preview and render;
- `source_url` points to the original page, repository, or rights record, not a search result;
- `creator` identifies the creator, publisher, user, organization, or generation origin when known;
- `license` records the verified license, explicit permission, user ownership, or a clear unresolved rights-review state;
- `sha256` binds the record to the exact local bytes.

Store local copies under the run directory. Never hotlink runtime media. If the original page cannot be opened, the creator cannot be identified, or the rights cannot be verified, record the uncertainty and select a different option or stop for review. Do not invent a license.

Generated material must record its generation origin and any input asset rights. User-supplied material is not automatically cleared; confirm ownership or permission for the intended channels.

## Capture and runtime QA

For screenshots and recordings, review the entire frame at full resolution, not only the intended crop. Check account identity, secrets, customer data, notifications, browser chrome, unrelated tabs, private paths, and legibility. Keep a clean master capture and derive crops from that immutable source.

For code-native and captured visuals alike, review them in the actual storyboard composition mode and project dimensions. A `support_top` or `support_right` asset must remain readable at its real on-screen size, not only when opened full-screen.

Use fixed-canvas previews for fixed-canvas components: render at the canonical width and height, then uniformly scale the whole canvas to fit the preview container. Preserve aspect ratio and a fixed transform origin. Do not rely on responsive reflow in a smaller iframe, because changed line breaks and geometry are not evidence of the final rendered frame.

For deterministic web visuals, inspect start, middle, and end frames; seek to the same time after different prior seeks; test clamping outside the duration; and confirm preview autoplay stops after the first manual seek. No runtime asset may require network access.
