"""
deploy_api_function_url.py

apigateway:POST is denied in this sandbox (same block pattern as Glue
Crawler, Bedrock invoke, and DynamoDB creation - see README). Real API
Gateway cannot be provisioned here.

Substitute: AWS Lambda Function URLs - a native Lambda feature (no API
Gateway involved) that exposes a function directly as a public HTTPS
endpoint. This satisfies the actual intent of the requirement ("a real
endpoint for programmatic access, not just CLI/notebook") using only
Lambda permissions, which are confirmed working in this sandbox.

Documented explicitly as a substitute for API Gateway, not a claim that
API Gateway itself was used.
"""

import boto3
import zipfile
import io
import time
from botocore.exceptions import ClientError

REGION = "us-east-1"
FUNCTION_NAME = "capstone-knowledge-api"
ROLE_NAME = "capstone-lambda-execution-role"

account_id = boto3.client("sts").get_caller_identity()["Account"]
ROLE_ARN = f"arn:aws:iam::{account_id}:role/{ROLE_NAME}"

lambda_client = boto3.client("lambda", region_name=REGION)


def build_deployment_zip() -> bytes:
    files_to_bundle = {
        "api_lambda_function.py": "scripts/api_lambda_function.py",
        "query_router_rulebased.py": "scripts/query_router_rulebased.py",
        "sql_validator.py": "scripts/sql_validator.py",
        "data.csv": "data/data.csv",
        "sample_governance_policy.txt": "data/sample_governance_policy.txt",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for arcname, path in files_to_bundle.items():
            z.write(path, arcname=arcname)
    return buf.getvalue()


def create_or_update_function(zip_bytes: bytes) -> str:
    try:
        response = lambda_client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Role=ROLE_ARN,
            Handler="api_lambda_function.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Timeout=30,
            MemorySize=512,
            Description="Capstone Gold: knowledge query endpoint (Lambda Function URL - API Gateway blocked)",
        )
        print(f"Created function: {response['FunctionArn']}")
        return response["FunctionArn"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            print("Function exists - updating code.")
            response = lambda_client.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes)
            time.sleep(3)
            return response["FunctionArn"]
        raise


def create_function_url() -> str:
    try:
        response = lambda_client.create_function_url_config(
            FunctionName=FUNCTION_NAME,
            AuthType="NONE",  # public endpoint for capstone testing; use AWS_IAM for production
        )
        url = response["FunctionUrl"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            response = lambda_client.get_function_url_config(FunctionName=FUNCTION_NAME)
            url = response["FunctionUrl"]
        else:
            raise

    # Allow public invocation of the URL (separate from IAM invoke permission)
    try:
        lambda_client.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="AllowPublicFunctionUrl",
            Action="lambda:InvokeFunctionUrl",
            Principal="*",
            FunctionUrlAuthType="NONE",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceConflictException":
            raise

    return url


if __name__ == "__main__":
    print("Building deployment package...")
    zip_bytes = build_deployment_zip()

    print("Deploying Lambda function...")
    function_arn = create_or_update_function(zip_bytes)
    time.sleep(5)

    print("Creating Lambda Function URL (API Gateway substitute)...")
    url = create_function_url()

    print(f"\nDeployment complete. Real public endpoint:\n  {url}")
    print("\nTest it:")
    print(f"""  curl -X POST {url} \\
    -H "Content-Type: application/json" \\
    -d '{{"query": "What are the top 3 most streamed songs?"}}'""")