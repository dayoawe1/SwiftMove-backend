from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
import uuid
from enum import Enum

# Enums for status fields
class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ContactStatus(str, Enum):
    NEW = "new"
    READ = "read"
    REPLIED = "replied"

class QuoteStatus(str, Enum):
    PENDING = "pending"
    QUOTED = "quoted"
    ACCEPTED = "accepted"
    DECLINED = "declined"

class ServiceType(str, Enum):
    RESIDENTIAL_MOVING = "residential-moving"
    COMMERCIAL_MOVING = "commercial-moving"
    HOUSE_CLEANING = "house-cleaning"
    OFFICE_CLEANING = "office-cleaning"
    FULL_SERVICE = "full-service"

class MoveSize(str, Enum):
    STUDIO = "studio"
    TWO_BR = "2br"
    FOUR_BR = "4br"
    OFFICE_SMALL = "office-small"
    OFFICE_LARGE = "office-large"

class PreferredTime(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    FLEXIBLE = "flexible"

class ContactSubject(str, Enum):
    QUOTE = "quote"
    BOOKING = "booking"
    QUESTION = "question"
    COMPLAINT = "complaint"
    COMPLIMENT = "compliment"
    OTHER = "other"

# Base models
class ServiceBooking(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: EmailStr
    phone: str
    serviceType: ServiceType
    moveSize: Optional[MoveSize] = None
    currentAddress: str
    newAddress: Optional[str] = None
    preferredDate: datetime
    preferredTime: Optional[PreferredTime] = None
    specialRequests: Optional[str] = None
    status: BookingStatus = BookingStatus.PENDING
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class ServiceBookingCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    serviceType: ServiceType
    moveSize: Optional[MoveSize] = None
    currentAddress: str
    newAddress: Optional[str] = None
    preferredDate: datetime
    preferredTime: Optional[PreferredTime] = None
    specialRequests: Optional[str] = None

class ServiceBookingUpdate(BaseModel):
    status: Optional[BookingStatus] = None
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class ContactMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: EmailStr
    phone: Optional[str] = None
    subject: ContactSubject
    message: str
    status: ContactStatus = ContactStatus.NEW
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class ContactMessageCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    subject: ContactSubject
    message: str

class ContactMessageUpdate(BaseModel):
    status: Optional[ContactStatus] = None
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class QuoteRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: EmailStr
    phone: str
    serviceType: ServiceType
    moveSize: Optional[MoveSize] = None
    fromAddress: str
    toAddress: Optional[str] = None
    additionalServices: List[str] = []
    estimatedPrice: Optional[float] = None
    status: QuoteStatus = QuoteStatus.PENDING
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class QuoteRequestCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    serviceType: ServiceType
    moveSize: Optional[MoveSize] = None
    fromAddress: str
    toAddress: Optional[str] = None
    additionalServices: List[str] = []

class QuoteRequestUpdate(BaseModel):
    estimatedPrice: Optional[float] = None
    status: Optional[QuoteStatus] = None
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class Service(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    price: str
    features: List[str]
    category: str
    popular: bool = False

class Testimonial(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    role: str
    rating: int = Field(ge=1, le=5)
    text: str
    location: str
    verified: bool = True
    createdAt: datetime = Field(default_factory=datetime.utcnow)

class ServiceArea(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    active: bool = True

class CompanyStats(BaseModel):
    happyClients: str
    averageRating: str
    yearsExperience: str
    completedMoves: str

# Chat Models
class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sessionId: str
    message: str
    sender: str  # 'user' or 'bot'
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatMessageCreate(BaseModel):
    sessionId: str
    message: str

class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    lastActivity: datetime = Field(default_factory=datetime.utcnow)