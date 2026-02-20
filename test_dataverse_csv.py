import requests
import cgitb
cgitb.enable(format="text")
from langchain_community.document_loaders import CSVLoader

file_url = "https://dataverse.harvard.edu/api/access/datafile/13322684"
print("Downloading...")
content = requests.get(file_url).content
with open("test.csv", "wb") as f:
    f.write(content)

print(f"Downloaded {len(content)} bytes.")

try:
    loader = CSVLoader(file_path="test.csv")
    docs = loader.load()
    print("Loaded docs:", len(docs))
except Exception as e:
    import traceback
    traceback.print_exc()
