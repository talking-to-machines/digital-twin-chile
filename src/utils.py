import requests, re, json, time, ast, os, warnings
import pandas as pd

pd.set_option("future.no_silent_downcasting", True)
from requests.auth import HTTPBasicAuth
from datetime import datetime, timezone
from tqdm import tqdm
from tqdm.auto import tqdm as tqdm_auto

tqdm.pandas()

from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor
from prompts.prompt_template import x_tweet_prompt_template
from config.base_config import (
    OPENAI_API_KEY,
    X_API_USERNAME,
    X_API_PASSWORD,
    NUM_PARALLEL_PROCESSES,
)
from config.digital_twin_config import (
    WEB_SEARCH_COUNTRY,
)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
base_dir = os.path.dirname(os.path.abspath(__file__))


def construct_system_prompt(
    row: pd.Series,
    system_prompt_template: str,
    interview_type: str,
    include_profile_info: bool = True,
) -> str:
    if include_profile_info:
        if interview_type.startswith("x"):
            profile_args = {
                "profile_picture": row.get("profilePicture", ""),
                "name": row.get("name", ""),
                "account_id": row.get("account_id", ""),
                "location": row.get("location", ""),
                "description": row.get("description", ""),
                "url": row.get("url", ""),
                "created_at": row.get("createdAt", ""),
                "is_verified": row.get("isVerified", ""),
                "is_blue_verified": row.get("isBlueVerified", ""),
                "protected": row.get("protected", ""),
                "followers": row.get("followers", ""),
                "following": row.get("following", ""),
                "statuses_count": row.get("statusesCount", ""),
                "favourites_count": row.get("favouritesCount", ""),
                "media_count": row.get("mediaCount", ""),
                "tweets": row.get("posts_combined", ""),
            }

        else:
            profile_args = {}
    else:
        profile_args = {
            "profile_picture": "",
            "name": "",
            "account_id": "",
            "location": "",
            "description": "",
            "url": "",
            "created_at": "",
            "is_verified": "",
            "is_blue_verified": "",
            "protected": "",
            "followers": "",
            "following": "",
            "statuses_count": "",
            "favourites_count": "",
            "media_count": "",
            "tweets": "",
        }

    return system_prompt_template.format(**profile_args)


def construct_user_prompt(
    row: pd.Series, user_prompt_template: str, interview_type: str
) -> str:

    return user_prompt_template


def extract_llm_responses(text, substring_exclusion_list: list = []) -> pd.Series:
    # Split the text by double newlines to separate different questions
    questions_blocks = re.split(r"(?=\*\*question:)", text)
    questions_blocks = [
        block
        for block in questions_blocks
        if block
        and not any(substring in block for substring in substring_exclusion_list)
    ]  # remove blocks containing stock recommendations

    # Initialize lists to store the extracted data
    questions_list = []
    explanations_list = []
    symbols_list = []
    categories_list = []
    speculations_list = []
    values_list = []
    response_list = []
    stock_ticker_list = []
    recommendation_list = []
    confidence_list = []
    expected_holding_period_list = []
    primary_catalyst_type_list = []

    # Define regex patterns for each field
    question_pattern = r"\*\*question: (.*?)\*\*"
    explanation_pattern = r"\*\*explanation: (.*?)\*\*"
    symbol_pattern = r"\*\*symbol: (.*?)\*\*"
    category_pattern = r"\*\*category: (.*?)\*\*"
    speculation_pattern = r"\*\*speculation: (.*?)\*\*"
    value_pattern = r"\*\*value: (.*?)\*\*"
    response_pattern = r"\*\*response: (.*?)\*\*"
    stock_ticker_pattern = r"\*\*stock ticker: (.*?)\*\*"
    recommendation_pattern = r"\*\*recommendation: (.*?)\*\*"
    confidence_pattern = r"\*\*confidence: (.*?)\*\*"
    expected_holding_period_pattern = r"\*\*expected holding period: (.*?)\*\*"
    primary_catalyst_type_pattern = r"\*\*primary catalyst type: (.*?)\*\*"

    # Iterate through each question block and extract the fields
    for block in questions_blocks:
        if pd.isnull(block) or not block:
            continue
        question = re.search(question_pattern, block, re.DOTALL)
        explanation = re.search(explanation_pattern, block, re.DOTALL)
        symbol = re.search(symbol_pattern, block, re.DOTALL)
        category = re.search(category_pattern, block, re.DOTALL)
        speculation = re.search(speculation_pattern, block, re.DOTALL)
        value = re.search(value_pattern, block, re.DOTALL)
        response = re.search(response_pattern, block, re.DOTALL)
        stock_ticker = re.search(stock_ticker_pattern, block, re.DOTALL)
        recommendation = re.search(recommendation_pattern, block, re.DOTALL)
        confidence = re.search(confidence_pattern, block, re.DOTALL)
        expected_holding_period = re.search(
            expected_holding_period_pattern, block, re.DOTALL
        )
        primary_catalyst_type = re.search(
            primary_catalyst_type_pattern, block, re.DOTALL
        )

        questions_list.append(question.group(1).replace("”", "") if question else None)
        explanations_list.append(explanation.group(1) if explanation else None)
        symbols_list.append(symbol.group(1) if symbol else None)
        categories_list.append(category.group(1) if category else None)
        speculations_list.append(speculation.group(1) if speculation else None)
        values_list.append(value.group(1) if value else None)
        response_list.append(response.group(1) if response else None)
        stock_ticker_list.append(stock_ticker.group(1) if stock_ticker else None)
        recommendation_list.append(recommendation.group(1) if recommendation else None)
        confidence_list.append(confidence.group(1) if confidence else None)
        expected_holding_period_list.append(
            expected_holding_period.group(1) if expected_holding_period else None
        )
        primary_catalyst_type_list.append(
            primary_catalyst_type.group(1) if primary_catalyst_type else None
        )

    # Create a DataFrame
    data = {
        "question": questions_list,
        "explanation": explanations_list,
        "symbol": symbols_list,
        "category": categories_list,
        "speculation": speculations_list,
        "value": values_list,
        "response": response_list,
        "stock_ticker": stock_ticker_list,
        "recommendation": recommendation_list,
        "confidence": confidence_list,
        "expected_holding_period": expected_holding_period_list,
        "primary_catalyst_type": primary_catalyst_type_list,
    }
    df = pd.DataFrame(data)

    # Flatten the DataFrame into a single Series
    flattened_series = pd.Series()
    for _, row in df.iterrows():
        question_prefix = row["question"]
        if row["explanation"]:
            flattened_series[f"{question_prefix} - explanation"] = row["explanation"]
        if row["symbol"]:
            flattened_series[f"{question_prefix} - symbol"] = row["symbol"]
        if row["category"]:
            flattened_series[f"{question_prefix} - category"] = row["category"]
        if row["speculation"]:
            flattened_series[f"{question_prefix} - speculation"] = row["speculation"]
        if row["value"]:
            flattened_series[f"{question_prefix} - value"] = row["value"]
        if row["response"]:
            flattened_series[f"{question_prefix} - response"] = row["response"]
        if row["stock_ticker"]:
            flattened_series[f"{question_prefix} - stock ticker"] = row["stock_ticker"]
        if row["recommendation"]:
            flattened_series[f"{question_prefix} - recommendation"] = row[
                "recommendation"
            ]
        if row["confidence"]:
            flattened_series[f"{question_prefix} - confidence"] = row["confidence"]
        if row["expected_holding_period"]:
            flattened_series[f"{question_prefix} - expected holding period"] = row[
                "expected_holding_period"
            ]
        if row["primary_catalyst_type"]:
            flattened_series[f"{question_prefix} - primary catalyst type"] = row[
                "primary_catalyst_type"
            ]

    return flattened_series


def coalesce_columns_by_regex(data: pd.DataFrame, regex_list: list) -> pd.DataFrame:
    """
    Coalesces columns in a DataFrame that match any of the provided regex patterns.
    For each regex pattern in `regex_list`, finds all columns whose names match the pattern (case-insensitive).
    Among the matching columns, retains the one with the fewest missing values, and fills its missing values
    using the next best matching columns (row-wise, using backfill). All other matching columns are dropped.

    Parameters:
        data (pd.DataFrame): The input DataFrame whose columns are to be coalesced.
        regex_list (list): A list of regex patterns (strings) to match column names.

    Returns:
        pd.DataFrame: The DataFrame with coalesced columns, where for each pattern only one column remains,
        containing the most complete set of values from the original matching columns.
    """
    for pattern in regex_list:
        compiled_pattern = re.compile(pattern, flags=re.IGNORECASE)
        matching_cols = [col for col in data.columns if compiled_pattern.search(col)]
        if not matching_cols:
            continue

        # Sort matching columns by null count (fewest nulls first)
        sorted_cols = sorted(matching_cols, key=lambda col: data[col].isna().sum())

        # Fill in missing values in the best column using bfill along row-wise for sorted matching columns
        retained_col = sorted_cols[0]
        data[retained_col] = data[sorted_cols].bfill(axis=1).iloc[:, 0]

        # Drop all other matching columns
        cols_to_drop = sorted_cols[1:]
        data = data.drop(columns=cols_to_drop)
    return data


def _coerce_history(x):
    # Accept list or JSON string; return list[{"role","content"}]
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return []
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return []
    return list(x)


def messages_to_input(messages: list) -> str:
    """
    Convert a list of chat messages (each a dict with 'role' and 'content')
    into a single transcript string for the Responses API 'input'.
    """
    lines = []
    for m in messages:
        role = str(m.get("role", "")).upper()
        content = str(m.get("content", "")).strip()
        if content:  # skip empty
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def create_batch_file(
    prompts: pd.DataFrame,
    project_name: str,
    execution_date: str,
    gpt_model: str,
    system_prompt_field: str,
    user_prompt_field: str = "question_prompt",
    history_field: str = None,
    batch_file_name: str = "batch_input.jsonl",
    vector_store_ids: list = [],
) -> str:
    # Creating an array of json tasks
    tasks = []

    for i in range(len(prompts)):
        custom_id = f"{prompts.loc[i, 'custom_id']}"
        sys_txt = (
            str(prompts.loc[i, system_prompt_field])
            if system_prompt_field in prompts.columns
            else ""
        )

        user_txt = (
            str(prompts.loc[i, user_prompt_field])
            if user_prompt_field in prompts.columns
            else ""
        )

        history = _coerce_history(
            prompts.get(history_field, [None])[i]
            if history_field in prompts.columns
            else []
        )

        # Build messages
        messages = []
        if sys_txt:
            messages.append({"role": "system", "content": sys_txt})

        if history:
            for m in history:
                r, c = m.get("role", "user"), m.get("content", "")
                messages.append({"role": r, "content": c})

        messages.append({"role": "user", "content": user_txt})

        if gpt_model.startswith("gpt-4"):
            if vector_store_ids:
                task = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": {
                        "model": gpt_model,
                        "temperature": 0,
                        "input": messages_to_input(messages),
                        "tools": [
                            {
                                "type": "file_search",
                                "vector_store_ids": vector_store_ids,
                            }
                        ],
                    },
                }

            else:
                task = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": gpt_model,
                        "temperature": 0,
                        "messages": messages,
                    },
                }

        elif gpt_model.startswith("gpt-5"):
            if vector_store_ids:
                task = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": {
                        "model": gpt_model,
                        "input": messages_to_input(messages),
                        "tools": [
                            {
                                "type": "file_search",
                                "vector_store_ids": vector_store_ids,
                            }
                        ],
                    },
                }

            else:
                task = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": gpt_model,
                        "messages": messages,
                    },
                }
        else:
            raise ValueError(f"Unsupported GPT model: {gpt_model}")

        tasks.append(task)

    # Creating batch file
    with open(
        f"{base_dir}/../data/{project_name}/{execution_date}/batch-files/{batch_file_name}",
        "w",
    ) as file:
        for obj in tasks:
            file.write(json.dumps(obj) + "\n")

    return batch_file_name


def batch_query(
    project_name: str,
    execution_date: str,
    batch_input_file_dir: str,
    batch_output_file_dir: str,
    vector_store_ids: list = [],
) -> pd.DataFrame:
    # Upload batch input file
    batch_file = openai_client.files.create(
        file=open(
            f"{base_dir}/../data/{project_name}/{execution_date}/batch-files/{batch_input_file_dir}",
            "rb",
        ),
        purpose="batch",
    )

    # Create batch job
    if vector_store_ids:
        batch_job = openai_client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/responses",
            completion_window="24h",
        )
    else:
        batch_job = openai_client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )

    # Check batch status
    while True:
        batch_job = openai_client.batches.retrieve(batch_job.id)
        print(f"Batch job status: {batch_job.status}")
        if batch_job.status == "completed":
            break
        elif batch_job.status == "failed":
            raise Exception("Batch job failed.")
        else:
            # Wait for 5 minutes before checking again
            time.sleep(300)

    # Retrieve batch results
    result_file_id = batch_job.output_file_id
    results = openai_client.files.content(result_file_id).content

    # Save the batch output
    with open(
        f"{base_dir}/../data/{project_name}/{execution_date}/batch-files/{batch_output_file_dir}",
        "wb",
    ) as file:
        file.write(results)

    # Loading data from saved output file
    response_list = []
    with open(
        f"{base_dir}/../data/{project_name}/{execution_date}/batch-files/{batch_output_file_dir}",
        "r",
    ) as file:
        for line in file:
            # Parsing the JSON result string into a dict
            result = json.loads(line.strip())

            if vector_store_ids:
                try:
                    query_response = ""
                    for idx in range(len(result["response"]["body"]["output"])):
                        if (
                            result["response"]["body"]["output"][idx].get("content", "")
                            == ""
                        ):
                            continue
                        else:
                            query_response = result["response"]["body"]["output"][idx][
                                "content"
                            ][0]["text"]
                            break

                    if query_response == "":
                        warnings.warn(
                            f"No query response found in Custom ID: {result['custom_id']}. Returning empty response."
                        )
                    response_list.append(
                        {
                            "custom_id": f'{result["custom_id"]}',
                            "query_response": query_response,
                        }
                    )

                except Exception as e:
                    warnings.warn(
                        f"No query response found in Custom ID: {result["custom_id"]}. Returning empty response."
                    )
                    response_list.append(
                        {
                            "custom_id": f'{result["custom_id"]}',
                            "query_response": "",
                        }
                    )

            else:
                response_list.append(
                    {
                        "custom_id": f'{result["custom_id"]}',
                        "query_response": result["response"]["body"]["choices"][0][
                            "message"
                        ]["content"],
                    }
                )

    return pd.DataFrame(response_list)


def extract_tagged_users(tagged_str: str, is_tiktok: bool = True) -> str:
    """
    Extracts user handles from a string representation of a list of tagged users.

    Args:
        tagged_str (str): A string representation of a list of dictionaries,
                          where each dictionary contains a "user_handle" key.
        is_tiktok (bool): A boolean indicating whether the tagged users are from TikTok.

    Returns:
        str: A comma-separated string of user handles. If the input is invalid
             or an error occurs, an empty string is returned.
    """
    try:
        user_list = []
        tagged_list = ast.literal_eval(tagged_str)
        for tag in tagged_list:
            if is_tiktok:
                user_list.append(tag.get("user_handle", ""))
            else:  # For X (formerly Twitter)
                user_list.append(tag.get("profile_name", ""))

        return ", ".join([user for user in user_list if user != ""])

    except Exception as e:
        return ""


def extract_hashtags(hashtags_str: str) -> str:
    """
    Extracts hashtags from a raw string representation of a list og hashtags.
    Args:
        hashtags_str (str): A string representation of a list of hashtags.
    Returns:
        str: A comma-separated string of hashtag names. If an error occurs,
             an empty string is returned.
    """
    try:
        hashtags_list = ast.literal_eval(hashtags_str)
        return ", ".join([hashtag for hashtag in hashtags_list if hashtag != ""])

    except Exception as e:
        return ""


def extract_tweets(profile_id: str, tweet_metadata: pd.DataFrame) -> str:
    # Filter the rows where profile_id matches
    filtered_tweets = tweet_metadata[tweet_metadata["account_id"] == profile_id].copy()

    # Sort the filtered tweets by creation time from latest to oldest
    filtered_tweets = filtered_tweets.sort_values(
        by="createdAt", ascending=False
    ).reset_index(drop=True)

    # Join the list of tweets into a single string, separated by newlines
    tweets_list = []
    for i in range(len(filtered_tweets)):
        tweets_list += [
            x_tweet_prompt_template.format(
                created_at=(
                    filtered_tweets.loc[i, "createdAt"]
                    if "createdAt" in filtered_tweets.columns
                    else ""
                ),
                text=(
                    filtered_tweets.loc[i, "text"]
                    if "text" in filtered_tweets.columns
                    else ""
                ),
                like_count=(
                    filtered_tweets.loc[i, "likeCount"]
                    if "likeCount" in filtered_tweets.columns
                    else ""
                ),
                view_count=(
                    filtered_tweets.loc[i, "viewCount"]
                    if "viewCount" in filtered_tweets.columns
                    else ""
                ),
                retweet_count=(
                    filtered_tweets.loc[i, "retweetCount"]
                    if "retweetCount" in filtered_tweets.columns
                    else ""
                ),
                reply_count=(
                    filtered_tweets.loc[i, "replyCount"]
                    if "replyCount" in filtered_tweets.columns
                    else ""
                ),
                quote_count=(
                    filtered_tweets.loc[i, "quoteCount"]
                    if "quoteCount" in filtered_tweets.columns
                    else ""
                ),
                bookmark_count=(
                    filtered_tweets.loc[i, "bookmarkCount"]
                    if "bookmarkCount" in filtered_tweets.columns
                    else ""
                ),
                lang=(
                    filtered_tweets.loc[i, "lang"]
                    if "lang" in filtered_tweets.columns
                    else ""
                ),
                tagged_users=(
                    filtered_tweets.loc[i, "tagged_users"]
                    if "tagged_users" in filtered_tweets.columns
                    else ""
                ),
                hashtags=(
                    filtered_tweets.loc[i, "hashtags"]
                    if "hashtags" in filtered_tweets.columns
                    else ""
                ),
            )
        ]

    return "\n\n".join(tweets_list)


def perform_profile_interview(
    project_name: str,
    execution_date: str,
    gpt_model: str,
    profile_metadata_file: str,
    post_file: str,
    output_file: str,
    system_prompt_template: str,
    user_prompt_template: str,
    llm_response_field: str,
    interview_type: str,
    history_field: str = None,
    vector_store_ids: list = [],
    include_profile_info: bool = True,
    use_row_query: bool = False,
    enable_web_search: bool = False,
) -> None:
    # Create the project subfolder within the data folder if it does not exist
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base_dir, "../data"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "../data", project_name), exist_ok=True)
    os.makedirs(
        os.path.join(base_dir, "../data", project_name, execution_date), exist_ok=True
    )

    # Load profile and post metadata
    profile_metadata = pd.read_csv(
        os.path.join(
            base_dir, "../data", project_name, execution_date, profile_metadata_file
        )
    )
    post_metadata = pd.read_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, post_file),
        on_bad_lines="skip",
    )
    if "warning_code" in post_metadata.columns:
        post_metadata = post_metadata[
            post_metadata["warning_code"] != "dead_page"
        ].reset_index(drop=True)
    if "error_code" in post_metadata.columns:
        post_metadata = post_metadata[
            post_metadata["error_code"] != "crawl_failed"
        ].reset_index(drop=True)

    # Generate system and user prompts
    if interview_type.startswith("x"):
        try:
            post_metadata["createdAt"] = pd.to_datetime(
                post_metadata["createdAt"], format="%a %b %d %H:%M:%S %z %Y"
            )
        except ValueError:
            post_metadata["createdAt"] = pd.to_datetime(post_metadata["createdAt"])
        profile_metadata["posts_combined"] = profile_metadata["account_id"].apply(
            extract_tweets, args=(post_metadata,)
        )
    else:
        raise ValueError(f"Interview type: {interview_type} not supported.")

    if system_prompt_template:
        profile_metadata[f"{interview_type}_system_prompt"] = profile_metadata.apply(
            construct_system_prompt,
            args=(system_prompt_template, interview_type, include_profile_info),
            axis=1,
        )
    profile_metadata[f"{interview_type}_user_prompt"] = profile_metadata.apply(
        construct_user_prompt, args=(user_prompt_template, interview_type), axis=1
    )

    # Generate custom ids
    if "custom_id" in profile_metadata.columns:
        profile_metadata.drop(columns="custom_id", inplace=True)

    profile_metadata = profile_metadata.reset_index(drop=False)
    profile_metadata.rename(columns={"index": "custom_id"}, inplace=True)

    # Create folder to contain batch files
    os.makedirs(
        os.path.join(base_dir, "../data", project_name, execution_date, "batch-files"),
        exist_ok=True,
    )

    if (
        use_row_query or enable_web_search
    ):  # When performing row-wise queries or enabling web search
        profile_metadata_with_responses = profile_metadata.copy()
        row_query_args = [
            f"{interview_type}_system_prompt",
            f"{interview_type}_user_prompt",
            history_field,
            gpt_model,
            enable_web_search,
            vector_store_ids,
        ]

        # Choose how many parallel calls you want (tune for your rate limits)
        max_workers = NUM_PARALLEL_PROCESSES

        # Prepare rows in order so results line up with the DataFrame
        rows = [row for _, row in profile_metadata.iterrows()]

        def run_row_query(row):
            # row_query(row, args=(...)) matches your previous progress_apply usage
            return row_query(
                row,
                args=(row_query_args,),
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(
                tqdm_auto(executor.map(run_row_query, rows), total=len(rows))
            )

        # Assign results back to the DataFrame in the same order
        profile_metadata_with_responses[llm_response_field] = results

    else:  # Perform batch queries to save cost
        # Perform batch query for survey questions
        create_batch_file(
            profile_metadata,
            project_name=project_name,
            execution_date=execution_date,
            gpt_model=gpt_model,
            system_prompt_field=f"{interview_type}_system_prompt",
            user_prompt_field=f"{interview_type}_user_prompt",
            history_field=history_field,
            batch_file_name="batch_input.jsonl",
            vector_store_ids=vector_store_ids,
        )

        llm_responses = batch_query(
            project_name=project_name,
            execution_date=execution_date,
            batch_input_file_dir="batch_input.jsonl",
            batch_output_file_dir="batch_output.jsonl",
            vector_store_ids=vector_store_ids,
        )
        llm_responses.rename(
            columns={"query_response": llm_response_field}, inplace=True
        )

        # Merge LLM response with original dataset
        profile_metadata["custom_id"] = profile_metadata["custom_id"].astype("int64")
        llm_responses["custom_id"] = llm_responses["custom_id"].astype("int64")
        profile_metadata_with_responses = pd.merge(
            left=profile_metadata,
            right=llm_responses[["custom_id", llm_response_field]],
            on="custom_id",
        )

    # Save profile metadata after analysis into CSV file
    profile_metadata_with_responses.to_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file),
        index=False,
    )


def row_query(row: pd.Series, args: list) -> str:
    system_prompt = row[args[0][0]]
    user_prompt = row[args[0][1]]
    history_field = args[0][2]
    gpt_model = args[0][3]
    enable_web_search = args[0][4]
    vector_store_ids = args[0][5]

    # Skip if system_prompt/user_prompt is empty or NaN (depending on your logic)
    if not isinstance(system_prompt, str) or not isinstance(user_prompt, str):
        return ""

    query_parameters = {
        "model": gpt_model,
    }

    if history_field and history_field in row.index:
        history = row[history_field]
        if isinstance(history, str):
            try:
                history = json.loads(history)
            except Exception:
                history = []
        if isinstance(history, list) and history:
            input = []
            # messages.append({"role": "system", "content": system_prompt})
            for m in history:
                r, c = m.get("role", "user"), m.get("content", "")
                input.append({"role": r, "content": c})

            if system_prompt and system_prompt in row.index:
                input.append({"role": "system", "content": row[system_prompt]})

            input.append({"role": "user", "content": row[user_prompt]})
        else:
            input = [
                {"role": "system", "content": row[system_prompt]},
                {"role": "user", "content": row[user_prompt]},
            ]
    else:
        input = [
            {"role": "system", "content": row[system_prompt]},
            {"role": "user", "content": row[user_prompt]},
        ]
    query_parameters["input"] = input

    if vector_store_ids and enable_web_search:
        query_parameters["tools"] = [
            {
                "type": "web_search",
                "search_context_size": "medium",
                "user_location": {"type": "approximate", "country": WEB_SEARCH_COUNTRY},
            },
            {
                "type": "file_search",
                "vector_store_ids": vector_store_ids,
            },
        ]
        query_parameters["tool_choice"] = "required"

    elif vector_store_ids:
        query_parameters["tools"] = [
            {
                "type": "file_search",
                "vector_store_ids": vector_store_ids,
            }
        ]
        query_parameters["tool_choice"] = "required"

    elif enable_web_search:
        query_parameters["tools"] = [
            {
                "type": "web_search",
                "search_context_size": "medium",
                "user_location": {"type": "approximate", "country": WEB_SEARCH_COUNTRY},
            }
        ]
        query_parameters["tool_choice"] = "required"

    else:
        query_parameters["temperature"] = 0

    # Make a chat completion request
    try:
        response = openai_client.responses.create(**query_parameters)
        return response.output_text

    except Exception as e:
        # Handle errors (rate limits, etc.)
        print(f"Error processing row: {e}")
        return "Error or Timeout"


def perform_x_profile_search(
    project_name: str,
    execution_date: str,
    input_file: str,
    output_file: str,
    start_date: str,
    end_date: str,
    num_posts_per_profile: int,
    local_file: str = None,
    historical_post_file: str = None,
) -> pd.DataFrame:
    # Create the project subfolder within the data folder if it does not exist
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base_dir, "../data"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "../data", project_name), exist_ok=True)
    os.makedirs(
        os.path.join(base_dir, "../data", project_name, execution_date), exist_ok=True
    )

    # Define search parameters
    profile_list = pd.read_csv(
        os.path.join(base_dir, "../data", project_name, input_file)
    )["account_id"].tolist()

    # Peform profile search
    if local_file is None:  # Perform API search
        response_list = []
        for profile in tqdm(profile_list):
            attempt = 0

            while attempt < MAX_RETRIES:
                attempt += 1
                try:
                    response = requests.get(
                        "https://abundance.it.com/get_tweets",
                        params={
                            "user": profile,
                            "max_tweets_per_user": num_posts_per_profile,
                            "cut_off_time": f"{start_date}T00:00:00",  # YYYY-MM-DDTHH:MM:SS
                        },
                        auth=HTTPBasicAuth(X_API_USERNAME, X_API_PASSWORD),
                    )
                    response_list += response.json()[0]
                    time.sleep(3)
                    break

                except requests.exceptions.JSONDecodeError:
                    warnings.warn(
                        f"JSONDecodeError for profile {profile} (attempt {attempt}/{MAX_RETRIES}). Retrying..."
                    )
                except requests.exceptions.ReadTimeout:
                    warnings.warn(
                        f"ReadTimeout for profile {profile} (attempt {attempt}/{MAX_RETRIES}). Retrying..."
                    )
                except requests.exceptions.ConnectTimeout:
                    warnings.warn(
                        f"ConnectTimeout for profile {profile} (attempt {attempt}/{MAX_RETRIES}). Retrying..."
                    )
                except requests.exceptions.HTTPError as e:
                    warnings.warn(
                        f"HTTP error for profile {profile}: {e}. Skipping profile."
                    )
                    break
                except requests.exceptions.RequestException as e:
                    warnings.warn(
                        f"RequestException for profile {profile}: {e}. Retrying (attempt {attempt}/{MAX_RETRIES})..."
                    )

            else:
                warnings.warn(
                    f"Failed to fetch info for profile {profile} after {MAX_RETRIES} attempts. Skipping."
                )

        profile_search_results = pd.DataFrame([r for r in response_list if r])
        profile_search_results["account_id"] = profile_search_results["author"].apply(
            lambda x: x.get("userName")
        )
        profile_search_results["hashtags"] = profile_search_results["entities"].apply(
            extract_hashtags
        )
        profile_search_results["tagged_users"] = profile_search_results[
            "entities"
        ].apply(extract_tagged_users)

        # Filter posts that happen before start_date
        profile_search_results["createdAt"] = pd.to_datetime(
            profile_search_results["createdAt"], format="%a %b %d %H:%M:%S %z %Y"
        )
        profile_search_results = profile_search_results[
            profile_search_results["createdAt"]
            >= datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        ].reset_index(drop=True)

    else:  # Perform local search
        local_profile_search = pd.read_csv(local_file)
        local_profile_search["create_time_processed"] = pd.to_datetime(
            local_profile_search["createdAt"], utc=True
        )
        profile_search_results = pd.DataFrame()

        for profile in tqdm(profile_list):
            # Filter by account id, and post start and end date
            filtered_profile_search = local_profile_search[
                (local_profile_search["account_id"] == profile)
                & (
                    local_profile_search["create_time_processed"]
                    >= pd.to_datetime(start_date, utc=True)
                )
                & (
                    local_profile_search["create_time_processed"]
                    < pd.to_datetime(end_date, utc=True)
                )
            ].reset_index(drop=True)

            if filtered_profile_search.empty:
                continue

            profile_search_results = pd.concat(
                [
                    profile_search_results,
                    filtered_profile_search.drop(columns=["create_time_processed"]),
                ],
                ignore_index=True,
            )

    profile_search_results.to_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file),
        index=False,
    )

    if historical_post_file:
        historical_post_file_path = os.path.join(
            base_dir, "../data", project_name, execution_date, historical_post_file
        )
        historical_posts = pd.read_csv(historical_post_file_path, on_bad_lines="skip")
        historical_posts = (
            pd.concat(
                [historical_posts, profile_search_results],
                ignore_index=True,
            )
            .drop_duplicates(subset="id", keep="last")
            .reset_index(drop=True)
        )
        historical_posts.to_csv(historical_post_file_path, index=False)

    return profile_search_results


def perform_x_profile_metadata_search(
    project_name: str,
    execution_date: str,
    input_file: str,
    output_file: str = "",
    local_file: str = None,
) -> pd.DataFrame:
    # Create the project subfolder within the data folder if it does not exist
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base_dir, "../data"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "../data", project_name), exist_ok=True)
    os.makedirs(
        os.path.join(base_dir, "../data", project_name, execution_date), exist_ok=True
    )

    # Define list of profiles for search
    profile_data = pd.read_csv(
        os.path.join(base_dir, "../data", project_name, input_file)
    )
    assert (
        "account_id" in profile_data.columns
    ), "Input file must contain 'account_id' column."
    profile_list = list(set(profile_data["account_id"].tolist()))

    if local_file is None:  # Perform API search
        # Perform profile metadata search
        response_list = []
        for profile in tqdm(profile_list):
            attempt = 0

            while attempt < MAX_RETRIES:
                attempt += 1
                try:
                    response = requests.get(
                        "https://abundance.it.com/get_user_info",
                        params={
                            "user": profile,
                        },
                        auth=HTTPBasicAuth(X_API_USERNAME, X_API_PASSWORD),
                    )
                    response_list += response.json()
                    time.sleep(3)
                    break

                except requests.exceptions.JSONDecodeError:
                    warnings.warn(
                        f"JSONDecodeError for profile {profile} (attempt {attempt}/{MAX_RETRIES}). Retrying..."
                    )
                except requests.exceptions.ReadTimeout:
                    warnings.warn(
                        f"ReadTimeout for profile {profile} (attempt {attempt}/{MAX_RETRIES}). Retrying..."
                    )
                except requests.exceptions.ConnectTimeout:
                    warnings.warn(
                        f"ConnectTimeout for profile {profile} (attempt {attempt}/{MAX_RETRIES}). Retrying..."
                    )
                except requests.exceptions.HTTPError as e:
                    warnings.warn(
                        f"HTTP error for profile {profile}: {e}. Skipping profile."
                    )
                    break
                except requests.exceptions.RequestException as e:
                    warnings.warn(
                        f"RequestException for profile {profile}: {e}. Retrying (attempt {attempt}/{MAX_RETRIES})..."
                    )

            else:
                warnings.warn(
                    f"Failed to fetch info for profile {profile} after {MAX_RETRIES} attempts. Skipping."
                )

        profile_metadata = pd.DataFrame([r for r in response_list if r])
        profile_metadata.rename(columns={"userName": "account_id"}, inplace=True)

    else:  # Perform local search
        local_profile_metadata = pd.read_csv(local_file)
        profile_metadata = local_profile_metadata[
            local_profile_metadata["account_id"].isin(profile_list)
        ].reset_index(drop=True)

    profile_metadata.to_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file),
        index=False,
    )

    return profile_metadata
