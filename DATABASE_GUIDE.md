# Guía de Base de Datos - Garmin Planner

## Resumen de la Implementación

Se ha implementado una **base de datos SQLite local** completa para Garmin Planner v2.0 con las siguientes características:

### ✅ Componentes Implementados

1. **Modelos de Base de Datos** (`database/models.py`)
   - `User`: Usuarios y configuración
   - `Workout`: Entrenamientos programados
   - `Activity`: Actividades completadas
   - `Statistics`: Estadísticas pre-calculadas

2. **Servicio de Base de Datos** (`database/database.py`)
   - Conexión a SQLite
   - Gestión de sesiones
   - Inicialización automática

3. **Operaciones CRUD** (`database/crud.py`)
   - Funciones para crear, leer, actualizar y eliminar datos
   - Consultas optimizadas con filtros
   - Cálculo automático de estadísticas

4. **Servicio de Sincronización** (`database/sync_service.py`)
   - Sincronización de actividades desde Garmin Connect
   - Sincronización de workouts
   - Parseo automático de datos de Garmin
   - Actualización de estadísticas

5. **API REST Endpoints** (`api/db_endpoints.py`)
   - 15+ endpoints para gestión completa
   - Sincronización bajo demanda
   - Consulta de datos locales
   - Dashboard con resumen

6. **Herramientas CLI** (`scripts/`)
   - `init_db.py`: Inicialización y migración de datos históricos
   - `db_tools.py`: Gestión y consulta de la BD

## Inicio Rápido

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

Nuevas dependencias añadidas:
- `sqlalchemy>=2.0.0` - ORM para base de datos
- `alembic>=1.12.0` - Migraciones (futuro uso)

### 2. Inicializar Base de Datos

```bash
# Opción 1: Inicializar e importar datos históricos (6 meses)
python scripts/init_db.py --months 6

# Opción 2: Solo crear las tablas
python scripts/init_db.py --init-only

# Ver resumen
python scripts/init_db.py --summary
```

### 3. Iniciar el Servidor API

```bash
python run_api.py
```

La base de datos se inicializa automáticamente al arrancar el servidor.

## Ejemplos de Uso

### API - Sincronización

Sincronizar actividades del calendario visible (ej: última semana):

```bash
curl -X POST "http://localhost:8000/db/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tu_email@example.com",
    "password": "tu_contraseña",
    "start_date": "2025-10-01",
    "end_date": "2025-10-08",
    "sync_details": true
  }'
```

Respuesta:
```json
{
  "success": true,
  "new_activities": 12,
  "updated_activities": 0,
  "new_workouts": 3,
  "updated_workouts": 0,
  "sync_date": "2025-10-08T10:30:00",
  "message": "Synced 12 activities and 3 workouts"
}
```

### API - Consultar Actividades

```bash
# Todas las actividades de running de la última semana
curl "http://localhost:8000/db/users/tu_email@example.com/activities?sport_type=running&start_date=2025-10-01&limit=20"

# Detalles de una actividad específica
curl "http://localhost:8000/db/users/tu_email@example.com/activities/123"
```

### API - Crear Workout

```bash
curl -X POST "http://localhost:8000/db/users/tu_email@example.com/workouts?upload_to_garmin=true" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "run_interval_vo2max",
    "sport_type": "running",
    "structure": {
      "steps": [
        {"warmup": "2000m @H(z2)"},
        {"repeat": 6, "steps": [
          {"run": "800m @P(3:35-3:45)"},
          {"recovery": "400m"}
        ]},
        {"cooldown": "2000m @H(z2)"}
      ]
    },
    "scheduled_date": "2025-10-15T08:00:00",
    "description": "6x800m VO2 max intervals"
  }' \
  --data-urlencode "garmin_password=tu_contraseña"
```

### API - Dashboard

Obtener resumen completo (últimos 30 días):

```bash
curl "http://localhost:8000/db/users/tu_email@example.com/dashboard?days=30"
```

Respuesta incluye:
- Total de actividades
- Resumen por deporte (running, cycling)
- 10 actividades más recientes
- Estadísticas semanales

### API - Estadísticas

```bash
# Ver estadísticas semanales de running
curl "http://localhost:8000/db/users/tu_email@example.com/statistics?period_type=weekly&sport_type=running"

# Calcular estadísticas para un período
curl -X POST "http://localhost:8000/db/users/tu_email@example.com/statistics/calculate?period_type=weekly&start_date=2025-09-01&end_date=2025-10-08"
```

### CLI - Herramientas de BD

```bash
# Ver todos los usuarios
python scripts/db_tools.py list-users

# Ver actividades recientes
python scripts/db_tools.py list-activities tu_email@example.com --limit 20

# Ver workouts
python scripts/db_tools.py list-workouts tu_email@example.com

# Estadísticas semanales de running
python scripts/db_tools.py show-stats tu_email@example.com --period weekly --sport running

# Calcular estadísticas de los últimos 90 días
python scripts/db_tools.py calc-stats tu_email@example.com --days 90
```

## Flujo de Trabajo Frontend → Backend

### 1. Usuario abre el calendario (ej: semana del 1-7 Oct)

**Frontend:**
```javascript
// Cargar datos de la semana desde BD
const response = await fetch(
  `/db/users/${userEmail}/activities?start_date=2025-10-01&end_date=2025-10-07`
);
const activities = await response.json();

// Cargar workouts programados
const workoutsResponse = await fetch(
  `/db/users/${userEmail}/workouts?start_date=2025-10-01&end_date=2025-10-07&status=scheduled`
);
const workouts = await workoutsResponse.json();

// Mostrar en calendario
displayCalendar(activities, workouts);
```

### 2. Usuario hace click en "Sincronizar"

**Frontend:**
```javascript
async function syncData() {
  const startDate = getCalendarStartDate(); // Ej: 2025-10-01
  const endDate = getCalendarEndDate();     // Ej: 2025-10-07

  const response = await fetch('/db/sync', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      email: userEmail,
      password: userPassword, // Mejor: usar token guardado
      start_date: startDate,
      end_date: endDate,
      sync_details: false // true para splits/zonas
    })
  });

  const result = await response.json();

  if (result.success) {
    showNotification(`Sincronizados ${result.new_activities} entrenamientos`);
    reloadCalendar(); // Recargar datos desde BD
  }
}
```

### 3. Usuario crea un nuevo workout

**Frontend:**
```javascript
async function createWorkout(workoutData) {
  const response = await fetch(
    `/db/users/${userEmail}/workouts?upload_to_garmin=true`,
    {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        name: workoutData.name,
        sport_type: workoutData.sport, // "running" o "cycling"
        structure: workoutData.structure,
        scheduled_date: workoutData.date,
        yaml_content: workoutData.yaml
      })
    }
  );

  const workout = await response.json();

  // workout incluye garmin_workout_id si se subió correctamente
  addWorkoutToCalendar(workout);
}
```

### 4. Usuario ve estadísticas/dashboard

**Frontend:**
```javascript
async function loadDashboard(days = 30) {
  const response = await fetch(
    `/db/users/${userEmail}/dashboard?days=${days}`
  );
  const data = await response.json();

  // data.by_sport contiene totales por deporte
  // data.recent_activities contiene últimas actividades
  // data.statistics contiene stats semanales

  displayCharts(data);
  displayStats(data);
}
```

## Estructura de Datos

### Activity (ejemplo completo)

```json
{
  "id": 123,
  "garmin_activity_id": "12345678901",
  "activity_name": "Morning Run",
  "sport_type": "running",
  "start_time": "2025-10-05T08:30:00",
  "duration_seconds": 3600,
  "distance_meters": 10000,
  "average_pace": 6.0,
  "average_speed": 2.77,
  "average_heart_rate": 145,
  "max_heart_rate": 168,
  "average_cadence": 168,
  "elevation_gain": 125.5,
  "elevation_loss": 118.2,
  "calories": 650,
  "aerobic_training_effect": 3.2,
  "anaerobic_training_effect": 1.8,
  "splits": [...],
  "laps": [...],
  "heart_rate_zones": {...},
  "weather_data": {...}
}
```

### Workout (ejemplo completo)

```json
{
  "id": 45,
  "name": "run_interval_vo2max",
  "sport_type": "running",
  "garmin_workout_id": "987654321",
  "scheduled_date": "2025-10-10T08:00:00",
  "status": "scheduled",
  "structure": {
    "steps": [...]
  },
  "created_at": "2025-10-01T10:00:00",
  "updated_at": "2025-10-01T10:00:00"
}
```

### Statistics (ejemplo completo)

```json
{
  "period_type": "weekly",
  "period_start": "2025-10-01T00:00:00",
  "period_end": "2025-10-07T23:59:59",
  "sport_type": "running",
  "total_activities": 4,
  "total_distance_meters": 42000,
  "total_duration_seconds": 14400,
  "total_elevation_gain": 520,
  "total_calories": 2800,
  "avg_pace": 5.71,
  "avg_heart_rate": 142,
  "best_pace": 4.52,
  "best_distance": 15000,
  "longest_duration_seconds": 5400,
  "avg_aerobic_effect": 3.1,
  "avg_anaerobic_effect": 1.5
}
```

## Optimizaciones y Mejores Prácticas

### 1. Sincronización Eficiente

- Solo sincronizar el rango de fechas visible en el calendario
- Usar `sync_details=false` para sincronizaciones rápidas
- Sincronizar detalles solo cuando el usuario abre una actividad específica

### 2. Caching en Frontend

```javascript
// Cachear datos por 5 minutos
const cache = new Map();
const CACHE_TTL = 5 * 60 * 1000;

async function getActivities(startDate, endDate) {
  const cacheKey = `${startDate}-${endDate}`;
  const cached = cache.get(cacheKey);

  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  const data = await fetchActivities(startDate, endDate);
  cache.set(cacheKey, {data, timestamp: Date.now()});
  return data;
}
```

### 3. Estadísticas Pre-calculadas

En lugar de calcular estadísticas on-demand, usar las pre-calculadas:

```javascript
// ✅ Bueno: Usar estadísticas pre-calculadas
const stats = await fetch('/db/users/email/statistics?period_type=weekly');

// ❌ Evitar: Cargar todas las actividades y calcular en frontend
const activities = await fetch('/db/users/email/activities?limit=1000');
const stats = calculateStats(activities); // Lento
```

### 4. Paginación para Listados

```javascript
// Cargar actividades en páginas de 20
let offset = 0;
const limit = 20;

async function loadMoreActivities() {
  const activities = await fetch(
    `/db/users/email/activities?limit=${limit}&offset=${offset}`
  );
  offset += limit;
  appendActivities(activities);
}
```

## Troubleshooting

### La base de datos no se crea

```bash
# Verificar que la carpeta data/ existe
mkdir -p garmin_planner/data

# Inicializar manualmente
python -c "from database import init_db; init_db()"
```

### Actividades duplicadas

Las actividades se identifican por `garmin_activity_id` (único). No se crean duplicados.

### Sincronización lenta

- Reduce el rango de fechas
- Usa `sync_details=false`
- Sincroniza detalles solo cuando sea necesario

### Error de importación de módulos

```bash
# Asegúrate de estar en el directorio correcto
cd garmin_planner

# Verifica que database/ es accesible
python -c "from database import Database; print('OK')"
```

## Próximos Pasos

1. **Implementar Frontend**: Usar los endpoints `/db/*` para el calendario web
2. **Gráficos**: Usar `chart_data` de Statistics para visualizaciones
3. **Autenticación**: Implementar JWT para no enviar password en cada request
4. **Webhooks**: Sincronización automática cuando Garmin notifica nuevas actividades
5. **Export/Import**: Funcionalidad para backup de la BD

---

**Base de datos ubicada en**: `garmin_planner/data/garmin_planner.db`

Para cualquier duda, consulta [README.md](README.md) o el código fuente en `database/`.
