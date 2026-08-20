# Digital Twin Chile

---

## Prerequisites

- [Conda](https://docs.conda.io/en/latest/miniconda.html) (Miniconda or Anaconda)
- `git` (if you’re cloning this repository from a remote source)
- Python 3.12 (handled automatically by the conda environment instructions below)

---

## 1. Clone the Repository

```bash
git clone https://github.com/talking-to-machines/digital-twin-chile.git
cd digital-twin-chile
````

---

## 2. Create and Activate the Conda Environment

Create a new `conda` environment named `digital-twin-chile` with Python 3.12:

```bash
conda create --name digital-twin-chile python=3.12
conda activate digital-twin-chile
```

---

## 3. Install Python Dependencies

Install all required Python libraries from `requirements.txt`:

```bash
pip install -r requirements.txt
```

Make sure you run this command **after** activating the `digital-twin-chile` environment.

---

## 4. Run the Project

Once the environment is set up and dependencies are installed, run the main module:

```bash
python -m src.digital_twin_chile_x
```

This starts the main workflow of the **Digital Twin Chile** project. With no
arguments it runs treatment arm `a` (the corrected baseline) with profile
information and web search enabled.

### 4.1 Command-line options

| Flag | Values | Default | Description |
| --- | --- | --- | --- |
| `--treatment-arm` | `baseline`, `a`, `b`, `c`, `d` | `a` | Experimental prompt condition to run (see table below). |
| `--include-profile-info` / `--no-include-profile-info` | — | `--include-profile-info` | Include the user's profile metadata and tweets in the prompts. |
| `--enable-web-search` / `--no-enable-web-search` | — | `--enable-web-search` | Allow the model to use web search during the interviews. |
| `--skip-profile-search` | — | off | Skip Step 1 (profile metadata/post retrieval) and reuse the data already present in this arm's output folder. |
| `--num-runs` | integer ≥ 1 | `1` | Repetitions of this arm over the same sampled respondents. Each writes to its own `_runNN` namespace. |
| `--run-index-start` | integer ≥ 1 | `1` | Index of the first repetition. `--num-runs 5 --run-index-start 6` extends a 5-run study to 10 without redoing the first five. |
| `--sample-size` | integer ≥ 1 | unset | Respondents to draw at random from the roster. Omit to use the whole roster. Requires `--seed`. |
| `--seed` | integer | unset | Seed selecting **which respondents** are interviewed. See the note below — this is not `--option-order-seed-suffix`. |
| `--profile-roster` | path or filename | `final_meta_user_df_sample.csv` | Roster CSV of accounts to interview (needs an `account_id` column). A bare filename resolves against `data/digital-twin-chile-x/`. |
| `--profile-posts` | path or filename | `test_tweets.csv` | Post corpus. Must cover the sampled accounts — see the coverage preflight below. |
| `--allow-missing-posts` | — | off | Proceed even when some sampled accounts have no posts. Those interviews run with an empty post block. |
| `--dry-run` | — | off | Resolve sampling, namespacing and the preflight, print the plan and an API-call estimate, then exit without calling the API or writing files. |
| `--shuffle-scope` | `nominal`, `all` | `nominal` | Arm `c` only: which Stage 2 option lists to randomise. `nominal` shuffles only nominal-scale questions; `all` also shuffles ordinal scales. Ignored by other arms, and ignored if `--shuffle-keys` is given. |
| `--shuffle-keys` | comma-separated question keys, or `all` | unset | Arm `c` only: exact question keys to shuffle (e.g. `REGION,COMUNA,SEXO`), overriding `--shuffle-scope` entirely. Accepts any of Arm C's `SHUFFLEABLE_KEYS`, including `COMUNA` (otherwise always canonical order regardless of scope). Pass `all` to shuffle every shuffleable question (the split-sample "shuffle everything" diagnostic). |
| `--option-order-seed-suffix` (alias: `--seed-suffix`) | any string | `""` | Arm `c` only: appended to the per-question **option-order** shuffle seed and to the randomization-log/predictions filenames, so a different suffix (e.g. `_v2`) reshuffles independently for repeated-seed sensitivity runs without overwriting the previous run's output. |

> **Two different seeds.** `--seed` chooses **which respondents** are
> interviewed. `--option-order-seed-suffix` reshuffles **Arm C's answer
> options**. They are independent, and option order deliberately does *not*
> vary across `--num-runs` repetitions — see §4.8.

Run `python -m src.digital_twin_chile_x --help` to see all options.

### 4.2 Treatment arms

| Arm | Architecture | Description |
| --- | --- | --- |
| `baseline` | single-stage, 2 calls | Original (uncorrected) prompt. |
| `a` | single-stage, 2 calls | Corrected baseline with format + conservative-inference rules. |
| `b` | two-stage, JSON | Evidence extraction → survey prediction. |
| `c` | two-stage, JSON | Same as `b`, with randomised Stage 2 option ordering. |
| `d` | single-stage, 1 call | Minimal sparse prompt (code ranges only). |

### 4.3 Running a specific treatment arm

```bash
# Corrected baseline (default)
python -m src.digital_twin_chile_x --treatment-arm a

# Two-stage JSON arms
python -m src.digital_twin_chile_x --treatment-arm b
python -m src.digital_twin_chile_x --treatment-arm c

# Minimal sparse single-call
python -m src.digital_twin_chile_x --treatment-arm d

# Original uncorrected baseline
python -m src.digital_twin_chile_x --treatment-arm baseline
```

### 4.4 Toggling web search and profile information

```bash
# Enable web search and include profile information (these are the defaults)
python -m src.digital_twin_chile_x --treatment-arm a --enable-web-search --include-profile-info

# Disable web search
python -m src.digital_twin_chile_x --treatment-arm a --no-enable-web-search

# Exclude profile information
python -m src.digital_twin_chile_x --treatment-arm a --no-include-profile-info

# Reuse already-retrieved profile data instead of re-running Step 1
python -m src.digital_twin_chile_x --treatment-arm b --skip-profile-search
```

> **Note (arms `b` / `c`):** Stage 2 inherits the `--enable-web-search` setting.
> The two-stage design intends predictions to be grounded only in the Stage 1
> evidence sheet, so pass `--no-enable-web-search` for a strictly evidence-only
> Stage 2.

### 4.5 Arm `c`: randomising Stage 2 option order

```bash
# Default: shuffle only nominal-scale questions
python -m src.digital_twin_chile_x --treatment-arm c

# Also shuffle ordinal-scale questions
python -m src.digital_twin_chile_x --treatment-arm c --shuffle-scope all

# Shuffle only specific questions, ignoring --shuffle-scope
python -m src.digital_twin_chile_x --treatment-arm c --shuffle-keys REGION,COMUNA,SEXO

# Shuffle every shuffleable question (ordering-sensitivity diagnostic)
python -m src.digital_twin_chile_x --treatment-arm c --shuffle-keys all

# Re-run with an independent reshuffle, without overwriting the first run's output
python -m src.digital_twin_chile_x --treatment-arm c --seed-suffix _v2
```

Each Arm C run writes a per-subject randomization log (which option order was
shown) to `randomization_logs/`, alongside the Stage 2 output, for audit.

### 4.6 Output location

Each run is namespaced by variant and treatment arm so runs never overwrite each
other. Results are written to:

```
data/digital-twin-chile-x/pilot_<variant>_arm_<arm>/
```

where `<variant>` reflects the profile-info and web-search settings, e.g.
`data/digital-twin-chile-x/pilot_with_profile_info_with_web_search_arm_b/`.

Subsampled and repeated runs extend that name with a sample tag and a run index:

```
data/digital-twin-chile-x/pilot_<variant>_arm_<arm>_n<size>_seed<seed>_<hash>_run<NN>/
```

The hash is taken over the sampled account list, so **the same tag always means
the same respondents** — swapping the roster under a fixed seed produces a
visibly different directory rather than silently colliding with the previous
one. A plain `--treatment-arm a` (no sample, one run) keeps writing to exactly
the unsegmented directory it always has.

### 4.7 Repeated runs over a random subsample

The pinned model accepts no `temperature` and the API exposes no seed, so
repeated interviews on identical input are genuinely independent draws. That is
what makes repeated-run variance measurable.

```bash
# 50 respondents, 5 repetitions, reproducible sample
python -m src.digital_twin_chile_x --treatment-arm c \
  --profile-roster profile_metadata.csv --profile-posts profile_tweets.csv \
  --sample-size 50 --seed 20251213 --num-runs 5

# See exactly what that would do, and what it would cost, without calling the API
python -m src.digital_twin_chile_x --treatment-arm c \
  --profile-roster profile_metadata.csv --profile-posts profile_tweets.csv \
  --sample-size 50 --seed 20251213 --num-runs 5 --dry-run

# Extend the same study from 5 runs to 10, reusing the same 50 respondents
python -m src.digital_twin_chile_x --treatment-arm c \
  --profile-roster profile_metadata.csv --profile-posts profile_tweets.csv \
  --sample-size 50 --seed 20251213 --num-runs 5 --run-index-start 6
```

Every one of those needs `--profile-roster` / `--profile-posts`, because the
default roster holds only 5 accounts and `--sample-size 50` against it is an
error. Sampling more than the roster contains always fails up front rather than
silently shrinking the study.

The same `--seed` and `--sample-size` always select the same respondents, so
arms and information conditions run as separate commands stay directly
comparable. Samples are **nested**: at a fixed seed the `n=10` sample is a
subset of `n=25`, so a study can be piloted small and scaled up without
discarding the earlier runs.

Every run directory gets a `run_manifest_<execution_date>.json` recording the
seed, sample size, the full sampled account list, the git commit, the model, and
the `custom_id → account_id` map. `custom_id` is a positional row index and is
only meaningful within one run — **join on `account_id`**.

**Coverage preflight.** Before any API call, the run checks that every sampled
account actually has posts in `--profile-posts`, and that the roster carries the
profile columns the prompts read. Both failures are otherwise silent: a missing
roster column renders as an empty prompt field, and an account with no posts
gets an empty post block, and in both cases the prompt is still assembled, sent
and billed. The run aborts rather than spend money on degraded prompts; pass
`--allow-missing-posts` to override.

Note the roster/corpus pairings currently available:

| Roster | Accounts | Post coverage | Prompt columns present |
| --- | --- | --- | --- |
| `final_meta_user_df_sample.csv` (default) | 5 | 5/5 in `test_tweets.csv` | 15/15 |
| `final_meta_user_df.csv` | 128 | **5/128** | 15/15 |
| `profile_metadata.csv` | 1041 | 1041/1041 in `profile_tweets.csv` | **9/15** |

### 4.8 Option ordering across repetitions

Arm C's option-order seed is `{subject_id}_{question}{suffix}` — independent of
the run index, so **option order stays fixed across `--num-runs` repetitions**.
That is deliberate: repetitions exist to estimate the model's sampling variance
with the instrument held fixed, and Arm C randomises order *between subjects*.
If order also varied per repetition, repeat-to-repeat variance would confound
ordering effects with model sampling and could not be decomposed. To vary
ordering instead, use a separate invocation with a different
`--option-order-seed-suffix`; it gets its own output namespace.

### 4.9 Web-search logging

Every interview writes a `<interview_type>_web_search_log` column holding a JSON
record of what the model retrieved: each search call (query, listed sources,
opened URLs) and the `url_citation` annotations from its answer, plus the
response id, status, retrieval timestamp and token usage.

```python
import json, pandas as pd
df = pd.read_csv("data/digital-twin-chile-x/<run>/post_arm_d_interview_<run>.csv")
logs = df["x_digital_twin_arm_d_web_search_log"].map(json.loads)
queries = [s.get("query") for log in logs for s in log["searches"]]
```

The column is present in every arm with the same shape — on non-web arms it
holds a payload with `"path": "batch"` and empty `searches`/`citations`, so
`map(json.loads)` needs no special-casing. Two fields are worth knowing:
`action: "unavailable"` means the API reported a search but no query (nothing to
recover), whereas `action: "unknown"` means an action type this code does not
parse yet, with the payload preserved under `raw`.

These CSVs already exceed Excel's 32,767-character cell limit; analyse them in
pandas or R.

### 4.10 Outcome-knowledge probe (run before production)

Registered leakage control 1: behavioural verification that the pinned model
cannot answer questions about the 2025 Chilean election from parametric
knowledge. Must be run before any production interview.

```bash
python -m scripts.outcome_knowledge_probe --dry-run   # show the battery, no API calls
python -m scripts.outcome_knowledge_probe             # 8 items x 3 reps = 24 calls
```

The battery is fixed by the 17 August 2026 selection memo §4 and is asked
verbatim in Spanish — items 1–2 are in-cutoff anchors the model *should*
answer, items 3–8 concern post-cutoff events it should not. Web search is
disabled (no tools attached) and no sampling parameters are sent.

Each run archives `probe_manifest.json`, `probe_responses.json` and
`probe_responses.csv` under `outcome_knowledge_probe/probe_<timestamp>/` —
deliberately outside `data/`, which is gitignored, so the archive can ship with
the registration materials.

**Scoring is left to a human.** The script classifies each response as a
refusal or a substantive answer, which is mechanically decidable; whether a
substantive answer is *correct* or *hallucinated* depends on the real-world
outcome, and an analyst records that verdict in the `score` column of the CSV.
A confidently wrong answer is the expected failure mode under the training
cutoff and does **not** block the run.

The script exits `2` and prints a prominent warning if either critical item
(5 — who won the ballotage; 7 — who is president-elect) draws a substantive
answer, since the registration requires reassessment before production in that
case. Exit `0` means every critical item was refused.

---