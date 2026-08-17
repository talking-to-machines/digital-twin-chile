"""
Arm D — Minimal Sparse Prompt Template (free-text, post-hoc mapping)
AIPOP Chile — Digital Interview Pipeline

Rebuilt 2026-07-27 to match admin/pretesting-strategy_2.md section 2, which
specifies Arm D as: "Provides the social media data but with minimal
instructions. No explicit response categories — free-text output mapped to
categories post hoc." The previous implementation supplied compressed code
ranges (e.g. PARTIDO_POLITICO [PP1–PP15]), which is a different design: the
model still saw a code space per question. See QA report 06
(scripts/analysis/06_pilot_comparison_smoke_test_qa_matias.Rmd),
recommendation 12, and the pinned Asana task "Prompt Engineering Guide —
amendments and arm compliance".

Architecture: one call.
  Call 1 (elicitation — the sparse arm proper, and the only LLM call the
      Python pipeline makes for this arm):
      system = arm_d_system_prompt
      user   = arm_d_user_prompt   (fill {platform}, {name}, {account_id},
                                   {location}, {description}, {url},
                                   {created_at}, {is_verified},
                                   {is_blue_verified}, {protected},
                                   {followers}, {following},
                                   {statuses_count}, {favourites_count},
                                   {media_count}, {tweets},
                                   {profile_picture})
      The model answers each question in FREE TEXT (or "CI"), plus a
      speculation score (0-100) per question. pretesting-strategy_2.md
      Criterion 4 scopes the speculation-*calibration analysis* to Arms
      A/B/C but never excludes Arm D from producing the score itself; QA
      report 06 recommendation #11 treats Arm D's spec-compliance as an
      open decision, not a settled exclusion. Still no codes, no option
      lists -- only the response and speculation lines are added.

  Post-hoc mapping (mechanical coding, NOT part of the sparse manipulation,
      and NOT an LLM call): deliberately moved out of the Python pipeline and
      into R (scripts/build/), as deterministic keyword/regex matching
      against Call 1's free text -- no second LLM call, so no extra tokens,
      and the platform stays limited to interviewing. arm_d_mapping_system_prompt
      / arm_d_mapping_user_prompt_template below are kept only as a reference
      for the target code space per question (same option lists an R-side
      coder needs) -- they are not invoked by any driver code. Expect lower
      coding coverage/accuracy on the judgment-heavy questions (the seven
      FAVORABILIDAD_* items, TEMA_MAS_IMPORTANTE, and free-form income/age
      phrasing) than an LLM-based coder would give; that trade-off was a
      deliberate choice to avoid both extra tokens and in-platform cleaning.

Output format, Call 1 (one block of THREE lines per question):
  **question: <NOMBRE_PREGUNTA>**
  **response: <texto libre o CI>**
  **speculation: <puntuación 0-100>**

  "CI" = CANNOT_INFER (equivalent to Arms A/B/C; maps to NAD in the analysis
  dataset). Tag is "response" (English), not "respuesta", to reuse
  src/utils.py::extract_llm_responses()'s existing response_pattern and match
  every other arm's convention of English field tags in a Spanish-language
  prompt (question/symbol/category/explanation/speculation).

2026-07-27 content revisions shared with the other arms:
  - PP16 (Movimiento Amarillos Por Chile) added to the party code space; the
    fielded Q3.1 offers it.

2026-08-02/03 content revisions shared with the other arms (Ray's memo):
  - PP17 (No me identifico con un partido) added to the party code space,
    closing the item open since 27 Jul.
  - COMUNA is coded into the same COMU1-COMU346 space as Arms A/B/C. The
    free-text ELICITATION never sees codes (spec-compliant); the post-hoc
    MAPPER receives the full comuna list (imported from arm_b's programmatic
    extraction of Arm A's list) and assigns the COMU code, exactly as it does
    for every other question.

Communal (_COMUNAL) questions remain excluded, as in every arm: municipal
electoral data is an INPUT under information condition 4 (guide section 9.4),
not a block of output questions.

2026-07-29: added the speculation line to Call 1 (see above) so Arm D can be
scored on CI-speculation consistency for the architecture-pilot eligibility
rule (tracker item 6) and included in H5. Probability-distribution output
(the AI-RCT/Brier harmonization item) is deliberately NOT added here --
unlike speculation, it requires exposing each outcome's option list to the
model, which is a further departure from the sparse design; holding off
pending a separate decision.
"""

import os

from config.digital_twin_config import REFERENCE_DATE_SENTENCE

base_dir = os.path.dirname(os.path.abspath(__file__))

# Comuna code list — Arm A's, via arm_b's programmatic extraction, so all arms
# code COMUNA into the identical COMU1-COMU346 space. Used ONLY by the post-hoc
# mapper below; the sparse elicitation prompt never sees it.
from prompts.prompt_template_arm_b import comuna_option_list

# ─── Tweet formatter (shared) ─────────────────────────────────────────────────

x_tweet_prompt_template = """Creation Date: {created_at}
Tweet Text: {text}
Number of Likes: {like_count}
Number of Views: {view_count}
Number of Retweets: {retweet_count}
Number of Replies: {reply_count}
Number of Quotes: {quote_count}
Number of Bookmarks: {bookmark_count}
Language: {lang}
Tagged Users: {tagged_users}
Hashtags: {hashtags}"""

# ─── Call 1 — Sparse free-text elicitation ────────────────────────────────────

arm_d_system_prompt = f"""Usted está analizando un perfil de X (Twitter) de un usuario chileno.
Prediga cómo respondería esta persona a las preguntas de una encuesta política chilena.
Use únicamente la información disponible en el perfil. Responda en texto libre, breve y natural,
incluyendo siempre una breve justificación de su respuesta dentro de response (excepto cuando la
instrucción de la pregunta indique responder exactamente "NA", en cuyo caso no agregue nada más).
Para cada pregunta, produzca exactamente tres líneas: question, response y speculation. Debe
responder TODAS las preguntas de la lista, sin omitir ninguna, incluso si la respuesta es CI.
Escriba "CI" como respuesta cuando el perfil no proporcione información suficiente para predecir.
En speculation, indique con un puntaje de 0 a 100 cuánto especuló para llegar a su respuesta
(0 = evidencia directa en el perfil, 100 = conjetura pura sin evidencia).

{REFERENCE_DATE_SENTENCE}

Para las preguntas de intención de voto (incluida la segunda vuelta): piden la preferencia
política de esta persona, no si es elegible para votar. Si hay evidencia de residencia fuera de
Chile o alguna otra duda sobre elegibilidad, esa duda NO debe traducirse en una respuesta de
abstención ("no votó" / "no votaría"); responda igualmente según la preferencia política
observada (ideología, simpatía partidaria, sentimiento hacia los candidatos), como si esta
persona fuera a votar. Escriba "CI" únicamente cuando no exista ninguna señal política relevante
en el perfil — nunca como sustituto de una duda sobre residencia o elegibilidad.

Formato obligatorio: Encierre cada línea de la respuesta entre dos asteriscos (**) al inicio
y al final. Cada línea debe comenzar con el nombre del campo tal como en el ejemplo, seguido
de : , y terminar con **. No incluya texto fuera de los asteriscos ni líneas adicionales. Ejemplo:
**question: EDAD**
**response: 30 a 44 años**
**speculation: 30**"""

arm_d_user_prompt = """A continuación se presenta el perfil de X de un usuario chileno.

=== PERFIL ===
Usted está analizando un perfil de redes sociales en {platform} para responder a un conjunto de preguntas.
Los datos del perfil de {platform} incluyen:
- Imagen De Perfil: {profile_picture}
- Nombre Del Perfil: {name}
- ID De Perfil: {account_id}
- Ubicación: {location}
- Descripción Del Perfil: {description}
- Perfil Enlace Externo: {url}
- Fecha De Creación Del Perfil: {created_at}
- Perfil Verificado: {is_verified}
- Perfil Verificado Azul: {is_blue_verified}
- Perfil Protegido: {protected}
- Número De Seguidores: {followers} Seguidores
- Siguiendo: {following} Usuarios
- Número Total De Tweets: {statuses_count}
- Número De Favoritos: {favourites_count}
- Número De Contenido Multimedia: {media_count}
- Historial De Tweets (del más reciente al más antiguo):
{tweets}
=== FIN DEL PERFIL ===

Para cada pregunta de la lista a continuación, produzca exactamente el siguiente bloque:
**question: <NOMBRE_PREGUNTA>**
**response: <su respuesta en texto libre, o CI>**
**speculation: <puntaje 0-100 de cuánto especuló para responder>**

Preguntas:
PERSONA_REAL — ¿Es esta cuenta una persona real (no un bot, organización ni cuenta ficticia)?
PERSONA_VIVE_CHILE — ¿Vive esta persona en Chile?
REGION — ¿En qué región de Chile vive? (si la persona no vive en Chile, responda exactamente "NA"; si vive en Chile pero no hay evidencia suficiente para determinar la región, responda "CI")
COMUNA — ¿En qué comuna vive? (si la persona no vive en Chile, responda exactamente "NA"; si vive en Chile pero no hay evidencia suficiente para determinar la comuna, responda "CI")
EDAD — ¿Cuál es su edad?
SEXO — ¿Cuál es su género?
RANGO_INGRESOS_PERSONALES — ¿Cuál es su ingreso individual mensual aproximado, en pesos chilenos?
RANGO_INGRESOS_HOGAR — ¿Cuál es el ingreso mensual total aproximado de su hogar, en pesos chilenos?
ESTADO_CIVIL — ¿Cuál es su estado civil?
CALIFICACION_EDUCATIVA — ¿Cuál es su mayor nivel educacional?
OCUPACION_ACTUAL — ¿Cuál es su ocupación principal?
ORIENTACION_IDEOLOGICA — En una escala de 1 (Izquierda) a 10 (Derecha), ¿dónde se ubicaría políticamente?
PARTIDO_POLITICO — Generalmente, ¿con qué partido político chileno simpatiza?
AFINIDAD_PARTIDO — En una escala de 1 (ninguna simpatía) a 7 (mucha simpatía), ¿qué grado de afinidad siente por el partido que eligió?
INTERES_POLITICA — ¿Qué tanto le interesa la política en términos generales?
ATENCION_CAMPANA_2025 — ¿Cuánta atención prestó a la campaña para las elecciones generales de 2025?
ATENCION_CAMPANA_2021 — ¿Cuánta atención prestó a la campaña para las elecciones generales de 2021?
CONFIANZA_GENERAL — ¿Cree que se puede confiar en la mayoría de las personas, o que hay que ser muy cuidadoso?
PARTICIPACION_PRESIDENCIAL_2021 — ¿Votó esta persona en las elecciones presidenciales de 2021?
VOTO_PRESIDENCIAL_2021 — ¿Por quién votó en las elecciones presidenciales de 2021?
VOTO_BALLOTAGE_2021 — ¿Por quién votó en la segunda vuelta de las elecciones presidenciales de 2021?
INDV_PARTICIPACION_LEGISLATIVA_2021 — ¿Votó en las elecciones legislativas de 2021?
INDV_VOTO_LEGISLATIVO_2021 — ¿Por qué partido o lista votó en las elecciones legislativas de 2021?
INDV_PARTICIPACION_2025 — El 16 de noviembre de 2025 se realizaron las elecciones presidenciales en Chile. ¿Votó esta persona en la primera vuelta de esta elección?
INDV_INTENCION_VOTO_2025 — El 16 de noviembre de 2025 se realizaron las elecciones presidenciales en Chile. ¿Por quién votó en la primera vuelta de esta elección?
INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA — Ahora le preguntaremos sobre la segunda vuelta de las elecciones presidenciales, que se realizará el próximo domingo 14 de diciembre de 2025. Si las elecciones presidenciales fueran hoy, ¿por cuál de los siguientes candidatos votaría: Jeannette Jara o José Antonio Kast? (o si votaría nulo/blanco, no votaría, o no está seguro/a)
INDECISION_2025 — ¿Qué tan probable es que cambie su intención de voto antes de las elecciones de 2025?
FAVORABILIDAD_KAST — ¿Qué opinión tiene de José Antonio Kast?
FAVORABILIDAD_JARA — ¿Qué opinión tiene de Jeannette Jara?
FAVORABILIDAD_MATTHEI — ¿Qué opinión tiene de Evelyn Matthei?
FAVORABILIDAD_PARISI — ¿Qué opinión tiene de Franco Parisi?
FAVORABILIDAD_MEO — ¿Qué opinión tiene de Marco Enríquez-Ominami?
FAVORABILIDAD_ARTES — ¿Qué opinión tiene de Eduardo Artés?
FAVORABILIDAD_KAISER — ¿Qué opinión tiene de Johannes Kaiser?
TEMA_MAS_IMPORTANTE — ¿Cuál cree que es el problema más importante que enfrenta el país hoy en día?

¡USTED DEBE RESPONDER TODAS LAS PREGUNTAS DE LA LISTA, SIN OMITIR NINGUNA! Produzca un bloque de
tres líneas por pregunta, cada línea entre dos asteriscos (**question: ...**, **response: ...**,
**speculation: ...**), en el orden indicado!"""

# ─── Question labels (canonical var names, in prompt order) ──────────────────
#
# Drive the **field: value** parser for Call 1: scan the model output for
# **question: <label>** and extract the following "response" field.

ARM_D_QUESTION_LABELS = [
    "PERSONA_REAL",
    "PERSONA_VIVE_CHILE",
    "REGION",
    "COMUNA",
    "EDAD",
    "SEXO",
    "RANGO_INGRESOS_PERSONALES",
    "RANGO_INGRESOS_HOGAR",
    "ESTADO_CIVIL",
    "CALIFICACION_EDUCATIVA",
    "OCUPACION_ACTUAL",
    "ORIENTACION_IDEOLOGICA",
    "PARTIDO_POLITICO",
    "AFINIDAD_PARTIDO",
    "INTERES_POLITICA",
    "ATENCION_CAMPANA_2025",
    "ATENCION_CAMPANA_2021",
    "CONFIANZA_GENERAL",
    "PARTICIPACION_PRESIDENCIAL_2021",
    "VOTO_PRESIDENCIAL_2021",
    "VOTO_BALLOTAGE_2021",
    "INDV_PARTICIPACION_LEGISLATIVA_2021",
    "INDV_VOTO_LEGISLATIVO_2021",
    "INDV_PARTICIPACION_2025",
    "INDV_INTENCION_VOTO_2025",
    "INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA",
    "INDECISION_2025",
    "FAVORABILIDAD_KAST",
    "FAVORABILIDAD_JARA",
    "FAVORABILIDAD_MATTHEI",
    "FAVORABILIDAD_PARISI",
    "FAVORABILIDAD_MEO",
    "FAVORABILIDAD_ARTES",
    "FAVORABILIDAD_KAISER",
    "TEMA_MAS_IMPORTANTE",
]

# Canonical NAD marker (answer value when evidence is insufficient).
ARM_D_NO_DATA_MARKER = "CI"

# ─── Canonical variable map ───────────────────────────────────────────────────
#
# Maps each ARM_D_QUESTION_LABELS entry to its code space and Arm A question
# label. Documents the target code space the post-hoc mapping call codes into
# (the full option labels live in arm_d_mapping_user_prompt_template below),
# and supports cross-arm alignment in the analysis pipeline.

ARM_D_CANONICAL_MAP = {
    "PERSONA_REAL": {
        "code_space": "RP1=Persona real, RP2=Otro",
        "arm_a_field": "PERSONA REAL",
    },
    "PERSONA_VIVE_CHILE": {
        "code_space": "PLC1=Sí, PLC2=No",
        "arm_a_field": "PERSONA QUE VIVE EN CHILE",
    },
    "REGION": {
        "code_space": "REG1-REG17 (REG16=Metropolitana, REG17=NA)",
        "arm_a_field": "REGIÓN",
    },
    "COMUNA": {
        "code_space": "COMU1-COMU346 (lista completa en el prompt del mapper)",
        "arm_a_field": "COMUNA",
    },
    "EDAD": {
        "code_space": "AG1=18-29, AG2=30-44, AG3=45-64, AG4=65+",
        "arm_a_field": "EDAD",
    },
    "SEXO": {
        "code_space": "S1=Masculino, S2=Femenino",
        "arm_a_field": "SEXO",
    },
    "RANGO_INGRESOS_PERSONALES": {
        "code_space": "PINC1=$0-35k … PINC18=+$20M",
        "arm_a_field": "RANGO DE INGRESOS PERSONALES",
    },
    "RANGO_INGRESOS_HOGAR": {
        "code_space": "HINC1=$0-35k … HINC17=+$20M",
        "arm_a_field": "RANGO DE INGRESOS DEL HOGAR",
    },
    "ESTADO_CIVIL": {
        "code_space": "MAR1=Casado/a, MAR2=Separado/a, MAR3=Soltero/a, MAR4=Divorciado/a, MAR5=Viudo/a",
        "arm_a_field": "ESTADO CIVIL",
    },
    "CALIFICACION_EDUCATIVA": {
        "code_space": "EDU1-EDU14 (EDU6=Básica, EDU10=Técnico Superior, EDU11=Profesional, EDU12=Magíster, EDU13=Doctorado)",
        "arm_a_field": "CALIFICACIÓN EDUCATIVA MÁS ALTA",
    },
    "OCUPACION_ACTUAL": {
        "code_space": "OCCUP1=Patrón, OCCUP2=Cuenta propia, OCCUP3=Sector público, OCCUP4=Empresa pública, OCCUP5=Sector privado, OCCUP6=FF.AA., OCCUP7=Dom. adentro, OCCUP8=Dom. afuera",
        "arm_a_field": "OCUPACIÓN ACTUAL",
    },
    "ORIENTACION_IDEOLOGICA": {
        "code_space": "IoPoR1=1(Izq) … IoPoR10=10(Der)",
        "arm_a_field": "ORIENTACIÓN IDEOLÓGICA O POLÍTICA",
    },
    "PARTIDO_POLITICO": {
        "code_space": "PP1=Republicano, PP2=RN, PP3=FA, PP4=PC, PP5=PS, PP6=DC, PP7=UDI, PP8=PPD, PP9=PDG, PP10=Liberal, PP11=Demócratas Chile, PP12=EVOPOLI, PP13=Social Cristiano, PP14=Radical, PP15=FRVS, PP16=Amarillos, PP17=No me identifico",
        "arm_a_field": "PARTIDO POLÍTICO",
    },
    "AFINIDAD_PARTIDO": {
        "code_space": "Afi1-Afi7 (Afi1=ninguna simpatía, Afi7=mucha simpatía)",
        "arm_a_field": "AFINIDAD CON PARTIDO POLÍTICO",
    },
    "INTERES_POLITICA": {
        "code_space": "INTP1=Muy interesado/a, INTP2=Algo, INTP3=Poco, INTP4=Nada",
        "arm_a_field": "INTERÉS EN LA POLÍTICA",
    },
    "ATENCION_CAMPANA_2025": {
        "code_space": "ATT25_1=Mucho, ATT25_2=Algo, ATT25_3=Un poco, ATT25_4=Nada",
        "arm_a_field": "ATENCIÓN CAMPAÑA 2025",
    },
    "ATENCION_CAMPANA_2021": {
        "code_space": "ATT21_1=Mucho, ATT21_2=Algo, ATT21_3=Un poco, ATT21_4=Nada",
        "arm_a_field": "ATENCIÓN CAMPAÑA 2021",
    },
    "CONFIANZA_GENERAL": {
        "code_space": "TRUS1=Siempre confío, TRUS2=Mayoría del tiempo, TRUS3=~Mitad, TRUS4=Algunas veces, TRUS5=Nunca",
        "arm_a_field": "CONFIANZA GENERAL EN OTRAS PERSONAS",
    },
    "PARTICIPACION_PRESIDENCIAL_2021": {
        "code_space": "Thpa1=Sí, Thpa2=No, Thpa3=No recuerda",
        "arm_a_field": "VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021",
    },
    "VOTO_PRESIDENCIAL_2021": {
        "code_space": "Vpa1=no votó, Vpa2=Boric, Vpa3=Kast, Vpa4=Provoste, Vpa5=Sichel, Vpa6=Artés, Vpa7=MEO, Vpa8=Parisi",
        "arm_a_field": "VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021",
    },
    "VOTO_BALLOTAGE_2021": {
        "code_space": "Vba1=no votó, Vba2=Boric, Vba3=Kast, Vba4=no recuerda",
        "arm_a_field": "VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LA SEGUNDA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021",
    },
    "INDV_PARTICIPACION_LEGISLATIVA_2021": {
        "code_space": "Tpaindv1(prob=0) … Tpaindv7(prob=1)",
        "arm_a_field": "(INDV) VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021",
    },
    "INDV_VOTO_LEGISLATIVO_2021": {
        "code_space": "Vpaindv1=no votó, Vpaindv2=CS, Vpaindv3=RD, Vpaindv4=PC, Vpaindv5=PDC, Vpaindv6=PPD, Vpaindv7=UDI, Vpaindv8=RN, Vpaindv9=Republicano, Vpaindv10=PDG, Vpaindv11=PRO, Vpaindv12=independiente",
        "arm_a_field": "(INDV) VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021",
    },
    "INDV_PARTICIPACION_2025": {
        "code_space": "Tcuindv1=Sí, Tcuindv2=No, Tcuindv3=No recuerda",
        "arm_a_field": "(INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025",
    },
    "INDV_INTENCION_VOTO_2025": {
        "code_space": "Vcuindv1=no votó, Vcuindv2=Jara, Vcuindv3=Kast, Vcuindv4=Matthei, Vcuindv5=Kaiser, Vcuindv6=Parisi, Vcuindv7=MEO, Vcuindv8=Artés, Vcuindv9=Mayne-Nicholls",
        "arm_a_field": "(INDV) VOTACIÓN ACTUAL – OPCIÓN DE VOTO EN LA PRIMERA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025",
    },
    "INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA": {
        "code_space": "Vsv1=Jara, Vsv2=Kast, Vsv3=nulo/blanco, Vsv4=no votaría, Vsv5=no está seguro(a)",
        "arm_a_field": "(INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LA SEGUNDA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025",
    },
    "INDECISION_2025": {
        "code_space": "Und1(prob=0) … Und7(prob=1)",
        "arm_a_field": "INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025",
    },
    "FAVORABILIDAD_KAST": {
        "code_space": "Kfa1=muy favorable, Kfa2=algo favorable, Kfa3=algo desfavorable, Kfa4=muy desfavorable, Kfa5=desconozco",
        "arm_a_field": "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOSÉ ANTONIO KAST",
    },
    "FAVORABILIDAD_JARA": {
        "code_space": "Jfa1=muy favorable, Jfa2=algo favorable, Jfa3=algo desfavorable, Jfa4=muy desfavorable, Jfa5=desconozco",
        "arm_a_field": "FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA JEANNETTE JARA",
    },
    "FAVORABILIDAD_MATTHEI": {
        "code_space": "Efa1=muy favorable, Efa2=algo favorable, Efa3=algo desfavorable, Efa4=muy desfavorable, Efa5=desconozco",
        "arm_a_field": "FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA EVELYN MATTHEI",
    },
    "FAVORABILIDAD_PARISI": {
        "code_space": "Pfa1=muy favorable, Pfa2=algo favorable, Pfa3=algo desfavorable, Pfa4=muy desfavorable, Pfa5=desconozco",
        "arm_a_field": "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO FRANCO PARISI",
    },
    "FAVORABILIDAD_MEO": {
        "code_space": "Mfa1=muy favorable, Mfa2=algo favorable, Mfa3=algo desfavorable, Mfa4=muy desfavorable, Mfa5=desconozco",
        "arm_a_field": "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO MARCO ENRÍQUEZ-OMINAMI",
    },
    "FAVORABILIDAD_ARTES": {
        "code_space": "Afa1=muy favorable, Afa2=algo favorable, Afa3=algo desfavorable, Afa4=muy desfavorable, Afa5=desconozco",
        "arm_a_field": "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO EDUARDO ARTÉS",
    },
    "FAVORABILIDAD_KAISER": {
        "code_space": "JKfa1=muy favorable, JKfa2=algo favorable, JKfa3=algo desfavorable, JKfa4=muy desfavorable, JKfa5=desconozco",
        "arm_a_field": "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOHANNES KAISER",
    },
    "TEMA_MAS_IMPORTANTE": {
        "code_space": "Moi01=Economía, Moi02=Desempleo, Moi03=Corrupción, Moi04=Problemas políticos, Moi05=Delincuencia/seguridad, Moi06=Pobreza, Moi07=Educación, Moi08=Salud, Moi09=Desigualdad",
        "arm_a_field": "CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE",
    },
}

# ─── Call 2 — Post-hoc mapping (mechanical coding) ───────────────────────────
#
# This is NOT part of the sparse manipulation. The respondent-facing prompt
# above never shows codes or option lists; this second call codes the
# free-text answers into the canonical code space, exactly as a human coder
# would. Full option lists are appropriate here — the mapper is mechanical,
# and richness cannot contaminate the elicitation, which already happened.
# Output uses the Arm B JSON envelope so extract_json_predictions() works
# unchanged.

arm_d_mapping_system_prompt = """Usted es un codificador mecánico de respuestas de encuesta. Recibirá las respuestas en texto libre de un cuestionario y debe asignar a cada una el código de la opción que mejor corresponda, según las listas de opciones proporcionadas.

REGLAS ESTRICTAS:
1. Codifique ÚNICAMENTE a partir del texto libre de cada respuesta. No re-infiera desde ninguna otra fuente ni "mejore" la respuesta.
2. Si la respuesta es "CI", vacía, o no corresponde a ninguna opción, asigne el símbolo "CI" y la categoría "CANNOT_INFER".
3. El campo symbol debe contener ÚNICAMENTE el código (ej. AG3, PP7, CI). El campo category debe contener ÚNICAMENTE la etiqueta de la opción elegida. Nunca mezcle código y etiqueta en un mismo campo.
4. En explanation, cite el fragmento del texto libre que justifica el código asignado (máx. 1 frase).
5. Para COMUNA, seleccione el código COMU de la lista completa de comunas al final del prompt (o CI si la respuesta no corresponde a ninguna comuna).
6. El output DEBE ser un JSON válido con la estructura indicada. No incluya texto fuera del JSON."""

arm_d_mapping_user_prompt_template = """Cuenta analizada: {account_id}

=== RESPUESTAS EN TEXTO LIBRE (Call 1) ===
{free_text_answers}
=== FIN DE RESPUESTAS ===

Codifique cada respuesta con la opción que mejor corresponda y devuelva ÚNICAMENTE un objeto JSON válido con esta estructura:

{{
  "subject_id": "{account_id}",
  "pipeline_stage": "d_mapping",
  "predictions": {{
    "EDAD": {{"question": "EDAD", "symbol": "<código o CI>", "category": "<etiqueta de la opción>", "explanation": "<fragmento del texto libre que lo justifica>"}},
    "...": "... una entrada con la misma estructura por CADA pregunta listada abajo ..."
  }}
}}

Listas de opciones por pregunta:

PERSONA_REAL: RP1) Persona real | RP2) Otro (bot, organización, cuenta ficticia)
PERSONA_VIVE_CHILE: PLC1) Sí | PLC2) No
REGION: REG1) Antofagasta | REG2) Arica y Parinacota | REG3) Atacama | REG4) Aysén | REG5) Coquimbo | REG6) Araucanía | REG7) Los Lagos | REG8) Los Ríos | REG9) Magallanes | REG10) Tarapacá | REG11) Valparaíso | REG12) Ñuble | REG13) Biobío | REG14) O'Higgins | REG15) Maule | REG16) Metropolitana de Santiago | REG17) NA — no vive en Chile o región desconocida
COMUNA: seleccione el código COMU de la lista completa al final del prompt, o CI
EDAD: AG1) De 18 a 29 años | AG2) De 30 a 44 años | AG3) De 45 a 64 años | AG4) 65 años o más
SEXO: S1) Masculino | S2) Femenino
RANGO_INGRESOS_PERSONALES: PINC1) $0-$35.000 | PINC2) $35.001-$100.000 | PINC3) $100.001-$210.000 | PINC4) $210.001-$350.000 | PINC5) $350.001-$500.000 | PINC6) $500.001-$700.000 | PINC7) $700.001-$900.000 | PINC8) $900.001-$1.200.000 | PINC9) $1.200.001-$1.500.000 | PINC10) $1.500.001-$1.800.000 | PINC11) $1.800.001-$2.500.000 | PINC12) $2.500.001-$3.500.000 | PINC13) $3.500.001-$5.000.000 | PINC14) $5.000.001-$7.000.000 | PINC15) $7.000.001-$10.000.000 | PINC16) $10.000.001-$15.000.000 | PINC17) $15.000.001-$20.000.000 | PINC18) Más de $20.000.000
RANGO_INGRESOS_HOGAR: HINC1) $0-$35.000 | HINC2) $35.001-$60.000 | HINC3) $60.001-$100.000 | HINC4) $100.001-$200.000 | HINC5) $200.001-$350.000 | HINC6) $350.001-$500.000 | HINC7) $500.001-$750.000 | HINC8) $750.001-$1.000.000 | HINC9) $1.000.001-$1.500.000 | HINC10) $1.500.001-$2.000.000 | HINC11) $2.000.001-$3.000.000 | HINC12) $3.000.001-$5.000.000 | HINC13) $5.000.001-$7.500.000 | HINC14) $7.500.001-$10.000.000 | HINC15) $10.000.001-$15.000.000 | HINC16) $15.000.001-$20.000.000 | HINC17) Más de $20.000.000
ESTADO_CIVIL: MAR1) Casado(a) | MAR2) Separado(a) | MAR3) Soltero(a) | MAR4) Divorciado(a) | MAR5) Viudo(a)
CALIFICACION_EDUCATIVA: EDU1) Sala Cuna o Jardín Infantil | EDU2) PreKinder | EDU3) Kinder | EDU4) Especial o Diferencial | EDU5) Primaria o Preparatoria (sistema antiguo) | EDU6) Educación Básica | EDU7) Científico-Humanista | EDU8) Técnica Profesional | EDU9) Humanidades (sistema antiguo) | EDU10) Técnico Nivel Superior (carreras 1-4 años) | EDU11) Profesional (carreras 1-6 años) | EDU12) Magíster | EDU13) Doctorado | EDU14) Nunca asistió
OCUPACION_ACTUAL: OCCUP1) Patrón o dueño de empresa o negocio | OCCUP2) Trabajador por cuenta propia | OCCUP3) Empleado u obrero del sector público | OCCUP4) Empleado u obrero de empresas públicas | OCCUP5) Empleado u obrero del sector privado | OCCUP6) Fuerzas Armadas, de Orden y Seguridad | OCCUP7) Servicio doméstico puertas adentro | OCCUP8) Servicio doméstico puertas afuera
ORIENTACION_IDEOLOGICA: IoPoR1) 1 (Izquierda) | IoPoR2) 2 | IoPoR3) 3 | IoPoR4) 4 | IoPoR5) 5 (Centro) | IoPoR6) 6 | IoPoR7) 7 | IoPoR8) 8 | IoPoR9) 9 | IoPoR10) 10 (Derecha)
PARTIDO_POLITICO: PP1) Partido Republicano | PP2) Renovación Nacional (RN) | PP3) Frente Amplio | PP4) Partido Comunista (PC) | PP5) Partido Socialista (PS) | PP6) Democracia Cristiana (DC) | PP7) Unión Demócrata Independiente (UDI) | PP8) Partido Por la Democracia (PPD) | PP9) Partido de la Gente (PDG) | PP10) Partido Liberal | PP11) Partido Demócratas Chile | PP12) Evolución Política (EVOPOLI) | PP13) Partido Social Cristiano | PP14) Partido Radical (PR) | PP15) Frente Regionalista Verde Social (FRVS) | PP16) Movimiento Amarillos Por Chile | PP17) No me identifico con un partido
AFINIDAD_PARTIDO: Afi1) Ninguna simpatía | Afi2) | Afi3) | Afi4) | Afi5) | Afi6) | Afi7) Mucha simpatía
INTERES_POLITICA: INTP1) Muy interesado(a) | INTP2) Algo interesado(a) | INTP3) Poco interesado(a) | INTP4) Nada interesado(a)
ATENCION_CAMPANA_2025: ATT25_1) Mucho | ATT25_2) Algo | ATT25_3) Un poco | ATT25_4) Nada
ATENCION_CAMPANA_2021: ATT21_1) Mucho | ATT21_2) Algo | ATT21_3) Un poco | ATT21_4) Nada
CONFIANZA_GENERAL: TRUS1) Siempre confío en otras personas | TRUS2) La mayor parte del tiempo confío | TRUS3) Aproximadamente la mitad del tiempo confío | TRUS4) Algunas veces confío | TRUS5) Nunca confío
PARTICIPACION_PRESIDENCIAL_2021: Thpa1) Sí, votó | Thpa2) No votó | Thpa3) No recuerda
VOTO_PRESIDENCIAL_2021: Vpa1) No votó | Vpa2) Gabriel Boric | Vpa3) José Antonio Kast | Vpa4) Yasna Provoste | Vpa5) Sebastián Sichel | Vpa6) Eduardo Artés | Vpa7) Marco Enríquez-Ominami | Vpa8) Franco Parisi
VOTO_BALLOTAGE_2021: Vba1) No votó | Vba2) Gabriel Boric | Vba3) José Antonio Kast | Vba4) No recuerda
INDV_PARTICIPACION_LEGISLATIVA_2021: Tpaindv1) No hay posibilidad de que haya votado (prob=0) | Tpaindv2) Muy improbable (0,15) | Tpaindv3) Poco probable (0,3) | Tpaindv4) 50% de probabilidades (0,5) | Tpaindv5) Probable (0,7) | Tpaindv6) Muy probable (0,85) | Tpaindv7) Certeza de que votó (prob=1)
INDV_VOTO_LEGISLATIVO_2021: Vpaindv1) No votó | Vpaindv2) Convergencia Social (CS) | Vpaindv3) Revolución Democrática (RD) | Vpaindv4) Partido Comunista (PC) | Vpaindv5) PDC | Vpaindv6) PPD | Vpaindv7) UDI | Vpaindv8) RN | Vpaindv9) Partido Republicano | Vpaindv10) PDG | Vpaindv11) PRO | Vpaindv12) Independiente
INDV_PARTICIPACION_2025: Tcuindv1) Sí, votó | Tcuindv2) No votó | Tcuindv3) No recuerda
INDV_INTENCION_VOTO_2025: Vcuindv1) No votó | Vcuindv2) Jeannette Jara | Vcuindv3) José Antonio Kast | Vcuindv4) Evelyn Matthei | Vcuindv5) Johannes Kaiser | Vcuindv6) Franco Parisi | Vcuindv7) Marco Enríquez-Ominami | Vcuindv8) Eduardo Artés | Vcuindv9) Harold Mayne-Nicholls
INDECISION_2025: Und1) No hay posibilidad de cambio (prob=0) | Und2) Muy improbable que cambie (0,15) | Und3) Poco probable que cambie (0,3) | Und4) 50% de probabilidades de cambio (0,5) | Und5) Probable que cambie (0,7) | Und6) Muy probable que cambie (0,85) | Und7) Certeza de que cambiará (prob=1)
FAVORABILIDAD_KAST: Kfa1) Opinión muy favorable | Kfa2) Algo favorable | Kfa3) Algo desfavorable | Kfa4) Muy desfavorable | Kfa5) Desconoce al candidato
FAVORABILIDAD_JARA: Jfa1) Opinión muy favorable | Jfa2) Algo favorable | Jfa3) Algo desfavorable | Jfa4) Muy desfavorable | Jfa5) Desconoce a la candidata
FAVORABILIDAD_MATTHEI: Efa1) Opinión muy favorable | Efa2) Algo favorable | Efa3) Algo desfavorable | Efa4) Muy desfavorable | Efa5) Desconoce a la candidata
FAVORABILIDAD_PARISI: Pfa1) Opinión muy favorable | Pfa2) Algo favorable | Pfa3) Algo desfavorable | Pfa4) Muy desfavorable | Pfa5) Desconoce al candidato
FAVORABILIDAD_MEO: Mfa1) Opinión muy favorable | Mfa2) Algo favorable | Mfa3) Algo desfavorable | Mfa4) Muy desfavorable | Mfa5) Desconoce al candidato
FAVORABILIDAD_ARTES: Afa1) Opinión muy favorable | Afa2) Algo favorable | Afa3) Algo desfavorable | Afa4) Muy desfavorable | Afa5) Desconoce al candidato
FAVORABILIDAD_KAISER: JKfa1) Opinión muy favorable | JKfa2) Algo favorable | JKfa3) Algo desfavorable | JKfa4) Muy desfavorable | JKfa5) Desconoce al candidato
TEMA_MAS_IMPORTANTE: Moi01) Economía | Moi02) Desempleo | Moi03) Corrupción | Moi04) Problemas políticos | Moi05) Delincuencia / seguridad pública | Moi06) Pobreza | Moi07) Educación | Moi08) Salud | Moi09) Desigualdad de ingresos

Lista completa de comunas (COMUNA):
""" + comuna_option_list
