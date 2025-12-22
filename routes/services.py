from fastapi import APIRouter, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models import Service, Testimonial, ServiceArea, CompanyStats

router = APIRouter(prefix="/services", tags=["services"])

# This will be injected by the main app
db = None

def set_database(database: AsyncIOMotorDatabase):
    global db
    db = database

@router.get("/", response_model=List[Service])
async def get_all_services():
    """Get all available services"""
    try:
        services = await db.services.find().to_list(1000)
        if not services:
            # Return default services if none exist in database
            return get_default_services()
        return [Service(**service) for service in services]
    except Exception as e:
        # Return default services on error
        return get_default_services()

@router.get("/testimonials", response_model=List[Testimonial])
async def get_testimonials():
    """Get all customer testimonials"""
    try:
        testimonials = await db.testimonials.find({"verified": True}).sort("createdAt", -1).to_list(1000)
        if not testimonials:
            # Return default testimonials if none exist
            return get_default_testimonials()
        return [Testimonial(**testimonial) for testimonial in testimonials]
    except Exception as e:
        # Return default testimonials on error
        return get_default_testimonials()

@router.get("/areas", response_model=List[ServiceArea])
async def get_service_areas():
    """Get all service areas"""
    try:
        areas = await db.service_areas.find({"active": True}).to_list(1000)
        if not areas:
            # Return default areas if none exist
            return get_default_service_areas()
        return [ServiceArea(**area) for area in areas]
    except Exception as e:
        # Return default areas on error
        return get_default_service_areas()

@router.get("/stats", response_model=CompanyStats)
async def get_company_stats():
    """Get company statistics"""
    try:
        stats = await db.company_stats.find_one()
        if not stats:
            # Return default stats if none exist
            return get_default_stats()
        return CompanyStats(**stats)
    except Exception as e:
        # Return default stats on error
        return get_default_stats()

def get_default_services():
    """Default services data"""
    return [
        Service(
            id="1",
            title="Residential Moving",
            description="Complete home moving services with professional packing and careful handling.",
            price="Starting at $299",
            features=["Packing & Unpacking", "Furniture Assembly", "Fragile Item Protection", "Storage Solutions"],
            category="moving",
            popular=True
        ),
        Service(
            id="2",
            title="Commercial Moving",
            description="Office relocations with minimal downtime and professional handling.",
            price="Custom Quote",
            features=["Office Equipment", "IT Setup", "Document Handling", "Weekend Service"],
            category="moving"
        ),
        Service(
            id="3",
            title="House Cleaning",
            description="Deep cleaning services for your old and new home.",
            price="Starting at $149",
            features=["Deep Cleaning", "Carpet Cleaning", "Window Cleaning", "Post-Construction"],
            category="cleaning"
        ),
        Service(
            id="4",
            title="Office Cleaning",
            description="Professional office cleaning services to maintain work environment.",
            price="Starting at $99",
            features=["Daily Cleaning", "Sanitization", "Floor Care", "Restroom Maintenance"],
            category="cleaning"
        )
    ]

def get_default_testimonials():
    """Default testimonials data"""
    return [
        Testimonial(
            id="1",
            name="Sarah Johnson",
            role="Homeowner",
            rating=5,
            text="SwiftMove made our family's relocation completely stress-free. The team was professional, careful with our belongings, and the cleaning service left our old home spotless. Highly recommend!",
            location="Downtown"
        ),
        Testimonial(
            id="2",
            name="Mike Chen",
            role="Business Owner",
            rating=5,
            text="Outstanding commercial moving service! They relocated our entire office over the weekend with zero downtime. The cleaning crew also did an amazing job preparing our new space.",
            location="Westside"
        ),
        Testimonial(
            id="3",
            name="Emily Rodriguez",
            role="Property Manager",
            rating=5,
            text="We use SwiftMove for all our tenant move-outs. Their cleaning service is thorough and reliable, always leaving units rent-ready. Great communication and fair pricing.",
            location="Eastside"
        ),
        Testimonial(
            id="4",
            name="David Thompson",
            role="Homeowner",
            rating=5,
            text="The team handled our fragile antiques with exceptional care. The packing service was worth every penny, and the post-move cleaning was impeccable. Professional from start to finish.",
            location="Northpark"
        )
    ]

def get_default_service_areas():
    """Default service areas data"""
    return [
        ServiceArea(id="1", name="Ohio"),
        ServiceArea(id="2", name="Kentucky"),
        ServiceArea(id="3", name="Indiana")
    ]

def get_default_stats():
    """Default company stats"""
    return CompanyStats(
        happyClients="500+",
        averageRating="5.0",
        yearsExperience="3+",
        completedMoves="1000+"
    )