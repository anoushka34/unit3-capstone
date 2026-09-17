import boto3
import os

#initalize the boto client
s3_client = boto3.client('s3')

bucket_name = 'unit3capstoneac'
region = 'us-east-1'

def create_bucket_and_upload():
    print(f"Creating bucket {bucket_name}")
    try: 
        #check if us-east-1 works otherwise find another one
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)

        else:
            s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint':region})

        print("bucket created successfully")

    except Exception as e:
        print(f"Bucket creation exception {e}")

    local_file = 'data/data.csv'

    s3_key = 'structured-data/data.csv'

    if os.path.exists(local_file):
        print(f"uploading {local_file} to s3://{bucket_name}/{s3_key}...")

        s3_client.upload_file(local_file, bucket_name, s3_key)

    else:
        print(f"error: {local_file} not found")

if __name__ == "__main__":
    create_bucket_and_upload()