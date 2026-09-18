"""
test_function_url_iam_auth.py

The Function URL config says AuthType=NONE and the resource policy allows
anonymous invocation, yet curl gets Forbidden. This tests whether an
account-level guardrail (likely a Service Control Policy) is silently
forcing IAM authentication on all Function URLs regardless of the
per-function config - by signing the request properly with SigV4 and
seeing if THAT works.

Install once:
    pip install requests --break-system-packages
"""

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import json

REGION = "us-east-1"
FUNCTION_URL = "https://driubjioa324e6mi6omiia6k3a0sjwsa.lambda-url.us-east-1.on.aws/"

session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()

body = json.dumps({"query": "What are the top 3 most streamed songs?"})

request = AWSRequest(
    method="POST",
    url=FUNCTION_URL,
    data=body,
    headers={"Content-Type": "application/json"},
)

SigV4Auth(credentials, "lambda", REGION).add_auth(request)

response = requests.post(FUNCTION_URL, data=body, headers=dict(request.headers))

print(f"Status code: {response.status_code}")
print(f"Response body:\n{response.text}")

if response.status_code == 200:
    print("\nCONFIRMED: IAM-signed requests work, anonymous ones don't.")
    print("An account-level guardrail is forcing IAM auth on Function URLs.")
    print("Fix: switch AuthType to AWS_IAM and document that callers need valid AWS credentials.")
elif response.status_code == 403:
    print("\nStill forbidden even with IAM auth - this is a deeper block, not just an auth-type override.")