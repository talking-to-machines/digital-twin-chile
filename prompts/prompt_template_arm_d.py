"""
Arm D — Minimal Sparse Prompt Template
AIPOP Chile — Digital Interview Pipeline

Architecture: single-stage, sparse.
  One LLM call per subject. The model receives the full social media profile and
  a compact code scheme (prefix ranges only, no full category descriptions).
  It returns one structured **field: value** block per target construct.

Sparse philosophy preserved relative to Arms A/B/C:
  - No full category description lists per question.
  - No explicit inference guidelines (no REGLA DE INFERENCIA CONSERVADORA).
  - No format-correction rules (no REGLA DE FORMATO CRÍTICA).
  - No speculation calibration guidelines.
  - System prompt is minimal (5 lines).
  - The model maps codes naturally without anchoring to dense descriptions.

Output format (same **field: value** structure as Arm A):
  **question: <CANONICAL_VAR_NAME>**
  **symbol: <código o CI>**
  **category: <descripción del símbolo elegido>**
  **explanation: <justificación breve>**
  **speculation: <0-100>**

  "CI" = CANNOT_INFER (equivalent to Arms B/C CI; maps to NAD in analysis dataset).

Pipeline calls:
  Call 1:
      system = arm_d_system_prompt
      user   = arm_d_user_prompt   (fill {platform}, {name}, {account_id},
                                   {location}, {description}, {url},
                                   {created_at}, {is_verified},
                                   {is_blue_verified}, {protected},
                                   {followers}, {following},
                                   {statuses_count}, {favourites_count},
                                   {media_count}, {tweets},
                                   {profile_picture})

Output parsing:
  Same regex-based **field: value** parser as Arm A.
  ARM_D_QUESTION_LABELS (canonical var names in prompt order) drives extraction.
  ARM_D_CANONICAL_MAP documents code spaces and Arm A field correspondence.

Communal questions excluded: municipality-anchored variants require a structured
geographic lookup workflow incompatible with the sparse philosophy.
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

# ─── System Prompt ────────────────────────────────────────────────────────────

arm_d_system_prompt = """Usted está analizando un perfil de X (Twitter) de un usuario chileno.
Prediga cómo respondería esta persona a las preguntas de una encuesta política chilena.
Use únicamente la información disponible en el perfil. Sea conciso.
Para cada pregunta, produzca exactamente cinco líneas: question, symbol, category, explanation, speculation.
Use "CI" como símbolo cuando el perfil no proporcione información suficiente para predecir."""

# ─── User Prompt ─────────────────────────────────────────────────────────────

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
**question: <nombre_pregunta>**
**symbol: <código seleccionado o CI>**
**category: <descripción del símbolo elegido>**
**explanation: <justificación breve basada en el perfil>**
**speculation: <puntuación 0–100>**

Códigos válidos por pregunta (use "CI" si la evidencia es insuficiente):
PERSONA_REAL [RP1=Persona real, RP2=Otro]
PERSONA_VIVE_CHILE [PLC1=Sí, PLC2=No]
REGION [REG1–REG17]
COMUNA [COMU1–COMU346]
EDAD [AG1=<18, AG2=18-24, AG3=25-34, AG4=35-44, AG5=45-54, AG6=55-64, AG7=65+]
SEXO [S1=Masculino, S2=Femenino]
RANGO_INGRESOS_PERSONALES [PINC1–PINC17]
RANGO_INGRESOS_HOGAR [HINC1–HINC17]
ESTADO_CIVIL [MAR1–MAR5]
CALIFICACION_EDUCATIVA [EDU1–EDU14]
OCUPACION_ACTUAL [OCCUP1–OCCUP8]
ORIENTACION_IDEOLOGICA [IoPoR1=izquierda … IoPoR10=derecha]
PARTIDO_POLITICO [PP1–PP15]
AFINIDAD_PARTIDO [1–7]
INTERES_POLITICA [INTP1–INTP4]
ATENCION_CAMPANA_2025 [ATT25_1–ATT25_4]
ATENCION_CAMPANA_2021 [ATT21_1–ATT21_4]
CONFIANZA_GENERAL [TRUS1–TRUS5]
PARTICIPACION_PRESIDENCIAL_2021 [Thpa1–Thpa7]
VOTO_PRESIDENCIAL_2021 [Vpa1–Vpa8]
INDV_PARTICIPACION_LEGISLATIVA_2021 [Tpaindv1–Tpaindv7]
INDV_VOTO_LEGISLATIVO_2021 [Vpaindv1–Vpaindv12]
INDV_PARTICIPACION_2025 [Tcuindv1–Tcuindv7]
INDV_INTENCION_VOTO_2025 [Vcuindv1–Vcuindv8]
INTENCION_VOTO_2025_FECHA_TWEET [Vcu1–Vcu8]
INDECISION_2025 [Und1–Und7]
FAVORABILIDAD_KAST [Kfa1–Kfa5]
FAVORABILIDAD_JARA [Jfa1–Jfa5]
FAVORABILIDAD_MATTHEI [Efa1–Efa5]
FAVORABILIDAD_PARISI [Pfa1–Pfa5]
FAVORABILIDAD_MEO [Mfa1–Mfa5]
FAVORABILIDAD_ARTES [Afa1–Afa5]
FAVORABILIDAD_KAISER [JKfa1–JKfa5]
TEMA_MAS_IMPORTANTE [Moi01–Moi09]

¡Produzca un bloque de cinco líneas por pregunta, en el orden indicado!"""

# ─── Question labels (canonical var names, in prompt order) ──────────────────
#
# Drive the **field: value** parser: scan the model output for
# **question: <label>** and extract the subsequent symbol/category/etc. fields.

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
    "INDV_PARTICIPACION_LEGISLATIVA_2021",
    "INDV_VOTO_LEGISLATIVO_2021",
    "INDV_PARTICIPACION_2025",
    "INDV_INTENCION_VOTO_2025",
    "INTENCION_VOTO_2025_FECHA_TWEET",
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

# Canonical NAD marker (symbol value when evidence is insufficient).
ARM_D_NO_DATA_MARKER = "CI"

# ─── Canonical variable map ───────────────────────────────────────────────────
#
# Maps each ARM_D_QUESTION_LABELS entry to its code space and Arm A question
# label. Used by the post-run analysis pipeline for cross-arm alignment.

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
        "code_space": "COMU1-COMU346",
        "arm_a_field": "COMUNA",
    },
    "EDAD": {
        "code_space": "AG1=<18, AG2=18-24, AG3=25-34, AG4=35-44, AG5=45-54, AG6=55-64, AG7=65+",
        "arm_a_field": "EDAD",
    },
    "SEXO": {
        "code_space": "S1=Masculino, S2=Femenino",
        "arm_a_field": "SEXO",
    },
    "RANGO_INGRESOS_PERSONALES": {
        "code_space": "PINC1=$0-35k … PINC17=+$20M",
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
        "code_space": "PP1=Republicano, PP2=RN, PP3=FA, PP4=PC, PP5=PS, PP6=DC, PP7=UDI, PP8=PPD, PP9=PDG, PP10=Liberal, PP11=Demócratas Chile, PP12=EVOPOLI, PP13=Social Cristiano, PP14=Radical, PP15=FRVS",
        "arm_a_field": "PARTIDO POLÍTICO",
    },
    "AFINIDAD_PARTIDO": {
        "code_space": "1-7 (escala numérica)",
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
        "code_space": "Thpa1(prob=0) … Thpa7(prob=1)",
        "arm_a_field": "VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021",
    },
    "VOTO_PRESIDENCIAL_2021": {
        "code_space": "Vpa1=no votó, Vpa2=Boric, Vpa3=Kast, Vpa4=Provoste, Vpa5=Sichel, Vpa6=Artés, Vpa7=MEO, Vpa8=Parisi",
        "arm_a_field": "VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021",
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
        "code_space": "Tcuindv1(prob=0) … Tcuindv7(prob=1)",
        "arm_a_field": "(INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025",
    },
    "INDV_INTENCION_VOTO_2025": {
        "code_space": "Vcuindv1=no votaría, Vcuindv2=Jara, Vcuindv3=Kast, Vcuindv4=Matthei, Vcuindv5=Kaiser, Vcuindv6=Parisi, Vcuindv7=MEO, Vcuindv8=Artés",
        "arm_a_field": "(INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025",
    },
    "INTENCION_VOTO_2025_FECHA_TWEET": {
        "code_space": "Vcu1=no votaría, Vcu2=Kast, Vcu3=Jara, Vcu4=Matthei, Vcu5=Kaiser, Vcu6=Parisi, Vcu7=MEO, Vcu8=Artés",
        "arm_a_field": "PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025 SI LAS ELECCIONES SE CELEBRARAN EN LA FECHA DE SU ÚLTIMO TUIT",
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
