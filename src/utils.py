import requests, re, json, time, ast, os, random, warnings
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
from prompts.prompt_template_arm_b import STAGE2_JSON_KEYS
from config.base_config import (
    OPENAI_API_KEY,
    X_API_USERNAME,
    X_API_PASSWORD,
    NUM_PARALLEL_PROCESSES,
)
from config.digital_twin_config import (
    WEB_SEARCH_COUNTRY,
    WEB_SEARCH_CUTOFF_SENTENCE,
)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
base_dir = os.path.dirname(os.path.abspath(__file__))


# Mapping of prompt placeholder -> source column in the profile metadata frame.
_PROFILE_FIELD_COLUMNS = {
    "profile_picture": "profilePicture",
    "name": "name",
    "account_id": "account_id",
    "location": "location",
    "description": "description",
    "url": "url",
    "created_at": "createdAt",
    "is_verified": "isVerified",
    "is_blue_verified": "isBlueVerified",
    "protected": "protected",
    "followers": "followers",
    "following": "following",
    "statuses_count": "statusesCount",
    "favourites_count": "favouritesCount",
    "media_count": "mediaCount",
    "tweets": "posts_combined",
}


def build_profile_args(
    row: pd.Series,
    interview_type: str = "x",
    include_profile_info: bool = True,
) -> dict:
    """Build the placeholder -> value mapping for a single profile row.

    Args:
        row (pd.Series): One row of the profile metadata frame.
        interview_type (str): Interview identifier. Non-``x`` types return an
            empty mapping, since only X profiles are supported.
        include_profile_info (bool): When False every profile field is blanked
            (the platform label is still provided so prompt scaffolding
            renders), which is what the no-social conditions expect. Note this
            makes every participant's prompt byte-identical.

    Returns:
        dict: Placeholder name -> value, plus a ``platform`` label.

    Note:
        Fields are read with ``row.get(column, "")``, so a roster column that
        the prompts expect but the file lacks yields a blank field rather than
        an error. Check the roster schema up front if that matters.
    """
    # Only X (formerly Twitter) profiles are supported by the pipeline.
    if not interview_type.startswith("x"):
        return {}

    if include_profile_info:
        profile_args = {
            placeholder: row.get(column, "")
            for placeholder, column in _PROFILE_FIELD_COLUMNS.items()
        }
    else:
        profile_args = {placeholder: "" for placeholder in _PROFILE_FIELD_COLUMNS}

    profile_args["platform"] = "X (anteriormente Twitter)"
    return profile_args


def inject_profile_fields(
    row: pd.Series,
    template: str,
    interview_type: str = "x",
    include_profile_info: bool = True,
) -> str:
    """Substitute profile placeholders into a template via literal replacement.

    Unlike ``str.format``, this only replaces the known ``{placeholder}`` tokens
    and leaves every other brace untouched. That matters for the treatment arms
    whose user prompts embed literal JSON (single ``{`` / ``}``) next to the
    profile placeholders (Arms B/C/D).

    Args:
        row (pd.Series): One row of the profile metadata frame.
        template (str): Template containing ``{placeholder}`` tokens.
        interview_type (str): Interview identifier.
        include_profile_info (bool): When False every profile field is blanked.

    Returns:
        str: The template with known profile placeholders substituted and all
        other braces preserved verbatim.
    """
    profile_args = build_profile_args(row, interview_type, include_profile_info)
    for placeholder, value in profile_args.items():
        template = template.replace("{" + placeholder + "}", str(value))
    return template


def construct_system_prompt(
    row: pd.Series,
    system_prompt_template: str,
    interview_type: str,
    include_profile_info: bool = True,
    enable_web_search: bool = False,
) -> str:
    """Render an arm's system prompt for one participant.

    Args:
        row (pd.Series): One row of the profile metadata frame.
        system_prompt_template (str): The arm's system-prompt template, with
            ``{placeholder}`` tokens for the profile fields.
        interview_type (str): Interview identifier, e.g.
            ``"x_digital_twin_stage1"``. Only ``x``-prefixed types are
            supported.
        include_profile_info (bool): When False every profile field renders
            blank, which is what the no-social information conditions expect.
        enable_web_search (bool): When True, appends
            ``WEB_SEARCH_CUTOFF_SENTENCE`` so the retrieval-side cutoff
            instruction rides the web-search toggle.

    Returns:
        str: The system prompt with profile placeholders substituted.

    Raises:
        KeyError: If the template contains a ``{placeholder}`` that is not a
            known profile field.
    """
    profile_args = build_profile_args(row, interview_type, include_profile_info)
    system_prompt = system_prompt_template.format(**profile_args)
    if enable_web_search:
        system_prompt += "\n\n" + WEB_SEARCH_CUTOFF_SENTENCE
    return system_prompt


def construct_user_prompt(
    row: pd.Series,
    user_prompt_template: str,
    interview_type: str,
    include_profile_info: bool = True,
    inject_profile: bool = False,
) -> str:
    """Render an arm's user prompt for one participant.

    Args:
        row (pd.Series): One row of the profile metadata frame.
        user_prompt_template (str): The arm's user-prompt template.
        interview_type (str): Interview identifier, e.g.
            ``"x_digital_twin_arm_d"``.
        include_profile_info (bool): When False every profile field renders
            blank.
        inject_profile (bool): Whether to substitute profile placeholders.
            Baseline/Arm A keep profile data in the *system* prompt and pass
            False; Arms B/C/D place it in the user prompt and pass True.

    Returns:
        str: The user prompt, either verbatim or with profile fields injected.
    """
    # Baseline / Arm A keep profile data in the system prompt, so the user
    # prompt is returned verbatim. Arms B/C/D place profile data in the user
    # prompt and request literal injection instead.
    if inject_profile:
        return inject_profile_fields(
            row, user_prompt_template, interview_type, include_profile_info
        )
    return user_prompt_template


def extract_llm_responses(
    text, substring_exclusion_list: list = [], canonical_labels: list = None
) -> pd.Series:
    """
    ``canonical_labels``, if given, is matched case-insensitively against each
    parsed question label and the label is rewritten to its canonical form.
    Guards against the model echoing a question label back in the wrong case
    (observed for Arm D: a whole response in lowercase, e.g. "persona_real"
    instead of "PERSONA_REAL") producing a same-question-different-case
    duplicate column downstream instead of being recognised as the same
    question. Default ``None`` preserves the original behaviour for callers
    that don't pass it (e.g. stock-recommendation interviews, which have no
    such fixed label set to normalise against).

    Args:
        text (str): The model's raw ``**field: value**`` response.
        substring_exclusion_list (list): Blocks containing any of these
            substrings are dropped before parsing.
        canonical_labels (list): Optional fixed label set. Parsed labels are
            matched case-insensitively against it and rewritten to canonical
            form.

    Returns:
        pd.Series: One entry per parsed field, named ``"<QUESTION> - <field>"``
        (e.g. ``"EDAD - symbol"``). Fields absent from a block are omitted
        rather than set to None.
    """
    _canonical_lookup = (
        {label.lower(): label for label in canonical_labels} if canonical_labels else {}
    )

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
    probability_distribution_list = []

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
    probability_distribution_pattern = r"\*\*probability_distribution: (.*?)\*\*"

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
        probability_distribution = re.search(
            probability_distribution_pattern, block, re.DOTALL
        )

        _qname = question.group(1).replace("”", "") if question else None
        if _qname and _canonical_lookup:
            _qname = _canonical_lookup.get(_qname.strip().lower(), _qname)
        questions_list.append(_qname)
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
        probability_distribution_list.append(
            probability_distribution.group(1) if probability_distribution else None
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
        "probability_distribution": probability_distribution_list,
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
        if row["probability_distribution"]:
            flattened_series[f"{question_prefix} - probability_distribution"] = row[
                "probability_distribution"
            ]

    return flattened_series


def coalesce_columns_by_regex(data: pd.DataFrame, regex_list: list) -> pd.DataFrame:
    """
    Coalesces columns in a DataFrame that match any of the provided regex patterns.
    For each regex pattern in `regex_list`, finds all columns whose names match the pattern (case-insensitive).
    Among the matching columns, retains the one with the fewest missing values, and fills its missing values
    using the next best matching columns (row-wise, using backfill). All other matching columns are dropped.

    Args:
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


def extract_json_predictions(
    text,
    field_keys: tuple = (
        "symbol",
        "category",
        "speculation",
        "explanation",
        "evidence_basis",
        "probability_distribution",
    ),
) -> pd.Series:
    """Flatten a Stage 2 JSON prediction object (Arms B/C) into a flat Series.

    The two-stage arms return JSON of the form
    ``{"predictions": {"EDAD": {"symbol": ..., "category": ...}, ...}, ...}``.
    Each prediction field becomes a ``"<QUESTION> - <field>"`` column so that
    the downstream analysis schema matches the regex-based arms. Top-level
    bookkeeping fields (cannot_infer_fields, high_speculation_fields) are kept
    under an underscore-prefixed name. ``subject_id`` and ``overall_confidence``
    are intentionally not flattened here: the former duplicates the ``account_id``
    column already present on every row, and the latter was dropped from the
    schema per Ray's 2026-08-02 memo (kept: cannot_infer_fields,
    high_speculation_fields, estimated_political_tweet_pct; dropped:
    overall_confidence, overall_inference_quality). Parsing failures yield an
    empty Series.

    Args:
        text (str): The Stage 2 JSON response. Markdown code fences are
            stripped, and a bare ``{...}`` block is recovered as a fallback.
        field_keys (tuple): Prediction sub-fields to flatten into columns.

    Returns:
        pd.Series: One entry per prediction field, named
        ``"<QUESTION_KEY> - <field>"``, plus underscore-prefixed bookkeeping
        keys. List and dict values are JSON-encoded. Returns an empty Series if
        the text cannot be parsed at all.
    """
    flattened_series = pd.Series(dtype="object")
    if pd.isnull(text) or not isinstance(text, str) or not text.strip():
        return flattened_series

    raw = text.strip()
    # Strip Markdown code fences the model may wrap the JSON in.
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()

    try:
        data = json.loads(raw)
    except Exception:
        # Fall back to the first balanced-looking {...} block in the text.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return flattened_series
        try:
            data = json.loads(match.group(0))
        except Exception:
            return flattened_series

    if not isinstance(data, dict):
        return flattened_series

    predictions = data.get("predictions", {})
    if isinstance(predictions, dict):
        unknown_keys = sorted(set(predictions) - set(STAGE2_JSON_KEYS))
        if unknown_keys:
            # Loud, but not fatal here: this runs per row inside .apply(), before
            # the Stage 2 CSV is written. validate_stage2_prediction_keys() does
            # the hard raise once the output is safely on disk.
            warnings.warn(
                f"Stage 2 prediction JSON contains {len(unknown_keys)} question "
                f"key(s) outside the canonical schema: {unknown_keys}. These "
                "produce stray columns and leave the canonical column empty."
            )
        for question_key, prediction in predictions.items():
            if not isinstance(prediction, dict):
                continue
            for field in field_keys:
                if field in prediction and prediction[field] is not None:
                    value = prediction[field]
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value, ensure_ascii=False)
                    flattened_series[f"{question_key} - {field}"] = value

    for meta_key in (
        "cannot_infer_fields",
        "high_speculation_fields",
    ):
        if meta_key in data and data[meta_key] is not None:
            value = data[meta_key]
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            flattened_series[f"_{meta_key}"] = value

    return flattened_series


def validate_stage2_prediction_keys(
    stage2_df: pd.DataFrame,
    canonical_keys: tuple = STAGE2_JSON_KEYS,
    field: str = "symbol",
    id_col: str = "account_id",
) -> None:
    """Fail loudly on misspelled or missing Stage 2 question keys (Arms B/C).

    ``extract_json_predictions`` uses whatever question key the model returned as
    the column prefix, so a typo like ``EDDAD`` silently yields an ``"EDDAD -
    symbol"`` column while the canonical ``"EDAD - symbol"`` column stays empty.
    Nothing downstream catches this: unlike Arms A/D, the B/C path has no
    ``coalesce_columns_by_regex`` pass.

    Call this AFTER the Stage 2 CSV has been written. A four-arm 128-account run
    has already been paid for by this point, so the raw output must survive for
    diagnosis -- hence the raise happens here rather than inside the per-row
    ``.apply()``.

    Missing canonical keys warn (the model omitted a question); unknown keys
    raise, since they mean a column of predictions has silently gone missing.

    Args:
        stage2_df (pd.DataFrame): The flattened Stage 2 frame.
        canonical_keys (tuple): The expected question keys.
        field (str): Prediction sub-field whose columns identify which question
            keys are present.
        id_col (str): Column naming the subject, used in the error message.

    Returns:
        None: Raises or warns; the caller's frame is not modified.

    Raises:
        ValueError: If any returned question key is not in ``canonical_keys``.

    Warns:
        UserWarning: If a canonical key is missing from the output.
    """
    suffix = f" - {field}"
    present = {
        col[: -len(suffix)] for col in stage2_df.columns if col.endswith(suffix)
    }

    missing = sorted(set(canonical_keys) - present)
    if missing:
        warnings.warn(
            f"Stage 2 output is missing {len(missing)} canonical question "
            f"key(s) entirely: {missing}."
        )

    unknown = sorted(present - set(canonical_keys))
    if not unknown:
        return

    affected = 0
    accounts = []
    for key in unknown:
        rows = stage2_df[stage2_df[f"{key}{suffix}"].notna()]
        affected += len(rows)
        if id_col in stage2_df.columns:
            accounts.extend(rows[id_col].astype(str).tolist())

    detail = f" Affected accounts: {sorted(set(accounts))}." if accounts else ""
    raise ValueError(
        f"Stage 2 prediction JSON returned {len(unknown)} question key(s) "
        f"outside the canonical schema: {unknown}. {affected} row-key pair(s) "
        f"affected.{detail} The Stage 2 CSV was written before this check, so "
        "the raw output is on disk."
    )


def _coerce_history(x):
    """Normalise a stored conversation history into a list of messages.

    History round-trips through a CSV cell as a JSON string, so it comes back
    as ``str`` on reload but may still be a ``list`` in memory.

    Args:
        x: A JSON string, a list of message dicts, ``None``, or NaN.

    Returns:
        list: Message dicts with ``role`` and ``content`` keys. Returns an
        empty list for missing or unparseable input rather than raising, so a
        malformed history degrades to "no history" instead of failing the run.
    """
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
    """Flatten chat messages into a single transcript string.

    The Responses API's ``input`` field takes one string, so a multi-turn
    exchange is rendered as ``ROLE: content`` lines.

    Args:
        messages (list): Message dicts with ``role`` and ``content`` keys.

    Returns:
        str: Newline-joined ``ROLE: content`` lines. Messages with empty
        content are skipped.
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
    """Write a JSONL batch-input file, one request per participant.

    Used by the non-web information conditions, which go through the Batch API
    rather than issuing row-wise calls. Note this path can only ever attach the
    ``file_search`` tool -- the web-search tool is not available on the batch
    endpoint.

    Args:
        prompts (pd.DataFrame): Frame carrying ``custom_id`` plus the system
            and user prompt columns.
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name).
        gpt_model (str): Model id. Must start with ``gpt-4`` or ``gpt-5``;
            ``gpt-4`` requests set ``temperature=0`` while ``gpt-5`` omits the
            parameter, which the pinned snapshot does not accept.
        system_prompt_field (str): Column holding the system prompt.
        user_prompt_field (str): Column holding the user prompt.
        history_field (str): Optional column holding prior turns to replay.
        batch_file_name (str): Output filename inside ``batch-files/``.
        vector_store_ids (list): When non-empty, requests target
            ``/v1/responses`` with a ``file_search`` tool instead of
            ``/v1/chat/completions``.

    Returns:
        str: ``batch_file_name``, for the caller to hand to :func:`batch_query`.

    Raises:
        ValueError: If ``gpt_model`` is neither a ``gpt-4`` nor ``gpt-5`` model.
    """
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
    """Submit a batch job, block until it finishes, and return its responses.

    Polls every 5 minutes against a 24-hour completion window, so this call can
    block for hours -- that is the cost trade-off the batch path exists for.

    Args:
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name).
        batch_input_file_dir (str): Input filename inside ``batch-files/``.
        batch_output_file_dir (str): Filename to write raw results to inside
            ``batch-files/``.
        vector_store_ids (list): When non-empty, the job targets
            ``/v1/responses`` and results are parsed out of the ``output``
            array; otherwise ``/v1/chat/completions`` and the first choice.

    Returns:
        pd.DataFrame: Columns ``custom_id`` and ``query_response``.

    Raises:
        Exception: If the batch job reports status ``failed``.

    Warns:
        UserWarning: When a response carries no recoverable text, in which case
            that row's ``query_response`` is an empty string.
    """
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
    """Render one account's posts as the formatted block used in prompts.

    Args:
        profile_id (str): The ``account_id`` to select posts for.
        tweet_metadata (pd.DataFrame): Post corpus. Needs ``account_id`` and
            ``createdAt``; every content column (``text``, ``likeCount``,
            ``hashtags``, ...) is optional and renders empty when absent.

    Returns:
        str: One formatted block per post, most recent first, separated by
        blank lines. Returns an empty string when the account has no posts --
        which is silent by design here, so callers that care must check
        coverage themselves before building prompts.
    """
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
    inject_profile_into_user_prompt: bool = False,
    user_prompt_field_override: str = None,
) -> None:
    """Run one interview call for every participant and write the results CSV.

    Builds each participant's prompts, dispatches the calls, and writes the
    whole frame -- inputs, prompts, responses and the web-search log -- to
    ``output_file``. Because the frame is written whole with no column
    subsetting, columns from a previous call in the same arm are carried
    forward when the caller passes that call's CSV as ``profile_metadata_file``.

    Dispatch is decided by ``enable_web_search``: web-enabled conditions go
    row-wise through the Responses API with the ``web_search`` tool attached,
    concurrently across ``NUM_PARALLEL_PROCESSES`` threads; non-web conditions
    go through the Batch API, which is cheaper but can block for hours.

    Args:
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name and filename
            suffix).
        gpt_model (str): Model id to call.
        profile_metadata_file (str): Input CSV inside the run namespace. May be
            a previous call's output, which is how columns carry forward.
        post_file (str): Post corpus CSV inside the run namespace.
        output_file (str): Output CSV filename inside the run namespace.
        system_prompt_template (str): System-prompt template; an empty string
            skips creating the system-prompt column entirely (used by the
            second call of the two-call arms, which replays history instead).
        user_prompt_template (str): User-prompt template.
        llm_response_field (str): Column to write the model's text into.
        interview_type (str): Interview identifier. Also scopes the derived
            ``<interview_type>_system_prompt`` / ``_user_prompt`` /
            ``_web_search_log`` column names, which is what keeps successive
            calls in one arm from overwriting each other.
        history_field (str): Optional column holding prior turns to replay.
        vector_store_ids (list): Optional file-search vector stores.
        include_profile_info (bool): When False every profile field is blanked,
            so all participants receive a byte-identical prompt.
        use_row_query (bool): Force the row-wise path even without web search.
        enable_web_search (bool): Attach the web-search tool, which also
            forces the row-wise path.
        inject_profile_into_user_prompt (bool): Substitute profile fields into
            the user prompt (Arms B/C/D) rather than the system prompt.
        user_prompt_field_override (str): Use this pre-computed per-row column
            as the user prompt instead of rendering a template. Used by the
            two-stage arms, whose Stage 2 prompt embeds Stage 1's evidence.

    Returns:
        None: Results are written to ``output_file``.

    Raises:
        ValueError: If ``interview_type`` is not an ``x``-prefixed type.
        FileNotFoundError: If the metadata or post CSV is absent from the run
            namespace -- reachable when ``--skip-profile-search`` points at a
            namespace that was never populated.
    """
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
            args=(
                system_prompt_template,
                interview_type,
                include_profile_info,
                enable_web_search,
            ),
            axis=1,
        )
    if user_prompt_field_override:
        # Use a per-row user prompt that the caller pre-computed on disk (e.g. a
        # two-stage arm's Stage 2 prompt with the Stage 1 evidence injected).
        profile_metadata[f"{interview_type}_user_prompt"] = profile_metadata[
            user_prompt_field_override
        ]
    else:
        profile_metadata[f"{interview_type}_user_prompt"] = profile_metadata.apply(
            construct_user_prompt,
            args=(
                user_prompt_template,
                interview_type,
                include_profile_info,
                inject_profile_into_user_prompt,
            ),
            axis=1,
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

    # Scoped per interview_type (matching the *_system_prompt / *_user_prompt
    # convention above) so that the two-call and two-stage arms, which carry
    # each other's columns forward, cannot overwrite one another's log.
    web_search_log_field = f"{interview_type}_web_search_log"

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
            """Call :func:`row_query` for one row, closing over the shared args.

            Args:
                row (pd.Series): One participant's row, carrying the rendered
                    prompt columns.

            Returns:
                tuple[str, str]: ``(response_text, web_search_log_json)``.
            """
            return row_query(
                row,
                args=(row_query_args,),
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(
                tqdm_auto(executor.map(run_row_query, rows), total=len(rows))
            )

        # Assign results back to the DataFrame in the same order. The guard is
        # required: zip(*[]) raises, and an empty frame is reachable whenever
        # the roster/corpus filter matched no accounts.
        if results:
            response_texts, web_search_logs = (list(t) for t in zip(*results))
        else:
            response_texts, web_search_logs = [], []
        profile_metadata_with_responses[llm_response_field] = response_texts
        profile_metadata_with_responses[web_search_log_field] = web_search_logs

    else:  # Perform batch queries to save cost
        # Name the batch envelopes per interview_type, not with a fixed name.
        # A two-stage arm submits two batches into the same run directory, and
        # a fixed name meant Stage 2's request envelope overwrote Stage 1's --
        # so only one of the two archived. The same applied to the two-call
        # arms. Scoping by interview_type keeps every submitted envelope and
        # its raw results on disk, which is what the registered archive of
        # request bodies requires.
        batch_input_name = f"batch_input_{interview_type}.jsonl"
        batch_output_name = f"batch_output_{interview_type}.jsonl"

        create_batch_file(
            profile_metadata,
            project_name=project_name,
            execution_date=execution_date,
            gpt_model=gpt_model,
            system_prompt_field=f"{interview_type}_system_prompt",
            user_prompt_field=f"{interview_type}_user_prompt",
            history_field=history_field,
            batch_file_name=batch_input_name,
            vector_store_ids=vector_store_ids,
        )

        llm_responses = batch_query(
            project_name=project_name,
            execution_date=execution_date,
            batch_input_file_dir=batch_input_name,
            batch_output_file_dir=batch_output_name,
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

        # The batch endpoint cannot attach the web-search tool at all
        # (create_batch_file only ever emits file_search), and enable_web_search
        # routes to the row branch above, so "no searches" is an invariant here
        # rather than an assumption. Still write a payload so the column has the
        # same shape in every arm and downstream json.loads needs no special case.
        profile_metadata_with_responses[web_search_log_field] = empty_web_search_log(
            "batch", web_search_enabled=False
        )

    # Save profile metadata after analysis into CSV file
    profile_metadata_with_responses.to_csv(
        os.path.join(base_dir, "../data", project_name, execution_date, output_file),
        index=False,
    )


# ─── Web-search logging ───────────────────────────────────────────────────────
# The Responses API returns far more than the answer text: `response.output`
# carries one `web_search_call` item per search the model issued (with the query
# and, for some actions, the URLs it opened), and the assistant message's
# `annotations` carry `url_citation` entries for the sources actually cited.
# `response.output_text` throws all of that away. We persist it per interview so
# that what the model retrieved is auditable after the fact.

WEB_SEARCH_LOG_SCHEMA_VERSION = 1

# Backstops so one pathological response cannot produce an unbounded CSV cell.
MAX_LOGGED_SOURCES_PER_CALL = 100
MAX_LOGGED_CITATIONS = 200


def _g(obj, name, default=None):
    """Read an attribute without ever raising.

    Used for traversing SDK response objects, so that a shape change in a
    future SDK release degrades the log rather than failing the interview.

    Args:
        obj: Any object, including ``None``.
        name (str): Attribute name.
        default: Value to return when the attribute is missing or unreadable.

    Returns:
        The attribute value, or ``default``.
    """
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _safe_dump(obj):
    """Produce a serialisable representation of an unrecognised SDK object.

    Args:
        obj: Any object, typically a pydantic model from the OpenAI SDK.

    Returns:
        A dict when the object exposes ``to_dict`` or ``model_dump``, ``None``
        for ``None`` input, otherwise ``str(obj)`` or ``"<undumpable>"``.
    """
    if obj is None:
        return None
    for method in ("to_dict", "model_dump"):
        try:
            return getattr(obj, method)()
        except Exception:
            pass
    try:
        return str(obj)
    except Exception:
        return "<undumpable>"


def _dump_web_search_log(payload: dict) -> str:
    """Serialise a log payload to a single CSV-safe line.

    No ``indent``: that is what keeps literal newlines out of the cell. Matches
    the ``separators``/``ensure_ascii`` convention already used for
    ``entity_geographic_interview_history``.

    Args:
        payload (dict): The log payload to serialise.

    Returns:
        str: Single-line JSON. On a serialisation failure, returns a minimal
        payload carrying ``extract_error`` rather than raising, so one bad
        value cannot fail an interview that has already been paid for.
    """
    try:
        return json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), default=str
        )
    except Exception as exc:  # pragma: no cover - defensive
        return '{"v":%d,"extract_error":%s,"searches":[],"citations":[]}' % (
            WEB_SEARCH_LOG_SCHEMA_VERSION,
            json.dumps(repr(exc)[:500]),
        )


def empty_web_search_log(path: str, web_search_enabled: bool = False, **extra) -> str:
    """Build a log payload for an interview that issued no searches.

    Used for the batch path (where the web-search tool cannot be attached at
    all) and for skipped/failed rows, so that every row in every arm holds a
    parseable payload with the same shape. A downstream
    ``df[col].map(json.loads)`` then needs no special-casing for empty cells.

    Args:
        path (str): Why no searches occurred -- ``"batch"`` (batch endpoint),
            ``"skipped"`` (prompt missing, no call made) or ``"row"`` (the call
            failed; pair with ``error``).
        web_search_enabled (bool): Whether web search was requested.
        **extra: Additional top-level keys to merge in, e.g.
            ``error="RateLimitError(...)"``.

    Returns:
        str: Single-line JSON with empty ``searches`` and ``citations`` lists.
    """
    payload = {
        "v": WEB_SEARCH_LOG_SCHEMA_VERSION,
        "path": path,
        "web_search_enabled": bool(web_search_enabled),
        "n_web_search_calls": 0,
        "searches": [],
        "n_citations": 0,
        "citations": [],
    }
    payload.update(extra)
    return _dump_web_search_log(payload)


def _extract_search_action(action) -> dict:
    """Normalise one ``web_search_call.action`` into a flat dict.

    The SDK models this as a union: ``search`` carries ``query`` plus a nullable
    ``sources`` list, ``open_page`` carries ``url``, ``find`` carries ``url`` and
    ``pattern``. Any variant we do not recognise is preserved verbatim under
    ``raw`` rather than dropped, so a future SDK addition loses no data.

    Two failure modes are labelled distinctly, because they mean different
    things to an auditor reconstructing what the model retrieved:

    * ``"unavailable"`` -- the API returned a search call with no ``action`` at
      all (observed in practice, despite the SDK typing it as required). The
      query is genuinely unrecoverable; there is nothing more to parse.
    * ``"unknown"`` -- an ``action`` is present but its ``type`` is one we do
      not handle. The payload IS recoverable and is preserved under ``raw``,
      so this is a signal to extend this function.

    Args:
        action: The SDK's ``web_search_call.action``, or ``None``.

    Returns:
        dict: Always carries ``action``. A ``search`` adds ``query`` and
        ``sources`` (capped at ``MAX_LOGGED_SOURCES_PER_CALL``, flagged with
        ``sources_truncated``); ``open_page`` adds ``url``; ``find`` adds
        ``url`` and ``pattern``; an unrecognised type adds ``raw``.
    """
    if action is None:
        return {"action": "unavailable"}

    action_type = _g(action, "type")
    entry = {"action": action_type or "unknown"}

    if action_type == "search":
        entry["query"] = _g(action, "query")
        sources = _g(action, "sources") or []
        urls = []
        for source in sources[:MAX_LOGGED_SOURCES_PER_CALL]:
            url = _g(source, "url")
            if url:
                urls.append(url)
        entry["sources"] = urls
        if len(sources) > MAX_LOGGED_SOURCES_PER_CALL:
            entry["sources_truncated"] = True
    elif action_type == "open_page":
        entry["url"] = _g(action, "url")
    elif action_type == "find":
        entry["url"] = _g(action, "url")
        entry["pattern"] = _g(action, "pattern")
    else:
        entry["raw"] = _safe_dump(action)

    return entry


def build_web_search_log(
    response,
    *,
    web_search_enabled: bool,
    path: str = "row",
    error: str = None,
) -> str:
    """Summarise the web-search activity of one Responses API call as JSON.

    ``response`` is deliberately duck-typed rather than annotated as the SDK's
    ``Response``: every field is read through :func:`_g`, so the function can be
    exercised with plain ``types.SimpleNamespace`` fixtures at zero API cost, and
    it degrades rather than raises if the SDK's shape changes.

    Never raises. On an internal failure it returns a payload carrying
    ``extract_error`` so the problem is diagnosable from the output CSV instead
    of taking down a run mid-flight.

    Args:
        response: The Responses API result object (duck-typed).
        web_search_enabled (bool): Whether the web-search tool was attached.
        path (str): Dispatch path that produced this response, ``"row"``.
        error (str): Optional error repr when the call itself failed.

    Returns:
        str: Single-line JSON carrying ``searches`` (one entry per
        ``web_search_call``), ``citations`` (``url_citation`` annotations,
        capped at ``MAX_LOGGED_CITATIONS``), ``response_id``,
        ``response_status``, ``model``, ``created_at`` and ``usage``.

    Note:
        The API does not always report a query for a search call, in which case
        the entry is labelled ``action: "unavailable"``. Query text and
        citations are therefore best-effort, while the response id, timestamp
        and search count are reliable.
    """
    try:
        searches = []
        citations = []

        for item in _g(response, "output", None) or []:
            item_type = _g(item, "type")

            if item_type == "web_search_call":
                entry = {"id": _g(item, "id"), "status": _g(item, "status")}
                entry.update(_extract_search_action(_g(item, "action")))
                searches.append(entry)

            elif item_type == "message":
                for content in _g(item, "content", None) or []:
                    if _g(content, "type") != "output_text":
                        continue
                    for annotation in _g(content, "annotations", None) or []:
                        if _g(annotation, "type") != "url_citation":
                            continue
                        if len(citations) >= MAX_LOGGED_CITATIONS:
                            break
                        citations.append(
                            {
                                "url": _g(annotation, "url"),
                                "title": _g(annotation, "title"),
                                "start_index": _g(annotation, "start_index"),
                                "end_index": _g(annotation, "end_index"),
                            }
                        )

        usage = _g(response, "usage")
        payload = {
            "v": WEB_SEARCH_LOG_SCHEMA_VERSION,
            "path": path,
            "web_search_enabled": bool(web_search_enabled),
            "response_id": _g(response, "id"),
            "response_status": _g(response, "status"),
            "model": _g(response, "model"),
            # The retrieval timestamp: this is what lets an analyst check
            # whether retrieved content postdates the study's context cutoff.
            "created_at": _g(response, "created_at"),
            "usage": (
                {
                    "input_tokens": _g(usage, "input_tokens"),
                    "output_tokens": _g(usage, "output_tokens"),
                    "total_tokens": _g(usage, "total_tokens"),
                }
                if usage is not None
                else None
            ),
            "n_web_search_calls": len(searches),
            "searches": searches,
            "n_citations": len(citations),
            "citations": citations,
            "error": error,
            "extract_error": None,
        }
        return _dump_web_search_log(payload)

    except Exception as exc:
        return _dump_web_search_log(
            {
                "v": WEB_SEARCH_LOG_SCHEMA_VERSION,
                "path": path,
                "web_search_enabled": bool(web_search_enabled),
                "n_web_search_calls": 0,
                "searches": [],
                "n_citations": 0,
                "citations": [],
                "error": error,
                "extract_error": repr(exc)[:500],
            }
        )


def row_query(row: pd.Series, args: list) -> "tuple[str, str]":
    """Run one interview and return ``(response_text, web_search_log_json)``.

    The second element is always a parseable JSON string, on every return path,
    so the caller can assign it straight into a column without None-handling.

    Args:
        row (pd.Series): One participant's row, carrying the rendered prompt
            columns.
        args (list): A 1-tuple wrapping a 6-element list, unpacked positionally
            as ``(system_prompt_column, user_prompt_column, history_field,
            gpt_model, enable_web_search, vector_store_ids)``. This shape is
            what ``ThreadPoolExecutor.map`` needs to pass one argument per row.

    Returns:
        tuple[str, str]: The model's text and its web-search log. On failure,
        ``("Error or Timeout", <log carrying the exception repr>)`` -- errors
        are caught rather than raised, because ``executor.map`` is lazy and an
        escaping exception would abort a run whose other rows were already
        billed.
    """
    system_prompt = row.get(args[0][0], "")
    user_prompt = row[args[0][1]]
    history_field = args[0][2]
    gpt_model = args[0][3]
    enable_web_search = args[0][4]
    vector_store_ids = args[0][5]

    # Skip if system_prompt/user_prompt is empty or NaN (depending on your logic)
    if not isinstance(system_prompt, str) or not isinstance(user_prompt, str):
        return "", empty_web_search_log("skipped", enable_web_search)

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

            for m in history:
                r, c = m.get("role", "user"), m.get("content", "")
                input.append({"role": r, "content": c})

            if system_prompt and system_prompt in row.index:
                input.append({"role": "system", "content": system_prompt})

            input.append({"role": "user", "content": user_prompt})
        else:
            input = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
    else:
        input = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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

    # Make a chat completion request. Everything below stays inside this try:
    # ``executor.map`` is lazy, so an exception escaping here would surface when
    # the caller materialises the results and would abort the whole run after
    # the other rows had already been paid for.
    try:
        response = openai_client.responses.create(**query_parameters)
        return response.output_text, build_web_search_log(
            response, web_search_enabled=enable_web_search, path="row"
        )

    except Exception as e:
        # Handle errors (rate limits, etc.)
        print(f"Error processing row: {e}")
        return "Error or Timeout", empty_web_search_log(
            "row", enable_web_search, error=repr(e)[:500]
        )


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
    """Collect each rostered account's posts into the run namespace.

    Two branches. With ``local_file`` the posts are filtered out of an existing
    corpus, which is deterministic and free; without it they are fetched from
    the X API.

    Args:
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name).
        input_file (str): Roster CSV naming which accounts to collect. Only its
            ``account_id`` column is read. An absolute path is used as-is.
        output_file (str): Output CSV filename inside the run namespace.
        start_date (str): Inclusive lower bound on post date.
        end_date (str): Exclusive upper bound on post date. Applied on the
            local branch only -- the API branch bounds nothing at the top end.
        num_posts_per_profile (int): Per-account cap. Applied on the API branch
            only; the local branch ignores it and takes every matching post.
        local_file (str): Post corpus to filter. ``None`` selects the API branch.
        historical_post_file (str): Optional existing corpus to merge results
            into, de-duplicated on post id.

    Returns:
        pd.DataFrame: The collected posts, also written to ``output_file``.

    Note:
        ``start_date``/``end_date`` are parsed differently by the two branches
        (``pd.to_datetime`` locally, ``strptime("%Y-%m-%d")`` on the API path),
        so a format that works locally will not necessarily work against the
        API.
    """
    # Create the project subfolder within the data folder if it does not exist
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base_dir, "../data"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "../data", project_name), exist_ok=True)
    os.makedirs(
        os.path.join(base_dir, "../data", project_name, execution_date), exist_ok=True
    )

    # Resolve the registered study window once, so both retrieval branches
    # below apply an identical, inclusive-of-end_date bound.
    window_start, window_end = resolve_post_window(start_date, end_date)

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
                            # Derived from the resolved window rather than
                            # interpolating the raw config string, which is
                            # MM-DD-YYYY and not the ISO form this expects.
                            "cut_off_time": window_start.strftime("%Y-%m-%dT%H:%M:%S"),
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

        # Bound the corpus to the registered study window at BOTH ends. The
        # upper bound is the registered context cutoff, so it must be applied
        # here too -- not only on the local branch -- or a live scrape would
        # ingest posts published after the cutoff.
        profile_search_results["createdAt"] = pd.to_datetime(
            profile_search_results["createdAt"], format="%a %b %d %H:%M:%S %z %Y"
        )
        profile_search_results = profile_search_results[
            (profile_search_results["createdAt"] >= window_start)
            & (profile_search_results["createdAt"] < window_end)
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
                & (local_profile_search["create_time_processed"] >= window_start)
                & (local_profile_search["create_time_processed"] < window_end)
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


def resolve_post_window(start_date: str, end_date: str) -> "tuple[pd.Timestamp, pd.Timestamp]":
    """Resolve the registered post-collection window to half-open UTC bounds.

    The registered study window runs from account inception *through* December
    13, 2025 -- inclusive of the closing day, which is the close of the survey
    field period. Returning an exclusive upper bound of the following midnight
    is what makes "through the 13th" include everything posted on the 13th; a
    naive ``< end_date`` would silently drop that entire day.

    Both retrieval branches call this, so the local-corpus filter and the live
    API filter cannot drift apart or parse the configured dates differently.

    Args:
        start_date (str): Inclusive lower bound, as configured (``MM-DD-YYYY``).
        end_date (str): Inclusive upper bound *day*, as configured.

    Returns:
        tuple[pd.Timestamp, pd.Timestamp]: ``(start, end_exclusive)`` in UTC.
        A post belongs in the window when ``start <= createdAt < end_exclusive``.

    Raises:
        ValueError: If either date cannot be parsed.
    """
    start = pd.to_datetime(start_date, utc=True)
    # Normalise to midnight then add a day: the configured end_date names the
    # last day to INCLUDE, not the first instant to exclude.
    end_exclusive = pd.to_datetime(end_date, utc=True).normalize() + pd.Timedelta(days=1)
    if pd.isna(start) or pd.isna(end_exclusive):
        raise ValueError(f"Could not parse post window {start_date!r}..{end_date!r}")
    return start, end_exclusive


def select_profile_sample(
    roster_path: str,
    sample_size: int = None,
    seed: int = None,
) -> "tuple[list[str], dict]":
    """Draw a reproducible random subsample of ``account_id``s from a roster.

    Returns ``(account_ids, metadata)``. The ids are returned in canonical
    (sorted) order so that the sample-tag hash is order-invariant.

    Determinism, which is the whole point here, rests on three choices:

    * The candidate pool is **sorted first**, so re-exporting or re-sorting the
      roster CSV cannot change who gets drawn. ``astype(str)`` is required --
      ids read back as int64 from a future export would otherwise sort
      differently, and a mixed-type list raises under ``sorted``.
    * ``drop_duplicates()`` rather than ``set()``: iterating a set of strings is
      randomised per process by PYTHONHASHSEED, which would make the sample
      irreproducible across invocations.
    * ``random.Random(seed)`` rather than ``DataFrame.sample(random_state=)``:
      pandas' sampling depends on frame row order and on numpy Generator
      semantics, neither of which is contractually stable across versions.
      ``random.Random`` depends on nothing but ``(seed, list, k)``.

    Shuffling the whole pool and taking a prefix (rather than ``rng.sample``)
    additionally makes samples **nested**: at a fixed seed the n=10 sample is a
    subset of n=25, which is a subset of n=50. That lets a study be piloted
    small and scaled up without discarding the earlier runs.

    Args:
        roster_path (str): CSV listing candidate accounts. Needs an
            ``account_id`` column.
        sample_size (int): How many accounts to draw. ``None`` returns the
            whole roster.
        seed (int): Seed for the draw. Required for a reproducible sample.

    Returns:
        tuple[list[str], dict]: The selected ``account_id``s in canonical
        sorted order, and metadata recording the roster file and size, the
        requested and effective sizes, the seed, and the sampling method.

    Raises:
        ValueError: If the roster has no ``account_id`` column, contains no
            usable ids, or is smaller than ``sample_size``.
    """
    roster = pd.read_csv(roster_path)
    if "account_id" not in roster.columns:
        raise ValueError(
            f"Roster {roster_path} must contain an 'account_id' column; "
            f"found {list(roster.columns)[:10]}."
        )

    ids = sorted(
        roster["account_id"].dropna().astype(str).str.strip().drop_duplicates().tolist()
    )
    if not ids:
        raise ValueError(f"Roster {roster_path} contains no usable account_id values.")

    metadata = {
        "roster_file": os.path.abspath(roster_path),
        "roster_size": len(ids),
        "requested_size": sample_size,
        "seed": seed,
        "method": "sorted_shuffle_prefix",
    }

    if sample_size is None:
        metadata["effective_size"] = len(ids)
        return ids, metadata

    if sample_size > len(ids):
        raise ValueError(
            f"--sample-size {sample_size} exceeds the {len(ids)} unique accounts "
            f"in {roster_path}."
        )

    shuffled = ids[:]
    random.Random(seed).shuffle(shuffled)
    selected = sorted(shuffled[:sample_size])
    metadata["effective_size"] = len(selected)
    return selected, metadata


def perform_x_profile_metadata_search(
    project_name: str,
    execution_date: str,
    input_file: str,
    output_file: str = "",
    local_file: str = None,
) -> pd.DataFrame:
    """Collect each rostered account's profile metadata into the run namespace.

    Args:
        project_name (str): Project folder under ``data/``.
        execution_date (str): Run namespace (directory name).
        input_file (str): Roster CSV naming which accounts to collect. Only its
            ``account_id`` column is read. An absolute path is used as-is,
            which is how a sampled roster is supplied.
        output_file (str): Output CSV filename inside the run namespace.
        local_file (str): Metadata corpus to filter. ``None`` selects the API
            branch.

    Returns:
        pd.DataFrame: The collected profile metadata, also written to
        ``output_file``. Row order follows the corpus file, not the roster,
        and that order determines the ``custom_id`` assigned downstream.

    Raises:
        AssertionError: If the roster has no ``account_id`` column.

    Note:
        Columns the prompts expect but the corpus lacks are not detected here.
        They surface as blank prompt fields via ``build_profile_args``, so
        callers should check the roster schema before building prompts.
    """
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
    # drop_duplicates() rather than list(set(...)): iterating a set of strings is
    # randomised per process by PYTHONHASHSEED. That is harmless on the local
    # branch below (which filters with .isin, so corpus order wins), but on the
    # API branch profile_list order becomes the output row order, and therefore
    # the custom_id assignment -- which must be reproducible across runs.
    profile_list = profile_data["account_id"].dropna().drop_duplicates().tolist()

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
