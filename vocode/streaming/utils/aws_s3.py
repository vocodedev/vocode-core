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
