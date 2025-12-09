"""
Base MCP Server Utilities

Provides shared functionality for all MCP servers including:
- Configuration management
- Logging setup
- Common data structures
"""

import os
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger("mcp_servers")


@dataclass
class ToolResult:
    """Standard result structure for MCP tool calls."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        return result


class BaseMCPServer(ABC):
    """
    Base class for MCP servers.
    
    Each server exposes tools that agents can call to interact
    with external systems.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"mcp_servers.{self.name}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the server name."""
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Return list of tool definitions.
        
        Each tool definition should have:
        - name: Tool identifier
        - description: What the tool does
        - parameters: JSON schema for parameters
        """
        pass
    
    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool and return the result.
        
        Args:
            tool_name: The tool to execute
            arguments: Tool parameters
            
        Returns:
            ToolResult with success status and data/error
        """
        pass


def get_env_or_raise(key: str) -> str:
    """Get environment variable or raise if not set."""
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Environment variable {key} is required but not set")
    return value


def get_env_or_default(key: str, default: str) -> str:
    """Get environment variable or return default."""
    return os.environ.get(key, default)
