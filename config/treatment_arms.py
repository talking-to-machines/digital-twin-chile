"""
Treatment-arm registry for the AIPOP Chile digital-interview pipeline.

Each arm describes how the pipeline should run for a given experimental
condition: its architecture (how many LLM calls / what output format), the
prompt templates to use, and how the model output is parsed.

Architectures
-------------
- ``two_call_regex``  : single-stage, two LLM calls (entity/geographic, then
                        voting preference), ``**field: value**`` output parsed
                        by regex. Used by ``baseline`` and Arm A.
- ``one_call_regex``  : single-stage, one combined LLM call, ``**field: value**``
                        output parsed by regex. Used by Arm D.
- ``two_stage_json``  : Stage 1 evidence extraction -> JSON, then Stage 2
                        prediction -> JSON parsed with ``json.loads``. Used by
                        Arms B and C (Arm C randomises Stage 2 option order).

The pipeline entry point (``src/digital_twin_chile_x.py``) dispatches on the
``architecture`` field. Adding a new arm is a matter of adding an entry here.
"""

import re

from prompts import prompt_template as baseline_prompts
from prompts import prompt_template_arm_a as arm_a_prompts
from prompts import prompt_template_arm_b as arm_b_prompts
from prompts import prompt_template_arm_c as arm_c_prompts
from prompts import prompt_template_arm_d as arm_d_prompts
from config.digital_twin_config import (
    ENTITY_GEOGRAPHIC_INTERVIEW_REGEX_PATTERNS,
    VOTING_PREFERENCE_INTERVIEW_WO_VOTING_RESULTS_REGEX_PATTERNS,
)

# Architecture identifiers.
ARCH_TWO_CALL_REGEX = "two_call_regex"
ARCH_ONE_CALL_REGEX = "one_call_regex"
ARCH_TWO_STAGE_JSON = "two_stage_json"


def _arm_a_voting_patterns() -> list:
    """Derive Arm A's voting-prompt regex patterns from the baseline patterns.

    Arm A corrects two issues that change output column names relative to the
    baseline prompt:
      * the ``OCUPACIÓN ACUTAL`` typo is fixed to ``OCUPACIÓN ACTUAL``; and
      * AFINIDAD CON PARTIDO POLÍTICO emits ``symbol``/``category`` fields
        instead of a single ``value`` field.
    """
    patterns = []
    for pattern in VOTING_PREFERENCE_INTERVIEW_WO_VOTING_RESULTS_REGEX_PATTERNS:
        if "AFINIDAD CON PARTIDO POLÍTICO" in pattern and r"\-\s*value$" in pattern:
            # Replace the single value field with symbol + category fields.
            patterns.append(pattern.replace(r"\-\s*value$", r"\-\s*symbol$"))
            patterns.append(pattern.replace(r"\-\s*value$", r"\-\s*category$"))
            continue
        patterns.append(pattern.replace("OCUPACIÓN ACUTAL", "OCUPACIÓN ACTUAL"))
    return patterns


def _arm_d_patterns() -> list:
    r"""Build Arm D regex patterns from its canonical question labels.

    Arm D emits ``**question: <CANONICAL_LABEL>**`` / ``**response: <free
    text or CI>**`` blocks -- free-text elicitation only, no symbol/category/
    speculation/explanation fields -- parsed into ``"<LABEL> - response"``
    columns. Coding the free text into the canonical symbol space happens
    downstream in R, not in this pipeline.

    2026-07-30 fix: the pattern used to be ``rf"^{escaped}.*\-\s*response$"``
    -- the ``.*`` after the label let it match any OTHER label that starts
    with this one, not just this exact label. Confirmed as a real bug, not
    theoretical: adding ``INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA`` (a
    superset of the existing ``INDV_INTENCION_VOTO_2025``) made
    ``coalesce_columns_by_regex`` treat the two questions' "- response"
    columns as duplicates of the same pattern and silently drop one via
    ``bfill`` + column-drop, on an actual pilot run
    (``data/digital-twin-chile-x/pilot_with_profile_info_without_web_search_arm_d/``).
    ``ARM_D_QUESTION_LABELS`` has no other prefix collisions today (checked
    programmatically), so this was previously latent, not previously
    triggered. Fixed by anchoring the pattern to end right after the label
    (only optional whitespace before the literal "- response"), so it can
    no longer match a longer label that happens to start with this one.
    """
    patterns = []
    for label in arm_d_prompts.ARM_D_QUESTION_LABELS:
        escaped = re.escape(label)
        patterns.append(rf"^{escaped}\s*\-\s*response$")
    return patterns


TREATMENT_ARMS = {
    # Original baseline prompt (identical to prompt_template_v2.py).
    "baseline": {
        "architecture": ARCH_TWO_CALL_REGEX,
        "description": "Original baseline (uncorrected) single-stage prompt.",
        "system_prompt": baseline_prompts.x_digital_twin_system_prompt,
        "entity_user_prompt": baseline_prompts.x_digital_twin_entity_geographic_user_prompt,
        "voting_user_prompt": baseline_prompts.x_digital_twin_voting_preference_wo_voting_results_user_prompt,
        "entity_patterns": ENTITY_GEOGRAPHIC_INTERVIEW_REGEX_PATTERNS,
        "voting_patterns": VOTING_PREFERENCE_INTERVIEW_WO_VOTING_RESULTS_REGEX_PATTERNS,
    },
    # Arm A: corrected baseline (same architecture, fixed prompts + guardrails).
    "a": {
        "architecture": ARCH_TWO_CALL_REGEX,
        "description": "Corrected baseline with format + conservative-inference rules.",
        "system_prompt": arm_a_prompts.x_digital_twin_system_prompt,
        "entity_user_prompt": arm_a_prompts.x_digital_twin_entity_geographic_user_prompt,
        "voting_user_prompt": arm_a_prompts.x_digital_twin_voting_preference_wo_voting_results_user_prompt,
        "entity_patterns": ENTITY_GEOGRAPHIC_INTERVIEW_REGEX_PATTERNS,
        "voting_patterns": _arm_a_voting_patterns(),
    },
    # Arm B: two-stage evidence-extraction -> prediction, JSON output.
    "b": {
        "architecture": ARCH_TWO_STAGE_JSON,
        "description": "Two-stage evidence extraction then survey prediction (JSON).",
        "stage1_system_prompt": arm_b_prompts.arm_b_stage1_system_prompt,
        "stage1_user_prompt": arm_b_prompts.arm_b_stage1_user_prompt,
        "stage2_system_prompt": arm_b_prompts.arm_b_stage2_system_prompt,
        "stage2_user_prompt": arm_b_prompts.arm_b_stage2_user_prompt,
        # No dynamic Stage 2 builder: inject the Stage 1 JSON by literal replace.
        "stage2_user_builder": None,
    },
    # Arm C: identical to Arm B but Stage 2 randomises option order per subject.
    "c": {
        "architecture": ARCH_TWO_STAGE_JSON,
        "description": "Two-stage JSON with randomised Stage 2 option ordering.",
        "stage1_system_prompt": arm_c_prompts.arm_c_stage1_system_prompt,
        "stage1_user_prompt": arm_c_prompts.arm_c_stage1_user_prompt,
        "stage2_system_prompt": arm_c_prompts.arm_c_stage2_system_prompt,
        "stage2_user_prompt": None,
        # build_arm_c_stage2_user_prompt(stage_1_output_json, subject_id, save_log_path=...)
        "stage2_user_builder": arm_c_prompts.build_arm_c_stage2_user_prompt,
    },
    # Arm D: minimal sparse single-call prompt, **field: value** output.
    "d": {
        "architecture": ARCH_ONE_CALL_REGEX,
        "description": "Minimal sparse single-call prompt (code ranges only).",
        "system_prompt": arm_d_prompts.arm_d_system_prompt,
        "user_prompt": arm_d_prompts.arm_d_user_prompt,
        "patterns": _arm_d_patterns(),
    },
}

# Default arm: the corrected baseline.
DEFAULT_TREATMENT_ARM = "a"
