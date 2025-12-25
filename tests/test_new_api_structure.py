#!/usr/bin/env python3
"""
Test the actual structure of the new YouTube Transcript API
"""
import logging

logging.basicConfig(level=logging.INFO)

def test_api_structure():
    """Test the actual API structure"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        import inspect
        
        print("=== YouTube Transcript API 1.2.2 Structure ===")
        
        # Create instance
        api = YouTubeTranscriptApi()
        print(f"API instance type: {type(api)}")
        
        # Get all methods
        methods = [method for method in dir(api) if not method.startswith('_') and callable(getattr(api, method))]
        print(f"Available methods: {methods}")
        
        # Check each method signature
        for method_name in methods:
            method = getattr(api, method_name)
            try:
                sig = inspect.signature(method)
                print(f"{method_name}: {sig}")
            except Exception as e:
                print(f"{method_name}: Could not get signature - {e}")
        
        # Test with a simple video ID to see what happens
        test_video = "dQw4w9WgXcQ"  # Rick Roll
        
        print(f"\n=== Testing with video {test_video} ===")
        
        # Test list method
        try:
            print("Testing list() method...")
            result = api.list(test_video)
            print(f"list() returned type: {type(result)}")
            print(f"list() result: {result}")
            
            # If it's iterable, show first few items
            try:
                result_list = list(result)
                print(f"list() converted to list: {len(result_list)} items")
                if result_list:
                    print(f"First item: {result_list[0]}")
                    print(f"First item type: {type(result_list[0])}")
            except Exception as e:
                print(f"Could not convert to list: {e}")
                
        except Exception as e:
            print(f"list() method failed: {e}")
        
        # Test fetch method
        try:
            print("\nTesting fetch() method...")
            # Try with minimal parameters
            result = api.fetch(test_video)
            print(f"fetch() returned type: {type(result)}")
            print(f"fetch() result length: {len(result) if hasattr(result, '__len__') else 'no length'}")
            
            # Show first few items if it's a list
            if hasattr(result, '__iter__') and not isinstance(result, str):
                try:
                    result_list = list(result)[:3]  # First 3 items
                    print(f"First few items: {result_list}")
                except:
                    print(f"Result preview: {str(result)[:200]}...")
            else:
                print(f"Result preview: {str(result)[:200]}...")
                
        except Exception as e:
            print(f"fetch() method failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"API structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_api_structure()