"""
deploy_api.py

Deploys the real Enterprise Knowledge API: packages api_lambda_function.py
plus its dependencies into a zip, deploys as a Lambda function, then
creates a real API Gateway HTTP API in front of it with a public endpoint
URL - not a local function call like the original gold.py.

Uses the same capstone-lambda-execution-role proven working for the
Textract pipeline (it already has basic execution permissions; needs one
additional narrow Glue read permission for the metadata-query handler,
added below via the same narrow-policy pattern that worked before).
"""

import boto3
import zipfile
import io
import json
import time
from botocore.exceptions import ClientError

REGION = "us-east-1"
FUNCTION_NAME = "capstone-knowledge-api"
ROLE_NAME = "capstone-lambda-execution-role"
API_NAME = "capstone-knowledge-api-gateway"

account_id = boto3.client("sts").get_caller_identity()["Account"]
ROLE_ARN = f"arn:aws:iam::{account_id}:role/{ROLE_NAME}"

lambda_client = boto3.client("lambda", region_name=REGION)
apigw = boto3.client("apigatewayv2", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)


def ensure_glue_permission_on_role():
    """
    The metadata-query handler calls glue.get_table() - the role needs
    that permission too, following the same narrow-policy pattern that
    worked for Textract and S3 write.
    """
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["glue:GetTable", "glue:GetDatabase"],
            "Resource": "*"
        }]
    }
    try:
        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName="capstone-glue-read-for-api",
            PolicyDocument=json.dumps(policy),
        )
        print("Attached narrow Glue read permission to role.")
    except ClientError as e:
        print(f"Could not attach Glue permission: {e.response['Error']['Code']} - {e.response['Error']['Message']}")


def build_deployment_zip() -> bytes:
    files_to_bundle = {
        "api_lambda_function.py": "scripts/api_lambda_function.py",
        "query_router_rulebased.py": "scripts/query_router_rulebased.py",
        "sql_validator.py": "scripts/sql_validator.py",
        "generate_embeddings.py": "scripts/generate_embeddings.py",
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
            Description="Capstone Gold: real API Gateway-backed knowledge query endpoint",
        )
        print(f"Created function: {response['FunctionArn']}")
        return response["FunctionArn"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            print("Function exists - updating code.")
            response = lambda_client.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes)
            return response["FunctionArn"]
        raise


def create_api_gateway(function_arn: str) -> str:
    api = apigw.create_api(
        Name=API_NAME,
        ProtocolType="HTTP",
        Target=function_arn,
    )
    api_id = api["ApiId"]
    api_endpoint = api["ApiEndpoint"]

    try:
        lambda_client.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="AllowAPIGatewayInvoke",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{REGION}:{account_id}:{api_id}/*/*",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceConflictException":
            raise

    return api_endpoint


if __name__ == "__main__":
    print("Attaching Glue read permission needed by the metadata handler...")
    ensure_glue_permission_on_role()
    time.sleep(5)

    print("Building deployment package...")
    zip_bytes = build_deployment_zip()

    print("Deploying Lambda function...")
    function_arn = create_or_update_function(zip_bytes)
    time.sleep(5)

    print("Creating API Gateway HTTP API...")
    endpoint = create_api_gateway(function_arn)

    print(f"\nDeployment complete. Real public endpoint:\n  {endpoint}")
    print("\nTest it:")
    print(f"""  curl -X POST {endpoint} \\
    -H "Content-Type: application/json" \\
    -d '{{"query": "What are the top 3 most streamed songs?"}}'""")