import requests
import json

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

def test():
    query = "\"schizophrenia\" OR \"dopamine\" OR \"glutamate\" OR \"glycine\" OR \"GABA\" OR \"synapse\" OR \"prefrontal cortex\" OR \"cingulate cortex\" OR \"caudate nucleus\" OR \"hippocampus\" OR \"nucleus accumbens\""
    
    # 1. get web_env
    hist_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "usehistory": "y",
        "retmax": "0"
    }
    resp = requests.get(PUBMED_ESEARCH_URL, params=hist_params)
    data = resp.json().get("esearchresult", {})
    web_env = data.get("webenv")
    query_key = data.get("querykey")
    
    print(f"web_env: {web_env}, query_key: {query_key}")
    
    # 2. fetch page 10000 to 20000
    page_params = {
        "db": "pubmed",
        "retmode": "json",
        "usehistory": "y",
        "WebEnv": web_env,
        "query_key": query_key,
        "retstart": "10000",
        "retmax": "10000"
    }
    
    page_resp = requests.get(PUBMED_ESEARCH_URL, params=page_params)
    text = page_resp.text
    print(f"Response length: {len(text)}")
    print(text[:200])
    
    try:
        json_data = json.loads(text, strict=False)
        print("Parsed successfully with strict=False!")
    except Exception as e:
        print(f"Failed with strict=False: {e}")
        
    try:
        json_data = page_resp.json()
        print("Parsed successfully natively!")
    except Exception as e:
        print(f"Failed natively: {e}")

test()
