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
    serviceType: str  # Changed from ServiceType enum to string for flexibility
    moveSize: Optional[str] = None  # Changed from MoveSize enum to string for flexibility
    currentAddress: str
    newAddress: Optional[str] = None
    preferredDate: datetime
    preferredTime: Optional[str] = None  # Changed from PreferredTime enum to string for flexibility
    hoursNeeded: Optional[str] = None  # Added field
    specialRequests: Optional[str] = None
    status: BookingStatus = BookingStatus.PENDING
    totalCost: Optional[float] = None  # Admin-entered total cost for the job
    contractorCost: Optional[float] = None  # Cost paid to contractors (deducted from revenue)
    laborHours: Optional[float] = None  # Actual labor hours for the job
    convertedFromChatbot: Optional[str] = None  # ID of chatbot quote if converted
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

class ServiceBookingCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    serviceType: str  # Changed from ServiceType enum to string for flexibility
    moveSize: Optional[str] = None  # Changed from MoveSize enum to string for flexibility
    currentAddress: str
    newAddress: Optional[str] = None
    preferredDate: datetime
    preferredTime: Optional[str] = None  # Changed from PreferredTime enum to string for flexibility
    hoursNeeded: Optional[str] = None  # Added field
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
    source: Optional[str] = "contact_form"  # Source identifier: contact_form, chatbot, etc.
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

# Payment Models - for tracking deposits and payments against bookings
class PaymentType(str, Enum):
    DEPOSIT = "deposit"
    PARTIAL = "partial"
    FULL = "full"
    REFUND = "refund"

class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    CHECK = "check"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"

class Payment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bookingId: str  # Links to ServiceBooking
    amount: float
    paymentType: PaymentType
    paymentMethod: PaymentMethod
    notes: Optional[str] = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)

class PaymentCreate(BaseModel):
    bookingId: str
    amount: float
    paymentType: PaymentType
    paymentMethod: PaymentMethod
    notes: Optional[str] = None

# Task Models - for workflow-based task management linked to bookings
class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskType(str, Enum):
    FOLLOW_UP = "follow_up"
    CONFIRMATION = "confirmation"
    QUOTE_REVIEW = "quote_review"
    SCHEDULE_CALL = "schedule_call"
    SEND_INVOICE = "send_invoice"
    COLLECT_PAYMENT = "collect_payment"
    PRE_MOVE_CHECK = "pre_move_check"
    POST_SERVICE_FOLLOWUP = "post_service_followup"
    CUSTOM = "custom"

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bookingId: Optional[str] = None  # Links to ServiceBooking (can be null for general tasks)
    contactId: Optional[str] = None  # Links to Contact (for chatbot leads)
    title: str
    description: Optional[str] = None
    taskType: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dueDate: Optional[datetime] = None
    assignedTo: Optional[str] = None  # For future RBAC
    autoGenerated: bool = False  # True if system-generated from workflow
    # Denormalized fields for detailed view
    contactName: Optional[str] = None
    contactEmail: Optional[str] = None
    serviceType: Optional[str] = None
    serviceContext: Optional[str] = None  # Additional context about the service
    startedAt: Optional[datetime] = None  # When task moved to in_progress
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    completedAt: Optional[datetime] = None

class TaskCreate(BaseModel):
    bookingId: Optional[str] = None
    contactId: Optional[str] = None
    title: str
    description: Optional[str] = None
    taskType: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    dueDate: Optional[datetime] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    dueDate: Optional[datetime] = None
    completedAt: Optional[datetime] = None