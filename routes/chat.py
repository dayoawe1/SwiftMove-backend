from fastapi import APIRouter, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from datetime import datetime
import sys
from pathlib import Path
import os
import uuid
from dotenv import load_dotenv
import openai

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from models import ChatMessage, ChatMessageCreate, ChatSession

router = APIRouter(prefix="/chat", tags=["chat"])

# Injected by main app
db = None

def set_database(database: AsyncIOMotorDatabase):
    global db
    db = database


@router.post("/message", response_model=ChatMessage)
async def send_chat_message(message_data: ChatMessageCreate):
    """Send a message to the chatbot and get a response"""
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OPENAI_API_KEY is not configured"
            )

        client = openai.OpenAI(api_key=api_key)

        # Save user message
        user_message = ChatMessage(
            sessionId=message_data.sessionId,
            message=message_data.message,
            sender="user"
        )
        await db.chat_messages.insert_one(user_message.dict())

        # Detect quote request
        quote_keywords = [
            "quote", "price", "cost", "estimate", "how much",
            "cotización", "precio", "cuánto cuesta", "cuanto cuesta"
        ]
        is_quote_request = any(
            keyword in message_data.message.lower()
            for keyword in quote_keywords
        )

        if is_quote_request:
            await db.contacts.insert_one({
                "id": str(uuid.uuid4()),
                "name": f"ChatBot User - Session {message_data.sessionId[-8:]}",
                "email": "chatbot-quote@pending.com",
                "phone": "Pending via chat",
                "subject": "quote",
                "message": f"Quote request via chatbot: {message_data.message}",
                "status": "new",
                "sessionId": message_data.sessionId,
                "source": "chatbot",
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            })

        # Get recent chat history
        recent_messages = await db.chat_messages.find(
            {"sessionId": message_data.sessionId}
        ).sort("timestamp", -1).limit(10).to_list(10)

        recent_messages.reverse()

        # Detect Spanish
        spanish_keywords = [
            "hola", "buenos", "días", "tardes", "noches", "gracias",
            "por favor", "ayuda", "servicio", "mudanza", "limpieza",
            "precio", "costo", "¿", "¡", "español"
        ]
        is_spanish = any(
            keyword in message_data.message.lower()
            for keyword in spanish_keywords
        )

        conversation_context = "".join(
            f"{m['sender']}: {m['message']}\n"
            for m in recent_messages[:-1]
        )

        # System prompt
        if is_spanish:
            system_message = f"""
Eres Favour, un chatbot de servicio al cliente para SwiftMove & Clean.

Servicios:
- Mudanzas residenciales y comerciales
- Limpieza de casas y oficinas

Horario:
- Lunes a Sábado, 8AM – 6PM
Teléfono: (812) 669-4165
Áreas: Ohio, Kentucky, Indiana

Conversación reciente:
{conversation_context}

Responde en ESPAÑOL de forma profesional y amigable.
"""
        else:
            system_message = f"""
You are Favour, a helpful customer service chatbot for SwiftMove & Clean.

Services:
- Residential & Commercial Moving
- House & Office Cleaning

Hours:
- Monday – Saturday, 8AM – 6PM
Phone: (812) 669-4165
Service Areas: Ohio, Kentucky, Indiana

Recent conversation:
{conversation_context}

Respond in a friendly, professional tone.
"""

        # Build OpenAI messages
        messages = [{"role": "system", "content": system_message}]

        for msg in recent_messages[:-1]:
            role = "user" if msg["sender"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["message"]})

        messages.append({"role": "user", "content": message_data.message})

        # OpenAI request
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        bot_response = response.choices[0].message.content

        # Save bot response
        bot_message = ChatMessage(
            sessionId=message_data.sessionId,
            message=bot_response,
            sender="bot"
        )
        await db.chat_messages.insert_one(bot_message.dict())

        # Update session
        await db.chat_sessions.update_one(
            {"id": message_data.sessionId},
            {
                "$set": {"lastActivity": datetime.utcnow()},
                "$setOnInsert": {
                    "id": message_data.sessionId,
                    "createdAt": datetime.utcnow()
                }
            },
            upsert=True
        )

        return bot_message

    except Exception as e:
        print(f"Chat error: {str(e)}")

        fallback = ChatMessage(
            sessionId=message_data.sessionId,
            message=(
                "I'm sorry, I'm having trouble responding right now. "
                "Please call us at (812) 669-4165 for immediate assistance."
            ),
            sender="bot"
        )
        await db.chat_messages.insert_one(fallback.dict())
        return fallback


@router.get("/messages/{session_id}", response_model=List[ChatMessage])
async def get_chat_messages(session_id: str):
    messages = await db.chat_messages.find(
        {"sessionId": session_id}
    ).sort("timestamp", 1).to_list(1000)
    return [ChatMessage(**m) for m in messages]


@router.delete("/session/{session_id}")
async def clear_chat_session(session_id: str):
    result = await db.chat_messages.delete_many({"sessionId": session_id})
    await db.chat_sessions.delete_one({"id": session_id})
    return {"message": f"Cleared {result.deleted_count} messages"}


@router.get("/quote-requests")
async def get_chatbot_quote_requests():
    requests = await db.contacts.find(
        {"source": "chatbot", "subject": "quote"}
    ).sort("createdAt", -1).to_list(1000)

    for r in requests:
        r["_id"] = str(r["_id"])

    return requests
