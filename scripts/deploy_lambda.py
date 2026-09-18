"""
deploy_lambda.py

Deploys lambda_function.py as a real Lambda function using the role
confirmed working in test_attach_narrow_textract.py, and wires it to
trigger automatically on S3 PDF uploads under raw-pdfs/.

Run this once. After it succeeds, uploading any .pdf to
s3://unit3capstoneac/raw-pdfs/ will automatically trigger extraction,
with output landing in s3://unit3capstoneac/processed-text/.
"""

import boto3
import zipfile
import io
import time
from botocore.exceptions import ClientError

REGION = "us-east-1"
BUCKET = "unit3capstoneac"
FUNCTION_NAME = "capstone-pdf-textract-processor"
ROLE_NAME = "capstone-lambda-execution-role"

account_id = boto3.client("sts").get_caller_identity()["Account"]
ROLE_ARN = f"arn:aws:iam::{account_id}:role/{ROLE_NAME}"

lambda_client = boto3.client("lambda", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)


def build_deployment_zip(source_path: str = "scripts/lambda_function.py") -> bytes:
    with open(source_path, "r") as f:
        code = f.read()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("lambda_function.py", code)
    return buf.getvalue()


def create_or_update_function(zip_bytes: bytes) -> str:
    try:
        response = lambda_client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Role=ROLE_ARN,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Timeout=30,
            MemorySize=256,
            Description="Capstone: extracts text from PDFs uploaded to S3 via Textract",
        )
        print(f"Created function: {response['FunctionArn']}")
        return response["FunctionArn"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            print("Function already exists - updating code instead.")
            response = lambda_client.update_function_code(
                FunctionName=FUNCTION_NAME, ZipFile=zip_bytes
            )
            return response["FunctionArn"]
        raise


def add_s3_invoke_permission(function_arn: str):
    try:
        lambda_client.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="AllowS3Invoke",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{BUCKET}",
            SourceAccount=account_id,
        )
        print("Granted S3 permission to invoke the function.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            print("S3 invoke permission already exists - skipping.")
        else:
            raise


def configure_s3_trigger(function_arn: str):
    s3.put_bucket_notification_configuration(
        Bucket=BUCKET,
        NotificationConfiguration={
            "LambdaFunctionConfigurations": [
                {
                    "LambdaFunctionArn": function_arn,
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": {
                        "Key": {
                            "FilterRules": [
                                {"Name": "prefix", "Value": "raw-pdfs/"},
                                {"Name": "suffix", "Value": ".pdf"},
                            ]
                        }
                    },
                }
            ]
        },
    )
    print(f"S3 trigger configured: uploads to s3://{BUCKET}/raw-pdfs/*.pdf will now invoke the function.")


if __name__ == "__main__":
    print("Building deployment package...")
    zip_bytes = build_deployment_zip()

    print("Deploying Lambda function...")
    function_arn = create_or_update_function(zip_bytes)

    print("Waiting for function to become active...")
    time.sleep(5)  # brief pause for IAM role propagation + function state

    print("Granting S3 invoke permission...")
    add_s3_invoke_permission(function_arn)

    print("Configuring S3 event trigger...")
    configure_s3_trigger(function_arn)

    print("\nDeployment complete. Test by uploading a PDF:")
    print(f"  aws s3 cp data/sample_governance_policy.pdf s3://{BUCKET}/raw-pdfs/test-upload.pdf")
    print(f"  Then check: aws s3 ls s3://{BUCKET}/processed-text/")