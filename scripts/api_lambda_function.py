"""
api_lambda_function.py

Deploy this AS Lambda code (like lambda_function.py was for Textract).
This is the REAL Gold-tier "Enterprise Knowledge API" - the original
gold.py's lambda_api_handler() was just a local Python function called
directly in the same script, never actually deployed behind API Gateway.
This version is meant to be zipped and deployed, then wired to a real
API Gateway HTTP endpoint.

Note: query_router_rulebased.py and sql_validator.py must be packaged
into the same deployment zip alongside this file (see deploy_api.py),
since Lambda needs all dependencies bundled together.
"""

import json
from query_router_rulebased import classify_intent, generate_sql, handle_churn_query, handle_metadata_query, POLICY_PATH
from sql_validator import validate_sql
import pandas as pd

CSV_PATH = "data.csv"  # bundled alongside the code in the deployment zip


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        question = body.get("query", "")

        if not question:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing 'query' field in request body"})
            }

        route = classify_intent(question)
        q = question.lower()

        with open(POLICY_PATH) as f:
            policy_text = f.read()

        if "churn" in q:
            result = handle_churn_query(question, policy_text)
        elif "metadata" in q:
            result = handle_metadata_query(question, policy_text)
        elif route == "REDSHIFT":
            df = pd.read_csv(CSV_PATH)
            sql = generate_sql(question, df)
            validation = validate_sql(sql)
            result = {"route": route, "generated_sql": sql, "sql_valid": validation["valid"], "validation_reason": validation["reason"]}
        else:
            section = policy_text.split("2. DATA GOVERNANCE")[0].strip()
            result = {"route": route, "document_excerpt": section[:300]}

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "success", "query": question, "result": result}, default=str)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "error", "error": str(e)})
        }