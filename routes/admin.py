from fastapi import APIRouter, HTTPException, status, Depends, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from datetime import datetime, timedelta
import sys
from pathlib import Path
import os
import jwt
import hashlib

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models import ContactMessage, ServiceBooking, ChatMessage

router = APIRouter(prefix="/admin", tags=["admin"])

# This will be injected by the main app
db = None

def set_database(database: AsyncIOMotorDatabase):
    global db
    db = database

# Admin credentials from environment variables
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
JWT_SECRET = os.environ.get("JWT_SECRET", "swift-move-admin-secret-key-2024")

security = HTTPBearer()

def create_access_token(username: str):
    """Create JWT access token"""
    payload = {
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        username = payload.get("username")
        if username != ADMIN_USERNAME:
            return None
        return username
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated admin"""
    username = verify_token(credentials.credentials)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username

@router.post("/login")
async def admin_login(credentials: dict):
    """Admin login endpoint"""
    username = credentials.get("username")
    password = credentials.get("password")
    
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required"
        )
    
    # Hash the provided password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH:
        token = create_access_token(username)
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 86400,  # 24 hours
            "message": "Login successful"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@router.get("/dashboard/stats")
async def get_dashboard_stats(current_admin: str = Depends(get_current_admin)):
    """Get dashboard statistics"""
    try:
        # Count all requests
        total_contacts = await db.contacts.count_documents({})
        total_bookings = await db.bookings.count_documents({})
        chatbot_quotes = await db.contacts.count_documents({"source": "chatbot"})
        pending_contacts = await db.contacts.count_documents({"status": "new"})
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_contacts = await db.contacts.count_documents({"createdAt": {"$gte": week_ago}})
        recent_bookings = await db.bookings.count_documents({"createdAt": {"$gte": week_ago}})
        
        return {
            "total_contacts": total_contacts,
            "total_bookings": total_bookings,
            "chatbot_quotes": chatbot_quotes,
            "pending_contacts": pending_contacts,
            "recent_contacts": recent_contacts,
            "recent_bookings": recent_bookings,
            "last_updated": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dashboard stats: {str(e)}"
        )

@router.get("/contacts")
async def get_all_admin_contacts(current_admin: str = Depends(get_current_admin)):
    """Get all contact messages for admin"""
    try:
        contacts = await db.contacts.find().sort("createdAt", -1).to_list(1000)
        # Convert ObjectId to string
        for contact in contacts:
            if '_id' in contact:
                contact['_id'] = str(contact['_id'])
        return contacts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching contacts: {str(e)}"
        )

@router.get("/bookings")
async def get_all_admin_bookings(current_admin: str = Depends(get_current_admin)):
    """Get all bookings for admin"""
    try:
        bookings = await db.bookings.find().sort("createdAt", -1).to_list(1000)
        # Convert ObjectId to string
        for booking in bookings:
            if '_id' in booking:
                booking['_id'] = str(booking['_id'])
        return bookings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching bookings: {str(e)}"
        )

@router.get("/chatbot-quotes")
async def get_admin_chatbot_quotes(current_admin: str = Depends(get_current_admin)):
    """Get all chatbot quote requests for admin"""
    try:
        quotes = await db.contacts.find({"source": "chatbot"}).sort("createdAt", -1).to_list(1000)
        # Convert ObjectId to string
        for quote in quotes:
            if '_id' in quote:
                quote['_id'] = str(quote['_id'])
        return quotes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chatbot quotes: {str(e)}"
        )

@router.put("/contacts/{contact_id}/status")
async def update_contact_status(
    contact_id: str, 
    status_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Update contact message status"""
    try:
        new_status = status_data.get("status")
        if new_status not in ["new", "read", "replied"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status. Must be 'new', 'read', or 'replied'"
            )
        
        result = await db.contacts.update_one(
            {"id": contact_id},
            {"$set": {"status": new_status, "updatedAt": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found"
            )
        
        return {"message": f"Contact status updated to {new_status}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating contact status: {str(e)}"
        )

@router.put("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: str, 
    status_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Update booking status"""
    try:
        new_status = status_data.get("status")
        if new_status not in ["pending", "confirmed", "completed", "cancelled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status. Must be 'pending', 'confirmed', 'completed', or 'cancelled'"
            )
        
        result = await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"status": new_status, "updatedAt": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        return {"message": f"Booking status updated to {new_status}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating booking status: {str(e)}"
        )