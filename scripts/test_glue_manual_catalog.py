"""
test_glue_manual_catalog.py

glue:CreateCrawler is denied in this sandbox, but glue:GetDatabases and
glue:GetCrawlers both succeeded in the permission probe - meaning Glue
itself isn't fully blocked, only crawler creation specifically. Crawlers
are just a convenience that auto-discovers schema; the actual artifact
they produce (a database + table definition in the Glue Data Catalog) can
be created directly and manually via glue:CreateDatabase / glue:CreateTable.

This script tests whether that manual path is open. If it is, you get a
real, working Glue Catalog entry for your CSV - satisfying "Glue Crawler
catalogs and discovers schemas" in spirit (manual schema definition instead
of auto-discovery), fully documented as a substitution for the blocked
action.
"""

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
DATABASE_NAME = "capstone_spotify_db"
TABLE_NAME = "spotify_streaming_data"
S3_LOCATION = "s3://unit3capstoneac/structured-data/"

glue = boto3.client("glue", region_name=REGION)


def test_create_database():
    try:
        glue.create_database(
            DatabaseInput={
                "Name": DATABASE_NAME,
                "Description": "Manually-created catalog database (Crawler creation blocked by sandbox IAM policy)",
            }
        )
        print(f"SUCCESS: Created database '{DATABASE_NAME}'")
        return True
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "AlreadyExistsException":
            print(f"Database '{DATABASE_NAME}' already exists - treating as success.")
            return True
        print(f"DENIED/FAILED creating database: {code} - {e.response['Error']['Message']}")
        return False


def test_create_table():
    """
    Manually defines the schema a Crawler would have auto-discovered.
    Update the Columns list to match your actual data.csv headers.
    """
    try:
        glue.create_table(
            DatabaseName=DATABASE_NAME,
            TableInput={
                "Name": TABLE_NAME,
                "StorageDescriptor": {
                    # Matches the actual header row in data.csv:
                    # artist and title,wks,t10,pk,x?,PkStreams,total,artist name,song name,lyrics
                    "Columns": [
                        {"Name": "artist_and_title", "Type": "string"},
                        {"Name": "wks", "Type": "bigint"},
                        {"Name": "t10", "Type": "bigint"},
                        {"Name": "pk", "Type": "bigint"},
                        {"Name": "x", "Type": "string"},          # original header "x?" - Glue disallows "?" in column names
                        {"Name": "pkstreams", "Type": "bigint"},
                        {"Name": "total", "Type": "bigint"},
                        {"Name": "artist_name", "Type": "string"},
                        {"Name": "song_name", "Type": "string"},
                        {"Name": "lyrics", "Type": "string"},
                    ],
                    "Location": S3_LOCATION,
                    "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                    "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                    # OpenCSVSerDe (not LazySimpleSerDe) because the lyrics column
                    # contains commas and quoted text - LazySimpleSerDe does not
                    # respect CSV quoting and would misparse those rows.
                    "SerdeInfo": {
                        "SerializationLibrary": "org.apache.hadoop.hive.serde2.OpenCSVSerde",
                        "Parameters": {
                            "separatorChar": ",",
                            "quoteChar": "\"",
                        },
                    },
                },
                "TableType": "EXTERNAL_TABLE",
                "Parameters": {"classification": "csv", "skip.header.line.count": "1"},
            }
        )
        print(f"SUCCESS: Created table '{TABLE_NAME}' in database '{DATABASE_NAME}'")
        return True
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "AlreadyExistsException":
            print(f"Table '{TABLE_NAME}' already exists - treating as success.")
            return True
        print(f"DENIED/FAILED creating table: {code} - {e.response['Error']['Message']}")
        return False


def verify_catalog():
    """Confirms the table is queryable via the Glue Catalog API."""
    try:
        response = glue.get_table(DatabaseName=DATABASE_NAME, Name=TABLE_NAME)
        cols = response["Table"]["StorageDescriptor"]["Columns"]
        print(f"\nVerified catalog entry. Columns registered:")
        for c in cols:
            print(f"  - {c['Name']} ({c['Type']})")
        return True
    except ClientError as e:
        print(f"Could not verify table: {e.response['Error']['Message']}")
        return False


if __name__ == "__main__":
    print("Testing manual Glue Catalog creation (substitute for blocked Crawler)...\n")
    db_ok = test_create_database()
    if db_ok:
        table_ok = test_create_table()
        if table_ok:
            verify_catalog()