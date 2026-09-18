"""
upload_json.py

Closes the "S3 stores raw PDFs, CSVs, and JSONs" requirement - CSV and PDF
were already confirmed working; this adds JSON, using the same pattern as
s3.py and test_textract.py.
"""

import boto3
import json
import os

s3 = boto3.client("s3")
BUCKET = "unit3capstoneac"
LOCAL_JSON_PATH = "data/dataset_metadata.json"
S3_KEY = "structured-data/dataset_metadata.json"


def create_sample_json():
    """
    A real, useful JSON file for this project: metadata describing the
    ingested dataset, referencing the governance policy's required fields
    (and honestly showing which ones data.csv is missing - consistent with
    the metadata-check query elsewhere in this project rather than
    contradicting it).
    """
    metadata = {
        "dataset_name": "spotify_streaming_data",
        "source_file": "data.csv",
        "row_count": 8058,
        "columns": [
            "artist and title", "wks", "t10", "pk", "x?",
            "PkStreams", "total", "artist name", "song name", "lyrics"
        ],
        "governance_check": {
            "required_fields": [
                "source_system", "ingestion_date", "data_owner",
                "retention_period_days", "pii_classification"
            ],
            "present_in_dataset": [],
            "missing_from_dataset": [
                "source_system", "ingestion_date", "data_owner",
                "retention_period_days", "pii_classification"
            ],
            "compliant": False
        }
    }
    os.makedirs("data", exist_ok=True)
    with open(LOCAL_JSON_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Created {LOCAL_JSON_PATH}")


def upload_json():
    print(f"Uploading {LOCAL_JSON_PATH} to s3://{BUCKET}/{S3_KEY}...")
    s3.upload_file(LOCAL_JSON_PATH, BUCKET, S3_KEY)
    print("Upload complete.")


if __name__ == "__main__":
    create_sample_json()
    upload_json()