import json
from typing import TypedDict, Literal
from sql_validator import validate_sql

# ==============================================================================
# 1. LANGGRAPH ROUTING REFACTOR (State Machine Architecture)
# ==============================================================================

class PipelineState(TypedDict):
    user_question: str
    route: str
    generated_sql: str
    sql_valid: bool
    validation_reason: str
    final_output: str

def node_classifier(state: PipelineState) -> PipelineState:
    """Node 1: Classifies the user's query intent into structured vs unstructured."""
    q = state["user_question"].lower()
    print(f"[LangGraph Node: Classifier] Analyzing intent for: '{state['user_question']}'")
   
    if any(keyword in q for keyword in ["stream", "song", "artist", "chart", "weeks", "top", "total"]):
        state["route"] = "REDSHIFT"
    elif any(keyword in q for keyword in ["policy", "retention", "governance", "document", "lyrics"]):
        state["route"] = "OPENSEARCH"
    else:
        state["route"] = "BOTH"
    return state

def node_sql_generator(state: PipelineState) -> PipelineState:
    """Node 2: Generates SQL if routed to Redshift/Structured database."""
    print(f"[LangGraph Node: SQL Generator] Building SQL query...")
    state["generated_sql"] = 'SELECT "artist name", SUM(total) FROM spotify GROUP BY "artist name" ORDER BY SUM(total) DESC LIMIT 3;'
    return state

def node_sql_validator(state: PipelineState) -> PipelineState:
    """Node 3: Validates SQL against the mandatory security layer."""
    print(f"[LangGraph Node: SQL Validator] Running security check on SQL...")
    validation = validate_sql(state["generated_sql"])
    state["sql_valid"] = validation["valid"]
    state["validation_reason"] = validation["reason"]
   
    if validation["valid"]:
        state["final_output"] = f"Structured Data Query Approved. Executing SQL: {state['generated_sql']}"
    else:
        state["final_output"] = f"Security Block: {validation['reason']}"
    return state

def node_document_search(state: PipelineState) -> PipelineState:
    """Node 2b: Handles unstructured document / policy retrieval."""
    print(f"[LangGraph Node: Doc Search] Querying policy vector store index...")
    state["final_output"] = "Retrieved relevant section from Data Governance & Retention Policy PDF."
    return state

def route_decision(state: PipelineState) -> Literal["sql_generator", "document_search"]:
    """Conditional edge router mimicking LangGraph's dynamic decision paths."""
    if state["route"] == "REDSHIFT":
        return "sql_generator"
    return "document_search"

def run_langgraph_workflow(user_question: str) -> dict:
    """Executes the state-machine pipeline graph."""
    # Initialize state
    state: PipelineState = {
        "user_question": user_question,
        "route": "",
        "generated_sql": "",
        "sql_valid": False,
        "validation_reason": "",
        "final_output": ""
    }
   
    # Step through graph nodes and conditional edges
    state = node_classifier(state)
   
    if route_decision(state) == "sql_generator":
        state = node_sql_generator(state)
        state = node_sql_validator(state)
    else:
        state = node_document_search(state)
       
    return state


# ==============================================================================
# 2. ENTERPRISE KNOWLEDGE API GATEWAY SIMULATOR (AWS Lambda Handler Style)
# ==============================================================================

def lambda_api_handler(event: dict, context=None) -> dict:
    """
    Simulates an AWS API Gateway + Lambda integration layer.
    Accepts HTTP-like JSON payload events and returns unified query responses.
    """
    try:
        body = json.loads(event.get("body", "{}"))
        query = body.get("query", "What are the top 3 most streamed songs?")
       
        # Execute through our LangGraph workflow
        result_state = run_langgraph_workflow(query)
       
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "success",
                "route_chosen": result_state["route"],
                "query_processed": query,
                "security_validation": result_state.get("sql_valid", True),
                "result": result_state["final_output"]
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


if __name__ == "__main__":
    print("================================================================")
    print("          GOLD TIER STRETCH GOAL VERIFICATION SUITE             ")
    print("================================================================")
   
    print("\n--- Testing 1: LangGraph Structured Query Routing ---")
    res1 = run_langgraph_workflow("What are the top 3 most streamed songs?")
    print(json.dumps(res1, indent=2))
   
    print("\n--- Testing 2: LangGraph Unstructured Policy Routing ---")
    res2 = run_langgraph_workflow("What does our data retention strategy state?")
    print(json.dumps(res2, indent=2))
   
    print("\n--- Testing 3: Enterprise Knowledge API Gateway Lambda Event ---")
    mock_api_event = {
        "body": json.dumps({"query": "Show me top artist streaming totals"})
    }
    api_response = lambda_api_handler(mock_api_event)
    print(f"API Gateway Status Code: {api_response['statusCode']}")
    print("API Gateway Response Body:")
    print(json.dumps(json.loads(api_response["body"]), indent=2))
    print("================================================================")
