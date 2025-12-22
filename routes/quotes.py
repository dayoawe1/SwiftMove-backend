from fastapi import APIRouter, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models import (
    QuoteRequest,
    QuoteRequestCreate,
    QuoteRequestUpdate,
    ServiceType,
    MoveSize
)

router = APIRouter(prefix="/quotes", tags=["quotes"])

# This will be injected by the main app
db = None

def set_database(database: AsyncIOMotorDatabase):
    global db
    db = database

def calculate_estimate(service_type: ServiceType, move_size: MoveSize = None, additional_services: List[str] = []) -> float:
    """Calculate pricing estimate based on service type and size"""
    base_prices = {
        ServiceType.RESIDENTIAL_MOVING: {"studio": 299, "2br": 599, "4br": 999},
        ServiceType.COMMERCIAL_MOVING: {"office-small": 799, "office-large": 1499},
        ServiceType.HOUSE_CLEANING: {"studio": 149, "2br": 229, "4br": 349},
        ServiceType.OFFICE_CLEANING: {"office-small": 99, "office-large": 199},
        ServiceType.FULL_SERVICE: {"studio": 399, "2br": 699, "4br": 1199}
    }
    
    # Get base price
    if service_type in base_prices and move_size and move_size.value in base_prices[service_type]:
        base_price = base_prices[service_type][move_size.value]
    else:
        # Default pricing
        base_price = 299
    
    # Add additional services
    additional_cost = len(additional_services) * 50
    
    return base_price + additional_cost

@router.post("/", response_model=QuoteRequest, status_code=status.HTTP_201_CREATED)
async def create_quote_request(quote_data: QuoteRequestCreate):
    """Create a new quote request"""
    try:
        # Calculate estimated price
        estimated_price = calculate_estimate(
            quote_data.serviceType, 
            quote_data.moveSize, 
            quote_data.additionalServices
        )
        
        # Create quote request object
        quote_dict = quote_data.dict()
        quote_dict["estimatedPrice"] = estimated_price
        quote = QuoteRequest(**quote_dict)
        
        # Insert into database
        result = await db.quotes.insert_one(quote.dict())
        
        if result.inserted_id:
            return quote
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create quote request"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating quote request: {str(e)}"
        )

@router.get("/", response_model=List[QuoteRequest])
async def get_all_quotes():
    """Get all quote requests (admin endpoint)"""
    try:
        quotes = await db.quotes.find().sort("createdAt", -1).to_list(1000)
        return [QuoteRequest(**quote) for quote in quotes]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching quotes: {str(e)}"
        )

@router.get("/{quote_id}", response_model=QuoteRequest)
async def get_quote_request(quote_id: str):
    """Get a specific quote request by ID"""
    try:
        quote = await db.quotes.find_one({"id": quote_id})
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quote request not found"
            )
        return QuoteRequest(**quote)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching quote request: {str(e)}"
        )

@router.put("/{quote_id}", response_model=QuoteRequest)
async def update_quote_request(quote_id: str, update_data: QuoteRequestUpdate):
    """Update quote request with pricing or status"""
    try:
        update_dict = update_data.dict(exclude_unset=True)
        update_dict["updatedAt"] = datetime.utcnow()
        
        result = await db.quotes.update_one(
            {"id": quote_id},
            {"$set": update_dict}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quote request not found"
            )
        
        # Return updated quote
        updated_quote = await db.quotes.find_one({"id": quote_id})
        return QuoteRequest(**updated_quote)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating quote request: {str(e)}"
        )