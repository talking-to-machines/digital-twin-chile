import os, json
import pandas as pd
from tqdm import tqdm
from openai import OpenAI
import os
from typing import List

tqdm.pandas()
from config.base_config import GPT_MODEL
from config.digital_twin_config import (
    PROJECT_NAME,
    PIPELINE_EXECUTION_DATE,
    PROFILE_SEARCH_START_DATE,
    PROFILE_SEARCH_END_DATE,
    PROFILE_METADATA_SEARCH_FILE,
    NUM_POSTS_PER_PROFILE,
    PROFILE_SEARCH_FILE,
    ENTITY_GEOGRAPHIC_INTERVIEW_REGEX_PATTERNS,
    VOTING_PREFERENCE_INTERVIEW_WO_VOTING_RESULTS_REGEX_PATTERNS,
    # VOTING_PREFERENCE_INTERVIEW_WITH_VOTING_RESULTS_REGEX_PATTERNS,
    POST_ENTITY_GEOGRAPHIC_INTERVIEW_FILE,
    POST_VOTING_PREFERENCE_WO_VOTING_RESULTS_INTERVIEW_FILE,
    # POST_VOTING_PREFERENCE_WITH_VOTING_RESULTS_INTERVIEW_FILE,
    INCLUDE_PROFILE_INFORMATION,
    ENABLE_WEB_SEARCH,
)
from src.utils import (
    perform_x_profile_search,
    perform_x_profile_metadata_search,
    extract_llm_responses,
    perform_profile_interview,
    coalesce_columns_by_regex,
)
from prompts.prompt_template import (
    x_digital_twin_system_prompt,
    x_digital_twin_entity_geographic_user_prompt,
    x_digital_twin_voting_preference_wo_voting_results_user_prompt,
    # x_digital_twin_voting_preference_with_voting_results_user_prompt,
)

base_dir = os.path.dirname(os.path.abspath(__file__))
LOCAL_PROFILE_METADATA_FILE = os.path.join(
    base_dir,
    "../data/digital-twin-chile-x/final_meta_user_df.csv",
)
LOCAL_PROFILE_POST_FILE = os.path.join(
    base_dir,
    "../data/digital-twin-chile-x/test_tweets.csv",
)
# PAST_ELECTION_RESULTS_FILE = os.path.join(
#     base_dir,
#     "../data/digital-twin-chile-x/chile_past_election_results.txt",
# )


def conduct_entity_geographic_interview(
    project_name: str,
    execution_date: str,
    profile_metadata_file: str,
    post_file: str,
    output_file: str,
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
        system_prompt_template=x_digital_twin_system_prompt,
        user_prompt_template=x_digital_twin_entity_geographic_user_prompt,
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
        post_interview_results, ENTITY_GEOGRAPHIC_INTERVIEW_REGEX_PATTERNS
    )

    # Format past conversation
    post_interview_results["entity_geographic_interview_history"] = (
        post_interview_results.apply(
            lambda row: json.dumps(
                [
                    {"role": "system", "content": x_digital_twin_system_prompt},
                    {
                        "role": "user",
                        "content": x_digital_twin_entity_geographic_user_prompt,
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


# def upload_vector_store(
#     file_path: str,
#     vector_store_name: str,
# ) -> List[str]:
#     if not os.path.isfile(file_path):
#         raise FileNotFoundError(f"File not found: {file_path}")

#     client = OpenAI()

#     # 1) Find or create the vector store by name
#     vs_id = None
#     cursor = None
#     while True:
#         page = (
#             client.vector_stores.list(limit=100, after=cursor)
#             if cursor
#             else client.vector_stores.list(limit=100)
#         )
#         for vs in page.data:
#             if getattr(vs, "name", "") == vector_store_name:
#                 vs_id = vs.id
#                 break
#         if vs_id or not getattr(page, "has_more", False):
#             break
#         cursor = getattr(page, "last_id", None)

#     if not vs_id:
#         vs = client.vector_stores.create(name=vector_store_name)
#         vs_id = vs.id

#     # 2) Skip upload when a file with the same filename is already attached
#     basename = os.path.basename(file_path)
#     cursor = None
#     while True:
#         files_page = client.vector_stores.files.list(
#             vector_store_id=vs_id, limit=100, after=cursor
#         )
#         for f in files_page.data:
#             # Try to read filename directly; if absent, retrieve file metadata
#             fname = getattr(f, "filename", None)
#             if not fname:
#                 try:
#                     meta = client.files.retrieve(f.id)
#                     fname = getattr(meta, "filename", None) or getattr(
#                         meta, "name", None
#                     )
#                 except Exception:
#                     fname = None
#             if fname == basename:
#                 return [vs_id]
#         if not getattr(files_page, "has_more", False):
#             break
#         cursor = getattr(files_page, "last_id", None)

#     # 3) Upload and wait until indexing completes
#     with open(file_path, "rb") as fp:
#         client.vector_stores.file_batches.upload_and_poll(
#             vector_store_id=vs_id,
#             files=[fp],
#         )

#     return [vs_id]


def conduct_voting_preference_interview_without_voting_results(
    project_name: str,
    execution_date: str,
    profile_metadata_file: str,
    post_file: str,
    output_file: str,
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
        user_prompt_template=x_digital_twin_voting_preference_wo_voting_results_user_prompt,
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
        VOTING_PREFERENCE_INTERVIEW_WO_VOTING_RESULTS_REGEX_PATTERNS,
    )

    # Include LLM model information
    post_interview_results = post_interview_results.copy()
    post_interview_results["model"] = GPT_MODEL
    post_interview_results["include_profile_info"] = include_profile_info
    post_interview_results["enable_web_search"] = enable_web_search

    # # Format past conversation
    # post_interview_results["voting_preference_wo_voting_results_history"] = (
    #     post_interview_results.apply(
    #         lambda row: json.dumps(
    #             json.loads(row["entity_geographic_interview_history"])
    #             + [
    #                 {"role": "system", "content": x_digital_twin_system_prompt},
    #                 {
    #                     "role": "user",
    #                     "content": x_digital_twin_voting_preference_wo_voting_results_user_prompt,
    #                 },
    #                 {
    #                     "role": "assistant",
    #                     "content": row[
    #                         "x_digital_twin_voting_preference_wo_voting_results_llm_response"
    #                     ],
    #                 },
    #             ],
    #             ensure_ascii=False,
    #             separators=(",", ":"),
    #         ),
    #         axis=1,
    #     )
    # )

    # Save formatted interview results
    post_interview_results.to_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file),
        index=False,
    )


# def conduct_voting_preference_interview_with_voting_results(
#     project_name: str,
#     execution_date: str,
#     profile_metadata_file: str,
#     post_file: str,
#     output_file: str,
#     include_profile_info: bool = True,
#     enable_web_search: bool = True,
# ) -> None:
#     vector_store_ids = upload_vector_store(
#         PAST_ELECTION_RESULTS_FILE,
#         vector_store_name="digital-twin-chile-past-voting-results",
#     )

#     perform_profile_interview(
#         project_name=project_name,
#         execution_date=execution_date,
#         gpt_model=GPT_MODEL,
#         profile_metadata_file=profile_metadata_file,
#         post_file=post_file,
#         output_file=output_file,
#         system_prompt_template="",
#         user_prompt_template=x_digital_twin_voting_preference_with_voting_results_user_prompt,
#         llm_response_field="x_digital_twin_voting_preference_with_voting_results_llm_response",
#         interview_type="x_digital_twin_voting_preference_with_voting_results",
#         history_field="voting_preference_wo_voting_results_history",
#         vector_store_ids=vector_store_ids,
#         include_profile_info=include_profile_info,
#         enable_web_search=enable_web_search,
#     )

#     # Preprocess post interview results
#     post_interview_results = pd.read_csv(
#         os.path.join(base_dir, "../data", project_name, execution_date, output_file)
#     )
#     extracted_responses = post_interview_results[
#         "x_digital_twin_voting_preference_with_voting_results_llm_response"
#     ].apply(extract_llm_responses)
#     post_interview_results = pd.concat(
#         [post_interview_results, extracted_responses], axis=1
#     )
#     # Merge identical columns from interview response
#     post_interview_results = coalesce_columns_by_regex(
#         post_interview_results,
#         VOTING_PREFERENCE_INTERVIEW_WITH_VOTING_RESULTS_REGEX_PATTERNS,
#     )

#     # Include LLM model information
#     post_interview_results = post_interview_results.copy()
#     post_interview_results["model"] = GPT_MODEL

#     # Save formatted interview results
#     post_interview_results.to_csv(
#         os.path.join(base_dir, "../data", project_name, execution_date, output_file),
#         index=False,
#     )


if __name__ == "__main__":
    # Step 1: Perform profile search of Chile survey participants (profile metadata and posts)
    print(
        "Step 1: Perform profile search of Chile survey participants (profile metadata and posts)."
    )
    perform_x_profile_metadata_search(
        project_name=PROJECT_NAME,
        execution_date=PIPELINE_EXECUTION_DATE,
        input_file=LOCAL_PROFILE_METADATA_FILE,
        output_file=PROFILE_METADATA_SEARCH_FILE,
        local_file=LOCAL_PROFILE_METADATA_FILE,
    )
    perform_x_profile_search(
        project_name=PROJECT_NAME,
        execution_date=PIPELINE_EXECUTION_DATE,
        input_file=LOCAL_PROFILE_METADATA_FILE,
        output_file=PROFILE_SEARCH_FILE,
        start_date=PROFILE_SEARCH_START_DATE,
        end_date=PROFILE_SEARCH_END_DATE,
        num_posts_per_profile=NUM_POSTS_PER_PROFILE,
        local_file=LOCAL_PROFILE_POST_FILE,
    )

    # Step 2: Perform initial interview to idenitfy entity and geographic information
    print(
        "Step 2: Perform initial interview to idenitfy entity and geographic information."
    )
    conduct_entity_geographic_interview(
        project_name=PROJECT_NAME,
        execution_date=PIPELINE_EXECUTION_DATE,
        profile_metadata_file=PROFILE_METADATA_SEARCH_FILE,
        post_file=PROFILE_SEARCH_FILE,
        output_file=POST_ENTITY_GEOGRAPHIC_INTERVIEW_FILE,
        include_profile_info=INCLUDE_PROFILE_INFORMATION,
        enable_web_search=ENABLE_WEB_SEARCH,
    )

    # Step 3: Perform digital election polling of Chile survey participants without voting results
    print(
        "Step 3: Perform digital election polling of Chile survey participants without voting results."
    )
    conduct_voting_preference_interview_without_voting_results(
        project_name=PROJECT_NAME,
        execution_date=PIPELINE_EXECUTION_DATE,
        profile_metadata_file=POST_ENTITY_GEOGRAPHIC_INTERVIEW_FILE,
        post_file=PROFILE_SEARCH_FILE,
        output_file=POST_VOTING_PREFERENCE_WO_VOTING_RESULTS_INTERVIEW_FILE,
        include_profile_info=INCLUDE_PROFILE_INFORMATION,
        enable_web_search=ENABLE_WEB_SEARCH,
    )

    # # Step 4: Perform digital election polling of Chile survey participants with voting results
    # print(
    #     "Step 4: Perform digital election polling of Chile survey participants with voting results."
    # )
    # conduct_voting_preference_interview_with_voting_results(
    #     project_name=PROJECT_NAME,
    #     execution_date=PIPELINE_EXECUTION_DATE,
    #     profile_metadata_file=POST_VOTING_PREFERENCE_WO_VOTING_RESULTS_INTERVIEW_FILE,
    #     post_file=PROFILE_SEARCH_FILE,
    #     output_file=POST_VOTING_PREFERENCE_WITH_VOTING_RESULTS_INTERVIEW_FILE,
    #     include_profile_info=INCLUDE_PROFILE_INFORMATION,
    #     enable_web_search=ENABLE_WEB_SEARCH,
    # )
