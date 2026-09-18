import boto3
import json

from sql_validator import validate_sql

# Initialize Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
account_id = boto3.client("sts").get_caller_identity()["Account"]

# FIX: was using a bare model ID (anthropic.claude-3-haiku-20240307-v1:0),
# which does not match the inference-profile ARN pattern required for
# Claude models on Bedrock per the assignment's implementation note.
# Even with this fix, invocation is still blocked by the separate
# AWS Marketplace subscription permission issue documented in the README -
# this fix alone does not restore Bedrock access, it just removes a second,
# independent bug so the code is correct once that access is restored.
MODEL_ID = f"arn:aws:bedrock:us-east-1:{account_id}:inference-profile/us.anthropic.claude-sonnet-4-6"


def invoke_claude(prompt: str, max_tokens: int = 500) -> dict:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    result = json.loads(response["body"].read())
    return {
        "text": result["content"][0]["text"],
        "input_tokens": result["usage"]["input_tokens"],
        "output_tokens": result["usage"]["output_tokens"]
    }


def route_and_process_query(user_question: str):
    print(f"\n--- User Question: '{user_question}' ---")

    routing_prompt = f"""
    You are an intelligent router for a music analytics and document search system.
    Classify the following user question into one of three routing categories:
    - 'REDSHIFT' (for structured questions about metrics, stream counts, song ranks, artists)
    - 'OPENSEARCH' (for unstructured questions about lyrics, policy text, or qualitative descriptions)
    - 'BOTH' (for complex synthesis questions requiring both structured metrics and document/policy context)

    Return ONLY a JSON object with keys "route" (string) and "reasoning" (string).

    Question: {user_question}
    """

    router_res = invoke_claude(routing_prompt, max_tokens=200)
    print(f"Router Output Text: {router_res['text']}")

    try:
        cleaned_text = router_res['text'].strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:-3].strip()
        route_data = json.loads(cleaned_text)
        route = route_data.get("route", "REDSHIFT").upper()
    except Exception:
        route = "REDSHIFT"

    print(f"Determined Route: {route}")

    if route == "REDSHIFT":
        sql_prompt = f"""
        You are a SQL expert. Given a SQLite/Redshift table named 'spotify' with columns:
        'artist and title', 'wks', 't10', 'pk', 'x?', 'PkStreams', 'total', 'artist name', 'song name', 'lyrics'.
        Write a valid, safe SELECT SQL query to answer the user's question.
        Return ONLY the raw SQL query string, no markdown formatting.

        Question: {user_question}
        """
        sql_res = invoke_claude(sql_prompt, max_tokens=300)
        generated_sql = sql_res['text'].replace("```sql", "").replace("```", "").strip()
        print(f"Generated SQL: {generated_sql}")

        validation = validate_sql(generated_sql)
        print(f"SQL Validation Result: {validation}")

        if validation['valid']:
            print("Status: SQL passed validation and is safe for execution!")
        else:
            print(f"Status: SQL REJECTED - {validation['reason']}")


if __name__ == "__main__":
    test_question = "What are the top 3 most streamed songs by total streams?"
    route_and_process_query(test_question)