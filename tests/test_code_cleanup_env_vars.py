#!/usr/bin/env python3
"""
Test code cleanup and environment variable standardization
"""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_shared_managers_singleton():
    """Test that SharedManagers works as a singleton"""
    print("Testing SharedManagers singleton behavior...")
    
    try:
        from shared_managers import SharedManagers
        
        # Create two instances
        manager1 = SharedManagers()
        manager2 = SharedManagers()
        
        # Should be the same instance
        if manager1 is not manager2:
            print("❌ SharedManagers is not a singleton")
            return False
        
        print("✅ SharedManagers singleton behavior works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test singleton: {e}")
        return False

def test_shared_managers_proxy_manager():
    """Test SharedManagers ProxyManager creation"""
    print("Testing SharedManagers ProxyManager creation...")
    
    try:
        from shared_managers import SharedManagers
        
        # Mock environment variable
        with patch.dict(os.environ, {'OXYLABS_PROXY_CONFIG': '{"provider": "test", "host": "test.com", "port": 8080, "username": "user", "password": "pass", "protocol": "http"}'}):
            manager = SharedManagers()
            
            # Reset managers to ensure fresh creation
            manager.reset_managers()
            
            # Get proxy manager
            proxy_manager = manager.get_proxy_manager()
            
            if proxy_manager is None:
                print("❌ ProxyManager creation failed")
                return False
            
            # Should return the same instance on second call
            proxy_manager2 = manager.get_proxy_manager()
            
            if proxy_manager is not proxy_manager2:
                print("❌ ProxyManager not cached properly")
                return False
        
        print("✅ SharedManagers ProxyManager creation works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test ProxyManager creation: {e}")
        return False

def test_shared_managers_graceful_degradation():
    """Test SharedManagers graceful degradation with invalid config"""
    print("Testing SharedManagers graceful degradation...")
    
    try:
        from shared_managers import SharedManagers
        
        # Test with no config
        with patch.dict(os.environ, {'OXYLABS_PROXY_CONFIG': ''}, clear=False):
            manager = SharedManagers()
            manager.reset_managers()
            
            proxy_manager = manager.get_proxy_manager()
            
            # Should still return a ProxyManager instance (in degraded state)
            if proxy_manager is None:
                print("❌ ProxyManager should be created even with empty config")
                return False
            
            # Should not be in use
            if proxy_manager.in_use:
                print("❌ ProxyManager should not be in use with empty config")
                return False
        
        print("✅ SharedManagers graceful degradation works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test graceful degradation: {e}")
        return False

def test_transcript_service_shared_managers():
    """Test TranscriptService with shared managers"""
    print("Testing TranscriptService with shared managers...")
    
    try:
        from shared_managers import get_all_managers
        from transcript_service import TranscriptService
        
        # Get shared managers
        managers = get_all_managers()
        
        # Create TranscriptService with shared managers
        service = TranscriptService(shared_managers_dict=managers)
        
        # Should use the shared instances
        if service.proxy_manager is not managers['proxy_manager']:
            print("❌ TranscriptService not using shared ProxyManager")
            return False
        
        if service.http_client is not managers['proxy_http_client']:
            print("❌ TranscriptService not using shared ProxyHTTPClient")
            return False
        
        if service.user_agent_manager is not managers['user_agent_manager']:
            print("❌ TranscriptService not using shared UserAgentManager")
            return False
        
        print("✅ TranscriptService shared managers integration works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test TranscriptService integration: {e}")
        return False

def test_transcript_service_backwards_compatibility():
    """Test TranscriptService backwards compatibility without shared managers"""
    print("Testing TranscriptService backwards compatibility...")
    
    try:
        from transcript_service import TranscriptService
        
        # Create TranscriptService without shared managers (old way)
        service = TranscriptService(use_shared_managers=False)
        
        # Should still work (create its own managers)
        if service.proxy_manager is None and service.user_agent_manager is None:
            print("❌ TranscriptService failed to create managers in compatibility mode")
            return False
        
        print("✅ TranscriptService backwards compatibility works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test backwards compatibility: {e}")
        return False

def test_environment_variable_standardization():
    """Test that environment variables are standardized"""
    print("Testing environment variable standardization...")
    
    try:
        # Check key files for consistent usage
        files_to_check = [
            'google_auth.py',
            'token_manager.py'
        ]
        
        for file_path in files_to_check:
            if not os.path.exists(file_path):
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should use new format
            if 'GOOGLE_CLIENT_ID' not in content:
                print(f"❌ {file_path} missing GOOGLE_CLIENT_ID")
                return False
            
            if 'GOOGLE_CLIENT_SECRET' not in content:
                print(f"❌ {file_path} missing GOOGLE_CLIENT_SECRET")
                return False
            
            # Should not use old format
            if 'GOOGLE_OAUTH_CLIENT_ID' in content:
                print(f"❌ {file_path} still contains old GOOGLE_OAUTH_CLIENT_ID")
                return False
            
            if 'GOOGLE_OAUTH_CLIENT_SECRET' in content:
                print(f"❌ {file_path} still contains old GOOGLE_OAUTH_CLIENT_SECRET")
                return False
        
        print("✅ Environment variable standardization is correct")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test environment variables: {e}")
        return False

def test_migration_script_creation():
    """Test migration script creation"""
    print("Testing migration script creation...")
    
    try:
        from standardize_env_vars import create_migration_script
        
        # Create migration script
        script_path = create_migration_script()
        
        if not os.path.exists(script_path):
            print(f"❌ Migration script not created at {script_path}")
            return False
        
        # Check script content
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should contain mapping logic
        if 'GOOGLE_CLIENT_ID' not in content:
            print("❌ Migration script missing GOOGLE_CLIENT_ID mapping")
            return False
        
        if 'GOOGLE_CLIENT_SECRET' not in content:
            print("❌ Migration script missing GOOGLE_CLIENT_SECRET mapping")
            return False
        
        print("✅ Migration script creation works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test migration script: {e}")
        return False

def test_convenience_functions():
    """Test convenience functions for shared managers"""
    print("Testing convenience functions...")
    
    try:
        from shared_managers import get_proxy_manager, get_proxy_http_client, get_user_agent_manager, get_all_managers
        
        # Test individual functions
        proxy_manager = get_proxy_manager()
        http_client = get_proxy_http_client()
        ua_manager = get_user_agent_manager()
        all_managers = get_all_managers()
        
        # Should return instances (may be None for proxy if no config)
        if all_managers is None:
            print("❌ get_all_managers returned None")
            return False
        
        if 'proxy_manager' not in all_managers:
            print("❌ get_all_managers missing proxy_manager")
            return False
        
        if 'proxy_http_client' not in all_managers:
            print("❌ get_all_managers missing proxy_http_client")
            return False
        
        if 'user_agent_manager' not in all_managers:
            print("❌ get_all_managers missing user_agent_manager")
            return False
        
        print("✅ Convenience functions work correctly")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test convenience functions: {e}")
        return False

def test_no_code_duplication():
    """Test that code duplication has been eliminated"""
    print("Testing code duplication elimination...")
    
    try:
        # Check that TranscriptService can use shared managers
        from transcript_service import TranscriptService
        from shared_managers import get_all_managers
        
        # Create multiple TranscriptService instances with shared managers
        managers = get_all_managers()
        
        service1 = TranscriptService(shared_managers_dict=managers)
        service2 = TranscriptService(shared_managers_dict=managers)
        
        # Should use the same manager instances
        if service1.proxy_manager is not service2.proxy_manager:
            print("❌ Different TranscriptService instances not sharing ProxyManager")
            return False
        
        if service1.user_agent_manager is not service2.user_agent_manager:
            print("❌ Different TranscriptService instances not sharing UserAgentManager")
            return False
        
        print("✅ Code duplication has been eliminated")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test code duplication: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing code cleanup and environment variable standardization...")
    print()
    
    tests = [
        test_shared_managers_singleton,
        test_shared_managers_proxy_manager,
        test_shared_managers_graceful_degradation,
        test_transcript_service_shared_managers,
        test_transcript_service_backwards_compatibility,
        test_environment_variable_standardization,
        test_migration_script_creation,
        test_convenience_functions,
        test_no_code_duplication
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
        print()
    
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Code cleanup and environment standardization is working correctly.")
        print("📝 Key features verified:")
        print("   - SharedManagers singleton pattern")
        print("   - ProxyManager, ProxyHTTPClient, UserAgentManager sharing")
        print("   - TranscriptService integration with shared managers")
        print("   - Backwards compatibility maintained")
        print("   - Environment variable standardization (GOOGLE_CLIENT_*)")
        print("   - Migration script for deployment rollout")
        print("   - Code duplication elimination")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Code cleanup needs fixes.")
        sys.exit(1)