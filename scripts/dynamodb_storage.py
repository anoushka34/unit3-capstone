"""
dynamodb_storage.py

Substitute for RDS/Aurora in the capstone architecture.

Why: RDS/Aurora require a provisioned, billed instance even at minimal size,
and the sandbox account either lacks free-tier eligibility or carries cost
risk we chose to avoid. DynamoDB's free tier (25GB storage, 25 RCU/25 WCU)
does not expire after 12 months and requires no provisioned server, making
it a like-for-like substitute for "store raw extracted text for structured
querying" without incurring cost.

This does NOT replace Redshift (analytics warehouse) or OpenSearch (vector
search) roles in the architecture — only the RDS "store raw extracted text"
role from Step 2 of the assignment.
"""

import boto3
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

REGION = "us-east-1"
TABLE_NAME = "capstone-document-text"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
dynamodb_client = boto3.client("dynamodb", region_name=REGION)


def create_table():
    """
    Creates the DynamoDB table if it doesn't already exist.
    Uses on-demand (PAY_PER_REQUEST) billing so there's no idle hourly
    cost the way a provisioned RDS instance has — you only pay per
    read/write, and both are free up to the perpetual free-tier limits.
    """
    existing_tables = dynamodb_client.list_tables()["TableNames"]
    if TABLE_NAME in existing_tables:
        print(f"Table '{TABLE_NAME}' already exists.")
        return dynamodb.Table(TABLE_NAME)

    print(f"Creating table '{TABLE_NAME}'...")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "doc_id", "KeyType": "HASH"},       # Partition key
            {"AttributeName": "chunk_id", "KeyType": "RANGE"},    # Sort key
        ],
        AttributeDefinitions=[
            {"AttributeName": "doc_id", "AttributeType": "S"},
            {"AttributeName": "chunk_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print(f"Table '{TABLE_NAME}' created successfully.")
    return table


def store_text_chunk(doc_id: str, chunk_index: int, text: str, source_file: str, metadata: dict = None):
    """
    Stores one chunk of extracted document text.

    Mirrors the role RDS would have played: a queryable record of raw
    extracted text, keyed by document and chunk, with metadata attached
    for downstream filtering.
    """
    table = dynamodb.Table(TABLE_NAME)
    chunk_id = f"chunk-{chunk_index:04d}"

    item = {
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "text": text,
        "source_file": source_file,
        "chunk_index": chunk_index,
        "char_count": len(text),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        item["metadata"] = metadata

    try:
        table.put_item(Item=item)
        print(f"Stored {chunk_id} for doc_id={doc_id} ({len(text)} chars)")
    except ClientError as e:
        print(f"Error storing chunk: {e.response['Error']['Message']}")
        raise


def get_document_chunks(doc_id: str):
    """
    Retrieves all chunks for a given document, ordered by chunk_id
    (equivalent to a `SELECT * FROM raw_text WHERE doc_id = ?` in RDS).
    """
    table = dynamodb.Table(TABLE_NAME)
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("doc_id").eq(doc_id)
    )
    return response.get("Items", [])


def get_full_document_text(doc_id: str) -> str:
    """Reassembles a document's full text from its stored chunks, in order."""
    chunks = get_document_chunks(doc_id)
    chunks_sorted = sorted(chunks, key=lambda c: c["chunk_index"])
    return "\n".join(c["text"] for c in chunks_sorted)


def scan_all_documents():
    """
    Lists all distinct doc_ids currently stored.
    (Equivalent to `SELECT DISTINCT doc_id FROM raw_text` in RDS.)
    Note: scan is fine at capstone scale; would switch to a GSI for
    production-scale document counts.
    """
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan(ProjectionExpression="doc_id")
    doc_ids = sorted(set(item["doc_id"] for item in response.get("Items", [])))
    return doc_ids


if __name__ == "__main__":
    # Demo / smoke test
    create_table()

    demo_doc_id = str(uuid.uuid4())
    sample_chunks = [
        "This is the first chunk of extracted PDF text about data governance policy.",
        "This is the second chunk, continuing the policy discussion on retention rules.",
    ]

    for i, chunk_text in enumerate(sample_chunks):
        store_text_chunk(
            doc_id=demo_doc_id,
            chunk_index=i,
            text=chunk_text,
            source_file="data_governance_policy.pdf",
            metadata={"page_range": f"{i+1}-{i+1}"},
        )

    print("\n--- Retrieving stored chunks ---")
    chunks = get_document_chunks(demo_doc_id)
    for c in chunks:
        print(json.dumps(c, indent=2, default=str))

    print("\n--- Reassembled full text ---")
    print(get_full_document_text(demo_doc_id))

    print("\n--- All document IDs in table ---")
    print(scan_all_documents())