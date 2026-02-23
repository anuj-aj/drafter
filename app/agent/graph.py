from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from .state import AgentState
from .tools import build_tools
from .llm import get_llm_model
import logging

logger = logging.getLogger(__name__)


def build_graph(db, document_id, document_content):

    tools = build_tools(db, document_id)
    model = get_llm_model().bind_tools(tools)
    logger.debug(f"Building graph for document {document_id} with {len(tools)} tool(s)")

    def agent_node(state: AgentState):
        logger.debug(f"Agent node invoked for document {document_id}")
        system_prompt = SystemMessage(
            content=f"""
        You are Drafter AI.

        RULES:
        - The Current document content below is the BASE for all edits.
        - If the user wants to update the document, you MUST call the propose_update tool with the FULL updated content.
        - IMPORTANT: Preserve all existing content and add the user's requested changes ON TOP of it.
        - Never drop or lose prior edits.
        - Never claim the document was updated unless you called the propose_update tool.
        - Never fabricate version numbers.
        - Proposals are saved as drafts; the user will confirm to finalize.
        - If no update is required, respond normally.

        Current document content:
        {state['document_content']}
        """
        )

        messages = [system_prompt] + list(state["messages"])
        response = model.invoke(messages)

        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END
        }
    )
    graph.add_edge("tools", "agent")


    return graph.compile()

def should_continue(state: AgentState):
    messages = state["messages"]

    if not messages:
        return "end"

    last_message = messages[-1]

    # If LLM made a tool call
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"

    return "end"