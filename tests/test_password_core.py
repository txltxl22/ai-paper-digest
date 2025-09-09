"""
Simplified tests for password authentication functionality.
"""
import pytest
import tempfile
import json
import bcrypt
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.user_management.factory import create_user_management_module
from app.user_management.models import UserData
from app.user_management.services import UserService


class TestPasswordCoreFunctionality:
    """Test core password authentication functionality."""
    
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
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_password_hashing_and_verification(self):
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
    
    def test_admin_user_detection(self):
        """Test admin user detection."""
        assert self.user_service.is_admin_user("admin1") is True
        assert self.user_service.is_admin_user("admin2") is True
        assert self.user_service.is_admin_user("regular_user") is False
        assert self.user_service.is_admin_user("") is False
    
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
    
    def test_password_hash_security(self):
        """Test that password hashes are secure and not reversible."""
        user_data = self.user_service.get_user_data("security_user")
        password = "secure_password_123"
        
        # Set password
        user_data.set_password(password)
        
        # Get stored hash
        data = user_data.load()
        stored_hash = data["password_hash"]
        
        # Verify hash is not the plain password
        assert stored_hash != password
        assert len(stored_hash) > 50  # bcrypt hashes are long
        
        # Verify hash starts with bcrypt identifier
        assert stored_hash.startswith("$2b$")
        
        # Verify we can't reverse the hash
        assert stored_hash != password
        assert password not in stored_hash
    
    def test_password_storage_isolation(self):
        """Test that password data is properly isolated between users."""
        user1_data = self.user_service.get_user_data("user1")
        user2_data = self.user_service.get_user_data("user2")
        
        # Set different passwords
        user1_data.set_password("password1")
        user2_data.set_password("password2")
        
        # Verify isolation
        assert user1_data.check_password("password1") is True
        assert user1_data.check_password("password2") is False
        
        assert user2_data.check_password("password2") is True
        assert user2_data.check_password("password1") is False
        
        # Verify hashes are different
        data1 = user1_data.load()
        data2 = user2_data.load()
        assert data1["password_hash"] != data2["password_hash"]
    
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


class TestPasswordAPI:
    """Test password-related API functionality."""
    
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
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_password_status_logic(self):
        """Test password status logic without Flask context."""
        uid = "test_user"
        
        # Test user without password
        user_data = self.user_service.get_user_data(uid)
        assert user_data.has_password() is False
        assert self.user_service.is_admin_user(uid) is False
        
        # Set password and test again
        user_data.set_password("test_password")
        assert user_data.has_password() is True
        assert self.user_service.is_admin_user(uid) is False
        
        # Test admin user
        admin_data = self.user_service.get_user_data("admin1")
        assert admin_data.has_password() is False
        assert self.user_service.is_admin_user("admin1") is True
    
    def test_password_authentication_logic(self):
        """Test password authentication logic."""
        regular_uid = "regular_user"
        admin_uid = "admin1"
        
        # Regular user without password - should allow login
        user_data = self.user_service.get_user_data(regular_uid)
        assert not user_data.has_password()
        assert not self.user_service.is_admin_user(regular_uid)
        
        # Regular user with password - should require password
        user_data.set_password("user_password")
        assert user_data.has_password()
        assert user_data.check_password("user_password") is True
        assert user_data.check_password("wrong_password") is False
        
        # Admin user without password - should require password (admin always requires password)
        admin_data = self.user_service.get_user_data(admin_uid)
        assert not admin_data.has_password()
        assert self.user_service.is_admin_user(admin_uid)
        
        # Admin user with password - should require correct password
        admin_data.set_password("admin_password")
        assert admin_data.has_password()
        assert admin_data.check_password("admin_password") is True
        assert admin_data.check_password("wrong_password") is False
    
    def test_password_notification_logic(self):
        """Test password notification logic."""
        regular_uid = "regular_user"
        admin_uid = "admin1"
        
        # Regular user without password should get notification
        user_data = self.user_service.get_user_data(regular_uid)
        assert not user_data.has_password()
        assert not self.user_service.is_admin_user(regular_uid)
        # Should show notification for non-admin users without password
        
        # Admin user should not get notification
        admin_data = self.user_service.get_user_data(admin_uid)
        assert not admin_data.has_password()
        assert self.user_service.is_admin_user(admin_uid)
        # Should not show notification for admin users
    
    def test_password_error_scenarios(self):
        """Test various password error scenarios."""
        uid = "test_user"
        user_data = self.user_service.get_user_data(uid)
        user_data.set_password("correct_password")
        
        # Test various wrong passwords
        wrong_passwords = [
            "wrong_password",
            "correct_password ",
            " correct_password",
            "CORRECT_PASSWORD",
            "correct_passwor",
            "correct_passwordd",
            "",
            "123456",
            "password"
        ]
        
        for wrong_password in wrong_passwords:
            assert user_data.check_password(wrong_password) is False
        
        # Test correct password
        assert user_data.check_password("correct_password") is True
    
    def test_password_workflow(self):
        """Test complete password workflow."""
        uid = "workflow_user"
        
        # Step 1: User doesn't have password
        user_data = self.user_service.get_user_data(uid)
        assert user_data.has_password() is False
        
        # Step 2: Set password
        password = "workflow_password"
        success = self.user_service.set_user_password(uid, password)
        assert success is True
        assert user_data.has_password() is True
        
        # Step 3: Verify password works
        assert user_data.check_password(password) is True
        
        # Step 4: Change password
        new_password = "new_workflow_password"
        success = self.user_service.change_user_password(uid, password, new_password)
        assert success is True
        
        # Step 5: Verify new password works
        assert user_data.check_password(new_password) is True
        assert user_data.check_password(password) is False
        
        # Step 6: Remove password
        success = self.user_service.remove_user_password(uid, new_password)
        assert success is True
        assert user_data.has_password() is False
        
        # Step 7: Verify password is gone
        assert user_data.check_password(new_password) is False
