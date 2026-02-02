from fastapi import APIRouter, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from datetime import datetime
import sys
from pathlib import Path
import os
import uuid
import re
from dotenv import load_dotenv
import openai

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

def extract_contact_info(text):
    """Extract name, email, and phone from text"""
    # Email pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    # Phone pattern (various formats)
    phone_pattern = r'[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}'
    
    email = re.search(email_pattern, text)
    phone = re.search(phone_pattern, text)
    
    return {
        'email': email.group() if email else None,
        'phone': phone.group() if phone else None
    }

async def get_session_contact_info(session_id):
    """Get collected contact info from session messages"""
    messages = await db.chat_messages.find(
        {"sessionId": session_id}
    ).sort("timestamp", 1).to_list(1000)
    
    collected_info = {
        'name': None,
        'email': None,
        'phone': None,
        'service_interest': None,
        'service_type': None,  # residential moving, commercial moving, cleaning, etc.
        'from_address': None,
        'to_address': None,
        'move_date': None,
        'property_size': None,  # bedrooms, sqft, etc.
        'special_items': None,  # piano, antiques, etc.
        'additional_details': None,
        'messages': []
    }
    
    all_user_messages = []
    
    for msg in messages:
        if msg.get('sender') == 'user':
            text = msg.get('message', '')
            all_user_messages.append(text)
            collected_info['messages'].append(text)
            
            # Extract contact info
            info = extract_contact_info(text)
            if info['email']:
                collected_info['email'] = info['email']
            if info['phone']:
                collected_info['phone'] = info['phone']
            
            # Try to detect name
            text_lower = text.lower()
            name_prefixes = ['my name is', 'i am', "i'm", 'this is', 'name is', 'call me', 'it\'s']
            
            for prefix in name_prefixes:
                if prefix in text_lower:
                    # Extract name after the prefix
                    idx = text_lower.find(prefix) + len(prefix)
                    name_part = text[idx:].strip()
                    # Clean up - take first few words, remove punctuation
                    name_words = name_part.split()[:3]
                    name_clean = ' '.join(name_words).strip('.,!?')
                    if name_clean and len(name_clean) > 1:
                        collected_info['name'] = name_clean.title()
                        break
            
            # If no prefix found, check if it's a short alphabetic message (likely a name response)
            # But exclude messages that contain service-related keywords
            service_keywords_check = ['move', 'moving', 'clean', 'cleaning', 'help', 'need', 'want', 'looking', 'from', 'to', 'house', 'apartment', 'office', 'bedroom', 'quote', 'price', 'cost']
            if not collected_info['name'] and len(text.split()) <= 3:
                clean_text = text.strip('.,!?')
                if clean_text.replace(' ', '').replace('-', '').isalpha() and len(clean_text) > 1:
                    # Make sure it's not a service-related message
                    if not any(kw in clean_text.lower() for kw in service_keywords_check):
                        collected_info['name'] = clean_text.title()
            
            # Detect service interest and type
            service_keywords = {
                'moving': ['move', 'moving', 'relocate', 'relocation', 'mudanza', 'mudar'],
                'cleaning': ['clean', 'cleaning', 'limpieza', 'limpiar']
            }
            for service, keywords in service_keywords.items():
                if any(kw in text_lower for kw in keywords):
                    collected_info['service_interest'] = service
            
            # Detect specific service type
            if 'residential' in text_lower or 'house' in text_lower or 'home' in text_lower or 'apartment' in text_lower:
                if collected_info['service_interest'] == 'moving':
                    collected_info['service_type'] = 'Residential Moving'
                elif collected_info['service_interest'] == 'cleaning':
                    collected_info['service_type'] = 'Residential Cleaning'
            elif 'commercial' in text_lower or 'office' in text_lower or 'business' in text_lower:
                if collected_info['service_interest'] == 'moving':
                    collected_info['service_type'] = 'Commercial Moving'
                elif collected_info['service_interest'] == 'cleaning':
                    collected_info['service_type'] = 'Commercial Cleaning'
            
            # Detect property size (bedrooms)
            bedroom_patterns = [
                r'(\d+)\s*(?:bed(?:room)?s?|br|bdr)',
                r'(\d+)\s*(?:bedroom|bed)\s*(?:house|home|apt|apartment)',
                r'studio',
                r'(\d+)\s*(?:sq\.?\s*ft|square\s*feet)',
            ]
            for pattern in bedroom_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    if 'studio' in text_lower:
                        collected_info['property_size'] = 'Studio'
                    elif 'sq' in pattern or 'square' in pattern:
                        collected_info['property_size'] = f"{match.group(1)} sq ft"
                    else:
                        collected_info['property_size'] = f"{match.group(1)} bedroom"
                    break
            
            # Detect addresses (look for street indicators)
            address_indicators = ['street', 'st.', 'st,', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr', 'lane', 'ln', 'blvd', 'boulevard', 'way', 'court', 'ct']
            if any(ind in text_lower for ind in address_indicators):
                # Check for "from" and "to" context
                if 'from' in text_lower and not collected_info['from_address']:
                    collected_info['from_address'] = text
                elif 'to' in text_lower and not collected_info['to_address']:
                    collected_info['to_address'] = text
                elif not collected_info['from_address']:
                    collected_info['from_address'] = text
                elif not collected_info['to_address']:
                    collected_info['to_address'] = text
            
            # Detect dates
            date_patterns = [
                r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
                r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{0,4}\b',
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{0,4}\b',
                r'\bnext\s+(week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
                r'\bthis\s+(week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    collected_info['move_date'] = match.group(0)
                    break
            
            # Detect special items
            special_items_keywords = ['piano', 'antique', 'artwork', 'art', 'fragile', 'heavy', 'safe', 'gun safe', 'pool table', 'hot tub', 'exercise equipment', 'gym equipment', 'tv', 'television', 'glass', 'mirror', 'chandelier']
            found_items = [item for item in special_items_keywords if item in text_lower]
            if found_items:
                collected_info['special_items'] = ', '.join(found_items)
    
    # Store all messages as additional details context
    collected_info['additional_details'] = ' | '.join(all_user_messages[-5:]) if all_user_messages else None
    
    return collected_info

@router.post("/message", response_model=ChatMessage)
async def send_chat_message(message_data: ChatMessageCreate):
    """Send a message to the chatbot and get a response"""
    try:
        # Get OpenAI API key from environment
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Chatbot service is not properly configured - no OpenAI API key found"
            )
        
        # Store user message
        user_message = ChatMessage(
            sessionId=message_data.sessionId,
            message=message_data.message,
            sender="user"
        )
        await db.chat_messages.insert_one(user_message.dict())
        
        # Get collected contact info so far
        contact_info = await get_session_contact_info(message_data.sessionId)
        
        # Check what info is still needed
        missing_info = []
        if not contact_info['name']:
            missing_info.append('name')
        if not contact_info['email']:
            missing_info.append('email')
        if not contact_info['phone']:
            missing_info.append('phone')
        
        # Extract info from current message
        current_info = extract_contact_info(message_data.message)
        if current_info['email']:
            contact_info['email'] = current_info['email']
            if 'email' in missing_info:
                missing_info.remove('email')
        if current_info['phone']:
            contact_info['phone'] = current_info['phone']
            if 'phone' in missing_info:
                missing_info.remove('phone')
        
        # Check if current message could be a name
        text = message_data.message
        if 'name' in missing_info and len(text.split()) <= 4:
            if any(keyword in text.lower() for keyword in ['my name is', 'i am', "i'm", 'this is', 'name is']):
                for keyword in ['my name is', 'i am', "i'm", 'this is', 'name is']:
                    if keyword in text.lower():
                        name_part = text.lower().split(keyword)[-1].strip()
                        if name_part:
                            contact_info['name'] = name_part.title()
                            missing_info.remove('name')
                            break
            elif len(text.split()) <= 3 and text.replace(' ', '').isalpha() and len(text) > 1:
                contact_info['name'] = text.title()
                if 'name' in missing_info:
                    missing_info.remove('name')
        
        # Get recent chat history for context (last 10 messages)
        recent_messages = await db.chat_messages.find(
            {"sessionId": message_data.sessionId}
        ).sort("timestamp", -1).limit(10).to_list(10)
        
        # Build conversation history for context
        conversation_context = ""
        if recent_messages:
            recent_messages.reverse()
            for msg in recent_messages[:-1]:
                conversation_context += f"{msg['sender']}: {msg['message']}\n"
        
        # Detect if the message is in Spanish
        spanish_keywords = ['hola', 'buenos', 'días', 'tardes', 'noches', 'gracias', 'por favor', 'ayuda', 'servicio', 'mudanza', 'limpieza', 'precio', 'costo', '¿', '¡', 'español', 'habla', 'hablas']
        is_spanish = any(keyword in message_data.message.lower() for keyword in spanish_keywords)
        
        # Build info about what's collected
        # Check what service details are still needed
        missing_service_details = []
        if contact_info['service_interest'] == 'moving':
            if not contact_info['from_address']:
                missing_service_details.append('moving from address/location')
            if not contact_info['to_address']:
                missing_service_details.append('moving to address/location')
            if not contact_info['move_date']:
                missing_service_details.append('preferred move date')
            if not contact_info['property_size']:
                missing_service_details.append('property size (bedrooms or approximate size)')
        elif contact_info['service_interest'] == 'cleaning':
            if not contact_info['from_address']:
                missing_service_details.append('property address/location')
            if not contact_info['move_date']:
                missing_service_details.append('preferred cleaning date')
            if not contact_info['property_size']:
                missing_service_details.append('property size (bedrooms or square footage)')
        
        collected_status = f"""
Currently collected customer information:
- Name: {contact_info['name'] or 'NOT YET COLLECTED'}
- Email: {contact_info['email'] or 'NOT YET COLLECTED'}
- Phone: {contact_info['phone'] or 'NOT YET COLLECTED'}
- Service Interest: {contact_info['service_interest'] or 'Not specified yet'}
- Service Type: {contact_info['service_type'] or 'Not specified yet'}
- From Address: {contact_info['from_address'] or 'NOT YET COLLECTED'}
- To Address: {contact_info['to_address'] or 'NOT YET COLLECTED (if moving)'}
- Preferred Date: {contact_info['move_date'] or 'NOT YET COLLECTED'}
- Property Size: {contact_info['property_size'] or 'NOT YET COLLECTED'}
- Special Items: {contact_info['special_items'] or 'None mentioned'}

Missing contact information that MUST be collected: {', '.join(missing_info) if missing_info else 'All contact info collected!'}
Missing service details to collect: {', '.join(missing_service_details) if missing_service_details else 'Service details collected or not applicable yet'}
"""
        
        # System message for Swift Move and Clean chatbot
        if is_spanish:
            system_message = f"""Eres Favour, un chatbot de servicio al cliente para Swift Move and Clean, una empresa profesional de mudanzas y limpieza que sirve Indiana.

Información de la Empresa:
- Servicios: Mudanzas Residenciales, Mudanzas Comerciales, Soporte de Mudanza, Limpieza Residencial, Limpieza Comercial
- Horarios de Servicio: Lunes - Sábado, 8AM - 6PM
- Teléfono: (812) 669-4165
- Áreas de Servicio: Bloomington, Indianapolis, Columbus, Lafayette, Carmel, Greenwood, Avon, Seymour, Greensburg, Fishers, Zionsville, Muncie, Danville

{collected_status}

REGLAS IMPORTANTES - DEBES SEGUIR ESTAS REGLAS:
1. NUNCA des cotizaciones, precios o estimados de costos. Si preguntan por precios, di que un miembro del equipo los contactará con una cotización personalizada.
2. SIEMPRE recopila la siguiente información del cliente:
   - Nombre completo
   - Correo electrónico
   - Número de teléfono
   - Para MUDANZAS: dirección de origen, dirección de destino, fecha preferida, tamaño de la propiedad (cuántas habitaciones), artículos especiales (piano, antigüedades, etc.)
   - Para LIMPIEZA: dirección de la propiedad, fecha preferida, tamaño de la propiedad
3. Pregunta por los detalles del servicio uno por uno de manera conversacional, no todo de una vez.
4. Una vez que tengas toda la información, confirma los detalles y di que alguien se comunicará pronto con una cotización personalizada.
5. Sé amigable y profesional.

Conversación reciente:
{conversation_context}

Mensaje actual del usuario: {message_data.message}

Responde como Favour de manera útil y amigable EN ESPAÑOL. Recuerda: NO des precios, recopila todos los detalles del servicio y la información de contacto."""
        else:
            system_message = f"""You are Favour, a helpful customer service chatbot for Swift Move and Clean, a professional moving and cleaning service company serving Indiana.

Company Information:
- Services: Residential Moving, Commercial Moving, Moving Support, Residential Cleaning, Commercial Cleaning
- Service Hours: Monday - Saturday, 8AM - 6PM
- Phone: (812) 669-4165
- Service Areas: Bloomington, Indianapolis, Columbus, Lafayette, Carmel, Greenwood, Avon, Seymour, Greensburg, Fishers, Zionsville, Muncie, Danville

{collected_status}

IMPORTANT RULES - YOU MUST FOLLOW THESE:
1. NEVER provide quotes, prices, or cost estimates for ANY service (moving or cleaning). If asked about pricing, say that a team member will contact them with a personalized quote based on their specific needs.
2. ALWAYS collect the following information from the customer:
   - Full name
   - Email address  
   - Phone number
   - For MOVING services: current address (moving from), destination address (moving to), preferred move date, property size (number of bedrooms), any special items (piano, antiques, heavy safes, etc.)
   - For CLEANING services: property address, preferred cleaning date, property size (bedrooms or square footage), type of cleaning needed
3. Ask for service details one by one in a conversational manner, not all at once.
4. Once you have all the information, confirm the details and let them know someone will reach out shortly with a personalized quote.
5. Be friendly, professional, and helpful.
6. If they insist on getting a price, explain that pricing depends on many factors like distance, property size, items being moved, and our team will provide an accurate quote after reviewing their specific needs.

Recent conversation:
{conversation_context}

Current user message: {message_data.message}

Respond as Favour in a helpful, friendly manner. Remember: DO NOT provide any prices, collect all service details and contact information conversationally."""

        # Use OpenAI directly
        try:
            client = openai.OpenAI(api_key=api_key)
            
            messages = [
                {"role": "system", "content": system_message}
            ]
            
            for msg in recent_messages[:-1]:
                role = "user" if msg['sender'] == 'user' else "assistant"
                messages.append({"role": role, "content": msg['message']})
            
            messages.append({"role": "user", "content": message_data.message})
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            bot_response = response.choices[0].message.content
            
        except Exception as openai_error:
            print(f"OpenAI API error: {str(openai_error)}")
            raise Exception("OpenAI service unavailable")
        
        # Store bot response
        bot_message = ChatMessage(
            sessionId=message_data.sessionId,
            message=bot_response,
            sender="bot"
        )
        await db.chat_messages.insert_one(bot_message.dict())
        
        # Update or create chat session record with contact info
        session_data = {
            "id": message_data.sessionId,
            "lastActivity": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }
        
        if contact_info['name']:
            session_data['customerName'] = contact_info['name']
        if contact_info['email']:
            session_data['customerEmail'] = contact_info['email']
        if contact_info['phone']:
            session_data['customerPhone'] = contact_info['phone']
        if contact_info['service_interest']:
            session_data['serviceInterest'] = contact_info['service_interest']
        if contact_info['service_type']:
            session_data['serviceType'] = contact_info['service_type']
        if contact_info['from_address']:
            session_data['fromAddress'] = contact_info['from_address']
        if contact_info['to_address']:
            session_data['toAddress'] = contact_info['to_address']
        if contact_info['move_date']:
            session_data['preferredDate'] = contact_info['move_date']
        if contact_info['property_size']:
            session_data['propertySize'] = contact_info['property_size']
        
        await db.chat_sessions.update_one(
            {"id": message_data.sessionId},
            {
                "$set": session_data,
                "$setOnInsert": {"createdAt": datetime.utcnow()}
            },
            upsert=True
        )
        
        # If we have collected at least some contact info, store/update in contacts for admin
        if contact_info['name'] or contact_info['email'] or contact_info['phone']:
            # Check if contact already exists for this session
            existing_contact = await db.contacts.find_one({"sessionId": message_data.sessionId, "source": "chatbot"})
            
            # Build detailed message with all collected info
            service_details = []
            service_details.append(f"Service Type: {contact_info['service_type'] or contact_info['service_interest'] or 'General Inquiry'}")
            if contact_info['from_address']:
                service_details.append(f"From Address: {contact_info['from_address']}")
            if contact_info['to_address']:
                service_details.append(f"To Address: {contact_info['to_address']}")
            if contact_info['move_date']:
                service_details.append(f"Preferred Date: {contact_info['move_date']}")
            if contact_info['property_size']:
                service_details.append(f"Property Size: {contact_info['property_size']}")
            if contact_info['special_items']:
                service_details.append(f"Special Items: {contact_info['special_items']}")
            if contact_info['additional_details']:
                service_details.append(f"Conversation Notes: {contact_info['additional_details']}")
            
            contact_data = {
                "name": contact_info['name'] or f"Chat User - {message_data.sessionId[-8:]}",
                "email": contact_info['email'] or "pending@chat.com",
                "phone": contact_info['phone'] or "Pending",
                "subject": f"Chat Inquiry - {contact_info['service_type'] or contact_info['service_interest'] or 'General'}",
                "message": "\n".join(service_details),
                "status": "new",
                "sessionId": message_data.sessionId,
                "source": "chatbot",
                "updatedAt": datetime.utcnow()
            }
            
            if existing_contact:
                await db.contacts.update_one(
                    {"sessionId": message_data.sessionId, "source": "chatbot"},
                    {"$set": contact_data}
                )
            else:
                contact_data["id"] = str(uuid.uuid4())
                contact_data["createdAt"] = datetime.utcnow()
                await db.contacts.insert_one(contact_data)
        
        return bot_message
        
    except Exception as e:
        print(f"Chat error: {str(e)}")
        fallback_message = ChatMessage(
            sessionId=message_data.sessionId,
            message="I'm sorry, I'm having trouble responding right now. Please call us at (812) 669-4165 or use our booking form for assistance with your moving and cleaning needs.",
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
        # Also remove from contacts
        await db.contacts.delete_one({"sessionId": session_id, "source": "chatbot"})
        return {"message": f"Cleared {result.deleted_count} messages from session {session_id}"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing chat session: {str(e)}"
        )

@router.get("/sessions")
async def get_chat_sessions():
    """Get all chat sessions with customer info"""
    try:
        sessions = await db.chat_sessions.find().sort("lastActivity", -1).to_list(100)
        for session in sessions:
            if '_id' in session:
                session['_id'] = str(session['_id'])
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chat sessions: {str(e)}"
        )

@router.get("/quote-requests")
async def get_chatbot_quote_requests():
    """Get all quote requests from chatbot conversations"""
    try:
        quote_requests = await db.contacts.find(
            {"source": "chatbot"}
        ).sort("createdAt", -1).to_list(100)
        
        for request in quote_requests:
            if '_id' in request:
                request['_id'] = str(request['_id'])
        
        return quote_requests
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chatbot quote requests: {str(e)}"
        )
