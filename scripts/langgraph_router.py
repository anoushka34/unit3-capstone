"""
langgraph_router.py

Fixes the Gold-tier LangGraph refactor: the original gold.py kept the
state-machine structure but still called the OLD hardcoded SQL generator
(same query for every question). This version wires the state machine to
the REAL differentiated logic from query_router_rulebased.py instead.
"""

import json
from typing import TypedDict, Literal
from sql_validator import validate_sql
from query_router_rulebased import (
    classify_intent,
    generate_sql,
    question_mentions_unavailable_data,
    handle_churn_query,
    handle_metadata_query,
    POLICY_PATH,
)
import pandas as pd

CSV_PATH = "data/data.csv"


class PipelineState(TypedDict):
    user_question: str
    route: str
    generated_sql: str
    sql_valid: bool
    validation_reason: str
    final_output: str


def node_classifier(state: PipelineState) -> PipelineState:
    print(f"[LangGraph Node: Classifier] Analyzing intent for: '{state['user_question']}'")
    state["route"] = classify_intent(state["user_question"])
    return state


def node_sql_generator(state: PipelineState) -> PipelineState:
    """Uses the REAL per-question SQL templates, not a fixed hardcoded query."""
    print("[LangGraph Node: SQL Generator] Building SQL query...")
    df = pd.read_csv(CSV_PATH)
    state["generated_sql"] = generate_sql(state["user_question"], df)
    return state


def node_sql_validator(state: PipelineState) -> PipelineState:
    print("[LangGraph Node: SQL Validator] Running security check on SQL...")
    validation = validate_sql(state["generated_sql"])
    state["sql_valid"] = validation["valid"]
    state["validation_reason"] = validation["reason"]
    if validation["valid"]:
        state["final_output"] = f"Structured Data Query Approved. Executing SQL: {state['generated_sql']}"
    else:
        state["final_output"] = f"Security Block: {validation['reason']}"
    return state


def node_document_search(state: PipelineState) -> PipelineState:
    print("[LangGraph Node: Doc Search] Querying policy document...")
    with open(POLICY_PATH) as f:
        policy_text = f.read()
    section = policy_text.split("2. DATA GOVERNANCE")[0].strip()
    state["final_output"] = f"Retrieved from Data Governance & Retention Policy: {section[:200]}..."
    return state


def node_both_synthesis(state: PipelineState) -> PipelineState:
    """Handles the two harder synthesis queries with real combined answers."""
    print("[LangGraph Node: Synthesis] Combining structured + document sources...")
    q = state["user_question"].lower()
    with open(POLICY_PATH) as f:
        policy_text = f.read()

    if "churn" in q:
        result = handle_churn_query(state["user_question"], policy_text)
    elif "metadata" in q:
        result = handle_metadata_query(state["user_question"], policy_text)
    else:
        gap = question_mentions_unavailable_data(state["user_question"])
        result = {"note": gap or "No dedicated synthesis handler for this question."}

    state["final_output"] = json.dumps(result, default=str)
    return state


def route_decision(state: PipelineState) -> Literal["sql_generator", "document_search", "both_synthesis"]:
    if state["route"] == "REDSHIFT":
        return "sql_generator"
    elif state["route"] == "BOTH":
        return "both_synthesis"
    return "document_search"


def run_langgraph_workflow(user_question: str) -> dict:
    state: PipelineState = {
        "user_question": user_question, "route": "", "generated_sql": "",
        "sql_valid": False, "validation_reason": "", "final_output": ""
    }
    state = node_classifier(state)
    decision = route_decision(state)

    if decision == "sql_generator":
        state = node_sql_generator(state)
        state = node_sql_validator(state)
    elif decision == "both_synthesis":
        state = node_both_synthesis(state)
    else:
        state = node_document_search(state)

    return state


if __name__ == "__main__":
    test_questions = [
        "What are the top 3 most streamed songs?",
        "Show me all tracks by The Weeknd.",
        "What does our data retention strategy state?",
        "Does our current customer churn rate align with what our documented retention strategy says we should be seeing?",
        "Based on our data governance policy documents, are any of the currently-ingested datasets missing required metadata fields?",
    ]

    for q in test_questions:
        print(f"\n{'='*60}\n{q}\n{'='*60}")
        result = run_langgraph_workflow(q)
        print(json.dumps({k: v for k, v in result.items() if k != "user_question"}, indent=2, default=str))