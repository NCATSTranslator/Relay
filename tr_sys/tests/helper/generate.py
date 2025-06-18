"""Generate an assortment of TRAPI messages."""

import copy
import zstandard as zstd
import json
from pathlib import Path

def generate_query():
    """Give a clean copy of a TRAPI query graph."""
    return copy.deepcopy(creative_query)
def get_curie():
    """ return a list of curies"""
    return copy.deepcopy(curie_list["ids"])

def Compress_large_files(filename):
    file_path=Path(__file__).parent
    #load the JSON data
    with open(f'{file_path}/{filename}', 'r') as f:
        json_data=json.load(f)

    #convert JSON to bytes
    json_bytes = json.dumps(json_data).encode('utf-8')

    #compress the data
    compressed_data = zstd.compress(json_bytes)

    #save the compressed data
    with open(f'{filename}.zst', 'wb') as f:
        f.write(compressed_data)


def get_ARA_response():
    """ return a sample ARA response to a query """
    file_path=Path(__file__).parent

    with open(f'{file_path}/aragorn-resp.json.zst', 'rb') as f:
        dctx = zstd.ZstdDecompressor()
        decompressed = dctx.decompress(f.read())
    #Convert to string and parse as JSON
    json_str = decompressed.decode('utf-8')
    data = json.loads(json_str)
    return data

creative_query = {
    "message": {
        "query_graph": {
            "nodes": {
                "SN": {
                    "categories": ["biolink:ChemicalEntity"]
                },
                "ON": {
                    "ids": ["MONDO:0011705"],
                    "categories": ["biolink:Disease"]
                },
            },
            "edges": {
                "t_edge": {
                    "subject": "SN",
                    "object": "ON",
                    "predicates": ["biolink:treats"],
                    "knowledge_type": "inferred"
                }
            }
        }
    }
}

curie_list={
    "ids": [
        "CHEBI:16469",
        "GO:0006703",
        "MONDO:0011705",
        "CHEBI:18059",
        "CHEBI:26764",
        "CHEBI:9123",
        "NCBIGene:1576",
        "CHEBI:41774",
        "NCBIGene:1588",
        "CHEBI:6931"
    ]
}
if __name__ == "__main__":
    #Compress_large_files('appraiser_data_input.json')
    #Compress_large_files('aragorn-resp.json')
    get_ARA_response()