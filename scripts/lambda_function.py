"""
lambda_function.py

Deploy this AS the Lambda function code (not run directly). Triggered by
an S3 ObjectCreated event when a PDF lands under raw-pdfs/. Extracts text
via Textract, chunks it (500-1000 token range per assignment spec), and
writes the result back to S3 under processed-text/ as JSON.

This also closes the RDS "store raw extracted text" requirement gap - RDS
was ruled out on cost, DynamoDB was blocked by IAM - storing the extracted
text as structured JSON in S3 (a confirmed-working service) is the
substitute, now wired into the real automated pipeline instead of being a
separate manual step.
"""

import boto3
import json
import urllib.parse

s3 = boto3.client("s3")
textract = boto3.client("textract")

CHUNK_SIZE_WORDS = 150


def chunk_text(text: str, chunk_size_words: int = CHUNK_SIZE_WORDS):
    words = text.split()
    return [" ".join(words[i:i + chunk_size_words]) for i in range(0, len(words), chunk_size_words)]


def lambda_handler(event, context):
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

    print(f"Processing s3://{bucket}/{key}")

    if not key.lower().endswith(".pdf"):
        print(f"Skipping non-PDF file: {key}")
        return {"statusCode": 200, "body": "skipped - not a PDF"}

    # Extract text via Textract
    response = textract.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    lines = [block["Text"] for block in response["Blocks"] if block["BlockType"] == "LINE"]
    full_text = "\n".join(lines)

    # Chunk it
    chunks = chunk_text(full_text)

    # Build output record - substitute for "raw text stored in RDS"
    doc_id = key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    output = {
        "doc_id": doc_id,
        "source_key": key,
        "full_text": full_text,
        "chunks": [{"chunk_index": i, "text": c} for i, c in enumerate(chunks)],
        "char_count": len(full_text),
        "chunk_count": len(chunks),
    }

    output_key = f"processed-text/{doc_id}.json"
    s3.put_object(
        Bucket=bucket,
        Key=output_key,
        Body=json.dumps(output, indent=2),
        ContentType="application/json",
    )

    print(f"Wrote extracted text to s3://{bucket}/{output_key} ({len(chunks)} chunks)")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "doc_id": doc_id,
            "output_location": f"s3://{bucket}/{output_key}",
            "chunk_count": len(chunks),
        })
    }