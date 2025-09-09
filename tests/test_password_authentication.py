"""
Tests for password authentication functionality.
"""
import pytest
import tempfile
import json
import bcrypt
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask import Flask

from app.user_management.factory import create_user_management_module
from app.user_management.models import UserData
from app.user_management.services import UserService


class TestPasswordAuthentication:
    """Test password authentication functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.user_data_dir = self.temp_dir / "user_data"
        self.user_data_dir.mkdir()
        
        # Create user management module
        self.user_module = create_user_management_module(
            user_data_dir=self.user_data_dir,
            admin_user_ids=["admin1", "admin2"]
        )
        self.user_service = self.user_module["service"]
        self.app = Flask(__name__)
        self.app.register_blueprint(self.user_module["blueprint"])
        
        # Add a simple index route for testing
        @self.app.route('/')
        def index():
            return "Index page"
        
        self.client = self.app.test_client()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        user_data = self.user_service.get_user_data("test_user")
        
        # Test setting password
        password = "test_password_123"
        user_data.set_password(password)
        
        # Verify password hash is stored
        data = user_data.load()
        assert "password_hash" in data
        assert data["password_hash"] is not None
        assert isinstance(data["password_hash"], str)
        
        # Test password verification
        assert user_data.check_password(password) is True
        assert user_data.check_password("wrong_password") is False
        assert user_data.check_password("") is False
        
        # Test has_password method
        assert user_data.has_password() is True
    
    def test_password_verification_with_bcrypt(self):
        """Test password verification using bcrypt directly."""
        user_data = self.user_service.get_user_data("test_user")
        password = "secure_password_456"
        
        # Set password
        user_data.set_password(password)
        
        # Get stored hash
        data = user_data.load()
        stored_hash = data["password_hash"]
        
        # Verify with bcrypt directly
        assert bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')) is True
        assert bcrypt.checkpw("wrong".encode('utf-8'), stored_hash.encode('utf-8')) is False
    
    def test_password_removal(self):
        """Test password removal functionality."""
        user_data = self.user_service.get_user_data("test_user")
        
        # Set password first
        user_data.set_password("test_password")
        assert user_data.has_password() is True
        
        # Remove password
        user_data.remove_password()
        assert user_data.has_password() is False
        
        # Verify password hash is removed from data
        data = user_data.load()
        assert "password_hash" not in data or data["password_hash"] is None
    
    def test_user_service_password_methods(self):
        """Test UserService password management methods."""
        uid = "test_user"
        
        # Test setting password
        success = self.user_service.set_user_password(uid, "new_password")
        assert success is True
        
        user_data = self.user_service.get_user_data(uid)
        assert user_data.has_password() is True
        assert user_data.check_password("new_password") is True
        
        # Test changing password
        success = self.user_service.change_user_password(uid, "new_password", "updated_password")
        assert success is True
        
        assert user_data.check_password("updated_password") is True
        assert user_data.check_password("new_password") is False
        
        # Test changing password with wrong old password
        success = self.user_service.change_user_password(uid, "wrong_old", "another_password")
        assert success is False
        assert user_data.check_password("updated_password") is True  # Should remain unchanged
        
        # Test removing password
        success = self.user_service.remove_user_password(uid, "updated_password")
        assert success is True
        assert user_data.has_password() is False
    
    def test_password_authentication_for_admin_users(self):
        """Test password authentication requirements for admin users."""
        admin_uid = "admin1"
        
        # Admin user should require password even without setting one
        user_data = self.user_service.get_user_data(admin_uid)
        assert self.user_service.is_admin_user(admin_uid) is True
        
        # Test admin login without password (should fail)
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?error=invalid_password"
            response = self.client.post("/set_user", data={"uid": admin_uid})
            assert response.status_code == 302
            assert "error=invalid_password" in response.location
        
        # Test admin login with password
        user_data.set_password("admin_password")
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            response = self.client.post("/set_user", data={
                "uid": admin_uid,
                "password": "admin_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
    
    def test_password_authentication_for_regular_users(self):
        """Test password authentication for regular users."""
        regular_uid = "regular_user"
        
        # Regular user without password should login successfully
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?show_password_notification=true"
            response = self.client.post("/set_user", data={"uid": regular_uid})
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
            assert "show_password_notification=true" in response.location
        
        # Regular user with password should require password
        user_data = self.user_service.get_user_data(regular_uid)
        user_data.set_password("user_password")
        
        # Login without password should fail
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?error=invalid_password"
            response = self.client.post("/set_user", data={"uid": regular_uid})
            assert response.status_code == 302
            assert "error=invalid_password" in response.location
        
        # Login with correct password should succeed
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            response = self.client.post("/set_user", data={
                "uid": regular_uid,
                "password": "user_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
    
    def test_password_routes(self):
        """Test password-related API routes."""
        # Test password status route
        response = self.client.get("/password_status?uid=test_user")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "has_password" in data
        assert "is_admin" in data
        assert "requires_password" in data
        assert data["has_password"] is False
        assert data["is_admin"] is False
        assert data["requires_password"] is False
        
        # Test setting password
        response = self.client.post("/set_password", data={"password": "test_password"})
        assert response.status_code == 400  # No authenticated user
        
        # Test changing password
        response = self.client.post("/change_password", data={
            "old_password": "old", 
            "new_password": "new"
        })
        assert response.status_code == 400  # No authenticated user
        
        # Test removing password
        response = self.client.post("/remove_password", data={"password": "test_password"})
        assert response.status_code == 400  # No authenticated user
    
    def test_password_status_api_with_uid_parameter(self):
        """Test password status API with uid parameter."""
        uid = "test_user"
        
        # Test user without password
        response = self.client.get(f"/password_status?uid={uid}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["has_password"] is False
        assert data["is_admin"] is False
        assert data["requires_password"] is False
        
        # Set password and test again
        user_data = self.user_service.get_user_data(uid)
        user_data.set_password("test_password")
        
        response = self.client.get(f"/password_status?uid={uid}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["has_password"] is True
        assert data["is_admin"] is False
        assert data["requires_password"] is True
        
        # Test admin user
        admin_response = self.client.get("/password_status?uid=admin1")
        assert admin_response.status_code == 200
        admin_data = json.loads(admin_response.data)
        assert admin_data["is_admin"] is True
        assert admin_data["requires_password"] is True  # Admin always requires password
    
    def test_login_flow_with_password_errors(self):
        """Test login flow with various password error scenarios."""
        uid = "test_user"
        user_data = self.user_service.get_user_data(uid)
        user_data.set_password("correct_password")
        
        # Test login with wrong password
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?error=invalid_password"
            response = self.client.post("/set_user", data={
                "uid": uid,
                "password": "wrong_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" in response.location
        
        # Test login with correct password
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            response = self.client.post("/set_user", data={
                "uid": uid,
                "password": "correct_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
    
    def test_password_notification_for_new_users(self):
        """Test password notification for new users without passwords."""
        uid = "new_user"
        
        # Login new user without password
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?show_password_notification=true"
            response = self.client.post("/set_user", data={"uid": uid})
            assert response.status_code == 302
            assert "show_password_notification=true" in response.location
        
        # Admin users should not get notification
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            admin_response = self.client.post("/set_user", data={"uid": "admin1"})
            assert admin_response.status_code == 302
            assert "show_password_notification=true" not in admin_response.location
    
    def test_password_edge_cases(self):
        """Test password functionality edge cases."""
        user_data = self.user_service.get_user_data("test_user")
        
        # Test empty password
        with pytest.raises(ValueError):
            user_data.set_password("")
        
        # Test None password
        with pytest.raises(ValueError):
            user_data.set_password(None)
        
        # Test very long password
        long_password = "a" * 1000
        user_data.set_password(long_password)
        assert user_data.check_password(long_password) is True
        
        # Test special characters in password
        special_password = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        user_data.set_password(special_password)
        assert user_data.check_password(special_password) is True
        
        # Test unicode characters
        unicode_password = "密码123测试"
        user_data.set_password(unicode_password)
        assert user_data.check_password(unicode_password) is True
    
    def test_password_data_persistence(self):
        """Test that password data persists across UserData instances."""
        uid = "test_user"
        password = "persistent_password"
        
        # Set password with first instance
        user_data1 = self.user_service.get_user_data(uid)
        user_data1.set_password(password)
        
        # Create new instance and verify password persists
        user_data2 = self.user_service.get_user_data(uid)
        assert user_data2.has_password() is True
        assert user_data2.check_password(password) is True
        
        # Verify data is properly saved to file
        user_file = self.user_data_dir / f"{uid}.json"
        assert user_file.exists()
        
        with open(user_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        assert "password_hash" in saved_data
        assert saved_data["password_hash"] is not None
    
    def test_concurrent_password_operations(self):
        """Test concurrent password operations."""
        uid = "test_user"
        
        # Simulate concurrent password setting
        user_data1 = self.user_service.get_user_data(uid)
        user_data2 = self.user_service.get_user_data(uid)
        
        user_data1.set_password("password1")
        user_data2.set_password("password2")
        
        # The last operation should win
        final_user_data = self.user_service.get_user_data(uid)
        assert final_user_data.check_password("password2") is True
        assert final_user_data.check_password("password1") is False


class TestPasswordIntegration:
    """Integration tests for password functionality with the web app."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.user_data_dir = self.temp_dir / "user_data"
        self.user_data_dir.mkdir()
        
        # Create user management module
        self.user_module = create_user_management_module(
            user_data_dir=self.user_data_dir,
            admin_user_ids=["admin1", "admin2"]
        )
        self.user_service = self.user_module["service"]
        self.app = Flask(__name__)
        self.app.register_blueprint(self.user_module["blueprint"])
        
        # Add a simple index route for testing
        @self.app.route('/')
        def index():
            return "Index page"
        
        self.client = self.app.test_client()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_complete_password_workflow(self):
        """Test complete password workflow from setting to authentication."""
        uid = "workflow_user"
        
        # Step 1: User doesn't have password
        user_data = self.user_service.get_user_data(uid)
        assert user_data.has_password() is False
        
        # Step 2: Set password
        password = "workflow_password"
        success = self.user_service.set_user_password(uid, password)
        assert success is True
        assert user_data.has_password() is True
        
        # Step 3: Login with correct password
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            response = self.client.post("/set_user", data={
                "uid": uid,
                "password": password
            })
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
        
        # Step 4: Login with wrong password
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?error=invalid_password"
            response = self.client.post("/set_user", data={
                "uid": uid,
                "password": "wrong_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" in response.location
        
        # Step 5: Change password
        new_password = "new_workflow_password"
        success = self.user_service.change_user_password(uid, password, new_password)
        assert success is True
        
        # Step 6: Login with new password
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            response = self.client.post("/set_user", data={
                "uid": uid,
                "password": new_password
            })
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
        
        # Step 7: Remove password
        success = self.user_service.remove_user_password(uid, new_password)
        assert success is True
        assert user_data.has_password() is False
        
        # Step 8: Login without password (should work for non-admin)
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?show_password_notification=true"
            response = self.client.post("/set_user", data={"uid": uid})
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
    
    def test_admin_password_requirements(self):
        """Test that admin users always require password authentication."""
        admin_uid = "admin1"
        
        # Admin without password should fail login
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?error=invalid_password"
            response = self.client.post("/set_user", data={"uid": admin_uid})
            assert response.status_code == 302
            assert "error=invalid_password" in response.location
        
        # Set password for admin
        user_data = self.user_service.get_user_data(admin_uid)
        user_data.set_password("admin_password")
        
        # Admin with correct password should succeed
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            response = self.client.post("/set_user", data={
                "uid": admin_uid,
                "password": "admin_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
        
        # Admin with wrong password should fail
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?error=invalid_password"
            response = self.client.post("/set_user", data={
                "uid": admin_uid,
                "password": "wrong_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" in response.location
