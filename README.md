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
| `--shuffle-scope` | `nominal`, `all` | `nominal` | Arm `c` only: which Stage 2 option lists to randomise. `nominal` shuffles only nominal-scale questions; `all` also shuffles ordinal scales. Ignored by other arms, and ignored if `--shuffle-keys` is given. |
| `--shuffle-keys` | comma-separated question keys, or `all` | unset | Arm `c` only: exact question keys to shuffle (e.g. `REGION,COMUNA,SEXO`), overriding `--shuffle-scope` entirely. Accepts any of Arm C's `SHUFFLEABLE_KEYS`, including `COMUNA` (otherwise always canonical order regardless of scope). Pass `all` to shuffle every shuffleable question (the split-sample "shuffle everything" diagnostic). |
| `--seed-suffix` | any string | `""` | Arm `c` only: appended to the per-question shuffle seed and to the randomization-log/predictions filenames, so a different suffix (e.g. `_v2`) reshuffles independently for repeated-seed sensitivity runs without overwriting the previous run's output. |

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

---