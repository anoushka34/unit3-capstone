"""
test_textract.py

Implements the Bronze requirement: "Lambda uses Amazon Textract to extract
text" - tested here standalone first (per the assignment's own advice:
confirm a service works before building automation on top of it).

Uses the synchronous detect_document_text API (single-page/simple PDFs).
For multi-page or scanned PDFs at production scale you'd use the async
start_document_text_detection + get_document_text_detection pair instead,
but sync is sufficient to confirm Textract access and works for the sample
PDF here.
"""

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
BUCKET = "unit3capstoneac"
S3_KEY = "raw-pdfs/sample_governance_policy.pdf"
LOCAL_PDF_PATH = "data/sample_governance_policy.pdf"

s3 = boto3.client("s3", region_name=REGION)
textract = boto3.client("textract", region_name=REGION)


def upload_sample_pdf():
    print(f"Uploading {LOCAL_PDF_PATH} to s3://{BUCKET}/{S3_KEY}...")
    s3.upload_file(LOCAL_PDF_PATH, BUCKET, S3_KEY)
    print("Upload complete.")


def extract_text_from_s3_pdf():
    """
    Calls Textract directly against the S3 object (no need to download
    locally first) - this is also the same call pattern the Lambda function
    will use once triggered by an S3 upload event.
    """
    try:
        response = textract.detect_document_text(
            Document={"S3Object": {"Bucket": BUCKET, "Name": S3_KEY}}
        )
    except ClientError as e:
        print(f"Textract call failed: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        raise

    lines = [block["Text"] for block in response["Blocks"] if block["BlockType"] == "LINE"]
    full_text = "\n".join(lines)
    return full_text


def chunk_text(text: str, chunk_size_words: int = 150):
    words = text.split()
    return [" ".join(words[i:i + chunk_size_words]) for i in range(0, len(words), chunk_size_words)]


if __name__ == "__main__":
    upload_sample_pdf()

    print("\nExtracting text via Textract...")
    extracted_text = extract_text_from_s3_pdf()

    print(f"\n--- Extracted text ({len(extracted_text)} chars) ---")
    print(extracted_text)

    chunks = chunk_text(extracted_text)
    print(f"\n--- Chunked into {len(chunks)} chunk(s) (500-1000 token range target) ---")
    for i, c in enumerate(chunks):
        print(f"\nChunk {i}: {c[:150]}{'...' if len(c) > 150 else ''}")