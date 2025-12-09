import os
import json
import logging
from typing import Dict, Any, List, TypedDict, Annotated, Literal, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import AzureChatOpenAI

# Import local agents
from agents import AGENT_REGISTRY

# Configure logging
logger = logging.getLogger("kyc.graph")

# MCP servers will be stored here after initialization
_mcp_servers: Dict[str, Any] = {}


def initialize_mcp_servers(servers: Dict[str, Any]):
    """
    Initialize MCP servers for agent use.
    Call this at application startup.
    
    Args:
        servers: Dict of server_name -> server instance
                 e.g., {"postgres": PostgresMCPServer(), "blob": BlobMCPServer(), ...}
    """
    global _mcp_servers
    _mcp_servers = servers
    logger.info(f"Initialized MCP servers: {list(servers.keys())}")


def get_mcp_servers() -> Dict[str, Any]:
    """Get the initialized MCP servers."""
    return _mcp_servers


# Define the state of the agent
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    customer_data: Dict[str, Any]
    next_step: str
    step_results: Dict[str, Any]
    session_id: str
    thread_ids: Dict[str, str]  # Kept for compatibility
    final_response: str
    routing_signal: str  # "GO" or "STOP"
    mcp_tool_calls: List[Dict[str, Any]]  # Track MCP tool usage


# Define the available steps
STEPS = ["intake", "verification", "eligibility", "recommendation", "compliance", "action"]


# Orchestrator Node
async def orchestrator_node(state: AgentState):
    """
    Decides the next step based on the current state and conversation history.
    """
    logger.info("Orchestrator node executing...")
    
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    # If the last message is from a human, we must run the current step's agent
    if isinstance(last_message, HumanMessage):
        logger.info("Last message is Human. Routing to current step.")
        return {"routing_signal": "GO"}
        
    # If the last message is from an AI, we check if we should advance or stop
    if isinstance(last_message, AIMessage):
        current_step = state.get("next_step", "intake")
        step_results = state.get("step_results", {})
        
        # Check if the current step passed
        passed = False
        if current_step in step_results:
            results = step_results[current_step]
            if results:
                last_result = results[-1]
                response_text = last_result.get("response", "")
                
                # Check for PASS in response
                if "PASS" in response_text and ("{" in response_text or "[" in response_text):
                    passed = True
                
                # Also check parsed_decision if available
                parsed = last_result.get("parsed_decision", {})
                if parsed.get("decision") == "PASS":
                    passed = True
        
        if passed:
            # Advance to next step
            try:
                current_idx = STEPS.index(current_step)
                if current_idx < len(STEPS) - 1:
                    next_step = STEPS[current_idx + 1]
                    logger.info(f"Step {current_step} passed. Moving to {next_step}.")
                    return {"next_step": next_step, "routing_signal": "GO"}
                else:
                    next_step = "FINISH"
                    logger.info(f"Workflow completed at step {current_step}.")
                    return {"next_step": "FINISH", "routing_signal": "STOP"}
            except ValueError:
                pass
        
        # If NOT passed (Review/Fail), we STOP and wait for user input.
        logger.info(f"Step {current_step} did not pass or requires input. Stopping.")
        return {"routing_signal": "STOP"}

    return {"routing_signal": "STOP"}


# Generic Agent Node Factory using Local Agents with MCP
def create_agent_node(step_name: str):
    async def agent_node(state: AgentState):
        logger.info(f"Executing local agent node: {step_name}")
        
        session_id = state.get("session_id")
        customer_data = state.get("customer_data", {})
        thread_ids = state.get("thread_ids", {})
        messages = state.get("messages", [])
        mcp_tool_calls = state.get("mcp_tool_calls", [])
        
        # Extract the latest user message
        latest_message = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                latest_message = msg.content
                break
        
        # Get the agent class from registry and instantiate with MCP servers
        agent_class = AGENT_REGISTRY.get(step_name)
        if not agent_class:
            logger.error(f"No agent registered for step: {step_name}")
            return {
                "messages": [AIMessage(content=f"Error: No agent available for step {step_name}")],
                "final_response": f"Error: No agent available for step {step_name}"
            }
        
        # Create agent with MCP servers injected
        agent = agent_class(mcp_servers=_mcp_servers)
        
        # Call the local agent (now with agentic tool-calling capability)
        result = await agent.invoke(
            customer_data=customer_data,
            latest_message=latest_message,
            conversation_history=messages[-10:],
        )
        
        response_content = result.get("response", "")
        
        # Track MCP tool calls made by this agent
        new_tool_calls = result.get("tool_calls", [])
        all_tool_calls = mcp_tool_calls + [
            {"step": step_name, **tc} for tc in new_tool_calls
        ]
        
        # Add agent response to messages
        new_messages = [AIMessage(content=response_content)]
        
        # Update step results
        current_results = state.get("step_results", {}).copy()
        if step_name not in current_results:
            current_results[step_name] = []
        current_results[step_name].append(result)
        
        logger.info(f"[{step_name}] Agent completed with decision: {result.get('parsed_decision', {}).get('decision', 'UNKNOWN')}")
        if new_tool_calls:
            logger.info(f"[{step_name}] MCP tools used: {len(new_tool_calls)}")
        
        return {
            "messages": new_messages,
            "thread_ids": thread_ids,
            "step_results": current_results,
            "final_response": response_content,
            "mcp_tool_calls": all_tool_calls
        }
    return agent_node


# Build the Graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("orchestrator", orchestrator_node)
for step in STEPS:
    workflow.add_node(step, create_agent_node(step))

# Define conditional routing
def route_next(state: AgentState) -> Literal["intake", "verification", "eligibility", "recommendation", "compliance", "action", "FINISH", "__end__"]:
    signal = state.get("routing_signal", "STOP")
    if signal == "STOP":
        return END
    
    next_step = state.get("next_step", "intake")
    if next_step == "FINISH":
        return END
        
    return next_step

# Add edges
# Start -> Orchestrator
workflow.set_entry_point("orchestrator")

# Orchestrator -> Agent or End
workflow.add_conditional_edges(
    "orchestrator",
    route_next,
    {
        "intake": "intake",
        "verification": "verification",
        "eligibility": "eligibility",
        "recommendation": "recommendation",
        "compliance": "compliance",
        "action": "action",
        "FINISH": END,
        END: END
    }
)

# Agent -> Orchestrator (Loop back to check if we should advance)
for step in STEPS:
    workflow.add_edge(step, "orchestrator")

# Compile the graph
app_graph = workflow.compile()
