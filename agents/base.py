"""
Base KYC Agent with MCP Tool Support

Provides the foundation for all KYC agents with:
- Shared LLM configuration
- MCP tool integration for external data access
- Structured output parsing
- Tool calling capabilities
"""

import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger("kyc.agents")


class BaseKYCAgent(ABC):
    """
    Base class for all KYC agents.
    
    Each agent has:
    - A system prompt defining its role and decision criteria
    - MCP servers providing tools for external data access
    - An invoke method that processes state and returns a structured response
    - JSON output parsing to extract decision, reason, checks, etc.
    """
    
    def __init__(
        self, 
        llm: Optional[AzureChatOpenAI] = None,
        mcp_servers: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the agent with optional LLM and MCP servers.
        
        Args:
            llm: LangChain LLM instance (creates default if not provided)
            mcp_servers: Dict of MCP server name -> server instance
        """
        if llm:
            self.llm = llm
        else:
            self.llm = self._create_default_llm()
        
        self.mcp_servers = mcp_servers or {}
    
    def _create_default_llm(self) -> AzureChatOpenAI:
        """Create the default Azure OpenAI LLM from environment variables."""
        return AzureChatOpenAI(
            azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            temperature=0.3,  # Lower temperature for more consistent decisions
            max_tokens=2000,
        )
    
    @property
    @abstractmethod
    def step_name(self) -> str:
        """Return the step name for this agent (e.g., 'intake', 'verification')."""
        pass
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt that defines this agent's behavior."""
        pass
    
    @property
    def available_tools(self) -> List[str]:
        """Return list of MCP tool names this agent can use. Override in subclass."""
        return []
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible tool definitions for available tools."""
        tools = []
        for tool_name in self.available_tools:
            # Parse server_name.tool_name format
            if "." in tool_name:
                server_name, tool = tool_name.split(".", 1)
            else:
                # Try to find tool in any server
                for sname, server in self.mcp_servers.items():
                    for t in server.get_tools():
                        if t["name"] == tool_name:
                            server_name, tool = sname, tool_name
                            break
                    else:
                        continue
                    break
                else:
                    continue
            
            server = self.mcp_servers.get(server_name)
            if not server:
                continue
            
            for t in server.get_tools():
                if t["name"] == tool:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": f"{server_name}__{t['name']}",
                            "description": t["description"],
                            "parameters": t["parameters"]
                        }
                    })
                    break
        
        return tools
    
    async def call_mcp_tool(self, full_tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool and return the result.
        
        Args:
            full_tool_name: Tool name in format "server__tool"
            arguments: Tool parameters
            
        Returns:
            Tool result dictionary
        """
        if "__" not in full_tool_name:
            return {"success": False, "error": f"Invalid tool name format: {full_tool_name}"}
        
        server_name, tool_name = full_tool_name.split("__", 1)
        
        server = self.mcp_servers.get(server_name)
        if not server:
            return {"success": False, "error": f"MCP server not found: {server_name}"}
        
        result = await server.call_tool(tool_name, arguments)
        return result.to_dict()
    
    def format_customer_data(self, customer_data: Dict[str, Any]) -> str:
        """Format customer data for inclusion in the prompt."""
        if not customer_data:
            return "No customer data provided yet."
        
        lines = []
        for key, value in customer_data.items():
            if key not in ['latest_message', 'conversation_history']:
                # Highlight important fields
                if key in ['date_of_birth', 'dob', 'address', 'consent']:
                    lines.append(f"  - **{key}**: {value} ✓")
                else:
                    lines.append(f"  - {key}: {value}")
        
        return "\n".join(lines) if lines else "No customer data provided yet."
    
    def format_conversation_history(self, messages: list) -> str:
        """Format conversation history for context."""
        if not messages:
            return "No prior conversation."
        
        # Take last 10 messages for context
        recent = messages[-10:]
        lines = []
        for msg in recent:
            role = getattr(msg, 'type', 'unknown')
            content = getattr(msg, 'content', str(msg))
            lines.append(f"{role.upper()}: {content}")
        
        return "\n".join(lines)
    
    def format_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        """Format tool call results for inclusion in the prompt."""
        if not tool_results:
            return ""
        
        lines = ["## Data Retrieved from Tools:"]
        for result in tool_results:
            tool_name = result.get("tool_name", "unknown")
            data = result.get("result", {})
            lines.append(f"\n### {tool_name}:")
            lines.append(f"```json\n{json.dumps(data, indent=2, default=str)}\n```")
        
        return "\n".join(lines)
    
    def parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the LLM response to extract structured JSON.
        Handles cases where response may include extra text around JSON.
        """
        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # If no valid JSON found, return a default REVIEW response
        logger.warning(f"Could not parse JSON from agent response: {response_text[:200]}")
        return {
            "stage": self.step_name,
            "decision": "REVIEW",
            "reason": response_text[:500] if response_text else "Unable to process request",
            "checks": [],
            "risk_level": "MEDIUM",
            "next_action": "need_more_info"
        }
    
    async def invoke(
        self,
        customer_data: Dict[str, Any],
        latest_message: str,
        conversation_history: list,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke the agent with the current state.
        
        This method supports agentic tool calling - the agent can request
        and use MCP tools to gather external data before making decisions.
        
        Args:
            customer_data: Dictionary of customer information
            latest_message: The most recent user message
            conversation_history: List of prior messages
            **kwargs: Additional context (unused by base, available for subclasses)
            
        Returns:
            Dictionary with: status, step, response (raw), parsed_decision, tool_calls
        """
        try:
            tool_results = []
            tools = self.get_tool_definitions()
            
            # Build the user prompt with context
            user_prompt = self.build_user_prompt(
                customer_data=customer_data,
                latest_message=latest_message,
                conversation_history=conversation_history,
            )
            
            # Initial messages
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=user_prompt),
            ]
            
            # Agentic loop - allow up to 3 rounds of tool calling
            max_iterations = 3
            for iteration in range(max_iterations):
                if tools and iteration == 0:
                    # First call with tools available
                    response = await self.llm.ainvoke(messages, tools=tools, tool_choice="auto")
                else:
                    # Subsequent calls or no tools
                    response = await self.llm.ainvoke(messages)
                
                # Check for tool calls
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    messages.append(response)
                    
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        logger.info(f"[{self.step_name}] Calling tool: {tool_name}")
                        
                        result = await self.call_mcp_tool(tool_name, tool_args)
                        tool_results.append({
                            "tool_name": tool_name,
                            "arguments": tool_args,
                            "result": result
                        })
                        
                        # Add tool result to messages
                        messages.append(ToolMessage(
                            content=json.dumps(result, default=str),
                            tool_call_id=tool_call["id"]
                        ))
                else:
                    # No more tool calls, we have final response
                    break
            
            response_text = response.content
            parsed = self.parse_response(response_text)
            
            logger.info(f"[{self.step_name}] Agent decision: {parsed.get('decision', 'UNKNOWN')}")
            if tool_results:
                logger.info(f"[{self.step_name}] Tools used: {len(tool_results)}")
            
            return {
                "status": "success",
                "step": self.step_name,
                "response": response_text,
                "parsed_decision": parsed,
                "tool_calls": tool_results
            }
            
        except Exception as e:
            logger.error(f"[{self.step_name}] Agent error: {str(e)}")
            return {
                "status": "error",
                "step": self.step_name,
                "response": f"Error processing request: {str(e)}",
                "error": str(e),
                "parsed_decision": {
                    "stage": self.step_name,
                    "decision": "REVIEW",
                    "reason": f"Agent error: {str(e)}",
                    "checks": [],
                    "risk_level": "MEDIUM",
                    "next_action": "need_more_info"
                },
                "tool_calls": []
            }
    
    @abstractmethod
    def build_user_prompt(
        self,
        customer_data: Dict[str, Any],
        latest_message: str,
        conversation_history: list,
    ) -> str:
        """
        Build the user prompt for the LLM.
        Each agent subclass implements this with its specific format.
        """
        pass
