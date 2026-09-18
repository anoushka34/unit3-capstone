"""
find_lambda_role.py

Lambda functions require an IAM execution role. This sandbox has denied
essentially every IAM introspection/write action tested so far, so this
script checks for the most common pattern in training sandboxes: a
pre-created role (often named LabRole, voclabs-role, or similar) that
students are meant to use as-is, since they cannot create their own roles.

Run this BEFORE attempting Lambda deployment - if no usable role is found,
Lambda deployment is likely blocked the same way DynamoDB was, and that's
worth knowing before writing more code around it.
"""

import boto3
from botocore.exceptions import ClientError

iam = boto3.client("iam", region_name="us-east-1")

COMMON_LAB_ROLE_NAMES = [
    "LabRole",
    "voclabs",
    "vocareum-role",
    "LabInstanceRole",
    "AWSServiceRoleForLambda",
    "lambda-execution-role",
    "capstone-lambda-role",
]


def try_list_roles():
    """Broadest approach: list all roles and let you pick. May itself be denied."""
    try:
        response = iam.list_roles()
        roles = [r["RoleName"] for r in response["Roles"]]
        print(f"iam:ListRoles ALLOWED. Found {len(roles)} role(s):")
        for r in roles:
            print(f"  - {r}")
        return roles
    except ClientError as e:
        print(f"iam:ListRoles DENIED: {e.response['Error']['Message']}")
        return None


def try_get_specific_roles():
    """Fallback: check specific common lab role names one at a time."""
    found = []
    for name in COMMON_LAB_ROLE_NAMES:
        try:
            response = iam.get_role(RoleName=name)
            arn = response["Role"]["Arn"]
            print(f"FOUND: {name} -> {arn}")
            found.append(arn)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "NoSuchEntity":
                pass  # expected for names that don't exist here - not informative
            else:
                print(f"  {name}: {code} - {e.response['Error']['Message']}")
    return found


if __name__ == "__main__":
    print("Checking for a usable Lambda execution role...\n")

    roles = try_list_roles()
    if not roles:
        print("\nFalling back to checking common lab role names directly...")
        roles = try_get_specific_roles()

    print("\n" + "=" * 60)
    if roles:
        print(f"RESULT: Found {len(roles)} usable role(s). Lambda deployment is likely possible.")
        print("Use one of the ARNs above as the Role parameter in lambda.create_function().")
    else:
        print("RESULT: No usable execution role found or accessible.")
        print("This likely means Lambda deployment is blocked the same way IAM/DynamoDB")
        print("were - you cannot create a new role, and no pre-made one was discoverable.")
        print("This is worth adding to your instructor escalation alongside the other blocks.")