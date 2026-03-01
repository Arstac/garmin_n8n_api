from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from garminconnect import Garmin, GarminConnectAuthenticationError
import os
import sys
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import uvicorn
from datetime import date, datetime, timezone
from fastapi.middleware.cors import CORSMiddleware
import yaml
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from garmin_planner.client import Client
from garmin_planner.main import importWorkouts, scheduleWorkouts, replace_variables
from garmin_planner.__init__ import logger

from agent.models import ChatRequest, ChatResponse
from agent.chat_service import chat_service

# Import database components
from database import init_db
from api.db_endpoints import router as db_router

app = FastAPI(
    title="Garmin Planner API",
    description="API REST para gestionar entrenamientos en Garmin Connect con base de datos local",
    version="2.0.0"
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup"""
    init_db()
    logger.info("Database initialized successfully")

# Include database endpoints
app.include_router(db_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # o ["*"] para desarrollo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProcessYamlRequest(BaseModel):
    yaml_content: str
    email: str
    password: str
    delete_same_name_workout: bool = False



@app.get("/")
async def root():
    return {"message": "Athletes Calendar API - Running! 🏃‍♂️"}

@app.post("/chat", response_model=ChatResponse)
async def chat_with_trainer(request: ChatRequest):
    """
    Endpoint para chatear con el entrenador AI
    
    - **message**: Mensaje del usuario
    - **context**: Contexto opcional (entrenamientos, stats, etc.)
    - **session_id**: ID de sesión para mantener conversación
    """
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
        
        response = await chat_service.send_message(request)
        return response
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@app.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Obtiene el historial de una conversación"""
    history = chat_service.get_conversation_history(session_id)
    
    # Filtrar el mensaje del sistema para el frontend
    user_history = [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp
        }
        for msg in history if msg.role != "system"
    ]
    
    return {"session_id": session_id, "history": user_history}

@app.delete("/chat/session/{session_id}")
async def clear_chat_session(session_id: str):
    """Limpia una sesión de chat específica"""
    success = chat_service.clear_session(session_id)
    if success:
        return {"message": f"Sesión {session_id} eliminada exitosamente"}
    else:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

@app.get("/chat/sessions")
async def list_active_sessions():
    """Lista las sesiones activas"""
    sessions = list(chat_service.conversations.keys())
    return {"active_sessions": sessions, "count": len(sessions)}


@app.post("/process-yaml")
async def process_yaml(request: ProcessYamlRequest):
    try:
        # Parse YAML content
        data: Dict[str, Any] = yaml.safe_load(request.yaml_content)
        
        # Initialize Garmin client
        garmin_client = Client(request.email, request.password)
        
        # Settings
        settings = {"deleteSameNameWorkout": request.delete_same_name_workout}
        
        # Replace definitions if present
        if "definitions" in data:
            definitions_dict = data['definitions']
            data = replace_variables(data, definitions_dict) # type: ignore
        
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
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            workouts = schedule_plan['workouts']
            start_date_dt = datetime.combine(start_date, datetime.min.time())
            scheduleWorkouts(start_date_dt, workouts, garmin_client)
        
        return {"message": "YAML processed and workouts sent to Garmin successfully"}
    
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing YAML: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Modelo para credenciales
class Credentials(BaseModel):
    email: str
    password: str

# Instancia global de Garmin (en producción usar una base de datos o cache)
garmin_client: Optional[Garmin] = None

# Seguridad básica (en producción usar JWT o similar)
security = HTTPBasic()

def get_garmin_client() -> Garmin:
    """Obtener el cliente Garmin autenticado"""
    global garmin_client
    if garmin_client is None:
        raise HTTPException(status_code=401, detail="No autenticado. Use /login primero")
    return garmin_client

@app.post("/login")
async def login(credentials: Credentials):
    """
    Autenticar con Garmin Connect
    Request: POST /login
    Body (JSON): {"email": str, "password": str}
    Response: {"message": str}
    """
    global garmin_client
    try:
        garmin_client = Garmin(credentials.email, credentials.password)
        garmin_client.login()
        return {"message": "Autenticación exitosa"}
    except GarminConnectAuthenticationError as e:
        raise HTTPException(status_code=401, detail=f"Error de autenticación: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoint para obtener actividades y workouts del mes
@app.get("/calendar/{year}/{month}")
async def get_calendar_month(year: int, month: int, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener actividades y workouts del mes completo
    Request: GET /calendar/{year}/{month}
    Response: JSON con actividades y workouts del mes
    """
    try:
        url = f"calendar-service/year/{year}/month/{month}"
        data = client.download(url)
        # Si la respuesta es bytes, intentar decodificar y cargar como JSON
        import json
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except Exception:
                data = data.decode("latin-1")
            try:
                return json.loads(data)
            except Exception:
                return {"raw": data}
        # Si es string, intentar cargar como JSON
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return {"raw": data}
        # Si ya es dict/list, devolver tal cual
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo calendario: {str(e)}")
    
    
@app.get("/profile")
async def get_profile(client: Garmin = Depends(get_garmin_client)):
    """
    Obtener perfil del usuario
    Request: GET /profile
    Response: JSON con los datos del perfil
    """
    try:
        profile = client.get_user_profile()
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo perfil: {str(e)}")

@app.get("/activities")
async def get_activities(limit: int = 10, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener actividades recientes
    Request: GET /activities?limit=10
    Response: Lista de actividades recientes
    """
    try:
        activities = client.get_activities(0, limit)
        return activities
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo actividades: {str(e)}")

@app.get("/stats")
async def get_stats(client: Garmin = Depends(get_garmin_client)):
    """
    Obtener estadísticas diarias
    Request: GET /stats
    Response: JSON con estadísticas del día
    """
    try:
        today = datetime.now(timezone.utc).date().strftime("%Y-%m-%d")
        stats = client.get_stats(today)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")

@app.get("/health")
async def get_health_data(client: Garmin = Depends(get_garmin_client)):
    """
    Obtener datos de salud del día
    Request: GET /health
    Response: {"heart_rate": ..., "steps": ...}
    """
    try:
        today = datetime.now(timezone.utc).date().strftime("%Y-%m-%d")
        heart_rate = client.get_heart_rates(today)
        steps = client.get_steps_data(today)
        return {
            "heart_rate": heart_rate,
            "steps": steps
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo datos de salud: {str(e)}")


# ENDPOINTS DE WORKOUTS
@app.get("/workouts")
async def get_workouts(limit: int = 10, start: int = 0, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener lista de workouts programados
    Request: GET /workouts?start=1&limit=999
    Response: Lista de workouts
    """
    try:
        workouts = client.get_workouts(start=start, limit=limit)
        return workouts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo workouts: {str(e)}")

@app.get("/workouts/{workout_id}")
async def get_workout_detail(workout_id: int, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener detalle de un workout por ID
    Request: GET /workouts/{workout_id}
    Response: JSON con el detalle del workout
    """
    try:
        workout = client.get_workout_by_id(workout_id)
        return workout
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo workout: {str(e)}")


# ENDPOINTS ADICIONALES PARA ACTIVIDADES DETALLADAS
@app.get("/activities/{activity_id}")
async def get_activity(activity_id: str, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener actividad por ID
    Request: GET /activities/{activity_id}
    Response: JSON con los datos de la actividad
    """
    try:
        activity = client.get_activity(activity_id)
        return activity
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo actividad: {str(e)}")

@app.get("/activities/{activity_id}/details")
async def get_activity_details(activity_id: str, maxchart: int = 2000, maxpoly: int = 4000, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener detalles completos de una actividad
    Request: GET /activities/{activity_id}/details?maxchart=2000&maxpoly=4000
    Response: JSON con detalles completos de la actividad
    """
    try:
        details = client.get_activity_details(activity_id, maxchart, maxpoly)
        return details
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo detalles de actividad: {str(e)}")

@app.get("/activities/{activity_id}/splits")
async def get_activity_splits(activity_id: str, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener splits de una actividad
    Request: GET /activities/{activity_id}/splits
    Response: JSON con los splits de la actividad
    """
    try:
        splits = client.get_activity_splits(activity_id)
        return splits
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo splits: {str(e)}")

@app.get("/activities/{activity_id}/weather")
async def get_activity_weather(activity_id: str, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener datos del clima de una actividad
    Request: GET /activities/{activity_id}/weather
    Response: JSON con datos del clima
    """
    try:
        weather = client.get_activity_weather(activity_id)
        return weather
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo clima: {str(e)}")

@app.get("/activities/date-range")
async def get_activities_by_date(startdate: str, enddate: Optional[str] = None, activitytype: Optional[str] = None, sortorder: Optional[str] = None, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener actividades por rango de fechas
    Request: GET /activities/date-range?startdate=2025-01-01&enddate=2025-01-31&activitytype=running&sortorder=desc
    Response: Lista de actividades en el rango
    """
    try:
        activities = client.get_activities_by_date(startdate, enddate, activitytype, sortorder)
        return activities
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo actividades por fecha: {str(e)}")

# ENDPOINTS ADICIONALES PARA GOALS, GEAR Y ENTRENAMIENTO
@app.get("/goals")
async def get_goals(status: str = "active", start: int = 1, limit: int = 30, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener goals del usuario
    Request: GET /goals?status=active&start=1&limit=30
    Response: Lista de goals
    """
    try:
        goals = client.get_goals(status, start, limit)
        return goals
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo goals: {str(e)}")

@app.get("/gear")
async def get_gear(client: Garmin = Depends(get_garmin_client)):
    """
    Obtener gear del usuario
    Request: GET /gear
    Response: JSON con el gear del usuario
    """
    try:
        profile = client.get_user_profile()
        user_profile_number = profile.get("userProfileId")
        if not user_profile_number:
            raise HTTPException(status_code=400, detail="No se pudo obtener el userProfileId")
        gear = client.get_gear(str(user_profile_number))
        return gear
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo gear: {str(e)}")

@app.get("/sleep")
async def get_sleep_data(cdate: Optional[str] = None, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener datos de sueño
    Request: GET /sleep?cdate=2025-09-14
    Response: JSON con datos de sueño
    """
    try:
        if cdate is None:
            cdate = datetime.now(timezone.utc).date().strftime("%Y-%m-%d")
        sleep = client.get_sleep_data(cdate)
        return sleep
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo datos de sueño: {str(e)}")

@app.get("/training/readiness")
async def get_training_readiness(cdate: Optional[str] = None, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener training readiness
    Request: GET /training/readiness?cdate=2025-09-14
    Response: JSON con training readiness
    """
    try:
        if cdate is None:
            cdate = datetime.now(timezone.utc).date().strftime("%Y-%m-%d")
        readiness = client.get_training_readiness(cdate)
        return readiness
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo training readiness: {str(e)}")

@app.get("/training/status")
async def get_training_status(cdate: Optional[str] = None, client: Garmin = Depends(get_garmin_client)):
    """
    Obtener training status
    Request: GET /training/status?cdate=2025-09-14
    Response: JSON con training status
    """
    try:
        if cdate is None:
            cdate = datetime.now(timezone.utc).date().strftime("%Y-%m-%d")
        status = client.get_training_status(cdate)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo training status: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
