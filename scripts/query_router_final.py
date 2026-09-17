import json
from sql_validator import validate_sql

# Tokenomics Tracker to log token usage across a 10-query test run
tokenomics_log = []

def mock_invoke_bedrock(prompt: str, task_type: str) -> dict:
    """
    Simulates Bedrock responses and token consumption securely
    while preserving exact output structures for routing and SQL generation.
    """
    input_tokens = len(prompt.split()) * 2
   
    if task_type == "routing":
        output_text = '{"route": "REDSHIFT", "reasoning": "Question asks for aggregate metrics and stream totals from structured data."}'
        output_tokens = 25
    elif task_type == "sql":
        output_text = "SELECT \"artist name\", SUM(total) FROM spotify GROUP BY \"artist name\" ORDER BY SUM(total) DESC LIMIT 3;"
        output_tokens = 30
    else:
        output_text = "Contextual response generated based on retrieved records."
        output_tokens = 40
       
    # Log tokenomics per call
    tokenomics_log.append({
        "task_type": task_type,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens
    })
   
    return {
        "text": output_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
    }

def process_query_pipeline(user_question: str):
    print(f"\n==================================================")
    print(f"Processing Query: '{user_question}'")
    print(f"==================================================")
   
    # 1. Routing Step
    routing_prompt = f"Classify question into REDSHIFT, OPENSEARCH, or BOTH: {user_question}"
    router_res = mock_invoke_bedrock(routing_prompt, "routing")
   
    try:
        route_data = json.loads(router_res['text'])
        route = route_data.get("route", "REDSHIFT")
    except Exception:
        route = "REDSHIFT"
       
    print(f"-> Routed to: {route}")
   
    # 2. SQL Translation Step (if Redshift)
    if route == "REDSHIFT":
        sql_prompt = f"Generate SQL for: {user_question}"
        sql_res = mock_invoke_bedrock(sql_prompt, "sql")
        generated_sql = sql_res['text']
        print(f"-> Generated SQL: {generated_sql}")
       
        # 3. Mandatory SQL Validation Step
        validation = validate_sql(generated_sql)
        print(f"-> SQL Validation Status: Valid = {validation['valid']} ({validation['reason']})")
       
        if validation['valid']:
            print("-> Execution Status: Query approved and ready for warehouse execution.")
        else:
            print("-> Execution Status: Query BLOCKED by security validator.")

def run_10_query_tokenomics_test():
    print("\n--- Starting 10-Query Test Run & Tokenomics Tracking ---")
    sample_queries = [
        "What are the top 3 most streamed songs?",
        "Show me all tracks by The Weeknd.",
        "What is our current customer churn rate?",
        "List songs with peak streams over 50 million.",
        "What does our retention strategy document state?",
        "Check Glue catalog for missing metadata fields.",
        "Give me the average chart duration across all songs.",
        "Find songs that stayed on the chart for over 50 weeks.",
        "Compare total streams between Ed Sheeran and Harry Styles.",
        "Summarize the data governance policy requirements."
    ]
   
    for q in sample_queries:
        process_query_pipeline(q)
       
    # Produce Cost Summary (Step 2.9 requirement)
    print("\n==================================================")
    print("           TOKENOMICS COST SUMMARY                ")
    print("==================================================")
    total_input = sum(item['input_tokens'] for item in tokenomics_log)
    total_output = sum(item['output_tokens'] for item in tokenomics_log)
    total_combined = total_input + total_output
   
    # Standard Claude 3 Haiku / Sonnet pricing approximation (e.g., $0.25/MTok input, $1.25/MTok output)
    estimated_cost = (total_input / 1_000_000 * 0.25) + (total_output / 1_000_000 * 1.25)
   
    print(f"Total Queries Tested : {len(sample_queries)}")
    print(f"Total API Calls Logged: {len(tokenomics_log)}")
    print(f"Total Input Tokens   : {total_input}")
    print(f"Total Output Tokens  : {total_output}")
    print(f"Combined Token Count : {total_combined}")
    print(f"Estimated Pipeline Cost: ${estimated_cost:.6f}")
    print("==================================================")

if __name__ == "__main__":
    run_10_query_tokenomics_test()
