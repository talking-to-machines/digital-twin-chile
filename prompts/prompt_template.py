import os

base_dir = os.path.dirname(os.path.abspath(__file__))


# Digital Twin
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

digital_twin_profile_prompt_template = """- Imagen De Perfil: {profile_picture}
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
{tweets}"""

base_digital_twin_system_prompt = """Usted está analizando un perfil de redes sociales en {platform} para responder a un conjunto de preguntas.  
Los datos del perfil de {platform} incluyen:
{profile_prompt_template}

Instrucciones:  
Analice la información proporcionada y responda a las siguientes preguntas basándose estrictamente en los datos disponibles. No infiera ni asuma ningún detalle más allá de lo dado. Mantenga las respuestas concisas, precisas y basadas en los datos."""

x_digital_twin_system_prompt = base_digital_twin_system_prompt.format(
    platform="X (anteriormente Twitter)",
    profile_prompt_template=digital_twin_profile_prompt_template,
)

x_digital_twin_entity_geographic_user_prompt = """Se le presentará una serie de categorías a las que el usuario de este perfil de X (anteriormente Twitter) puede pertenecer. Las categorías están precedidas por un título (por ejemplo, "EDAD:" o "SEXO:" etc.) y un símbolo (por ejemplo, "A1", "A2" o "E1", etc.).

Para cada título, siga estrictamente las siguientes instrucciones:
1) Seleccione la respuesta más probable basándose estrictamente en los datos proporcionados por el perfil. La respuesta elegida debe ser la representación más precisa del perfil.
2) Seleccione solo un símbolo/categoría por pregunta. Un título, símbolo y categoría no pueden aparecer más de una vez en su respuesta.
3) Presente el símbolo seleccionado para cada pregunta (si corresponde) y escriba la respuesta asociada con el símbolo seleccionado en su totalidad.
4) Para cada símbolo/categoría seleccionado, indique el nivel de especulación involucrado en la selección en una escala de 0 (nada especulativo, cada elemento del perfil fue útil para la selección) a 100 (totalmente especulativo, no hay información relacionada con esta pregunta en los datos del perfil). Los niveles de especulación deben ser una medida directa de la cantidad de información útil disponible en el perfil y deben referirse únicamente a la información disponible en los datos del perfil —es decir, el nombre de usuario, nombre, descripción, foto de perfil y videos del perfil— y no deben verse afectados por información adicional disponible de cualquier otra fuente.

Para garantizar la coherencia, utilice las siguientes pautas para determinar los niveles de especulación:  
0–20 (Baja especulación): Los datos del perfil proporcionan información clara y directa relevante para la pregunta (por ejemplo, mención explícita en el perfil o vídeos).  
21–40 (Especulación moderada-baja): Los datos del perfil proporcionan indicadores indirectos pero de gran relevancia para la pregunta (por ejemplo, contexto de múltiples fuentes dentro del perfil o vídeos).  
41–60 (Especulación moderada): Los datos del perfil proporcionan algunas pistas o información parcialmente relevante para la pregunta (por ejemplo, inferido de intereses del usuario o referencias indirectas).  
61–80 (Especulación moderada-alta): Los datos del perfil proporcionan indicadores limitados y de relevancia débil para la pregunta (por ejemplo, pistas muy sutiles o contexto mínimo).  
81–100 (Alta especulación): Los datos del perfil no proporcionan ninguna o casi ninguna información relevante para la pregunta (por ejemplo, suposiciones basadas en información muy general).

5) Para cada categoría seleccionada, explique detalladamente qué características de los datos contribuyeron a su elección y a su nivel de especulación.
6) Mantenga un formato de respuesta estrictamente estructurado para garantizar la claridad y facilitar el análisis del texto.

Formato obligatorio: Encierre cada línea de la respuesta entre dos asteriscos (**) al inicio y al final. Cada línea debe comenzar con el nombre del campo en minúsculas, seguido de : , y terminar con **. No incluya texto fuera de los asteriscos ni líneas adicionales:
**question: PERSONA REAL**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: PERSONA QUE VIVE EN CHILE**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: REGIÓN**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: COMUNA**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

¡USTED DEBE DAR UNA RESPUESTA PARA CADA TÍTULO!  
A continuación, se presenta la lista de categorías a las que este usuario puede pertenecer:  

PERSONA REAL: ¿Esta cuenta corresponde a una persona real o a otro tipo de entidad?
RP1) Persona
RP2) Otro

PERSONA QUE VIVE EN CHILE: ¿El usuario de esta cuenta vive en Chile?
PLC1) Sí
PLC2) No

REGIÓN: Si la respuesta a la pregunta PERSONA QUE VIVE EN CHILE es "Sí", seleccione la región en la que vive el usuario de la siguiente lista.
REG1) DE ANTOFAGASTA
REG2) DE ARICA Y PARINACOTA
REG3) DE ATACAMA
REG4) DE AYSEN DEL GENERAL CARLOS IBAÑEZ DEL CAMPO
REG5) DE COQUIMBO
REG6) DE LA ARAUCANIA
REG7) DE LOS LAGOS
REG8) DE LOS RIOS
REG9) DE MAGALLANES Y DE LA ANTARTICA CHILENA
REG10) DE TARAPACA
REG11) DE VALPARAISO
REG12) DE ÑUBLE
REG13) DEL BIOBIO
REG14) DEL LIBERTADOR GENERAL BERNARDO O'HIGGINS
REG15) DEL MAULE
REG16) METROPOLITANA DE SANTIAGO

COMUNA: Si la respuesta a la pregunta PERSONA QUE VIVE EN CHILE es "Sí", seleccione la comuna en la que vive el usuario de la siguiente lista.
COMU1) ALGARROBO
COMU2) ALHUE
COMU3) ALTO BIOBIO
COMU4) ALTO DEL CARMEN
COMU5) ALTO HOSPICIO
COMU6) ANCUD
COMU7) ANDACOLLO
COMU8) ANGOL
COMU9) ANTARTICA
COMU10) ANTOFAGASTA
COMU11) ANTUCO
COMU12) ARAUCO
COMU13) ARICA
COMU14) AYSEN
COMU15) BUIN
COMU16) BULNES
COMU17) CABILDO
COMU18) CABO DE HORNOS(EX-NAVARINO)
COMU19) CABRERO
COMU20) CALAMA
COMU21) CALBUCO
COMU22) CALDERA
COMU23) CALERA
COMU24) CALERA DE TANGO
COMU25) CALLE LARGA
COMU26) CAMARONES
COMU27) CAMIÑA
COMU28) CANELA
COMU29) CARAHUE
COMU30) CARTAGENA
COMU31) CASABLANCA
COMU32) CASTRO
COMU33) CATEMU
COMU34) CAUQUENES
COMU35) CAÑETE
COMU36) CERRILLOS
COMU37) CERRO NAVIA
COMU38) CHAITEN
COMU39) CHANCO
COMU40) CHAÑARAL
COMU41) CHEPICA
COMU42) CHIGUAYANTE
COMU43) CHILE CHICO
COMU44) CHILLAN
COMU45) CHILLAN VIEJO
COMU46) CHIMBARONGO
COMU47) CHOLCHOL
COMU48) CHONCHI
COMU49) CISNES
COMU50) COBQUECURA
COMU51) COCHAMO
COMU52) COCHRANE
COMU53) CODEGUA
COMU54) COELEMU
COMU55) COIHUECO
COMU56) COINCO
COMU57) COLBUN
COMU58) COLCHANE
COMU59) COLINA
COMU60) COLLIPULLI
COMU61) COLTAUCO
COMU62) COMBARBALA
COMU63) CONCEPCION
COMU64) CONCHALI
COMU65) CONCON
COMU66) CONSTITUCION
COMU67) CONTULMO
COMU68) COPIAPO
COMU69) COQUIMBO
COMU70) CORONEL
COMU71) CORRAL
COMU72) COYHAIQUE
COMU73) CUNCO
COMU74) CURACAUTIN
COMU75) CURACAVI
COMU76) CURACO DE VELEZ
COMU77) CURANILAHUE
COMU78) CURARREHUE
COMU79) CUREPTO
COMU80) CURICO
COMU81) DALCAHUE
COMU82) DIEGO DE ALMAGRO
COMU83) DOÑIHUE
COMU84) EL BOSQUE
COMU85) EL CARMEN
COMU86) EL MONTE
COMU87) EL QUISCO
COMU88) EL TABO
COMU89) EMPEDRADO
COMU90) ERCILLA
COMU91) ESTACION CENTRAL
COMU92) FLORIDA
COMU93) FREIRE
COMU94) FREIRINA
COMU95) FRESIA
COMU96) FRUTILLAR
COMU97) FUTALEUFU
COMU98) FUTRONO
COMU99) GALVARINO
COMU100) GENERAL LAGOS
COMU101) GORBEA
COMU102) GRANEROS
COMU103) GUAITECAS
COMU104) HIJUELAS
COMU105) HUALAIHUE
COMU106) HUALAÑE
COMU107) HUALPEN
COMU108) HUALQUI
COMU109) HUARA
COMU110) HUASCO
COMU111) HUECHURABA
COMU112) ILLAPEL
COMU113) INDEPENDENCIA
COMU114) IQUIQUE
COMU115) ISLA DE MAIPO
COMU116) ISLA DE PASCUA
COMU117) JUAN FERNANDEZ
COMU118) LA CISTERNA
COMU119) LA CRUZ
COMU120) LA ESTRELLA
COMU121) LA FLORIDA
COMU122) LA GRANJA
COMU123) LA HIGUERA
COMU124) LA LIGUA
COMU125) LA PINTANA
COMU126) LA REINA
COMU127) LA SERENA
COMU128) LA UNION
COMU129) LAGO RANCO
COMU130) LAGO VERDE
COMU131) LAGUNA BLANCA
COMU132) LAJA
COMU133) LAMPA
COMU134) LANCO
COMU135) LAS CABRAS
COMU136) LAS CONDES
COMU137) LAUTARO
COMU138) LEBU
COMU139) LICANTEN
COMU140) LIMACHE
COMU141) LINARES
COMU142) LITUECHE
COMU143) LLAILLAY
COMU144) LLANQUIHUE
COMU145) LO BARNECHEA
COMU146) LO ESPEJO
COMU147) LO PRADO
COMU148) LOLOL
COMU149) LONCOCHE
COMU150) LONGAVI
COMU151) LONQUIMAY
COMU152) LOS ALAMOS
COMU153) LOS ANDES
COMU154) LOS ANGELES
COMU155) LOS LAGOS
COMU156) LOS MUERMOS
COMU157) LOS SAUCES
COMU158) LOS VILOS
COMU159) LOTA
COMU160) LUMACO
COMU161) MACHALI
COMU162) MACUL
COMU163) MAFIL
COMU164) MAIPU
COMU165) MALLOA
COMU166) MARCHIGUE
COMU167) MARIA ELENA
COMU168) MARIA PINTO
COMU169) MARIQUINA
COMU170) MAULE
COMU171) MAULLIN
COMU172) MEJILLONES
COMU173) MELIPEUCO
COMU174) MELIPILLA
COMU175) MOLINA
COMU176) MONTE PATRIA
COMU177) MOSTAZAL
COMU178) MULCHEN
COMU179) NACIMIENTO
COMU180) NANCAGUA
COMU181) NATALES
COMU182) NAVIDAD
COMU183) NEGRETE
COMU184) NINHUE
COMU185) NOGALES
COMU186) NUEVA IMPERIAL
COMU187) O'HIGGINS
COMU188) OLIVAR
COMU189) OLLAGUE
COMU190) OLMUE
COMU191) OSORNO
COMU192) OVALLE
COMU193) PADRE HURTADO
COMU194) PADRE LAS CASAS
COMU195) PAIHUANO
COMU196) PAILLACO
COMU197) PAINE
COMU198) PALENA
COMU199) PALMILLA
COMU200) PANGUIPULLI
COMU201) PANQUEHUE
COMU202) PAPUDO
COMU203) PAREDONES
COMU204) PARRAL
COMU205) PEDRO AGUIRRE CERDA
COMU206) PELARCO
COMU207) PELLUHUE
COMU208) PEMUCO
COMU209) PENCAHUE
COMU210) PENCO
COMU211) PERALILLO
COMU212) PERQUENCO
COMU213) PETORCA
COMU214) PEUMO
COMU215) PEÑAFLOR
COMU216) PEÑALOLEN
COMU217) PICA
COMU218) PICHIDEGUA
COMU219) PICHILEMU
COMU220) PINTO
COMU221) PIRQUE
COMU222) PITRUFQUEN
COMU223) PLACILLA
COMU224) PORTEZUELO
COMU225) PORVENIR
COMU226) POZO ALMONTE
COMU227) PRIMAVERA
COMU228) PROVIDENCIA
COMU229) PUCHUNCAVI
COMU230) PUCON
COMU231) PUDAHUEL
COMU232) PUENTE ALTO
COMU233) PUERTO MONTT
COMU234) PUERTO OCTAY
COMU235) PUERTO VARAS
COMU236) PUMANQUE
COMU237) PUNITAQUI
COMU238) PUNTA ARENAS
COMU239) PUQUELDON
COMU240) PUREN
COMU241) PURRANQUE
COMU242) PUTAENDO
COMU243) PUTRE
COMU244) PUYEHUE
COMU245) QUEILEN
COMU246) QUELLON
COMU247) QUEMCHI
COMU248) QUILACO
COMU249) QUILICURA
COMU250) QUILLECO
COMU251) QUILLON
COMU252) QUILLOTA
COMU253) QUILPUE
COMU254) QUINCHAO
COMU255) QUINTA DE TILCOCO
COMU256) QUINTA NORMAL
COMU257) QUINTERO
COMU258) QUIRIHUE
COMU259) RANCAGUA
COMU260) RANQUIL
COMU261) RAUCO
COMU262) RECOLETA
COMU263) RENAICO
COMU264) RENCA
COMU265) RENGO
COMU266) REQUINOA
COMU267) RETIRO
COMU268) RINCONADA
COMU269) RIO BUENO
COMU270) RIO CLARO
COMU271) RIO HURTADO
COMU272) RIO IBAÑEZ
COMU273) RIO NEGRO
COMU274) RIO VERDE
COMU275) ROMERAL
COMU276) SAAVEDRA
COMU277) SAGRADA FAMILIA
COMU278) SALAMANCA
COMU279) SAN ANTONIO
COMU280) SAN BERNARDO
COMU281) SAN CARLOS
COMU282) SAN CLEMENTE
COMU283) SAN ESTEBAN
COMU284) SAN FABIAN
COMU285) SAN FELIPE
COMU286) SAN FERNANDO
COMU287) SAN GREGORIO
COMU288) SAN IGNACIO
COMU289) SAN JAVIER
COMU290) SAN JOAQUIN
COMU291) SAN JOSE DE MAIPO
COMU292) SAN JUAN DE LA COSTA
COMU293) SAN MIGUEL
COMU294) SAN NICOLAS
COMU295) SAN PABLO
COMU296) SAN PEDRO
COMU297) SAN PEDRO DE ATACAMA
COMU298) SAN PEDRO DE LA PAZ
COMU299) SAN RAFAEL
COMU300) SAN RAMON
COMU301) SAN ROSENDO
COMU302) SAN VICENTE
COMU303) SANTA BARBARA
COMU304) SANTA CRUZ
COMU305) SANTA JUANA
COMU306) SANTA MARIA
COMU307) SANTIAGO
COMU308) SANTO DOMINGO
COMU309) SIERRA GORDA
COMU310) TALAGANTE
COMU311) TALCA
COMU312) TALCAHUANO
COMU313) TALTAL
COMU314) TEMUCO
COMU315) TENO
COMU316) TEODORO SCHMIDT
COMU317) TIERRA AMARILLA
COMU318) TILTIL
COMU319) TIMAUKEL
COMU320) TIRUA
COMU321) TOCOPILLA
COMU322) TOLTEN
COMU323) TOME
COMU324) TORRES DEL PAINE
COMU325) TORTEL
COMU326) TRAIGUEN
COMU327) TREHUACO
COMU328) TUCAPEL
COMU329) VALDIVIA
COMU330) VALLENAR
COMU331) VALPARAISO
COMU332) VICHUQUEN
COMU333) VICTORIA
COMU334) VICUÑA
COMU335) VILCUN
COMU336) VILLA ALEGRE
COMU337) VILLA ALEMANA
COMU338) VILLARRICA
COMU339) VITACURA
COMU340) VIÑA DEL MAR
COMU341) YERBAS BUENAS
COMU342) YUMBEL
COMU343) YUNGAY
COMU344) ZAPALLAR
COMU345) ÑIQUEN
COMU346) ÑUÑOA"""

x_digital_twin_voting_preference_wo_voting_results_user_prompt = """Formato obligatorio: Encierre cada línea de la respuesta entre dos asteriscos (**) al inicio y al final. Cada línea debe comenzar con el nombre del campo en minúsculas, seguido de : , y terminar con **. No incluya texto fuera de los asteriscos ni líneas adicionales:
**question: EDAD**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: SEXO**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: RANGO DE INGRESOS PERSONALES**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: RANGO DE INGRESOS DEL HOGAR**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: ESTADO CIVIL**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: CALIFICACIÓN EDUCATIVA MÁS ALTA**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: OCUPACIÓN ACUTAL:**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: ORIENTACIÓN IDEOLÓGICA O POLÍTICA**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: PARTIDO POLÍTICO**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: AFINIDAD CON PARTIDO POLÍTICO**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**value: [VALOR AQUÍ]**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: INTERÉS EN LA POLÍTICA**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: ATENCIÓN CAMPAÑA 2025**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: ATENCIÓN CAMPAÑA 2021**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: CONFIANZA GENERAL EN OTRAS PERSONAS**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: (INDV) VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: (INDV) VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: (INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: (INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOSÉ ANTONIO KAST**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA JEANNETTE JARA**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA EVELYN MATTHEI**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO FRANCO PARISI**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO MARCO ENRÍQUEZ-OMINAMI**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO EDUARDO ARTÉS**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOHANNES KAISER**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

**question: PREFERENCIAS DE VOTACIÓN ACTUALES**
**explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
**symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
**category: <CATEGORÍA SELECCIONADA AQUÍ>**
**speculation: <PUNTUACIÓN 0–100 AQUÍ>**

¡USTED DEBE DAR UNA RESPUESTA PARA CADA TÍTULO!  
A continuación, se presenta la lista de categorías a las que este usuario puede pertenecer:  

EDAD:
¿Cuál es su edad actual en años?
AG1) Menor de 18 años
AG2) De 18 a 24 años
AG3) De 25 a 34 años
AG4) De 35 a 44 años
AG5) De 45 a 54 años
AG6) De 55 a 64 años
AG7) 65 años o más

SEXO:
¿Cuál es su género?
S1) Masculino
S2) Femenino

RANGO DE INGRESOS PERSONALES:
¿En qué rango considera que se ubica su ingreso individual mensual?
PINC1) $ 0 a $35.000 
PINC2) $ 35.001 a $60.000 
PINC3) $ 60.001 a $100.000 
PINC4) $ 100.001 a $ 200.000 
PINC5) $ 200.001 a $ 350.000 
PINC6) $ 350.001 a $ 500.000 
PINC7) $ 500.001 a $ 750.000 
PINC8) $ 750.001 a $ 1.000.000 
PINC9) $ 1.000.001 a $ 1.500.000 
PINC10) $ 1.500.001 a $ 2.000.000
PINC11) $ 2.000.001 a $ 3.000.000
PINC12) $ 3.000.001 a $ 5.000.000
PINC13) $ 5.000.001 a $ 7.500.000
PINC14) $ 7.500.001 a $ 10.000.000
PINC15) $ 10.000.001 a $ 15.000.000
PINC16) $ 15.000.001 a $ 20.000.000
PINC17) Más de $ 20.000.000

RANGO DE INGRESOS DEL HOGAR:
¿En qué rango considera que se ubica el ingreso mensual total de su hogar?
HINC1) $ 0 a $35.000  
HINC2) $ 35.001 a $60.000  
HINC3) $ 60.001 a $100.000  
HINC4) $ 100.001 a $ 200.000  
HINC5) $ 200.001 a $ 350.000  
HINC6) $ 350.001 a $ 500.000  
HINC7) $ 500.001 a $ 750.000  
HINC8) $ 750.001 a $ 1.000.000  
HINC9) $ 1.000.001 a $ 1.500.000  
HINC10) $ 1.500.001 a $ 2.000.000  
HINC11) $ 2.000.001 a $ 3.000.000  
HINC12) $ 3.000.001 a $ 5.000.000  
HINC13) $ 5.000.001 a $ 7.500.000  
HINC14) $ 7.500.001 a $ 10.000.000  
HINC15) $ 10.000.001 a $ 15.000.000  
HINC16) $ 15.000.001 a $ 20.000.000  
HINC17) Más de $ 20.000.000

ESTADO CIVIL:
¿Cuál es su estado civil actual?
MAR1) Casado(a) – actualmente legalmente casado(a) y viviendo con su cónyuge
MAR2) Separado(a) – legalmente casado(a) pero separado(a) de su cónyuge
MAR3) Soltero(a) – nunca casado(a), incluyendo a quienes están legalmente separados
MAR4) Divorciado(a) – legalmente divorciado(a) y no vuelto(a) a casar
MAR5) Viudo(a) – el cónyuge ha fallecido y no vuelto(a) a casar

CALIFICACIÓN EDUCATIVA MÁS ALTA:
¿Cuál es su mayor nivel educacional?
EDU1) Sala Cuna o Jardín Infantil
EDU2) PreKinder
EDU3) Kinder
EDU4) Especial o Diferencial
EDU5) Primaria o Preparatoria (Sistema antiguo)
EDU6) Educación Básica
EDU7) Científico-Humanista
EDU8) Técnica Profesional
EDU9) Humanidades (Sistema antiguo)
EDU10) Técnico Nivel Superior (carreras 1–4 años)
EDU11) Profesional (carreras 1–6 años)
EDU12) Magíster
EDU13) Doctorado
EDU14) Nunca asistió

OCUPACIÓN ACUTAL:
¿Cuál de las opciones ejemplifica mejor su ocupación principal?
 OCCUP1) Patrón o dueño de empresa o negocio
OCCUP2) Trabajador por cuenta propia
OCCUP3) Empleado u obrero del sector público (Gob. Central o Municipal, excluye Fuerzas Armadas) OCCUP4) Empleado u obrero de empresas públicas
OCCUP5) Empleado u obrero del sector privado 
OCCUP6) Fuerzas Armadas, de Orden y Seguridad 
OCCUP7)  Servicio doméstico puertas adentro 
OCCUP8) Servicio doméstico puertas afuera

ORIENTACIÓN IDEOLÓGICA O POLÍTICA:
A continuación, se presenta una escala del 1 al 10 que va de izquierda a derecha, donde 1 significa "Izquierda" y 10 significa "Derecha". Hoy en día cuando se habla de tendencias políticas, mucha gente habla de aquellos que simpatizan más con la izquierda o con la derecha. Según el sentido que tengan para usted los términos "Izquierda" y "Derecha" cuando piensa sobre su punto de vista político, ¿Dónde se encontraría en esta escala? Indique el número.
IoPoR1) 1
IoPoR2) 2
IoPoR3) 3
IoPoR4) 4
IoPoR5) 5
IoPoR6) 6
IoPoR7) 7
IoPoR8) 8
IoPoR9) 9
IoPoR10) 10

PARTIDO POLÍTICO:
Generalmente, ¿con qué partido político simpatiza?
PP1) Partido Republicano
PP2) Renovación Nacional (RN)
PP3) Frente Amplio
PP4) Partido Comunista (PC)
PP5) Partido Socialista (PS)
PP6) Democracia Cristiana (DC)
PP7) Unión Demócrata Independiente (UDI)
PP8) Partido Por la Democracia (PPD)
PP9) Partido de la Gente (PDG)
PP10) Partido Liberal
PP11) Partido Demócratas Chile
PP12) Evolución Política (EVOPOLI)
PP13) Partido Social Cristiano
PP14) Partido Radical (PR)
PP15) Frente Regionalista Verde Social (FRVS)

AFINIDAD CON PARTIDO POLÍTICO:
En una escala de 1 a 7, donde 1 significa que no siente ninguna simpatía y 7 significa que siente mucha simpatía por el partido político escogido, ¿qué grado de afinidad siente por el partido que eligió?

INTERÉS EN LA POLÍTICA:
En términos generales, ¿qué tanto le interesa la política?
INTP1) Muy interesado(a)
INTP2) Algo interesado(a)
INTP3) Poco interesado(a)
INTP4) Nada interesado(a)

ATENCIÓN CAMPAÑA 2025:
¿Cuánta atención prestó a la campaña para las elecciones generales de 2025?
ATT25_1) Mucho
ATT25_2) Algo
ATT25_3) Un poco
ATT25_4) Nada

ATENCIÓN CAMPAÑA 2021:
¿Cuánta atención prestó a la campaña para las elecciones generales de 2021?
ATT21_1) Mucho
ATT21_2) Algo
ATT21_3) Un poco
ATT21_4) Nada

CONFIANZA GENERAL EN OTRAS PERSONAS:
En términos generales, ¿cree que se puede confiar en la mayoría de las personas, o que hay que ser muy cuidadoso al tratar con la gente?
TRUS1) Siempre confío en otras personas
TRUS2) La mayor parte del tiempo confío en otras personas
TRUS3) Aproximadamente la mitad del tiempo confío en otras personas
TRUS4) Algunas veces confío en otras personas
TRUS5) Nunca confío en otras personas

(INDV) VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021:
Tpaindv1) No hay posibilidad de que esta persona haya votado – Probabilidad: 0 – en las elecciones  legislativas de 2021.
Tpaindv2) Es muy improbable que esta persona haya votado – Probabilidad: 0,15 – en las elecciones legislativas de 2021.
Tpaindv3) Es poco probable que esta persona haya votado – Probabilidad: 0,3 – en las elecciones legislativas de 2021.
Tpaindv4) Hay un 50 % de probabilidades de que esta persona haya votado – Probabilidad: 0,5 – en las elecciones  legislativas de 2021.
Tpaindv5) Es probable que esta persona haya votado – Probabilidad: 0,7 – en las elecciones legislativas de 2021.
Tpaindv6) Es muy probable que esta persona haya votado – Probabilidad: 0,85 – en las elecciones legislativas de 2021.
Tpaindv7) Hay certeza de que esta persona ha votado – Probabilidad: 1 – en las elecciones legislativas de 2021.

(INDV) VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021:
Vpaindv1) no votó en las elecciones  legislativas de 2021
Vpaindv2) votó por un candidato de Convergencia Social (CS) en las elecciones legislativas de 2021
Vpaindv3) votó por un candidato de Revolución Democrática (RD) en las elecciones legislativas de 2021
Vpaindv4) votó por un candidato del Partido Comunista (PC) en las elecciones legislativas de 2021.
Vpaindv5) votó por un candidato del Partido Demócrata Cristiano (PDC) en las elecciones  legislativas de 2021.
Vpandv6) votó por un candidato del Partido por la Democracia (PPD) en las elecciones legislativas de 2021.
Vpandv7) votó por un candidato de Unión Demócrata Independiente (UDI) en las elecciones legislativas de 2021
Vpandv8) votó por un candidato de Renovación Nacional (RN) en las elecciones legislativas de 2021
Vpandv9) votó por un candidato del Partido Republicano (PLR) en las elecciones legislativas de 2021
Vpandv10) votó por un candidato del Partido de la Gente (PDG) en las elecciones legislativas de 2021
Vpandv11) votó por un candidato del Partido Progresista (PRO) en las elecciones legislativas de 2021
Vpandv12) votó por un candidato independiente en las elecciones legislativas de 2021

VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021:
Thpa1) No hay posibilidad de que esta persona haya votado – Probabilidad: 0 – en las elecciones presidenciales de 2021 Thpa2) Es muy improbable que esta persona haya votado – Probabilidad: 0,15 – en las elecciones presidenciales de 2021 
Thpa3) Es improbable que esta persona haya votado – Probabilidad: 0,3 – en las elecciones presidenciales de 2021 Thpa4) 50 % de probabilidades de que esta persona haya votado – Probabilidad: 0,5 – en las elecciones presidenciales de 2021 Thpa5) Es probable que esta persona haya votado – Probabilidad: 0,7 – en las elecciones presidenciales de 2021 Thpa6) Es muy probable que esta persona haya votado – Probabilidad: 0.85 – en las elecciones presidenciales de 2021 Thpa7) Se tiene certeza de que esta persona ha votado – Probabilidad: 1 – en las elecciones presidenciales de 2021 

VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021: 
Vpa1) no votó en las elecciones presidenciales de 2021
Vpa2) votó por Gabriel Boric, candidato de Convergencia Social, en las elecciones presidenciales de 2021
Vpa3) votó por José Antonio Kast, candidato del Partido Republicano, en las elecciones presidenciales de 2021
Vpa4) votó por Yasna Provoste, candidata del Partido Demócrata Cristiano, en las elecciones presidenciales de 2021
Vpa5) votó por Sebastián Sichel, candidato independiente apoyado por Chile Podemos Más, en las elecciones presidenciales de 2021
Vpa6) votó por Eduardo Artés, candidato de la Unión Patriótica, en las elecciones presidenciales de 2021
Vpa7) votó por Marco Enríquez-Ominami, candidato del Partido Progresista, en las elecciones presidenciales de 2021
Vpa8) votó por Franco Parisi, candidato del Partido de la Gente, en las elecciones presidenciales de 2021

(INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025:
Tcuindv1) No hay posibilidad de que esta persona vaya a votar – Probabilidad: 0 – en las elecciones presidenciales de 2025
Tcuindv2) Es muy improbable que esta persona vaya a votar – Probabilidad: 0,15 – en las elecciones presidenciales de 2025
Tcuindv3) Es improbable que esta persona vaya a votar – Probabilidad: 0,3 – en las elecciones presidenciales de 2025
Tcuindv4) Probabilidad del 50 % de que esta persona vote – Probabilidad: 0,5 – en las elecciones presidenciales de 2025
Tcuindv5) Probable que esta persona vaya a votar – Probabilidad: 0,7 – en las elecciones presidenciales de 2025
Tcuindv6) Es muy probable que esta persona vaya a votar – Probabilidad: 0,85 – en las elecciones presidenciales de 2025
Tcuindv7) Hay certeza de que esta persona irá a votar – Probabilidad: 1 – en las elecciones presidenciales de 2025

(INDV) PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025:
Vcuindv1) no votaría en las elecciones presidenciales de 2025
Vcuindv2) votaría por Jeannette Jara, la candidata del Partido Comunista (PC), en las elecciones presidenciales de 2025
Vcuindv3) votaría por José Antonio Kast, el candidato del Partido Republicano (Republicano), en las elecciones presidenciales de 2025
Vcuindv4) votaría por Evelyn Matthei, la candidata apoyada por la Unión Demócrata Independiente (UDI) / Renovación Nacional (RN), en las elecciones presidenciales de 2025
Vcuindv5) votaría por Johannes Kaiser, candidato del Partido Nacional Libertario (PNL), en las elecciones presidenciales de 2025
Vcuindv6) votaría por Franco Parisi, candidato del Partido de la Gente (PDG), en las elecciones presidenciales de 2025
Vcuindv7) votaría por Marco Enríquez-Ominami, candidato independiente no afiliado a ningún partido mayoritario (recogiendo firmas), en las elecciones presidenciales de 2025
Vcuindv8) votaría por Eduardo Artés, candidato independiente no afiliado a ningún partido mayoritario (en proceso de recolección de firmas), en las elecciones presidenciales de 2025

INDECISIÓN EN TORNO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025: 
¿CUÁN PROBABLE ES QUE EL USUARIO CAMBIE DE OPINIÓN SOBRE SU VOTO RESPECTO A LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025, ENTRE AHORA — FECHA DE SU ÚLTIMO TUIT — Y EL DÍA DE LAS ELECCIONES EN NOVIEMBRE DE 2025?
Und1) No hay posibilidad de que esta persona cambie de opinión - probabilidad: 0 - sobre por cuál candidato presidencial votar - o si se quedará en casa y no votará en absoluto - en las elecciones del 16 de noviembre de 2025
Und2) Es muy improbable que esta persona cambie de opinión - probabilidad: 0,15 - sobre por cuál candidato presidencial votar - o si se quedará en casa y no votará en absoluto - en las elecciones del 16 de noviembre de 2025
Und3) Es poco probable que esta persona cambie de opinión - probabilidad: 0,3 - sobre por cuál candidato presidencial votar - o si se quedará en casa y no votará en absoluto - en las elecciones del 16 de noviembre de 2025
Und4) Probabilidad del 50 % de que esta persona cambie de opinión - probabilidad: 0,5 - sobre por cuál candidato presidencial votar - o si se quedará en casa y no votará en absoluto - en las elecciones del 16 de noviembre de 2025
Und5) Es probable que esta persona cambie de opinión - probabilidad: 0,7 - sobre por cuál candidato presidencial votar - o si se quedará en casa y no votará en absoluto - en las elecciones del 16 de noviembre de 2025
Und6) Es muy probable que esta persona cambie de opinión - Probabilidad: 0,85 - sobre por cuál candidato presidencial votar - o si se quedará en casa y no votará en absoluto - en las elecciones del 16 de noviembre de 2025
Und7) Se tiene certeza de que esta persona cambiará de opinión - probabilidad: 1 - sobre por cuál candidato presidencial votar - o si se quedará en casa y no votará en absoluto - en las elecciones del 16 de noviembre de 2025

FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOSÉ ANTONIO KAST:
Kfa1) Opinión muy favorable de José Antonio Kast
Kfa2) Opinión algo favorable de José Antonio Kast
Kfa3) Opinión algo desfavorable de José Antonio Kast
Kfa4) Opinión muy desfavorable de José Antonio Kast
Kfa5) Desconozco quién es José Antonio Kast, por lo que no puedo tener una opinión sobre él

FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA JEANNETTE JARA:
Jfa1) Opinión muy favorable de Jeannette Jara
Jfa2) Opinión algo favorable de Jeannette Jara
Jfa3) Opinión algo desfavorable de Jeannette Jara
Jfa4) Opinión muy desfavorable de Jeannette Jara
Jfa5) Desconozco quién es Jeannette Jara, por lo que no puedo tener una opinión sobre ella

FAVORABILIDAD DE LA CANDIDATA PRESIDENCIAL CHILENA EVELYN MATTHEI:
Efa1) Opinión muy favorable de Evelyn Matthei
Efa2) Opinión algo favorable de Evelyn Matthei
Efa3) Opinión algo desfavorable de Evelyn Matthei
Efa4) Opinión muy desfavorable de Evelyn Matthei
Efa5) Desconozco quién es Evelyn Matthei, por lo que no puedo tener una opinión sobre ella

FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO FRANCO PARISI:
Pfa1) Opinión muy favorable de Franco Parisi
Pfa2) Opinión algo favorable de Franco Parisi
Pfa3) Opinión algo desfavorable de Franco Parisi
Pfa4) Opinión muy desfavorable de Franco Parisi
Pfa5) Desconozco quién es Franco Parisi, por lo que no puedo tener una opinión sobre él

FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO MARCO ENRÍQUEZ-OMINAMI:
Mfa1) Opinión muy favorable de Marco Enríquez-Ominami
Mfa2) Opinión algo favorable de Marco Enríquez-Ominami
Mfa3) Opinión algo desfavorable de Marco Enríquez-Ominami
Mfa4) Opinión muy desfavorable de Marco Enríquez-Ominami
Mfa5) Desconozco quién es Marco Enríquez-Ominami, por lo que no puedo tener una opinión sobre él

FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO EDUARDO ARTÉS:
Afa1) Opinión muy favorable de Eduardo Artés
Afa2) Opinión algo favorable de Eduardo Artés
Afa3) Opinión algo desfavorable de Eduardo Artés
Afa4) Opinión muy desfavorable de Eduardo Artés
Afa5) Desconozco quién es Eduardo Artés, por lo que no puedo tener una opinión sobre él

FAVORABILIDAD DEL CANDIDATO PRESIDENCIAL CHILENO JOHANNES KAISER:
Kfa1) Opinión muy favorable de Johannes Kaiser
Kfa2) Opinión algo favorable de Johannes Kaiser
Kfa3) Opinión algo desfavorable de Johannes Kaiser
Kfa4) Opinión muy desfavorable de Johannes Kaiser
Kfa5) Desconozco quién es Johannes Kaiser, por lo que no puedo tener una opinión sobre él 

CREENCIA SOBRE EL TEMA MÁS IMPORTANTE ACTUALMENTE:
¿Cuál cree que es el problema más importante que enfrenta el país hoy en día? Por favor, elija un solo tema que considere el más importante.
Moi01) Economía
Moi02) Desempleo
Moi03) Corrupción
Moi04) Problemas políticos
Moi05) Delincuencia / seguridad pública
Moi06) Pobreza
Moi07) Educación
Moi08) Salud
Moi09) Desigualdad de ingresos

PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025 SI LAS ELECCIONES SE CELEBRARAN EN LA FECHA DE SU ÚLTIMO TUIT:
OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025 SI LAS ELECCIONES SE CELEBRARAN EN LA FECHA DE SU ÚLTIMO TUIT:
Vcu1) no votaría en las elecciones presidenciales de 2025
Vcu2) votaría por José Antonio Kast, candidato del Partido Republicano, en las elecciones presidenciales de 2025
Vcu3) votaría por Jeannette Jara, candidata del Partido Comunista, en las elecciones presidenciales de 2025
Vcu4) votaría por Evelyn Matthei, candidata de la Unión Demócrata Independiente, en las elecciones presidenciales de 2025
Vcu5) votaría por Johannes Kaiser, candidato del Partido Nacional Libertario, en las elecciones presidenciales de 2025
Vcu6) votaría por Franco Parisi, candidato del Partido de la Gente, en las elecciones presidenciales de 2025
Vcu7) votaría por Marco Enríquez-Ominami, candidato independiente, en las elecciones presidenciales de 2025
Vcu8) votaría por Eduardo Artés, candidato independiente, en las elecciones presidenciales de 2025"""

# x_digital_twin_voting_preference_with_voting_results_user_prompt = """Los resultados de las Elecciones Presidenciales de Chile de noviembre de 2021 se reportan a nivel de COMUNA y REGIÓN (número de votos por candidato). El conjunto de datos está disponible en:
# https://talkingtomachines.org/votacion-comunal-in-chile/
# Usted ya respondió en un paso anterior la pregunta relacionada con la COMUNA y REGIÓN – “REGIÓN y COMUNA”.
# A partir de este punto, siga estrictamente estas reglas:
# 	1.	Utilice la COMUNA previamente indicada como clave.
# 	2.	Localice en el conjunto de datos los resultados oficiales de la elección (número de votos por candidato) para esa comuna.
# 	3.	Considere estos resultados como la única referencia válida.
# 	4.	Para cada pregunta posterior, debe:
# * Basar su razonamiento y análisis exclusivamente en los resultados de esa comuna.
# * Integrar de manera explícita los números de votos relevantes en sus respuestas.
# * Nunca usar datos de otra comuna o región.
# * Nunca inferir ni aproximar resultados.

# Formato obligatorio: Encierre cada línea de la respuesta entre dos asteriscos (**) al inicio y al final. Cada línea debe comenzar con el nombre del campo en minúsculas, seguido de : , y terminar con **. No incluya texto fuera de los asteriscos ni líneas adicionales:
# **question: VOTACIÓN ANTERIOR - PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021**
# **explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
# **symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
# **category: <CATEGORÍA SELECCIONADA AQUÍ>**
# **speculation: <PUNTUACIÓN 0–100 AQUÍ>**

# **question: VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021**
# **explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
# **symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
# **category: <CATEGORÍA SELECCIONADA AQUÍ>**
# **speculation: <PUNTUACIÓN 0–100 AQUÍ>**

# **question: VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE 2021**
# **explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
# **symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
# **category: <CATEGORÍA SELECCIONADA AQUÍ>**
# **speculation: <PUNTUACIÓN 0–100 AQUÍ>**

# **question: VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021**
# **explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
# **symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
# **category: <CATEGORÍA SELECCIONADA AQUÍ>**
# **speculation: <PUNTUACIÓN 0–100 AQUÍ>**

# **question: PREFERENCIAS DE VOTACIÓN ACTUALES – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025**
# **explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
# **symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
# **category: <CATEGORÍA SELECCIONADA AQUÍ>**
# **speculation: <PUNTUACIÓN 0–100 AQUÍ>**

# **question: PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025**
# **explanation: <RAZONAMIENTO DETALLADO AQUÍ>**
# **symbol: <SÍMBOLO SELECCIONADO AQUÍ>**
# **category: <CATEGORÍA SELECCIONADA AQUÍ>**
# **speculation: <PUNTUACIÓN 0–100 AQUÍ>**

# ¡USTED DEBE DAR UNA RESPUESTA PARA CADA TÍTULO!
# A continuación, se presenta la lista de categorías a las que este usuario puede pertenecer:

# VOTACIÓN ANTERIOR - PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021:
# Tpa1) No hay posibilidad de que esta persona haya votado - Probabilidad: 0 - en las elecciones presidenciales de 2021 en {municipality}
# Tpa2) Es muy improbable que esta persona haya votado - Probabilidad: 0.15 - en las elecciones presidenciales de 2021 en {municipality}
# Tpa3) Es poco probable que esta persona haya votado - Probabilidad: 0,3 - en las elecciones presidenciales de 2021 en {municipality}.
# Tpa4) Probabilidad del 50 % de que esta persona haya votado: 0,5 en las elecciones presidenciales de 2021 en {municipality}.
# Tpa5) Probabilidad de que esta persona haya votado: 0,7 en las elecciones presidenciales de 2021  en {municipality}
# Tpa6) Es muy probable que esta persona haya votado - Probabilidad: 0,85 - en las elecciones presidenciales de 2021 en {municipality}
# Tpa7) Se tiene la certeza de que esta persona ha votado - Probabilidad: 1 -  en las elecciones presidenciales de 2021 en {municipality}

# VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2021:
# Vpa1) no votó en las elecciones presidenciales de 2021 en {municipality}
# Vpa2) votó por Gabriel Boric, candidato de Convergencia Social, en las elecciones presidenciales de 2021 en {municipality}
# Vpa3) votó por José Antonio Kast, candidato del Partido Republicano, en las elecciones presidenciales de 2021 en {municipality}
# Vpa4) votó por Yasna Provoste, candidata del Partido Demócrata Cristiano, en las elecciones presidenciales de 2021 en {municipality}
# Vpa5) votó por Sebastián Sichel, candidato independiente apoyado por Chile Podemos Más, en las elecciones presidenciales de 2021 en {municipality}
# Vpa6) votó por Eduardo Artés, candidato de la Unión Patriótica, en las elecciones presidenciales de 2021
# Vpa7) votó por Marco Enríquez-Ominami, candidato del Partido Progresista, en las elecciones presidenciales de 2021 en {municipality}
# Vpa8) votó por Franco Parisi, candidato del Partido de la Gente, en las elecciones presidenciales de 2021 en {municipality}

# VOTACIÓN ANTERIOR – PARTICIPACIÓN EN LAS ELECCIONES LEGISLATIVAS DE CHILE 2021:
# Tpa1) No hay posibilidad de que esta persona haya votado – Probabilidad: 0 – en las elecciones legislativas de 2021 en {municipality}.
# Tpa2) Es muy improbable que esta persona haya votado – Probabilidad: 0,15 – en las elecciones legislativas de 2021 en {municipality}.
# Tpa3) Es poco probable que esta persona haya votado – Probabilidad: 0,3 – en las elecciones legislativas de 2021 en {municipality}.
# Tpa4) Hay un 50 % de probabilidades de que esta persona haya votado – Probabilidad: 0,5 – en las elecciones legislativas de 2021 en {municipality}.
# Tpa5) Es probable que esta persona haya votado – Probabilidad: 0,7 – en las elecciones parlamentarias de 2021 en {municipality}.
# Tpa6) Es muy probable que esta persona haya votado – Probabilidad: 0,85 – en las elecciones legislativas de 2021 en {municipality}.
# Tpa7) Hay certeza de que esta persona ha votado – Probabilidad: 1 – en las elecciones legislativas de 2021 en {municipality}.

# VOTACIÓN ANTERIOR – OPCIÓN DE VOTO EN LAS ELECCIONES LEGISLATIVAS DE CHILE DE 2021:
# Vpa1) no votó en las elecciones legislativas de 2021 en {municipality}
# Vpa2) votó por un candidato de Convergencia Social (CS) en las elecciones legislativas de 2021 en {municipality}
# Vpa3) votó por un candidato de Revolución Democrática (RD) en las elecciones  legislativas de 2021 en {municipality}
# Vpa4) votó por un candidato del Partido Comunista (PC) en las elecciones legislativas de 2021 en {municipality}.
# Vpa5) votó por un candidato del Partido Demócrata Cristiano (PDC) en las elecciones  legislativas de 2021 en {municipality}.
# Vpa6) votó por un candidato del Partido por la Democracia (PPD) en las elecciones legislativas de 2021 en {municipality}.
# Vpa7) votó por un candidato de Unión Demócrata Independiente (UDI) en las elecciones legislativas  de 2021 en {municipality}
# Vpa8) votó por un candidato de Renovación Nacional (RN) en las elecciones legislativas de 2021 en {municipality}
# Vpa9) votó por un candidato del Partido Republicano (PLR) en las elecciones legislativas de 2021 en {municipality}
# Vpa10) votó por un candidato del Partido de la Gente (PDG) en las elecciones legislativas de 2021 en {municipality}
# Vpa11) votó por un candidato del Partido Progresista (PRO) en las elecciones legislativas de 2021 en {municipality}
# Vpa12) votó por un candidato independiente en las elecciones legislativas de 2021 en {municipality}

# PREFERENCIAS DE VOTACIÓN ACTUALES – PARTICIPACIÓN EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025:
# Tcu1) No hay posibilidad de que esta persona vaya a votar – Probabilidad: 0 – en las elecciones presidenciales de 2025 en {municipality}
# Tcu2) Es muy improbable que esta persona vaya a votar – Probabilidad: 0,15 – en las elecciones presidenciales de 2025 en {municipality}
# Tcu3) Es improbable que esta persona vaya a votar – Probabilidad: 0,3 – en las elecciones presidenciales de 2025 en {municipality}
# Tcu4) Probabilidad del 50 % de que esta persona vote – Probabilidad: 0,5 – en las elecciones presidenciales de 2025 en {municipality}
# Tcu5) Probable que esta persona vaya a votar – Probabilidad: 0,7 – en las elecciones presidenciales de 2025 en {municipality}
# Tcu6) Es muy probable que esta persona vaya a votar – Probabilidad: 0,85 – en las elecciones presidenciales de 2025 en {municipality}
# Tcu7) Hay certeza de que esta persona irá a votar – Probabilidad: 1 – en las elecciones presidenciales de 2025 en {municipality}

# PREFERENCIAS DE VOTACIÓN ACTUALES – OPCIÓN DE VOTO EN LAS ELECCIONES PRESIDENCIALES DE CHILE DE 2025:
# Vcu1) no votaría en las elecciones presidenciales de 2025 en {municipality}
# Vcu2) votaría por Jeannette Jara, la candidata del Partido Comunista (PC), en las elecciones presidenciales de 2025 en {municipality}
# Vcu3) votaría por José Antonio Kast, el candidato del Partido Republicano (Republicano), en las elecciones presidenciales de 2025 en {municipality}
# Vcu4) votaría por Evelyn Matthei, la candidata apoyada por la Unión Demócrata Independiente (UDI) / Renovación Nacional (RN), en las elecciones presidenciales de 2025 en {municipality}
# Vcu5) votaría por Johannes Kaiser, candidato del Partido Nacional Libertario (PNL), en las elecciones presidenciales de 2025 en {municipality}
# Vcu6) votaría por Franco Parisi, candidato del Partido de la Gente (PDG), en las elecciones presidenciales de 2025 en {municipality}
# Vcu7) votaría por Marco Enríquez-Ominami, candidato independiente no afiliado a ningún partido mayoritario (recogiendo firmas), en las elecciones presidenciales de 2025 en {municipality}
# Vcu8) votaría por Eduardo Artés, candidato independiente no afiliado a ningún partido mayoritario (en proceso de recolección de firmas), en las elecciones presidenciales de 2025 en {municipality}"""
