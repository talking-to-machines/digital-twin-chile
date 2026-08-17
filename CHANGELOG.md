# Prompt changelog

Tracks substantive changes to `prompts/prompt_template_arm_{a,b,c,d}.py` and
`prompts/prompt_template.py`, from the original pipeline version to the
current one. Per `CLAUDE.md`, prompt changes must be explicitly documented —
this file is that record, going forward, instead of change-log-style
comments embedded in the prompt files themselves. Existing in-file comment
blocks describing past changes are left as-is (removing them is a separate
cleanup); new changes should be logged here instead of added as new
comments there.

## Unreleased / planned

- Follow-up (not done here, tracked separately): fix the Dropbox-side QA
  script's (`scripts/analysis/06_pilot_comparison_smoke_test_qa_round2_matias.Rmd`)
  B/C Stage-1 divergence check and `code_specs` regexes (widen PINC to
  PINC1-18, add `Vsv` and `Vba` rows) per Ray's 2026-08-02 memo. Out of scope
  for this repo/commit by instruction.
- **Municipal electoral-data retrieval: not wired into the driver (guide
  §9.4).** `arm_b_municipal_web_instruction` / `arm_c_municipal_web_instruction`
  (`prompts/prompt_template_arm_b.py`) already implement the intended
  *input*-side instruction correctly: if Stage 1 evidence supports a comuna at
  `confidence: medium` or higher, retrieve that comuna's 2021 electoral
  results via web search and use them as additional context for the
  individual-level vote/turnout predictions — text is explicitly scoped
  "solo con búsqueda web habilitada" (information condition 4 only). Nothing
  in `src/digital_twin_chile_x.py` currently appends this instruction to the
  Stage 2 system prompt when `enable_web_search=True`, so it has no effect at
  runtime. To do, after the architecture pilot selects a production
  architecture: wire this into the driver for that architecture, gated on
  `enable_web_search`. Until wired, no arm retrieves or uses actual electoral
  results as a prediction input. (This supersedes the six now-removed
  `*_COMUNAL` output questions, which used the same guide instruction as a
  source for extra output items rather than as prediction context — see the
  2026-07-27 revision note in `prompt_template_arm_b.py` and QA report 06.)

## 2026-08-15 (CANNOT_INFER scope — safety-valve review, Step 2)

Per `admin/memos/Memo_SafetyValve_Review_2026.08.12.docx` §4 (Ray, 12 Aug), the
documented template review triggered when the architecture pilot's registered
safety valve fired on CANNOT_INFER rates (A 80.1%, B 60.5%, C 59.5%, all above
the 40% threshold). The memo's §2 split the inflation into (a) sample
composition — citing a 5 Aug audit figure of "52% of accounts have ZERO posts
at the Dec-13 cutoff" — and (b) guardrail conservatism, and called (a) "most of
the story." Step 1 of the review (`scripts/analysis/06d_architecture_pilot_ci_diagnosis.Rmd`
in the parent repo, rendered 2026-08-13) inverts that: the 52% figure came from
restricting one input scrape in isolation, and the pilot's actual corpus
(`proc/build/06_append_random_users_tweets.csv`) has **3.1% zero-post accounts
(4/128)**. Restricting the CI rate to accounts with ≥1 in-window post — the
memo's own §5 realignment — moves every architecture by under 2pp. So cause (b)
is the dominant driver and this prompt change has to carry the correction. CI
concentrates in a recurring set of question types across all three
architectures (household/personal income, generalized trust, marital status,
campaign attention, candidate favorability), largely independent of account
richness — items a profile rarely answers directly, which a strict
CI-on-no-direct-statement reading refuses near-universally.

- **Added `REGLA SOBRE CANNOT_INFER` to Arms A, B and C**, byte-identical in all
  three (verified programmatically) so the arm contrast stays clean — Ray's §4
  draft text verbatim: CI only when the profile contains NO relevant signal;
  where a weak or indirect signal exists, commit to the most plausible answer
  and express the uncertainty through the speculation score and, for the primary
  outcomes, the probability distribution. Arm A needs two copies because its two
  calls share no rule text: `x_digital_twin_entity_geographic_user_prompt` (after
  numbered item 6) and `x_digital_twin_voting_preference_wo_voting_results_user_prompt`
  (after `REGLA SOBRE INTENCIÓN DE VOTO`). Arm B gets one copy in
  `arm_b_stage2_system_prompt`, same position. **Arm C needs no separate edit** —
  `arm_c_stage2_system_prompt` is `arm_b_stage2_system_prompt` plus the ordering
  block, so it inherits by construction.
- **Amended `REGLAS ESTRICTAS` items 3–5 in `arm_b_stage2_system_prompt`** — as
  written they were the operative CI trigger for B/C ("úsela cuando no haya
  evidencia de nivel medium o superior" / "no asigne CANNOT_INFER si hay
  evidencia de nivel medium o superior") and directly contradicted the new rule,
  which would have shipped a prompt arguing with itself and made the re-run
  uninterpretable. Item 3 now routes `confidence: 'low'` to a committed answer
  with high speculation; item 4 restricts CI to `confidence: 'none'` with no
  relevant signal; item 5 forbids CI wherever any signal exists, however weak.
  Item 3's old tail ("en lugar de la categoría modal") was dropped only because
  the `REGLA DE INFERENCIA CONSERVADORA` block immediately below already forbids
  modal-category defaulting — that block, including the `>70` speculation floor,
  is unchanged, as are the `NIVELES DE ESPECULACIÓN` bands and the NA-vs-CI
  distinction for REGION/COMUNA.
- **Added the NA-vs-CI carve-out to Arm A's Call 1 only** — one extra sentence on
  the end of the rule restating that "NA" still means not resident in Chile and
  "CI" means resident but no signal on region/comuna. Call 1 previously had no
  general CI rule at all, and its REGIÓN/COMUNA question stems are the only place
  that distinction lives for Arm A. Arms B/C already carry it in
  `DISTINCIÓN OBLIGATORIA ENTRE TIPOS DE PREGUNTAS`, so they need nothing extra.
- **Arm D deliberately untouched** — per memo §6 it re-runs unchanged as the
  benchmark. Stage 1 of Arms B/C also untouched: it is evidence-only, forbidden
  from predicting, and emits `confidence`, never CI.
- **Corrected the schema count in `REGLAS ESTRICTAS` item 8 from 34 to 35 claves**
  — *not requested by the memo.* `_STAGE2_QUESTIONS` has been 35 since the
  ballotage batch added `VOTO_BALLOTAGE_2021` and bumped the assert 34→35, but
  the prose count was never updated, so the prompt handed the model a 35-key
  schema while instructing it there were 34. Likely crossed with
  `CANONICAL_OPTIONS` (34, keyed by `opt_key`, excludes COMUNA). Flagged here
  separately because it is a plausible contributor to the criterion-(i)
  parseable-output shortfall the re-run has to clear (A 98.4%, B 97.2%, C 97.2%
  against a 99% bar).
- **Passed `canonical_labels` to Arm A's two extractor calls** (memo §4's first
  pipeline recommendation). `extract_llm_responses` already accepted the
  parameter and Arm D already used it; Arm A passed nothing. Added
  `ARM_A_GEO_QUESTION_LABELS` (4) and `ARM_A_VOTE_QUESTION_LABELS` (31) to
  `prompt_template_arm_b.py`, derived from the existing `_STAGE2_QUESTIONS`
  (whose entries already carry Arm A's verbatim title and a geo/vote tag) so no
  second source of truth is introduced. Threaded through `arm_cfg` as
  `entity_labels`/`voting_labels` rather than hardcoded into the two interview
  functions — those functions are shared with the `baseline` arm, whose prompt
  asks "OCUPACIÓN ACUTAL" (sic); normalising that against Arm A's spelling would
  silently break the baseline-vs-A comparison. Defaults `None`, so every other
  arm is unaffected.
- **Added key-format validation to Arms B/C structured output** (memo §4's second
  pipeline recommendation). `extract_json_predictions` used whatever question key
  the model returned as the column prefix, so a typo like `EDDAD` produced a
  stray `"EDDAD - symbol"` column while the canonical column stayed empty — with
  no warning, and no `coalesce_columns_by_regex` pass downstream to catch it.
  Now: per-row `warnings.warn` naming the offending keys, plus a new
  `validate_stage2_prediction_keys()` (`src/utils.py`) that raises `ValueError`
  with the bad keys and affected account IDs. **The raise fires after
  `stage2_df.to_csv()`, not inside the `.apply()`** — by that point a four-arm
  128-account run has already been paid for, and the raw output has to survive
  for diagnosis. Missing canonical keys warn rather than raise. Validated against
  the 35 `json_key`s in the new `STAGE2_JSON_KEYS`, deliberately not against
  `CANONICAL_OPTIONS` (different keyspace, 34 entries, excludes COMUNA).
- Mechanical note: the new rule contains no braces, so it is safe in both the
  `.format()`-ed Stage 2 system prompt (where the `probability_distribution`
  example must stay `{{...}}`) and Arm A's verbatim user prompts. Insertions sit
  in the rules preamble, not inside a question block, so `_extract_arm_a_block`'s
  title-keyed parsing of Arm A's prompt strings is unaffected.
- Verified: all four arm modules import cleanly with every count invariant
  holding (`_STAGE2_QUESTIONS` 35, `CANONICAL_OPTIONS` 34,
  `ARM_D_QUESTION_LABELS` 35, `STAGE2_JSON_KEYS` 35 unique, nominal/ordinal
  partition plus COMUNA still covering `SHUFFLEABLE_KEYS`); the rule line is
  byte-identical across Arm A Call 2 / B / C and appears exactly once per prompt;
  it is absent from both Stage 1 prompts and from Arm D; "medium o superior" is
  gone from B and C; the `>70` floor, `REGLA DE INFERENCIA CONSERVADORA` and the
  NA-vs-CI block are intact; `construct_system_prompt` renders B and C without a
  brace error and the rule survives into the delivered prompt; `extract_llm_responses`
  normalises a lowercase title with labels, leaves it alone without them, and
  leaves baseline's "ACUTAL" untouched; `extract_json_predictions` is silent and
  35-column on clean JSON, warns on `EDDAD`, and the validator raises naming the
  account. 43/43 checks. **Not yet verified against a fresh smoke test or a
  delivered-prompt check on real run output** — the delivered-prompt grep
  (mirroring `06c_architecture_pilot_report.Rmd`'s `ref-date-check`) must cover
  the *user*-prompt columns too, since Arm A's copies live in user prompts, not
  the system prompt.

## 2026-08-10 (reference-date instruction)

Per Ray's Slack message (`#digital-twins`, 2026-08-08 01:53), responding to Matias's
2026-08-05 audit memo (`admin/memos/Memo_Matias_AuditFindings_2026.08.05.docx`),
which found the reference-date instruction from the registration's "Post-Election
Information Environment and Leakage Controls" section (`paper/main8_4_final.tex`,
§Procedures) had never actually been implemented in any prompt. Ray's spec: one
identical context-block passage in ALL architectures (A-D) and ALL arms, both
stages for B/C — uniformity matters because arm contrasts must differ only in
the 2×2 toggles; the web arms (2 and 4) additionally get one extra sentence
riding the web-search toggle (no retrieved content postdating December 13,
2025).

- **Added `REFERENCE_DATE_SENTENCE` and `WEB_SEARCH_CUTOFF_SENTENCE`** as the
  single source of truth for both sentences (`config/digital_twin_config.py`),
  so all arms stay textually identical rather than risking drift from
  copy-pasting the string by hand.
- **`REFERENCE_DATE_SENTENCE` inserted into every arm's system prompt(s)**:
  Arm A (`prompt_template_arm_a.py`, `base_digital_twin_system_prompt`,
  inserted after the profile block, before `Instrucciones:` — covers both of
  Arm A's calls, since Call 2 inherits Call 1's system prompt via replayed
  history rather than constructing its own); Arm B
  (`prompt_template_arm_b.py`, `arm_b_stage1_system_prompt` and
  `arm_b_stage2_system_prompt`, inserted after each stage's opening sentence) —
  Arm C inherits automatically via its existing aliasing/inheritance of Arm
  B's prompts, no separate edit needed; Arm D (`prompt_template_arm_d.py`,
  `arm_d_system_prompt`, inserted after the speculation-scoring paragraph,
  before the vote-intention paragraph). Baseline (`prompt_template.py`) was
  deliberately left untouched — it is not one of the architecture-pilot's
  A-D candidates, per instruction.
- **`WEB_SEARCH_CUTOFF_SENTENCE` wired centrally, not per arm file**: added
  `enable_web_search` parameter to `construct_system_prompt()`
  (`src/utils.py`), which appends the sentence after the existing
  `.format(**profile_args)` call when `enable_web_search=True`. This is the
  single chokepoint `perform_profile_interview()` already calls for every
  arm and every stage, so the sentence applies uniformly to arms 2/4 across
  all four architectures (including both B/C stages and Arm A's
  history-inherited Call 2) without any per-arm conditional logic.
  `enable_web_search` was already threaded into every
  `perform_profile_interview()` call site in `src/digital_twin_chile_x.py`;
  only the one call to `construct_system_prompt()` needed the new argument
  added.
- Mechanical note: Arm B's Stage 2 system prompt contains an escaped-brace
  JSON example (`probability_distribution`) that must survive
  `construct_system_prompt()`'s `.format()` call — inserted
  `REFERENCE_DATE_SENTENCE` there via plain string concatenation rather than
  an f-string, since an f-string would collapse the `{{`/`}}` escapes
  immediately at module-load time and break the later `.format()` call. Arm
  A, Arm B Stage 1, and Arm D contain no such escapes, so those three use
  f-string interpolation instead.
- Verified: all four arm modules import cleanly with
  `REFERENCE_DATE_SENTENCE` present in each (`prompt_template.py` confirmed
  absent, as intended); `construct_system_prompt()` confirmed to append
  `WEB_SEARCH_CUTOFF_SENTENCE` only when `enable_web_search=True`, and the
  Stage 2 `probability_distribution` JSON example confirmed intact after
  `.format()`. Not yet verified against a fresh smoke test — that is the
  "verify in delivered prompts" step of Ray's sequence, to run before the
  pilot launches.

## 2026-08-05 (vote-intention stated-preference instruction)

Per Ray's memo `admin/memos/Memo_PilotLaunch_Instructions_2026.08.04_v2.docx`
§2(ii), one of the two settled instructions required before pilot launch.
Motivated by a specific smoke-test finding, not a general concern: on the
runoff-vote question (`INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA`), Arm B and
Arm C disagreed for 3 of 5 profiles — checked and ruled out as Arm C's
option-shuffle noise (Kast's list position differed across the three
accounts, so a shuffle artifact would not produce the same disagreement
direction every time). The actual split was a reasoning-path divergence: Arm
B anchored on `demographics.location` ("no vive en Chile → no votaría"), Arm
C anchored on `political.ideology` ("señal de derecha fuerte → votaría
Kast si votara") — same three accounts, same direction, every time. Both
readings are individually defensible for someone whose eligibility to vote
in Chile is itself uncertain, but they produce opposite predictions for the
same underlying evidence, so the architectures need to agree on which one is
correct.

Ray's resolution: vote-intention questions ask what the respondent would
answer on the survey, i.e. their political preference — not whether they
are eligible to vote. A residence or eligibility doubt must not be
converted into an abstention answer ("no votó"/"no votaría"); the model
should answer from the political-preference evidence as if the person were
voting, and reserve CANNOT_INFER for profiles with no political signal at
all. This is Arm C's reasoning path, not Arm B's — Arm B's
location-anchored abstention default is the one being corrected.

- **Added a `REGLA SOBRE INTENCIÓN DE VOTO` block to all four arms**, same
  wording throughout (adapted to each arm's native format): Arm A
  (`prompt_template_arm_a.py`, `x_digital_twin_voting_preference_wo_voting_results_user_prompt`,
  inserted after the existing `REGLA DE INFERENCIA CONSERVADORA` block); Arm
  B (`prompt_template_arm_b.py`, `arm_b_stage2_system_prompt`, inserted
  after the `DISTINCIÓN OBLIGATORIA ENTRE TIPOS DE PREGUNTAS` section) —
  Arm C inherits automatically via `arm_c_stage2_system_prompt =
  arm_b_stage2_system_prompt + ...`, no separate edit needed; Arm D
  (`prompt_template_arm_d.py`, `arm_d_system_prompt`, inserted after the
  existing CI-escape sentence).
- **Deliberately does not name the registration's Q7.5–7.7 exclusion or any
  other survey-internal mechanism** — earlier draft did, but that's
  pipeline/registration bookkeeping the model has no way to act on and no
  need to know about; the instruction only needs to state the behavior
  (answer the political preference, don't infer abstention from residence
  doubt), not the reason it's safe to do so downstream.
- Verified by import: all four arm modules import cleanly with the new text
  present in each; `CANONICAL_OPTIONS` (34), `ARM_D_QUESTION_LABELS` (35),
  and Arm C's `NOMINAL_KEYS`/`ORDINAL_KEYS` partition are all unchanged.
  Not yet verified against a fresh smoke test — this is a prompt-text change
  only, no schema/count change, so the existing invariants were the
  relevant check.

## 2026-08-04 (post smoke_test_4 Arm B review)

Found by inspecting the Arm B `smoke_test_4` output columns directly against
Lucas's summary-fields decision (Ray's 2026-08-02 memo) — the decision was
recorded as "Done" in the PreReg tracker but never actually landed in the
prompt.

- **Actually dropped `overall_confidence` (Stage 2) and
  `overall_inference_quality` (Stage 1) from `prompt_template_arm_b.py`'s
  JSON schemas** — both were still present in the schema text despite the
  memo's decision, so the model kept emitting them (`_overall_confidence`
  visible in `smoke_test_4`'s output). Kept `cannot_infer_fields`,
  `high_speculation_fields` (Stage 2), and `estimated_political_tweet_pct`
  (Stage 1), per the same decision.
- **Stopped flattening `subject_id` into its own `_subject_id` CSV column**
  (`src/utils.py::extract_json_predictions`) — it's a pure duplicate of the
  `account_id` column already on every row (Stage 1's `subject_id` is
  hardcoded to `{account_id}`, not model-generated). Left `subject_id` in
  the JSON schema itself (still useful as self-describing metadata inside
  the raw JSON blob); only removed it from the meta-key flattening tuple,
  same treatment as `overall_confidence`.
- **Added instructions for the three summary fields that were never
  explained to the model**, only ever shown as bare schema placeholders:
  `cannot_infer_fields` (list questions where `symbol == "CI"`),
  `high_speculation_fields` (list questions where `speculation > 70`,
  referencing the existing REGLA DE INFERENCIA CONSERVADORA threshold
  already in the prompt), and `estimated_political_tweet_pct` (defined what
  counts as a "political" tweet and over what base — previously just
  `"<porcentaje estimado>"` with no definition at all).
- **Made `most_important_issue`'s Stage 1 evidence field state the
  underlying question** ("el problema más importante que enfrenta el país
  (Chile) hoy en día") instead of the vaguer "tema prioritario", which could
  read as personal interests rather than Q5.1's specific framing.

## 2026-08-02 (post round-3 smoke-test QA)

Three fixes implemented from
`scripts/analysis/06_pilot_comparison_smoke_test_qa_round3_matias.Rmd`'s
Recommendations, against the pipeline state that round 3's smoke test
(`data/pilot_comparison/smoke_test_3/`) actually ran on. Not yet re-verified
by a fresh smoke test.

- **Fixed `ci_bad_category`'s root cause: Arm B/C's Stage 2 output sometimes
  wrote `category: "CI"` instead of `category: "CANNOT_INFER"` for a `CI`
  symbol.** Root cause, confirmed by reading the actual schema text rather
  than assumed: every one of the ~30 entries in `arm_b_stage2_system_prompt`'s
  JSON schema documents `category` as a bare `"<texto>"` placeholder, with no
  reminder that it should read `"CANNOT_INFER"` specifically when `symbol` is
  `"CI"` — even though the correct pairing already exists earlier in the same
  prompt (`"CI) CANNOT_INFER"` in every question's option list, same as Arm
  A). Arm A doesn't have this problem because its bold-block format keeps
  that pairing visible immediately next to where each answer gets written;
  Arm B/C's single end-of-prompt JSON object doesn't. Fixed in two places
  (`prompt_template_arm_b.py`, inherited by Arm C via
  `arm_c_stage2_system_prompt = arm_b_stage2_system_prompt + ...` and
  `fill_stage2_user_prompt()`): added `- Cuando symbol sea "CI", category
  debe ser exactamente "CANNOT_INFER" -- nunca repita "CI" en el campo
  category.` to the `REGLA DE FORMATO CRÍTICA` section (with a `"CI"`/
  `"CANNOT_INFER"` example alongside the existing `PP12` example), and a
  short reminder immediately before the JSON schema itself in the user
  prompt, since that's the text actually adjacent to where the model fills
  in the field. Verified by import: `prompts.prompt_template_arm_c`'s
  `arm_c_stage2_system_prompt` inherits both changes automatically, no
  separate edit needed there.

- **Unified `probabilities`/`probability_distribution` across arms: one
  column name, one decimal convention.** Arm A previously asked for a
  `**probabilities:**` bold line formatted as a `SÍMBOLO=probabilidad`
  delimited string with Spanish-locale comma decimals (e.g.
  `AG1=0,20; AG2=0,45; ...`), while Arm B/C's `probability_distribution`
  JSON field used period decimals — two different column names and two
  different decimal separators for the same four PRIMARY-outcome questions.
  Standardised on B/C's shape (JSON, period decimal) since it's already
  standard JSON and already what two of the three arms produced. Changed
  `prompt_template_arm_a.py`'s `DISTRIBUCIÓN DE PROBABILIDAD` instruction
  and all four worked examples (EDAD, SEXO, ORIENTACION_IDEOLOGICA,
  INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA) from the bold field name
  `probabilities` to `probability_distribution`, with a JSON-object example
  and an explicit "punto decimal, nunca coma" instruction. Matching change
  in `src/utils.py::extract_llm_responses()`: renamed the
  `probabilities_pattern`/`probabilities_list` machinery and the flattened
  `{question} - probabilities` column to `probability_distribution_pattern`/
  `probability_distribution_list`/`{question} - probability_distribution`,
  so Arm A's column now has the same name as Arm B/C's. This field is Arm-A
  specific in `extract_llm_responses()` (checked: no other prompt consumes
  it), so the rename doesn't affect stock-recommendation interviews or any
  other caller of that function. Verified: `config/digital_twin_config.py`
  has no `probabilities`-pattern column-coalescing entry to update either
  (same as the earlier 2026-08-01 check). Content still depends on the model
  actually following the new JSON/period-decimal instruction — not verified
  against a fresh run yet.

- **Removed two stale `Vcu2` format examples**, in
  `prompt_template_arm_a.py` (`REGLA DE FORMATO CRÍTICA`, appears twice —
  once in the entity/geographic prompt, once in the voting-preference
  prompt) and `prompt_template_arm_b.py` (same rule, Stage 2 system prompt).
  `Vcu2` referenced the `INTENCION_VOTO_2025_FECHA_TWEET` symbol family,
  which was removed from the codebook 2026-07-29 — the example cited a code
  that no longer exists anywhere in the current prompts. Replaced with
  `Vsv2` (the `INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA` family added
  2026-07-30), which is live in the current codebook.

## 2026-08-02/03

Six instrument-alignment fixes from Ray Duch's 2026-08-02 memo
(`admin/memos/Memo_Matias_PilotLaunch_2026.08.02.docx`), closing every
`MISMATCH`/`MISSING` row in `documentation/Qualtrics Crosswalk.xlsx`'s
Crosswalk v3 sheet except `INDECISION_2025` (still open). Applied across
Arms A/B/C/D and `config/digital_twin_config.py` as needed; option wording
and cutpoints sourced verbatim from the Crosswalk's `Comp` tab (the actual
fielded Qualtrics text), not paraphrased from the memo. This batch **blocks
the pilot** (EDAD specifically) — nothing downstream (fresh smoke test,
architecture pilot, V8.1, OSF filing) proceeds without it.

- **EDAD: AG1-AG7 (7 brackets) → AG1-AG4 (4 registered analysis brackets).**
  18-29 / 30-44 / 45-64 / 65+, replacing the old <18/18-24/25-34/.../65+
  scheme. `CANONICAL_OPTIONS["EDAD"]` count unaffected (still one entry);
  option text shrinks from 7 to 4 codes + CI.
- **Q3.5/Q3.8 participation (THPA/TCUINDV): 7-point probability scale →
  3-option Sí/No/No recuerdo.** Matches the fielded instrument exactly
  (neither field is part of the four-outcome Brier probability-elicitation
  set, so dropping the probability framing doesn't touch that commitment).
  Reclassified `THPA`/`TCUINDV` from `ORDINAL_KEYS` to `NOMINAL_KEYS` in Arm
  C (confirmed decision, 2026-08-03) — now that the scale is a 3-category
  Sí/No/No recuerdo choice rather than a probability continuum, it's a
  nominal set and gets shuffled like the other nominal fields.
- **Q3.9 vote intention 2025 (VCUINDV): added Vcuindv9 (Harold
  Mayne-Nicholls); reframed from hypothetical intention ("votaría") to
  realized first-round vote ("votó"), matching the fielded item (survey was
  fielded after the first round).** Retitled the field from "(INDV)
  PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES
  PRESIDENCIALES DE CHILE DE 2025" to "(INDV) VOTACIÓN ACTUAL – OPCIÓN DE
  VOTO EN LA PRIMERA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE
  2025" — updated everywhere this title is matched (Arm B's
  `_STAGE2_QUESTIONS` extraction anchor, Arm D's `arm_a_field` reference,
  and the corresponding 4-line regex block in `config/digital_twin_config.py`).
  Also reframed Arm D's sibling field INDV_PARTICIPACION_2025's free-text
  question (was still asking "¿Votará...?" in future tense) to match.
- **Fixed a pre-existing regex bug in `config/digital_twin_config.py`:
  every `(INDV)`-prefixed title pattern had unescaped parentheses**
  (`^(INDV) ...`), which regex-parses as a capture group matching bare
  "INDV" rather than the literal "(INDV)" text — so none of these 16
  patterns (4 fields × 4 sub-fields: the two 2021 legislative-vote fields,
  TCUINDV's participation title, and VCUINDV's title) ever actually matched
  Arm A's real column names, and `coalesce_columns_by_regex` silently
  no-op'd for all of them (low practical impact in the single-column case,
  but the merge-safety-net for near-duplicate columns was dead for this
  whole field class). Escaped to `\(INDV\)` throughout; verified all 16
  patterns now match their real column names. Predates this batch —
  discovered while updating the VCUINDV title regex, not introduced by it.
- **Added missing Q3.7 (2021 ballotage) field: `VOTO_BALLOTAGE_2021`,
  symbols Vba1-4 + CI** (no votó / Boric / Kast / no recuerda; "Prefiero no
  responder" flows through CI, same convention as PINC's PNR). Mirrors
  `VOTO_PRESIDENCIAL_2021`'s block structure. New symbol prefix `Vba` chosen
  to parallel `Vpa` (2021 first round) and `Vsv` (2025 ballotage, already
  built) — not specified in the memo, flagging for confirmation. Required:
  new tuple in Arm B's `_STAGE2_QUESTIONS` (34→35, `CANONICAL_OPTIONS`
  33→34), new `NOMINAL_KEYS` entry in Arm C, four new touch points in Arm D,
  and a new 4-line regex block in `config/digital_twin_config.py` (the one
  fix among the six that needed a config edit, since it's a brand-new title
  with no existing pattern).
- **PARTIDO_POLITICO: added PP17 "No me identifico con un partido."**
  Closes the item deliberately left open since 2026-07-27 (a real, frequent
  ground-truth category the pipeline previously couldn't predict).
- **PINC (RANGO_INGRESOS_PERSONALES): realigned to fielded Q7.12, 17→18
  codes.** Old brackets (e.g. $35-60k, $60-100k) didn't match the fielded
  cutpoints (e.g. $35-100k, $100-210k). New cutpoints taken verbatim from
  the Comp tab. `RANGO_INGRESOS_HOGAR` (HINC, household income) intentionally
  left untouched — the Crosswalk already marks it "Confirmed match" against
  its own fielded item (Q7.13), whose brackets differ from Q7.12's.

## 2026-08-01

- **Removed resolved-judgment fields from Stage 1's evidence schema; Stage 2
  now infers REGION/COMUNA from raw evidence instead of copying a Stage 1
  value.** Stage 1's own system prompt says "En esta etapa NO realice
  predicciones de encuesta. Solo documente evidencia," but an audit found 17
  sub-fields across the schema that were already resolved categorical
  judgments, not evidence: `demographics.location.inferred_region`/
  `inferred_municipality`, `political.ideology.net_direction`,
  `political.party_affiliation.inferred_affinity`,
  `political.political_interest.estimated_level`,
  `political.vote_2021_presidential/vote_2021_legislative/
  vote_2025_intention.inferred_signal` (×3),
  `political.candidate_sentiments.{kast,jara,matthei,parisi,meo,artes,
  kaiser}.valence` (×7), `civic.campaign_attention_2025/campaign_attention_2021/
  general_trust.estimated_level` (×3), `issues.most_important_issue.
  inferred_concern`. In Stage 2, only `REGION`/`COMUNA` exploited this,
  pointing `evidence_basis` directly at the resolved field instead of
  inferring from raw evidence like every other question — the exact failure
  mode Ray's `prompt-engineering-guide.md` §11 warns about ("commune
  assigned without evidence").

  Every listed field now matches the canonical shape already used correctly
  by `age`/`gender`/`education`/`occupation`/`marital_status`/`income`
  (`direct_evidence`/`indirect_evidence`/`supporting_quotes`/`confidence`),
  with three deliberate exceptions, confirmed with Matias: `ideology` keeps
  `left_signals`/`right_signals`/`center_signals` alongside the canonical
  fields (raw categorized observations, not a synthesized verdict, so they
  don't violate the rule); `vote_2025_intention` and
  `electoral_participation` keep `active_abstention_signals` for the same
  reason; `candidate_sentiments` keeps its 7-candidate dict structure but
  each candidate now gets the full canonical 4-field shape instead of a bare
  `valence` judgment. `profile_metadata` (`richness`,
  `estimated_political_tweet_pct`, `overall_inference_quality`) is left
  unchanged — none of its three fields resolves a specific survey-answer
  judgment the way the removed fields did.

  Stage 2: `REGION`/`COMUNA`'s `evidence_basis` changed from
  `demographics.location.inferred_region`/`inferred_municipality` to
  `demographics.location` (matching `PERSONA_VIVE_CHILE`'s existing correct
  pattern). The "Preguntas geográficas" system-prompt paragraph now
  instructs inferring region/comuna from `demographics.location`'s raw
  evidence — the same reasoning process used for every other question —
  instead of reading a pre-resolved field. `arm_b_municipal_web_instruction`
  (not yet wired into the driver) updated for consistency, from checking
  `inferred_municipality` to inferring a comuna from raw evidence with
  `confidence` 'medium' or higher.

  **Not done as part of this change:** the Dropbox-side QA script
  (`06_pilot_comparison_smoke_test_qa_round2_matias.Rmd`)'s Arm B vs Arm C
  Stage-1 divergence check (`stage1_conclusion_keys`/`stage1_bc_diffs_for`,
  and an earlier region/comuna-specific diff table) hard-codes exactly the
  field names removed here. Left as-is, it will not error — `get_by_parts()`
  returns `NULL` for a missing key on both sides, and the diff comparison
  will silently report false "0% divergence" instead of failing loudly.
  Tracked as a separate follow-up; do not trust that script's Stage-1
  divergence section against post-change data until it's updated to compare
  `confidence` per field instead.

- **Added field-filling instructions to Stage 1's system prompt** (`arm_b_stage1_system_prompt`):
  a `NIVELES DE CONFIANZA` section giving graded criteria (explicit self-statement / converging
  indirect signals / one weak signal / nothing) for `confidence: high/medium/low/none`, applied
  uniformly across every Stage 1 field including the three structured-list fields; a short
  instruction tying `supporting_quotes` to verbatim citation of the same field's evidence; and a
  `LISTAS ESTRUCTURADAS` section defining what counts as a `left_signals`/`right_signals`/
  `center_signals` entry versus `indirect_evidence`, and — the more consequential distinction —
  that `active_abstention_signals` requires an affirmative disaffection/rejection signal, not
  mere absence of vote-intention evidence (that's `confidence: none`). Motivation: Stage 1
  previously had no criteria at all for `high`/`medium`/`low` (only the `none` case, via rule 3),
  unlike Stage 2's `NIVELES DE ESPECULACIÓN`; this gap is the leading explanation for observed
  Arm B vs Arm C divergence on `confidence` for the same profiles. Kept deliberately terse — this
  system prompt runs once per Stage 1 call across the full dataset, so length is a recurring
  token cost, not a one-off.

- **Fixed: `extract_llm_responses()` silently dropped Arm A's `**probabilities: ...**` output.**
  Arm A's prompt correctly asks for a `probabilities` bold-line on the four PRIMARY outcomes
  (`prompt_template_arm_a.py:552,559,596,675`), per the 30 Jul probability-elicitation addition —
  but the shared regex parser in `src/utils.py` only recognized `question`/`explanation`/`symbol`/
  `category`/`speculation`/`value`/`response`/`stock_ticker`/`recommendation`/`confidence`/
  `expected_holding_period`/`primary_catalyst_type`, with no pattern for `probabilities` at all.
  The model's probability output was never a parsing failure — it just had nowhere to go, so the
  column never existed in the output CSV. Added the missing pattern, list, and flattened-column
  entry (`{question} - probabilities`), matching the existing fields' pattern exactly. Verified via
  a standalone regex test against a synthetic Arm-A-format response block. Checked the column-
  coalescing regex lists (`config/digital_twin_config.py`) too — no equivalent gap there, since
  `probabilities` only ever has one source column per question, nothing to coalesce.

- **Fixed: `extract_json_predictions()` (Arms B/C) silently dropped `probability_distribution`
  the same way Arm A's regex parser did.** Its `field_keys` default tuple only listed `symbol`/
  `category`/`speculation`/`explanation`/`evidence_basis` — no `probability_distribution`, so the
  model's per-symbol probability object for the four PRIMARY outcomes was parsed by Stage 2
  correctly and then discarded during flattening, never becoming a column. Added
  `probability_distribution` to `field_keys`, and generalized the per-field value handling to
  `json.dumps()` any list/dict value (not just this one) before writing it into the flattened
  Series, matching how the existing `cannot_infer_fields`/`high_speculation_fields` meta-fields
  were already serialized. Verified via a synthetic Stage 2 JSON response: the probability object
  now extracts as a proper JSON string column, and questions without a `probability_distribution`
  key (the other 30) are unaffected.

- **Fixed: `arm_b_stage2_system_prompt` broke `construct_system_prompt()`'s `.format()` call.**
  The `DISTRIBUCIÓN DE PROBABILIDAD` worked example (added in the 30 Jul batch) contained literal
  JSON braces (`{"AG1": 0.05, ...}`); since `construct_system_prompt()` (`src/utils.py`) calls
  `.format(**profile_args)` unconditionally on every arm's system prompt, this raised
  `KeyError: '"AG1"'` the first time Arm B (or C, which inherits this prompt) was actually run.
  Escaped to `{{`/`}}` so the example renders as literal text. Confirmed Arm A and Arm D have no
  equivalent issue.

## 2026-07-30

**Implemented in a separate checkout** (`C:\Users\mbmat\OneDrive\Desktop\digital-twin-chile`,
copied from the Dropbox repo before this batch, to be copied back after
review) — all four arms verified to import cleanly and pass their
count-invariants after every step below, not just at the end.

- **Added a CANNOT_INFER (`CI`) escape option to every question in Arm A,
  and standardized `_CI_LINES` in Arm B (inherited by Arm C) to a single
  uniform line.** Arm A previously had zero `CI`/`CANNOT_INFER` occurrences
  anywhere. Added `CI) CANNOT_INFER` as the last option under all ~31
  non-geographic questions (REGION/COMUNA handled separately below, since
  they also needed the NA change). `_CI_LINES` (`prompt_template_arm_b.py`)
  previously carried a bespoke Spanish reason phrase per field (e.g. `"CI)
  CANNOT_INFER — sin evidencia sobre el tema prioritario"`); every entry is
  now exactly `"CI) CANNOT_INFER"`, symbol `CI)` and category `CANNOT_INFER`,
  no per-field suffix.

- **REGION/COMUNA: dropped `REG17`, made `NA` purely instructional (not a
  listed option), added `CI` as a plain option.** `REG17) NA` removed from
  Arm A's REGION list entirely (down to `REG1`–`REG16`); COMUNA's `CI)
  CANNOT_INFER` added the same way. Both questions' instruction sentences
  now read: "...seleccione la región/comuna... de la siguiente lista, o
  'CI' si no hay evidencia suficiente... Si la respuesta a PERSONA QUE VIVE
  EN CHILE es 'No', responda con 'NA' (no seleccione ningún código numerado
  de la lista)." **`NA` is deliberately not a bulleted option** — an
  earlier draft of this change listed `NA) La persona no vive en Chile...`
  as a bullet in both the option list and Arm B's generated block, which
  Matias caught as reintroducing exactly the "NA looks like a selectable
  code" problem this change exists to fix. Reverted; the instruction
  sentence alone carries the rule, and Arm B/C inherit it automatically
  (the sentence is extracted into `_sentences` by `_extract_arm_a_block`,
  same mechanism as every other question's descriptive text — no separate
  NA-line machinery needed). Arm B's Stage 2 JSON schema symbol enum for
  REGION updated from `<REG1|...|REG16|REG17|CI>` to `<REG1|...|REG16|NA|CI>`
  (COMUNA's enum already said `NA|CI`, unchanged). Arm B's docstring
  (`DISTINCIÓN OBLIGATORIA` section) and Arm D's REGION/COMUNA question
  lines updated to state the same NA-vs-CI rule in their own native format
  (Arm D: free-text instruction, no option list to change).

- **Arm D: added the "Formato obligatorio" instruction, matching Arm A's
  wording, plus reinforced the closing reminder.** `arm_d_system_prompt`
  now states the bold-wrapping rule explicitly (previously never mentioned
  asterisks at all) with a worked example. The closing line in
  `arm_d_user_prompt` — "¡Produzca un bloque de tres líneas por
  pregunta...!" — now also says "cada línea entre dos asteriscos
  (**question: ...**, **response: ...**, **speculation: ...**)". Root
  cause and evidence for this fix are in the round-2 QA report; this entry
  just records what was actually changed and where.

- **Added the Q3.10 ballotage item, `INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA`,
  across Arms A–D.** Verbatim stem and options confirmed against the actual
  fielded Qualtrics export, not the crosswalk placeholder — source:
  `documentation/questionnaire/Twitter_-_Chile_PK_in_progress_-_new_Version.qsf`,
  `QID418` (`DataExportTag: Q3.10`), `ChoiceOrder: ["10", 5, "7", "19", "20"]`.
  Stem: "Ahora le preguntaremos sobre la segunda vuelta de las elecciones
  presidenciales, que se realizará el próximo domingo 14 de diciembre de
  2025. Si las elecciones presidenciales fueran hoy, ¿por cuál de los
  siguientes candidatos votaría? Recuerde que esta encuesta es confidencial
  y para fines académicos." Options, fielded order: Jeannette Jara – PC/
  Unidad por Chile; José Antonio Kast – Republicano/PSC; voto nulo o
  blanco; no voy a votar; no estoy seguro(a). **New symbol family: `Vsv1`–
  `Vsv5`** (Vsv = "voto segunda vuelta"; chosen fresh, doesn't collide with
  any existing prefix — not specified by Ray/the crosswalk, flagging the
  choice here for review). Per-arm implementation, each arm's own native
  format:
  - **Arm A:** bold-block schema entry + concrete `Vsv1`–`Vsv5` + `CI`
    option list, positioned immediately after the existing first-round
    `(INDV) ... OPCIÓN DE VOTO ... 2025` question.
  - **Arm B:** new `("VSV", "INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA", ...,
    "vote")` entry in `_STAGE2_QUESTIONS` (count 33→34), extracted
    automatically from Arm A's text by the existing generic loop, `_CI_LINES`
    entry, Stage 2 JSON schema entry. `CANONICAL_OPTIONS` count 32→33.
  - **Arm C:** inherits via `CANONICAL_OPTIONS`; added `"VSV"` to
    `NOMINAL_KEYS` (a candidate-choice question, same category as `VCUINDV`).
  - **Arm D:** new question line in `arm_d_user_prompt`, `ARM_D_QUESTION_LABELS`
    entry (count 33→34), `ARM_D_CANONICAL_MAP` reference entry.
  **Not done as part of this batch:** the `code_specs` row in
  `scripts/analysis/06_pilot_comparison_smoke_test_qa_round2_matias.Rmd`'s
  QA engine — that file lives in the separate Chile/Dropbox repo, out of
  scope for this digital-twin-chile-only checkout. Needs a follow-up edit
  there (regex `^Vsv[1-5]$|^CI$`) before the QA script will validate this
  question instead of flagging every answer as `bad_symbol`.

  **Bug found and fixed as a direct result of this addition:**
  `config/treatment_arms.py`'s `_arm_d_patterns()` builds Arm D's
  column-coalescing regex from `ARM_D_QUESTION_LABELS` as
  `rf"^{escaped}.*\-\s*response$"` — the `.*` let a pattern for one label
  also match any OTHER label that happens to start with it. Since
  `INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA` starts with the existing
  `INDV_INTENCION_VOTO_2025`, `coalesce_columns_by_regex` treated both
  questions' `- response` columns as duplicates under
  `INDV_INTENCION_VOTO_2025`'s pattern and dropped one — confirmed on an
  actual pilot run
  (`data/digital-twin-chile-x/pilot_with_profile_info_without_web_search_arm_d/`):
  the raw LLM text had a correctly bold-formatted
  `INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA` response for 4 of 5 profiles,
  but the parsed CSV had no `- response` column for it at all. No other
  label pairs in `ARM_D_QUESTION_LABELS` have this prefix relationship
  (checked programmatically), so this was latent, not previously
  triggered. Fixed: pattern anchored to `rf"^{escaped}\s*\-\s*response$"`
  so it can no longer match a longer label.

  **Second bug found while verifying the first fix, and its two-part
  fix.** Replaying the same pilot run's raw data through the corrected
  pattern surfaced that `vitoquiles`'s entire response used lowercase
  question labels (`persona_real`, `indv_intencion_voto_2025`, ...)
  instead of the canonical uppercase ones every other profile used.
  `coalesce_columns_by_regex`'s patterns are case-insensitive but only
  ever covered `- response`, never `- speculation` — so `vitoquiles`'s
  response data merged correctly by luck (case-insensitive match) while
  its speculation data was stranded in an uncoalesced
  `indv_intencion_voto_2025 - speculation` column, invisible to anything
  reading the canonical uppercase column name. Root cause traced to this
  session's own earlier "Formato obligatorio" fix (above): its
  instruction "el nombre del campo **en minúsculas**" is unambiguous in
  Arm A (refers to the fixed meta-labels `symbol`/`category`/etc., whose
  *values* are short codes like `PP12`, never confusable with a "field
  name") but genuinely ambiguous in Arm D, where the `question` field's
  *value* **is** a canonical label in full (`EDAD`, `PERSONA_REAL`) —
  the model over-applied "lowercase" to that value for this one profile,
  despite the worked example directly below showing the correct casing.
  Two-part fix, not one:
  1. **Prompt (removes the ambiguity, ~+2 tokens, not yet validated with
     a smoke test):** `arm_d_system_prompt`'s "el nombre del campo en
     minúsculas" → "el nombre del campo **tal como en el ejemplo**" —
     points at the worked example (which already shows both required
     casings unambiguously) instead of stating an abstractable rule.
  2. **Parser (defensive backstop, zero marginal cost, verified against
     real data):** `extract_llm_responses()` (`src/utils.py`) gained an
     optional `canonical_labels` parameter — case-insensitive lookup that
     rewrites a parsed question label to its canonical form before it's
     used as a column-name key, so a case-variant duplicate column is
     never created in the first place (no longer relying on
     `coalesce_columns_by_regex`'s "fewest nulls wins" heuristic, which
     only coincidentally kept the uppercase column this time because just
     1 of 5 profiles drifted — it would silently start keeping the wrong
     casing if more profiles did). Wired in at the Arm D call site in
     `digital_twin_chile_x.py` with `canonical_labels=ARM_D_QUESTION_LABELS`.
     Default `None` leaves every other caller of `extract_llm_responses`
     unchanged. Verified by replaying `vitoquiles`'s actual raw response
     text through the updated function directly: zero case-variant
     columns remain, for any of the 34 questions, before coalescing even
     runs.

- **Added probability-distribution elicitation for the four PRIMARY
  outcomes — EDAD, SEXO, ORIENTACION_IDEOLOGICA,
  INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA — in Arms A, B, and C.** Per
  Ray's 2026-07-29 08:27 direction: alongside the existing point
  prediction and speculation score, the model additionally writes a
  probability (0–1, summing to 1 across that question's full option set
  including `CI`) per response-option. Arm A: a `**probabilities:**` bold
  line added to just these 4 questions' schema blocks, plus a new
  instruction paragraph (with a worked example) explaining the field and
  which four questions carry it. Arm B: a `"probability_distribution":
  {...}` JSON object added to the same 4 schema entries, plus matching
  instruction text in `arm_b_stage2_system_prompt`; Arm C inherits both
  automatically (shared system prompt + `CANONICAL_OPTIONS`). **Arm D
  deliberately excluded, not silently — flagging for Ray/Matias to
  confirm, not assuming.** The 2026-07-29 entry below already noted this
  exact tension when speculation was added to Arm D: probability output
  "requires exposing each outcome's option list to the model, a further
  departure from the sparse design... held pending a separate decision."
  That decision was not made today; Arm D still shows no option lists at
  all (`ARM_D_NO_DATA_MARKER` aside), so adding per-option probabilities
  there would require rebuilding Arm D's entire minimal-instructions
  premise, not a one-line addition. Confirm before extending this to Arm D.
  Design choice not otherwise specified by Ray: exact field name
  (`probabilities`/`probability_distribution`) and format (0–1 decimal,
  `SÍMBOLO=P` pairs for Arm A, JSON object for B/C) — flagging for review,
  not asserting these are the only reasonable choices.

- **Arm D: require an explanation inside `response` for every question, and
  require every question to be answered.** Motivated by Arm B's existing
  "¡USTED DEBE DAR UNA RESPUESTA PARA CADA PREGUNTA!" completeness rule,
  which Arm D never had an equivalent of. Two changes to
  `prompt_template_arm_d.py`:
  1. `arm_d_system_prompt` now reads "Responda en texto libre, breve y
     natural, incluyendo siempre una breve justificación de su respuesta
     dentro de response (excepto cuando la instrucción de la pregunta
     indique responder exactamente "NA", en cuyo caso no agregue nada
     más)" and adds "Debe responder TODAS las preguntas de la lista, sin
     omitir ninguna, incluso si la respuesta es CI."
  2. `arm_d_user_prompt`'s closing reminder gained a leading "¡USTED DEBE
     RESPONDER TODAS LAS PREGUNTAS DE LA LISTA, SIN OMITIR NINGUNA!" line,
     mirroring Arm B's phrasing.
  **REGION/COMUNA's bare `NA` is an explicit exception, not an oversight.**
  Earlier today's REGION/COMUNA NA-vs-CI fix (above) intentionally left
  `NA` unexplained — its meaning ("la persona no vive en Chile") is already
  fixed by the instruction sentence that produces it, so appending a reason
  would be redundant. A first draft of this change added a parenthetical
  reason to the `NA` response itself (e.g. `"NA (no vive en Chile)"`) in
  both the general system-prompt rule and the REGION/COMUNA lines
  specifically — Matias caught this as reintroducing exactly the kind of
  answer-format drift the earlier fix removed ("we should keep what we
  had, i.e. NA if the subject doesn't live in Chile. It will show as NaN
  in the data and that's right"). Reverted; the new "incluyendo siempre
  una breve justificación" clause explicitly carves out the `NA` case via
  the "(excepto cuando...)" parenthetical above. Also relevant, **flagged
  but not yet resolved:** the raw pilot output for `eduardomenoni` and
  `Doct_Tricornio` shows `NA` on 8 other Chile-election-specific questions
  beyond REGION/COMUNA whenever the model infers the person doesn't live
  in Chile (`PARTICIPACION_PRESIDENCIAL_2021`, `VOTO_PRESIDENCIAL_2021`,
  `INDV_PARTICIPACION_LEGISLATIVA_2021`, `INDV_VOTO_LEGISLATIVO_2021`,
  `INDV_PARTICIPACION_2025`, `INDV_INTENCION_VOTO_2025`,
  `INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA`, `INDECISION_2025`). This is
  NOT sanctioned behavior — only REGION/COMUNA are ever instructed to
  accept `NA`, everything else should fall back to `CI`. But that pilot
  data predates every Arm D prompt fix made today (CI escape, formato
  obligatorio, completeness), so it reflects the uncorrected prompt, not
  the current one — no code change made based on it. **If a fresh Arm D
  run under today's corrected prompt still produces `NA` outside
  REGION/COMUNA, that is a red flag and needs a prompt fix** (e.g. an
  explicit "`NA` only valid for REGION/COMUNA, use `CI` everywhere else"
  line), not something to wave through as expected model behavior.
  Separately, pandas/R's default treatment of the literal string `"NA"`
  as a missing value on `read_csv()` is intended, not a bug — no code
  change needed there. Verified via `ast.parse` and a live import of
  `prompt_template_arm_d`, asserting the new wording is present in both
  `arm_d_system_prompt` and `arm_d_user_prompt` and that
  `ARM_D_QUESTION_LABELS` still has its expected 34 entries.

## 2026-07-29

- **Removed `INTENCION_VOTO_2025_FECHA_TWEET`** ("vote preference as of the
  date of their last tweet," code family `Vcu1`–`Vcu8`) from all four arms.
  This closes out a decision from the Monday 9 Feb 2026 meeting notes (Asana
  task 1213046085824132, comment by Matias): "Remove questions related to
  'the last tweets': Ensure that no duplicate questions remain in the final
  instrument" — recorded then, never actually implemented until now.
  Removed from:
  - Arm A: the `**question:.../FECHA DE SU ÚLTIMO TUIT**` output block and
    its `Vcu1`–`Vcu8` option list.
  - Arm B: the JSON-schema entry, the `_STAGE2_QUESTIONS` tuple (count
    34→33) and its CI fallback line. `CANONICAL_OPTIONS`'s own count assert
    (33→32, since COMUNA is excluded from that dict separately) updated to
    match.
  - Arm C: the `VCU_FECHA_TWEET` key in `NOMINAL_KEYS` (Arm C inherits
    everything else from Arm B by construction).
  - Arm D: the question line, `ARM_D_QUESTION_LABELS` entry,
    `ARM_D_CANONICAL_MAP` entry, and the post-hoc mapper's option-list line.
  Left untouched: `INDECISION_2025`'s wording, which references "fecha de su
  último tuit" only as a temporal anchor ("between now — date of last tweet —
  and election day"), not as a dependency on the removed question's answer.
  Also untouched: the deprecated, unused `prompt_template.py` (superseded
  original, not imported by any live arm) still contains the old question —
  left as-is since nothing reads it.
  Verified: all four arms import cleanly end-to-end with every
  count-invariant passing (`_STAGE2_QUESTIONS`=33, `CANONICAL_OPTIONS`=32,
  Arm C's `NOMINAL_KEYS`/`ORDINAL_KEYS` partition still equals
  `CANONICAL_OPTIONS`'s keys, `ARM_D_QUESTION_LABELS`=33).
- **Arm D: added a `speculation` line to Call 1.** Output block changed from
  two lines (`question`, `response`) to three (`question`, `response`,
  `speculation`, 0–100). Rationale: needed so Arm D can be scored on
  CI–speculation consistency for the architecture-pilot eligibility rule
  (pre-reg tracker item 6) and included in H5. `pretesting-strategy_2.md`
  Criterion 4 scopes the speculation-*calibration analysis* to Arms A/B/C
  but does not exclude Arm D from producing the score itself.
  Deliberately NOT added: probability-distribution output (the AI-RCT/Brier
  harmonization item) — unlike speculation, that requires exposing each
  outcome's option list to the model, a further departure from the sparse
  design. Held pending a separate decision.
- **Arm D: post-hoc mapping moved out of the Python pipeline entirely, into
  deterministic R-side matching** (`scripts/build/`, not yet written — see
  `[[digital_twin_chile_pipeline_state]]` memory). The `arm_d_mapping_*`
  prompt constants in `prompt_template_arm_d.py` are now kept only as
  reference for the target code space per question; they are not invoked by
  any driver code. This supersedes the 27 Jul design (below), which still
  used a second LLM call for mapping.

## 2026-07-27

- **Arm A:**
  - `PP16) Movimiento Amarillos Por Chile` added to `PARTIDO_POLITICO` — the
    fielded Qualtrics instrument (Q3.1) offers it; its absence was a
    deviation. `"No me identifico con un partido"` remains deliberately
    unmapped (open team decision, not an oversight).
  - `AFINIDAD_PARTIDO` symbol changed from a bare `1`–`7` to `Afi1`–`Afi7`.
    It was the only symbol in the codebook with no letter prefix; the QA
    engine's `code_specs` regex needs widening from `^[1-7]$` to `^Afi[1-7]$`
    to match (see QA report 06 appendix).
  - `IoPoR1`/`IoPoR10` given explicit verbal anchors ("1 Izquierda", "10
    Derecha") in the option line itself, rather than relying on prose above
    the list.
  - Comuna typo fixed: `COMU106) HUALAAÑE` → `HUALAÑE` (cross-validated
    against an independent 2021 election-results dataset; see
    `[[digital_twin_chile_pipeline_state]]`).
- **Arm D: full rebuild** to match `admin/pretesting-strategy_2.md` section 2
  ("free-text output mapped to categories post hoc"). The previous
  implementation supplied compressed code ranges per question (e.g.
  `PARTIDO_POLITICO [PP1–PP15]`), which is a different design — the model
  still saw a code space. Rebuilt as free-text elicitation (Call 1) plus a
  post-hoc mapping step (at this point still a second LLM call using an Arm
  B–style JSON envelope; see 29 Jul entry above for the later change to
  R-side matching). Content revisions shared with Arm A (PP16, comuna coded
  into the same `COMU1`–`COMU346` space) applied here too.
- **Arm C:** added `shuffle_keys` (explicit override of which questions are
  randomized, including `COMUNA`, previously always canonical) and CLI flags
  `--shuffle-scope`, `--shuffle-keys` (accepts `all`), `--seed-suffix` on
  `digital_twin_chile_x.py`.
