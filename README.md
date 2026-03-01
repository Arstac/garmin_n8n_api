# Garmin Planner

Una aplicación completa para automatizar la creación y programación de entrenamientos en Garmin Connect, con API REST y asistente de entrenamiento basado en IA.

## Descripción

Garmin Planner elimina la necesidad de gestionar manualmente los entrenamientos en Garmin Connect, permitiendo crear y programar sesiones completas mediante archivos YAML o a través de una API REST. Ideal para atletas que siguen planes de entrenamiento estructurados para running y ciclismo.

## Motivación

Los usuarios de Garmin saben lo tedioso que es crear y gestionar entrenamientos en Garmin Connect, especialmente cuando sigues un plan estructurado de maratón o triatlón. Garmin Planner simplifica este proceso, permitiéndote alcanzar tus objetivos sin perder tiempo en configuraciones manuales.

## Características

### Core
- **Creación automática de entrenamientos**: Crea entrenamientos complejos (intervalos, tempo, rodajes) con calentamientos, series y enfriamientos
- **Programación masiva**: Programa múltiples entrenamientos en tu calendario de Garmin Connect de una sola vez
- **Soporte multi-deporte**: Compatible con running y ciclismo
- **Gestión inteligente**: Elimina automáticamente entrenamientos duplicados si se configuran

### API REST
- **Endpoints completos**: Acceso a calendario, actividades, estadísticas, workouts, perfil y datos de salud
- **Procesamiento de YAML**: Envía planes de entrenamiento vía API
- **Autenticación segura**: Login con credenciales de Garmin Connect

### Asistente IA
- **Chat con entrenador virtual**: Asistente especializado en deportes basado en OpenAI
- **Generación de planes**: Crea planes de entrenamiento personalizados en formato YAML
- **Conversaciones persistentes**: Mantiene el contexto de la conversación por sesión
- **Contexto inteligente**: Integra datos de entrenamientos y estadísticas en las respuestas

## Estructura del archivo YAML

El archivo YAML de configuración incluye las siguientes secciones:

### 1. Credenciales (para uso CLI)
```yaml
email: "tu_email@example.com"
password: "tu_contraseña"
```
**Nota**: Al usar la API REST, las credenciales se envían en el request, no en el YAML.

### 2. Configuración
```yaml
settings:
  deleteSameNameWorkout: true  # Elimina entrenamientos con el mismo nombre antes de crear
```

### 3. Definiciones (opcional)
Define variables reutilizables para ritmos, potencias y zonas:
```yaml
definitions:
  GA: 5:05-5:25           # Ritmo de aeróbico general
  Threshold: 4:25-4:40    # Ritmo de umbral
  VO2MaxP: 3:35-3:45     # Ritmo de VO2 max
  W1: 140-150            # Rango de potencia 1
  W2: 150-160            # Rango de potencia 2
```

### 4. Entrenamientos
Define los entrenamientos separados por deporte:

#### Running
```yaml
run-workouts:
  run_interval_vo2max:
    - warmup: 2000m @H(z2)
    - repeat(6):
      - run: 800m @P($VO2MaxP)
      - recovery: 400m
    - cooldown: 2000m @H(z2)
```

#### Ciclismo
```yaml
bike-workouts:
  bike_interval_vo2max:
    - warmup: 15min @H(z2)
    - repeat(8):
      - bike: 30sec @W(z5)
      - recovery: 2min
    - cooldown: 15min @H(z2)
```

### 5. Planificación (opcional)
Programa los entrenamientos en fechas específicas:
```yaml
schedulePlan:
  start_from: 2025-10-10
  workouts:
    - run_interval_vo2max
    - run_e_16k
    - bike_e_14k
```
**Nota**: Si un entrenamiento no existe en Garmin Connect, se omite ese día. 

## Sintaxis de entrenamientos

### Tipos de paso
- `warmup`: Calentamiento
- `cooldown`: Enfriamiento
- `run`: Carrera a pie
- `bike`: Ciclismo
- `recovery`: Recuperación
- `repeat(n)`: Repetir n veces los pasos internos

### Duraciones
- **Tiempo**: `30sec`, `15min`
- **Distancia**: `400m`, `2000m`, `12000m`
- **Manual**: `lap` (presionar botón de vuelta)

### Objetivos
- **Ritmo**: `@P(4:30-4:50)` o `@P($GA)` → ritmo min/km
- **Frecuencia cardíaca**: `@H(z2)` → zona cardíaca (z1 a z5)
- **Potencia**: `@W(140-160)` o `@W(z3)` → watts o zona de potencia
- **Cadencia**: `@C(90)` → rpm

### Ejemplo completo
```yaml
email: "example@gmail.com"
password: "password"

settings:
  deleteSameNameWorkout: true

definitions:
  GA: 5:05-5:25
  VO2MaxP: 3:35-3:45

run-workouts:
  run_interval_vo2max:
    - warmup: 2000m @H(z2)
    - repeat(6):
      - run: 800m @P($VO2MaxP)
      - recovery: 400m
    - cooldown: 2000m @H(z2)
  run_e_10k:
    - warmup: 2000m @H(z2)
    - run: 7000m @P($GA)
    - cooldown: 2000m @H(z2)

bike-workouts:
  bike_e_60min:
    - warmup: 10min @W(z2)
    - bike: 40min @W(z2)
    - cooldown: 10min @W(z1)

schedulePlan:
  start_from: 2025-10-10
  workouts:
    - run_interval_vo2max
    - run_e_10k
    - bike_e_60min
```

## Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/yeekang-0311/garmin_planner.git
cd garmin_planner
```

### 2. Crear entorno virtual (recomendado)
```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crea un archivo `.env` en la raíz del proyecto para el asistente IA (opcional):
```env
OPENAI_API_KEY=tu_api_key_de_openai
OPENAI_MODEL=gpt-4o-mini
MAX_CONVERSATION_HISTORY=20
```

### 5. Configurar credenciales de Garmin
Crea el archivo `garmin_planner/secrets.yaml`:
```yaml
email: "tu_email@example.com"
password: "tu_contraseña"
```

## Uso

### Modo CLI - Procesamiento de archivos YAML

Ejecuta el programa con un archivo YAML de configuración:

```bash
python -m garmin_planner sampleInput.yaml
```

El programa:
1. Lee el archivo YAML
2. Se conecta a Garmin Connect
3. Crea los entrenamientos definidos
4. Los programa en las fechas especificadas (si hay `schedulePlan`)

### Modo API - Servidor REST

Inicia el servidor API:

```bash
python run_api.py
```

El servidor estará disponible en `http://localhost:8000`

#### Documentación interactiva
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API REST - Endpoints

### Autenticación
```bash
POST /login
Body: {"email": "tu_email@example.com", "password": "tu_contraseña"}
```

### Procesamiento de YAML
```bash
POST /process-yaml
Body: {
  "yaml_content": "...",
  "email": "tu_email@example.com",
  "password": "tu_contraseña",
  "delete_same_name_workout": true
}
```

### Calendario y Actividades
- `GET /calendar/{year}/{month}` - Obtener calendario mensual
- `GET /activities?limit=10` - Actividades recientes
- `GET /activities/{activity_id}` - Detalles de una actividad
- `GET /activities/{activity_id}/splits` - Splits de una actividad
- `GET /activities/date-range?startdate=2025-01-01&enddate=2025-01-31` - Actividades por rango

### Entrenamientos
- `GET /workouts?start=1&limit=999` - Lista de workouts
- `GET /workouts/{workout_id}` - Detalle de un workout

### Datos del Usuario
- `GET /profile` - Perfil del usuario
- `GET /stats` - Estadísticas del día
- `GET /health` - Datos de salud (FC, pasos)
- `GET /sleep?cdate=2025-09-14` - Datos de sueño
- `GET /training/readiness` - Estado de preparación
- `GET /training/status` - Estado de entrenamiento
- `GET /goals?status=active` - Objetivos activos
- `GET /gear` - Equipamiento del usuario

### Chat con Entrenador IA
```bash
POST /chat
Body: {
  "message": "Crea un plan de 4 semanas para correr un maratón",
  "context": {
    "recent_workouts": "...",
    "current_goals": "..."
  },
  "session_id": "optional-session-id"
}
```

- `GET /chat/history/{session_id}` - Historial de conversación
- `DELETE /chat/session/{session_id}` - Limpiar sesión
- `GET /chat/sessions` - Sesiones activas

### Ejemplo de uso con curl

#### Login
```bash
curl -X POST "http://localhost:8000/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"tu_email@example.com","password":"tu_contraseña"}'
```

#### Procesar YAML
```bash
curl -X POST "http://localhost:8000/process-yaml" \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": "settings:\n  deleteSameNameWorkout: true\nrun-workouts:\n  run_e_10k:\n    - warmup: 2000m @H(z2)\n    - run: 7000m @P(5:00-5:20)\n    - cooldown: 2000m @H(z2)",
    "email": "tu_email@example.com",
    "password": "tu_contraseña",
    "delete_same_name_workout": true
  }'
```

#### Chat con entrenador
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Necesito un plan de 4 días para mejorar mi VO2 max",
    "context": {}
  }'
```

## Asistente de Entrenamiento IA

El asistente utiliza OpenAI para generar planes de entrenamiento personalizados. Características:

- **Especializado en deportes**: Experto en running, ciclismo y entrenamiento de fuerza
- **Genera YAML válido**: Crea archivos YAML listos para usar con Garmin Planner
- **Conversacional**: Mantiene el contexto de la conversación
- **Motivador**: Proporciona consejos personalizados y realistas

### Ejemplo de conversación

**Usuario**: "Quiero preparar una media maratón en 8 semanas, 4 días por semana"

**Asistente**: Genera un plan completo en YAML con:
- Entrenamientos de base aeróbica
- Sesiones de tempo y umbral
- Intervalos de VO2 max
- Rodajes largos progresivos
- Planificación semanal

## Arquitectura del Proyecto

```
garmin_planner/
├── api/
│   └── api.py                 # FastAPI REST endpoints
├── agent/
│   ├── chat_service.py        # Servicio de chat con OpenAI
│   └── models.py              # Modelos Pydantic para chat
├── garmin_planner/
│   ├── client.py              # Cliente de Garmin Connect (garth)
│   ├── constant.py            # Constantes y enums
│   ├── main.py                # Lógica principal CLI
│   ├── parser.py              # Parser de YAML y sintaxis
│   ├── model/
│   │   └── workoutModel.py    # Modelos de workout
│   ├── sampleInput.yaml       # Ejemplo de configuración
│   └── secrets.yaml           # Credenciales (no incluir en git)
├── run_api.py                 # Punto de entrada del servidor
├── requirements.txt           # Dependencias Python
└── README.md                  # Este archivo
```

## Dependencias Principales

- **garth**: Cliente no oficial de Garmin Connect
- **garminconnect**: Librería alternativa de Garmin
- **FastAPI**: Framework web para la API REST
- **Uvicorn**: Servidor ASGI
- **OpenAI**: API de ChatGPT para el asistente IA
- **Pydantic**: Validación de datos
- **PyYAML**: Parser de archivos YAML

## Seguridad

⚠️ **Importante**:
- No incluyas `secrets.yaml` en el control de versiones
- Añade `secrets.yaml` y `.env` a tu `.gitignore`
- Las credenciales se almacenan localmente en `.garth/` tras el primer login
- Para producción, considera usar variables de entorno en lugar de archivos de secretos

## Solución de Problemas

### Error de autenticación
```
GarminConnectAuthenticationError
```
**Solución**: Verifica que tus credenciales en `secrets.yaml` sean correctas.

### Entrenamientos no se crean
**Solución**: Revisa la sintaxis del YAML. Usa el archivo `sampleInput.yaml` como referencia.

### API devuelve 401
**Solución**: Debes hacer login primero con `POST /login` antes de usar otros endpoints.

### El asistente IA no responde
**Solución**: Verifica que `OPENAI_API_KEY` esté configurada en el archivo `.env`.

## Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/amazing-feature`)
3. Commit tus cambios (`git commit -m 'Add amazing feature'`)
4. Push a la rama (`git push origin feature/amazing-feature`)
5. Abre un Pull Request

## Licencia

Este proyecto es de código abierto. Consulta el archivo LICENSE para más detalles.

## Créditos

- Desarrollador original: [yeekang-0311](https://github.com/yeekang-0311)
- Librería [garth](https://github.com/matin/garth) para conexión con Garmin Connect
- Comunidad de usuarios de Garmin

## Base de Datos Local (SQLite) 🆕

### Características de la Base de Datos

A partir de la versión 2.0, Garmin Planner incluye una **base de datos SQLite local** que almacena:

- **Usuarios**: Configuración personal, zonas, ritmos y preferencias
- **Actividades completadas**: Todas tus carreras y entrenamientos con métricas detalladas
- **Workouts programados**: Entrenamientos planificados y su estado
- **Estadísticas agregadas**: Métricas calculadas por períodos (semanal, mensual)

### Ventajas

✅ **Rendimiento**: Consultas rápidas sin llamadas constantes a Garmin API
✅ **Offline**: Acceso a tus datos sin conexión
✅ **Análisis avanzado**: Estadísticas y gráficos personalizados
✅ **Historial completo**: Mantén todos tus datos históricos localmente

### Inicialización de la Base de Datos

#### Primera vez - Importar datos históricos

```bash
# Importar los últimos 6 meses de datos desde Garmin
python scripts/init_db.py --months 6

# Solo crear las tablas sin importar datos
python scripts/init_db.py --init-only

# Ver resumen de la base de datos
python scripts/init_db.py --summary
```

### Nuevos Endpoints con Base de Datos

Todos los endpoints de base de datos están bajo el prefijo `/db`:

#### Sincronización
```bash
# Sincronizar actividades y workouts desde Garmin
POST /db/sync
Body: {
  "email": "tu_email@example.com",
  "password": "tu_contraseña",
  "start_date": "2025-01-01",
  "end_date": "2025-10-08",
  "sync_details": true
}
```

#### Consulta de Actividades
```bash
# Obtener actividades del usuario desde BD
GET /db/users/{email}/activities?start_date=2025-01-01&end_date=2025-10-08&sport_type=running&limit=50

# Obtener detalles de una actividad específica
GET /db/users/{email}/activities/{activity_id}
```

#### Gestión de Workouts
```bash
# Crear workout (se guarda en BD y opcionalmente se sube a Garmin)
POST /db/users/{email}/workouts?upload_to_garmin=true
Body: {
  "name": "run_interval_vo2max",
  "sport_type": "running",
  "structure": {...},
  "scheduled_date": "2025-10-15"
}

# Listar workouts del usuario
GET /db/users/{email}/workouts?status=planned&start_date=2025-10-01

# Eliminar workout
DELETE /db/users/{email}/workouts/{workout_id}
```

#### Estadísticas
```bash
# Obtener estadísticas calculadas
GET /db/users/{email}/statistics?period_type=weekly&sport_type=running

# Calcular estadísticas para un período
POST /db/users/{email}/statistics/calculate?period_type=weekly&start_date=2025-09-01&end_date=2025-10-08

# Dashboard con resumen completo
GET /db/users/{email}/dashboard?days=30
```

### Flujo de Trabajo Recomendado

1. **Inicialización** (primera vez):
   ```bash
   python scripts/init_db.py --months 6
   ```

2. **Uso diario**:
   - El frontend hace click en "Sincronizar"
   - Se llama a `POST /db/sync` con rango de fechas del calendario visible
   - Nuevas actividades se guardan en BD
   - El frontend lee datos de la BD (no de Garmin API)

3. **Crear nuevo workout**:
   - Se llama a `POST /db/users/{email}/workouts`
   - Se guarda en BD
   - Se sube automáticamente a Garmin Connect
   - Se retorna el workout con `garmin_workout_id`

### Herramientas de Base de Datos

El proyecto incluye utilidades CLI para gestionar la BD:

```bash
# Listar usuarios
python scripts/db_tools.py list-users

# Ver actividades de un usuario
python scripts/db_tools.py list-activities tu_email@example.com --limit 30

# Ver workouts
python scripts/db_tools.py list-workouts tu_email@example.com

# Mostrar estadísticas
python scripts/db_tools.py show-stats tu_email@example.com --period weekly --sport running

# Calcular estadísticas
python scripts/db_tools.py calc-stats tu_email@example.com --days 90

# Eliminar usuario y todos sus datos
python scripts/db_tools.py delete-user tu_email@example.com

# Limpiar toda la base de datos
python scripts/db_tools.py clear-db
```

### Estructura de la Base de Datos

La base de datos incluye 4 tablas principales:

**users**: Información del usuario
- email, display_name, garmin_user_id
- settings (JSON con preferencias)
- last_sync_at

**workouts**: Entrenamientos programados
- name, sport_type, structure (JSON)
- garmin_workout_id, scheduled_date, status
- estimated_duration, estimated_distance

**activities**: Actividades completadas
- garmin_activity_id, activity_name, sport_type
- start_time, duration, distance
- Métricas: pace, heart_rate, cadence, power, elevation
- splits, laps, heart_rate_zones, power_zones (JSON)
- raw_data (JSON completo de Garmin)

**statistics**: Estadísticas pre-calculadas
- period_type (weekly/monthly/yearly)
- Totales: activities, distance, duration, calories
- Promedios: pace, heart_rate, power
- chart_data (JSON para gráficos)

### Ubicación de la Base de Datos

```
garmin_planner/data/garmin_planner.db
```

La carpeta `data/` está en `.gitignore` para no subir datos personales al repositorio.

## Roadmap

- [x] Base de datos SQLite local ✨
- [x] Sincronización con Garmin Connect
- [x] Estadísticas y métricas agregadas
- [ ] Frontend web para gestión visual de entrenamientos
- [ ] Gráficos interactivos de rendimiento
- [ ] Soporte para natación y otros deportes
- [ ] Importación de planes desde TrainingPeaks
- [ ] Notificaciones de entrenamientos próximos
- [ ] Exportación a otros formatos (GPX, TCX)
- [ ] Sistema de autenticación JWT
- [ ] Multi-usuario con roles

## Contacto y Soporte

Si tienes preguntas o problemas:
- Abre un [Issue](https://github.com/yeekang-0311/garmin_planner/issues) en GitHub
- Consulta la documentación de la API en `/docs`

---

**¡Disfruta entrenando con Garmin Planner!** 🏃‍♂️ 🚴‍♀️