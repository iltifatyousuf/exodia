import os
import sys
import operator
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# Ensure project root is on sys.path for package imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str

try:
    from langchain_ollama import ChatOllama
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import create_react_agent

    from ai_engine.tools.playbook_tools import block_ip_address, isolate_host
    from ai_engine.tools.qdrant_tools import search_past_breaches
    from ai_engine.tools.suricata_tools import generate_suricata_rule
    from ai_engine.tools.neo4j_tools import query_threat_graph
    from ai_engine.guardrails import evaluate_ai_confidence, send_to_human_review_queue

    MODEL_NAME = os.getenv("EXODIA_LLM_MODEL", "llama3.2")
    MODEL_TEMP = float(os.getenv("EXODIA_LLM_TEMPERATURE", "0"))
    llm = ChatOllama(model=MODEL_NAME, temperature=MODEL_TEMP)

    threat_tools = [search_past_breaches, query_threat_graph]
    threat_agent_node = create_react_agent(
        llm, tools=threat_tools,
        state_modifier="You are the Threat Analysis Agent. Use Qdrant to search for historical CVEs, and Neo4j to map complex threat actor/ASN relationships. Return a structured threat assessment."
    )

    remediation_tools = [block_ip_address, isolate_host, generate_suricata_rule]
    remediation_agent_node = create_react_agent(
        llm, tools=remediation_tools,
        state_modifier="You are the Remediation Agent. Based on the threat analysis, execute the appropriate SOAR playbook to block malicious IPs or isolate compromised hosts. If the attack is novel, generate a Suricata rule to block the specific payload pattern permanently."
    )

    compliance_agent_node = create_react_agent(
        llm, tools=[],
        state_modifier="You are the Compliance Agent. Map every remediation action to the relevant SOC2 (CC6.1 Logical Access) or ISO27001 control requirement. Return the compliance log entry."
    )

    def threat_node(state: AgentState):
        result = threat_agent_node.invoke({"messages": state["messages"]})
        return {
            "messages": [AIMessage(content=f"[Threat Agent]: {result['messages'][-1].content}")],
            "next_agent": "Guardrails"
        }

    def guardrails_node(state: AgentState):
        last_response = state["messages"][-1].content
        confidence_score = evaluate_ai_confidence(last_response)

        if confidence_score < 0.80:
            send_to_human_review_queue("Alert Data", last_response)
            return {
                "messages": [AIMessage(content="[Guardrails]: Confidence below threshold. Incident paused. Sent to Human-in-the-loop review queue.")],
                "next_agent": "Compliance"
            }
        else:
            return {
                "messages": [],
                "next_agent": "Remediation"
            }

    def remediation_node(state: AgentState):
        result = remediation_agent_node.invoke({"messages": state["messages"]})
        return {
            "messages": [AIMessage(content=f"[Remediation Agent]: {result['messages'][-1].content}")],
            "next_agent": "Compliance"
        }

    def compliance_node(state: AgentState):
        result = compliance_agent_node.invoke({"messages": state["messages"]})
        return {
            "messages": [AIMessage(content=f"[Compliance Agent]: {result['messages'][-1].content}")],
            "next_agent": "Supervisor"
        }

    def supervisor_node(state: AgentState):
        last_message = state["messages"][-1].content

        if "Compliance Agent" in last_message or "Human-in-the-loop" in last_message:
            return {"messages": [], "next_agent": "FINISH"}

        return {"messages": [], "next_agent": "Threat"}

    graph = StateGraph(AgentState)

    graph.add_node("Supervisor", supervisor_node)
    graph.add_node("Threat", threat_node)
    graph.add_node("Guardrails", guardrails_node)
    graph.add_node("Remediation", remediation_node)
    graph.add_node("Compliance", compliance_node)

    graph.set_entry_point("Supervisor")

    graph.add_conditional_edges(
        "Supervisor",
        lambda state: state["next_agent"],
        {"Threat": "Threat", "FINISH": END}
    )

    graph.add_conditional_edges(
        "Guardrails",
        lambda state: state["next_agent"],
        {"Remediation": "Remediation", "Compliance": "Compliance"}
    )

    graph.add_edge("Threat", "Guardrails")
    graph.add_edge("Remediation", "Compliance")
    graph.add_edge("Compliance", "Supervisor")

    workflow = graph.compile()

except Exception as e:
    print(f"[Error] Failed to initialize Multi-Agent Orchestrator: {e}")
    workflow = None
