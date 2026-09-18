"""
test_create_lambda_role.py

The 10 existing roles don't trust Lambda. Before concluding Lambda
automation is blocked entirely, this tests whether a NEW role can be
created with the correct trust policy - iam:ListRoles unexpectedly worked
despite iam:GetUser being denied, so IAM is not uniformly blocked here and
this is worth testing directly rather than assuming.

If this succeeds, attaches AWSLambdaBasicExecutionRole (CloudWatch Logs
write access) plus S3 read and Textract access so the role is actually
usable for the capstone's Lambda function.
"""

import boto3
import json
from botocore.exceptions import ClientError

iam = boto3.client("iam", region_name="us-east-1")
ROLE_NAME = "capstone-lambda-execution-role"

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }
    ]
}

MANAGED_POLICIES_TO_ATTACH = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonTextractFullAccess",
]


def test_create_role():
    try:
        response = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
            Description="Execution role for capstone Lambda function (S3 -> Textract trigger)",
        )
        role_arn = response["Role"]["Arn"]
        print(f"SUCCESS: Created role {ROLE_NAME}")
        print(f"  ARN: {role_arn}")
        return role_arn
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "EntityAlreadyExists":
            print(f"Role {ROLE_NAME} already exists - fetching its ARN.")
            existing = iam.get_role(RoleName=ROLE_NAME)
            return existing["Role"]["Arn"]
        print(f"FAILED: {code} - {e.response['Error']['Message']}")
        return None


def attach_policies(role_name: str):
    for policy_arn in MANAGED_POLICIES_TO_ATTACH:
        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print(f"Attached: {policy_arn}")
        except ClientError as e:
            print(f"FAILED to attach {policy_arn}: {e.response['Error']['Code']} - {e.response['Error']['Message']}")


if __name__ == "__main__":
    print("Testing whether a new Lambda execution role can be created...\n")
    role_arn = test_create_role()

    if role_arn:
        print("\nAttaching required policies...")
        attach_policies(ROLE_NAME)
        print(f"\nIf all attachments succeeded, use this role ARN for Lambda deployment:\n  {role_arn}")
        print("\nNote: IAM role/policy changes can take ~10-30 seconds to propagate "
              "before Lambda will successfully assume the role.")
    else:
        print("\nCould not create a usable role. Lambda automation is likely blocked "
              "the same way DynamoDB and Bedrock are - add this to the instructor escalation.")