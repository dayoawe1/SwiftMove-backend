from fastapi import APIRouter, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models import (
    ContactMessage,
    ContactMessageCreate,
    ContactMessageUpdate,
    ContactStatus
)

router = APIRouter(prefix="/contacts", tags=["contacts"])

# This will be injected by the main app
db = None

def set_database(database: AsyncIOMotorDatabase):
    global db
    db = database

@router.post("/", response_model=ContactMessage, status_code=status.HTTP_201_CREATED)
async def create_contact_message(message_data: ContactMessageCreate):
    """Submit a contact form message"""
    try:
        # Create contact message object with source identifier
        message_dict = message_data.dict()
        message_dict["source"] = "contact_form"  # Mark as contact form submission
        message = ContactMessage(**message_dict)
        
        # Insert into database
        result = await db.contacts.insert_one(message.dict())
        
        if result.inserted_id:
            return message
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create contact message"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating contact message: {str(e)}"
        )

@router.get("/", response_model=List[ContactMessage])
async def get_all_contacts():
    """Get all contact messages (admin endpoint)"""
    try:
        contacts = await db.contacts.find().sort("createdAt", -1).to_list(1000)
        return [ContactMessage(**contact) for contact in contacts]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching contacts: {str(e)}"
        )

@router.get("/{contact_id}", response_model=ContactMessage)
async def get_contact_message(contact_id: str):
    """Get a specific contact message by ID"""
    try:
        contact = await db.contacts.find_one({"id": contact_id})
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact message not found"
            )
        return ContactMessage(**contact)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching contact message: {str(e)}"
        )

@router.put("/{contact_id}", response_model=ContactMessage)
async def update_contact_status(contact_id: str, update_data: ContactMessageUpdate):
    """Update contact message status (mark as read/replied)"""
    try:
        update_dict = update_data.dict(exclude_unset=True)
        update_dict["updatedAt"] = datetime.utcnow()
        
        result = await db.contacts.update_one(
            {"id": contact_id},
            {"$set": update_dict}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact message not found"
            )
        
        # Return updated contact
        updated_contact = await db.contacts.find_one({"id": contact_id})
        return ContactMessage(**updated_contact)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating contact message: {str(e)}"
        )