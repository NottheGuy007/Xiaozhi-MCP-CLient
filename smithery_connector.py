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
    """Client to connect and interact with Smithery.ai hosted MCP servers"""
    
    def __init__(self):
        self.api_key = os.getenv("SMITHERY_API_KEY", "")
        self.servers = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
    async def connect_server(self, server_name, server_url, config=None):
        """Connect to a Smithery MCP server"""
        try:
            logger.info(f"Connecting to Smithery server: {server_name} at {server_url}")
            
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
                        "name": "xiaozhi-reminder-proxy",
                        "version": "1.0.0"
                    }
                }
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = await self.http_client.post(
                server_url,
                json=init_request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                self.servers[server_name] = {
                    "url": server_url,
                    "config": config or {},
                    "capabilities": result.get("result", {})
                }
                logger.info(f"Successfully connected to {server_name}")
                return True
            else:
                logger.error(f"Failed to connect to {server_name}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to {server_name}: {e}")
            return False
    
    async def list_tools(self, server_name):
        """List available tools from a Smithery server"""
        if server_name not in self.servers:
            return {"error": f"Server {server_name} not connected"}
        
        try:
            server = self.servers[server_name]
            
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = await self.http_client.post(
                server["url"],
                json=request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                tools = result.get("result", {}).get("tools", [])
                return {"success": True, "tools": tools}
            else:
                return {"error": f"Failed to list tools: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error listing tools from {server_name}: {e}")
            return {"error": str(e)}
    
    async def call_tool(self, server_name, tool_name, arguments):
        """Call a tool on a Smithery server"""
        if server_name not in self.servers:
            return {"error": f"Server {server_name} not connected"}
        
        try:
            server = self.servers[server_name]
            
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            logger.info(f"Calling tool {tool_name} on {server_name}")
            
            response = await self.http_client.post(
                server["url"],
                json=request,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("result", {})
            else:
                return {"error": f"Tool call failed: {response.status_code}", "details": response.text}
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """Close connections"""
        await self.http_client.aclose()


smithery_client = SmitheryClient()


def smithery_connect(server_name, server_url, config_json="{}"):
    """
    Connect to a Smithery.ai hosted MCP server
    
    Args:
        server_name: Friendly name for the server (e.g., 'exa', 'github')
        server_url: Full URL to the Smithery hosted server
        config_json: JSON string with server configuration
    
    Returns:
        JSON string with connection status
    """
    try:
        config = json.loads(config_json) if config_json else {}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        success = loop.run_until_complete(
            smithery_client.connect_server(server_name, server_url, config)
        )
        
        if success:
            return json.dumps({
                "success": True,
                "message": f"Connected to Smithery server: {server_name}",
                "server_name": server_name,
                "url": server_url
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": f"Failed to connect to {server_name}"
            }, indent=2)
            
    except Exception as e:
        logger.error(f"Error in smithery_connect: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


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
                "connected": True
            })
        
        return json.dumps({
            "success": True,
            "count": len(servers),
            "servers": servers
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error listing servers: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


def smithery_list_tools(server_name):
    """
    List available tools from a connected Smithery server
    
    Args:
        server_name: Name of the connected server
    
    Returns:
        JSON string with list of tools
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            smithery_client.list_tools(server_name)
        )
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


def smithery_call_tool(server_name, tool_name, arguments_json="{}"):
    """
    Call a tool on a connected Smithery server
    
    Args:
        server_name: Name of the connected server
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
            smithery_client.call_tool(server_name, tool_name, arguments)
        )
        
        return json.dumps({
            "success": True,
            "server": server_name,
            "tool": tool_name,
            "result": result
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error calling tool: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)


if __name__ == "__main__":
    logger.info("Smithery Connector initialized")
    logger.info("Available functions: smithery_connect, smithery_list_servers, smithery_list_tools, smithery_call_tool")
