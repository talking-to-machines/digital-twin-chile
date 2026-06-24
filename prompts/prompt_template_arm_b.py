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
  Municipality for communal questions: extract from
      stage1_json["demographics"]["location"]["inferred_municipality"].
"""

import os

base_dir = os.path.dirname(os.path.abspath(__file__))

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

arm_b_stage1_system_prompt = """Usted es un asistente de extracción de evidencia. Su tarea es analizar un perfil de red social y documentar ÚNICAMENTE la evidencia observable — directa o indirecta — presente en los datos proporcionados.

REGLAS ESTRICTAS:
1. En esta etapa NO realice predicciones de encuesta. Solo documente evidencia.
2. Distinga entre evidencia directa (explícita) e indirecta (inferible de contexto).
3. Si no hay evidencia relevante para una dimensión, indique "ninguna" en el campo correspondiente y asigne confidence: "none".
4. No impute características demográficas basadas en perfiles típicos de Twitter.
5. Incluya citas textuales de tweets cuando sea pertinente y relevante.
6. El output DEBE ser un JSON válido con la estructura del esquema Stage 1. No incluya texto fuera del bloque JSON."""

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
  "subject_id": "<valor de {name}>",
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
      "inferred_region": "<región chilena inferida, o 'CANNOT_INFER'>",
      "inferred_municipality": "<comuna inferida, o 'CANNOT_INFER'>",
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
      "left_signals": [],
      "right_signals": [],
      "center_signals": [],
      "explicit_self_placement": "<autodeclaración explícita, o 'ninguna'>",
      "net_direction": "<izquierda|centro-izquierda|centro|centro-derecha|derecha|CANNOT_INFER>",
      "confidence": "<high|medium|low|none>"
    },
    "party_affiliation": {
      "explicit_mentions": [],
      "inferred_affinity": "<partido más consistente, o 'CANNOT_INFER'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "political_interest": {
      "evidence": "<descripción de tweets políticos o 'ninguna'>",
      "estimated_level": "<muy alto|alto|moderado|bajo|ninguno|CANNOT_INFER>",
      "confidence": "<high|medium|low|none>"
    },
    "vote_2021_presidential": {
      "explicit_mention": "<cita explícita, o 'ninguna'>",
      "inferred_signal": "<candidato más consistente, o 'CANNOT_INFER'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "vote_2021_legislative": {
      "explicit_mention": "<cita explícita, o 'ninguna'>",
      "inferred_signal": "<partido/lista más consistente, o 'CANNOT_INFER'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "vote_2025_intention": {
      "explicit_mention": "<declaración explícita, o 'ninguna'>",
      "inferred_signal": "<candidato más consistente, o 'CANNOT_INFER'>",
      "active_abstention_signals": [],
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    },
    "candidate_sentiments": {
      "kast":    {"valence": "<muy favorable|favorable|desfavorable|muy desfavorable|neutral|CANNOT_INFER>", "supporting_quotes": []},
      "jara":    {"valence": "<muy favorable|favorable|desfavorable|muy desfavorable|neutral|CANNOT_INFER>", "supporting_quotes": []},
      "matthei": {"valence": "<muy favorable|favorable|desfavorable|muy desfavorable|neutral|CANNOT_INFER>", "supporting_quotes": []},
      "parisi":  {"valence": "<muy favorable|favorable|desfavorable|muy desfavorable|neutral|CANNOT_INFER>", "supporting_quotes": []},
      "meo":     {"valence": "<muy favorable|favorable|desfavorable|muy desfavorable|neutral|CANNOT_INFER>", "supporting_quotes": []},
      "artes":   {"valence": "<muy favorable|favorable|desfavorable|muy desfavorable|neutral|CANNOT_INFER>", "supporting_quotes": []},
      "kaiser":  {"valence": "<muy favorable|favorable|desfavorable|muy desfavorable|neutral|CANNOT_INFER>", "supporting_quotes": []}
    }
  },
  "civic": {
    "campaign_attention_2025": {
      "evidence": "<tweets sobre campaña 2025, o 'ninguna'>",
      "estimated_level": "<mucho|algo|poco|nada|CANNOT_INFER>",
      "confidence": "<high|medium|low|none>"
    },
    "campaign_attention_2021": {
      "evidence": "<tweets sobre campaña 2021, o 'ninguna'>",
      "estimated_level": "<mucho|algo|poco|nada|CANNOT_INFER>",
      "confidence": "<high|medium|low|none>"
    },
    "general_trust": {
      "evidence": "<señales de confianza/desconfianza interpersonal, o 'ninguna'>",
      "estimated_level": "<siempre confía|mayoría del tiempo|aprox. mitad|algunas veces|nunca|CANNOT_INFER>",
      "confidence": "<high|medium|low|none>"
    },
    "electoral_participation": {
      "evidence": "<señales de participación pasada o intención futura, o 'ninguna'>",
      "active_abstention_signals": [],
      "confidence": "<high|medium|low|none>"
    }
  },
  "issues": {
    "most_important_issue": {
      "explicit_mentions": [],
      "inferred_concern": "<tema más prominente, o 'CANNOT_INFER'>",
      "supporting_quotes": [],
      "confidence": "<high|medium|low|none>"
    }
  },
  "profile_metadata": {
    "richness": "<rich (>500 tweets)|moderate (50-500 tweets)|sparse (<50 tweets)>",
    "estimated_political_tweet_pct": "<porcentaje estimado>",
    "overall_inference_quality": "<alta|moderada|baja|muy baja>"
  }
}"""

# ─── Stage 2 — Survey Response Prediction ────────────────────────────────────

arm_b_stage2_system_prompt = """Usted es un predictor de respuestas de encuesta. Su tarea es predecir cómo respondería este usuario a un conjunto de preguntas de encuesta sobre política chilena, basándose ÚNICAMENTE en la hoja de evidencia extraída de su perfil (output de Stage 1).

REGLAS ESTRICTAS:
1. Base sus predicciones exclusivamente en la hoja de evidencia Stage 1. No use conocimiento general sobre demografía típica de Twitter en Chile.
2. Adopte encuadre de proxy predictivo: "Dado lo que se observa en este perfil, esta persona tiene mayor probabilidad de responder..."
3. Donde la evidencia en Stage 1 sea insuficiente (confidence 'none' o 'low' sin señales concretas), seleccione CANNOT_INFER (símbolo: "CI") en lugar de la categoría modal.
4. CANNOT_INFER es una respuesta válida. Úsela cuando no haya evidencia de nivel medium o superior.
5. No asigne CANNOT_INFER si hay evidencia de nivel medium o superior.
6. El output DEBE ser un JSON válido con la estructura del esquema Stage 2. No incluya texto fuera del JSON.
8. Cada predicción DEBE incluir los campos: question (nombre canónico de la variable), symbol (código), category (etiqueta de la categoría), explanation (justificación breve basada en Stage 1, máx. 2 frases), speculation (0-100), evidence_basis (campo de Stage 1 que sustenta la predicción).
7. Niveles de especulación (basados en Stage 1):
   0-20:  confidence high + direct_evidence no vacío.
   21-40: confidence medium, señales convergentes.
   41-60: confidence low, señales aisladas.
   61-80: confidence low, sin señales concretas.
   81-100: confidence none.

DISTINCIÓN OBLIGATORIA ENTRE TIPOS DE PREGUNTAS:
- Preguntas '(INDV)': predicción basada ÚNICAMENTE en la evidencia del perfil (Stage 1). Especulación típicamente 60-90. Los prefijos de código varían por pregunta (Tpaindv, Thpa, Tcuindv, Vpaindv, Vpa, Vcuindv, Vcu).
- Preguntas geográficas (PERSONA_REAL, PERSONA_VIVE_CHILE, REGION, COMUNA): derivar de demographics.location en Stage 1. Si location.confidence es 'none', usar CI.
- Preguntas comunales (sufijo _COMUNAL): combinar resultados electorales de la comuna (location.inferred_municipality de Stage 1) con el perfil. Si Stage 1 reporta CANNOT_INFER para localización, usar CI para todas las preguntas comunales."""

arm_b_stage2_user_prompt = """A continuación se presenta la hoja de evidencia (Stage 1) de este perfil. Basándose en ella, prediga las respuestas de encuesta.

=== HOJA DE EVIDENCIA (STAGE 1 OUTPUT) ===
{stage_1_output_json}
=== FIN DE HOJA DE EVIDENCIA ===

Devuelva ÚNICAMENTE un objeto JSON válido con la siguiente estructura. Para cada pregunta, seleccione el símbolo más probable o "CI" (CANNOT_INFER) si la evidencia es insuficiente.

{
  "subject_id": "<subject_id de Stage 1>",
  "pipeline_stage": "2",
  "predictions": {
    "PERSONA_REAL":                       {"question": "PERSONA_REAL",                       "symbol": "<RP1|RP2|CI>",                                          "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "profile_metadata"},
    "PERSONA_VIVE_CHILE":                 {"question": "PERSONA_VIVE_CHILE",                 "symbol": "<PLC1|PLC2|CI>",                                        "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "demographics.location"},
    "REGION":                             {"question": "REGION",                             "symbol": "<REG1..REG17|CI>",                                      "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "demographics.location.inferred_region"},
    "COMUNA":                             {"question": "COMUNA",                             "symbol": "<COMU1..COMU346|CI>",                                   "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "demographics.location.inferred_municipality"},
    "EDAD":                               {"question": "EDAD",                               "symbol": "<AG1|AG2|AG3|AG4|AG5|AG6|AG7|CI>",                      "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "SEXO":                               {"question": "SEXO",                               "symbol": "<S1|S2|CI>",                                            "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "RANGO_INGRESOS_PERSONALES":          {"question": "RANGO_INGRESOS_PERSONALES",          "symbol": "<PINC1..PINC17|CI>",                                    "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "RANGO_INGRESOS_HOGAR":               {"question": "RANGO_INGRESOS_HOGAR",               "symbol": "<HINC1..HINC17|CI>",                                    "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "ESTADO_CIVIL":                       {"question": "ESTADO_CIVIL",                       "symbol": "<MAR1|MAR2|MAR3|MAR4|MAR5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "CALIFICACION_EDUCATIVA":             {"question": "CALIFICACION_EDUCATIVA",             "symbol": "<EDU1..EDU14|CI>",                                      "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "OCUPACION_ACTUAL":                   {"question": "OCUPACION_ACTUAL",                   "symbol": "<OCCUP1..OCCUP8|CI>",                                   "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "ORIENTACION_IDEOLOGICA":             {"question": "ORIENTACION_IDEOLOGICA",             "symbol": "<IoPoR1..IoPoR10|CI>",                                  "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "PARTIDO_POLITICO":                   {"question": "PARTIDO_POLITICO",                   "symbol": "<PP1..PP15|CI>",                                        "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "AFINIDAD_PARTIDO":                   {"question": "AFINIDAD_PARTIDO",                   "symbol": "<1|2|3|4|5|6|7|CI>",                                   "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INTERES_POLITICA":                   {"question": "INTERES_POLITICA",                   "symbol": "<INTP1|INTP2|INTP3|INTP4|CI>",                          "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "ATENCION_CAMPANA_2025":              {"question": "ATENCION_CAMPANA_2025",              "symbol": "<ATT25_1|ATT25_2|ATT25_3|ATT25_4|CI>",                  "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "ATENCION_CAMPANA_2021":              {"question": "ATENCION_CAMPANA_2021",              "symbol": "<ATT21_1|ATT21_2|ATT21_3|ATT21_4|CI>",                  "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "CONFIANZA_GENERAL":                  {"question": "CONFIANZA_GENERAL",                  "symbol": "<TRUS1|TRUS2|TRUS3|TRUS4|TRUS5|CI>",                    "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "PARTICIPACION_PRESIDENCIAL_2021":    {"question": "PARTICIPACION_PRESIDENCIAL_2021",    "symbol": "<Thpa1|Thpa2|Thpa3|Thpa4|Thpa5|Thpa6|Thpa7|CI>",       "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "VOTO_PRESIDENCIAL_2021":             {"question": "VOTO_PRESIDENCIAL_2021",             "symbol": "<Vpa1|Vpa2|Vpa3|Vpa4|Vpa5|Vpa6|Vpa7|Vpa8|CI>",         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_PARTICIPACION_LEGISLATIVA_2021":{"question": "INDV_PARTICIPACION_LEGISLATIVA_2021","symbol": "<Tpaindv1..Tpaindv7|CI>",                               "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_VOTO_LEGISLATIVO_2021":         {"question": "INDV_VOTO_LEGISLATIVO_2021",         "symbol": "<Vpaindv1..Vpaindv12|CI>",                              "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_PARTICIPACION_2025":            {"question": "INDV_PARTICIPACION_2025",            "symbol": "<Tcuindv1..Tcuindv7|CI>",                               "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDV_INTENCION_VOTO_2025":           {"question": "INDV_INTENCION_VOTO_2025",           "symbol": "<Vcuindv1..Vcuindv8|CI>",                               "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INTENCION_VOTO_2025_FECHA_TWEET":    {"question": "INTENCION_VOTO_2025_FECHA_TWEET",    "symbol": "<Vcu1|Vcu2|Vcu3|Vcu4|Vcu5|Vcu6|Vcu7|Vcu8|CI>",         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "INDECISION_2025":                    {"question": "INDECISION_2025",                    "symbol": "<Und1..Und7|CI>",                                       "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_KAST":                 {"question": "FAVORABILIDAD_KAST",                 "symbol": "<Kfa1|Kfa2|Kfa3|Kfa4|Kfa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_JARA":                 {"question": "FAVORABILIDAD_JARA",                 "symbol": "<Jfa1|Jfa2|Jfa3|Jfa4|Jfa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_MATTHEI":              {"question": "FAVORABILIDAD_MATTHEI",              "symbol": "<Efa1|Efa2|Efa3|Efa4|Efa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_PARISI":               {"question": "FAVORABILIDAD_PARISI",               "symbol": "<Pfa1|Pfa2|Pfa3|Pfa4|Pfa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_MEO":                  {"question": "FAVORABILIDAD_MEO",                  "symbol": "<Mfa1|Mfa2|Mfa3|Mfa4|Mfa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_ARTES":                {"question": "FAVORABILIDAD_ARTES",                "symbol": "<Afa1|Afa2|Afa3|Afa4|Afa5|CI>",                         "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "FAVORABILIDAD_KAISER":               {"question": "FAVORABILIDAD_KAISER",               "symbol": "<JKfa1|JKfa2|JKfa3|JKfa4|JKfa5|CI>",                    "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "TEMA_MAS_IMPORTANTE":                {"question": "TEMA_MAS_IMPORTANTE",                "symbol": "<Moi01..Moi09|CI>",                                     "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>"},
    "PARTICIPACION_PRESIDENCIAL_2021_COMUNAL": {"question": "PARTICIPACION_PRESIDENCIAL_2021_COMUNAL", "symbol": "<Tpa1..Tpa7|CI>",    "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "municipality_used": "<comuna o N/A>", "municipal_result_cited": "<resultado comunal citado>"},
    "VOTO_PRESIDENCIAL_2021_COMUNAL":     {"question": "VOTO_PRESIDENCIAL_2021_COMUNAL",     "symbol": "<Vpa1..Vpa8|CI>",     "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "municipality_used": "<comuna o N/A>", "municipal_result_cited": "<resultado comunal citado>"},
    "PARTICIPACION_LEGISLATIVA_2021_COMUNAL": {"question": "PARTICIPACION_LEGISLATIVA_2021_COMUNAL", "symbol": "<Tpa1..Tpa7|CI>", "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "municipality_used": "<comuna o N/A>"},
    "VOTO_LEGISLATIVO_2021_COMUNAL":      {"question": "VOTO_LEGISLATIVO_2021_COMUNAL",      "symbol": "<Vpa1..Vpa12|CI>",    "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "municipality_used": "<comuna o N/A>"},
    "PARTICIPACION_2025_COMUNAL":         {"question": "PARTICIPACION_2025_COMUNAL",         "symbol": "<Tcu1..Tcu7|CI>",     "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "municipality_used": "<comuna o N/A>"},
    "INTENCION_VOTO_2025_COMUNAL":        {"question": "INTENCION_VOTO_2025_COMUNAL",        "symbol": "<Vcu1..Vcu8|CI>",     "category": "<texto>", "explanation": "<justificación breve>", "speculation": <0-100>, "evidence_basis": "<campo Stage 1>", "municipality_used": "<comuna o N/A>", "municipal_result_cited": "<resultado comunal citado>"}
  },
  "cannot_infer_fields": [],
  "high_speculation_fields": [],
  "overall_confidence": "<alta|moderada|baja|muy baja>"
}

Notas adicionales sobre campos específicos:
- PERSONA_REAL/PERSONA_VIVE_CHILE/REGION/COMUNA: derivar de demographics.location de Stage 1. Mapear a RP/PLC/REG/COMU directamente.
- PARTICIPACION_PRESIDENCIAL_2021 (Thpa1-7) y VOTO_PRESIDENCIAL_2021 (Vpa1-8): presidenciales 2021.
- INDV_PARTICIPACION_LEGISLATIVA_2021 (Tpaindv1-7) e INDV_VOTO_LEGISLATIVO_2021 (Vpaindv1-12): legislativas 2021.
- INTENCION_VOTO_2025_FECHA_TWEET (Vcu1-8): intención anclada a la fecha del último tweet. Vcu1=no votaría, Vcu2=Kast, Vcu3=Jara, Vcu4=Matthei, Vcu5=Kaiser, Vcu6=Parisi, Vcu7=MEO, Vcu8=Artés.
- explanation: máximo 2 frases; debe citar el campo de Stage 1 que sustenta la predicción.

Categorías de referencia por pregunta:

EDAD: AG1=Menor de 18 años, AG2=18-24, AG3=25-34, AG4=35-44, AG5=45-54, AG6=55-64, AG7=65+
SEXO: S1=Masculino, S2=Femenino
RANGO_INGRESOS_PERSONALES: PINC1=$0-35.000 ... PINC17=Más de $20.000.000
RANGO_INGRESOS_HOGAR: HINC1=$0-35.000 ... HINC17=Más de $20.000.000
ESTADO_CIVIL: MAR1=Casado/a, MAR2=Separado/a, MAR3=Soltero/a, MAR4=Divorciado/a, MAR5=Viudo/a
CALIFICACION_EDUCATIVA: EDU1=Sala Cuna, EDU6=Ed. Básica, EDU10=Técnico Superior, EDU11=Profesional, EDU12=Magíster, EDU13=Doctorado
OCUPACION_ACTUAL: OCCUP1=Patrón/dueño, OCCUP2=Cuenta propia, OCCUP3=Sector público, OCCUP4=Empresa pública, OCCUP5=Sector privado, OCCUP6=FF.AA., OCCUP7=Dom. adentro, OCCUP8=Dom. afuera
ORIENTACION_IDEOLOGICA: IoPoR1=1(Izq) ... IoPoR10=10(Der). NO asignar IoPoR5 por defecto; usar CI.
PARTIDO_POLITICO: PP1=Republicano, PP2=RN, PP3=Frente Amplio, PP4=PC, PP5=PS, PP6=DC, PP7=UDI, PP8=PPD, PP9=PDG, PP10=Liberal, PP11=Demócratas Chile, PP12=EVOPOLI, PP13=Social Cristiano, PP14=Radical, PP15=FRVS
AFINIDAD_PARTIDO: 1-7 (escala numérica)
INTERES_POLITICA: INTP1=Muy interesado/a, INTP2=Algo, INTP3=Poco, INTP4=Nada
ATENCION_CAMPANA_2025/2021: ATT_1=Mucho, ATT_2=Algo, ATT_3=Un poco, ATT_4=Nada
CONFIANZA_GENERAL: TRUS1=Siempre confío ... TRUS5=Nunca confío
PARTICIPACION PRESIDENCIAL 2021: Thpa1(prob=0), Thpa2(0,15), Thpa3(0,3), Thpa4(0,5), Thpa5(0,7), Thpa6(0,85), Thpa7(prob=1)
VOTO PRESIDENCIAL 2021: Vpa1=no votó, Vpa2=Boric, Vpa3=Kast, Vpa4=Provoste, Vpa5=Sichel, Vpa6=Artés, Vpa7=MEO, Vpa8=Parisi
PARTICIPACION LEGISLATIVA 2021 (INDV): Tpaindv1(prob=0) ... Tpaindv7(prob=1)
VOTO LEGISLATIVO 2021 (INDV): Vpaindv1=no votó, Vpaindv2=CS, Vpaindv3=RD, Vpaindv4=PC, Vpaindv5=PDC, Vpaindv6=PPD, Vpaindv7=UDI, Vpaindv8=RN, Vpaindv9=Republicano, Vpaindv10=PDG, Vpaindv11=PRO, Vpaindv12=independiente
PARTICIPACION 2025 (INDV): Tcuindv1(prob=0) ... Tcuindv7(prob=1). NO usar Tcuindv1 por defecto; usar CI.
INTENCION_VOTO_2025 (INDV): Vcuindv1=no votaría, Vcuindv2=Jara, Vcuindv3=Kast, Vcuindv4=Matthei, Vcuindv5=Kaiser, Vcuindv6=Parisi, Vcuindv7=MEO, Vcuindv8=Artés. NO usar Vcuindv1 por defecto; usar CI.
INTENCION_VOTO_2025_FECHA_TWEET: Vcu1=no votaría, Vcu2=Kast, Vcu3=Jara, Vcu4=Matthei, Vcu5=Kaiser, Vcu6=Parisi, Vcu7=MEO, Vcu8=Artés. Pregunta anclada a la fecha del último tweet (refleja intención en ese momento).
INDECISION_2025: Und1(prob=0) ... Und7(prob=1)
FAVORABILIDAD KAST: Kfa1=muy favorable ... Kfa5=desconozco
FAVORABILIDAD JARA: Jfa1=muy favorable ... Jfa5=desconozco
FAVORABILIDAD MATTHEI: Efa1=muy favorable ... Efa5=desconozco
FAVORABILIDAD PARISI: Pfa1=muy favorable ... Pfa5=desconozco
FAVORABILIDAD MEO: Mfa1=muy favorable ... Mfa5=desconozco
FAVORABILIDAD ARTES: Afa1=muy favorable ... Afa5=desconozco
FAVORABILIDAD KAISER: JKfa1=muy favorable ... JKfa5=desconozco
TEMA_MAS_IMPORTANTE: Moi01=Economía, Moi02=Desempleo, Moi03=Corrupción, Moi04=Problemas políticos, Moi05=Delincuencia/seguridad, Moi06=Pobreza, Moi07=Educación, Moi08=Salud, Moi09=Desigualdad
PARTICIPACION COMUNAL 2021: Tpa1(prob=0)...Tpa7(prob=1) en {municipality}
VOTO PRESIDENCIAL COMUNAL 2021: Vpa1=no votó, Vpa2=Boric, Vpa3=Kast, Vpa4=Provoste, Vpa5=Sichel, Vpa6=Artés, Vpa7=MEO, Vpa8=Parisi — en {municipality}
VOTO LEGISLATIVO COMUNAL 2021: Vpa1=no votó ... Vpa12=independiente — en {municipality}
PARTICIPACION 2025 COMUNAL: Tcu1(prob=0)...Tcu7(prob=1) en {municipality}
INTENCION VOTO 2025 COMUNAL: Vcu1=no votaría, Vcu2=Kast, Vcu3=Jara, Vcu4=Matthei, Vcu5=Kaiser, Vcu6=Parisi, Vcu7=MEO, Vcu8=Artés — en {municipality}
Resultados comunales 2021: https://talkingtomachines.org/votacion-comunal-in-chile/
PERSONA_REAL: RP1=Persona real, RP2=Otro (bot, organización, cuenta ficticia)
PERSONA_VIVE_CHILE: PLC1=Sí, PLC2=No
REGION (derivar de demographics.location.inferred_region de Stage 1): REG1=Antofagasta, REG2=Arica y Parinacota, REG3=Atacama, REG4=Aysén, REG5=Coquimbo, REG6=Araucanía, REG7=Los Lagos, REG8=Los Ríos, REG9=Magallanes, REG10=Tarapacá, REG11=Valparaíso, REG12=Ñuble, REG13=Biobío, REG14=O'Higgins, REG15=Maule, REG16=Metropolitana de Santiago, REG17=NA (fuera de Chile)
COMUNA (derivar de demographics.location.inferred_municipality de Stage 1): seleccione el código COMU1-COMU346 que corresponda a la comuna inferida. Si location.confidence es 'none', use CI."""
