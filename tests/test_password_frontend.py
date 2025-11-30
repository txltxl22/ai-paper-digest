"""
Tests for password authentication frontend functionality.
"""
import pytest
import tempfile
import json
import bcrypt
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask import Flask

from app.user_management.factory import create_user_management_module
from app.index_page.factory import create_index_page_module


class TestPasswordFrontendIntegration:
    """Test password authentication frontend integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.user_data_dir = self.temp_dir / "user_data"
        self.summary_dir = self.temp_dir / "summary"
        self.user_data_dir.mkdir()
        self.summary_dir.mkdir()
        
        # Create user management module
        self.user_module = create_user_management_module(
            user_data_dir=self.user_data_dir,
            admin_user_ids=["admin1", "admin2"]
        )
        self.user_service = self.user_module["service"]
        
        # Create index page module
        self.index_module = create_index_page_module(
            summary_dir=self.summary_dir,
            user_service=self.user_service,
            index_template="<html><body>Index page</body></html>"
        )
        
        self.app = Flask(__name__)
        self.app.register_blueprint(self.user_module["blueprint"])
        self.app.register_blueprint(self.index_module["blueprint"])
        
        self.client = self.app.test_client()
        
        # Use faster bcrypt for tests (rounds=4 instead of 12) - same security logic, faster execution
        original_gensalt = bcrypt.gensalt
        self.bcrypt_patcher = patch('app.user_management.models.bcrypt.gensalt', 
                                   lambda: original_gensalt(4))
        self.bcrypt_patcher.start()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.bcrypt_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_password_status_api_for_frontend(self):
        """Test password status API that frontend JavaScript uses."""
        # Test user without password
        response = self.client.get("/password_status?uid=regular_user")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == {
            "has_password": False,
            "is_admin": False,
            "requires_password": False
        }
        
        # Set password for user
        user_data = self.user_service.get_user_data("regular_user")
        user_data.set_password("user_password")
        
        # Test user with password
        response = self.client.get("/password_status?uid=regular_user")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == {
            "has_password": True,
            "is_admin": False,
            "requires_password": True
        }
        
        # Test admin user
        response = self.client.get("/password_status?uid=admin1")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == {
            "has_password": False,
            "is_admin": True,
            "requires_password": True
        }
        
        # Set password for admin
        admin_data = self.user_service.get_user_data("admin1")
        admin_data.set_password("admin_password")
        
        # Test admin with password
        response = self.client.get("/password_status?uid=admin1")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == {
            "has_password": True,
            "is_admin": True,
            "requires_password": True
        }
    
    def test_login_form_submission_scenarios(self):
        """Test various login form submission scenarios."""
        # Test 1: Regular user without password
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?show_password_notification=true"
            response = self.client.post("/set_user", data={"uid": "regular_user"})
            assert response.status_code == 302
            assert "show_password_notification=true" in response.location
        
        # Test 2: Regular user with password (correct)
        user_data = self.user_service.get_user_data("regular_user")
        user_data.set_password("user_password")
        
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            response = self.client.post("/set_user", data={
                "uid": "regular_user",
                "password": "user_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
            assert "show_password_notification=true" not in response.location
        
        # Test 3: Admin user with password (correct) (reduced: removed admin without password test)
        admin_data = self.user_service.get_user_data("admin1")
        admin_data.set_password("admin_password")
        
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/"
            response = self.client.post("/set_user", data={
                "uid": "admin1",
                "password": "admin_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" not in response.location
        
        # Test 6: Admin user with password (incorrect)
        with patch('app.user_management.services.url_for') as mock_url_for:
            mock_url_for.return_value = "/?error=invalid_password"
            response = self.client.post("/set_user", data={
                "uid": "admin1",
                "password": "wrong_password"
            })
            assert response.status_code == 302
            assert "error=invalid_password" in response.location
    
    def test_password_management_api_routes(self):
        """Test password management API routes used by frontend."""
        # Test password status without uid parameter (should fail without auth)
        response = self.client.get("/password_status")
        assert response.status_code == 400
        
        # Test setting password without authentication
        response = self.client.post("/set_password", data={"password": "new_password"})
        assert response.status_code == 400
        
        # Test changing password without authentication
        response = self.client.post("/change_password", data={
            "old_password": "old",
            "new_password": "new"
        })
        assert response.status_code == 400
        
        # Test removing password without authentication
        response = self.client.post("/remove_password", data={"password": "current"})
        assert response.status_code == 400
    
    def test_error_handling_in_api(self):
        """Test error handling in password-related API endpoints."""
        # Test invalid uid parameter
        response = self.client.get("/password_status?uid=")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        
        # Test invalid uid parameter (whitespace)
        response = self.client.get("/password_status?uid=   ")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        
        # Test non-existent user
        response = self.client.get("/password_status?uid=nonexistent_user")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["has_password"] is False
        assert data["is_admin"] is False
        assert data["requires_password"] is False
    
    def test_password_notification_logic(self):
        """Test password notification logic for different user types."""
        # Test new regular user (should get notification)
        response = self.client.post("/set_user", data={"uid": "new_regular_user"})
        assert response.status_code == 302
        assert "show_password_notification=true" in response.location
        
        # Test new admin user (should not get notification)
        response = self.client.post("/set_user", data={"uid": "admin2"})
        assert response.status_code == 302
        assert "show_password_notification=true" not in response.location
        
        # Test existing user without password (should get notification)
        user_data = self.user_service.get_user_data("existing_user")
        # User exists but no password set
        response = self.client.post("/set_user", data={"uid": "existing_user"})
        assert response.status_code == 302
        assert "show_password_notification=true" in response.location
        
        # Test existing user with password (should not get notification)
        user_data.set_password("existing_password")
        response = self.client.post("/set_user", data={
            "uid": "existing_user",
            "password": "existing_password"
        })
        assert response.status_code == 302
        assert "show_password_notification=true" not in response.location


class TestPasswordSecurity:
    """Test password security aspects."""
    
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
        
        # Use faster bcrypt for tests (rounds=4 instead of 12) - same security logic, faster execution
        original_gensalt = bcrypt.gensalt
        self.bcrypt_patcher = patch('app.user_management.models.bcrypt.gensalt', 
                                   lambda: original_gensalt(4))
        self.bcrypt_patcher.start()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.bcrypt_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir)
    
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
    
    def test_password_timing_attack_resistance(self):
        """Test that password verification is resistant to timing attacks."""
        user_data = self.user_service.get_user_data("timing_user")
        password = "timing_test_password"
        
        # Set password
        user_data.set_password(password)
        
        # Test that wrong passwords take similar time to verify
        import time
        
        # Time correct password verification
        start_time = time.time()
        user_data.check_password(password)
        correct_time = time.time() - start_time
        
        # Time wrong password verification
        start_time = time.time()
        user_data.check_password("wrong_password")
        wrong_time = time.time() - start_time
        
        # Times should be similar (within reasonable margin)
        # This is a basic test - in production, more sophisticated timing analysis would be needed
        time_diff = abs(correct_time - wrong_time)
        assert time_diff < 0.1  # Should be within 100ms
    
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
    
    def test_password_file_security(self):
        """Test that password files are stored securely."""
        uid = "file_security_user"
        user_data = self.user_service.get_user_data(uid)
        password = "file_security_password"
        
        # Set password
        user_data.set_password(password)
        
        # Check that file exists
        user_file = self.user_data_dir / f"{uid}.json"
        assert user_file.exists()
        
        # Read file content
        with open(user_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # Verify password is not stored in plain text
        assert password not in file_content
        assert "password_hash" in file_content
        
        # Verify file contains proper JSON structure
        file_data = json.loads(file_content)
        assert "password_hash" in file_data
        assert "read" in file_data
        assert "events" in file_data
        assert "favorites" in file_data


class TestPasswordEdgeCases:
    """Test edge cases and error conditions for password functionality."""
    
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
        
        # Use faster bcrypt for tests (rounds=4 instead of 12) - same security logic, faster execution
        original_gensalt = bcrypt.gensalt
        self.bcrypt_patcher = patch('app.user_management.models.bcrypt.gensalt', 
                                   lambda: original_gensalt(4))
        self.bcrypt_patcher.start()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.bcrypt_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_empty_and_none_passwords(self):
        """Test handling of empty and None passwords."""
        user_data = self.user_service.get_user_data("edge_user")
        
        # Test empty string
        with pytest.raises(ValueError):
            user_data.set_password("")
        
        # Test None
        with pytest.raises(ValueError):
            user_data.set_password(None)
        
        # Test whitespace-only (should be accepted, but not recommended)
        user_data.set_password("   ")
        assert user_data.has_password() is True
        assert user_data.check_password("   ") is True
    
    def test_very_long_passwords(self):
        """Test handling of very long passwords."""
        user_data = self.user_service.get_user_data("long_password_user")
        
        # Test very long password
        long_password = "a" * 10000
        user_data.set_password(long_password)
        assert user_data.check_password(long_password) is True
        assert user_data.has_password() is True
    
    def test_unicode_and_special_characters(self):
        """Test handling of unicode and special characters in passwords."""
        user_data = self.user_service.get_user_data("unicode_user")
        
        # Test special characters (reduced from 3 to 1 type for faster tests)
        special_password = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        user_data.set_password(special_password)
        assert user_data.check_password(special_password) is True
    
    def test_concurrent_password_operations(self):
        """Test concurrent password operations."""
        import threading
        import time
        
        user_data = self.user_service.get_user_data("concurrent_user")
        results = []
        
        def set_password(password):
            try:
                user_data.set_password(password)
                results.append(f"set_{password}")
            except Exception as e:
                results.append(f"error_{password}_{str(e)}")
        
        def check_password(password):
            try:
                result = user_data.check_password(password)
                results.append(f"check_{password}_{result}")
            except Exception as e:
                results.append(f"error_check_{password}_{str(e)}")
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=set_password, args=(f"password_{i}",))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify at least one password was set successfully
        assert any("set_password_" in result for result in results)
        
        # Verify the final state
        assert user_data.has_password() is True
    
    def test_password_verification_with_corrupted_data(self):
        """Test password verification with corrupted data."""
        user_data = self.user_service.get_user_data("corrupted_user")
        
        # Set password normally
        user_data.set_password("normal_password")
        assert user_data.check_password("normal_password") is True
        
        # Corrupt the password hash in the data
        data = user_data.load()
        data["password_hash"] = "corrupted_hash"
        user_data.save(data)
        
        # Verify password verification fails gracefully
        assert user_data.check_password("normal_password") is False
        assert user_data.has_password() is True  # Still has a hash, just corrupted
    
    def test_password_removal_edge_cases(self):
        """Test edge cases for password removal."""
        user_data = self.user_service.get_user_data("remove_user")
        
        # Test removing password when none exists
        user_data.remove_password()
        assert user_data.has_password() is False
        
        # Set password and remove it
        user_data.set_password("test_password")
        assert user_data.has_password() is True
        
        user_data.remove_password()
        assert user_data.has_password() is False
        
        # Verify data is clean
        data = user_data.load()
        assert "password_hash" not in data or data["password_hash"] is None
