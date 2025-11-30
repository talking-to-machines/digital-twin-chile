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

This should start the main workflow of the **Digital Twin Chile** project.

---