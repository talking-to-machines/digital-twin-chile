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

- None currently — see "2026-07-30" below for the four items that were
  planned as of earlier today and are now implemented.

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
