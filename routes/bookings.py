from fastapi import APIRouter, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
import os
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models import (
    ServiceBooking, 
    ServiceBookingCreate, 
    ServiceBookingUpdate,
    BookingStatus
)

router = APIRouter(prefix="/bookings", tags=["bookings"])

# This will be injected by the main app
db = None

def set_database(database: AsyncIOMotorDatabase):
    global db
    db = database

@router.post("/", response_model=ServiceBooking, status_code=status.HTTP_201_CREATED)
async def create_booking(booking_data: ServiceBookingCreate):
    """Create a new service booking"""
    try:
        # Create booking object
        booking = ServiceBooking(**booking_data.dict())
        
        # Insert into database
        result = await db.bookings.insert_one(booking.dict())
        
        if result.inserted_id:
            # Return the created booking
            return booking
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create booking"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating booking: {str(e)}"
        )

@router.get("/", response_model=List[ServiceBooking])
async def get_all_bookings():
    """Get all bookings (admin endpoint)"""
    try:
        bookings = await db.bookings.find().sort("createdAt", -1).to_list(1000)
        return [ServiceBooking(**booking) for booking in bookings]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching bookings: {str(e)}"
        )

@router.get("/{booking_id}", response_model=ServiceBooking)
async def get_booking(booking_id: str):
    """Get a specific booking by ID"""
    try:
        booking = await db.bookings.find_one({"id": booking_id})
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        return ServiceBooking(**booking)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching booking: {str(e)}"
        )

@router.put("/{booking_id}", response_model=ServiceBooking)
async def update_booking(booking_id: str, update_data: ServiceBookingUpdate):
    """Update booking status"""
    try:
        update_dict = update_data.dict(exclude_unset=True)
        update_dict["updatedAt"] = datetime.utcnow()
        
        result = await db.bookings.update_one(
            {"id": booking_id},
            {"$set": update_dict}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        # Return updated booking
        updated_booking = await db.bookings.find_one({"id": booking_id})
        return ServiceBooking(**updated_booking)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating booking: {str(e)}"
        )

@router.delete("/{booking_id}")
async def cancel_booking(booking_id: str):
    """Cancel a booking (soft delete by updating status)"""
    try:
        result = await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"status": BookingStatus.CANCELLED, "updatedAt": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        return {"message": "Booking cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling booking: {str(e)}"
        )