import os
import sys
import json
import logging
import asyncio
import re
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("auto_connect_manager")


class AutoConnectManager:
    """
    Automatically connects to pre-configured MCP servers on startup
    """
    
    def __init__(self, config_file="servers_config.json"):
        self.config_file = Path(config_file)
        self.servers_config = []
        self.connected_servers = {}
        
    def load_config(self):
        """Load server configuration from JSON file"""
        try:
            if not self.config_file.exists():
                logger.warning(f"Config file not found: {self.config_file}")
                logger.info("Creating default config file...")
                self.create_default_config()
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                self.servers_config = config.get("servers", [])
            
            logger.info(f"Loaded {len(self.servers_config)} server configurations")
            return True
            
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return False
    
    def create_default_config(self):
        """Create a default configuration file"""
        default_config = {
            "servers": [
                {
                    "enabled": False,
                    "name": "whatsapp",
                    "type": "remote",
                    "qualified_name": "Quegenx/wapulse-whatsapp-mcp",
                    "url": "https://server.smithery.ai/@Quegenx/wapulse-whatsapp-mcp/mcp",
                    "params": {
                        "api_key": "${SMITHERY_API_KEY}",
                        "profile": "structural-finch-M804tv"
                    },
                    "description": "WhatsApp messaging server"
                }
            ]
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        logger.info(f"Created default config at {self.config_file}")
    
    def resolve_env_vars(self, value):
        """Replace ${VAR_NAME} with environment variable values"""
        if isinstance(value, str):
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, value)
            for var_name in matches:
                env_value = os.getenv(var_name, "")
                if not env_value:
                    logger.warning(f"Environment variable {var_name} not set")
                value = value.replace(f"${{{var_name}}}", env_value)
            return value
        elif isinstance(value, dict):
            return {k: self.resolve_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve_env_vars(item) for item in value]
        else:
            return value
    
    async def connect_server(self, server_config):
        """Connect to a single server"""
        try:
            name = server_config.get("name")
            qualified_name = server_config.get("qualified_name")
            url = server_config.get("url")
            
            logger.info(f"Connecting to server: {name} ({qualified_name})")
            
            # Import smithery client
            from smithery_connector import smithery_client
            
            # Resolve environment variables
            params = self.resolve_env_vars(server_config.get("params", {}))
            config = self.resolve_env_vars(server_config.get("config", {}))
            
            # Build URL with params if provided
            if params:
                query_string = "&".join([f"{k}={v}" for k, v in params.items()])
                full_url = f"{url}?{query_string}"
            else:
                full_url = url
            
            # Connect
            result = await smithery_client.connect_hosted_server(
                qualified_name,
                config,
                full_url
            )
            
            if result.get("success"):
                self.connected_servers[name] = {
                    "qualified_name": qualified_name,
                    "url": full_url,
                    "description": server_config.get("description", ""),
                    "status": "connected"
                }
                logger.info(f"✅ Successfully connected to {name}")
                return True
            else:
                logger.error(f"❌ Failed to connect to {name}: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error connecting to {name}: {e}")
            return False
    
    async def connect_all(self):
        """Connect to all enabled servers"""
        logger.info("=" * 60)
        logger.info("AUTO-CONNECTING TO PRE-CONFIGURED SERVERS")
        logger.info("=" * 60)
        
        if not self.load_config():
            logger.error("Failed to load configuration")
            return
        
        enabled_servers = [s for s in self.servers_config if s.get("enabled", False)]
        
        if not enabled_servers:
            logger.info("No servers enabled for auto-connect")
            logger.info("Edit servers_config.json to enable servers")
            return
        
        logger.info(f"Found {len(enabled_servers)} enabled server(s)")
        
        tasks = []
        for server_config in enabled_servers:
            tasks.append(self.connect_server(server_config))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        
        logger.info("=" * 60)
        logger.info(f"AUTO-CONNECT COMPLETE: {success_count}/{len(enabled_servers)} successful")
        logger.info("=" * 60)
        
        self.print_status()
    
    def print_status(self):
        """Print connection status"""
        if not self.connected_servers:
            logger.info("No servers connected")
            return
        
        logger.info("\n📡 CONNECTED SERVERS:")
        for name, info in self.connected_servers.items():
            logger.info(f"  ✅ {name}: {info['description']}")
            logger.info(f"     {info['qualified_name']}")
        logger.info("")
    
    def get_status(self):
        """Get connection status as JSON"""
        return json.dumps({
            "success": True,
            "total_configured": len(self.servers_config),
            "enabled": len([s for s in self.servers_config if s.get("enabled")]),
            "connected": len(self.connected_servers),
            "servers": self.connected_servers
        }, indent=2)


# Global instance
auto_connect_manager = AutoConnectManager()


def get_auto_connected_servers():
    """
    Get list of auto-connected servers
    
    Returns:
        JSON string with connected servers
    """
    return auto_connect_manager.get_status()


async def initialize_auto_connect():
    """Initialize auto-connect on server startup"""
    await auto_connect_manager.connect_all()


if __name__ == "__main__":
    logger.info("Auto-Connect Manager Test")
    asyncio.run(initialize_auto_connect())
