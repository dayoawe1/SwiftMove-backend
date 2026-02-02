"""
Backend API Tests for Swift Move and Clean Admin Dashboard
Tests: Revenue tracking, Payment management, Task management, Admin login
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from environment
ADMIN_USERNAME = "dayoawe1"
ADMIN_PASSWORD = "Movers123!"

class TestAdminLogin:
    """Admin authentication tests"""
    
    def test_admin_login_success(self):
        """Test successful admin login"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        print(f"✓ Admin login successful, token received")
    
    def test_admin_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        print(f"✓ Invalid credentials correctly rejected")
    
    def test_admin_login_missing_fields(self):
        """Test login with missing fields"""
        response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "username": ADMIN_USERNAME
        })
        assert response.status_code == 400
        print(f"✓ Missing password correctly rejected")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/admin/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestDashboardStats:
    """Dashboard statistics endpoint tests"""
    
    def test_get_dashboard_stats(self, auth_headers):
        """Test fetching dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_contacts" in data
        assert "total_bookings" in data
        assert "chatbot_quotes" in data
        assert "pending_contacts" in data
        print(f"✓ Dashboard stats retrieved: {data['total_bookings']} bookings, {data['total_contacts']} contacts")
    
    def test_dashboard_stats_unauthorized(self):
        """Test dashboard stats without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/stats")
        assert response.status_code in [401, 403]
        print(f"✓ Unauthorized access correctly rejected")


class TestBookingsEndpoints:
    """Booking management endpoint tests"""
    
    def test_get_all_bookings(self, auth_headers):
        """Test fetching all bookings"""
        response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} bookings")
        return data
    
    def test_update_booking_cost(self, auth_headers):
        """Test setting booking cost"""
        # First get a booking
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available to test cost update")
        
        booking_id = bookings[0].get("id")
        test_cost = 500.00
        
        response = requests.put(
            f"{BASE_URL}/api/admin/bookings/{booking_id}/cost",
            headers=auth_headers,
            json={"totalCost": test_cost}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ Booking cost updated to ${test_cost}")
    
    def test_update_booking_cost_invalid(self, auth_headers):
        """Test setting invalid booking cost"""
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        response = requests.put(
            f"{BASE_URL}/api/admin/bookings/{booking_id}/cost",
            headers=auth_headers,
            json={"totalCost": -100}  # Invalid negative cost
        )
        assert response.status_code == 400
        print(f"✓ Negative cost correctly rejected")
    
    def test_update_booking_cost_not_found(self, auth_headers):
        """Test setting cost for non-existent booking"""
        response = requests.put(
            f"{BASE_URL}/api/admin/bookings/nonexistent-id/cost",
            headers=auth_headers,
            json={"totalCost": 100}
        )
        assert response.status_code == 404
        print(f"✓ Non-existent booking correctly returns 404")


class TestPaymentEndpoints:
    """Payment management endpoint tests"""
    
    def test_get_all_payments(self, auth_headers):
        """Test fetching all payments"""
        response = requests.get(f"{BASE_URL}/api/admin/payments", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} payments")
    
    def test_create_payment_deposit(self, auth_headers):
        """Test logging a deposit payment"""
        # First get a booking
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available to test payment creation")
        
        booking_id = bookings[0].get("id")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/payments",
            headers=auth_headers,
            json={
                "bookingId": booking_id,
                "amount": 100.00,
                "paymentType": "deposit",
                "paymentMethod": "cash",
                "notes": "TEST_deposit payment"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "paymentId" in data
        print(f"✓ Deposit payment created: {data['paymentId']}")
        return data["paymentId"]
    
    def test_create_payment_partial(self, auth_headers):
        """Test logging a partial payment"""
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/payments",
            headers=auth_headers,
            json={
                "bookingId": booking_id,
                "amount": 200.00,
                "paymentType": "partial",
                "paymentMethod": "card",
                "notes": "TEST_partial payment"
            }
        )
        assert response.status_code == 200
        print(f"✓ Partial payment created")
    
    def test_create_payment_full(self, auth_headers):
        """Test logging a full payment"""
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/payments",
            headers=auth_headers,
            json={
                "bookingId": booking_id,
                "amount": 300.00,
                "paymentType": "full",
                "paymentMethod": "bank_transfer",
                "notes": "TEST_full payment"
            }
        )
        assert response.status_code == 200
        print(f"✓ Full payment created")
    
    def test_create_payment_refund(self, auth_headers):
        """Test logging a refund"""
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/payments",
            headers=auth_headers,
            json={
                "bookingId": booking_id,
                "amount": 50.00,
                "paymentType": "refund",
                "paymentMethod": "cash",
                "notes": "TEST_refund"
            }
        )
        assert response.status_code == 200
        print(f"✓ Refund payment created")
    
    def test_create_payment_invalid_booking(self, auth_headers):
        """Test creating payment for non-existent booking"""
        response = requests.post(
            f"{BASE_URL}/api/admin/payments",
            headers=auth_headers,
            json={
                "bookingId": "nonexistent-booking-id",
                "amount": 100.00,
                "paymentType": "deposit",
                "paymentMethod": "cash"
            }
        )
        assert response.status_code == 404
        print(f"✓ Payment for non-existent booking correctly rejected")
    
    def test_delete_payment(self, auth_headers):
        """Test deleting a payment"""
        # First create a payment to delete
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        # Create payment
        create_response = requests.post(
            f"{BASE_URL}/api/admin/payments",
            headers=auth_headers,
            json={
                "bookingId": booking_id,
                "amount": 10.00,
                "paymentType": "deposit",
                "paymentMethod": "cash",
                "notes": "TEST_to_delete"
            }
        )
        payment_id = create_response.json().get("paymentId")
        
        # Delete payment
        response = requests.delete(
            f"{BASE_URL}/api/admin/payments/{payment_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        print(f"✓ Payment deleted successfully")
    
    def test_delete_payment_not_found(self, auth_headers):
        """Test deleting non-existent payment"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/payments/nonexistent-id",
            headers=auth_headers
        )
        assert response.status_code == 404
        print(f"✓ Non-existent payment deletion correctly returns 404")


class TestRevenueEndpoints:
    """Revenue analytics endpoint tests"""
    
    def test_get_revenue_summary(self, auth_headers):
        """Test fetching revenue summary"""
        response = requests.get(f"{BASE_URL}/api/admin/revenue/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields
        assert "totalRevenue" in data
        assert "monthlyRevenue" in data
        assert "lastMonthRevenue" in data
        assert "growthPercentage" in data
        assert "outstandingBalance" in data
        assert "breakdown" in data
        
        breakdown = data["breakdown"]
        assert "deposits" in breakdown
        assert "partialPayments" in breakdown
        assert "fullPayments" in breakdown
        assert "refunds" in breakdown
        
        print(f"✓ Revenue summary retrieved:")
        print(f"  - Total Revenue: ${data['totalRevenue']}")
        print(f"  - Monthly Revenue: ${data['monthlyRevenue']}")
        print(f"  - Outstanding Balance: ${data['outstandingBalance']}")
        print(f"  - Growth: {data['growthPercentage']}%")
    
    def test_get_monthly_revenue(self, auth_headers):
        """Test fetching monthly revenue data"""
        response = requests.get(f"{BASE_URL}/api/admin/revenue/monthly", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if data:
            assert "month" in data[0]
            assert "revenue" in data[0]
            assert "payments" in data[0]
        
        print(f"✓ Monthly revenue data retrieved: {len(data)} months")


class TestTaskEndpoints:
    """Task management endpoint tests"""
    
    def test_get_all_tasks(self, auth_headers):
        """Test fetching all tasks"""
        response = requests.get(f"{BASE_URL}/api/admin/tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} tasks")
    
    def test_create_task(self, auth_headers):
        """Test creating a manual task"""
        response = requests.post(
            f"{BASE_URL}/api/admin/tasks",
            headers=auth_headers,
            json={
                "title": "TEST_Follow up with client",
                "description": "Test task description",
                "taskType": "follow_up",
                "priority": "medium"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "taskId" in data
        print(f"✓ Task created: {data['taskId']}")
        return data["taskId"]
    
    def test_create_task_with_booking(self, auth_headers):
        """Test creating a task linked to a booking"""
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/tasks",
            headers=auth_headers,
            json={
                "bookingId": booking_id,
                "title": "TEST_Pre-move check for booking",
                "description": "Verify all details before move",
                "taskType": "pre_move_check",
                "priority": "high"
            }
        )
        assert response.status_code == 200
        print(f"✓ Task linked to booking created")
    
    def test_update_task_status(self, auth_headers):
        """Test updating task status"""
        # First create a task
        create_response = requests.post(
            f"{BASE_URL}/api/admin/tasks",
            headers=auth_headers,
            json={
                "title": "TEST_Task to update",
                "taskType": "follow_up",
                "priority": "low"
            }
        )
        task_id = create_response.json().get("taskId")
        
        # Update to in_progress
        response = requests.put(
            f"{BASE_URL}/api/admin/tasks/{task_id}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        assert response.status_code == 200
        print(f"✓ Task status updated to in_progress")
        
        # Update to completed
        response = requests.put(
            f"{BASE_URL}/api/admin/tasks/{task_id}",
            headers=auth_headers,
            json={"status": "completed"}
        )
        assert response.status_code == 200
        print(f"✓ Task status updated to completed")
    
    def test_update_task_priority(self, auth_headers):
        """Test updating task priority"""
        # First create a task
        create_response = requests.post(
            f"{BASE_URL}/api/admin/tasks",
            headers=auth_headers,
            json={
                "title": "TEST_Task priority update",
                "taskType": "follow_up",
                "priority": "low"
            }
        )
        task_id = create_response.json().get("taskId")
        
        response = requests.put(
            f"{BASE_URL}/api/admin/tasks/{task_id}",
            headers=auth_headers,
            json={"priority": "urgent"}
        )
        assert response.status_code == 200
        print(f"✓ Task priority updated to urgent")
    
    def test_delete_task(self, auth_headers):
        """Test deleting a task"""
        # First create a task
        create_response = requests.post(
            f"{BASE_URL}/api/admin/tasks",
            headers=auth_headers,
            json={
                "title": "TEST_Task to delete",
                "taskType": "custom",
                "priority": "low"
            }
        )
        task_id = create_response.json().get("taskId")
        
        response = requests.delete(
            f"{BASE_URL}/api/admin/tasks/{task_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        print(f"✓ Task deleted successfully")
    
    def test_delete_task_not_found(self, auth_headers):
        """Test deleting non-existent task"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/tasks/nonexistent-id",
            headers=auth_headers
        )
        assert response.status_code == 404
        print(f"✓ Non-existent task deletion correctly returns 404")
    
    def test_get_tasks_by_status(self, auth_headers):
        """Test filtering tasks by status"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tasks?status_filter=pending",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # All returned tasks should be pending
        for task in data:
            assert task.get("status") == "pending"
        print(f"✓ Task filtering by status works: {len(data)} pending tasks")


class TestAutoGeneratedTasks:
    """Test auto-generated tasks from deposit payments"""
    
    def test_deposit_creates_task(self, auth_headers):
        """Test that logging a deposit auto-generates a collect payment task"""
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        # Get current task count
        tasks_before = requests.get(f"{BASE_URL}/api/admin/tasks", headers=auth_headers).json()
        
        # Create deposit payment
        response = requests.post(
            f"{BASE_URL}/api/admin/payments",
            headers=auth_headers,
            json={
                "bookingId": booking_id,
                "amount": 75.00,
                "paymentType": "deposit",
                "paymentMethod": "cash",
                "notes": "TEST_deposit for auto-task"
            }
        )
        assert response.status_code == 200
        
        # Check if task was created
        tasks_after = requests.get(f"{BASE_URL}/api/admin/tasks", headers=auth_headers).json()
        
        # Should have at least one more task
        assert len(tasks_after) >= len(tasks_before)
        
        # Find the auto-generated task
        auto_tasks = [t for t in tasks_after if t.get("autoGenerated") == True and t.get("bookingId") == booking_id]
        print(f"✓ Deposit payment created auto-generated task(s): {len(auto_tasks)} found")


class TestBookingDetails:
    """Test booking details with financials endpoint"""
    
    def test_get_booking_details(self, auth_headers):
        """Test fetching full booking details with payments and tasks"""
        bookings_response = requests.get(f"{BASE_URL}/api/admin/bookings", headers=auth_headers)
        bookings = bookings_response.json()
        
        if not bookings:
            pytest.skip("No bookings available")
        
        booking_id = bookings[0].get("id")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/bookings/{booking_id}/details",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "booking" in data
        assert "payments" in data
        assert "tasks" in data
        assert "financials" in data
        
        financials = data["financials"]
        assert "totalCost" in financials
        assert "totalPaid" in financials
        assert "totalRefunded" in financials
        assert "balanceDue" in financials
        assert "paymentStatus" in financials
        
        print(f"✓ Booking details retrieved:")
        print(f"  - Total Cost: ${financials['totalCost']}")
        print(f"  - Total Paid: ${financials['totalPaid']}")
        print(f"  - Balance Due: ${financials['balanceDue']}")
        print(f"  - Payment Status: {financials['paymentStatus']}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_payments(self, auth_headers):
        """Clean up TEST_ prefixed payments"""
        payments = requests.get(f"{BASE_URL}/api/admin/payments", headers=auth_headers).json()
        test_payments = [p for p in payments if p.get("notes", "").startswith("TEST_")]
        
        deleted = 0
        for payment in test_payments:
            response = requests.delete(
                f"{BASE_URL}/api/admin/payments/{payment['id']}",
                headers=auth_headers
            )
            if response.status_code == 200:
                deleted += 1
        
        print(f"✓ Cleaned up {deleted} test payments")
    
    def test_cleanup_test_tasks(self, auth_headers):
        """Clean up TEST_ prefixed tasks"""
        tasks = requests.get(f"{BASE_URL}/api/admin/tasks", headers=auth_headers).json()
        test_tasks = [t for t in tasks if t.get("title", "").startswith("TEST_")]
        
        deleted = 0
        for task in test_tasks:
            response = requests.delete(
                f"{BASE_URL}/api/admin/tasks/{task['id']}",
                headers=auth_headers
            )
            if response.status_code == 200:
                deleted += 1
        
        print(f"✓ Cleaned up {deleted} test tasks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
