import boto3
from botocore.client import Config

config = Config(
    s3 = {
        'use_accelerate_endpoint': True
    }
)
_s3 = boto3.client('s3', config=config)

def load_from_s3(bucket_name, object_key):
    try:
        response = _s3.get_object(
            Bucket=bucket_name,
            Key=object_key,
        )
        return response["Body"].read()
    except Exception as e:
        # print(f"Error loading object from S3: {str(e)}")
        # return None
        raise Exception(f"Error loading object from S3: {str(e)}")
