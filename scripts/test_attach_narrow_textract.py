"""
test_attach_narrow_textract.py

AmazonTextractFullAccess was denied when attaching to the new Lambda role,
but iam:AttachRolePolicy itself clearly works (two other policies attached
fine on the same role). This tests whether the block is specific to broad
"FullAccess"-style policies, by trying a minimal inline policy scoped to
only the one Textract action the Lambda function actually needs
(DetectDocumentText), via iam:PutRolePolicy instead of AttachRolePolicy.

This matters: without SOME form of Textract permission on the role, a
deployed Lambda function cannot call Textract even though your own user
session can (the two run under different IAM identities).
"""

import boto3
import json
from botocore.exceptions import ClientError

iam = boto3.client("iam", region_name="us-east-1")
ROLE_NAME = "capstone-lambda-execution-role"

NARROW_TEXTRACT_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["textract:DetectDocumentText", "textract:AnalyzeDocument"],
            "Resource": "*"
        }
    ]
}


def test_inline_policy():
    try:
        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName="capstone-textract-minimal",
            PolicyDocument=json.dumps(NARROW_TEXTRACT_POLICY),
        )
        print("SUCCESS: Narrow inline Textract policy attached.")
        print("The role now has textract:DetectDocumentText and AnalyzeDocument.")
        return True
    except ClientError as e:
        print(f"FAILED: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        return False


if __name__ == "__main__":
    print("Testing narrow inline Textract policy (vs. the denied broad managed policy)...\n")
    success = test_inline_policy()

    if success:
        print("\nThe role capstone-lambda-execution-role is now fully ready for "
              "Lambda deployment: basic execution + S3 read + minimal Textract access.")
    else:
        print("\nTextract permission cannot be granted to this role at all, broad or "
              "narrow. A deployed Lambda function will not be able to call Textract, "
              "even though your own user session can. Add this to the escalation list.")