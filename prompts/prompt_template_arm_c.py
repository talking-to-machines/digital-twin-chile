"""
Arm C — Two-Stage Architecture with Randomised Option Ordering
AIPOP Chile — Digital Interview Pipeline

Architecture: identical to Arm B (two-stage) except that Stage 2 presents answer
options in a randomised order per respondent per question.

Pipeline calls:
  Call 1 (Stage 1):  same as Arm B — use arm_b_stage1_system_prompt and
                     arm_b_stage1_user_prompt from prompt_template_arm_b.py.
                     Import them directly to avoid duplication.

  Call 2 (Stage 2):
      system = arm_c_stage2_system_prompt
      user   = build_arm_c_stage2_user_prompt(stage_1_output_json, subject_id)
               This function fills {stage_1_output_json} and all
               {shuffled_options_*} placeholders before the API call.

Output parsing:
  Same JSON schema as Arm B Stage 2. Parse with json.loads().
  The randomisation_log is written by build_arm_c_stage2_user_prompt and should
  be saved alongside the raw LLM output for ordering sensitivity analyses.

Randomisation contract:
  - Seed: f"{subject_id}_{question_key}"  (deterministic, reproducible).
  - All options including CI are shuffled together.
  - Canonical symbol codes are preserved regardless of display order.
  - The model selects based on evidence content, not option position.
"""

import os
import random
import json
from typing import Dict, List

base_dir = os.path.dirname(os.path.abspath(__file__))

# Stage 1 is identical to Arm B — import to avoid duplication
from prompts.prompt_template_arm_b import (
    x_tweet_prompt_template,
    arm_b_stage1_system_prompt as arm_c_stage1_system_prompt,
    arm_b_stage1_user_prompt as arm_c_stage1_user_prompt,
)

# ─── Canonical option lists ───────────────────────────────────────────────────
# Each value is a list of option strings exactly as they appear in the prompt.
# The pipeline shuffles these lists and joins them with "\n" before insertion.

CANONICAL_OPTIONS: Dict[str, List[str]] = {
    "EDAD": [
        "AG1) Menor de 18 años",
        "AG2) De 18 a 24 años",
        "AG3) De 25 a 34 años",
        "AG4) De 35 a 44 años",
        "AG5) De 45 a 54 años",
        "AG6) De 55 a 64 años",
        "AG7) 65 años o más",
        "CI) CANNOT_INFER — sin evidencia suficiente para inferir la edad",
    ],
    "SEXO": [
        "S1) Masculino",
        "S2) Femenino",
        "CI) CANNOT_INFER — sin evidencia suficiente para inferir el género",
    ],
    "PINC": [
        "PINC1) $0 a $35.000",
        "PINC2) $35.001 a $60.000",
        "PINC3) $60.001 a $100.000",
        "PINC4) $100.001 a $200.000",
        "PINC5) $200.001 a $350.000",
        "PINC6) $350.001 a $500.000",
        "PINC7) $500.001 a $750.000",
        "PINC8) $750.001 a $1.000.000",
        "PINC9) $1.000.001 a $1.500.000",
        "PINC10) $1.500.001 a $2.000.000",
        "PINC11) $2.000.001 a $3.000.000",
        "PINC12) $3.000.001 a $5.000.000",
        "PINC13) $5.000.001 a $7.500.000",
        "PINC14) $7.500.001 a $10.000.000",
        "PINC15) $10.000.001 a $15.000.000",
        "PINC16) $15.000.001 a $20.000.000",
        "PINC17) Más de $20.000.000",
        "CI) CANNOT_INFER — sin evidencia suficiente para inferir el ingreso personal",
    ],
    "HINC": [
        "HINC1) $0 a $35.000",
        "HINC2) $35.001 a $60.000",
        "HINC3) $60.001 a $100.000",
        "HINC4) $100.001 a $200.000",
        "HINC5) $200.001 a $350.000",
        "HINC6) $350.001 a $500.000",
        "HINC7) $500.001 a $750.000",
        "HINC8) $750.001 a $1.000.000",
        "HINC9) $1.000.001 a $1.500.000",
        "HINC10) $1.500.001 a $2.000.000",
        "HINC11) $2.000.001 a $3.000.000",
        "HINC12) $3.000.001 a $5.000.000",
        "HINC13) $5.000.001 a $7.500.000",
        "HINC14) $7.500.001 a $10.000.000",
        "HINC15) $10.000.001 a $15.000.000",
        "HINC16) $15.000.001 a $20.000.000",
        "HINC17) Más de $20.000.000",
        "CI) CANNOT_INFER — sin evidencia suficiente para inferir el ingreso del hogar",
    ],
    "ESTADO_CIVIL": [
        "MAR1) Casado(a) — legalmente casado/a y viviendo con su cónyuge",
        "MAR2) Separado(a) — legalmente casado/a pero separado/a",
        "MAR3) Soltero(a) — nunca casado/a",
        "MAR4) Divorciado(a) — legalmente divorciado/a",
        "MAR5) Viudo(a) — cónyuge fallecido",
        "CI) CANNOT_INFER — sin evidencia suficiente para inferir el estado civil",
    ],
    "EDUCACION": [
        "EDU1) Sala Cuna o Jardín Infantil",
        "EDU2) PreKinder",
        "EDU3) Kinder",
        "EDU4) Especial o Diferencial",
        "EDU5) Primaria o Preparatoria (Sistema antiguo)",
        "EDU6) Educación Básica",
        "EDU7) Científico-Humanista",
        "EDU8) Técnica Profesional",
        "EDU9) Humanidades (Sistema antiguo)",
        "EDU10) Técnico Nivel Superior (carreras 1–4 años)",
        "EDU11) Profesional (carreras 1–6 años)",
        "EDU12) Magíster",
        "EDU13) Doctorado",
        "EDU14) Nunca asistió",
        "CI) CANNOT_INFER — sin evidencia suficiente para inferir el nivel educativo",
    ],
    "OCUPACION": [
        "OCCUP1) Patrón o dueño de empresa o negocio",
        "OCCUP2) Trabajador por cuenta propia",
        "OCCUP3) Empleado u obrero del sector público",
        "OCCUP4) Empleado u obrero de empresas públicas",
        "OCCUP5) Empleado u obrero del sector privado",
        "OCCUP6) Fuerzas Armadas, de Orden y Seguridad",
        "OCCUP7) Servicio doméstico puertas adentro",
        "OCCUP8) Servicio doméstico puertas afuera",
        "CI) CANNOT_INFER — sin evidencia suficiente para inferir la ocupación",
    ],
    "IDEOLOGIA": [
        "IoPoR1) 1 (Izquierda)",
        "IoPoR2) 2",
        "IoPoR3) 3",
        "IoPoR4) 4",
        "IoPoR5) 5 (Centro) — NO usar por defecto; solo con evidencia",
        "IoPoR6) 6",
        "IoPoR7) 7",
        "IoPoR8) 8",
        "IoPoR9) 9",
        "IoPoR10) 10 (Derecha)",
        "CI) CANNOT_INFER — sin señales políticas suficientes para situar al usuario en la escala",
    ],
    "PARTIDO": [
        "PP1) Partido Republicano",
        "PP2) Renovación Nacional (RN)",
        "PP3) Frente Amplio",
        "PP4) Partido Comunista (PC)",
        "PP5) Partido Socialista (PS)",
        "PP6) Democracia Cristiana (DC)",
        "PP7) Unión Demócrata Independiente (UDI)",
        "PP8) Partido Por la Democracia (PPD)",
        "PP9) Partido de la Gente (PDG)",
        "PP10) Partido Liberal",
        "PP11) Partido Demócratas Chile",
        "PP12) Evolución Política (EVOPOLI)",
        "PP13) Partido Social Cristiano",
        "PP14) Partido Radical (PR)",
        "PP15) Frente Regionalista Verde Social (FRVS)",
        "CI) CANNOT_INFER — sin evidencia suficiente para identificar afinidad partidaria",
    ],
    "AFINIDAD": [
        "1) Ninguna simpatía",
        "2)",
        "3)",
        "4)",
        "5)",
        "6)",
        "7) Mucha simpatía",
        "CI) CANNOT_INFER — sin partido identificado o sin evidencia de afinidad",
    ],
    "INTERES": [
        "INTP1) Muy interesado(a)",
        "INTP2) Algo interesado(a)",
        "INTP3) Poco interesado(a)",
        "INTP4) Nada interesado(a)",
        "CI) CANNOT_INFER — sin evidencia suficiente para estimar el interés político",
    ],
    "ATT2025": [
        "ATT25_1) Mucho",
        "ATT25_2) Algo",
        "ATT25_3) Un poco",
        "ATT25_4) Nada",
        "CI) CANNOT_INFER — sin evidencia sobre atención a la campaña 2025",
    ],
    "ATT2021": [
        "ATT21_1) Mucho",
        "ATT21_2) Algo",
        "ATT21_3) Un poco",
        "ATT21_4) Nada",
        "CI) CANNOT_INFER — sin evidencia sobre atención a la campaña 2021",
    ],
    "CONFIANZA": [
        "TRUS1) Siempre confío en otras personas",
        "TRUS2) La mayor parte del tiempo confío en otras personas",
        "TRUS3) Aproximadamente la mitad del tiempo confío en otras personas",
        "TRUS4) Algunas veces confío en otras personas",
        "TRUS5) Nunca confío en otras personas",
        "CI) CANNOT_INFER — sin evidencia sobre confianza interpersonal",
    ],
    "THPA": [
        "Thpa1) No hay posibilidad de que haya votado — prob: 0",
        "Thpa2) Es muy improbable que haya votado — prob: 0,15",
        "Thpa3) Es improbable que haya votado — prob: 0,3",
        "Thpa4) 50% de probabilidades de que haya votado — prob: 0,5",
        "Thpa5) Es probable que haya votado — prob: 0,7",
        "Thpa6) Es muy probable que haya votado — prob: 0,85",
        "Thpa7) Se tiene certeza de que ha votado — prob: 1",
        "CI) CANNOT_INFER — sin evidencia sobre participación presidencial 2021",
    ],
    "VPA": [
        "Vpa1) No votó en las elecciones presidenciales de 2021",
        "Vpa2) Votó por Gabriel Boric (Convergencia Social)",
        "Vpa3) Votó por José Antonio Kast (Partido Republicano)",
        "Vpa4) Votó por Yasna Provoste (PDC)",
        "Vpa5) Votó por Sebastián Sichel (Chile Podemos Más)",
        "Vpa6) Votó por Eduardo Artés (Unión Patriótica)",
        "Vpa7) Votó por Marco Enríquez-Ominami (Partido Progresista)",
        "Vpa8) Votó por Franco Parisi (Partido de la Gente)",
        "CI) CANNOT_INFER — sin evidencia sobre opción de voto presidencial 2021",
    ],
    "TPAINDV_LEG": [
        "Tpaindv1) No hay posibilidad de que haya votado — prob: 0",
        "Tpaindv2) Es muy improbable que haya votado — prob: 0,15",
        "Tpaindv3) Es poco probable que haya votado — prob: 0,3",
        "Tpaindv4) 50% de probabilidades de que haya votado — prob: 0,5",
        "Tpaindv5) Es probable que haya votado — prob: 0,7",
        "Tpaindv6) Es muy probable que haya votado — prob: 0,85",
        "Tpaindv7) Hay certeza de que ha votado — prob: 1",
        "CI) CANNOT_INFER — sin evidencia sobre participación legislativa 2021",
    ],
    "VPAINDV_LEG": [
        "Vpaindv1) No votó en las elecciones legislativas de 2021",
        "Vpaindv2) Votó por un candidato de Convergencia Social (CS)",
        "Vpaindv3) Votó por un candidato de Revolución Democrática (RD)",
        "Vpaindv4) Votó por un candidato del Partido Comunista (PC)",
        "Vpaindv5) Votó por un candidato del Partido Demócrata Cristiano (PDC)",
        "Vpaindv6) Votó por un candidato del Partido por la Democracia (PPD)",
        "Vpaindv7) Votó por un candidato de Unión Demócrata Independiente (UDI)",
        "Vpaindv8) Votó por un candidato de Renovación Nacional (RN)",
        "Vpaindv9) Votó por un candidato del Partido Republicano (PLR)",
        "Vpaindv10) Votó por un candidato del Partido de la Gente (PDG)",
        "Vpaindv11) Votó por un candidato del Partido Progresista (PRO)",
        "Vpaindv12) Votó por un candidato independiente",
        "CI) CANNOT_INFER — sin evidencia sobre opción de voto legislativo 2021",
    ],
    "TCUINDV": [
        "Tcuindv1) No hay posibilidad de que vaya a votar — prob: 0",
        "Tcuindv2) Es muy improbable que vaya a votar — prob: 0,15",
        "Tcuindv3) Es improbable que vaya a votar — prob: 0,3",
        "Tcuindv4) 50% de probabilidades de que vote — prob: 0,5",
        "Tcuindv5) Probable que vaya a votar — prob: 0,7",
        "Tcuindv6) Es muy probable que vaya a votar — prob: 0,85",
        "Tcuindv7) Hay certeza de que irá a votar — prob: 1",
        "CI) CANNOT_INFER — sin evidencia sobre intención de participación 2025",
    ],
    "VCUINDV": [
        "Vcuindv1) No votaría en las elecciones presidenciales de 2025",
        "Vcuindv2) Votaría por Jeannette Jara (PC)",
        "Vcuindv3) Votaría por José Antonio Kast (Republicano)",
        "Vcuindv4) Votaría por Evelyn Matthei (UDI/RN)",
        "Vcuindv5) Votaría por Johannes Kaiser (PNL)",
        "Vcuindv6) Votaría por Franco Parisi (PDG)",
        "Vcuindv7) Votaría por Marco Enríquez-Ominami (independiente)",
        "Vcuindv8) Votaría por Eduardo Artés (independiente)",
        "CI) CANNOT_INFER — sin evidencia sobre intención de voto 2025",
    ],
    "VCU_FECHA_TWEET": [
        "Vcu1) No votaría en las elecciones presidenciales de 2025",
        "Vcu2) Votaría por José Antonio Kast (Partido Republicano)",
        "Vcu3) Votaría por Jeannette Jara (PC)",
        "Vcu4) Votaría por Evelyn Matthei (UDI)",
        "Vcu5) Votaría por Johannes Kaiser (PNL)",
        "Vcu6) Votaría por Franco Parisi (PDG)",
        "Vcu7) Votaría por Marco Enríquez-Ominami (independiente)",
        "Vcu8) Votaría por Eduardo Artés (independiente)",
        "CI) CANNOT_INFER — sin evidencia sobre intención en fecha del último tweet",
    ],
    "INDECISION": [
        "Und1) No hay posibilidad de cambio — prob: 0",
        "Und2) Es muy improbable que cambie — prob: 0,15",
        "Und3) Es poco probable que cambie — prob: 0,3",
        "Und4) 50% de probabilidades de cambio — prob: 0,5",
        "Und5) Es probable que cambie — prob: 0,7",
        "Und6) Es muy probable que cambie — prob: 0,85",
        "Und7) Hay certeza de que cambiará — prob: 1",
        "CI) CANNOT_INFER — sin evidencia sobre indecisión electoral",
    ],
    "FAV_KAST": [
        "Kfa1) Opinión muy favorable de José Antonio Kast",
        "Kfa2) Opinión algo favorable de José Antonio Kast",
        "Kfa3) Opinión algo desfavorable de José Antonio Kast",
        "Kfa4) Opinión muy desfavorable de José Antonio Kast",
        "Kfa5) Desconozco quién es José Antonio Kast",
        "CI) CANNOT_INFER — sin evidencia sobre la opinión respecto a Kast",
    ],
    "FAV_JARA": [
        "Jfa1) Opinión muy favorable de Jeannette Jara",
        "Jfa2) Opinión algo favorable de Jeannette Jara",
        "Jfa3) Opinión algo desfavorable de Jeannette Jara",
        "Jfa4) Opinión muy desfavorable de Jeannette Jara",
        "Jfa5) Desconozco quién es Jeannette Jara",
        "CI) CANNOT_INFER — sin evidencia sobre la opinión respecto a Jara",
    ],
    "FAV_MATTHEI": [
        "Efa1) Opinión muy favorable de Evelyn Matthei",
        "Efa2) Opinión algo favorable de Evelyn Matthei",
        "Efa3) Opinión algo desfavorable de Evelyn Matthei",
        "Efa4) Opinión muy desfavorable de Evelyn Matthei",
        "Efa5) Desconozco quién es Evelyn Matthei",
        "CI) CANNOT_INFER — sin evidencia sobre la opinión respecto a Matthei",
    ],
    "FAV_PARISI": [
        "Pfa1) Opinión muy favorable de Franco Parisi",
        "Pfa2) Opinión algo favorable de Franco Parisi",
        "Pfa3) Opinión algo desfavorable de Franco Parisi",
        "Pfa4) Opinión muy desfavorable de Franco Parisi",
        "Pfa5) Desconozco quién es Franco Parisi",
        "CI) CANNOT_INFER — sin evidencia sobre la opinión respecto a Parisi",
    ],
    "FAV_MEO": [
        "Mfa1) Opinión muy favorable de Marco Enríquez-Ominami",
        "Mfa2) Opinión algo favorable de Marco Enríquez-Ominami",
        "Mfa3) Opinión algo desfavorable de Marco Enríquez-Ominami",
        "Mfa4) Opinión muy desfavorable de Marco Enríquez-Ominami",
        "Mfa5) Desconozco quién es Marco Enríquez-Ominami",
        "CI) CANNOT_INFER — sin evidencia sobre la opinión respecto a MEO",
    ],
    "FAV_ARTES": [
        "Afa1) Opinión muy favorable de Eduardo Artés",
        "Afa2) Opinión algo favorable de Eduardo Artés",
        "Afa3) Opinión algo desfavorable de Eduardo Artés",
        "Afa4) Opinión muy desfavorable de Eduardo Artés",
        "Afa5) Desconozco quién es Eduardo Artés",
        "CI) CANNOT_INFER — sin evidencia sobre la opinión respecto a Artés",
    ],
    "FAV_KAISER": [
        "JKfa1) Opinión muy favorable de Johannes Kaiser",
        "JKfa2) Opinión algo favorable de Johannes Kaiser",
        "JKfa3) Opinión algo desfavorable de Johannes Kaiser",
        "JKfa4) Opinión muy desfavorable de Johannes Kaiser",
        "JKfa5) Desconozco quién es Johannes Kaiser",
        "CI) CANNOT_INFER — sin evidencia sobre la opinión respecto a Kaiser",
    ],
    "MAS_IMPORTANTE": [
        "Moi01) Economía",
        "Moi02) Desempleo",
        "Moi03) Corrupción",
        "Moi04) Problemas políticos",
        "Moi05) Delincuencia / seguridad pública",
        "Moi06) Pobreza",
        "Moi07) Educación",
        "Moi08) Salud",
        "Moi09) Desigualdad de ingresos",
        "CI) CANNOT_INFER — sin evidencia sobre el tema prioritario",
    ],
}

# ─── Stage 2 — System Prompt (adds randomisation instruction) ─────────────────

arm_c_stage2_system_prompt = """Usted es un predictor de respuestas de encuesta. Su tarea es predecir cómo respondería este usuario a un conjunto de preguntas de encuesta sobre política chilena, basándose ÚNICAMENTE en la hoja de evidencia extraída de su perfil (output de Stage 1).

REGLAS ESTRICTAS (idénticas a Arm B):
1. Base sus predicciones exclusivamente en la hoja de evidencia Stage 1. No use conocimiento general sobre demografía típica de Twitter en Chile.
2. Adopte encuadre de proxy predictivo: "Dado lo que se observa en este perfil, esta persona tiene mayor probabilidad de responder..."
3. Donde la evidencia en Stage 1 sea insuficiente, seleccione CANNOT_INFER (símbolo: "CI").
4. No asigne CANNOT_INFER si hay evidencia de nivel medium o superior.
5. El output DEBE ser un JSON válido con la estructura del esquema Stage 2 (idéntico al de Arm B). No incluya texto fuera del JSON.
6. Niveles de especulación: 0-20=evidencia directa alta, 21-40=indirecta fuerte, 41-60=indirecta débil, 61-80=muy escasa, 81-100=ninguna.
7. Cada predicción DEBE incluir los campos: question (nombre canónico), symbol (código), category (etiqueta), explanation (justificación breve, máx. 2 frases, basada en Stage 1), speculation (0-100), evidence_basis.

REGLA ADICIONAL — ORDEN ALEATORIO DE OPCIONES:
Las opciones de respuesta de cada pregunta han sido presentadas en orden ALEATORIO por el sistema de inferencia. El orden en que aparecen las opciones NO indica preferencia, relevancia ni jerarquía.
- Seleccione siempre basándose en el CONTENIDO de la evidencia de Stage 1, no en la posición de las opciones.
- Los códigos de símbolo (ej. AG3, PP7, Vcuindv4) son los identificadores canónicos y permanecen válidos independientemente del orden de presentación.
- Esta regla se aplica a todas las preguntas de esta etapa.

DISTINCIÓN OBLIGATORIA ENTRE TIPOS DE PREGUNTAS:
- Preguntas '(INDV)': predicción basada ÚNICAMENTE en evidencia del perfil (Stage 1). Los prefijos de código varían: Tpaindv (legislativas 2021), Thpa (presidenciales 2021), Tcuindv (participación 2025), Vpaindv (voto legislativo), Vpa (voto presidencial 2021), Vcuindv (voto 2025).
- Preguntas geográficas (PERSONA_REAL, PERSONA_VIVE_CHILE, REGION, COMUNA): mapear desde demographics.location de Stage 1 a los códigos RP/PLC/REG/COMU. No se presentan opciones aleatorias para REGION y COMUNA por volumen; derivar directamente de inferred_region e inferred_municipality.
- Preguntas comunales (sufijo _COMUNAL): combinar resultados electorales de la comuna con el perfil. Si Stage 1 reporta CANNOT_INFER para localización, usar CI."""

# ─── Stage 2 — User Prompt Template (with shuffled_options placeholders) ──────

_arm_c_stage2_user_prompt_template = """A continuación se presenta la hoja de evidencia (Stage 1) de este perfil. Basándose en ella, prediga las respuestas de encuesta.

=== HOJA DE EVIDENCIA (STAGE 1 OUTPUT) ===
{stage_1_output_json}
=== FIN DE HOJA DE EVIDENCIA ===

NOTA: Las opciones de cada pregunta se presentan a continuación en orden aleatorio por respondente. El orden varía y no debe influir en su selección. Los códigos de símbolo son canónicos.

Devuelva ÚNICAMENTE un objeto JSON válido con el esquema Stage 2 de Arm B. Cada entrada de predictions debe tener los campos: question, symbol, category, explanation, speculation, evidence_basis. Estructura de ejemplo para una pregunta:
  "EDAD": {{"question": "EDAD", "symbol": "AG4", "category": "De 35 a 44 años", "explanation": "La descripción del perfil y el vocabulario empleado sugieren una persona adulta de mediana edad.", "speculation": 55, "evidence_basis": "demographics.age"}}

CLAVES JSON CANÓNICAS REQUERIDAS — usar exactamente estos nombres como claves en el objeto "predictions":
EDAD, SEXO, RANGO_INGRESOS_PERSONALES, RANGO_INGRESOS_HOGAR, ESTADO_CIVIL, CALIFICACION_EDUCATIVA, OCUPACION_ACTUAL,
ORIENTACION_IDEOLOGICA, PARTIDO_POLITICO, AFINIDAD_PARTIDO, INTERES_POLITICA, ATENCION_CAMPANA_2025, ATENCION_CAMPANA_2021,
CONFIANZA_GENERAL, PARTICIPACION_PRESIDENCIAL_2021, VOTO_PRESIDENCIAL_2021, INDV_PARTICIPACION_LEGISLATIVA_2021,
INDV_VOTO_LEGISLATIVO_2021, INDV_PARTICIPACION_2025, INDV_INTENCION_VOTO_2025, INTENCION_VOTO_2025_FECHA_TWEET,
INDECISION_2025, FAVORABILIDAD_KAST, FAVORABILIDAD_JARA, FAVORABILIDAD_MATTHEI, FAVORABILIDAD_PARISI,
FAVORABILIDAD_MEO, FAVORABILIDAD_ARTES, FAVORABILIDAD_KAISER, TEMA_MAS_IMPORTANTE,
PERSONA_REAL, PERSONA_VIVE_CHILE, REGION, COMUNA

EDAD [→ "EDAD"]:
¿Cuál es su edad actual en años?
{shuffled_options_EDAD}

SEXO [→ "SEXO"]:
¿Cuál es su género?
{shuffled_options_SEXO}

RANGO DE INGRESOS PERSONALES [→ "RANGO_INGRESOS_PERSONALES"]:
¿En qué rango considera que se ubica su ingreso individual mensual?
{shuffled_options_PINC}

RANGO DE INGRESOS DEL HOGAR [→ "RANGO_INGRESOS_HOGAR"]:
¿En qué rango considera que se ubica el ingreso mensual total de su hogar?
{shuffled_options_HINC}

ESTADO CIVIL [→ "ESTADO_CIVIL"]:
¿Cuál es su estado civil actual?
{shuffled_options_ESTADO_CIVIL}

CALIFICACIÓN EDUCATIVA MÁS ALTA [→ "CALIFICACION_EDUCATIVA"]:
¿Cuál es su mayor nivel educacional?
{shuffled_options_EDUCACION}

OCUPACIÓN ACTUAL [→ "OCUPACION_ACTUAL"]:
¿Cuál de las opciones ejemplifica mejor su ocupación principal?
{shuffled_options_OCUPACION}

ORIENTACIÓN IDEOLÓGICA O POLÍTICA [→ "ORIENTACION_IDEOLOGICA"]:
Escala 1–10 (1=Izquierda, 10=Derecha). ¿Dónde se ubicaría usted?
{shuffled_options_IDEOLOGIA}

PARTIDO POLÍTICO [→ "PARTIDO_POLITICO"]:
Generalmente, ¿con qué partido político simpatiza?
{shuffled_options_PARTIDO}

AFINIDAD CON PARTIDO POLÍTICO [→ "AFINIDAD_PARTIDO"]:
Escala 1–7 (1=ninguna simpatía, 7=mucha simpatía).
{shuffled_options_AFINIDAD}

INTERÉS EN LA POLÍTICA [→ "INTERES_POLITICA"]:
¿Qué tanto le interesa la política en términos generales?
{shuffled_options_INTERES}

ATENCIÓN CAMPAÑA 2025 [→ "ATENCION_CAMPANA_2025"]:
¿Cuánta atención prestó a la campaña para las elecciones generales de 2025?
{shuffled_options_ATT2025}

ATENCIÓN CAMPAÑA 2021 [→ "ATENCION_CAMPANA_2021"]:
¿Cuánta atención prestó a la campaña para las elecciones generales de 2021?
{shuffled_options_ATT2021}

CONFIANZA GENERAL EN OTRAS PERSONAS [→ "CONFIANZA_GENERAL"]:
¿Cree que se puede confiar en la mayoría de las personas, o que hay que ser muy cuidadoso?
{shuffled_options_CONFIANZA}

VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE 2021 [→ "PARTICIPACION_PRESIDENCIAL_2021"]:
[Solo perfil. Códigos: Thpa1..Thpa7]
{shuffled_options_THPA}

VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE 2021 [→ "VOTO_PRESIDENCIAL_2021"]:
[Solo perfil. Códigos: Vpa1..Vpa8]
{shuffled_options_VPA}

(INDV) VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE 2021 [→ "INDV_PARTICIPACION_LEGISLATIVA_2021"]:
[Solo perfil. Códigos: Tpaindv1..Tpaindv7]
{shuffled_options_TPAINDV_LEG}

(INDV) VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE 2021 [→ "INDV_VOTO_LEGISLATIVO_2021"]:
[Solo perfil. Códigos: Vpaindv1..Vpaindv12]
{shuffled_options_VPAINDV_LEG}

(INDV) PREFERENCIAS ACTUALES – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE 2025 [→ "INDV_PARTICIPACION_2025"]:
[Solo perfil. No usar Tcuindv1 por defecto; usar CI si sin evidencia.]
{shuffled_options_TCUINDV}

(INDV) PREFERENCIAS ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE 2025 [→ "INDV_INTENCION_VOTO_2025"]:
[Solo perfil. No usar Vcuindv1 por defecto; usar CI si sin evidencia.]
{shuffled_options_VCUINDV}

PREFERENCIAS ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE 2025 SI LAS ELECCIONES SE CELEBRARAN EN LA FECHA DE SU ÚLTIMO TUIT [→ "INTENCION_VOTO_2025_FECHA_TWEET"]:
[Anclar a la fecha del último tweet, no a la fecha actual.]
{shuffled_options_VCU_FECHA_TWEET}

INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE 2025 [→ "INDECISION_2025"]:
{shuffled_options_INDECISION}

FAVORABILIDAD DE JOSÉ ANTONIO KAST [→ "FAVORABILIDAD_KAST"]:
{shuffled_options_FAV_KAST}

FAVORABILIDAD DE JEANNETTE JARA [→ "FAVORABILIDAD_JARA"]:
{shuffled_options_FAV_JARA}

FAVORABILIDAD DE EVELYN MATTHEI [→ "FAVORABILIDAD_MATTHEI"]:
{shuffled_options_FAV_MATTHEI}

FAVORABILIDAD DE FRANCO PARISI [→ "FAVORABILIDAD_PARISI"]:
{shuffled_options_FAV_PARISI}

FAVORABILIDAD DE MARCO ENRÍQUEZ-OMINAMI [→ "FAVORABILIDAD_MEO"]:
{shuffled_options_FAV_MEO}

FAVORABILIDAD DE EDUARDO ARTÉS [→ "FAVORABILIDAD_ARTES"]:
{shuffled_options_FAV_ARTES}

FAVORABILIDAD DE JOHANNES KAISER [→ "FAVORABILIDAD_KAISER"]:
{shuffled_options_FAV_KAISER}

CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE [→ "TEMA_MAS_IMPORTANTE"]:
¿Cuál cree que es el problema más importante que enfrenta el país hoy en día?
{shuffled_options_MAS_IMPORTANTE}

Resultados comunales 2021: https://talkingtomachines.org/votacion-comunal-in-chile/
Para preguntas comunales, usar location.inferred_municipality de Stage 1.

CAMPOS GEOGRÁFICOS (sin opciones aleatorias — derivar directamente de Stage 1):
PERSONA_REAL [→ "PERSONA_REAL"]: RP1=Persona real, RP2=Otro (bot, organización, ficticio). Inferir de profile_metadata y contexto general del perfil.
PERSONA_VIVE_CHILE [→ "PERSONA_VIVE_CHILE"]: PLC1=Sí, PLC2=No. Derivar de demographics.location de Stage 1.
REGION [→ "REGION"]: Seleccionar REG1-REG17 basado en location.inferred_region de Stage 1. REG16=Metropolitana de Santiago, REG17=NA (no vive en Chile o desconocida). Si location.confidence='none', usar CI.
COMUNA [→ "COMUNA"]: Seleccionar COMU1-COMU346 basado en location.inferred_municipality de Stage 1. Si location.confidence='none', usar CI.
Incluir los cuatro campos geográficos en el JSON de salida con el mismo esquema que los demás campos (symbol, category, speculation, evidence_basis)."""


def build_arm_c_stage2_user_prompt(
    stage_1_output_json: str,
    subject_id: str,
    randomization_seed_suffix: str = "",
    save_log_path: str | None = None,
) -> str:
    """
    Fill all {shuffled_options_*} placeholders with randomised option lists
    and inject stage_1_output_json.

    Args:
        stage_1_output_json:   Raw string output from Stage 1 call.
        subject_id:            User identifier (used as randomisation seed base).
        randomization_seed_suffix: Append e.g. '_v2', '_v3' for sensitivity runs.
        save_log_path:         If provided, write the randomisation log (JSON) here.

    Returns:
        Fully formatted user prompt string ready to send to the model.
    """
    shuffled: Dict[str, str] = {}
    log: Dict[str, List[str]] = {}

    for key, options in CANONICAL_OPTIONS.items():
        seed = f"{subject_id}_{key}{randomization_seed_suffix}"
        rng = random.Random(seed)
        shuffled_opts = options.copy()
        rng.shuffle(shuffled_opts)
        shuffled[f"shuffled_options_{key}"] = "\n".join(shuffled_opts)
        log[key] = shuffled_opts

    if save_log_path:
        with open(save_log_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "subject_id": subject_id,
                    "seed_suffix": randomization_seed_suffix,
                    "order": log,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    return _arm_c_stage2_user_prompt_template.format(
        stage_1_output_json=stage_1_output_json,
        **shuffled,
    )
