import os, json
import argparse
import pandas as pd
from tqdm import tqdm

tqdm.pandas()
from config.base_config import GPT_MODEL
from config.digital_twin_config import (
    PROJECT_NAME,
    PROFILE_SEARCH_START_DATE,
    PROFILE_SEARCH_END_DATE,
    NUM_POSTS_PER_PROFILE,
    INCLUDE_PROFILE_INFORMATION,
    ENABLE_WEB_SEARCH,
    build_execution_date,
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
)

base_dir = os.path.dirname(os.path.abspath(__file__))
LOCAL_PROFILE_METADATA_FILE = os.path.join(
    base_dir,
    "../data/digital-twin-chile-x/final_meta_user_df_sample.csv",
)
LOCAL_PROFILE_POST_FILE = os.path.join(
    base_dir,
    "../data/digital-twin-chile-x/test_tweets.csv",
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
) -> None:
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
    ].apply(extract_llm_responses)
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
) -> None:
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
    ].apply(extract_llm_responses)
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
    """Single-stage, single-call interview (Arm D).

    The profile data lives in the user prompt (literal injection), and the
    model emits one ``**field: value**`` block per construct, parsed by regex.
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
    ].apply(extract_llm_responses)
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
) -> None:
    """Two-stage evidence-extraction then prediction interview (Arms B and C).

    Stage 1 extracts an evidence sheet (JSON) from the profile. Stage 2 predicts
    the survey answers (JSON) from that evidence sheet. Arm C additionally
    randomises Stage 2 option ordering per subject via its prompt builder.

    Stage 2 inherits the ``enable_web_search`` setting. The evidence-only design
    argues for running Stage 2 without web search; pass --no-enable-web-search to
    keep predictions strictly grounded in the Stage 1 evidence sheet.
    """
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
        base_dir, "../data", project_name, execution_date, "randomisation_logs"
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
            save_log_path = os.path.join(log_dir, f"{subject_id}.json")
            stage2_user_prompts.append(
                stage2_builder(evidence, subject_id, save_log_path=save_log_path)
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


def parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    treatment_arm = args.treatment_arm
    include_profile_info = args.include_profile_info
    enable_web_search = args.enable_web_search
    arm_cfg = TREATMENT_ARMS[treatment_arm]
    architecture = arm_cfg["architecture"]

    # Namespace every output by variant + arm so runs never clobber each other.
    execution_date = build_execution_date(
        include_profile_info, enable_web_search, treatment_arm
    )
    profile_metadata_file = f"profile_metadata_{execution_date}.csv"
    profile_search_file = f"profile_search_{execution_date}.csv"

    print(f"Treatment arm       : {treatment_arm} ({arm_cfg['description']})")
    print(f"Architecture        : {architecture}")
    print(f"Include profile info: {include_profile_info}")
    print(f"Enable web search   : {enable_web_search}")
    print(f"Output namespace    : {execution_date}")

    # Step 1: Perform profile search of Chile survey participants (metadata + posts)
    if not args.skip_profile_search:
        print(
            "Step 1: Perform profile search of Chile survey participants "
            "(profile metadata and posts)."
        )
        perform_x_profile_metadata_search(
            project_name=PROJECT_NAME,
            execution_date=execution_date,
            input_file=LOCAL_PROFILE_METADATA_FILE,
            output_file=profile_metadata_file,
            local_file=LOCAL_PROFILE_METADATA_FILE,
        )
        perform_x_profile_search(
            project_name=PROJECT_NAME,
            execution_date=execution_date,
            input_file=LOCAL_PROFILE_METADATA_FILE,
            output_file=profile_search_file,
            start_date=PROFILE_SEARCH_START_DATE,
            end_date=PROFILE_SEARCH_END_DATE,
            num_posts_per_profile=NUM_POSTS_PER_PROFILE,
            local_file=LOCAL_PROFILE_POST_FILE,
        )
    else:
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
        )

    else:
        raise ValueError(
            f"Unknown architecture '{architecture}' for treatment arm "
            f"'{treatment_arm}'."
        )

    print("Pipeline complete.")
