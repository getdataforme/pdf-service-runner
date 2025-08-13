"""
Environment Configuration Loader

Loads environment variables from the root .env file for the PDF service runner.
"""

import os
from pathlib import Path

def load_root_env():
    """
    Load environment variables from the root .env file.
    
    This ensures the PDF service runner uses the same configuration
    as the main application.
    """
    try:
        # Get the root directory (go up from pdf-service-runner/src/utils)
        current_dir = Path(__file__).parent
        root_dir = current_dir.parent.parent.parent  # Go up three levels from src/utils
        env_file = root_dir / '.env'
        
        if env_file.exists():
            print(f"Loading environment from: {env_file}")
            
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse key=value pairs
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        # Set environment variable
                        os.environ[key] = value
                        
                        # Map MONGODB_CONNECTION_STRING to MONGODB_CONNECTION_STRING for compatibility
                        if key == 'MONGODB_CONNECTION_STRING':
                            os.environ['MONGODB_CONNECTION_STRING'] = value
            
            print(f"Loaded environment variables from {env_file}")
            print(f"DATABASE_URL configured: {bool(os.getenv('DATABASE_URL'))}")
            print(f"MONGODB_CONNECTION_STRING configured: {bool(os.getenv('MONGODB_CONNECTION_STRING'))}")
            print(f"MONGODB_CONNECTION_STRING configured: {bool(os.getenv('MONGODB_CONNECTION_STRING'))}")
            print(f"GCS_BUCKET_NAME configured: {bool(os.getenv('GCS_BUCKET_NAME'))}")
            
        else:
            print(f"WARNING: No .env file found at {env_file}")
            print("WARNING: Using system environment variables only")
            
    except Exception as e:
        print(f"ERROR: Error loading .env file: {e}")
        print("ERROR: Using system environment variables only")

# Load environment variables when this module is imported
load_root_env()
