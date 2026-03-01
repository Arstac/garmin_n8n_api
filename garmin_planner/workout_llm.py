import os
from typing import TypedDict, Annotated
from pydantic import BaseModel, Field
from typing_extensions import NotRequired
from dotenv import load_dotenv
import yaml
from typing import Dict, Any
import datetime
import sys
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.prompts import ChatPromptTemplate

from garmin_planner.client import Client
from garmin_planner.main import importWorkouts, scheduleWorkouts, replace_variables
from garmin_planner.__init__ import logger
from garmin_planner.parser import *
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))


llm = ChatOpenAI(model="gpt-4o-mini")  # OPENAI_API_KEY se lee de env automáticamente 

class YamlRequest(BaseModel):
    """Request body for generating YAML configuration."""
    username: str = Field(description="The name of the user")
    password: str = Field(description="The password of the user")
    yaml_content: str = Field(description="The content of the YAML file")
    delete_same_name_workout: bool = False
    
class State(TypedDict):
    # Historial de mensajes con reducer (opcional para este caso, pero correcto)
    messages: Annotated[list, add_messages]
    user_input: str
    yaml_content: NotRequired[str]
    username: NotRequired[str]
    password: NotRequired[str]
    delete_same_name_workout: NotRequired[bool]
    
def generar_yaml(state: State):
    """Generates a YAML configuration based on user input."""
    system="""Rol del sistema (colócalo como instrucciones superiores del modelo):

Eres un generador de planes de entrenamiento que devuelve **exclusivamente** un documento **YAML** válido, sin texto adicional, sin comentarios, sin bloques de código markdown. El YAML representa credenciales, ajustes, definiciones reutilizables, entrenamientos (ciclismo y carrera) y, opcionalmente, una planificación en calendario compatible con el planificador de Garmin según este **esquema y reglas**.

## 1) Reglas de formato y salida
- **Salida**: devuelve **solo YAML** (sin explicaciones, sin ```).
- **Indentación**: 2 espacios. No uses tabuladores.
- **Claves válidas de nivel raíz** (en este orden si existen):
  1) `email` (string)
  2) `password` (string)
  3) `settings` (obj)
  4) `definitions` (obj, opcional)
  5) `bike-workouts` (obj, opcional)
  6) `run-workouts` (obj, opcional)
  7) `schedulePlan` (obj, opcional)
- Si el usuario no proporciona credenciales, usa **placeholders**:  
  `email: "tu_email@ejemplo.com"`  
  `password: "tu_contraseña"`
- **No** agregues comentarios `#` en la salida final.
- **No** repitas la misma clave de entrenamiento dos veces.

## 2) Esquema de `settings`
```yaml
settings:
  deleteSameNameWorkout: true|false
```
- Valor por defecto sugerido: `true`.

## 3) Esquema de `definitions` (opcional)
- Mapa clave→valor para reutilizar en objetivos:
  - Ejemplos: ritmos (`GA: 5:05-5:25`), potencia (`W1: 140-150`), etc.
- Referencia en pasos con `$NOMBRE`: `@P($GA)`, `@W($W1)`.

## 4) Esquema de entrenamientos
- Se agrupan por:
  - `bike-workouts`: 
  - `run-workouts`: 
- Cada clave dentro es el **nombre del entrenamiento** (string en snake_case o kebab-case, sin espacios, p.ej. `run_e_10k`, `bike_interval_vo2max`).
- El valor es una **lista ordenada de pasos**.

### 4.1 Tipos de paso soportados
- `warmup`, `cooldown`, `bike`, `run`, `recovery`, `repeat(n)` (bucle).
- Estructura de un paso simple:  
  `- <tipo>: <duración> <objetivo?>`
- Estructura de bucle:  
  ```yaml
  - repeat(n):
    - <paso1>
    - <paso2>
  ```
  donde `n` es entero > 0.

### 4.2 Duraciones válidas
- Tiempo: `Xsec`, `Ymin` (p.ej., `30sec`, `15min`)
- Distancia: `Z m` en metros **sin espacio**: `400m`, `2000m`, `12000m`
- Vuelta manual: `lap`
- **Normaliza** formatos a exactamente estos: `sec`, `min`, `m`, `lap`.

### 4.3 Objetivos válidos (opcionales)
- Ritmo: `@P(mm:ss-mm:ss)` o `@P($VAR)`
- Frecuencia cardiaca: `@H(z1|z2|z3|z4|z5)` o `@H(zN-zM)` o `@H($VAR)`
- Cadencia: `@C(INT)` o `@C($VAR)`  (ej.: `@C(90)`)
- Potencia: `@W(INT-INT)` o `@W(zN)` o `@W($VAR)`  (ej.: `@W(140-150)` o `@W(2)`)
- **Solo uno** de estos objetivos por paso, salvo que el usuario pida explícitamente combinarlos; en ese caso, usa **máximo 2** y en el orden: Potencia/Cadencia/Ritmo/FC.
- Si el usuario especifica “zona” (p.ej., z2), asigna al objetivo correspondiente (`@H(z2)` o `@W(z2)`), según el deporte y la petición.

### 4.4 Validaciones
- `repeat(n)` debe contener **≥1** paso hijo.
- No mezcles `bike` y `run` en el mismo bloque de workout (los tipos están separados por familia).
- `warmup`/`cooldown` no deben estar dentro de `repeat(n)`.
- Todas las duraciones deben cumplir formato válido.
- Los nombres de workout deben ser **únicos** dentro de su familia.
- Si el usuario pide `X` días/semana y `schedulePlan` se incluye, garantiza **un workout por día** con el orden solicitado.

## 5) Planificación (`schedulePlan`, opcional)
```yaml
schedulePlan:
  start_from: YYYY-MM-DD
  workouts:
    - <nombre_entrenamiento_del_dia_1>
    - <nombre_entrenamiento_del_dia_2>
    # ...
```
- `start_from` es fecha ISO (ej.: `2025-10-10`).
- `workouts` es una lista de **nombres** definidos previamente (uno por día, en orden cronológico).
- Si el usuario no aporta fecha, omite `schedulePlan` o usa una fecha razonable **solo si la pide**.

## 6) Interpretación de la petición del usuario
- Extrae: objetivo (p.ej., “sub90 en media maratón”), volumen semanal, días disponibles, preferencias (ritmo/FC/potencia), limitaciones (p.ej., “sin series muy cortas”), deportes (run/bike), periodización (base/tempo/umbral/VO2).
- Si faltan datos esenciales (p.ej., días por semana) y **no** se permite preguntar, asume valores prudentes:
  - Días/semana: 4 (run) o 3 (bike) según el foco mencionado.
  - Volumen por sesión fácil: 40–60 min run o 60–90 min bike.
  - Calienta/enfría: 10–20 min.
- Usa `definitions` para ritmos/zona cuando el usuario proporcione rangos o umbrales; si no, puede quedar vacío.

## 7) Política de nombres
- Usa nombres concisos y descriptivos en **snake_case**:
  - `run_e_10k`, `run_tempo_6x1k`, `bike_sweetspot_3x12min`, `bike_e_60min`.
- Evita acentos y espacios.

## 8) Seguridad
- Si el usuario no facilita credenciales, deja placeholders.
- **Nunca** inventes emails reales ni contraseñas reales.

---

## Ejemplo “few-shot” 1 (petición: carrera, 4 días/semana, objetivo GA + VO2, con calendario)

**Usuario (resumen):**  
Quiero 4 días de running durante 1 semana. Ritmos objetivo: GA 5:05–5:25, VO2 3:35–3:45. Empezar el 2025-10-10. Elimina entrenos con mismo nombre.

**Asistente (solo YAML):**
email: "tu_email@ejemplo.com"
password: "tu_contraseña"
settings:
  deleteSameNameWorkout: true
definitions:
  GA: 5:05-5:25
  VO2: 3:35-3:45
run-workouts:
  run_e_10k:
    - warmup: 15min @H(z2)
    - run: 7000m @P($GA)
    - cooldown: 10min @H(z2)
  run_vo2_6x800:
    - warmup: 2000m @H(z2)
    - repeat(6):
      - run: 800m @P($VO2)
      - recovery: 400m
    - cooldown: 2000m @H(z2)
  run_tempo_20min:
    - warmup: 15min @H(z2)
    - run: 20min @P(4:25-4:40)
    - cooldown: 10min @H(z2)
  run_e_12k:
    - warmup: 15min @H(z2)
    - run: 9000m @P($GA)
    - cooldown: 10min @H(z2)
schedulePlan:
  start_from: 2025-10-10
  workouts:
    - run_vo2_6x800
    - run_e_10k
    - run_tempo_20min
    - run_e_12k

## Ejemplo “few-shot” 2 (petición: ciclismo, 3 días sin calendario, potencia en zonas)
**Usuario (resumen):**  
Quiero 3 sesiones de bici, con trabajo Sweet Spot y VO2. Objetivos por potencia (zonas 2 y 4-5). Sin planificación.

**Asistente (solo YAML):**
email: "tu_email@ejemplo.com"
password: "tu_contraseña"
settings:
  deleteSameNameWorkout: true
definitions:
  W_SS: 240-260
bike-workouts:
  bike_e_60min:
    - warmup: 10min @W(z2)
    - bike: 40min @W(z2)
    - cooldown: 10min @W(z1)
  bike_sweetspot_3x12min:
    - warmup: 15min @W(z2)
    - repeat(3):
      - bike: 12min @W($W_SS)
      - recovery: 5min
    - cooldown: 10min @W(z1)
  bike_vo2_5x3min:
    - warmup: 15min @W(z2)
    - repeat(5):
      - bike: 3min @W(z5)
      - recovery: 3min
    - cooldown: 10min @W(z1)

---

## Plantilla de arranque (si no hay datos, usa placeholders)
- Días/semana: inferir a partir del texto del usuario o usar 4 (run) / 3 (bike).
- Objetivo: GA/Tempo/Umbral/VO2 según palabras clave del usuario.
- Zonas/ritmos: si no se aportan, puedes dejar pasos con `@H(z2)` (fácil) o `@W(z2)` por defecto y evitar definir `definitions`.

**Estructura mínima válida a devolver:**
email: "tu_email@ejemplo.com"
password: "tu_contraseña"
settings:
  deleteSameNameWorkout: true
definitions:
bike-workouts:
run-workouts:

*(Elimina los bloques vacíos si no los usas.)*
    """
    print("probando cargar state[user_input]")
    user_input = state["user_input"]
    
    print(f"User message: {user_input}")
    
    
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", "{user_input}")
        ]
    )
    
    chain = prompt | llm.with_structured_output(YamlRequest)

    response = chain.invoke({"user_input": user_input})
    
    print("---YAML GENERATED---", response)
    
    return {"yaml_content": response.yaml_content, "username": response.username, "password": response.password, "delete_same_name_workout": response.delete_same_name_workout}


def upload_to_garmin(state: State):
    """Uploads the generated YAML to Garmin using provided credentials."""
    if "yaml_content" not in state:
        raise ValueError("YAML content not generated yet.")
    
    yaml_content = state["yaml_content"]
    delete_same_name_workout = state.get("delete_same_name_workout", False)
    print("--------------------------------")
    print("--------------------------------")
    print("Uploading to Garmin with the following YAML content:")
    print(yaml_content)
    print("--------------------------------")
    print("--------------------------------")
    try:
        # Parse YAML content
        data: Dict[str, Any] = yaml.safe_load(yaml_content)
        if data is None:
            raise ValueError("YAML content is empty or invalid")
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"Current directory: {current_dir}")
        # Read garmin_planer/secrets.yaml and get username and password
        secrets = parseYaml(os.path.join(current_dir, "garmin_planner/secrets.yaml"))
        if not secrets:
            logger.error("Failed to parse secrets.yaml")
            sys.exit("Exiting: secrets.yaml not found.")
        if ("email" not in secrets) or ("password" not in secrets):
            logger.error("Missing 'email' or 'password' in YAML input.")
            sys.exit("Exiting: 'email' or 'password' not found.")

        email = secrets['email']
        password = secrets['password']
        # Initialize Garmin client
        garmin_client = Client(email, password)

        # Settings
        settings = {"deleteSameNameWorkout": delete_same_name_workout}
        
        # Replace definitions if present
        if "definitions" in data:
            definitions_dict = data['definitions']
            data = replace_variables(data, definitions_dict)
        
        # Process bike workouts
        if "bike-workouts" in data:
            bike_workouts = data['bike-workouts']
            importWorkouts(
                workouts=bike_workouts,
                toDeletePrevious=settings['deleteSameNameWorkout'],
                conn=garmin_client,
                sport_type="bike"
            )
        
        # Process run workouts
        if "run-workouts" in data:
            run_workouts = data['run-workouts']
            importWorkouts(
                workouts=run_workouts,
                toDeletePrevious=settings['deleteSameNameWorkout'],
                conn=garmin_client,
                sport_type="run"
            )
        
        # Process schedule plan if present
        if "schedulePlan" in data:
            schedule_plan = data['schedulePlan']
            start_date_str = schedule_plan['start_from']
            if isinstance(start_date_str, str):
                try:
                    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD")
            elif isinstance(start_date_str, datetime.date):
                start_date = start_date_str
            else:
                raise ValueError("Invalid date format. Expected string or date object")
            workouts = schedule_plan['workouts']
            start_date_dt = datetime.datetime.combine(start_date, datetime.time())
            scheduleWorkouts(start_date_dt, workouts, garmin_client)
        
        return {"message": "YAML processed and workouts sent to Garmin successfully"}
    
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing YAML: {str(e)}")
        raise ValueError(f"Internal server error: {str(e)}")

graph = StateGraph(State)
graph.add_node("generar_yaml", generar_yaml)
graph.add_node("upload_to_garmin", upload_to_garmin)

graph.add_edge(START, "generar_yaml")
graph.add_edge("generar_yaml", "upload_to_garmin")
graph.add_edge("upload_to_garmin", END)

app = graph.compile()