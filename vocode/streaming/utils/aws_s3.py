import boto3
from botocore.client import Config
import concurrent.futures
import functools
import asyncio

config = Config(
    s3 = {
        'use_accelerate_endpoint': True
    }
)
_s3 = boto3.client('s3', config=config)
executor = concurrent.futures.ThreadPoolExecutor()
from aiobotocore.session import get_session

def aio(f):
    '''Takes a synchronous function 
    and returns a corresponding async coroutine '''
    async def aio_wrapper(**kwargs):
        f_bound = functools.partial(f, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, f_bound)
    return aio_wrapper

get_object_async = aio(_s3.get_object)

async def load_from_s3(bucket_name, object_key):
    try:
        response = await get_object_async(
            Bucket=bucket_name,
            Key=object_key,
        )
        return response["Body"].read()
    except Exception as e:
        raise Exception(f"Error loading object from S3: {str(e)}")
    
async def load_from_s3_async(bucket_name, object_key, s3_client) -> bytes:
    """
    Asynchronously loads an object from an AWS S3 bucket using an S3 client.

    Args:
        bucket_name (str): The name of the AWS S3 bucket where the object is stored.
        object_key (str): The key (path) of the object within the S3 bucket.
        s3_client (aiobotocore.client.AioBaseClient): An AWS S3 client instance used for making requests.

    Returns:
        bytes: The content of the S3 object as bytes.

    Usage:
        # Example usage within an async function:
        import aiohttp
        import aiobotocore

        async def fetch_data_from_s3():
            with aiobotocore.get_session().create_client('s3') as s3_client: 
                # Specify the AWS S3 bucket name and object key.
                bucket_name = 'my-s3-bucket'
                object_key = 'path/to/my-object.txt'
                s3_data = await load_from_s3_async(bucket_name, object_key, s3_client)

        asyncio.run(fetch_data_from_s3())
    """
    
    response = await s3_client.get_object(Bucket=bucket_name, Key=object_key)
    async with response['Body'] as stream:
        return await stream.read()

