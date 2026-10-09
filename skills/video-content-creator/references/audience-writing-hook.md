# Audience, Spoken Writing, and Hook Strategy

Read this reference before proposing or revising scope, outline, or spoken copy. It turns audience and hook choices into reviewable editorial contracts without imposing one universal tone or hook length.

## Define an audience profile at scope

An audience is not merely a list of titles or demographics. Define the situation in which each group watches, what it needs from the video, and what knowledge the script may safely assume. For new or substantively revised scope work, use the additive `audience_profile` contract in `artifact-contract.md`.

- `primary_groups` contains at least one group. Each group records a stable `id`, a human-readable `label`, its `need`, and an `assumed_knowledge` list.
- `secondary_groups` uses the same shape and may be empty. Do not let a secondary group quietly raise the knowledge floor for everyone.
- `shared_need` is the problem or decision that makes the groups belong in one video.
- `shared_baseline` is the lowest common knowledge the script may use without explanation.
- `desired_takeaway` states what the viewer should understand, decide, or do afterward.
- `do_not_assume` lists concepts, organizational rituals, acronyms, and prior experiences that need explanation.
- `avoid_terms` lists labels that should be replaced unless a precise use is justified.
- `language`, `tone`, and `term_policy` control delivery rather than factual depth. Choose `term_policy` from `plain_first`, `define_on_first_use`, or `expert_shorthand`; use `plain_first` for mixed or non-specialist audiences.

When audiences span levels or roles, bridge them instead of alternating between separate mini-lectures. Lead with the shared consequence, explain the mechanism in ordinary language, then add the technical label or nuance only if it helps later reasoning. For example, executives and new developers can share a delivery problem even though they enter it from different roles.

Do not equate plain language with shallow content. Preserve the causal chain, evidence, caveats, and tradeoffs; remove only the unnecessary decoding cost.

## Write for the ear

The teleprompter is speech, not a compressed article. Apply these rules to every spoken segment:

1. Give each sentence one main job. Prefer a concrete actor and action over stacked abstract nouns.
2. Make causal, contrast, and consequence links audible. Remove bullet-like restarts that make each sentence sound unrelated to the previous one.
3. Put the plain-language concept before its formal or English label. Add the label only if the host will reuse it or the viewer benefits from learning it.
4. Expand or explain an acronym on first use unless the audience profile explicitly allows it unexplained.
5. Prefer an example that can be understood from the sentence itself; do not require knowledge of an internal ceremony, tool, or company process.
6. Read the copy aloud at the intended pace. Rewrite breathless sentences, ambiguous references, tongue-twisting clusters, and phrases that require rereading.

For a mixed non-specialist and technical audience, a useful order is:

```text
recognizable consequence -> plain mechanism -> optional technical detail -> practical implication
```

Run an explicit term audit before the script gate. Compare the spoken copy with `shared_baseline`, `do_not_assume`, and `avoid_terms`; do not rely on the writer's familiarity with the subject.

## Match the creator's speaking voice

An explicit wording sample from the creator is the strongest evidence for how the Human Host should sound. Treat it as a style specimen, not text to repeat. Extract the reusable traits that matter for the current project:

- the relationship created by pronouns and address, such as `mình`, `bạn`, or a light `anh em`;
- energy and emotional temperature, from measured and analytical to youthful and excited;
- stance, such as sharing an observation, explaining a mechanism, recommending a practice, or issuing a warning;
- colloquial density and where slang is allowed to carry emphasis;
- the kind of memorable comparison or metaphor the creator naturally uses;
- phrases and tones the creator explicitly dislikes.

Record stable project direction in `audience_profile.tone` when scope is being created or substantively revised. Put script-specific performance guidance in `segments[].producer_notes.delivery`; it must not leak into the spoken projection. Do not invent first-hand experience merely to sound personal. A Host may say that an idea is useful, surprising, or worth sharing as an editorial judgment, but may claim to have tried it only when the creator supplied that experience.

For a Dev Xịn video, when the creator has not supplied a different direction, use a youthful, practical, share-first Vietnamese register: the Host normally speaks as `mình`, explains to `bạn`, and may use `anh em` once as a light audience address. A colloquial verdict such as “ngon” may create recognition in the hook, but it is neither required nor a substitute for the concrete payoff. Keep slang sparse enough that executives, non-specialists, and new developers can still understand the sentence on one listen. Explicit creator feedback always wins over this default.

“Share-first” means the viewer receives an observation, decision rule, or practice worth retelling. It does not mean inserting a generic request to share the video. One vivid metaphor can compress a complex system—for example, comparing parallel projects with a team of assistants—but the next beat must ground that metaphor in the real capability and limits. Energy may heighten relevance; it must not inflate causality, certainty, availability, or scale.

## Make scene-to-scene continuity audible

When a script already has, or is about to receive, manual storyboard scenes, read the intended scene units consecutively. A viewer should hear why the next scene follows even with the visuals hidden. Use the semantic relationship that actually exists:

- consequence: `nhờ vậy`, `vì vậy`;
- sequence: `sau đó`, `ghép xong rồi`;
- contrast or another side of the system: `còn ở giữa`, `ở đầu bên kia`;
- condition or audience fork: `nếu...`, `còn nếu...`;
- plain-language grounding: `nói đơn giản`;
- recap: `tóm lại`.

These are relationship classes, not phrases that must be inserted mechanically. Do not make every scene start with a connector, repeat the same connector, or use one that misstates the logic. A deliberate reset is valid when the subject truly changes. Keep every manual boundary at a complete sentence start; put an intra-sentence change in the current visual component instead of asking the Host to press Next mid-thought.

### Teleprompter delivery rules and scene flow

When the teleprompter text is split across scenes where the Host presses `[NEXT]`, avoid the common traps that make reading sound disjointed or repetitive:

1. **Place topic triggers at the beginning of the new scene, never the end of the old scene:**
   - *Trap:* Asking "Which tool should you choose today?" at the end of Scene 9 while the screen still displays the previous GitHub competitor radar, then pressing Next into Scene 10 and restarting the thought.
   - *Rule:* The topic-shift question or trigger belongs at the exact start of the new scene. When the Host presses Next, the new visual appears immediately and the Host's opening words explain that visual directly.
2. **Eliminate awkward scene restarts (No redundant framing):**
   - When moving to the next scene, do not re-introduce or summarize what was just said. Dive directly into the new evidence or beat.
3. **Master 3 pedagogical reasoning patterns for crisp delivery:**
   - **Diễn giải (Deductive / Principle to specifics):** State the thesis/architecture upfront, then unpack each element with short, parallel phrases (e.g., Tasks $\rightarrow$ Schedules $\rightarrow$ Skills). The visual component highlights each element as speech progresses without forcing a manual scene split.
   - **Liệt kê (Categorical Enumeration with ordered chaining):** Group options by clear criteria (e.g., ecosystem fit & cost). Instead of repeating conditional clauses (*"Nếu bạn... Còn nếu bạn... Cuối cùng nếu bạn..."*), use punchy ordered links: *"Một là... Hai là... Ba là..."*. This gives the Host an energetic cadence and gives the viewer an instantly scannable taxonomy.
   - **Quy nạp (Inductive / Observation to rule):** Move from recognizable personal frustration or real-world operational risk to the governing takeaway (e.g., from typing repetitive prompts every morning to realizing the prompt fatigue paradox; from destructive unintended actions to the strict Human-in-the-Loop Authority Boundary).
4. **Short sentence budget:** Keep spoken sentences between 10 and 20 words. Avoid multi-clause compound sentences that exhaust breath support on the teleprompter.

## Build an adaptive hook

The hook is the shortest honest path from the title's promise to a reason to keep watching. It is not a mandatory anecdote, miniature introduction, or summary of the whole video.

Choose its budget from the approved format, delivery pace, audience, and complexity. If the scope supplies no better constraint, use these as starting points rather than universal limits:

- up to 90 seconds total: roughly 3–8 seconds;
- 2–10 minutes total: target roughly 10–20 seconds and normally cap at 25 seconds;
- longer or evidence-heavy formats: allow more time only when the extra setup is necessary to understand the payoff.

Record the decision in `outline.hook_brief`. Compute its word ceiling from delivery pace:

```text
max_words = floor(max_seconds * delivery_wpm / 60)
estimated_seconds = actual_hook_words * 60 / delivery_wpm
```

Do not hide a generous word allowance behind an unrealistically high delivery rate. Rehearsed timing may refine the estimate, but the registered brief must retain a reasonable planning rate.

### Calibrate a youthful, creator-native hook

When the approved voice is youthful and share-first, a useful hook shape is:

```text
brief colloquial reaction -> recognizable pain -> concrete capability -> memorable comparison -> body handoff
```

This is an option, not a universal formula. A reaction such as “thật sự ngon” works only when the same or next sentence names what the viewer can actually do. A team, copilot, or command-center metaphor must remain visibly a comparison and may not create a stronger factual claim than the evidence supports. If an operational limit would overload the hook, keep the hook honest and place the material caveat immediately after it, before the tutorial or recommendation depends on that limit. If the slang, metaphor, and caveat push the hook past its approved budget, keep the concrete payoff and cut the decoration first.

### Hook acceptance criteria

A hook passes only when all of these are true:

- The first sentence establishes a relevant problem, contradiction, consequence, result, or direct question.
- By the locator's end, the viewer understands the payoff and the specific gap the video will resolve.
- It carries one central tension. A number or factual result supports that tension rather than starting a second argument.
- It aligns with the title without merely repeating it.
- It stays accurate without front-loading a chain of disclaimers. If a material caveat cannot fit cleanly, keep the hook neutral and give the caveat immediately afterward.
- When a creator voice sample exists, it matches the sample's reusable traits without turning one phrase into recurring boilerplate.
- Any slang or superlative reads as a bounded creator reaction; every adjacent factual clause remains supported and avoids unconditional claims such as “everywhere” or “24/7” when host, rollout, permission, or connectivity conditions matter.
- It contains no unexplained term prohibited by the audience profile.
- It avoids greetings, channel introductions, credentials, broad history, long hypothetical setup, generic hype, and source-distinctive phrasing unless the approved strategy specifically justifies one.
- Its final line hands the viewer directly to the first proof, mechanism, or example in the body.

`hook_brief.opening_move` describes the mechanism, not final wording. Examples include a contradiction, consequence, result-first statement, or direct question. `viewer_payoff` says what the viewer gains; `curiosity_gap` says what remains unresolved. They must be related but not duplicates.

Before registering spoken copy, run a short creator-voice pass in addition to the normal quality checks:

- consecutive beats sound connected when read aloud without visuals;
- colloquial markers are purposeful rather than filler or a repeated channel catchphrase;
- the viewer can retell at least one useful idea or comparison without mistaking it for a literal guarantee;
- the concrete capability and material limitation remain distinguishable from the Host's enthusiasm;
- the wording still respects the approved audience baseline and measured hook budget.

## Locate and measure the final hook

The canonical hook text remains inside the first relevant script segment; do not maintain another copy. `script.hook.segment_id` identifies that segment, and `end_phrase` is an exact, unique phrase ending the hook. Count from the start of that segment through the end phrase, inclusive. The phrase must not occur twice in the segment.

At the script gate, show:

- the exact extracted hook;
- its actual word count;
- estimated seconds at the registered `delivery_wpm`;
- whether it meets `target_seconds`, `max_seconds`, and `max_words`;
- the complete generated teleprompter inline in the gate response, followed by its optional file path and registered script digest.

Approval of the hook excerpt alone is feedback, not approval of the script artifact. Only explicit approval of the current registered script digest opens the storyboard stage.

## Gate and invalidation behavior

- Approve audience intent and baseline at the scope gate. Changing groups, shared need, baseline, desired takeaway, or term policy invalidates scope and every descendant.
- Approve the hook mechanism, payoff, curiosity gap, and budget at the outline gate. Changing those choices invalidates outline and every descendant.
- Approve exact hook wording and timing with the complete script. Trimming or rewriting the hook without changing its approved strategy invalidates script and its descendants, but does not require a new outline approval.
- If requested wording changes alter the title alignment, audience promise, central tension, or body handoff, revise the outline rather than disguising a structural change as copyediting.

Use the additive and conditional legacy rules in `artifact-contract.md`. Do not retroactively invalidate a registered legacy artifact merely because it predates these fields.
