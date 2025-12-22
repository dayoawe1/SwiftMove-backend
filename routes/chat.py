from fastapi import APIRouter, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from datetime import datetime
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from models import ChatMessage, ChatMessageCreate, ChatSession

router = APIRouter(prefix="/chat", tags=["chat"])

# This will be injected by the main app
db = None

def set_database(database: AsyncIOMotorDatabase):
    global db
    db = database

@router.post("/message", response_model=ChatMessage)
async def send_chat_message(message_data: ChatMessageCreate):
    """Send a message to the chatbot and get a response"""
    try:
        # Import the LLM chat integration
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        # Get API key from environment
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Chatbot service is not properly configured"
            )
        
        # Store user message
        user_message = ChatMessage(
            sessionId=message_data.sessionId,
            message=message_data.message,
            sender="user"
        )
        await db.chat_messages.insert_one(user_message.dict())
        
        # Check if user is requesting a quote and store it
        quote_keywords = ['quote', 'price', 'cost', 'estimate', 'how much', 'cotización', 'precio', 'cuánto cuesta', 'cuanto cuesta']
        is_quote_request = any(keyword in message_data.message.lower() for keyword in quote_keywords)
        
        if is_quote_request:
            # Store quote request in contacts collection for follow-up
            quote_inquiry = {
                "id": str(uuid.uuid4()),
                "name": f"ChatBot User - Session {message_data.sessionId[-8:]}",
                "email": "chatbot-quote@pending.com",  # Placeholder
                "phone": "Pending via chat",
                "subject": "quote", 
                "message": f"Quote request via chatbot: {message_data.message}",
                "status": "new",
                "sessionId": message_data.sessionId,
                "source": "chatbot",
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            }
            await db.contacts.insert_one(quote_inquiry)
        
        # Get recent chat history for context (last 10 messages)
        recent_messages = await db.chat_messages.find(
            {"sessionId": message_data.sessionId}
        ).sort("timestamp", -1).limit(10).to_list(10)
        
        # Build conversation history for context
        conversation_context = ""
        if recent_messages:
            # Reverse to get chronological order
            recent_messages.reverse()
            for msg in recent_messages[:-1]:  # Exclude the current message
                conversation_context += f"{msg['sender']}: {msg['message']}\n"
        
        # Detect if the message is in Spanish
        spanish_keywords = ['hola', 'buenos', 'días', 'tardes', 'noches', 'gracias', 'por favor', 'ayuda', 'servicio', 'mudanza', 'limpieza', 'precio', 'costo', '¿', '¡', 'español', 'habla', 'hablas']
        is_spanish = any(keyword in message_data.message.lower() for keyword in spanish_keywords)
        
        # System message for SwiftMove & Clean chatbot
        if is_spanish:
            system_message = f"""Eres Favour, un chatbot de servicio al cliente para SwiftMove & Clean, una empresa profesional de mudanzas y limpieza que sirve a Ohio, Kentucky e Indiana.

Información de la Empresa:
- Servicios: Mudanzas Residenciales, Mudanzas Comerciales, Limpieza de Casas, Limpieza de Oficinas
- Horarios de Servicio: Lunes - Sábado, 8AM - 6PM
- Teléfono: (501) 575-5189
- Áreas de Servicio: Ohio (Cincinnati, Columbus, Cleveland, Dayton), Kentucky (Louisville, Lexington, Covington), Indiana (Indianapolis, Fort Wayne, Evansville)

Tu función es:
1. Responder preguntas sobre nuestros servicios, precios y disponibilidad
2. Ayudar a los clientes a entender nuestros procesos de mudanza y limpieza
3. Proporcionar asistencia de reserva y recopilar información básica
4. Ofrecer consejos útiles para mudanzas y limpieza
5. Ser amigable, profesional y conocedor

Directrices:
- Mantén las respuestas conversacionales y útiles
- Si preguntan sobre precios específicos, menciona que proporcionamos cotizaciones personalizadas gratuitas
- Para solicitudes de reserva, pregunta por detalles básicos (tipo de servicio, ubicación, fecha preferida)
- Si no puedes responder algo, ofrece conectarlos con nuestro equipo
- Siempre sé alentador y solidario con sus necesidades de mudanza/limpieza

Conversación reciente:
{conversation_context}

Mensaje actual del usuario: {message_data.message}

Responde como Favour de manera útil y amigable EN ESPAÑOL."""
        else:
            system_message = f"""You are Favour, a helpful customer service chatbot for SwiftMove & Clean, a professional moving and cleaning service company serving Ohio, Kentucky, and Indiana.

Company Information:
- Services: Residential Moving, Commercial Moving, House Cleaning, Office Cleaning
- Service Hours: Monday - Saturday, 8AM - 6PM
- Phone: (501) 575-5189
- Service Areas: Ohio (Cincinnati, Columbus, Cleveland, Dayton), Kentucky (Louisville, Lexington, Covington), Indiana (Indianapolis, Fort Wayne, Evansville)

Your role is to:
1. Answer questions about our services, pricing, and availability
2. Help customers understand our moving and cleaning processes
3. Provide booking assistance and collect basic information
4. Offer helpful tips for moving and cleaning
5. Be friendly, professional, and knowledgeable

Guidelines:
- Keep responses conversational and helpful
- If asked about specific pricing, mention we provide free custom quotes
- For booking requests, ask for basic details (service type, location, date preference)
- If you can't answer something, offer to connect them with our team
- Always be encouraging and supportive about their moving/cleaning needs
- If the user writes in Spanish, respond in Spanish

Recent conversation:
{conversation_context}

Current user message: {message_data.message}

Respond as Favour in a helpful, friendly manner."""

        # Initialize chat with LLM
        chat = LlmChat(
            api_key=api_key,
            session_id=message_data.sessionId,
            system_message=system_message
        ).with_model("openai", "gpt-4o-mini")
        
        # Create user message for LLM
        llm_user_message = UserMessage(text=message_data.message)
        
        # Get response from LLM
        bot_response = await chat.send_message(llm_user_message)
        
        # Store bot response
        bot_message = ChatMessage(
            sessionId=message_data.sessionId,
            message=bot_response,
            sender="bot"
        )
        await db.chat_messages.insert_one(bot_message.dict())
        
        # Update session activity
        await db.chat_sessions.update_one(
            {"id": message_data.sessionId},
            {
                "$set": {"lastActivity": datetime.utcnow()},
                "$setOnInsert": {"id": message_data.sessionId, "createdAt": datetime.utcnow()}
            },
            upsert=True
        )
        
        return bot_message
        
    except Exception as e:
        print(f"Chat error: {str(e)}")
        # Return a fallback response
        fallback_message = ChatMessage(
            sessionId=message_data.sessionId,
            message="I'm sorry, I'm having trouble responding right now. Please call us at (501) 575-5189 or use our booking form for assistance with your moving and cleaning needs.",
            sender="bot"
        )
        await db.chat_messages.insert_one(fallback_message.dict())
        return fallback_message

@router.get("/messages/{session_id}", response_model=List[ChatMessage])
async def get_chat_messages(session_id: str):
    """Get all messages for a chat session"""
    try:
        messages = await db.chat_messages.find(
            {"sessionId": session_id}
        ).sort("timestamp", 1).to_list(1000)
        return [ChatMessage(**message) for message in messages]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chat messages: {str(e)}"
        )

@router.delete("/session/{session_id}")
async def clear_chat_session(session_id: str):
    """Clear all messages for a chat session"""
    try:
        result = await db.chat_messages.delete_many({"sessionId": session_id})
        await db.chat_sessions.delete_one({"id": session_id})
        return {"message": f"Cleared {result.deleted_count} messages from session {session_id}"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing chat session: {str(e)}"
        )

@router.get("/quote-requests")
async def get_chatbot_quote_requests():
    """Get all quote requests from chatbot conversations"""
    try:
        quote_requests = await db.contacts.find(
            {"source": "chatbot", "subject": "quote"}
        ).sort("createdAt", -1).to_list(1000)
        
        # Convert ObjectId to string for each document
        for request in quote_requests:
            if '_id' in request:
                request['_id'] = str(request['_id'])
                
        return quote_requests
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chatbot quote requests: {str(e)}"
        )