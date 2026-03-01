import os
import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from agent.models import ChatMessage, ChatRequest, ChatResponse

from dotenv import load_dotenv
load_dotenv()
class ChatService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.max_history = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))
        
        # Memoria de conversaciones en memoria (por sesión)
        self.conversations: Dict[str, List[ChatMessage]] = {}
        
        # Sistema prompt para el trainer
        self.system_prompt = """
        Eres un entrenador personal especializado en deportes llamado "Coach AI".
        
        Características:
        - Experto en running, cycling, strength training, y swimming
        - Motivador y positivo, pero realista
        - Das consejos personalizados basados en datos del usuario
        - Hablas en español de manera natural y cercana
        - Utilizas emojis ocasionalmente para ser más amigable
        
        Contexto del usuario:
        - Utiliza una aplicación de calendario deportivo
        - Puede tener datos de entrenamientos, actividades y progreso
        - Busca mejorar su rendimiento deportivo
        
        Instrucciones:
        - Responde de manera concisa pero útil
        - Si no tienes información específica, pide más detalles
        - Sugiere planes de entrenamiento realistas
        - Motiva al usuario a mantener constancia
        """

    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """Obtiene una sesión existente o crea una nueva"""
        if not session_id or session_id not in self.conversations:
            session_id = str(uuid.uuid4())
            self.conversations[session_id] = []
            
            # Añadir el prompt del sistema al inicio
            system_message = ChatMessage(
                role="system",
                content=self.system_prompt,
                timestamp=datetime.now()
            )
            self.conversations[session_id].append(system_message)
        
        return session_id

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Añade un mensaje a la conversación"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now()
        )
        
        self.conversations[session_id].append(message)
        
        # Limitar el historial (mantener siempre el system prompt)
        if len(self.conversations[session_id]) > self.max_history + 1:
            # Mantener el primer mensaje (system) y los últimos N mensajes
            system_msg = self.conversations[session_id][0]
            recent_messages = self.conversations[session_id][-(self.max_history-1):]
            self.conversations[session_id] = [system_msg] + recent_messages

    def build_context_prompt(self, context: Dict) -> str:
        """Construye un prompt con contexto del usuario"""
        context_parts = []
        
        if context.get("recent_workouts"):
            context_parts.append(f"Entrenamientos recientes: {context['recent_workouts']}")
        
        if context.get("current_goals"):
            context_parts.append(f"Objetivos actuales: {context['current_goals']}")
        
        if context.get("user_stats"):
            context_parts.append(f"Estadísticas: {context['user_stats']}")
        
        if context.get("current_week_plan"):
            context_parts.append(f"Plan de la semana: {context['current_week_plan']}")
        
        return "\n".join(context_parts) if context_parts else ""

    async def send_message(self, request: ChatRequest) -> ChatResponse:
        """Envía un mensaje al modelo y obtiene respuesta"""
        
        # Obtener o crear sesión
        session_id = self.get_or_create_session(request.session_id)
        
        # Construir contexto si se proporciona
        user_message = request.message
        if request.context:
            context_info = self.build_context_prompt(request.context)
            if context_info:
                user_message = f"{context_info}\n\nPregunta del usuario: {request.message}"
        
        # Añadir mensaje del usuario
        self.add_message(session_id, "user", user_message)
        
        try:
            # Preparar mensajes para OpenAI
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in self.conversations[session_id]
            ]
            
            # Llamada a OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=0.7,
                # max_tokens=500,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            assistant_response = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else None
            
            # Añadir respuesta del asistente
            self.add_message(session_id, "assistant", assistant_response)
            
            return ChatResponse(
                response=assistant_response,
                session_id=session_id,
                timestamp=datetime.now(),
                tokens_used=tokens_used,
                model_used=self.model
            )
            
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            # Respuesta de fallback
            fallback_response = "Lo siento, hay un problema técnico en este momento. ¿Puedes intentar de nuevo? 🤖"
            
            self.add_message(session_id, "assistant", fallback_response)
            
            return ChatResponse(
                response=fallback_response,
                session_id=session_id,
                timestamp=datetime.now(),
                model_used=self.model
            )

    def get_conversation_history(self, session_id: str) -> List[ChatMessage]:
        """Obtiene el historial de conversación"""
        return self.conversations.get(session_id, [])

    def clear_session(self, session_id: str) -> bool:
        """Limpia una sesión específica"""
        if session_id in self.conversations:
            del self.conversations[session_id]
            return True
        return False

# Instancia global del servicio
chat_service = ChatService()