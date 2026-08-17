"""
Arm C — Two-Stage Architecture with Randomised Option Ordering
AIPOP Chile — Digital Interview Pipeline

Architecture: identical to Arm B (two-stage) except that Stage 2 presents
answer options in a randomised order per respondent per question. As of the
2026-07-27 alignment pass this identity holds BY CONSTRUCTION: Arm C defines
no question wording, no option lists, and no prediction rules of its own —
everything is imported from prompt_template_arm_b (which in turn extracts
titles, survey sentences and option labels from Arm A at import time). The
only Arm C additions are the ordering rule, the shuffling machinery, and the
randomisation log. See QA report 06, section "Alignment pass: A governs where
the documentation is silent".

Pipeline calls:
  Call 1 (Stage 1):  same as Arm B — arm_c_stage1_system_prompt /
                     arm_c_stage1_user_prompt are aliases of Arm B's.

  Call 2 (Stage 2):
      system = arm_c_stage2_system_prompt
               (= arm_b_stage2_system_prompt + the ORDEN ALEATORIO rule)
      user   = build_arm_c_stage2_user_prompt(stage_1_output_json, subject_id)
               (= Arm B's Stage 2 user prompt with nominal option lists
               shuffled and the ordering NOTA inserted)

Output parsing:
  Same JSON schema as Arm B Stage 2. Parse with json.loads().
  The randomisation_log is written by build_arm_c_stage2_user_prompt and should
  be saved alongside the raw LLM output for ordering sensitivity analyses.

Randomisation contract (revised 2026-07-27; QA report 06, recommendations
1a/5/6/8/14):
  - Seed: f"{subject_id}_{question_key}{randomization_seed_suffix}"
    (deterministic, reproducible; the suffix enables sensitivity re-runs).
  - PRODUCTION DEFAULT (shuffle_scope="nominal"): only NOMINAL_KEYS are
    shuffled. Ordinal scales (ORDINAL_KEYS) are presented in canonical order —
    scrambling an ordered scale degrades the response format instead of
    removing an order bias. shuffle_scope="all" restores the old
    shuffle-everything behaviour for the split-sample ordering diagnostic.
  - ordinal_direction="reversed" presents each ordinal scale end-to-start
    (CI stays last) — the contingency if the diagnostic shows ordinal
    position sensitivity. Default "canonical".
  - Within a shuffled list, all options including CI are shuffled together.
  - COMUNA (346 options) is excluded from shuffling by volume and always
    rendered in canonical order.
  - Canonical symbol codes are preserved regardless of display order.
  - The model selects based on evidence content, not option position.
"""

import random
import json
from typing import Dict, List

# Everything content-bearing comes from Arm B (which extracts from Arm A).
from prompts.prompt_template_arm_b import (
    x_tweet_prompt_template,
    arm_b_stage1_system_prompt as arm_c_stage1_system_prompt,
    arm_b_stage1_user_prompt as arm_c_stage1_user_prompt,
    arm_b_stage2_system_prompt,
    CANONICAL_OPTIONS,
    fill_stage2_user_prompt,
    comuna_option_list,
    _CI_LINES,
)

# All keys build_arm_c_stage2_user_prompt is allowed to shuffle: the 34
# CANONICAL_OPTIONS questions plus COMUNA, which is handled separately below
# because (at 346 options) it is excluded from the scope-based nominal/all
# partition by volume, not because it can never be shuffled.
SHUFFLEABLE_KEYS = frozenset(CANONICAL_OPTIONS) | {"COMUNA"}

# ─── Scale-type classification (QA report 06, section "Two thirds of the
# shuffled questions are ordinal scales") ─────────────────────────────────────
# Option-order randomisation is a control for NOMINAL choice sets, where order
# is an arbitrary nuisance. On an ORDINAL scale the order is part of the
# response format, so the production default leaves ordinal lists in canonical
# order. EDUCACION is quasi-ordinal (EDU4/EDU14 sit out of position) and is
# treated as ordinal here. Declared explicitly rather than pattern-detected.

NOMINAL_KEYS = (
    "SEXO",
    "ESTADO_CIVIL",
    "OCUPACION",
    "PARTIDO",
    "VPA",
    "VBA",
    "VPAINDV_LEG",
    "VCUINDV",
    "VSV",
    "MAS_IMPORTANTE",
    "PERSONA_REAL",
    "PERSONA_VIVE_CHILE",
    "REGION",
    "THPA",
    "TCUINDV",
)

ORDINAL_KEYS = (
    "EDAD",
    "PINC",
    "HINC",
    "EDUCACION",
    "IDEOLOGIA",
    "AFINIDAD",
    "INTERES",
    "ATT2025",
    "ATT2021",
    "CONFIANZA",
    "TPAINDV_LEG",
    "INDECISION",
    "FAV_KAST",
    "FAV_JARA",
    "FAV_MATTHEI",
    "FAV_PARISI",
    "FAV_MEO",
    "FAV_ARTES",
    "FAV_KAISER",
)

assert set(NOMINAL_KEYS) | set(ORDINAL_KEYS) == set(CANONICAL_OPTIONS), (
    "Every CANONICAL_OPTIONS key must be classified as nominal or ordinal"
)
assert not set(NOMINAL_KEYS) & set(ORDINAL_KEYS), (
    "A key cannot be both nominal and ordinal"
)

# ─── Stage 2 — System Prompt: Arm B's + the ordering rule ─────────────────────
# "Same as Arm B" holds by construction: any edit to Arm B's rules propagates
# here automatically. The ONLY Arm C addition is this block.

_ORDEN_ALEATORIO_RULE = """REGLA ADICIONAL — ORDEN ALEATORIO DE OPCIONES:
Algunas preguntas presentan sus opciones en orden ALEATORIO por el sistema de inferencia; las preguntas de escala (edad, ingresos, escalas 1-7/1-10, probabilidades, favorabilidad) y la lista de comunas se presentan en su orden natural. En cualquier caso, el orden en que aparecen las opciones NO indica preferencia, relevancia ni jerarquía.
- Seleccione siempre basándose en el CONTENIDO de la evidencia de Stage 1, no en la posición de las opciones.
- Los códigos de símbolo (ej. AG3, PP7, Vcuindv4) son los identificadores canónicos y permanecen válidos independientemente del orden de presentación.
- Esta regla se aplica a todas las preguntas de esta etapa."""

arm_c_stage2_system_prompt = arm_b_stage2_system_prompt + "\n\n" + _ORDEN_ALEATORIO_RULE

# The NOTA inserted into the user prompt's {ordering_note} slot (Arm B fills
# that slot with an empty string).
_ARM_C_ORDERING_NOTE = """
NOTA: Las opciones de varias preguntas se presentan a continuación en orden aleatorio por respondente; las preguntas de escala y la lista de comunas se presentan en su orden natural. El orden no debe influir en su selección. Los códigos de símbolo son canónicos.
"""


def _is_ci_option(option: str) -> bool:
    """Test whether an option line is the CANNOT_INFER escape.

    Used to keep the CI escape pinned last when an ordinal scale is reversed,
    so reversal changes the scale direction without displacing the escape.

    Args:
        option (str): A rendered option line, e.g. ``"AG3) De 25 a 34 años"``.

    Returns:
        bool: True if the line is the ``CI)`` CANNOT_INFER escape.
    """
    return option.startswith("CI)")


def build_arm_c_stage2_user_prompt(
    stage_1_output_json: str,
    subject_id: str,
    randomization_seed_suffix: str = "",
    save_log_path: str | None = None,
    shuffle_scope: str = "nominal",
    ordinal_direction: str = "canonical",
    shuffle_keys: "list[str] | None" = None,
) -> str:
    """
    Build Arm C's Stage 2 user prompt: Arm B's shared template with option
    lists shuffled per the randomisation contract and the ordering NOTA
    inserted. Uses literal replacement throughout (never str.format), so JSON
    braces and evidence-sheet content are safe.

    Args:
        stage_1_output_json:   Raw string output from Stage 1 call.
        subject_id:            User identifier (used as randomisation seed base).
        randomization_seed_suffix: Append e.g. '_v2', '_v3' for sensitivity runs.
        save_log_path:         If provided, write the randomisation log (JSON) here.
        shuffle_scope:         "nominal" (production default) shuffles only
                               NOMINAL_KEYS; ordinal scales render in canonical
                               order. "all" shuffles every key in
                               CANONICAL_OPTIONS (NOMINAL_KEYS | ORDINAL_KEYS).
                               Ignored when ``shuffle_keys`` is given.
        ordinal_direction:     "canonical" (default) or "reversed". Reversed
                               renders each unshuffled ordinal scale
                               end-to-start with the CI escape kept last — the
                               contingency if the diagnostic shows ordinal
                               position sensitivity (rec. 6c). Ignored for
                               keys that are shuffled.
        shuffle_keys:          Explicit override of which questions to
                               shuffle, bypassing the nominal/all scope
                               partition entirely. Any subset of
                               SHUFFLEABLE_KEYS (the 33 CANONICAL_OPTIONS
                               keys plus "COMUNA"). Lets a caller shuffle an
                               arbitrary combination — e.g. everything
                               including COMUNA for the split-sample
                               "shuffle everything" diagnostic (QA report 06,
                               rec. 6a), which shuffle_scope cannot express
                               since COMUNA is otherwise always canonical.
                               None (default) falls back to shuffle_scope.

    Returns:
        Fully formatted user prompt string ready to send to the model.
    """
    if shuffle_scope not in ("nominal", "all"):
        raise ValueError(f"shuffle_scope must be 'nominal' or 'all', got {shuffle_scope!r}")
    if ordinal_direction not in ("canonical", "reversed"):
        raise ValueError(f"ordinal_direction must be 'canonical' or 'reversed', got {ordinal_direction!r}")
    if shuffle_keys is not None:
        unknown = set(shuffle_keys) - SHUFFLEABLE_KEYS
        if unknown:
            raise ValueError(f"Unknown shuffle key(s): {sorted(unknown)}")

    options_fill: Dict[str, str] = {}
    log: Dict[str, List[str]] = {}

    for key, options in CANONICAL_OPTIONS.items():
        if shuffle_keys is not None:
            do_shuffle = key in shuffle_keys
        else:
            do_shuffle = shuffle_scope == "all" or key in NOMINAL_KEYS
        opts = options.copy()
        if do_shuffle:
            seed = f"{subject_id}_{key}{randomization_seed_suffix}"
            random.Random(seed).shuffle(opts)
        elif ordinal_direction == "reversed":
            # Reverse the scale, keep the CI escape at the end.
            ci = [o for o in opts if _is_ci_option(o)]
            opts = list(reversed([o for o in opts if not _is_ci_option(o)])) + ci
        options_fill[key] = "\n".join(opts)
        log[key] = opts

    # COMUNA: canonical order (346 options, excluded from the nominal/all
    # scope by volume) unless explicitly requested via shuffle_keys.
    comuna_shuffle = shuffle_keys is not None and "COMUNA" in shuffle_keys
    comuna_opts = comuna_option_list.split("\n")
    if comuna_shuffle:
        seed = f"{subject_id}_COMUNA{randomization_seed_suffix}"
        random.Random(seed).shuffle(comuna_opts)
    options_fill["COMUNA"] = "\n".join(comuna_opts) + "\n" + _CI_LINES["COMUNA"]
    log["COMUNA"] = comuna_opts

    if save_log_path:
        with open(save_log_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "subject_id": subject_id,
                    "seed_suffix": randomization_seed_suffix,
                    "shuffle_scope": shuffle_scope if shuffle_keys is None else None,
                    "shuffle_keys": sorted(shuffle_keys) if shuffle_keys is not None else None,
                    "ordinal_direction": ordinal_direction,
                    "order": log,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    prompt = fill_stage2_user_prompt(options_fill, ordering_note=_ARM_C_ORDERING_NOTE)
    return prompt.replace("{stage_1_output_json}", stage_1_output_json)


# Municipal electoral data — condition-4 INPUT instruction (guide section 9.4).
# Identical contract to Arm B's; re-exported so the driver can append it to
# either arm's Stage 2 system prompt when enable_web_search is True. Wiring is
# a documented src follow-up (QA report 06); nothing references this yet.
from prompts.prompt_template_arm_b import (  # noqa: E402
    arm_b_municipal_web_instruction as arm_c_municipal_web_instruction,
)
