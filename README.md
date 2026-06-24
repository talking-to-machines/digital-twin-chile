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

### 4.5 Output location

Each run is namespaced by variant and treatment arm so runs never overwrite each
other. Results are written to:

```
data/digital-twin-chile-x/pilot_<variant>_arm_<arm>/
```

where `<variant>` reflects the profile-info and web-search settings, e.g.
`data/digital-twin-chile-x/pilot_with_profile_info_with_web_search_arm_b/`.

---