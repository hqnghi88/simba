import sys
from langchain_community.document_loaders import CSVLoader

file_path = "/Users/hqnghi/git/simba/uploads/era-agriculture/01a. ERA_Compiled_2025.csv"

try:
    loader = CSVLoader(file_path=file_path)
    docs = loader.load()
    print("Loaded successfully, doc count:", len(docs))
except Exception as e:
    import traceback
    traceback.print_exc()
