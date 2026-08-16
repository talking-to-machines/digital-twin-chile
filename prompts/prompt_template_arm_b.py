"""
Arm B — Two-Stage Evidence-Extraction Prompt Template
AIPOP Chile — Digital Interview Pipeline

Architecture: two-stage.
  Stage 1: evidence extraction from raw profile → JSON evidence sheet.
  Stage 2: survey response prediction from evidence sheet → JSON predictions.

Pipeline calls:
  Call 1 (Stage 1):
      system = arm_b_stage1_system_prompt
      user   = arm_b_stage1_user_prompt   (fill {platform}, {name}, {account_id},
                                           {location}, {description}, {url},
                                           {created_at}, {is_verified},
                                           {is_blue_verified}, {protected},
                                           {followers}, {following},
                                           {statuses_count}, {favourites_count},
                                           {media_count}, {tweets},
                                           {profile_picture})

  Call 2 (Stage 2):
      system = arm_b_stage2_system_prompt
      user   = arm_b_stage2_user_prompt   (fill {stage_1_output_json} with the
                                           raw string output of Call 1)

Output parsing:
  Both stages return JSON. Parse with json.loads().
  Stage 1 keys: see arm_b_stage1_output_schema (documentation reference).
  Stage 2 keys: predictions.<FIELD>.symbol / .category / .speculation / .evidence_basis
               cannot_infer_fields (list), high_speculation_fields (list).
  CANNOT_INFER symbol ("CI") maps to NAD in the analysis dataset.

2026-07-27 revision (QA report 06, recommendations 1a/1b/3/4/5/7/15/16):
  - The six *_COMUNAL questions are REMOVED. Stage 2 now asks the same 33
    questions as Arm A. Municipal electoral data is an INPUT for information
    condition 4 only (guide section 9.4): see arm_b_municipal_web_instruction,
    to be appended to the Stage 2 system prompt by the driver when
    enable_web_search is True. Not wired yet.
  - COMUNA uses the SAME full COMU1-COMU346 code list as Arm A. The list is
    extracted programmatically from prompt_template_arm_a.py at import time
    (comuna_option_list below), so the two arms cannot drift.
  - Reference categories are complete (no elisions); every symbol placeholder
    in the Stage 2 schema enumerates its codes explicitly (PP1|PP2|...|PP17,
    never PP1..PP17) to avoid code hallucination; ATT codes fixed to
    ATT25_/ATT21_; EDU all 14; PP now includes PP16 (Movimiento Amarillos Por
    Chile — present in the fielded Q3.1) and PP17 (No me identifico con un
    partido, added 2026-08-02/03 per Ray's memo).
  - Stage 1 subject_id is the account handle ({account_id}), not the display
    name; Stage 1 output now carries pipeline_stage: "1".
"""

import os
import re as _re

from config.digital_twin_config import REFERENCE_DATE_SENTENCE

base_dir = os.path.dirname(os.path.abspath(__file__))

# ─── Comuna option list (single source: Arm A) ────────────────────────────────
# Arms A, B and C must offer the identical COMU1-COMU346 code list. Rather than
# maintaining a second 346-line copy that could drift, extract the block from
# Arm A's prompt at import time.

from prompts.prompt_template_arm_a import (
    x_digital_twin_entity_geographic_user_prompt as _arm_a_geo_prompt,
)

comuna_option_list = "\n".join(
    _re.findall(r"^COMU\d+\) .+$", _arm_a_geo_prompt, _re.M)
)
assert comuna_option_list.count("\n") == 345, (
    "Expected 346 COMUNA options extracted from Arm A; got "
    f"{comuna_option_list.count(chr(10)) + 1}"
)

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

# ─── Stage 1 — Evidence Extraction ───────────────────────────────────────────

arm_b_stage1_system_prompt = f"""Usted es un asistente de extracción de evidencia. Su tarea es analizar un perfil de red social y documentar ÚNICAMENTE la evidencia observable — directa o indirecta — presente en los datos proporcionados.

{REFERENCE_DATE_SENTENCE}

REGLAS ESTRICTAS:
1. En esta etapa NO realice predicciones de encuesta. Solo documente evidencia.
2. Distinga entre evidencia directa (explícita) e indirecta (inferible de contexto).
3. Si no hay evidencia relevante para una dimensión, indique "ninguna" en el campo correspondiente y asigne confidence: "none".
4. No impute características demográficas basadas en perfiles típicos de Twitter.
5. Incluya citas textuales de tweets cuando sea pertinente y relevante.
6. El output DEBE ser un JSON válido con la estructura del esquema Stage 1. No incluya texto fuera del bloque JSON.

NIVELES DE CONFIANZA (aplica a todo campo, incluidas las listas left_signals/right_signals/center_signals/active_abstention_signals):
- high: autodeclaración explícita en palabras de la persona (ej.: "voté Rechazo y voto Kast").
- medium: 2+ señales indirectas convergentes, o 1 señal indirecta de peso (ej.: retweets y hashtags reiterados del mismo sector).
- low: una sola señal indirecta, débil o ambigua, sin corroborar.
- none: sin evidencia relevante (Regla 3); direct_evidence/indirect_evidence "ninguna", listas vacías.

supporting_quotes: cite literalmente (verbatim) el o los tweets que respaldan direct_evidence/indirect_evidence del mismo campo. No incluya tweets no vinculados; no lo deje vacío si citó contenido puntual del perfil.

LISTAS ESTRUCTURADAS (left/right/center_signals, active_abstention_signals): cada entrada es una observación puntual (cita breve, cuenta, hashtag), no una síntesis — indirect_evidence sintetiza, la lista no. Señal ambigua: no la fuerce en ninguna lista. active_abstention_signals: solo señales activas de desafección/rechazo (ej.: "no pienso votar", crítica sistemática a todos los candidatos); la ausencia de evidencia de voto es confidence: none, no una señal de abstención.

PROFILE_METADATA: "estimated_political_tweet_pct" es el porcentaje estimado (0-100) de los tweets del perfil (posts_combined) cuyo contenido se relaciona con política chilena (elecciones, candidatos, partidos, gobierno, políticas públicas) — cuente tweets propios y retweets con comentario; una estimación aproximada basada en inspección del historial es aceptable, no se requiere un conteo exacto."""

arm_b_stage1_user_prompt = """Se presenta a continuación el perfil de X (Twitter) de un usuario chileno. Extraiga la evidencia observable según el esquema JSON de Stage 1.

=== DATOS DEL PERFIL ===
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
- Siguiente: {following} Usuarios
- Número Total De Tweets: {statuses_count}
- Número De Favoritos: {favourites_count}
- Número De Contenido Multimedia: {media_count}
- Historial De Tweets (del más reciente al más antiguo):
{tweets}
=== FIN DEL PERFIL ===

Analice el perfil y devuelva ÚNICAMENTE un objeto JSON válido con la estructura del esquema Stage 1. No incluya texto introductorio ni explicación fuera del JSON.

Esquema Stage 1 (devuelva exactamente esta estructura):
{
  "subject_id": "{account_id}",
  "pipeline_stage": "1",
  "demographics": {
    "age": {
      "direct_evidence": "<cita textual explícita de edad, o 'ninguna'>",
      "indirect_evidence": "<indicios contextuales de rango etario, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "gender": {
      "direct_evidence": "<pronombres, nombre, autodescripción, o 'ninguna'>",
      "indirect_evidence": "<indicios de género por contexto, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "location": {
      "direct_evidence": "<ubicación explícita en perfil o tweets, o 'ninguna'>",
      "indirect_evidence": "<menciones de lugares, eventos locales, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "education": {
      "direct_evidence": "<mención de institución, título, nivel, o 'ninguna'>",
      "indirect_evidence": "<indicios por vocabulario, temas, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "occupation": {
      "direct_evidence": "<ocupación explícita en bio o tweets, o 'ninguna'>",
      "indirect_evidence": "<indicios de actividad laboral, sector, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "marital_status": {
      "direct_evidence": "<estado civil explícito, o 'ninguna'>",
      "indirect_evidence": "<menciones de pareja, hijos, familia, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "income": {
      "direct_evidence": "<ingreso explícito, o 'ninguna'>",
      "indirect_evidence": "<indicios socioeconómicos (barrio, consumo), o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    }
  },
  "political": {
    "ideology": {
      "direct_evidence": "<autodeclaración ideológica explícita, o 'ninguna'>",
      "indirect_evidence": "<síntesis de señales ideológicas por contexto (vocabulario, cuentas seguidas, hashtags), o 'ninguna'>",
      "left_signals": [],
      "right_signals": [],
      "center_signals": [],
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "party_affiliation": {
      "direct_evidence": "<mención explícita de partido o afiliación, o 'ninguna'>",
      "indirect_evidence": "<indicios indirectos de afinidad partidaria (cuentas seguidas, hashtags, eventos), o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "political_interest": {
      "direct_evidence": "<declaración explícita de interés en política, o 'ninguna'>",
      "indirect_evidence": "<frecuencia o tono de tweets políticos, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "vote_2021_presidential": {
      "direct_evidence": "<cita explícita, o 'ninguna'>",
      "indirect_evidence": "<indicios indirectos de voto (menciones, símbolos, retweets), o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "vote_2021_legislative": {
      "direct_evidence": "<cita explícita, o 'ninguna'>",
      "indirect_evidence": "<indicios indirectos de voto (menciones, símbolos, retweets), o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "vote_2025_intention": {
      "direct_evidence": "<declaración explícita, o 'ninguna'>",
      "indirect_evidence": "<indicios indirectos de intención de voto, o 'ninguna'>",
      "active_abstention_signals": [],
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "candidate_sentiments": {
      "kast":    {"direct_evidence": "<cita explícita sobre Kast, o 'ninguna'>", "indirect_evidence": "<indicios indirectos de sentimiento hacia Kast, o 'ninguna'>", "supporting_quotes": [], "confidence": "<high|medium|low|none>"},
      "jara":    {"direct_evidence": "<cita explícita sobre Jara, o 'ninguna'>", "indirect_evidence": "<indicios indirectos de sentimiento hacia Jara, o 'ninguna'>", "supporting_quotes": [], "confidence": "<high|medium|low|none>"},
      "matthei": {"direct_evidence": "<cita explícita sobre Matthei, o 'ninguna'>", "indirect_evidence": "<indicios indirectos de sentimiento hacia Matthei, o 'ninguna'>", "supporting_quotes": [], "confidence": "<high|medium|low|none>"},
      "parisi":  {"direct_evidence": "<cita explícita sobre Parisi, o 'ninguna'>", "indirect_evidence": "<indicios indirectos de sentimiento hacia Parisi, o 'ninguna'>", "supporting_quotes": [], "confidence": "<high|medium|low|none>"},
      "meo":     {"direct_evidence": "<cita explícita sobre MEO, o 'ninguna'>", "indirect_evidence": "<indicios indirectos de sentimiento hacia MEO, o 'ninguna'>", "supporting_quotes": [], "confidence": "<high|medium|low|none>"},
      "artes":   {"direct_evidence": "<cita explícita sobre Artés, o 'ninguna'>", "indirect_evidence": "<indicios indirectos de sentimiento hacia Artés, o 'ninguna'>", "supporting_quotes": [], "confidence": "<high|medium|low|none>"},
      "kaiser":  {"direct_evidence": "<cita explícita sobre Kaiser, o 'ninguna'>", "indirect_evidence": "<indicios indirectos de sentimiento hacia Kaiser, o 'ninguna'>", "supporting_quotes": [], "confidence": "<high|medium|low|none>"}
    }
  },
  "civic": {
    "campaign_attention_2025": {
      "direct_evidence": "<mención explícita de atención a la campaña 2025, o 'ninguna'>",
      "indirect_evidence": "<indicios indirectos de atención a la campaña 2025 (tweets sobre campaña, candidatos, eventos), o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "campaign_attention_2021": {
      "direct_evidence": "<mención explícita de atención a la campaña 2021, o 'ninguna'>",
      "indirect_evidence": "<indicios indirectos de atención a la campaña 2021, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "general_trust": {
      "direct_evidence": "<declaración explícita de confianza/desconfianza interpersonal, o 'ninguna'>",
      "indirect_evidence": "<señales indirectas de confianza/desconfianza interpersonal, o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "electoral_participation": {
      "direct_evidence": "<señales explícitas de participación pasada o intención futura, o 'ninguna'>",
      "indirect_evidence": "<indicios indirectos de participación electoral, o 'ninguna'>",
      "active_abstention_signals": [],
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    }
  },
  "issues": {
    "most_important_issue": {
      "direct_evidence": "<mención explícita de cuál es, según el usuario, el problema más importante que enfrenta el país (Chile) hoy en día, o 'ninguna'>",
      "indirect_evidence": "<indicios indirectos de qué problema del país le preocupa más (frecuencia, tono, temas recurrentes), o 'ninguna'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    }
  },
  "profile_metadata": {
    "richness": "<rich (>500 tweets)|moderate (50-500 tweets)|sparse (<50 tweets)>",
    "estimated_political_tweet_pct": "<porcentaje estimado>"
  }
}"""

# ─── Stage 2 — Survey Response Prediction ────────────────────────────────────

arm_b_stage2_system_prompt = """Usted es un predictor de respuestas de encuesta. Su tarea es predecir cómo respondería este usuario a un conjunto de preguntas de encuesta sobre política chilena, basándose ÚNICAMENTE en la hoja de evidencia extraída de su perfil (output de Stage 1).

""" + REFERENCE_DATE_SENTENCE + """

REGLAS ESTRICTAS:
1. Base sus predicciones exclusivamente en la hoja de evidencia Stage 1. No use conocimiento general sobre demografía típica de Twitter en Chile.
2. Adopte encuadre de proxy predictivo: "Dado lo que se observa en este perfil, esta persona tiene mayor probabilidad de responder..."
3. Donde la evidencia en Stage 1 sea débil o indirecta (confidence 'low'), comprométase con la respuesta más plausible y refleje la incertidumbre en el puntaje de especulación, no en CANNOT_INFER.
4. CANNOT_INFER es una respuesta válida únicamente cuando confidence sea 'none' y no exista ninguna señal relevante para la pregunta.
5. No asigne CANNOT_INFER si existe cualquier señal relevante para la pregunta, aunque sea débil o indirecta.
6. El output DEBE ser un JSON válido con la estructura del esquema Stage 2. No incluya texto fuera del JSON.
7. Cada predicción DEBE incluir los campos: question (nombre canónico de la variable), symbol (código), category (etiqueta de la categoría), explanation, speculation (0-100), evidence_basis (campo de Stage 1 que sustenta la predicción). En explanation, explique qué características de la hoja de evidencia contribuyeron a su elección y a su nivel de especulación.
8. Debe incluir una entrada en "predictions" para CADA una de las 35 claves del esquema. ¡USTED DEBE DAR UNA RESPUESTA PARA CADA PREGUNTA!

REGLA DE INFERENCIA CONSERVADORA:
Solo seleccione una categoría para edad, educación, ocupación, estado civil, ingresos u orientación política si la hoja de evidencia proporciona evidencia clara y directa.
La ausencia de evidencia debe traducirse en una puntuación de especulación más alta (>70). No asigne la categoría modal simplemente por ser la más común.
No trate la ausencia de información como evidencia de abstención ni de una ideología política específica.
En particular, evite asignar automáticamente como respuesta predeterminada: edad 25–34, ocupación "Profesional", ideología = 5, o "no votaría".

REGLA DE FORMATO CRÍTICA:
- El campo symbol debe contener ÚNICAMENTE el código (por ejemplo: PP12, AG3, Vsv2), sin paréntesis ni texto adicional.
- El campo category debe contener ÚNICAMENTE la descripción completa de la categoría, sin incluir el código.
- Nunca mezcle código y descripción en el mismo campo.
- Cuando symbol sea "CI", category debe ser exactamente "CANNOT_INFER" -- nunca repita "CI" en el campo category.

Correcto:
"symbol": "PP12", "category": "Evolución Política (EVOPOLI)"
"symbol": "CI", "category": "CANNOT_INFER"

Incorrecto:
"symbol": "PP12)", "category": "PP12) Evolución Política (EVOPOLI)"
"symbol": "CI", "category": "CI"

NIVELES DE ESPECULACIÓN:
Para cada símbolo/categoría seleccionado, indique el nivel de especulación involucrado en la selección en una escala de 0 (nada especulativo, cada elemento de la hoja de evidencia fue útil para la selección) a 100 (totalmente especulativo, no hay información relacionada con esta pregunta en la hoja de evidencia).
Para garantizar la coherencia, utilice las siguientes pautas para determinar los niveles de especulación:
0–20 (Baja especulación): La hoja de evidencia proporciona información clara y directa relevante para la pregunta (por ejemplo, evidencia directa con confidence high en Stage 1).
21–40 (Especulación moderada-baja): La hoja de evidencia proporciona indicadores indirectos pero de gran relevancia para la pregunta (por ejemplo, señales convergentes con confidence medium).
41–60 (Especulación moderada): La hoja de evidencia proporciona algunas pistas o información parcialmente relevante para la pregunta (por ejemplo, señales aisladas con confidence low).
61–80 (Especulación moderada-alta): La hoja de evidencia proporciona indicadores limitados y de relevancia débil para la pregunta (por ejemplo, confidence low sin señales concretas).
81–100 (Alta especulación): La hoja de evidencia no proporciona ninguna o casi ninguna información relevante para la pregunta (corresponde a confidence none en Stage 1).

DISTINCIÓN OBLIGATORIA ENTRE TIPOS DE PREGUNTAS:
- Preguntas '(INDV)': predicción basada ÚNICAMENTE en la evidencia del perfil (Stage 1). Los prefijos de código varían por pregunta (Tpaindv, Thpa, Tcuindv, Vpaindv, Vpa, Vcuindv, Vcu).
- Preguntas geográficas (PERSONA_REAL, PERSONA_VIVE_CHILE, REGION, COMUNA): infiera la región y la comuna a partir de la evidencia cruda en demographics.location (direct_evidence, indirect_evidence, supporting_quotes) — el mismo proceso de razonamiento que emplea para cualquier otra pregunta. Para COMUNA, seleccione el código COMU que mejor corresponda de la lista completa de comunas incluida en la pregunta COMUNA.
- Distinción NA vs CI en REGION y COMUNA: "NA" (símbolo y categoría literalmente "NA", no un código numerado de la lista) significa que la persona NO vive en Chile, según la regla de la pregunta PERSONA QUE VIVE EN CHILE. "CI" significa que la persona sí vive en Chile pero la evidencia es insuficiente para determinar la región/comuna específica (location.confidence 'none' en Stage 1). No use NA cuando corresponde CI, ni viceversa.

REGLA SOBRE INTENCIÓN DE VOTO: Las preguntas de intención de voto (incluida la segunda vuelta) piden la preferencia política de esta persona, no si es elegible para votar. Si hay evidencia de residencia fuera de Chile o alguna otra duda sobre elegibilidad, esa duda NO debe traducirse en una respuesta de abstención ("no votó" / "no votaría"); responda igualmente según la preferencia política observada (ideología, simpatía partidaria, sentimiento hacia los candidatos), como si esta persona fuera a votar. Asigne CANNOT_INFER únicamente cuando no exista ninguna señal política relevante en el perfil — nunca como sustituto de una duda sobre residencia o elegibilidad.

REGLA SOBRE CANNOT_INFER: Asigne CI únicamente cuando el perfil no contenga NINGUNA señal relevante para la pregunta. Si existe una señal débil o indirecta, comprométase con la respuesta más plausible y exprese su incertidumbre mediante el puntaje de especulación (y, en los resultados primarios, mediante la distribución de probabilidad) — no mediante CI.

DISTRIBUCIÓN DE PROBABILIDAD (solo para cuatro preguntas primarias): Para EDAD, SEXO, ORIENTACION_IDEOLOGICA, e INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA — y únicamente para estas cuatro — incluya además un campo "probability_distribution": un objeto JSON que asigna una probabilidad (0 a 1) a CADA símbolo posible de esa pregunta, incluyendo CI, sumando 1.0 en total. Ejemplo para EDAD: "probability_distribution": {{"AG1": 0.20, "AG2": 0.45, "AG3": 0.25, "AG4": 0.10, "CI": 0.00}}. No incluya este campo en ninguna otra pregunta.

CAMPOS DE RESUMEN (nivel superior, fuera de "predictions"): "cannot_infer_fields" debe listar las claves de pregunta (los mismos nombres usados en "predictions", ej. "EDAD", "PARTIDO_POLITICO") donde symbol es "CI". "high_speculation_fields" debe listar las claves de pregunta donde speculation > 70, consistente con la REGLA DE INFERENCIA CONSERVADORA. Ambas listas pueden quedar vacías ([]) si ninguna pregunta cumple el criterio."""

_arm_b_stage2_user_prompt_template = """A continuación se presenta la hoja de evidencia (Stage 1) de este perfil. Basándose en ella, prediga las respuestas de encuesta.

=== HOJA DE EVIDENCIA (STAGE 1 OUTPUT) ===
{stage_1_output_json}
=== FIN DE HOJA DE EVIDENCIA ===
{ordering_note}
Devuelva ÚNICAMENTE un objeto JSON válido con la siguiente estructura. Para cada pregunta, seleccione el símbolo más probable o "CI" (CANNOT_INFER) si la evidencia es insuficiente. Cuando symbol sea "CI", category debe ser exactamente "CANNOT_INFER" (nunca "CI").

{
  "subject_id": "<subject_id de Stage 1>",
  "pipeline_stage": "2",
  "predictions": {
    "PERSONA_REAL":                       {"question": "PERSONA_REAL",                       "symbol": "<RP1|RP2|CI>",                                          "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "profile_metadata"},
    "PERSONA_VIVE_CHILE":                 {"question": "PERSONA_VIVE_CHILE",                 "symbol": "<PLC1|PLC2|CI>",                                        "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "demographics.location"},
    "REGION":                             {"question": "REGION",                             "symbol": "<REG1|REG2|REG3|REG4|REG5|REG6|REG7|REG8|REG9|REG10|REG11|REG12|REG13|REG14|REG15|REG16|NA|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "demographics.location"},
    "COMUNA":                             {"question": "COMUNA",                             "symbol": "<código COMU de la lista de la pregunta COMUNA|NA|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "demographics.location"},
    "EDAD":                               {"question": "EDAD",                               "symbol": "<AG1|AG2|AG3|AG4|CI>",                                  "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "probability_distribution": {"AG1": <0-1>, "AG2": <0-1>, "AG3": <0-1>, "AG4": <0-1>, "CI": <0-1>}},
    "SEXO":                               {"question": "SEXO",                               "symbol": "<S1|S2|CI>",                                            "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "probability_distribution": {"S1": <0-1>, "S2": <0-1>, "CI": <0-1>}},
    "RANGO_INGRESOS_PERSONALES":          {"question": "RANGO_INGRESOS_PERSONALES",          "symbol": "<PINC1|PINC2|PINC3|PINC4|PINC5|PINC6|PINC7|PINC8|PINC9|PINC10|PINC11|PINC12|PINC13|PINC14|PINC15|PINC16|PINC17|PINC18|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "RANGO_INGRESOS_HOGAR":               {"question": "RANGO_INGRESOS_HOGAR",               "symbol": "<HINC1|HINC2|HINC3|HINC4|HINC5|HINC6|HINC7|HINC8|HINC9|HINC10|HINC11|HINC12|HINC13|HINC14|HINC15|HINC16|HINC17|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "ESTADO_CIVIL":                       {"question": "ESTADO_CIVIL",                       "symbol": "<MAR1|MAR2|MAR3|MAR4|MAR5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "CALIFICACION_EDUCATIVA":             {"question": "CALIFICACION_EDUCATIVA",             "symbol": "<EDU1|EDU2|EDU3|EDU4|EDU5|EDU6|EDU7|EDU8|EDU9|EDU10|EDU11|EDU12|EDU13|EDU14|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "OCUPACION_ACTUAL":                   {"question": "OCUPACION_ACTUAL",                   "symbol": "<OCCUP1|OCCUP2|OCCUP3|OCCUP4|OCCUP5|OCCUP6|OCCUP7|OCCUP8|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "ORIENTACION_IDEOLOGICA":             {"question": "ORIENTACION_IDEOLOGICA",             "symbol": "<IoPoR1|IoPoR2|IoPoR3|IoPoR4|IoPoR5|IoPoR6|IoPoR7|IoPoR8|IoPoR9|IoPoR10|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "probability_distribution": {"IoPoR1": <0-1>, "IoPoR2": <0-1>, "IoPoR3": <0-1>, "IoPoR4": <0-1>, "IoPoR5": <0-1>, "IoPoR6": <0-1>, "IoPoR7": <0-1>, "IoPoR8": <0-1>, "IoPoR9": <0-1>, "IoPoR10": <0-1>, "CI": <0-1>}},
    "PARTIDO_POLITICO":                   {"question": "PARTIDO_POLITICO",                   "symbol": "<PP1|PP2|PP3|PP4|PP5|PP6|PP7|PP8|PP9|PP10|PP11|PP12|PP13|PP14|PP15|PP16|PP17|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "AFINIDAD_PARTIDO":                   {"question": "AFINIDAD_PARTIDO",                   "symbol": "<Afi1|Afi2|Afi3|Afi4|Afi5|Afi6|Afi7|CI>",              "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INTERES_POLITICA":                   {"question": "INTERES_POLITICA",                   "symbol": "<INTP1|INTP2|INTP3|INTP4|CI>",                          "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "ATENCION_CAMPANA_2025":              {"question": "ATENCION_CAMPANA_2025",              "symbol": "<ATT25_1|ATT25_2|ATT25_3|ATT25_4|CI>",                  "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "ATENCION_CAMPANA_2021":              {"question": "ATENCION_CAMPANA_2021",              "symbol": "<ATT21_1|ATT21_2|ATT21_3|ATT21_4|CI>",                  "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "CONFIANZA_GENERAL":                  {"question": "CONFIANZA_GENERAL",                  "symbol": "<TRUS1|TRUS2|TRUS3|TRUS4|TRUS5|CI>",                    "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "PARTICIPACION_PRESIDENCIAL_2021":    {"question": "PARTICIPACION_PRESIDENCIAL_2021",    "symbol": "<Thpa1|Thpa2|Thpa3|CI>",                                "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "VOTO_PRESIDENCIAL_2021":             {"question": "VOTO_PRESIDENCIAL_2021",             "symbol": "<Vpa1|Vpa2|Vpa3|Vpa4|Vpa5|Vpa6|Vpa7|Vpa8|CI>",         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "VOTO_BALLOTAGE_2021":                {"question": "VOTO_BALLOTAGE_2021",                "symbol": "<Vba1|Vba2|Vba3|Vba4|CI>",                              "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_PARTICIPACION_LEGISLATIVA_2021":{"question": "INDV_PARTICIPACION_LEGISLATIVA_2021","symbol": "<Tpaindv1|Tpaindv2|Tpaindv3|Tpaindv4|Tpaindv5|Tpaindv6|Tpaindv7|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_VOTO_LEGISLATIVO_2021":         {"question": "INDV_VOTO_LEGISLATIVO_2021",         "symbol": "<Vpaindv1|Vpaindv2|Vpaindv3|Vpaindv4|Vpaindv5|Vpaindv6|Vpaindv7|Vpaindv8|Vpaindv9|Vpaindv10|Vpaindv11|Vpaindv12|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_PARTICIPACION_2025":            {"question": "INDV_PARTICIPACION_2025",            "symbol": "<Tcuindv1|Tcuindv2|Tcuindv3|CI>",                       "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_INTENCION_VOTO_2025":           {"question": "INDV_INTENCION_VOTO_2025",           "symbol": "<Vcuindv1|Vcuindv2|Vcuindv3|Vcuindv4|Vcuindv5|Vcuindv6|Vcuindv7|Vcuindv8|Vcuindv9|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA": {"question": "INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA", "symbol": "<Vsv1|Vsv2|Vsv3|Vsv4|Vsv5|CI>",                          "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "probability_distribution": {"Vsv1": <0-1>, "Vsv2": <0-1>, "Vsv3": <0-1>, "Vsv4": <0-1>, "Vsv5": <0-1>, "CI": <0-1>}},
    "INDECISION_2025":                    {"question": "INDECISION_2025",                    "symbol": "<Und1|Und2|Und3|Und4|Und5|Und6|Und7|CI>",               "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_KAST":                 {"question": "FAVORABILIDAD_KAST",                 "symbol": "<Kfa1|Kfa2|Kfa3|Kfa4|Kfa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_JARA":                 {"question": "FAVORABILIDAD_JARA",                 "symbol": "<Jfa1|Jfa2|Jfa3|Jfa4|Jfa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_MATTHEI":              {"question": "FAVORABILIDAD_MATTHEI",              "symbol": "<Efa1|Efa2|Efa3|Efa4|Efa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_PARISI":               {"question": "FAVORABILIDAD_PARISI",               "symbol": "<Pfa1|Pfa2|Pfa3|Pfa4|Pfa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_MEO":                  {"question": "FAVORABILIDAD_MEO",                  "symbol": "<Mfa1|Mfa2|Mfa3|Mfa4|Mfa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_ARTES":                {"question": "FAVORABILIDAD_ARTES",                "symbol": "<Afa1|Afa2|Afa3|Afa4|Afa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_KAISER":               {"question": "FAVORABILIDAD_KAISER",               "symbol": "<JKfa1|JKfa2|JKfa3|JKfa4|JKfa5|CI>",                    "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "TEMA_MAS_IMPORTANTE":                {"question": "TEMA_MAS_IMPORTANTE",                "symbol": "<Moi01|Moi02|Moi03|Moi04|Moi05|Moi06|Moi07|Moi08|Moi09|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"}
  },
  "cannot_infer_fields": [],
  "high_speculation_fields": []
}

¡USTED DEBE DAR UNA RESPUESTA PARA CADA TÍTULO!
A continuación, se presenta la lista de categorías a las que este usuario puede pertenecer:

{question_blocks}"""

# ─── Stage 2 question blocks — extracted from Arm A (single source) ──────────
# Alignment pass 2026-07-27 (QA report 06, "A governs where the documentation
# is silent"): every question title, survey sentence, and option label is
# EXTRACTED from Arm A's prompts at import time, so B cannot drift from the
# fielded instrument. The only content differences from A are the documented
# ones, applied as explicit, visible patches below:
#   - a CI escape line per question (guide §4);
#   - IoPoR endpoint verbal anchors (guide §8 "map numeric codes to verbal
#     labels");
#   - the RP2 gloss (QA-established PERSONA_REAL ambiguity);
#   - AFINIDAD's instrument-style 1-7 list (fielded Q3.2 shows anchors +
#     numeric row; A itself lists no options for this question).

from prompts.prompt_template_arm_a import (
    x_digital_twin_voting_preference_wo_voting_results_user_prompt as _arm_a_voting_prompt,
)

# (opt_key, json_key, A-verbatim title, source) — order: Arm A's own asking
# order (geographic call first, then the voting call's sequence).
_STAGE2_QUESTIONS = [
    ("PERSONA_REAL", "PERSONA_REAL", "PERSONA REAL", "geo"),
    ("PERSONA_VIVE_CHILE", "PERSONA_VIVE_CHILE", "PERSONA QUE VIVE EN CHILE", "geo"),
    ("REGION", "REGION", "REGIÓN", "geo"),
    ("COMUNA", "COMUNA", "COMUNA", "geo"),
    ("EDAD", "EDAD", "EDAD", "vote"),
    ("SEXO", "SEXO", "SEXO", "vote"),
    ("PINC", "RANGO_INGRESOS_PERSONALES", "RANGO DE INGRESOS PERSONALES", "vote"),
    ("HINC", "RANGO_INGRESOS_HOGAR", "RANGO DE INGRESOS DEL HOGAR", "vote"),
    ("ESTADO_CIVIL", "ESTADO_CIVIL", "ESTADO CIVIL", "vote"),
    ("EDUCACION", "CALIFICACION_EDUCATIVA", "CALIFICACIÓN EDUCATIVA MÁS ALTA", "vote"),
    ("OCUPACION", "OCUPACION_ACTUAL", "OCUPACIÓN ACTUAL", "vote"),
    ("IDEOLOGIA", "ORIENTACION_IDEOLOGICA", "ORIENTACIÓN IDEOLÓGICA O POLÍTICA", "vote"),
    ("PARTIDO", "PARTIDO_POLITICO", "PARTIDO POLÍTICO", "vote"),
    ("AFINIDAD", "AFINIDAD_PARTIDO", "AFINIDAD CON PARTIDO POLÍTICO", "vote"),
    ("INTERES", "INTERES_POLITICA", "INTERÉS EN LA POLÍTICA", "vote"),
    ("ATT2025", "ATENCION_CAMPANA_2025", "ATENCIÓN CAMPAÑA 2025", "vote"),
    ("ATT2021", "ATENCION_CAMPANA_2021", "ATENCIÓN CAMPAÑA 2021", "vote"),
    ("CONFIANZA", "CONFIANZA_GENERAL", "CONFIANZA GENERAL EN OTRAS PERSONAS", "vote"),
    ("TPAINDV_LEG", "INDV_PARTICIPACION_LEGISLATIVA_2021",
     "(INDV) VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021", "vote"),
    ("VPAINDV_LEG", "INDV_VOTO_LEGISLATIVO_2021",
     "(INDV) VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021", "vote"),
    ("THPA", "PARTICIPACION_PRESIDENCIAL_2021",
     "VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021", "vote"),
    ("VPA", "VOTO_PRESIDENCIAL_2021",
     "VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021", "vote"),
    ("VBA", "VOTO_BALLOTAGE_2021",
     "VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LA SEGUNDA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021", "vote"),
    ("TCUINDV", "INDV_PARTICIPACION_2025",
     "(INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025", "vote"),
    ("VCUINDV", "INDV_INTENCION_VOTO_2025",
     "(INDV) VOTACIÓN ACTUAL – OPCIÓN DE VOTO EN LA PRIMERA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025", "vote"),
    ("VSV", "INDV_INTENCION_VOTO_2025_SEGUNDA_VUELTA",
     "(INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LA SEGUNDA VUELTA DE LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025", "vote"),
    ("INDECISION", "INDECISION_2025",
     "INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025", "vote"),
    ("FAV_KAST", "FAVORABILIDAD_KAST",
     "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOSÉ ANTONIO KAST", "vote"),
    ("FAV_JARA", "FAVORABILIDAD_JARA",
     "FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA JEANNETTE JARA", "vote"),
    ("FAV_MATTHEI", "FAVORABILIDAD_MATTHEI",
     "FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA EVELYN MATTHEI", "vote"),
    ("FAV_PARISI", "FAVORABILIDAD_PARISI",
     "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO FRANCO PARISI", "vote"),
    ("FAV_MEO", "FAVORABILIDAD_MEO",
     "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO MARCO ENRÍQUEZ-OMINAMI", "vote"),
    ("FAV_ARTES", "FAVORABILIDAD_ARTES",
     "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO EDUARDO ARTÉS", "vote"),
    ("FAV_KAISER", "FAVORABILIDAD_KAISER",
     "FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOHANNES KAISER", "vote"),
    ("MAS_IMPORTANTE", "TEMA_MAS_IMPORTANTE",
     "CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE", "vote"),
]
assert len(_STAGE2_QUESTIONS) == 35

# Arm A's verbatim question titles, split by which of Arm A's two calls asks
# them. Passed to extract_llm_responses(canonical_labels=...) so a title the
# model echoes back with different casing lands on the canonical column --
# the same treatment Arm D already gets via ARM_D_QUESTION_LABELS. Kept
# arm-specific on purpose: the baseline arm asks "OCUPACIÓN ACUTAL" (sic) and
# must keep doing so, or the two arms stop being comparable.
ARM_A_GEO_QUESTION_LABELS = [q[2] for q in _STAGE2_QUESTIONS if q[3] == "geo"]
ARM_A_VOTE_QUESTION_LABELS = [q[2] for q in _STAGE2_QUESTIONS if q[3] == "vote"]
assert len(ARM_A_GEO_QUESTION_LABELS) == 4
assert len(ARM_A_VOTE_QUESTION_LABELS) == 31

# Canonical Stage 2 JSON keys (Arms B/C), for key-format validation in
# src/utils.py::extract_json_predictions. Note these are the json_key values,
# NOT the opt_key values CANONICAL_OPTIONS is keyed by.
STAGE2_JSON_KEYS = tuple(q[1] for q in _STAGE2_QUESTIONS)
assert len(set(STAGE2_JSON_KEYS)) == 35

# CI escape line per question (guide §4). 2026-07-30: standardized to a
# single uniform line for every question -- symbol exactly "CI)", category
# exactly "CANNOT_INFER", no per-field reason suffix (see CHANGELOG.md).
# Previously each question carried a bespoke Spanish reason phrase; that
# variation was cosmetic, not semantic, and is dropped here.
_CI_LINE = "CI) CANNOT_INFER"
_CI_LINES = {
    key: _CI_LINE
    for key in [
        "PERSONA_REAL", "PERSONA_VIVE_CHILE", "REGION", "COMUNA", "EDAD",
        "SEXO", "PINC", "HINC", "ESTADO_CIVIL", "EDUCACION", "OCUPACION",
        "IDEOLOGIA", "PARTIDO", "AFINIDAD", "INTERES", "ATT2025", "ATT2021",
        "CONFIANZA", "THPA", "VPA", "VBA", "TPAINDV_LEG", "VPAINDV_LEG", "TCUINDV",
        "VCUINDV", "VSV", "INDECISION", "FAV_KAST", "FAV_JARA", "FAV_MATTHEI",
        "FAV_PARISI", "FAV_MEO", "FAV_ARTES", "FAV_KAISER", "MAS_IMPORTANTE",
    ]
}

# Documented label deviations from A, applied as visible patches.
# IDEOLOGIA's IoPoR1/IoPoR10 verbal anchors previously needed patching in here,
# but the 2026-07-27 Arm A edit added "Izquierda"/"Derecha" directly to those
# option lines, so (like AFINIDAD below) no override is needed anymore -- the
# old patch's exact-string lookup would now raise ValueError.
_OPTION_PATCHES = {
    "PERSONA_REAL": {"RP2) Otro": "RP2) Otro (bot, organización, cuenta ficticia)"},
}

# AFINIDAD's Afi1-Afi7 option list (endpoint anchors, bare numeric interior,
# matching fielded Q3.2's format) now lives in Arm A itself, alongside every
# other question's options -- no override needed here. Symbol prefix "Afi"
# added 2026-07-27: a bare "1"-"7" was the only symbol in the codebook with no
# letter prefix. See report 06 appendix for the corresponding QA code_specs
# regex change (^[1-7]$ -> ^Afi[1-7]$), needed on Lucas's side.
#
# No trailing space required after the closing paren: AFINIDAD's interior
# points (Afi2)...Afi6)) are bare codes with no label text, unlike every
# other option in the codebook.
_OPT_LINE_RE = _re.compile(r"^[A-Za-z][A-Za-z0-9]*_?\d+\)")


def _extract_arm_a_block(source: str, title: str) -> "list[str]":
    """
    Return the lines of Arm A's block for `title`, title prefix stripped.
    Handles both of A's layouts: title alone on its line (voting prompt) and
    title + sentence on one line (geographic prompt, e.g.
    "PERSONA REAL: ¿Esta cuenta corresponde a ...?").
    """
    anchor = "\n" + title + ":"
    start = source.index(anchor) + 1  # start of the title line
    end = source.find("\n\n", start)
    if end == -1:
        end = len(source)
    lines = source[start:end].splitlines()
    first_remainder = lines[0][len(title) + 1:].strip()
    rest = lines[1:]
    return ([first_remainder] if first_remainder else []) + rest


# NA (REGION/COMUNA only, "does not live in Chile" per PERSONA_VIVE_CHILE)
# is deliberately NOT a listed option bullet -- it is a literal symbol/
# category value the model writes directly, per the instruction sentence
# alone (Arm A's REGIÓN/COMUNA title lines, inherited into _sentences below).
# Listing "NA)" as a bullet would make it look like a selectable numbered
# code again, the exact problem this change is fixing. See CHANGELOG.md,
# "REGION/COMUNA -- drop REG17...".

CANONICAL_OPTIONS: "dict[str, list[str]]" = {}
_question_blocks: "list[str]" = []

for _opt_key, _json_key, _title, _src in _STAGE2_QUESTIONS:
    _source = _arm_a_geo_prompt if _src == "geo" else _arm_a_voting_prompt
    _lines = _extract_arm_a_block(_source, _title)
    _sentences = []
    for _l in _lines:
        if _OPT_LINE_RE.match(_l):
            break
        _sentences.append(_l)
    _options = [_l for _l in _lines if _OPT_LINE_RE.match(_l)]

    for _old, _new in _OPTION_PATCHES.get(_opt_key, {}).items():
        _i = _options.index(_old)
        _options[_i] = _new
    _options = _options + [_CI_LINES[_opt_key]]

    if _opt_key == "COMUNA":
        # Options are the full comuna list (already extracted above) + CI.
        assert "\n".join(_options[:-1]) == comuna_option_list
    else:
        CANONICAL_OPTIONS[_opt_key] = _options

    _block = _title + ' [→ "' + _json_key + '"]:'
    if _sentences:
        _block += "\n" + "\n".join(_sentences)
    _block += "\n{options_" + _opt_key + "}"
    _question_blocks.append(_block)

assert len(CANONICAL_OPTIONS) == 34
_QUESTION_BLOCKS_TEXT = "\n\n".join(_question_blocks)


def fill_stage2_user_prompt(options_by_key: "dict[str, str]", ordering_note: str = "") -> str:
    """
    Fill the shared Stage 2 user-prompt template. `options_by_key` maps each
    opt_key (incl. COMUNA) to its rendered option block. Uses literal
    replacement, never str.format, so JSON braces in the template are safe.
    Leaves {stage_1_output_json} for the caller (driver replaces it for Arm B;
    Arm C's builder replaces it directly).
    """
    out = _arm_b_stage2_user_prompt_template.replace(
        "{question_blocks}", _QUESTION_BLOCKS_TEXT
    ).replace("{ordering_note}", ordering_note)
    for _key, _block in options_by_key.items():
        out = out.replace("{options_" + _key + "}", _block)
    assert "{options_" not in out, "unfilled option placeholder"
    return out


# COMUNA's rendered option block (full Arm A list + CI escape) — static in
# every arm; exported for Arm C's builder.
comuna_options_block = comuna_option_list + "\n" + _CI_LINES["COMUNA"]

_canonical_fill = {k: "\n".join(v) for k, v in CANONICAL_OPTIONS.items()}
_canonical_fill["COMUNA"] = comuna_options_block

arm_b_stage2_user_prompt = fill_stage2_user_prompt(_canonical_fill, ordering_note="")


# ─── Municipal electoral data — INPUT instruction, information condition 4 ────
# Guide section 9.4: municipal data informs INDIVIDUAL predictions; it is not a
# separate block of output questions. The driver must append this to the
# Stage 2 system prompt ONLY when enable_web_search is True (condition 4).
# Wiring is a documented src follow-up (QA report 06); nothing references this
# string yet.

arm_b_municipal_web_instruction = """
USO DE DATOS ELECTORALES COMUNALES (solo con búsqueda web habilitada):
Si la evidencia cruda de ubicación en Stage 1 (demographics.location, con confidence 'medium' o superior) permite inferir una comuna específica, recupere mediante búsqueda web los resultados electorales de esa comuna (elecciones 2021: participación y votación presidencial/legislativa; apoyo por candidato a nivel comunal) y úselos como CONTEXTO ADICIONAL para informar las predicciones individuales — en particular las de participación y voto. Reglas:
- Los datos comunales complementan, nunca reemplazan, la evidencia individual del perfil.
- Cite en explanation cuándo un resultado comunal influyó en la predicción.
- No busque información que identifique a la persona (regla de no desanonimización).
- Mantenga consistencia temporal: para la elección de 2025 no trate resultados de 2021 como actuales."""
