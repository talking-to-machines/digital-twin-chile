import hashlib
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="config/.env")

base_dir = os.path.dirname(os.path.abspath(__file__))

PROJECT_NAME = "digital-twin-chile-x"
INCLUDE_PROFILE_INFORMATION = (
    True  # NOTE: SET THIS TRUE OR FALSE FOR EACH VARIANT EXECUTION
)
ENABLE_WEB_SEARCH = True  # NOTE: SET THIS TRUE OR FALSE FOR EACH VARIANT EXECUTION
PIPELINE_EXECUTION_DATE = "pilot_"

if ENABLE_WEB_SEARCH and INCLUDE_PROFILE_INFORMATION:
    PIPELINE_EXECUTION_DATE += "with_profile_info_with_web_search"
elif ENABLE_WEB_SEARCH and not INCLUDE_PROFILE_INFORMATION:
    PIPELINE_EXECUTION_DATE += "without_profile_info_with_web_search"
elif not ENABLE_WEB_SEARCH and INCLUDE_PROFILE_INFORMATION:
    PIPELINE_EXECUTION_DATE += "with_profile_info_without_web_search"
else:
    PIPELINE_EXECUTION_DATE += "without_profile_info_without_web_search"

PROFILE_SEARCH_START_DATE = "01-01-2000"  # MM-DD-YYYY format
PROFILE_SEARCH_END_DATE = "12-31-2025"  # MM-DD-YYYY format

# Reference-date instruction (Ray, Slack #digital-twins, 2026-08-08): one
# identical passage in the context block of every architecture (A-D) and every
# arm, both stages for B/C. WEB_SEARCH_CUTOFF_SENTENCE is the additional
# sentence riding the web-search toggle for arms 2 and 4 only — see
# construct_system_prompt() in src/utils.py.
REFERENCE_DATE_SENTENCE = (
    "Fecha de referencia: para este análisis, la fecha actual es el 13 de "
    "diciembre de 2025; responda solo con información disponible hasta esa "
    "fecha, sin conocimiento de eventos posteriores."
)
WEB_SEARCH_CUTOFF_SENTENCE = (
    "Su búsqueda web no debe incluir contenido publicado después del 13 de "
    "diciembre de 2025."
)

WEB_SEARCH_COUNTRY = "CL"
NUM_POSTS_PER_PROFILE = 100
PROFILE_METADATA_SEARCH_FILE = f"profile_metadata_{PIPELINE_EXECUTION_DATE}.csv"
PROFILE_SEARCH_FILE = f"profile_search_{PIPELINE_EXECUTION_DATE}.csv"
POST_ENTITY_GEOGRAPHIC_INTERVIEW_FILE = (
    f"post_entity_geographic_interview_{PIPELINE_EXECUTION_DATE}.csv"
)
POST_VOTING_PREFERENCE_WO_VOTING_RESULTS_INTERVIEW_FILE = (
    f"post_voting_preference_interview_wo_voting_results_{PIPELINE_EXECUTION_DATE}.csv"
)
POST_VOTING_PREFERENCE_WITH_VOTING_RESULTS_INTERVIEW_FILE = f"post_voting_preference_interview_with_voting_results_{PIPELINE_EXECUTION_DATE}.csv"


def build_variant_suffix(include_profile_info: bool, enable_web_search: bool) -> str:
    """Build the information-condition suffix used in output paths.

    The two booleans form the 2x2 of information conditions (the
    pre-registration's Arms 1-4), which is orthogonal to the prompt
    architecture chosen by ``--treatment-arm``.

    Args:
        include_profile_info (bool): Whether the participant's profile fields
            and posts are included in the prompts.
        enable_web_search (bool): Whether the web-search tool is attached.

    Returns:
        str: One of ``with_profile_info_with_web_search``,
        ``without_profile_info_with_web_search``,
        ``with_profile_info_without_web_search`` or
        ``without_profile_info_without_web_search``.
    """
    if enable_web_search and include_profile_info:
        return "with_profile_info_with_web_search"
    elif enable_web_search and not include_profile_info:
        return "without_profile_info_with_web_search"
    elif not enable_web_search and include_profile_info:
        return "with_profile_info_without_web_search"
    else:
        return "without_profile_info_without_web_search"


def build_sample_tag(seed: int, account_ids: "list[str]") -> str:
    """Identify a user subsample by size, seed and a hash of its members.

    Hashing the *resulting sample* rather than the inputs means the tag subsumes
    the roster file, the seed and the requested size at once, and gives the
    guarantee ``same tag <=> same user set``. Swapping the roster underneath a
    fixed seed therefore produces a visibly different output directory instead
    of silently colliding with the previous one.

    Args:
        seed (int): The seed that produced this sample, recorded in the tag so
            the directory name states how to reproduce it.
        account_ids (list[str]): The sampled account ids. Order-invariant --
            the caller passes them sorted so the digest is canonical.

    Returns:
        str: A tag of the form ``n<size>_seed<seed>_<6-char sha256 prefix>``,
        e.g. ``n50_seed20251213_1f3a9c``.
    """
    digest = hashlib.sha256("\n".join(account_ids).encode("utf-8")).hexdigest()
    return f"n{len(account_ids)}_seed{seed}_{digest[:6]}"


def build_execution_date(
    include_profile_info: bool,
    enable_web_search: bool,
    treatment_arm: str,
    *,
    sample_tag: str = "",
    run_index: "int | None" = None,
) -> str:
    """Namespace each run by variant and treatment arm so outputs never clobber.

    The returned string is used two ways at once: as the output *directory*
    name under ``data/<project>/`` and as a *suffix* on every artifact inside
    it. Extending it here is therefore what keeps repeated runs from
    overwriting each other, including the otherwise fixed
    ``batch-files/batch_input.jsonl`` and ``randomization_logs/`` names.

    Args:
        include_profile_info (bool): Whether profile fields and posts are in
            the prompts.
        enable_web_search (bool): Whether the web-search tool is attached.
        treatment_arm (str): Prompt architecture key, e.g. ``"a"`` or ``"c"``.
        sample_tag (str): Optional subsample identifier from
            :func:`build_sample_tag`. Empty (default) omits the segment.
        run_index (int | None): Optional repetition index, rendered as
            ``_runNN``. ``None`` (default) omits the segment.

    Returns:
        str: e.g. ``pilot_with_profile_info_with_web_search_arm_a`` for a plain
        run, or
        ``pilot_with_profile_info_with_web_search_arm_c_n50_seed20251213_1f3a9c_run03``
        for run 3 of a seeded 50-respondent study.

    Note:
        ``sample_tag`` and ``run_index`` are keyword-only and default to the
        legacy behaviour, so existing three-positional-argument callers (such
        as ``scripts/export_appendix_b.py``) produce byte-identical output.
    """
    variant = build_variant_suffix(include_profile_info, enable_web_search)
    name = f"pilot_{variant}_arm_{treatment_arm}"
    if sample_tag:
        name += f"_{sample_tag}"
    if run_index is not None:
        name += f"_run{run_index:02d}"
    return name


ENTITY_GEOGRAPHIC_INTERVIEW_REGEX_PATTERNS = [
    r"^PERSONA REAL.*\-\s*explanation$",
    r"^PERSONA REAL.*\-\s*symbol$",
    r"^PERSONA REAL.*\-\s*category$",
    r"^PERSONA REAL.*\-\s*speculation$",
    r"^PERSONA QUE VIVE EN CHILE.*\-\s*explanation$",
    r"^PERSONA QUE VIVE EN CHILE.*\-\s*symbol$",
    r"^PERSONA QUE VIVE EN CHILE.*\-\s*category$",
    r"^PERSONA QUE VIVE EN CHILE.*\-\s*speculation$",
    r"^REGIÓN.*\-\s*explanation$",
    r"^REGIÓN.*\-\s*symbol$",
    r"^REGIÓN.*\-\s*category$",
    r"^REGIÓN.*\-\s*speculation$",
    r"^COMUNA.*\-\s*explanation$",
    r"^COMUNA.*\-\s*symbol$",
    r"^COMUNA.*\-\s*category$",
    r"^COMUNA.*\-\s*speculation$",
]

VOTING_PREFERENCE_INTERVIEW_WO_VOTING_RESULTS_REGEX_PATTERNS = [
    r"^EDAD.*\-\s*symbol$",
    r"^EDAD.*\-\s*category$",
    r"^EDAD.*\-\s*speculation$",
    r"^EDAD.*\-\s*explanation$",
    r"^SEXO.*\-\s*symbol$",
    r"^SEXO.*\-\s*category$",
    r"^SEXO.*\-\s*speculation$",
    r"^SEXO.*\-\s*explanation$",
    r"^RANGO DE INGRESOS PERSONALES.*\-\s*symbol$",
    r"^RANGO DE INGRESOS PERSONALES.*\-\s*category$",
    r"^RANGO DE INGRESOS PERSONALES.*\-\s*speculation$",
    r"^RANGO DE INGRESOS PERSONALES.*\-\s*explanation$",
    r"^RANGO DE INGRESOS DEL HOGAR.*\-\s*symbol$",
    r"^RANGO DE INGRESOS DEL HOGAR.*\-\s*category$",
    r"^RANGO DE INGRESOS DEL HOGAR.*\-\s*speculation$",
    r"^RANGO DE INGRESOS DEL HOGAR.*\-\s*explanation$",
    r"^ESTADO CIVIL.*\-\s*symbol$",
    r"^ESTADO CIVIL.*\-\s*category$",
    r"^ESTADO CIVIL.*\-\s*speculation$",
    r"^ESTADO CIVIL.*\-\s*explanation$",
    r"^CALIFICACIÓN EDUCATIVA MÁS ALTA.*\-\s*symbol$",
    r"^CALIFICACIÓN EDUCATIVA MÁS ALTA.*\-\s*category$",
    r"^CALIFICACIÓN EDUCATIVA MÁS ALTA.*\-\s*speculation$",
    r"^CALIFICACIÓN EDUCATIVA MÁS ALTA.*\-\s*explanation$",
    r"^OCUPACIÓN ACUTAL.*\-\s*symbol$",
    r"^OCUPACIÓN ACUTAL.*\-\s*category$",
    r"^OCUPACIÓN ACUTAL.*\-\s*speculation$",
    r"^OCUPACIÓN ACUTAL.*\-\s*explanation$",
    r"^ORIENTACIÓN IDEOLÓGICA O POLÍTICA.*\-\s*symbol$",
    r"^ORIENTACIÓN IDEOLÓGICA O POLÍTICA.*\-\s*category$",
    r"^ORIENTACIÓN IDEOLÓGICA O POLÍTICA.*\-\s*speculation$",
    r"^ORIENTACIÓN IDEOLÓGICA O POLÍTICA.*\-\s*explanation$",
    r"^PARTIDO POLÍTICO.*\-\s*symbol$",
    r"^PARTIDO POLÍTICO.*\-\s*category$",
    r"^PARTIDO POLÍTICO.*\-\s*speculation$",
    r"^PARTIDO POLÍTICO.*\-\s*explanation$",
    r"^AFINIDAD CON PARTIDO POLÍTICO.*\-\s*value$",
    r"^AFINIDAD CON PARTIDO POLÍTICO.*\-\s*speculation$",
    r"^AFINIDAD CON PARTIDO POLÍTICO.*\-\s*explanation$",
    r"^INTERÉS EN LA POLÍTICA.*\-\s*symbol$",
    r"^INTERÉS EN LA POLÍTICA.*\-\s*category$",
    r"^INTERÉS EN LA POLÍTICA.*\-\s*speculation$",
    r"^INTERÉS EN LA POLÍTICA.*\-\s*explanation$",
    r"^ATENCIÓN CAMPAÑA 2025.*\-\s*symbol$",
    r"^ATENCIÓN CAMPAÑA 2025.*\-\s*category$",
    r"^ATENCIÓN CAMPAÑA 2025.*\-\s*speculation$",
    r"^ATENCIÓN CAMPAÑA 2025.*\-\s*explanation$",
    r"^ATENCIÓN CAMPAÑA 2021.*\-\s*symbol$",
    r"^ATENCIÓN CAMPAÑA 2021.*\-\s*category$",
    r"^ATENCIÓN CAMPAÑA 2021.*\-\s*speculation$",
    r"^ATENCIÓN CAMPAÑA 2021.*\-\s*explanation$",
    r"^CONFIANZA GENERAL EN OTRAS PERSONAS.*\-\s*symbol$",
    r"^CONFIANZA GENERAL EN OTRAS PERSONAS.*\-\s*category$",
    r"^CONFIANZA GENERAL EN OTRAS PERSONAS.*\-\s*speculation$",
    r"^CONFIANZA GENERAL EN OTRAS PERSONAS.*\-\s*explanation$",
    r"^\(INDV\) VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*symbol$",
    r"^\(INDV\) VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*category$",
    r"^\(INDV\) VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*speculation$",
    r"^\(INDV\) VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*explanation$",
    r"^\(INDV\) VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*symbol$",
    r"^\(INDV\) VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*category$",
    r"^\(INDV\) VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*speculation$",
    r"^\(INDV\) VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*explanation$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*symbol$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*category$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*speculation$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*explanation$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*symbol$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*category$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*speculation$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*explanation$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LA SEGUNDA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*symbol$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LA SEGUNDA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*category$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LA SEGUNDA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*speculation$",
    r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LA SEGUNDA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*explanation$",
    r"^\(INDV\) PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*symbol$",
    r"^\(INDV\) PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*category$",
    r"^\(INDV\) PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*speculation$",
    r"^\(INDV\) PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*explanation$",
    r"^\(INDV\) VOTACIÓN ACTUAL\s[-–—]\sOPCIÓN DE VOTO EN LA PRIMERA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*symbol$",
    r"^\(INDV\) VOTACIÓN ACTUAL\s[-–—]\sOPCIÓN DE VOTO EN LA PRIMERA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*category$",
    r"^\(INDV\) VOTACIÓN ACTUAL\s[-–—]\sOPCIÓN DE VOTO EN LA PRIMERA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*speculation$",
    r"^\(INDV\) VOTACIÓN ACTUAL\s[-–—]\sOPCIÓN DE VOTO EN LA PRIMERA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*explanation$",
    r"^INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*symbol$",
    r"^INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*category$",
    r"^INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*speculation$",
    r"^INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*explanation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOSÉ ANTONIO KAST.*\-\s*symbol$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOSÉ ANTONIO KAST.*\-\s*category$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOSÉ ANTONIO KAST.*\-\s*speculation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOSÉ ANTONIO KAST.*\-\s*explanation$",
    r"^FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA JEANNETTE JARA.*\-\s*symbol$",
    r"^FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA JEANNETTE JARA.*\-\s*category$",
    r"^FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA JEANNETTE JARA.*\-\s*speculation$",
    r"^FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA JEANNETTE JARA.*\-\s*explanation$",
    r"^FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA EVELYN MATTHEI.*\-\s*symbol$",
    r"^FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA EVELYN MATTHEI.*\-\s*category$",
    r"^FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA EVELYN MATTHEI.*\-\s*speculation$",
    r"^FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA EVELYN MATTHEI.*\-\s*explanation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO FRANCO PARISI.*\-\s*symbol$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO FRANCO PARISI.*\-\s*category$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO FRANCO PARISI.*\-\s*speculation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO FRANCO PARISI.*\-\s*explanation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO MARCO ENRÍQUEZ-OMINAMI.*\-\s*symbol$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO MARCO ENRÍQUEZ-OMINAMI.*\-\s*category$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO MARCO ENRÍQUEZ-OMINAMI.*\-\s*speculation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO MARCO ENRÍQUEZ-OMINAMI.*\-\s*explanation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO EDUARDO ARTÉS.*\-\s*symbol$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO EDUARDO ARTÉS.*\-\s*category$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO EDUARDO ARTÉS.*\-\s*speculation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO EDUARDO ARTÉS.*\-\s*explanation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOHANNES KAISER.*\-\s*symbol$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOHANNES KAISER.*\-\s*category$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOHANNES KAISER.*\-\s*speculation$",
    r"^FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOHANNES KAISER.*\-\s*explanation$",
    r"^CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE.*\-\s*symbol$",
    r"^CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE.*\-\s*category$",
    r"^CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE.*\-\s*speculation$",
    r"^CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE.*\-\s*explanation$",
    r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025 SI LAS ELECCIONES SE CELEBRARAN EN LA FECHA DE SU ÚLTIMO TUIT.*\-\s*symbol$",
    r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025 SI LAS ELECCIONES SE CELEBRARAN EN LA FECHA DE SU ÚLTIMO TUIT.*\-\s*category$",
    r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025 SI LAS ELECCIONES SE CELEBRARAN EN LA FECHA DE SU ÚLTIMO TUIT.*\-\s*speculation$",
    r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025 SI LAS ELECCIONES SE CELEBRARAN EN LA FECHA DE SU ÚLTIMO TUIT.*\-\s*explanation$",
]

# VOTING_PREFERENCE_INTERVIEW_WITH_VOTING_RESULTS_REGEX_PATTERNS = [
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*symbol$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*category$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*speculation$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*explanation$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*symbol$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*category$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*speculation$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021.*\-\s*explanation$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE 2021.*\-\s*symbol$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE 2021.*\-\s*category$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE 2021.*\-\s*speculation$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE 2021.*\-\s*explanation$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*symbol$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*category$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*speculation$",
#     r"^VOTACIÓN ANTERIOR\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021.*\-\s*explanation$",
#     r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*symbol$",
#     r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*category$",
#     r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*speculation$",
#     r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sPARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*explanation$",
#     r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*symbol$",
#     r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*category$",
#     r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*speculation$",
#     r"^PREFERENCIAS DE VOTACIÓN ACTUALES\s[-–—]\sOPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025.*\-\s*explanation$",
# ]
