import os
import pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import SpacyTextSplitter
from langchain.vectorstores import Pinecone
from langchain.document_loaders import DirectoryLoader, UnstructuredFileLoader

PINECONE_API_KEY = 'XXXXXXXXXX'
PINECONE_ENVIRONMENT = 'XXXXXXXXXX'
OPENAI_API_KEY = 'XXXXXXXXXX'


try:
    loader = DirectoryLoader('./docs', glob="**/*.*", show_progress=True, loader_cls=UnstructuredFileLoader)
    print("Loading documents...")
    documents = loader.load()
    text_splitter = SpacyTextSplitter(chunk_size=1000)
    print("Splitting documents...")
    docs = text_splitter.split_documents(documents)
    print("embeddings documents...")
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

    pinecone.init(
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENVIRONMENT,
    )

    index_name = "XXXXXXXXXX"

    print("Creating index...")
    docsearch = Pinecone.from_documents(docs, embeddings, index_name=index_name)
    print("Index created successfully.")
except Exception as e:
    print(f"An error occurred: {e}")