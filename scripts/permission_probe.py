"""
permission_probe.py

Since iam:SimulatePrincipalPolicy itself is denied, we can't ask AWS what
we're allowed to do. Instead, this script tries a harmless, read-only call
against every service the capstone needs, and reports Allowed / Denied for
each. This builds a full permission map in one run instead of discovering
blocks one at a time.

Every call here is non-destructive (list/describe/get-caller-identity style).
Nothing is created, modified, or deleted.
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGION = "us-east-1"

results = []


def probe(service_name: str, action_label: str, func):
    try:
        func()
        results.append((service_name, action_label, "ALLOWED", ""))
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        results.append((service_name, action_label, f"DENIED ({code})", msg))
    except NoCredentialsError:
        results.append((service_name, action_label, "NO CREDENTIALS", ""))
    except Exception as e:
        results.append((service_name, action_label, "ERROR", str(e)))


def run_probes():
    # Identity check
    sts = boto3.client("sts", region_name=REGION)
    probe("STS", "GetCallerIdentity", lambda: sts.get_caller_identity())

    # S3
    s3 = boto3.client("s3", region_name=REGION)
    probe("S3", "ListBuckets", lambda: s3.list_buckets())

    # Glue
    glue = boto3.client("glue", region_name=REGION)
    probe("Glue", "GetCrawlers", lambda: glue.get_crawlers())
    probe("Glue", "GetDatabases", lambda: glue.get_databases())

    # DynamoDB
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    probe("DynamoDB", "ListTables", lambda: dynamodb.list_tables())

    # RDS
    rds = boto3.client("rds", region_name=REGION)
    probe("RDS", "DescribeDBInstances", lambda: rds.describe_db_instances())

    # Bedrock (control plane - listing models, not invoking)
    bedrock_ctrl = boto3.client("bedrock", region_name=REGION)
    probe("Bedrock", "ListFoundationModels", lambda: bedrock_ctrl.list_foundation_models())

    # Lambda
    lam = boto3.client("lambda", region_name=REGION)
    probe("Lambda", "ListFunctions", lambda: lam.list_functions())

    # Redshift
    redshift = boto3.client("redshift", region_name=REGION)
    probe("Redshift", "DescribeClusters", lambda: redshift.describe_clusters())

    # OpenSearch
    opensearch = boto3.client("opensearch", region_name=REGION)
    probe("OpenSearch", "ListDomainNames", lambda: opensearch.list_domain_names())

    # Textract
    textract = boto3.client("textract", region_name=REGION)
    # Textract has no "list" call with zero args that's cheap/safe across all SDK
    # versions, so we use a deliberately invalid job id - a permission denial
    # will surface before any "not found" validation error would.
    def textract_probe():
        try:
            textract.get_document_text_detection(JobId="00000000-0000-0000-0000-000000000000")
        except ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException":
                raise
            # any other error (e.g. InvalidJobIdException) means we passed
            # the permission check, so treat as allowed
            return
    probe("Textract", "GetDocumentTextDetection (permission check)", textract_probe)

    # IAM (already known denied, included for completeness in the report)
    iam = boto3.client("iam", region_name=REGION)
    probe("IAM", "GetUser", lambda: iam.get_user())
    probe("IAM", "ListUserPolicies", lambda: iam.list_user_policies(UserName="Whiz_User_353696.89077867"))

    # CloudWatch Logs (useful to know if you can even see Lambda logs later)
    logs = boto3.client("logs", region_name=REGION)
    probe("CloudWatch Logs", "DescribeLogGroups", lambda: logs.describe_log_groups())


def print_report():
    print("=" * 70)
    print("SANDBOX PERMISSION MAP")
    print("=" * 70)
    col_widths = (16, 40, 20)
    print(f"{'Service':<16}{'Action':<40}{'Result':<20}")
    print("-" * 70)
    for service, action, status, _ in results:
        print(f"{service:<16}{action:<40}{status:<20}")
    print("=" * 70)

    denied = [r for r in results if "DENIED" in r[2]]
    allowed = [r for r in results if r[2] == "ALLOWED"]

    print(f"\nAllowed: {len(allowed)} / {len(results)}")
    print(f"Denied:  {len(denied)} / {len(results)}\n")

    if denied:
        print("Denied action details (for instructor escalation):")
        for service, action, status, msg in denied:
            print(f"\n  [{service}] {action}")
            print(f"  {msg}")


if __name__ == "__main__":
    run_probes()
    print_report()