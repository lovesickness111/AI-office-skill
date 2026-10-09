# Artifact and Gate Contract

Read this reference before initializing, resuming, revising, validating, or packaging a run. The workflow is a dependency graph with conversational approvals, not a one-click pipeline.

## Canonical run layout

```text
<run-dir>/
  run_manifest.json
  research/
    full_transcript.md
    source_analysis.json
    source_playbook.md
    claim_ledger.json
    research_cache.json       # optional derived cache used by the YouTube helper
  editorial/
    scope_proposal.json
    outline.json
  script/
    final.json
    teleprompter-script.md    # generated spoken-only review view at the script gate
  storyboard/
    storyboard.json
  creator-pack/
    teleprompter-clean.md     # exact approved spoken-only projection
    teleprompter-script.md    # scene-divided Human Host recording view
    karaoke_captions.json     # present when project.karaoke_caption.enabled is true
    producer-script.md
    quality_report.json
```

The four canonical research artifacts are transcript, analysis, playbook, and claim ledger. `research_cache.json` is optional derived state for the YouTube helper; it is neither required nor registered for an article run. The evidence packet is the canonical research set, not an extra summary that discards source detail. For an article, `full_transcript.md` contains the user-provided article content with stable locators such as `[section: Heading]` or `[paragraph: 12]`.

`scripts/workflow.py` is the state authority. Its supported operations are `init`, `status`, `register`, `approve`, `validate`, `materialize-script`, and `package`. Pass it an explicit run directory. Use `scripts/youtube_to_content.py` only for the YouTube research phase; its research operations may produce or reuse the four canonical research artifacts and register research only after they validate.

## Manifest

`run_manifest.json` has manifest version `1`. It uses UTC timestamps and atomic writes. It must contain enough information to answer what the run is, which inputs produced each stage, which artifacts are current, and which exact revisions the user approved.

Required fields:

```json
{
  "manifest_version": 1,
  "run_id": "stable-local-id",
  "created_at": "UTC ISO-8601",
  "updated_at": "UTC ISO-8601",
  "source": {
    "url": "YouTube URL when applicable"
  },
  "configuration": {},
  "stages": {},
  "approvals": {}
}
```

Stage and approval maps are populated lazily as work is registered and approved; absence means no record yet. For an article run, put its source kind, stable user-content identifier, and content hash in `configuration`; the original article content remains in `research/full_transcript.md`. Each registered stage record tracks `status`, `registered_at`, `checked_at`, aggregate `artifact_sha256`, canonical `artifacts`, `input_stage`, `input_artifact_sha256`, and validation result. Each approval record tracks `status`, `approved_at`, `approved_by`, the approved `artifact_sha256`, and an optional concise note. Never store hidden reasoning or raw chain-of-thought.

## Canonical artifact schemas

All JSON artifacts use UTF-8, stable IDs within a run, and a `schema_version`. Optional presentation fields are allowed, but the following semantic fields are required.

### `research/source_analysis.json`

- `schema_version`: `"1.0"`.
- `source`: title, creator or author when known, source kind, locator, language, and duration when applicable.
- `topic`, `core_thesis`, and `audience`.
- `hook`: type, source locator, mechanism, and reusable abstract pattern. Keep verbatim excerpts short and only when needed for analysis.
- `flow[]`: stable ID, source locator, purpose, technique, and key claim in observed order.
- `key_facts[]` plus `pacing`, `rhetorical_devices[]`, `visual_moments[]`, and `weaknesses[]` when supported by the source.

This artifact describes the source. It does not prescribe the new video's outline.

### `research/claim_ledger.json`

```json
{
  "schema_version": "1.0",
  "source_url": "YouTube URL, primary article URL when supplied, or null",
  "claims": [
    {
      "id": "claim-stable-id",
      "text": "Atomic checkable claim",
      "kind": "source_claim | independently_verified | creator_interpretation | open_uncertainty",
      "evidence": [
        {
          "timestamp": "YouTube timestamp when applicable",
          "detail": "Brief paraphrase plus article section/paragraph or external locator",
          "source_url": "Primary-source URL when independently verified"
        }
      ],
      "verification_status": "supported | disputed | unverified | not_applicable",
      "confidence": "high | medium | low",
      "must_keep": true,
      "usage_note": "How the script may qualify or use the claim"
    }
  ]
}
```

Do not convert the source speaker's assertion into an independently verified fact. Current or consequential technical claims should be checked against primary sources when available. Preserve disagreements and uncertainty instead of smoothing them away.

### `editorial/scope_proposal.json`

```json
{
  "schema_version": "1.0",
  "format": "single_video | series",
  "title": "Working title",
  "thesis": "Original thesis for the new content",
  "audience": "Intended viewer",
  "audience_profile": {
    "primary_groups": [
      {
        "id": "stable-group-id",
        "label": "Human-readable viewer group",
        "need": "Problem or decision this group brings",
        "assumed_knowledge": []
      }
    ],
    "secondary_groups": [],
    "shared_need": "Reason these groups belong in one video",
    "shared_baseline": "Lowest common knowledge safe to assume",
    "desired_takeaway": "What viewers should understand, decide, or do",
    "do_not_assume": [],
    "avoid_terms": [],
    "language": "vi-VN",
    "tone": ["plain-spoken", "direct"],
    "term_policy": "plain_first"
  },
  "creator_goal": "What the Human Host wants to achieve",
  "viewer_promise": "Specific value delivered",
  "rationale": "Concise evidence-based scope rationale",
  "included_claim_ids": ["claim-stable-id"],
  "deferred_claim_ids": [],
  "target_duration_seconds": 300,
  "word_budget": {"min": 600, "target": 750, "max": 900},
  "knowledge_units": [],
  "parts": [
    {
      "id": "part-stable-id",
      "promise": "Part-specific promise",
      "knowledge_unit_ids": []
    }
  ],
  "tradeoffs": [],
  "open_questions": [],
  "success_criteria": []
}
```

For `series`, `parts` contains at least two part proposals; its final size is determined by knowledge dependencies and evidence, not a universal target. `knowledge_units` may record each unit's question, claim IDs, dependencies, disposition, and destination. Never pad a topic to meet a preset duration or compress it to a preset scene count. The numeric values above illustrate field shape only; derive real budgets from the approved scope.

`audience_profile` is additive. It is required for newly created scopes and for substantive revisions to audience, promise, language, or terminology policy. `primary_groups` must be non-empty; `secondary_groups` may be empty and uses the same object shape. Group IDs must be unique across both arrays. `shared_baseline`, not the most expert group's knowledge, controls what the spoken copy may leave unexplained. `term_policy` is one of `plain_first`, `define_on_first_use`, or `expert_shorthand`; mixed or non-specialist audiences normally use `plain_first`. Preserve the concise `audience` field as a human-readable summary and compatibility field.

### `editorial/outline.json`

```json
{
  "schema_version": "1.0",
  "title": "Working title",
  "word_budget": {"min": 600, "target": 750, "max": 900},
  "hook_strategy": "Mechanism and curiosity gap, not final copied wording",
  "hook_brief": {
    "section_id": "section-stable-id-containing-the-hook",
    "opening_move": "contradiction | consequence | result_first | direct_question",
    "title_alignment": "How the opening immediately confirms the title's promise",
    "viewer_payoff": "What the viewer gains by continuing",
    "curiosity_gap": "The precise unresolved question",
    "target_seconds": 18,
    "max_seconds": 25,
    "max_words": 62,
    "delivery_wpm": 150,
    "body_handoff": "How the hook leads into the first proof, mechanism, or example",
    "avoid": ["long_setup", "undefined_jargon"]
  },
  "sections": [
    {
      "id": "section-stable-id",
      "title": "Section title",
      "purpose": "Narrative job",
      "summary": "What is explained",
      "claim_ids": [],
      "knowledge_unit_ids": [],
      "estimated_words": 120,
      "transition_in": "How this follows from the previous segment",
      "transition_out": "Question, consequence, or setup carried forward"
    }
  ],
  "deferred_items": []
}
```

Every substantive section must earn its place, link to evidence, and bridge to its neighbors. A list of topics without transitions is not an acceptable outline. This artifact approves narrative structure and evidence allocation; it deliberately does not contain the full Human Host voiceover. Complete spoken wording belongs to the script stage after the outline is approved.

`hook_brief` is additive and is required when creating a new outline or substantively revising its hook strategy. Its `section_id` must resolve to exactly one outline section. `target_seconds` cannot exceed `max_seconds`; `max_words` must not exceed the floor of `max_seconds * delivery_wpm / 60`, and may be stricter. Values are derived from format and audience rather than copied as universal defaults. `opening_move`, `viewer_payoff`, and `curiosity_gap` describe the editorial mechanism and must not smuggle final voiceover into the outline. Read [audience-writing-hook.md](audience-writing-hook.md) for the decision criteria.

### `script/final.json`

```json
{
  "schema_version": "1.0",
  "title": "Approved working title or final title",
  "target_duration_seconds": 300,
  "word_budget": {"min": 600, "target": 750, "max": 900},
  "hook": {
    "segment_id": "segment-containing-the-hook",
    "end_phrase": "Exact unique final phrase of the hook"
  },
  "segments": [
    {
      "id": "same stable segment ID used downstream",
      "heading": "Producer-facing segment heading",
      "text": "Only words intended for the Human Host to say",
      "claim_ids": [],
      "transition": "Continuity intent",
      "producer_notes": {
        "delivery": [],
        "pronunciation": [],
        "camera": [],
        "evidence": []
      }
    }
  ],
  "quality": {
    "fact_pass": {"status": "passed", "summary": "Every checkable claim maps to current evidence."},
    "continuity_pass": {"status": "passed", "summary": "Transitions and references remain coherent."},
    "originality_pass": {"status": "passed", "summary": "No source expression or distinctive sequence is reused."},
    "audience_fit_pass": {"status": "passed", "summary": "The copy respects the approved baseline and term policy."},
    "spoken_language_pass": {"status": "passed", "summary": "The host can read the copy naturally at the intended pace."},
    "hook_pass": {
      "status": "passed",
      "word_count": 44,
      "estimated_seconds": 17.6,
      "summary": "The extracted hook meets its approved payoff, language, and timing contract."
    }
  }
}
```

The numeric duration and budget above illustrate field shape only. The fact, continuity, and originality passes are always required. When a current scope has `audience_profile`, `audience_fit_pass` and `spoken_language_pass` are also required. When a current outline has `hook_brief`, the script `hook` locator and `hook_pass` are required. Each applicable quality pass requires `status: "passed"` and a concise, auditable `summary`; it must not contain hidden reasoning.

The hook locator never duplicates spoken text. Its `segment_id` must match the outline hook section and a script segment, and `end_phrase` must occur exactly once in that segment. The hook is the prefix from the start of that segment through `end_phrase`, inclusive. Its measured words and estimated time at `hook_brief.delivery_wpm` must agree with `hook_pass` and stay within `max_words` and `max_seconds`.

`script/final.json` is the canonical voiceover. Every segment `text` must be complete, natural speech that a Human Host can read aloud; `heading`, `claim_ids`, `transition`, and `producer_notes` are metadata and must not leak into the spoken copy. After writing or revising the canonical script, generate its review view before registration:

```powershell
python scripts/workflow.py materialize-script --run-dir <run-dir>
python scripts/workflow.py register --run-dir <run-dir> --stage script
```

The generated `script/teleprompter-script.md` is a required script-stage artifact and must contain only the title followed by spoken segment text in order. It must not contain segment headings, evidence annotations, camera directions, cue IDs, B-roll instructions, pronunciation notes, or implementation details. Script validation compares it byte-for-byte with the deterministic projection of `script/final.json`; never edit it independently. At the script approval gate, reproduce its complete spoken text in the conversation so the Human Host can review the actual read-aloud experience without opening the Markdown file. Keep the file link available as an optional audit and reuse artifact, not as a substitute for the conversational review.

After storyboard approval, packaging copies that exact approved projection to `creator-pack/teleprompter-clean.md`. It also derives `creator-pack/teleprompter-script.md`, a scene-divided recording view whose scene boundaries come from safe ordered shot-entry cues, and, when `project.karaoke_caption.enabled` is true, `creator-pack/karaoke_captions.json`. New or materially revised storyboards materialize `project.scene_navigation` as manual, sentence-start navigation with intra-sentence visual changes owned by the current component. Every distinct shot-entry cue therefore begins at segment character zero or immediately after terminal punctuation and has zero offset; a cue after a comma, colon, conjunction, preposition, or partial clause is not a Next boundary. Derivation begins at canonical text position zero. If the first entry cue occurs later, an initial Host-only scene owns the exact prefix. Each distinct safe cue in script order starts one subsequent scene, while coincident shots share that scene; when there are no shots, one Host-only scene owns all canonical text. Boundaries consume no characters, so concatenating scene text must reproduce the canonical characters exactly, including punctuation and whitespace. Derived views may add scene labels, caption chunks, timing metadata, and indicators outside the spoken text, but may not add, delete, normalize, or independently edit its characters.

The karaoke plan is a Human Host rehearsal aid before recorded audio exists. Estimate word timing from the configured reading rate and punctuation pauses; this timing is not authoritative sync. Keep the overlay hidden by default in generated previews while retaining the scene-divided teleprompter and, when configured, `karaoke_captions.json`. Hiding the overlay must not change scene projection, scene count, or manual Next behavior. Only when the creator explicitly requests a timed rehearsal should the capture stage show one bounded phrase group at a time, highlight exactly the currently spoken word, replace the previous group as speech advances, and hide the whole caption during punctuation/scene pauses and after the scene completes. Never draw `NEXT`, `END`, `HẾT`, a button, or transport status inside the capture stage. Karaoke never auto-advances: the finished visual remains in place until the Host uses `ArrowRight` or a review control, and `ArrowRight` on the final scene is a no-op. The configured `end_indicator` is retained only for the scene-divided teleprompter and package metadata, where `[BẤM NEXT]` tells the Host when to operate the external control. Karaoke belongs to the interactive desktop-capture preview/carousel and is not automatically burned into per-shot MP4 renders. Once recorded audio exists, forced-alignment timestamps against the exact canonical text are authoritative and replace estimated rehearsal timing. `creator-pack/producer-script.md` remains the separate production view keyed by the same segment and scene IDs; it may include headings, cue/shot notes, delivery, pronunciation, camera, and evidence notes without changing spoken prose. `creator-pack/quality_report.json` records derivation and validation status, including whether karaoke timing is estimated or forced-aligned.

When resuming a legacy run that already has `script/final.json` but lacks the script-gate teleprompter, move any legacy segment `voiceover` value into the canonical `text` field, run `materialize-script`, and re-register the script without otherwise rewriting its spoken text. Because the canonical script-stage artifact set changed, its aggregate hash changes and the creator must approve that new script revision before storyboard or packaging can continue.

The storyboard schema is defined in [visual-strategy.md](visual-strategy.md).

## Conversational presentation contract

Canonical files preserve exact state; the conversation is the creator's review surface. On completion or material revision of every phase, respond in the user's language and translate the current validated and registered artifact into clear prose, bullets, or a compact table. The response must expose all approval-significant content and be sufficient for the creator to understand the result, request changes, or grant the next approval without opening a file.

Never use a file path, link, SHA-256, raw JSON dump, or validation status as the whole phase response. Show those only after the human-readable review as audit metadata. Do not hide a consequential choice behind phrases such as "details are in the artifact." If the material is long, organize it into readable sections; length is not a reason to replace approval content with a link.

The conversational review is an ephemeral projection, not another canonical artifact or independently editable copy. Generate it from the registered artifact rather than memory. If it differs from the artifact, fix and re-register before asking for approval. Do not expose hidden chain-of-thought; provide concise evidence, assumptions, rationale, and tradeoffs only.

Present these contents by phase:

| Phase | Required conversational review |
|---|---|
| Research | Explain the source's core thesis, hook and retention mechanics, strongest useful evidence, important weaknesses or uncertainty, and what may be learned without copying the source. State the editorial implication for the proposed new content. The full transcript and ledger need not be pasted. |
| Scope | State the recommended format, working title, thesis, audience and shared knowledge baseline, viewer promise, target duration or word budget, what is included and deferred, all proposed parts when it is a series, and the important tradeoffs or open questions. End with the exact scope decision awaiting approval. |
| Outline | Show the hook mechanism, payoff, curiosity gap, and time or word budget, then every section in order with its narrative purpose, main evidence or claim, estimated allocation, and transition to the next section. State the overall arc, meaningful omissions, and the exact outline decision awaiting approval. Do not replace this with section IDs or raw JSON. |
| Script | Show the exact hook with measured words and estimated duration when the hook contract applies, followed by the complete teleprompter-ready spoken text in approved order. Also state total words and estimated duration. Keep production metadata outside the spoken copy; summarize applicable quality passes and only consequential producer notes. Ask for approval of this exact wording. An excerpt or summary is not sufficient for script approval. |
| Storyboard | Begin with an opening-coverage audit: enumerate the title, hook, pain or consequence, reversal or solution, payoff, and roadmap beats that actually exist, and show whether each is covered by a shot or intentionally left to the Host. State the title treatment and the ending decision explicitly. For a CTA, distinguish `visual_cta` from `spoken_cta`; a visual-only `Follow Dev Xịn` card must not be described as words the Host will say, while `spoken_cta.spoken_phrase` must locate words already present exactly once in the approved script. Then show each planned shot and each intentional Host-only interval in narrative order. For each manual scene, quote enough opening and closing spoken text to prove it is a complete sentence-level unit, state where the Host presses Next, and distinguish internal component-state cues from manual boundaries. For each shot, state the spoken cue, entry or exit behavior or planned duration, composition, communication intent, selected treatment and why, important alternatives, and any sourcing, rights, or privacy issue. When the composition is `support_top`, explicitly state that the real HTML/stage the Human Host records on a desktop is vertical `9:16` at `432x768`, with the illustration in the upper square `(x=0, y=0, width=432, height=432)` and a blank Host frame below it `(x=0, y=432, width=432, height=336)` where the Host places their own camera feed in the recording software. State that this is not a preview of a larger master and no later export step is assumed. Illustration pixels and ordinary overlays must not overflow into the Host frame; karaoke is hidden by default, and only an explicitly visible rehearsal overlay is an intentional exception around which the Host must be positioned. Make clear what the viewer sees and why; do not require the creator to decode `storyboard.json`. Ask for approval of this exact visual plan before building assets. |
| Asset build and package | Explain what was built or sourced, scene and asset coverage, what remains unrendered, the dominant theme and layouts, runtime and validation results, and any unresolved rights or production warning. Name and distinguish `teleprompter-clean.md`, the scene-divided `teleprompter-script.md`, `producer-script.md`, and `quality_report.json`. State that karaoke is hidden in the preview by default and that hiding it does not alter Teleprompter scenes or manual Next points. When karaoke metadata is enabled, also explain `karaoke_captions.json`, its estimated timing status, and how to opt into a visible rehearsal overlay; only then explain caption placement, phrase-group replacement, single active-word highlight, capture-stage hiding during pauses and after scene completion, and Host positioning around the overlay. State that `[BẤM NEXT]` remains a teleprompter/metadata cue and is never drawn inside the recording frame. Provide preview and output links as conveniences after the explanation. |

When revising an already presented phase, lead with what changed, what stayed the same, why, and which descendants are now stale, then present the complete current review content needed for approval. Bind the approval request to the newly registered SHA-256, but phrase the decision in human terms rather than asking the creator to approve or repeat a hash. A clear statement such as "approve this outline" applies to the exact most recently presented revision; the Agent passes its digest to `--expected-sha256` and verifies it has not changed.

## Gate invariants

The dependency chain is:

```text
research -> scope -> outline -> script -> storyboard -> package
```

- Research has no user approval gate, but all four canonical research artifacts must validate before scope can be registered.
- Scope, outline, script, and storyboard require explicit user approval of their current aggregate artifact hash.
- Scope registration requires current registered research. Outline, script, and storyboard registration require a current approval for scope, outline, and script respectively.
- Script registration requires both `script/final.json` and its generated `script/teleprompter-script.md`; the two must contain identical spoken text.
- An approval is valid only for the exact hash recorded. Editing a canonical artifact immediately makes that approval ineffective.
- Registering or changing an upstream stage makes every descendant stage and approval stale. Preserve the files for review, but do not treat them as current.
- The Agent cannot self-approve. A broad request such as "make the whole pack" authorizes work only through the next unapproved conversational gate.
- After creating and registering a gated artifact, show the complete natural-language phase review defined above, including the recommendation, tradeoffs, unresolved items, file path, and registered SHA-256. A path-only response, raw JSON dump, or request to open a file is not a valid gate presentation. If the current user message has not explicitly approved that exact artifact, end the turn.
- On the next turn, record approval with the presented digest as `--expected-sha256` before starting the dependent stage. If the user requests changes, revise and re-register the artifact; do not record approval unless they explicitly grant it.
- `package` requires a current storyboard approval and a successful full validation.

Never use terminal `input()`, a blocking stdin prompt, or a sleeping process to simulate a gate.

## Cache and invalidation

`research/research_cache.json` fingerprints the source URL or content hash, model, prompt version, schema version, research configuration, and upstream content hash. A cache hit is valid only when the complete fingerprint matches and all expected artifacts validate. API credentials should be required lazily only on a fingerprint miss.

Apply the narrowest correct invalidation:

- Source content, source locator, research model, research prompt/schema, or transcription configuration change: invalidate research and every descendant.
- Claim-ledger evidence change: invalidate scope and every descendant.
- Audience groups, shared need, baseline, desired takeaway, term policy, creator goal, thesis, coverage, or series decision change: invalidate scope and every descendant.
- Outline ordering, claims, transitions, or hook mechanism/payoff/gap/budget change: invalidate outline and every descendant.
- Spoken text, exact hook wording or locator, spoken CTA, claims, or producer intent change: invalidate script and every descendant.
- Opening visual coverage, title treatment, visual-only CTA or ending, cue, shot, modality, asset, ratio, theme, visual timing, or `project.karaoke_caption` change: invalidate storyboard and package, but retain approved editorial stages.
- A renderer implementation change invalidates affected rendered assets and package outputs; it does not invalidate the approved editorial meaning unless the storyboard contract changed.

Never use file existence alone as a cache key. Never overwrite an approved revision without making its approval stale.

## Required quality passes

Run the first three checks before every script registration. Run checks four and five whenever the current scope has `audience_profile`, and check six whenever the current outline has `hook_brief`:

1. **Fact pass**: every checkable claim resolves to a current claim ID; disputed or unverified claims are qualified; no citation implies more than its evidence supports.
2. **Continuity pass**: transitions carry setup, causality, contrast, or consequence across segments; pronouns and references resolve; repeated setup and bullet-like restarts are removed. When revising a script that already has a storyboard, the intended manual scenes also read as one continuous performance: each opening either carries an audible relationship from the prior scene or makes a deliberate, justified reset.
3. **Originality pass**: compare against the source transcript/article for copied phrasing, examples, distinctive sequencing, and visual motifs. Retain facts and abstract communication techniques, not source expression. Rewrite flagged overlap and record only a concise result, not hidden reasoning.
4. **Audience-fit pass**: compare the copy with the approved `shared_baseline`, `do_not_assume`, `avoid_terms`, and `term_policy`; explain or replace any unsupported assumption without flattening the causal argument.
5. **Spoken-language pass**: read for one-pass comprehension, audible transitions, resolved references, manageable breath groups, and natural pronunciation at the intended pace. When the creator supplied a voice sample, verify its reusable traits—rather than its exact catchphrases—are reflected with an audience-appropriate slang and metaphor budget.
6. **Hook pass**: extract the canonical hook through its locator, verify title alignment, payoff, curiosity gap, audience-safe terminology, body handoff, originality, word count, and estimated duration against the approved brief. Distinguish subjective enthusiasm from factual claims; ground memorable metaphors in the real capability and place any material operating caveat in the hook or immediately after it.

Validation must fail on dangling claim IDs, missing transitions, mismatched segment IDs, stale approvals, unresolved cue references, or any clean, scene-divided, producer, or karaoke projection whose concatenated spoken characters differ from `script/final.json`. Scene boundaries must deterministically match canonical start and ordered distinct shot-entry cues, including the Host-only prefix and no-shot cases.

## Additive editorial compatibility

These audience and hook contracts extend schema version `1.0`; they do not rewrite previously registered meaning. A legacy registered or approved scope may lack `audience_profile`, a legacy outline may lack `hook_brief`, and its script may therefore lack the hook locator and conditional passes. Continue to validate the legacy artifact under the requirements that applied when it was registered, and do not make its approval stale merely because these additive fields now exist.

Whenever an Agent newly creates an artifact, substantively revises the corresponding audience or hook decision, or explicitly migrates a legacy run, write the additive fields and apply their conditional validation. Once an upstream additive field is present, its downstream locator and quality requirements are mandatory. Migration changes the registered artifact hash and follows the normal approval and invalidation rules.
