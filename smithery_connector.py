import os
import sys
import json
import logging
import asyncio
import httpx
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("smithery_connector")


class SmitheryClient:
    """
    Client to connect to Smithery.ai hosted MCP servers
    Requires SMITHERY_API_KEY environment variable
    """
    
    def __init__(self):
        self.api_key = os.getenv("SMITHERY_API_KEY", "")
        if not self.api_key:
            logger.warning("SMITHERY_API_KEY not set - Smithery features will be limited")
        
        self.servers = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.registry_url = "https://registry.smithery.ai"
        self.server_base_url = "https://server.smithery.ai"
        
    async def search_servers(self, query, page=1, page_size=10):
        """Search for MCP servers in Smithery registry"""
        try:
            if not self.api_key:
                return {"error": "SMITHERY_API_KEY not set"}
            
            url = f"{self.registry_url}/servers"
            params = {
                "q": query,
                "page": page,
                "pageSize": page_size
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            }
            
            logger.info(f"Searching Smithery registry for: {query}")
            
            response = await self.http_client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "servers": data.get("servers", []),
                    "pagination": data.get("pagination", {})
                }
            else:
                return {"error": f"Search failed: {response.status_code}", "details": response.text}
                
        except Exception as e:
            logger.error(f"Error searching servers: {e}")
            return {"error": str(e)}
    
    async def get_server_info(self, qualified_name):
        """Get detailed info about a specific server (format: owner/repo)"""
        try:
            if not self.api_key:
                return {"error": "SMITHERY_API_KEY not set"}
            
            url = f"{self.registry_url}/servers/{qualified_name}"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            }
            
            logger.info(f"Getting server info: {qualified_name}")
            
            response = await self.http_client.get(url, headers=headers)
            
            if response.status_code == 200:
                return {"success": True, "server": response.json()}
            else:
                return {"error": f"Failed to get server info: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            return {"error": str(e)}
    
    async def connect_hosted_server(self, qualified_name, server_config):
        """
        Connect to a Smithery HOSTED server
        
        Args:
            qualified_name: Server name in format owner/repo (e.g., 'smithery-ai/github')
            server_config: Dict with server-specific config (e.g., {"githubPersonalAccessToken": "..."})
        """
        try:
            if not self.api_key:
                return {"error": "SMITHERY_API_KEY not set. Get one from https://smithery.ai"}
            
            server_url = f"{self.server_base_url}/@{qualified_name}"
            
            logger.info(f"Connecting to hosted Smithery server: {qualified_name}")
            logger.info(f"Server URL: {server_url}")
            
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "xiaozhi-reminder-server",
                        "version": "1.0.0"
                    }
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            if server_config:
                headers["X-Server-Config"] = json.dumps(server_config)
            
            response = await self.http_client.post(
                server_url,
                json=init_request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.servers[qualified_name] = {
                    "url": server_url,
                    "config": server_config,
                    "capabilities": result.get("result", {}),
                    "type": "hosted"
                }
                logger.info(f"Successfully connected to {qualified_name}")
                return {
                    "success": True,
                    "message": f"Connected to {qualified_name}",
                    "server_url": server_url,
                    "capabilities": result.get("result", {})
                }
            else:
                error_msg = f"Failed to connect: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"error": error_msg}
                
        except Exception as e:
            logger.error(f"Error connecting to {qualified_name}: {e}")
            return {"error": str(e)}
    
    async def list_tools(self, qualified_name):
        """List available tools from a connected server"""
        if qualified_name not in self.servers:
            return {"error": f"Server {qualified_name} not connected. Connect first."}
        
        try:
            server = self.servers[qualified_name]
            
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            if server.get("config"):
                headers["X-Server-Config"] = json.dumps(server["config"])
            
            response = await self.http_client.post(
                server["url"],
                json=request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                tools = result.get("result", {}).get("tools", [])
                return {
                    "success": True,
                    "server": qualified_name,
                    "count": len(tools),
                    "tools": tools
                }
            else:
                return {"error": f"Failed to list tools: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error listing tools from {qualified_name}: {e}")
            return {"error": str(e)}
    
    async def call_tool(self, qualified_name, tool_name, arguments):
        """Call a tool on a connected server"""
        if qualified_name not in self.servers:
            return {"error": f"Server {qualified_name} not connected. Connect first."}
        
        try:
            server = self.servers[qualified_name]
            
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            if server.get("config"):
                headers["X-Server-Config"] = json.dumps(server["config"])
            
            logger.info(f"Calling {tool_name} on {qualified_name}")
            
            response = await self.http_client.post(
                server["url"],
                json=request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "server": qualified_name,
                    "tool": tool_name,
                    "result": result.get("result", {})
                }
            else:
                return {
                    "error": f"Tool call failed: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"Error calling {tool_name} on {qualified_name}: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """Close connections"""
        await self.http_client.aclose()


smithery_client = SmitheryClient()


def smithery_search(query, page="1", page_size="10"):
    """
    Search for MCP servers in Smithery registry
    
    Args:
        query: Search term (e.g., 'github', 'web search', 'database')
        page: Page number (default: 1)
        page_size: Results per page (default: 10)
    
    Returns:
        JSON string with search results
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            smithery_client.search_servers(query, int(page), int(page_size))
        )
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in smithery_search: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def smithery_get_info(qualified_name):
    """
    Get detailed information about a Smithery server
    
    Args:
        qualified_name: Server name in format owner/repo (e.g., 'smithery-ai/github')
    
    Returns:
        JSON string with server details
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            smithery_client.get_server_info(qualified_name)
        )
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in smithery_get_info: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def smithery_connect(qualified_name, config_json="{}"):
    """
    Connect to a Smithery hosted MCP server
    
    Args:
        qualified_name: Server name in format owner/repo (e.g., 'smithery-ai/github')
        config_json: JSON string with server configuration (e.g., '{"githubPersonalAccessToken": "ghp_..."}')
    
    Returns:
        JSON string with connection status
    
    Example:
        smithery_connect('smithery-ai/github', '{"githubPersonalAccessToken": "ghp_abc123"}')
    """
    try:
        config = json.loads(config_json) if config_json else {}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            smithery_client.connect_hosted_server(qualified_name, config)
        )
        
        return json.dumps(result, indent=2)
            
    except Exception as e:
        logger.error(f"Error in smithery_connect: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def smithery_list_servers():
    """
    List all connected Smithery servers
    
    Returns:
        JSON string with list of connected servers
    """
    try:
        servers = []
        for name, info in smithery_client.servers.items():
            servers.append({
                "name": name,
                "url": info["url"],
                "type": info.get("type", "unknown"),
                "connected": True
            })
        
        return json.dumps({
            "success": True,
            "count": len(servers),
            "servers": servers
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error listing servers: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def smithery_list_tools(qualified_name):
    """
    List available tools from a connected Smithery server
    
    Args:
        qualified_name: Name of the connected server (e.g., 'smithery-ai/github')
    
    Returns:
        JSON string with list of tools
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            smithery_client.list_tools(qualified_name)
        )
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def smithery_call_tool(qualified_name, tool_name, arguments_json="{}"):
    """
    Call a tool on a connected Smithery server
    
    Args:
        qualified_name: Name of the connected server (e.g., 'smithery-ai/github')
        tool_name: Name of the tool to call
        arguments_json: JSON string with tool arguments
    
    Returns:
        JSON string with tool results
    """
    try:
        arguments = json.loads(arguments_json) if arguments_json else {}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            smithery_client.call_tool(qualified_name, tool_name, arguments)
        )
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error calling tool: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2)


if __name__ == "__main__":
    logger.info("Smithery Connector initialized")
    logger.info("Set SMITHERY_API_KEY environment variable to use Smithery features")
    logger.info("Get your API key from: https://smithery.ai")
