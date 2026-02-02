from fastapi import APIRouter, HTTPException, status, Depends, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
import os
import jwt
import hashlib
import uuid

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models import (
    ContactMessage, ServiceBooking, ChatMessage, 
    Payment, PaymentCreate, PaymentType, PaymentMethod,
    Task, TaskCreate, TaskUpdate, TaskStatus, TaskPriority, TaskType
)

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
    """Get dashboard statistics with proper siloing"""
    try:
        # Count chatbot leads separately
        chatbot_quotes = await db.contacts.count_documents({"source": "chatbot"})
        
        # Count contact form submissions (excluding chatbot leads)
        all_contacts = await db.contacts.count_documents({})
        contact_form_submissions = all_contacts - chatbot_quotes
        
        # Count bookings (from booking form)
        total_bookings = await db.bookings.count_documents({})
        
        # Pending items
        pending_contacts = await db.contacts.count_documents({
            "status": "new",
            "source": {"$ne": "chatbot"}
        })
        pending_chatbot = await db.contacts.count_documents({
            "status": "new",
            "source": "chatbot"
        })
        pending_bookings = await db.bookings.count_documents({"status": "pending"})
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_contacts = await db.contacts.count_documents({
            "createdAt": {"$gte": week_ago},
            "source": {"$ne": "chatbot"}
        })
        recent_bookings = await db.bookings.count_documents({"createdAt": {"$gte": week_ago}})
        recent_chatbot = await db.contacts.count_documents({
            "createdAt": {"$gte": week_ago},
            "source": "chatbot"
        })
        
        return {
            "total_contacts": contact_form_submissions,  # Only contact form submissions
            "total_bookings": total_bookings,
            "chatbot_quotes": chatbot_quotes,
            "pending_contacts": pending_contacts,
            "pending_bookings": pending_bookings,
            "pending_chatbot": pending_chatbot,
            "recent_contacts": recent_contacts,
            "recent_bookings": recent_bookings,
            "recent_chatbot": recent_chatbot,
            "last_updated": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dashboard stats: {str(e)}"
        )

@router.get("/contacts")
async def get_all_admin_contacts(current_admin: str = Depends(get_current_admin)):
    """Get contact form submissions only (excludes chatbot leads)"""
    try:
        # Filter to only show contact form submissions, not chatbot leads
        contacts = await db.contacts.find({
            "$or": [
                {"source": {"$exists": False}},  # Legacy contacts without source
                {"source": "contact_form"},       # Contact form submissions
                {"source": {"$nin": ["chatbot"]}} # Any source that's not chatbot
            ]
        }).sort("createdAt", -1).to_list(1000)
        
        # Additional filter to exclude chatbot entries
        contacts = [c for c in contacts if c.get("source") != "chatbot"]
        
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
    """Get service booking form submissions only (excludes converted chatbot leads)"""
    try:
        # Get all bookings - these come from the booking form
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
        if new_status not in ["new", "read", "replied", "contacted"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status. Must be 'new', 'read', 'replied', or 'contacted'"
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

# ================== CHATBOT QUOTE TO BOOKING CONVERSION ==================

@router.post("/chatbot-quotes/{quote_id}/convert-to-booking")
async def convert_chatbot_to_booking(
    quote_id: str,
    conversion_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Convert a chatbot quote to a booking when marked as contacted"""
    try:
        # Find the chatbot quote
        quote = await db.contacts.find_one({"id": quote_id, "source": "chatbot"})
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chatbot quote not found"
            )
        
        # Check if already converted
        existing_booking = await db.bookings.find_one({"convertedFromChatbot": quote_id})
        if existing_booking:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This quote has already been converted to a booking"
            )
        
        # Extract actual customer name from conversation notes or message
        customer_name = quote.get("name", "Unknown")
        message_content = quote.get("message", "")
        
        # Try to extract name from conversation notes (format: "Name | email | phone | ...")
        if "Conversation Notes:" in message_content:
            try:
                notes_part = message_content.split("Conversation Notes:")[-1].strip()
                parts = [p.strip() for p in notes_part.split("|")]
                if parts and parts[0] and "@" not in parts[0] and not parts[0].isdigit():
                    customer_name = parts[0]
            except:
                pass
        
        # Check if user provided a manual override for customer name - PRIORITY
        if conversion_data.get("customerName"):
            customer_name = conversion_data.get("customerName")
        # If name still looks like a greeting or too long (message captured), try to fix
        elif customer_name.lower().startswith(("hi", "hello", "hey", "good", "i need", "looking", "we need")):
            # Name is probably wrong, keep as-is but flag it
            pass
        
        # Parse service details from the quote notes if available
        service_type = conversion_data.get("serviceType", "General Service")
        preferred_date = conversion_data.get("preferredDate", datetime.now(timezone.utc) + timedelta(days=7))
        if isinstance(preferred_date, str):
            preferred_date = datetime.fromisoformat(preferred_date.replace('Z', '+00:00'))
        
        # Try to extract address from message if not provided
        current_address = conversion_data.get("currentAddress", "To be confirmed")
        new_address = conversion_data.get("newAddress")
        
        if current_address == "To be confirmed" and "From Address:" in message_content:
            try:
                addr_part = message_content.split("From Address:")[-1].split("\n")[0].strip()
                if addr_part:
                    current_address = addr_part
            except:
                pass
        
        # Create the booking from chatbot data
        booking_id = str(uuid.uuid4())
        booking = {
            "id": booking_id,
            "name": customer_name,
            "email": quote.get("email", ""),
            "phone": quote.get("phone", ""),
            "serviceType": service_type,
            "moveSize": conversion_data.get("moveSize"),
            "currentAddress": current_address,
            "newAddress": new_address,
            "preferredDate": preferred_date.isoformat() if isinstance(preferred_date, datetime) else preferred_date,
            "preferredTime": conversion_data.get("preferredTime", "flexible"),
            "hoursNeeded": conversion_data.get("hoursNeeded"),
            "specialRequests": quote.get("notes") or quote.get("message", ""),
            "status": "pending",
            "totalCost": None,
            "contractorCost": None,
            "laborHours": None,
            "convertedFromChatbot": quote_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        
        await db.bookings.insert_one(booking)
        
        # Update the chatbot quote status to 'contacted'
        await db.contacts.update_one(
            {"id": quote_id},
            {"$set": {"status": "contacted", "convertedToBooking": booking_id, "updatedAt": datetime.now(timezone.utc)}}
        )
        
        # Create a follow-up task for the new booking
        task = {
            "id": str(uuid.uuid4()),
            "bookingId": booking_id,
            "contactId": quote_id,
            "title": f"Initial follow-up: {customer_name}",
            "description": f"Booking converted from chatbot lead. Confirm service details and schedule.",
            "taskType": "follow_up",
            "priority": "high",
            "status": "pending",
            "dueDate": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "autoGenerated": True,
            "contactName": customer_name,
            "contactEmail": quote.get("email"),
            "serviceType": service_type,
            "serviceContext": f"Converted from chatbot quote. Original message: {quote.get('message', 'N/A')[:100]}",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "completedAt": None,
            "startedAt": None
        }
        await db.tasks.insert_one(task)
        
        return {
            "message": "Chatbot quote converted to booking successfully",
            "bookingId": booking_id,
            "taskId": task["id"],
            "customerName": customer_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error converting quote to booking: {str(e)}"
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
            {"$set": {"status": new_status, "updatedAt": datetime.now(timezone.utc)}}
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


# ================== BOOKING COST MANAGEMENT ==================

@router.put("/bookings/{booking_id}/cost")
async def update_booking_cost(
    booking_id: str,
    cost_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Update booking total cost (admin-entered)"""
    try:
        total_cost = cost_data.get("totalCost")
        if total_cost is None or total_cost < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valid totalCost required (must be >= 0)"
            )
        
        result = await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"totalCost": float(total_cost), "updatedAt": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        return {"message": f"Booking cost updated to ${total_cost}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating booking cost: {str(e)}"
        )

@router.put("/bookings/{booking_id}/contractor-cost")
async def update_booking_contractor_cost(
    booking_id: str,
    cost_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Update booking contractor cost (deducted from revenue)"""
    try:
        contractor_cost = cost_data.get("contractorCost")
        if contractor_cost is None or contractor_cost < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valid contractorCost required (must be >= 0)"
            )
        
        result = await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"contractorCost": float(contractor_cost), "updatedAt": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        return {"message": f"Contractor cost updated to ${contractor_cost}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating contractor cost: {str(e)}"
        )

@router.put("/bookings/{booking_id}/labor-hours")
async def update_booking_labor_hours(
    booking_id: str,
    hours_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Update booking labor hours"""
    try:
        labor_hours = hours_data.get("laborHours")
        if labor_hours is None or labor_hours < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valid laborHours required (must be >= 0)"
            )
        
        result = await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"laborHours": float(labor_hours), "updatedAt": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        return {"message": f"Labor hours updated to {labor_hours}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating labor hours: {str(e)}"
        )

@router.put("/bookings/{booking_id}/financials")
async def update_booking_financials(
    booking_id: str,
    financial_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Update all booking financial fields at once"""
    try:
        update_fields = {"updatedAt": datetime.now(timezone.utc)}
        
        if "totalCost" in financial_data and financial_data["totalCost"] is not None:
            update_fields["totalCost"] = float(financial_data["totalCost"])
        if "contractorCost" in financial_data and financial_data["contractorCost"] is not None:
            update_fields["contractorCost"] = float(financial_data["contractorCost"])
        if "laborHours" in financial_data and financial_data["laborHours"] is not None:
            update_fields["laborHours"] = float(financial_data["laborHours"])
        
        result = await db.bookings.update_one(
            {"id": booking_id},
            {"$set": update_fields}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        return {"message": "Booking financials updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating booking financials: {str(e)}"
        )

# ================== PAYMENT MANAGEMENT ==================

@router.get("/payments")
async def get_all_payments(current_admin: str = Depends(get_current_admin)):
    """Get all payments"""
    try:
        payments = await db.payments.find().sort("createdAt", -1).to_list(1000)
        for payment in payments:
            if '_id' in payment:
                payment['_id'] = str(payment['_id'])
        return payments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payments: {str(e)}"
        )

@router.get("/payments/booking/{booking_id}")
async def get_booking_payments(
    booking_id: str,
    current_admin: str = Depends(get_current_admin)
):
    """Get all payments for a specific booking"""
    try:
        payments = await db.payments.find({"bookingId": booking_id}).sort("createdAt", -1).to_list(100)
        for payment in payments:
            if '_id' in payment:
                payment['_id'] = str(payment['_id'])
        return payments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching booking payments: {str(e)}"
        )

@router.post("/payments")
async def create_payment(
    payment_data: PaymentCreate,
    current_admin: str = Depends(get_current_admin)
):
    """Log a new payment against a booking"""
    try:
        # Verify booking exists
        booking = await db.bookings.find_one({"id": payment_data.bookingId})
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        payment = Payment(
            bookingId=payment_data.bookingId,
            amount=payment_data.amount,
            paymentType=payment_data.paymentType,
            paymentMethod=payment_data.paymentMethod,
            notes=payment_data.notes
        )
        
        payment_dict = payment.model_dump()
        await db.payments.insert_one(payment_dict)
        
        # Auto-generate task if payment is a deposit
        if payment_data.paymentType == PaymentType.DEPOSIT:
            task = Task(
                bookingId=payment_data.bookingId,
                title=f"Collect remaining balance for booking",
                description=f"Deposit of ${payment_data.amount} received. Follow up for remaining balance.",
                taskType=TaskType.COLLECT_PAYMENT,
                priority=TaskPriority.MEDIUM,
                autoGenerated=True,
                dueDate=datetime.now(timezone.utc) + timedelta(days=3)
            )
            task_dict = task.model_dump()
            task_dict['dueDate'] = task_dict['dueDate'].isoformat() if task_dict['dueDate'] else None
            task_dict['completedAt'] = task_dict['completedAt'].isoformat() if task_dict['completedAt'] else None
            task_dict['createdAt'] = task_dict['createdAt'].isoformat()
            await db.tasks.insert_one(task_dict)
        
        return {"message": "Payment logged successfully", "paymentId": payment.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating payment: {str(e)}"
        )

@router.delete("/payments/{payment_id}")
async def delete_payment(
    payment_id: str,
    current_admin: str = Depends(get_current_admin)
):
    """Delete a payment record"""
    try:
        result = await db.payments.delete_one({"id": payment_id})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        return {"message": "Payment deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting payment: {str(e)}"
        )

# ================== REVENUE ANALYTICS ==================

def parse_datetime(date_str):
    """Parse datetime string from MongoDB, handling various formats"""
    if isinstance(date_str, datetime):
        return date_str if date_str.tzinfo else date_str.replace(tzinfo=timezone.utc)
    try:
        # Try ISO format with timezone
        if 'Z' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        elif '+' in date_str:
            return datetime.fromisoformat(date_str)
        else:
            # No timezone, assume UTC
            return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except:
        return datetime.now(timezone.utc)

@router.get("/revenue/summary")
async def get_revenue_summary(current_admin: str = Depends(get_current_admin)):
    """Get revenue summary - calculated from logged payments with contractor cost deductions"""
    try:
        now = datetime.now(timezone.utc)
        
        # Get all payments and bookings
        all_payments = await db.payments.find().to_list(10000)
        all_bookings = await db.bookings.find().to_list(10000)
        
        # Calculate gross totals from payments
        gross_revenue = sum(p.get('amount', 0) for p in all_payments if p.get('paymentType') != 'refund')
        total_refunds = sum(p.get('amount', 0) for p in all_payments if p.get('paymentType') == 'refund')
        
        # Calculate total contractor costs
        total_contractor_costs = sum(b.get('contractorCost', 0) or 0 for b in all_bookings)
        
        # Net revenue = gross payments - refunds - contractor costs
        net_revenue = gross_revenue - total_refunds - total_contractor_costs
        
        # This month's payments
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_payments = [p for p in all_payments if parse_datetime(p.get('createdAt', '')) >= first_of_month]
        monthly_gross = sum(p.get('amount', 0) for p in this_month_payments if p.get('paymentType') != 'refund')
        monthly_refunds = sum(p.get('amount', 0) for p in this_month_payments if p.get('paymentType') == 'refund')
        
        # This month's contractor costs (from bookings created/updated this month)
        this_month_bookings = [b for b in all_bookings if parse_datetime(b.get('createdAt', '')) >= first_of_month]
        monthly_contractor_costs = sum(b.get('contractorCost', 0) or 0 for b in this_month_bookings)
        monthly_net_revenue = monthly_gross - monthly_refunds - monthly_contractor_costs
        
        # Last month's payments for comparison
        first_of_last_month = (first_of_month - timedelta(days=1)).replace(day=1)
        last_month_payments = [p for p in all_payments 
                               if parse_datetime(p.get('createdAt', '')) >= first_of_last_month 
                               and parse_datetime(p.get('createdAt', '')) < first_of_month]
        last_month_gross = sum(p.get('amount', 0) for p in last_month_payments if p.get('paymentType') != 'refund')
        
        # Calculate growth based on net revenue
        if last_month_gross > 0:
            growth_percentage = ((monthly_gross - last_month_gross) / last_month_gross) * 100
        else:
            growth_percentage = 100 if monthly_gross > 0 else 0
        
        # Payment breakdown
        deposits = sum(p.get('amount', 0) for p in this_month_payments if p.get('paymentType') == 'deposit')
        partial_payments = sum(p.get('amount', 0) for p in this_month_payments if p.get('paymentType') == 'partial')
        full_payments = sum(p.get('amount', 0) for p in this_month_payments if p.get('paymentType') == 'full')
        
        # Get outstanding balances (bookings with cost set but not fully paid)
        bookings_with_cost = [b for b in all_bookings if (b.get('totalCost') or 0) > 0]
        outstanding_balance = 0
        for booking in bookings_with_cost:
            booking_payments = [p for p in all_payments if p.get('bookingId') == booking['id']]
            paid = sum(p.get('amount', 0) for p in booking_payments if p.get('paymentType') != 'refund')
            refunded = sum(p.get('amount', 0) for p in booking_payments if p.get('paymentType') == 'refund')
            balance = booking.get('totalCost', 0) - paid + refunded
            if balance > 0:
                outstanding_balance += balance
        
        # Calculate total labor hours
        total_labor_hours = sum(b.get('laborHours', 0) or 0 for b in all_bookings)
        monthly_labor_hours = sum(b.get('laborHours', 0) or 0 for b in this_month_bookings)
        
        return {
            "grossRevenue": gross_revenue - total_refunds,
            "totalContractorCosts": total_contractor_costs,
            "netRevenue": net_revenue,
            "monthlyGrossRevenue": monthly_gross - monthly_refunds,
            "monthlyContractorCosts": monthly_contractor_costs,
            "monthlyNetRevenue": monthly_net_revenue,
            "lastMonthRevenue": last_month_gross,
            "growthPercentage": round(growth_percentage, 1),
            "outstandingBalance": outstanding_balance,
            "totalLaborHours": total_labor_hours,
            "monthlyLaborHours": monthly_labor_hours,
            "breakdown": {
                "deposits": deposits,
                "partialPayments": partial_payments,
                "fullPayments": full_payments,
                "refunds": monthly_refunds,
                "contractorCosts": monthly_contractor_costs
            },
            "lastUpdated": now.isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating revenue summary: {str(e)}"
        )

@router.get("/revenue/monthly")
async def get_monthly_revenue(
    months: int = 6,
    current_admin: str = Depends(get_current_admin)
):
    """Get monthly revenue data for charts"""
    try:
        now = datetime.now(timezone.utc)
        monthly_data = []
        
        for i in range(months - 1, -1, -1):
            # Calculate month start/end
            month_date = now - timedelta(days=30 * i)
            month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if month_date.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1)
            
            # Get payments for this month
            payments = await db.payments.find({
                "createdAt": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}
            }).to_list(1000)
            
            revenue = sum(p.get('amount', 0) for p in payments if p.get('paymentType') != 'refund')
            refunds = sum(p.get('amount', 0) for p in payments if p.get('paymentType') == 'refund')
            
            monthly_data.append({
                "month": month_start.strftime("%b %Y"),
                "revenue": revenue - refunds,
                "payments": len([p for p in payments if p.get('paymentType') != 'refund']),
                "refunds": refunds
            })
        
        return monthly_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching monthly revenue: {str(e)}"
        )

# ================== TASK MANAGEMENT ==================

@router.get("/tasks")
async def get_all_tasks(
    status_filter: Optional[str] = None,
    current_admin: str = Depends(get_current_admin)
):
    """Get all tasks with optional status filter, enriched with contact/booking details"""
    try:
        query = {}
        if status_filter and status_filter != 'all':
            query["status"] = status_filter
        
        tasks = await db.tasks.find(query).sort("createdAt", -1).to_list(1000)
        
        # Enrich tasks with contact and booking details
        for task in tasks:
            if '_id' in task:
                task['_id'] = str(task['_id'])
            
            # If task has bookingId but no contact info, fetch from booking
            if task.get('bookingId') and not task.get('contactName'):
                booking = await db.bookings.find_one({"id": task['bookingId']})
                if booking:
                    task['contactName'] = booking.get('name')
                    task['contactEmail'] = booking.get('email')
                    task['serviceType'] = booking.get('serviceType')
                    task['serviceContext'] = f"{booking.get('serviceType', 'N/A')} - {booking.get('currentAddress', 'N/A')[:50]}"
            
            # If task has contactId but no contact info, fetch from contacts
            if task.get('contactId') and not task.get('contactName'):
                contact = await db.contacts.find_one({"id": task['contactId']})
                if contact:
                    task['contactName'] = contact.get('name')
                    task['contactEmail'] = contact.get('email')
                    task['serviceContext'] = contact.get('message', '')[:100] if contact.get('message') else 'N/A'
        
        return tasks
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching tasks: {str(e)}"
        )

@router.get("/tasks/booking/{booking_id}")
async def get_booking_tasks(
    booking_id: str,
    current_admin: str = Depends(get_current_admin)
):
    """Get all tasks for a specific booking"""
    try:
        tasks = await db.tasks.find({"bookingId": booking_id}).sort("createdAt", -1).to_list(100)
        for task in tasks:
            if '_id' in task:
                task['_id'] = str(task['_id'])
        return tasks
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching booking tasks: {str(e)}"
        )

@router.post("/tasks")
async def create_task(
    task_data: TaskCreate,
    current_admin: str = Depends(get_current_admin)
):
    """Create a new task with enriched contact/service details"""
    try:
        # Fetch contact/booking info if available
        contact_name = None
        contact_email = None
        service_type = None
        service_context = None
        
        if task_data.bookingId:
            booking = await db.bookings.find_one({"id": task_data.bookingId})
            if booking:
                contact_name = booking.get('name')
                contact_email = booking.get('email')
                service_type = booking.get('serviceType')
                service_context = f"{booking.get('serviceType', 'N/A')} - {booking.get('currentAddress', 'N/A')[:50]}"
        
        if task_data.contactId:
            contact = await db.contacts.find_one({"id": task_data.contactId})
            if contact:
                contact_name = contact_name or contact.get('name')
                contact_email = contact_email or contact.get('email')
                service_context = service_context or (contact.get('message', '')[:100] if contact.get('message') else 'N/A')
        
        task = Task(
            bookingId=task_data.bookingId,
            contactId=task_data.contactId,
            title=task_data.title,
            description=task_data.description,
            taskType=task_data.taskType,
            priority=task_data.priority,
            dueDate=task_data.dueDate,
            autoGenerated=False,
            contactName=contact_name,
            contactEmail=contact_email,
            serviceType=service_type,
            serviceContext=service_context
        )
        
        task_dict = task.model_dump()
        task_dict['dueDate'] = task_dict['dueDate'].isoformat() if task_dict['dueDate'] else None
        task_dict['completedAt'] = task_dict['completedAt'].isoformat() if task_dict['completedAt'] else None
        task_dict['startedAt'] = task_dict['startedAt'].isoformat() if task_dict.get('startedAt') else None
        task_dict['createdAt'] = task_dict['createdAt'].isoformat()
        await db.tasks.insert_one(task_dict)
        
        return {"message": "Task created successfully", "taskId": task.id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating task: {str(e)}"
        )

@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    current_admin: str = Depends(get_current_admin)
):
    """Update a task with proper status transition tracking"""
    try:
        update_dict = {}
        if task_data.title is not None:
            update_dict["title"] = task_data.title
        if task_data.description is not None:
            update_dict["description"] = task_data.description
        if task_data.priority is not None:
            update_dict["priority"] = task_data.priority.value
        if task_data.status is not None:
            update_dict["status"] = task_data.status.value
            # Track status transition timestamps
            if task_data.status == TaskStatus.IN_PROGRESS:
                update_dict["startedAt"] = datetime.now(timezone.utc).isoformat()
            elif task_data.status == TaskStatus.COMPLETED:
                update_dict["completedAt"] = datetime.now(timezone.utc).isoformat()
            elif task_data.status == TaskStatus.PENDING:
                # Reset timestamps when moving back to pending
                update_dict["startedAt"] = None
                update_dict["completedAt"] = None
        if task_data.dueDate is not None:
            update_dict["dueDate"] = task_data.dueDate.isoformat()
        
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        result = await db.tasks.update_one(
            {"id": task_id},
            {"$set": update_dict}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        return {"message": "Task updated successfully", "newStatus": task_data.status.value if task_data.status else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating task: {str(e)}"
        )

@router.put("/tasks/{task_id}/transition")
async def transition_task_status(
    task_id: str,
    transition_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Transition task to next logical status (pending -> in_progress -> completed)"""
    try:
        # Get current task
        task = await db.tasks.find_one({"id": task_id})
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        current_status = task.get("status", "pending")
        target_status = transition_data.get("status")
        
        # Define valid transitions
        valid_transitions = {
            "pending": ["in_progress", "completed", "cancelled"],
            "in_progress": ["completed", "pending", "cancelled"],
            "completed": ["pending"],
            "cancelled": ["pending"]
        }
        
        if target_status not in valid_transitions.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transition from '{current_status}' to '{target_status}'"
            )
        
        update_dict = {"status": target_status}
        
        if target_status == "in_progress":
            update_dict["startedAt"] = datetime.now(timezone.utc).isoformat()
        elif target_status == "completed":
            update_dict["completedAt"] = datetime.now(timezone.utc).isoformat()
        elif target_status == "pending":
            update_dict["startedAt"] = None
            update_dict["completedAt"] = None
        
        await db.tasks.update_one(
            {"id": task_id},
            {"$set": update_dict}
        )
        
        return {
            "message": f"Task transitioned from '{current_status}' to '{target_status}'",
            "previousStatus": current_status,
            "newStatus": target_status
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error transitioning task: {str(e)}"
        )

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    current_admin: str = Depends(get_current_admin)
):
    """Delete a task"""
    try:
        result = await db.tasks.delete_one({"id": task_id})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        return {"message": "Task deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting task: {str(e)}"
        )

# ================== WORKFLOW AUTOMATION ==================

async def generate_booking_tasks(booking_id: str, booking_status: str):
    """Auto-generate tasks based on booking status changes"""
    task_templates = {
        "pending": {
            "title": "Review and confirm new booking",
            "taskType": TaskType.CONFIRMATION,
            "priority": TaskPriority.HIGH,
            "days_due": 1
        },
        "confirmed": {
            "title": "Pre-service call - confirm details",
            "taskType": TaskType.PRE_MOVE_CHECK,
            "priority": TaskPriority.MEDIUM,
            "days_due": 2
        },
        "completed": {
            "title": "Post-service follow-up call",
            "taskType": TaskType.POST_SERVICE_FOLLOWUP,
            "priority": TaskPriority.LOW,
            "days_due": 3
        }
    }
    
    template = task_templates.get(booking_status)
    if template:
        task = Task(
            bookingId=booking_id,
            title=template["title"],
            taskType=template["taskType"],
            priority=template["priority"],
            dueDate=datetime.now(timezone.utc) + timedelta(days=template["days_due"]),
            autoGenerated=True
        )
        task_dict = task.model_dump()
        task_dict['dueDate'] = task_dict['dueDate'].isoformat() if task_dict['dueDate'] else None
        task_dict['completedAt'] = task_dict['completedAt'].isoformat() if task_dict['completedAt'] else None
        task_dict['createdAt'] = task_dict['createdAt'].isoformat()
        await db.tasks.insert_one(task_dict)

# Update the existing booking status endpoint to trigger task generation
@router.put("/bookings/{booking_id}/status-with-tasks")
async def update_booking_status_with_tasks(
    booking_id: str, 
    status_data: dict,
    current_admin: str = Depends(get_current_admin)
):
    """Update booking status and auto-generate workflow tasks"""
    try:
        new_status = status_data.get("status")
        if new_status not in ["pending", "confirmed", "completed", "cancelled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status"
            )
        
        result = await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"status": new_status, "updatedAt": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        # Auto-generate tasks based on new status
        await generate_booking_tasks(booking_id, new_status)
        
        return {"message": f"Booking updated to {new_status} and tasks generated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )

# ================== BOOKING DETAILS WITH FINANCIALS ==================

@router.get("/bookings/{booking_id}/details")
async def get_booking_details(
    booking_id: str,
    current_admin: str = Depends(get_current_admin)
):
    """Get full booking details including payments and tasks"""
    try:
        booking = await db.bookings.find_one({"id": booking_id})
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        if '_id' in booking:
            booking['_id'] = str(booking['_id'])
        
        # Get payments
        payments = await db.payments.find({"bookingId": booking_id}).to_list(100)
        for p in payments:
            if '_id' in p:
                p['_id'] = str(p['_id'])
        
        # Get tasks
        tasks = await db.tasks.find({"bookingId": booking_id}).to_list(100)
        for t in tasks:
            if '_id' in t:
                t['_id'] = str(t['_id'])
        
        # Calculate payment summary
        total_paid = sum(p.get('amount', 0) for p in payments if p.get('paymentType') != 'refund')
        total_refunded = sum(p.get('amount', 0) for p in payments if p.get('paymentType') == 'refund')
        total_cost = booking.get('totalCost', 0) or 0
        balance_due = total_cost - total_paid + total_refunded
        
        return {
            "booking": booking,
            "payments": payments,
            "tasks": tasks,
            "financials": {
                "totalCost": total_cost,
                "totalPaid": total_paid,
                "totalRefunded": total_refunded,
                "balanceDue": max(0, balance_due),
                "paymentStatus": "paid" if balance_due <= 0 and total_cost > 0 else "partial" if total_paid > 0 else "unpaid"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching booking details: {str(e)}"
        )

# ================== DATABASE RESET (DANGER ZONE) ==================

@router.delete("/reset-database")
async def reset_database(
    confirmation: dict,
    current_admin: str = Depends(get_current_admin)
):
    """
    Delete all records from the database. This action is irreversible.
    Requires confirmation text "DELETE ALL DATA" to proceed.
    """
    try:
        confirm_text = confirmation.get("confirmation")
        if confirm_text != "DELETE ALL DATA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmation text does not match. Please type 'DELETE ALL DATA' to confirm."
            )
        
        # Track what will be deleted
        counts = {
            "contacts": await db.contacts.count_documents({}),
            "bookings": await db.bookings.count_documents({}),
            "payments": await db.payments.count_documents({}),
            "tasks": await db.tasks.count_documents({}),
        }
        
        # Delete all records from each collection
        await db.contacts.delete_many({})
        await db.bookings.delete_many({})
        await db.payments.delete_many({})
        await db.tasks.delete_many({})
        
        return {
            "message": "Database reset successfully. All records have been deleted.",
            "deleted": counts,
            "total_deleted": sum(counts.values())
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resetting database: {str(e)}"
        )

@router.get("/database-stats")
async def get_database_stats(current_admin: str = Depends(get_current_admin)):
    """Get current record counts from all collections"""
    try:
        return {
            "contacts": await db.contacts.count_documents({}),
            "bookings": await db.bookings.count_documents({}),
            "payments": await db.payments.count_documents({}),
            "tasks": await db.tasks.count_documents({}),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching database stats: {str(e)}"
        )
