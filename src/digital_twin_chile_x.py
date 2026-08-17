import os, json
import argparse
import subprocess
import sys
from datetime import datetime, timezone
import pandas as pd
from tqdm import tqdm

tqdm.pandas()
from config.base_config import GPT_MODEL, NUM_PARALLEL_PROCESSES
from config.digital_twin_config import (
    PROJECT_NAME,
    PROFILE_SEARCH_START_DATE,
    PROFILE_SEARCH_END_DATE,
    NUM_POSTS_PER_PROFILE,
    INCLUDE_PROFILE_INFORMATION,
    ENABLE_WEB_SEARCH,
    WEB_SEARCH_COUNTRY,
    build_execution_date,
    build_sample_tag,
)
from config.treatment_arms import (
    TREATMENT_ARMS,
    DEFAULT_TREATMENT_ARM,
    ARCH_TWO_CALL_REGEX,
    ARCH_ONE_CALL_REGEX,
    ARCH_TWO_STAGE_JSON,
)
from src.utils import (
    perform_x_profile_search,
    perform_x_profile_metadata_search,
    extract_llm_responses,
    extract_json_predictions,
    perform_profile_interview,
    coalesce_columns_by_regex,
    validate_stage2_prediction_keys,
    select_profile_sample,
    _PROFILE_FIELD_COLUMNS,
)
from prompts.prompt_template_arm_c import SHUFFLEABLE_KEYS
from prompts.prompt_template_arm_d import ARM_D_QUESTION_LABELS

base_dir = os.path.dirname(os.path.abspath(__file__))
LOCAL_PROFILE_METADATA_FILE = os.path.join(
    base_dir,
    "../data/digital-twin-chile-x/final_meta_user_df_sample.csv",
)
LOCAL_PROFILE_POST_FILE = os.path.join(
    base_dir,
    "../data/digital-twin-chile-x/test_tweets.csv",
)

# Roster columns the prompt builder reads. A roster missing any of these still
# runs -- build_profile_args falls back to "" per field -- so the preflight
# checks for them explicitly rather than letting prompts render blank silently.
PROFILE_SOURCE_COLUMNS = sorted(
    column for column in _PROFILE_FIELD_COLUMNS.values() if column != "posts_combined"
)


def conduct_entity_geographic_interview(
    project_name: str,
    execution_date: str,
    profile_metadata_file: str,
    post_file: str,
    output_file: str,
    system_prompt: str,
    entity_user_prompt: str,
    entity_patterns: list,
    include_profile_info: bool = True,
    enable_web_search: bool = True,
    entity_labels: list = None,
) -> None:
    """Run call 1 of the two-call arms: the entity and geographic questions.

    Writes the parsed results and appends an ``entity_geographic_interview_history``
    column holding this exchange as JSON, which call 2 replays so the profile
    block reaches it without being rebuilt.

    Args:
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name and filename suffix).
        profile_metadata_file (str): Profile metadata CSV in the run namespace.
        post_file (str): Post corpus CSV in the run namespace.
        output_file (str): Output CSV filename in the run namespace.
        system_prompt (str): The arm's system prompt template.
        entity_user_prompt (str): The arm's entity/geographic user prompt.
        entity_patterns (list): Regexes for coalescing duplicate output columns.
        include_profile_info (bool): Whether to include profile fields and posts.
        enable_web_search (bool): Whether to attach the web-search tool.
        entity_labels (list): Optional canonical question labels used to
            normalise the case of labels echoed back by the model.

    Returns:
        None: Results are written to ``output_file``.
    """
    perform_profile_interview(
        project_name=project_name,
        execution_date=execution_date,
        gpt_model=GPT_MODEL,
        profile_metadata_file=profile_metadata_file,
        post_file=post_file,
        output_file=output_file,
        system_prompt_template=system_prompt,
        user_prompt_template=entity_user_prompt,
        llm_response_field="x_digital_twin_entity_geographic_llm_response",
        interview_type="x_digital_twin_entity_geographic",
        include_profile_info=include_profile_info,
        enable_web_search=enable_web_search,
    )

    # Preprocess post interview results
    post_interview_results = pd.read_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file)
    )
    extracted_responses = post_interview_results[
        "x_digital_twin_entity_geographic_llm_response"
    ].apply(extract_llm_responses, canonical_labels=entity_labels)
    post_interview_results = pd.concat(
        [post_interview_results, extracted_responses], axis=1
    )
    # Merge identical columns from interview response
    post_interview_results = coalesce_columns_by_regex(
        post_interview_results, entity_patterns
    )

    # Format past conversation
    post_interview_results["entity_geographic_interview_history"] = (
        post_interview_results.apply(
            lambda row: json.dumps(
                [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": entity_user_prompt,
                    },
                    {
                        "role": "assistant",
                        "content": row["x_digital_twin_entity_geographic_llm_response"],
                    },
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            axis=1,
        )
    )

    # Save formatted interview results
    post_interview_results.to_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file),
        index=False,
    )


def conduct_voting_preference_interview_without_voting_results(
    project_name: str,
    execution_date: str,
    profile_metadata_file: str,
    post_file: str,
    output_file: str,
    voting_user_prompt: str,
    voting_patterns: list,
    treatment_arm: str,
    include_profile_info: bool = True,
    enable_web_search: bool = True,
    voting_labels: list = None,
) -> None:
    """Run call 2 of the two-call arms: the voting-preference questions.

    Sent with an empty system prompt; the profile block reaches the model by
    replaying call 1's exchange from ``entity_geographic_interview_history``.
    Because ``profile_metadata_file`` is call 1's output CSV, all of call 1's
    columns carry forward into this call's output.

    Args:
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name and filename suffix).
        profile_metadata_file (str): Call 1's output CSV in the run namespace.
        post_file (str): Post corpus CSV in the run namespace.
        output_file (str): Output CSV filename in the run namespace.
        voting_user_prompt (str): The arm's voting-preference user prompt.
        voting_patterns (list): Regexes for coalescing duplicate output columns.
        treatment_arm (str): Arm key, recorded as a column on the output.
        include_profile_info (bool): Whether profile fields and posts are used.
        enable_web_search (bool): Whether to attach the web-search tool.
        voting_labels (list): Optional canonical question labels used to
            normalise the case of labels echoed back by the model.

    Returns:
        None: Results are written to ``output_file``, with ``model``,
        ``treatment_arm``, ``include_profile_info`` and ``enable_web_search``
        recorded as columns.
    """
    perform_profile_interview(
        project_name=project_name,
        execution_date=execution_date,
        gpt_model=GPT_MODEL,
        profile_metadata_file=profile_metadata_file,
        post_file=post_file,
        output_file=output_file,
        system_prompt_template="",
        user_prompt_template=voting_user_prompt,
        llm_response_field="x_digital_twin_voting_preference_wo_voting_results_llm_response",
        interview_type="x_digital_twin_voting_preference_wo_voting_results",
        history_field="entity_geographic_interview_history",
        include_profile_info=include_profile_info,
        enable_web_search=enable_web_search,
    )

    # Preprocess post interview results
    post_interview_results = pd.read_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file)
    )
    extracted_responses = post_interview_results[
        "x_digital_twin_voting_preference_wo_voting_results_llm_response"
    ].apply(extract_llm_responses, canonical_labels=voting_labels)
    post_interview_results = pd.concat(
        [post_interview_results, extracted_responses], axis=1
    )
    # Merge identical columns from interview response
    post_interview_results = coalesce_columns_by_regex(
        post_interview_results,
        voting_patterns,
    )

    # Include LLM model information
    post_interview_results = post_interview_results.copy()
    post_interview_results["model"] = GPT_MODEL
    post_interview_results["treatment_arm"] = treatment_arm
    post_interview_results["include_profile_info"] = include_profile_info
    post_interview_results["enable_web_search"] = enable_web_search

    # Save formatted interview results
    post_interview_results.to_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file),
        index=False,
    )


def conduct_single_call_interview(
    project_name: str,
    execution_date: str,
    profile_metadata_file: str,
    post_file: str,
    output_file: str,
    system_prompt: str,
    user_prompt: str,
    patterns: list,
    treatment_arm: str,
    include_profile_info: bool = True,
    enable_web_search: bool = True,
) -> None:
    """Run the single-stage, single-call interview (Arm D).

    The profile data lives in the user prompt (literal injection), and the
    model emits one ``**field: value**`` block per construct, parsed by regex.

    Args:
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name and filename suffix).
        profile_metadata_file (str): Profile metadata CSV in the run namespace.
        post_file (str): Post corpus CSV in the run namespace.
        output_file (str): Output CSV filename in the run namespace.
        system_prompt (str): Arm D's system prompt.
        user_prompt (str): Arm D's user prompt, carrying the profile block.
        patterns (list): Regexes for coalescing duplicate output columns.
        treatment_arm (str): Arm key, recorded as a column on the output.
        include_profile_info (bool): Whether to include profile fields and posts.
        enable_web_search (bool): Whether to attach the web-search tool.

    Returns:
        None: Results are written to ``output_file``.
    """
    perform_profile_interview(
        project_name=project_name,
        execution_date=execution_date,
        gpt_model=GPT_MODEL,
        profile_metadata_file=profile_metadata_file,
        post_file=post_file,
        output_file=output_file,
        system_prompt_template=system_prompt,
        user_prompt_template=user_prompt,
        llm_response_field="x_digital_twin_arm_d_llm_response",
        interview_type="x_digital_twin_arm_d",
        include_profile_info=include_profile_info,
        inject_profile_into_user_prompt=True,
        enable_web_search=enable_web_search,
    )

    # Preprocess post interview results
    post_interview_results = pd.read_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file)
    )
    extracted_responses = post_interview_results[
        "x_digital_twin_arm_d_llm_response"
    ].apply(extract_llm_responses, canonical_labels=ARM_D_QUESTION_LABELS)
    post_interview_results = pd.concat(
        [post_interview_results, extracted_responses], axis=1
    )
    post_interview_results = coalesce_columns_by_regex(post_interview_results, patterns)

    # Include LLM model information
    post_interview_results = post_interview_results.copy()
    post_interview_results["model"] = GPT_MODEL
    post_interview_results["treatment_arm"] = treatment_arm
    post_interview_results["include_profile_info"] = include_profile_info
    post_interview_results["enable_web_search"] = enable_web_search

    post_interview_results.to_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file),
        index=False,
    )


def conduct_two_stage_json_interview(
    project_name: str,
    execution_date: str,
    profile_metadata_file: str,
    post_file: str,
    stage1_output_file: str,
    stage2_output_file: str,
    arm_cfg: dict,
    treatment_arm: str,
    include_profile_info: bool = True,
    enable_web_search: bool = True,
    shuffle_scope: str = "nominal",
    shuffle_keys: "list[str] | None" = None,
    randomization_seed_suffix: str = "",
) -> None:
    """Two-stage evidence-extraction then prediction interview (Arms B and C).

    Stage 1 extracts an evidence sheet (JSON) from the profile. Stage 2 predicts
    the survey answers (JSON) from that evidence sheet. Arm C additionally
    randomises Stage 2 option ordering per subject via its prompt builder.

    Stage 2 inherits the ``enable_web_search`` setting. The evidence-only design
    argues for running Stage 2 without web search; pass --no-enable-web-search to
    keep predictions strictly grounded in the Stage 1 evidence sheet.

    ``shuffle_scope`` and ``shuffle_keys`` are only meaningful for Arm C.
    ``shuffle_scope``: "nominal" (default) shuffles only nominal-scale
    questions; "all" also shuffles ordinal scales. ``shuffle_keys``, if given,
    overrides ``shuffle_scope`` entirely and shuffles exactly the named
    questions (any subset of Arm C's ``SHUFFLEABLE_KEYS``, which includes
    "COMUNA" — otherwise always canonical order regardless of scope).

    ``randomization_seed_suffix`` (Arm C only) is appended to the per-question
    shuffle seed, so re-running with a different suffix (e.g. "_v2", "_v3")
    reshuffles independently for sensitivity/ordering-diagnostic runs, and is
    also appended to the randomization log filename and the Stage 2 output
    filename so repeated-seed runs don't overwrite each other's audit trail
    or predictions.

    The standalone Stage 1 CSV is deleted once Stage 2 finishes: Stage 2's
    output carries every Stage 1 column forward (it's read back in as Stage
    2's own "profile metadata"), so keeping both as final artifacts is a
    duplicate with nothing gained from the second copy.

    Args:
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name and filename suffix).
        profile_metadata_file (str): Profile metadata CSV in the run namespace.
        post_file (str): Post corpus CSV in the run namespace.
        stage1_output_file (str): Stage 1 CSV filename. Deleted after Stage 2.
        stage2_output_file (str): Stage 2 CSV filename, the surviving artifact.
        arm_cfg (dict): The arm's registry entry, supplying both stages'
            prompts and, for Arm C, the per-subject Stage 2 prompt builder.
        treatment_arm (str): Arm key, recorded as a column on the output.
        include_profile_info (bool): Whether to include profile fields and posts.
        enable_web_search (bool): Whether to attach the web-search tool. Stage 2
            inherits this; pass False for a strictly evidence-only Stage 2.
        shuffle_scope (str): Arm C only. ``"nominal"`` shuffles only
            nominal-scale questions; ``"all"`` also shuffles ordinal scales.
        shuffle_keys (list[str] | None): Arm C only. Explicit question keys to
            shuffle, overriding ``shuffle_scope``.
        randomization_seed_suffix (str): Arm C only. Appended to the
            option-order shuffle seed and to the log and Stage 2 filenames, so
            repeated-seed sensitivity runs do not overwrite each other.

    Returns:
        None: Results are written to ``stage2_output_file``.

    Raises:
        ValueError: If Stage 2 returns a question key outside the canonical
            set, raised after the output is safely on disk.
    """
    if randomization_seed_suffix:
        # Vary the Stage 2 output filename by seed so repeated-seed
        # sensitivity runs don't clobber each other's predictions.
        root, ext = os.path.splitext(stage2_output_file)
        stage2_output_file = f"{root}{randomization_seed_suffix}{ext}"

    # ---- Stage 1: evidence extraction ----
    perform_profile_interview(
        project_name=project_name,
        execution_date=execution_date,
        gpt_model=GPT_MODEL,
        profile_metadata_file=profile_metadata_file,
        post_file=post_file,
        output_file=stage1_output_file,
        system_prompt_template=arm_cfg["stage1_system_prompt"],
        user_prompt_template=arm_cfg["stage1_user_prompt"],
        llm_response_field="x_digital_twin_stage1_evidence_json",
        interview_type="x_digital_twin_stage1",
        include_profile_info=include_profile_info,
        inject_profile_into_user_prompt=True,
        enable_web_search=enable_web_search,
    )

    # ---- Build Stage 2 user prompts from the Stage 1 evidence sheets ----
    stage1_path = os.path.join(
        base_dir, "../data", project_name, execution_date, stage1_output_file
    )
    stage1_df = pd.read_csv(stage1_path)

    stage2_builder = arm_cfg.get("stage2_user_builder")
    log_dir = os.path.join(
        base_dir, "../data", project_name, execution_date, "randomization_logs"
    )
    if stage2_builder is not None:
        os.makedirs(log_dir, exist_ok=True)

    stage2_user_prompts = []
    for _, row in stage1_df.iterrows():
        evidence = row.get("x_digital_twin_stage1_evidence_json", "")
        if not isinstance(evidence, str):
            evidence = ""
        if stage2_builder is not None:
            # Arm C: randomise option order per subject and log the ordering.
            subject_id = str(row.get("account_id", row.get("custom_id", "")))
            save_log_path = os.path.join(
                log_dir,
                f"randomization_log_{subject_id}{randomization_seed_suffix}.json",
            )
            stage2_user_prompts.append(
                stage2_builder(
                    evidence,
                    subject_id,
                    randomization_seed_suffix=randomization_seed_suffix,
                    save_log_path=save_log_path,
                    shuffle_scope=shuffle_scope,
                    shuffle_keys=shuffle_keys,
                )
            )
        else:
            # Arm B: inject the evidence sheet into the static Stage 2 prompt.
            stage2_user_prompts.append(
                arm_cfg["stage2_user_prompt"].replace("{stage_1_output_json}", evidence)
            )
    stage1_df["x_digital_twin_stage2_user_prompt"] = stage2_user_prompts
    stage1_df.to_csv(stage1_path, index=False)

    # ---- Stage 2: survey-response prediction ----
    perform_profile_interview(
        project_name=project_name,
        execution_date=execution_date,
        gpt_model=GPT_MODEL,
        profile_metadata_file=stage1_output_file,
        post_file=post_file,
        output_file=stage2_output_file,
        system_prompt_template=arm_cfg["stage2_system_prompt"],
        user_prompt_template="",
        user_prompt_field_override="x_digital_twin_stage2_user_prompt",
        llm_response_field="x_digital_twin_stage2_predictions_json",
        interview_type="x_digital_twin_stage2",
        include_profile_info=include_profile_info,
        enable_web_search=enable_web_search,
    )

    # ---- Parse Stage 2 JSON predictions into flat columns ----
    stage2_path = os.path.join(
        base_dir, "../data", project_name, execution_date, stage2_output_file
    )
    stage2_df = pd.read_csv(stage2_path)
    extracted_responses = stage2_df["x_digital_twin_stage2_predictions_json"].apply(
        extract_json_predictions
    )
    stage2_df = pd.concat([stage2_df, extracted_responses], axis=1)

    stage2_df = stage2_df.copy()
    stage2_df["model"] = GPT_MODEL
    stage2_df["treatment_arm"] = treatment_arm
    stage2_df["include_profile_info"] = include_profile_info
    stage2_df["enable_web_search"] = enable_web_search

    stage2_df.to_csv(stage2_path, index=False)

    # Raise only after the output is safely on disk (see the docstring).
    validate_stage2_prediction_keys(stage2_df)

    # Stage 2's file now carries every Stage 1 column forward (evidence JSON,
    # profile fields, the built Stage 2 user prompt) plus its own predictions,
    # so the standalone Stage 1 CSV is a duplicate final artifact. Drop it.
    os.remove(stage1_path)


def positive_int(value: str) -> int:
    """Parse an argparse value that must be a positive integer.

    Args:
        value (str): The raw command-line token.

    Returns:
        int: The parsed value, guaranteed >= 1.

    Raises:
        argparse.ArgumentTypeError: If the token is not an integer, or is < 1.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}")
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {parsed}")
    return parsed


def parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    """Define and parse the pipeline's command-line interface.

    Args:
        argv (list[str] | None): Argument list to parse. ``None`` (default)
            reads ``sys.argv``. Passing a list lets a caller drive the parser
            in-process without spawning a subprocess.

    Returns:
        argparse.Namespace: Parsed arguments. Note ``--option-order-seed-suffix``
        and its legacy alias ``--seed-suffix`` both land on ``seed_suffix``.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run the AIPOP Chile digital-interview pipeline for a chosen "
            "treatment arm."
        )
    )
    parser.add_argument(
        "--treatment-arm",
        choices=sorted(TREATMENT_ARMS.keys()),
        default=DEFAULT_TREATMENT_ARM,
        help=(
            "Experimental prompt condition to run. "
            "baseline=original prompt; a=corrected baseline; "
            "b=two-stage JSON; c=two-stage JSON with randomised options; "
            "d=minimal sparse single call. (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--include-profile-info",
        action=argparse.BooleanOptionalAction,
        default=INCLUDE_PROFILE_INFORMATION,
        help="Include profile information in the prompts (default from config).",
    )
    parser.add_argument(
        "--enable-web-search",
        action=argparse.BooleanOptionalAction,
        default=ENABLE_WEB_SEARCH,
        help="Enable web search during interviews (default from config).",
    )
    parser.add_argument(
        "--skip-profile-search",
        action="store_true",
        default=False,
        help=(
            "Skip Step 1 (profile metadata/post search) and reuse the data "
            "already present in this arm's output folder."
        ),
    )
    parser.add_argument(
        "--num-runs",
        type=positive_int,
        default=1,
        help=(
            "Number of independent repetitions of this arm over the same "
            "sampled respondents. Each repetition writes to its own '_runNN' "
            "output namespace. The pinned model accepts no temperature and the "
            "API exposes no seed, so repetitions are genuinely independent "
            "draws -- which is what makes repeated-run variance measurable. "
            "(default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--run-index-start",
        type=positive_int,
        default=1,
        help=(
            "Index of the first repetition. Use '--num-runs 5 "
            "--run-index-start 6' to extend an existing 5-run study to 10 runs "
            "without re-running the first five. (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--sample-size",
        type=positive_int,
        default=None,
        help=(
            "Number of respondents to draw at random from the roster. Omit to "
            "use the entire roster (the existing behaviour). Requires --seed. "
            "Errors if larger than the roster."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Random seed selecting WHICH RESPONDENTS are interviewed. The same "
            "seed, sample size and roster always yield the same respondents, so "
            "arms and information conditions run as separate commands remain "
            "directly comparable. Samples are nested: at a fixed seed the n=10 "
            "sample is a subset of n=25. NOTE: unrelated to "
            "--option-order-seed-suffix, which reshuffles Arm C's option order."
        ),
    )
    parser.add_argument(
        "--profile-roster",
        default=None,
        help=(
            "Roster CSV listing the accounts to interview (must have an "
            "'account_id' column). Absolute path, or a filename resolved "
            "against data/digital-twin-chile-x/. "
            "(default: final_meta_user_df_sample.csv, 5 accounts)"
        ),
    )
    parser.add_argument(
        "--profile-posts",
        default=None,
        help=(
            "Post corpus CSV to draw each account's posts from. Must cover the "
            "sampled accounts -- the run aborts if any sampled account has no "
            "posts, since an empty post block still produces a prompt that is "
            "sent and billed. (default: test_tweets.csv)"
        ),
    )
    parser.add_argument(
        "--allow-missing-posts",
        action="store_true",
        default=False,
        help=(
            "Proceed even when some sampled accounts have no posts in the post "
            "corpus. Those interviews run with an empty post block."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Resolve sampling, output namespacing and the coverage preflight, "
            "print the plan and the estimated API call count, then exit without "
            "issuing any API call or writing any file."
        ),
    )
    parser.add_argument(
        "--shuffle-scope",
        choices=["nominal", "all"],
        default="nominal",
        help=(
            "Arm C only: which Stage 2 option lists to randomise. "
            "'nominal' (default) shuffles only nominal-scale questions; "
            "'all' also shuffles ordinal scales. Ignored by arms other than "
            "'c', and ignored if --shuffle-keys is given. (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--shuffle-keys",
        default=None,
        help=(
            "Arm C only: comma-separated list of exact question keys to "
            "shuffle (e.g. 'REGION,COMUNA,SEXO'), overriding --shuffle-scope "
            "entirely. Accepts any of Arm C's SHUFFLEABLE_KEYS, including "
            "'COMUNA' (otherwise always canonical order regardless of "
            "scope). Pass the literal value 'all' to shuffle every "
            "SHUFFLEABLE_KEYS question (the split-sample 'shuffle "
            "everything' diagnostic). Omit to use --shuffle-scope instead."
        ),
    )
    parser.add_argument(
        "--option-order-seed-suffix",
        "--seed-suffix",
        dest="seed_suffix",
        default="",
        help=(
            "Arm C only: appended to the per-question OPTION-ORDER shuffle seed "
            "(f'{subject_id}_{key}{seed_suffix}'), so a different suffix "
            "(e.g. '_v2', '_v3') reshuffles independently for repeated-seed "
            "sensitivity/ordering-diagnostic runs. Also appended to the "
            "randomization log filename and the Stage 2 predictions filename "
            "so repeated runs don't overwrite each other. Empty (default) "
            "reproduces the baseline seed. NOTE: this reshuffles ANSWER "
            "OPTIONS, not respondents -- see --seed for respondent sampling. "
            "'--seed-suffix' remains accepted as an alias."
        ),
    )
    return parser.parse_args(argv)


def resolve_corpus_paths(args: argparse.Namespace) -> "tuple[str, str]":
    """Resolve --profile-roster / --profile-posts to absolute paths.

    Each accepts either an absolute path or a bare filename, which is resolved
    against ``data/<PROJECT_NAME>/``. Omitting both preserves the historical
    defaults exactly.

    Args:
        args (argparse.Namespace): Parsed arguments, read for
            ``profile_roster`` and ``profile_posts``.

    Returns:
        tuple[str, str]: Absolute ``(roster_path, posts_path)``.

    Raises:
        SystemExit: If either explicitly-given path does not exist.
    """

    def _resolve(value: str, default: str, label: str) -> str:
        """Resolve one corpus argument to an existing absolute path.

        Args:
            value (str): The flag's value, possibly empty or ``None``.
            default (str): Path to use when the flag was not given.
            label (str): Flag name, used in the error message.

        Returns:
            str: An absolute path that exists on disk.

        Raises:
            SystemExit: If the resolved path does not exist.
        """
        if not value:
            return default
        path = (
            value
            if os.path.isabs(value)
            else os.path.join(base_dir, "../data", PROJECT_NAME, value)
        )
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise SystemExit(f"{label} not found: {path}")
        return path

    return (
        _resolve(args.profile_roster, LOCAL_PROFILE_METADATA_FILE, "--profile-roster"),
        _resolve(args.profile_posts, LOCAL_PROFILE_POST_FILE, "--profile-posts"),
    )


def coverage_preflight(
    account_ids: "list[str]",
    roster_path: str,
    posts_path: str,
    include_profile_info: bool,
    allow_missing_posts: bool,
) -> dict:
    """Fail loudly on the two silent data failures this pipeline permits.

    A roster column that the prompt builder expects but the file lacks becomes
    an empty prompt field (``build_profile_args`` uses ``row.get(col, "")``),
    and an account with no posts becomes an empty post block. Neither raises:
    the prompt is still assembled, sent and billed. So check both up front.

    Args:
        account_ids (list[str]): The sampled accounts about to be interviewed.
        roster_path (str): Roster CSV, checked for the profile columns the
            prompts read.
        posts_path (str): Post corpus CSV, checked for coverage of every
            sampled account.
        include_profile_info (bool): Whether profile fields are in the prompts.
            When False the schema check is moot and a note is printed instead,
            since every prompt is then identical.
        allow_missing_posts (bool): Downgrade partial post coverage from a hard
            failure to a warning.

    Returns:
        dict: ``accounts_without_posts`` (int) and ``missing_profile_columns``
        (list[str]).

    Raises:
        SystemExit: If no sampled account has any post, or if some are missing
            and ``allow_missing_posts`` is False.
    """
    report = {}

    posts = pd.read_csv(posts_path, usecols=["account_id"], low_memory=False)
    covered = set(posts["account_id"].dropna().astype(str).str.strip())
    missing = [a for a in account_ids if a not in covered]
    report["accounts_without_posts"] = len(missing)

    if missing:
        preview = ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
        message = (
            f"{len(missing)} of {len(account_ids)} sampled accounts have zero "
            f"posts in {os.path.basename(posts_path)}: {preview}"
        )
        if len(missing) == len(account_ids):
            raise SystemExit(
                f"ERROR: {message}\n"
                "No sampled account has any post; the post-retrieval step would "
                "produce an empty file and the interview step would then fail. "
                "Pick a post corpus that covers this roster."
            )
        if not allow_missing_posts:
            raise SystemExit(
                f"ERROR: {message}\n"
                "Those interviews would run with an empty post block and still "
                "be billed. Pass --allow-missing-posts to proceed anyway, or "
                "pick a post corpus that covers this roster."
            )
        print(f"WARNING: {message}")
        print("         Proceeding because --allow-missing-posts was passed.")

    roster_columns = set(pd.read_csv(roster_path, nrows=1).columns)
    missing_fields = [c for c in PROFILE_SOURCE_COLUMNS if c not in roster_columns]
    report["missing_profile_columns"] = missing_fields
    if missing_fields and include_profile_info:
        print(
            f"WARNING: {os.path.basename(roster_path)} is missing "
            f"{len(missing_fields)} of the {len(PROFILE_SOURCE_COLUMNS)} profile "
            f"columns the prompts read: {', '.join(missing_fields)}"
        )
        print("         Those fields render blank in every prompt, silently.")

    if not include_profile_info:
        print(
            "NOTE: --no-include-profile-info blanks every profile field, so all "
            f"{len(account_ids)} interviews in this run send a byte-identical "
            "prompt."
        )

    return report


def write_manifest(path: str, payload: dict) -> None:
    """Write a run manifest, never failing the run if it cannot be written.

    Called once before the interviews start (so a crashed run still leaves
    provenance) and again on success. A manifest failure must not take down a
    run whose API calls have already been billed, so errors are caught.

    Args:
        path (str): Destination JSON file.
        payload (dict): Manifest contents.

    Returns:
        None: On failure a warning is printed and the run continues.
    """
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"WARNING: could not write manifest {path}: {exc!r}")


def _git_commit() -> "str | None":
    """Read the repository's current commit hash, best-effort.

    Recorded in each run manifest so a set of results can be tied back to the
    exact prompt templates that produced them.

    Returns:
        str | None: The full commit hash, or ``None`` if git is unavailable,
        the directory is not a repository, or the call times out.
    """
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=os.path.join(base_dir, ".."),
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            or None
        )
    except Exception:
        return None


def _read_custom_id_map(run_dir: str, profile_metadata_file: str) -> "dict | None":
    """Map custom_id -> account_id for this run.

    ``custom_id`` is a positional row index, so it is only meaningful relative
    to a specific (sample, corpus) pair. Recording the mapping makes any join
    that used it repairable; downstream analysis should key on ``account_id``.

    Args:
        run_dir (str): The run's output directory.
        profile_metadata_file (str): Profile metadata CSV filename within it.

    Returns:
        dict | None: ``{custom_id: account_id}``, or ``None`` if the file
        cannot be read -- this is bookkeeping, so it must not fail the run.
    """
    try:
        frame = pd.read_csv(os.path.join(run_dir, profile_metadata_file))
        if "custom_id" in frame.columns and "account_id" in frame.columns:
            return {
                str(k): str(v) for k, v in zip(frame["custom_id"], frame["account_id"])
            }
        return {str(i): str(a) for i, a in enumerate(frame["account_id"])}
    except Exception:
        return None


def run_pipeline(
    *,
    treatment_arm: str,
    include_profile_info: bool,
    enable_web_search: bool,
    skip_profile_search: bool,
    shuffle_scope: str,
    shuffle_keys: "list[str] | None",
    seed_suffix: str,
    roster_path: str,
    posts_path: str,
    sample_account_ids: "list[str] | None" = None,
    sample_metadata: "dict | None" = None,
    sample_tag: str = "",
    run_index: "int | None" = None,
    num_runs: int = 1,
    run_index_start: int = 1,
    argv: "list[str] | None" = None,
    dry_run: bool = False,
) -> str:
    """Execute one full pipeline run for a single arm and information condition.

    Resolves the output namespace, writes the sampled roster and the run
    manifest, retrieves profile data, then dispatches to the interview
    functions for this arm's architecture.

    Args:
        treatment_arm (str): Prompt architecture key, e.g. ``"a"`` or ``"c"``.
        include_profile_info (bool): Whether profile fields and posts are in
            the prompts.
        enable_web_search (bool): Whether to attach the web-search tool. Also
            decides the dispatch path: web-enabled runs go row-wise through the
            Responses API, others through the Batch API.
        skip_profile_search (bool): Reuse profile data already present in this
            namespace instead of retrieving it.
        shuffle_scope (str): Arm C only. ``"nominal"`` or ``"all"``.
        shuffle_keys (list[str] | None): Arm C only. Explicit keys to shuffle.
        seed_suffix (str): Arm C only. Option-order shuffle seed suffix. Not
            the respondent-sampling seed.
        roster_path (str): Absolute path to the full roster CSV.
        posts_path (str): Absolute path to the post corpus CSV.
        sample_account_ids (list[str] | None): Accounts to interview. ``None``
            uses the whole roster.
        sample_metadata (dict | None): Sampling provenance for the manifest.
        sample_tag (str): Subsample identifier for the output namespace.
        run_index (int | None): Repetition index for the output namespace.
            ``None`` omits the ``_runNN`` segment, preserving legacy paths.
        num_runs (int): Total repetitions, recorded in the manifest.
        run_index_start (int): First repetition index, recorded in the manifest.
        argv (list[str] | None): Original command line, recorded in the manifest.
        dry_run (bool): Print the resolved plan and API-call estimate, then
            return without calling the API or writing anything.

    Returns:
        str: The ``execution_date`` namespace this run used.

    Raises:
        SystemExit: If ``skip_profile_search`` is set but this namespace has
            not been populated by a prior run.
        ValueError: If the arm's architecture is unrecognised.
    """
    arm_cfg = TREATMENT_ARMS[treatment_arm]
    architecture = arm_cfg["architecture"]

    # Namespace every output by variant + arm (+ sample + run) so runs never
    # clobber each other.
    execution_date = build_execution_date(
        include_profile_info,
        enable_web_search,
        treatment_arm,
        sample_tag=sample_tag,
        run_index=run_index,
    )
    profile_metadata_file = f"profile_metadata_{execution_date}.csv"
    profile_search_file = f"profile_search_{execution_date}.csv"
    run_dir = os.path.join(base_dir, "../data", PROJECT_NAME, execution_date)

    print(f"Treatment arm       : {treatment_arm} ({arm_cfg['description']})")
    print(f"Architecture        : {architecture}")
    print(f"Include profile info: {include_profile_info}")
    print(f"Enable web search   : {enable_web_search}")
    print(f"Output namespace    : {execution_date}")
    if sample_account_ids is not None:
        print(f"Sampled respondents : {len(sample_account_ids)}")

    if dry_run:
        calls_per_interview = 1 if architecture == ARCH_ONE_CALL_REGEX else 2
        n_subjects = len(sample_account_ids) if sample_account_ids is not None else "all"
        print(f"Output directory    : {os.path.abspath(run_dir)}")
        print(
            f"Estimated API calls : {n_subjects} subjects x "
            f"{calls_per_interview} call(s) = "
            f"{n_subjects * calls_per_interview if isinstance(n_subjects, int) else '?'}"
        )
        return execution_date

    os.makedirs(run_dir, exist_ok=True)

    # Narrow the roster to the sampled accounts. Written to the run directory so
    # each run carries its own audit copy of exactly who was interviewed, and
    # passed as an absolute path (os.path.join discards the earlier components,
    # which is how the driver already supplies these files today).
    roster_for_search = roster_path
    if sample_account_ids is not None:
        sampled_roster = pd.read_csv(roster_path)
        sampled_roster = sampled_roster[
            sampled_roster["account_id"].astype(str).str.strip().isin(sample_account_ids)
        ].reset_index(drop=True)
        roster_for_search = os.path.join(run_dir, f"sample_roster_{execution_date}.csv")
        sampled_roster.to_csv(roster_for_search, index=False)

    manifest_path = os.path.join(run_dir, f"run_manifest_{execution_date}.json")
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "completed_at_utc": None,
        "argv": argv,
        "cwd": os.getcwd(),
        "git_commit": _git_commit(),
        "project_name": PROJECT_NAME,
        "execution_date": execution_date,
        "treatment_arm": treatment_arm,
        "architecture": architecture,
        "arm_description": arm_cfg["description"],
        "include_profile_info": include_profile_info,
        "enable_web_search": enable_web_search,
        "skip_profile_search": skip_profile_search,
        "gpt_model": GPT_MODEL,
        "web_search_country": WEB_SEARCH_COUNTRY,
        "num_parallel_processes": NUM_PARALLEL_PROCESSES,
        "profile_search_start_date": PROFILE_SEARCH_START_DATE,
        "profile_search_end_date": PROFILE_SEARCH_END_DATE,
        "num_posts_per_profile": NUM_POSTS_PER_PROFILE,
        "posts_file": posts_path,
        "sample": dict(
            sample_metadata or {},
            sample_tag=sample_tag,
            account_ids=sample_account_ids,
        ),
        "run": {
            "index": run_index,
            "num_runs": num_runs,
            "run_index_start": run_index_start,
        },
        "arm_c": {
            "seed_suffix": seed_suffix,
            "shuffle_scope": shuffle_scope,
            "shuffle_keys": shuffle_keys,
        },
    }
    write_manifest(manifest_path, manifest)

    # Step 1: Perform profile search of Chile survey participants (metadata + posts)
    if not skip_profile_search:
        print(
            "Step 1: Perform profile search of Chile survey participants "
            "(profile metadata and posts)."
        )
        perform_x_profile_metadata_search(
            project_name=PROJECT_NAME,
            execution_date=execution_date,
            input_file=roster_for_search,
            output_file=profile_metadata_file,
            local_file=roster_path,
        )
        perform_x_profile_search(
            project_name=PROJECT_NAME,
            execution_date=execution_date,
            input_file=roster_for_search,
            output_file=profile_search_file,
            start_date=PROFILE_SEARCH_START_DATE,
            end_date=PROFILE_SEARCH_END_DATE,
            num_posts_per_profile=NUM_POSTS_PER_PROFILE,
            local_file=posts_path,
        )
    else:
        # A fresh run namespace is empty, so the interview step would die on a
        # bare FileNotFoundError deep inside perform_profile_interview. Check
        # here instead, where the message can name the missing file.
        for required in (profile_metadata_file, profile_search_file):
            candidate = os.path.join(run_dir, required)
            if not os.path.exists(candidate):
                raise SystemExit(
                    f"ERROR: --skip-profile-search was passed but {candidate} "
                    "does not exist. Run once without the flag to populate this "
                    "namespace first."
                )
        print("Step 1 skipped (--skip-profile-search); reusing existing profile data.")

    # Step 2+: dispatch on the arm's architecture.
    if architecture == ARCH_TWO_CALL_REGEX:
        entity_output_file = f"post_entity_geographic_interview_{execution_date}.csv"
        voting_output_file = (
            f"post_voting_preference_interview_wo_voting_results_{execution_date}.csv"
        )

        print("Step 2: Entity & geographic interview.")
        conduct_entity_geographic_interview(
            project_name=PROJECT_NAME,
            execution_date=execution_date,
            profile_metadata_file=profile_metadata_file,
            post_file=profile_search_file,
            output_file=entity_output_file,
            system_prompt=arm_cfg["system_prompt"],
            entity_user_prompt=arm_cfg["entity_user_prompt"],
            entity_patterns=arm_cfg["entity_patterns"],
            include_profile_info=include_profile_info,
            enable_web_search=enable_web_search,
            entity_labels=arm_cfg.get("entity_labels"),
        )

        print("Step 3: Voting-preference interview (without voting results).")
        conduct_voting_preference_interview_without_voting_results(
            project_name=PROJECT_NAME,
            execution_date=execution_date,
            profile_metadata_file=entity_output_file,
            post_file=profile_search_file,
            output_file=voting_output_file,
            voting_user_prompt=arm_cfg["voting_user_prompt"],
            voting_patterns=arm_cfg["voting_patterns"],
            treatment_arm=treatment_arm,
            include_profile_info=include_profile_info,
            enable_web_search=enable_web_search,
            voting_labels=arm_cfg.get("voting_labels"),
        )

    elif architecture == ARCH_ONE_CALL_REGEX:
        output_file = f"post_arm_{treatment_arm}_interview_{execution_date}.csv"

        print("Step 2: Single-call sparse interview.")
        conduct_single_call_interview(
            project_name=PROJECT_NAME,
            execution_date=execution_date,
            profile_metadata_file=profile_metadata_file,
            post_file=profile_search_file,
            output_file=output_file,
            system_prompt=arm_cfg["system_prompt"],
            user_prompt=arm_cfg["user_prompt"],
            patterns=arm_cfg["patterns"],
            treatment_arm=treatment_arm,
            include_profile_info=include_profile_info,
            enable_web_search=enable_web_search,
        )

    elif architecture == ARCH_TWO_STAGE_JSON:
        stage1_output_file = f"post_stage1_evidence_{execution_date}.csv"
        stage2_output_file = f"post_stage2_predictions_{execution_date}.csv"

        print("Step 2: Two-stage JSON interview (evidence extraction + prediction).")
        if treatment_arm == "c":
            if shuffle_keys is not None:
                print(f"Shuffle keys         : {shuffle_keys}")
            else:
                print(f"Shuffle scope        : {shuffle_scope}")
            if seed_suffix:
                print(f"Option-order suffix  : {seed_suffix}")
        conduct_two_stage_json_interview(
            project_name=PROJECT_NAME,
            execution_date=execution_date,
            profile_metadata_file=profile_metadata_file,
            post_file=profile_search_file,
            stage1_output_file=stage1_output_file,
            stage2_output_file=stage2_output_file,
            arm_cfg=arm_cfg,
            treatment_arm=treatment_arm,
            include_profile_info=include_profile_info,
            enable_web_search=enable_web_search,
            shuffle_scope=shuffle_scope,
            shuffle_keys=shuffle_keys,
            randomization_seed_suffix=seed_suffix,
        )

    else:
        raise ValueError(
            f"Unknown architecture '{architecture}' for treatment arm "
            f"'{treatment_arm}'."
        )

    manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["custom_id_map"] = _read_custom_id_map(run_dir, profile_metadata_file)
    write_manifest(manifest_path, manifest)

    print("Pipeline complete.")
    return execution_date


def main(argv: "list[str] | None" = None) -> None:
    """Entry point: resolve the sample once, then run each repetition.

    The subsample is drawn a single time and reused for every repetition, so
    repeated runs differ only in the model's sampling -- which is what makes
    repeated-run variance interpretable.

    Args:
        argv (list[str] | None): Argument list. ``None`` reads ``sys.argv``.

    Returns:
        None: Each repetition writes to its own output namespace.

    Raises:
        SystemExit: If ``--sample-size`` is given without ``--seed``, if a
            corpus path does not exist, or if the coverage preflight fails.
    """
    args = parse_args(argv)
    parser_argv = list(argv) if argv is not None else sys.argv[1:]

    if args.sample_size is not None and args.seed is None:
        raise SystemExit(
            "ERROR: --sample-size requires --seed. Recording the seed is what "
            "makes the sampled respondents reproducible across arms, "
            "conditions and repetitions."
        )
    if args.seed is not None and args.sample_size is None:
        print(
            "WARNING: --seed has no effect without --sample-size; the whole "
            "roster is being used."
        )

    roster_path, posts_path = resolve_corpus_paths(args)

    sample_account_ids = None
    sample_metadata = {}
    sample_tag = ""
    if args.sample_size is not None:
        try:
            sample_account_ids, sample_metadata = select_profile_sample(
                roster_path, args.sample_size, args.seed
            )
        except ValueError as exc:
            # Surface a roster/sample-size mismatch the same way as the other
            # up-front validation failures, rather than as a raw traceback.
            raise SystemExit(f"ERROR: {exc}")
        sample_tag = build_sample_tag(args.seed, sample_account_ids)
        print(f"Sample tag          : {sample_tag}")
        coverage_preflight(
            sample_account_ids,
            roster_path,
            posts_path,
            args.include_profile_info,
            args.allow_missing_posts,
        )

    if args.shuffle_keys is None:
        shuffle_keys = None
    elif args.shuffle_keys.strip().lower() == "all":
        shuffle_keys = sorted(SHUFFLEABLE_KEYS)
    else:
        shuffle_keys = [k.strip() for k in args.shuffle_keys.split(",") if k.strip()]

    # Segment the output namespace by run only in "study mode". A bare
    # invocation (1 run, no sample, default start index) therefore keeps writing
    # to exactly the directory it always has. Tying the segment to --sample-size
    # as well as --num-runs avoids the case where `--sample-size N --num-runs 1`
    # writes an unlabelled directory that a later `--num-runs 5` then orphans.
    segmented = (
        args.num_runs > 1 or args.run_index_start != 1 or args.sample_size is not None
    )
    run_indices = (
        list(range(args.run_index_start, args.run_index_start + args.num_runs))
        if segmented
        else [None]
    )

    for position, run_index in enumerate(run_indices, start=1):
        if len(run_indices) > 1:
            print(f"\n=== Run {position}/{len(run_indices)} (index {run_index}) ===")
        execution_date = run_pipeline(
            treatment_arm=args.treatment_arm,
            include_profile_info=args.include_profile_info,
            enable_web_search=args.enable_web_search,
            skip_profile_search=args.skip_profile_search,
            shuffle_scope=args.shuffle_scope,
            shuffle_keys=shuffle_keys,
            seed_suffix=args.seed_suffix,
            roster_path=roster_path,
            posts_path=posts_path,
            sample_account_ids=sample_account_ids,
            sample_metadata=sample_metadata,
            sample_tag=sample_tag,
            run_index=run_index,
            num_runs=args.num_runs,
            run_index_start=args.run_index_start,
            argv=parser_argv,
            dry_run=args.dry_run,
        )
        if len(run_indices) > 1:
            print(f"Run {position}/{len(run_indices)} -> {execution_date}")

    if args.dry_run:
        print("\nDry run: no API calls issued and no files written.")


if __name__ == "__main__":
    main()
