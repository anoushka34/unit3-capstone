"""
add_s3_write_permission.py

The Lambda role has AmazonS3ReadOnlyAccess (can read the uploaded PDF) but
no write permission (can't save extracted text back). This adds a narrow
inline policy scoped to only the processed-text/ prefix - not full S3
write access - following the same narrow-policy pattern that worked for
Textract.
"""

import boto3
import json
from botocore.exceptions import ClientError

iam = boto3.client("iam", region_name="us-east-1")
ROLE_NAME = "capstone-lambda-execution-role"
BUCKET = "unit3capstoneac"

NARROW_WRITE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:PutObject"],
            "Resource": f"arn:aws:s3:::{BUCKET}/processed-text/*"
        }
    ]
}

try:
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="capstone-s3-write-processed-text",
        PolicyDocument=json.dumps(NARROW_WRITE_POLICY),
    )
    print("SUCCESS: Narrow S3 write policy attached (processed-text/* only).")
    print("Wait ~10-15 seconds for IAM propagation before re-testing the Lambda trigger.")
except ClientError as e:
    print(f"FAILED: {e.response['Error']['Code']} - {e.response['Error']['Message']}")