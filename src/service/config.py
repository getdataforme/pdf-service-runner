"""
Configuration Management

Handles loading and accessing configuration settings from YAML files
and environment variables.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

class Config:
    """
    Configuration manager for the PDF extraction service.
    
    Loads settings from config.yaml file with fallback to defaults.
    Supports environment variable overrides.
    """
    
    def __init__(self, config_file: str = 'config.yaml'):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to the YAML configuration file
        """
        self.config_file = config_file
        self.settings = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file with fallback to defaults.
        
        Returns:
            Dictionary containing all configuration settings
        """
        if not os.path.exists(self.config_file):
            print(f"Config file {self.config_file} not found, using defaults")
            return self._get_default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                # Merge with defaults to ensure all keys exist
                defaults = self._get_default_config()
                return self._deep_merge(defaults, config)
        except Exception as e:
            print(f"Error loading config from {self.config_file}: {e}")
            print("Using default configuration")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Return default configuration settings.
        
        Returns:
            Dictionary with default configuration values
        """
        return {
            "service": {
                "name": "PDF Extraction Service",
                "version": "1.0.0",
                "host": "0.0.0.0",
                "port": 8000,
                "debug": os.getenv("DEBUG", "false").lower() == "true",
                "reload": True,
                "workers": 1
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "file_rotation": "1 day",
                "file_retention": "7 days",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "extraction": {
                "max_concurrent_jobs": 5,
                "job_timeout_minutes": 30,
                "patterns_cache_ttl": 3600,
                "default_date_range_days": 365
            },
            "database": {
                "mongodb": {
                    "uri": os.getenv("MONGODB_CONNECTION_STRING"),
                    "database": "courts-database",
                    "collection": "allcourts",
                    "connection_timeout": 10000
                },
                "gcs": {
                    "bucket_name": os.getenv("GCS_BUCKET_NAME"),
                    "credentials_json": os.getenv("GCP_CREDENTIALS_JSON"),
                    "download_timeout": 300
                }
            },
            "paths": {
                "patterns_dir": "patterns",
                "pdfs_dir": "pdfs", 
                "outputs_dir": "outputs",
                "logs_dir": "logs",
                "temp_dir": "temp"
            },
            "defaults": {
                "county_name": "orange",
                "document_type": "complaint"
            }
        }

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key (supports dot notation).
        
        Args:
            key: Configuration key (e.g., 'service.port', 'logging.level')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.settings
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_service_config(self) -> Dict[str, Any]:
        """Get service-specific configuration."""
        return self.get('service', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.get('logging', {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return self.get('database', {})
    
    def get_paths_config(self) -> Dict[str, Any]:
        """Get paths configuration."""
        return self.get('paths', {})
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        paths = self.get_paths_config()
        for path_key, path_value in paths.items():
            if path_key.endswith('_dir'):
                Path(path_value).mkdir(parents=True, exist_ok=True)
    
    def validate_config(self) -> bool:
        """
        Validate that required configuration values are present.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        required_env_vars = ['MONGODB_CONNECTION_STRING', 'GCS_BUCKET_NAME', 'GCP_CREDENTIALS_JSON']
        missing_vars = []
        
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
        
        return True


# Global configuration instance
config = Config()