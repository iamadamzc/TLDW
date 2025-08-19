#!/usr/bin/env python3
"""
Test script for code cleanup and environment variable standardization
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestEnvironmentVariableStandardization(unittest.TestCase):
    """Test environment variable standardization for Google OAuth"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear any existing Google OAuth environment variables
        for var in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 
                   'GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET']:
            if var in os.environ:
                del os.environ[var]
    
    def tearDown(self):
        """Clean up test environment"""
        # Clear test environment variables
        for var in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 
                   'GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET']:
            if var in os.environ:
                del os.environ[var]
    
    def test_google_auth_uses_new_variables(self):
        """Test that google_auth.py uses new standardized variable names"""
        # Set new standardized variables
        os.environ['GOOGLE_CLIENT_ID'] = 'test-client-id'
        os.environ['GOOGLE_CLIENT_SECRET'] = 'test-client-secret'
        
        # Import google_auth module (this will execute the variable loading)
        import google_auth
        
        # Verify the module uses the new variables
        self.assertEqual(google_auth.GOOGLE_CLIENT_ID, 'test-client-id')
        self.assertEqual(google_auth.GOOGLE_CLIENT_SECRET, 'test-client-secret')
    
    def test_google_auth_backwards_compatibility(self):
        """Test that google_auth.py falls back to legacy variable names"""
        # Set only legacy variables
        os.environ['GOOGLE_OAUTH_CLIENT_ID'] = 'legacy-client-id'
        os.environ['GOOGLE_OAUTH_CLIENT_SECRET'] = 'legacy-client-secret'
        
        # Reload the module to test backwards compatibility
        if 'google_auth' in sys.modules:
            del sys.modules['google_auth']
        
        import google_auth
        
        # Verify the module falls back to legacy variables
        self.assertEqual(google_auth.GOOGLE_CLIENT_ID, 'legacy-client-id')
        self.assertEqual(google_auth.GOOGLE_CLIENT_SECRET, 'legacy-client-secret')
    
    def test_google_auth_new_variables_take_precedence(self):
        """Test that new variables take precedence over legacy ones"""
        # Set both new and legacy variables
        os.environ['GOOGLE_CLIENT_ID'] = 'new-client-id'
        os.environ['GOOGLE_CLIENT_SECRET'] = 'new-client-secret'
        os.environ['GOOGLE_OAUTH_CLIENT_ID'] = 'legacy-client-id'
        os.environ['GOOGLE_OAUTH_CLIENT_SECRET'] = 'legacy-client-secret'
        
        # Reload the module
        if 'google_auth' in sys.modules:
            del sys.modules['google_auth']
        
        import google_auth
        
        # Verify new variables take precedence
        self.assertEqual(google_auth.GOOGLE_CLIENT_ID, 'new-client-id')
        self.assertEqual(google_auth.GOOGLE_CLIENT_SECRET, 'new-client-secret')

class TestSharedManagersIntegration(unittest.TestCase):
    """Test shared managers eliminate duplication"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock the shared_managers to avoid actual initialization
        self.shared_managers_patcher = patch('shared_managers.shared_managers')
        self.mock_shared_managers = self.shared_managers_patcher.start()
        
        # Mock the manager instances
        self.mock_proxy_manager = MagicMock()
        self.mock_http_client = MagicMock()
        self.mock_user_agent_manager = MagicMock()
        
        self.mock_shared_managers.get_proxy_manager.return_value = self.mock_proxy_manager
        self.mock_shared_managers.get_proxy_http_client.return_value = self.mock_http_client
        self.mock_shared_managers.get_user_agent_manager.return_value = self.mock_user_agent_manager
    
    def tearDown(self):
        """Clean up test environment"""
        self.shared_managers_patcher.stop()
        
        # Clear any imported modules
        modules_to_clear = [mod for mod in sys.modules.keys() if 'transcript_service' in mod]
        for mod in modules_to_clear:
            del sys.modules[mod]
    
    def test_transcript_service_uses_shared_managers(self):
        """Test that TranscriptService uses shared managers by default"""
        # Set required environment variable
        os.environ['DEEPGRAM_API_KEY'] = 'test-key'
        
        try:
            from transcript_service import TranscriptService
            
            # Create TranscriptService instance
            service = TranscriptService()
            
            # Verify it uses shared managers
            self.assertEqual(service.proxy_manager, self.mock_proxy_manager)
            self.assertEqual(service.http_client, self.mock_http_client)
            self.assertEqual(service.user_agent_manager, self.mock_user_agent_manager)
            
            # Verify shared managers were called
            self.mock_shared_managers.get_proxy_manager.assert_called_once()
            self.mock_shared_managers.get_proxy_http_client.assert_called_once()
            self.mock_shared_managers.get_user_agent_manager.assert_called_once()
            
        finally:
            if 'DEEPGRAM_API_KEY' in os.environ:
                del os.environ['DEEPGRAM_API_KEY']
    
    def test_shared_managers_singleton_behavior(self):
        """Test that SharedManagers follows singleton pattern"""
        from shared_managers import SharedManagers
        
        # Create multiple instances
        instance1 = SharedManagers()
        instance2 = SharedManagers()
        
        # Verify they are the same instance
        self.assertIs(instance1, instance2)

class TestDeploymentScriptConsistency(unittest.TestCase):
    """Test deployment script environment variable consistency"""
    
    def test_migration_script_exists(self):
        """Test that migration script exists and is executable"""
        script_path = 'deployment/migrate-env-vars.sh'
        self.assertTrue(os.path.exists(script_path), f"Migration script {script_path} should exist")
        
        # Check if script is executable (on Unix systems)
        if os.name != 'nt':  # Not Windows
            self.assertTrue(os.access(script_path, os.X_OK), f"Migration script {script_path} should be executable")
    
    def test_migration_script_content(self):
        """Test that migration script has correct variable mappings"""
        script_path = 'deployment/migrate-env-vars.sh'
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Verify it maps the correct variables
        self.assertIn('GOOGLE_OAUTH_CLIENT_ID', content)
        self.assertIn('GOOGLE_OAUTH_CLIENT_SECRET', content)
        self.assertIn('GOOGLE_CLIENT_ID', content)
        self.assertIn('GOOGLE_CLIENT_SECRET', content)
        
        # Verify it has the correct mapping direction
        self.assertIn('GOOGLE_OAUTH_CLIENT_ID → GOOGLE_CLIENT_ID', content)
        self.assertIn('GOOGLE_OAUTH_CLIENT_SECRET → GOOGLE_CLIENT_SECRET', content)

def run_tests():
    """Run all tests"""
    print("🧪 Running Code Cleanup and Environment Variable Tests")
    print("=" * 60)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestEnvironmentVariableStandardization))
    suite.addTests(loader.loadTestsFromTestCase(TestSharedManagersIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestDeploymentScriptConsistency))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    if result.wasSuccessful():
        print("✅ All tests passed!")
        print()
        print("📋 Summary:")
        print("   - Environment variable standardization: ✅")
        print("   - Shared managers integration: ✅")
        print("   - Deployment script consistency: ✅")
        print("   - Backwards compatibility: ✅")
        return True
    else:
        print("❌ Some tests failed!")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)