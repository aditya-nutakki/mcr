import os, json
import sys
from dotenv import load_dotenv
from time import sleep
from script_utils import *
import uuid

load_dotenv()

# meant to be run as a standalone file after cd'ing into this dir
sys.path.append("../")

from modules import *
from bundles import *

from random import random, choice, uniform
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder

from sentence_transformers import SentenceTransformer

from time import time, sleep
from copy import deepcopy

from concurrent.futures import ThreadPoolExecutor
import threading

"""
Things to do:
    1. upsert EVERYTHING precedent wise into their respective namespaces
    2. Embed it with the custom trained model
    3. Hybrid embeddings - dont forget to embed with "dotproduct" and use normalised embeddings
    4. 


Things to explore:
    1. Further training your embedding model on synthetic data across supreme court cases
    2. Better prompting techniques
    3. Semantic de-duplication for info which was indexed
    4. 

"""


"""
example of each judgement in question:

{
    "case_title": "VIVEK NARAYAN SHARMA VS. UNION OF INDIA",
    "doj": "02-01-2023",
    "case_type": "(WRIT PETITION (CIVIL) /906/2016)",
    "normal_citation": "[2023] 1 S.C.R. 1",
    "neutral_citation": "2023 INSC 2",
    "download_link": [
        "https://digiscr.sci.gov.in/pdf_viewer?dir=YWRtaW4vanVkZ2VtZW50X2ZpbGUvanVkZ2VtZW50X3BkZi8yMDIzL3ZvbHVtZSAxL1BhcnQgSS8yMDIzXzFfMS0yMzBfMTcwMzE2MzMyOC5wZGY="
    ],
    "download_status": true,
    "save_path": "./scr2/[2023]_1_S.C.R._1.pdf",
    "case_id": "8370e9b5-b6a5-485f-804b-4080cddb7893",
    "indexed_file_path": "/mnt/d/work/projects/agents/scripts/processed_data/[2023]_1_S.C.R._1.json"
}
"""


namespaces = ["judgement", "case_brief", "prayers", "cause_of_action", "allegation", "interpretations", "trial_proceedings", "misc_details", "prior_history", "case_timeline", "ratio", "obiter", "plaintiff_arguments", "respondent_arguments"]
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
pc = Pinecone(api_key = PINECONE_API_KEY)

index = pc.Index(host = "https://all-sc-hybrid-ss7yj2b.svc.aped-4627-b74a.pinecone.io")


# manager = multiprocessing.Manager()
# lock = manager.Lock()


def init_tracker(tracker_path):
    if os.path.exists(tracker_path):
        return read_json(tracker_path)
    
    else:
        
        # tracker = [{
        #                 "case_id": "",
        #                 "case_title": "",
        #                 "doj": "",
        #                 "case_type": "",
        #                 "normal_citation": "",
        #                 "neutral_citation": "",
        #                 "doc_source": "",
        #                 "type": "",
        #                 "excerpt": ""
        #             }]
        
        tracker = {}

        write_json(data = tracker, filepath = tracker_path)
        return tracker


def init_embedding_model(model_path, device = "cuda", truncate_dim = 768):
    return SentenceTransformer(model_path, device = device, truncate_dim = truncate_dim)


def init_sparse_embedding_model(model_path):
    # by default loads only BM25 model
    return BM25Encoder().load(model_path)


def upsert_pinecone(vectors, namespace):
    assert namespace != "", "Namespace cannot be blank!"
    # stime = time()
    index.upsert(
        vectors = vectors,
        namespace = namespace
    )
    # ftime = time()
    # print(f"took {ftime-stime} to upsert")
    # print(f"done with {vectors} and {namespace}")


def _prepare_hybrid_vectors(data, namespace, metadata, dense_embedding_model, sparse_embedding_model):

    def generate_dense_embedding(text):
        if isinstance(text, str):
            return dense_embedding_model.encode(text, normalize_embeddings = True).tolist()
        return 
    
    
    def generate_sparse_embedding(text):
        if isinstance(text, str):
            return sparse_embedding_model.encode_documents(text) # ensure this is "encode_documents" while upserting as per pinecone documentation -> https://docs.pinecone.io/guides/data/encode-sparse-vectors
        return


    # for namespace in namespaces:
    vectors = []
    original_metadata = metadata

    try:
        info = data[namespace] # the namespace MUST exist in the JSON file
    except:

        try:
            if namespace == "plaintiff_arguments":
                info = data["arguments"]["plaintiff"]

            elif namespace == "respondent_arguments":
                info = data["arguments"]["respondent"]

        except Exception as e:
            print(f"failed getting space because of {e}; {data}")
            return vectors

    print(f"doing {namespace}")
    if isinstance(info, str):
        if info:
            info = [info]
        else:
            return vectors
     
    if isinstance(info, list):
        # list of strings
        for _info in info:
            if _info:
                # doing it serially instead of parallely to avoid crashing (might happen because of data structure ambiguity)
                _info_embedding = generate_dense_embedding(_info) # dense embedding
                _info_sparse_embedding = generate_sparse_embedding(_info)

                # print(_info_embedding, type(_info_embedding), len(_info_embedding))

                if _info_embedding and _info_sparse_embedding:
                    metadata = deepcopy(original_metadata)
                    metadata["excerpt"] = _info
                    vectors.append({"id": str(uuid.uuid4()), "values": _info_embedding, "sparse_values": _info_sparse_embedding, "metadata": metadata})


    return vectors


def save_to_tracker_v2(tracker_path, judgement_path, vectors, namespace):
    for vec in vectors:
        del vec["values"], vec["sparse_values"]

    if judgement_path in tracker_path:
        # appending to something that exists
        judgement_data = read_json(judgement_path)
        judgement_data[namespace] = vectors

    else:
        # writing it for the first time
        judgement_data = {namespace: vectors}
    
    # with lock:
    #     with open(judgement_path, "w") as f:
    #         json.dump(judgement_data, f)

    write_json(judgement_data, judgement_path)


def upsert_judgements(judgements_path, tracker_path):

    lock = threading.Lock()

    def _prepare_vectors_and_upsert(namespace):
        metadata = {
                        "case_id": case_id,
                        "case_title": case_title,
                        "doj": doj,
                        "case_type": case_type,
                        "normal_citation": normal_citation,
                        "neutral_citation": neutral_citation,
                        "doc_source": doc_source,
                        "type": namespace
                    }
        namespace_vectors = _prepare_hybrid_vectors(indexed_data, namespace, metadata = metadata, dense_embedding_model = model, sparse_embedding_model = bm25)
        if namespace_vectors:
            # print(namespace_vectors)
            try:
                upsert_pinecone(vectors = namespace_vectors, namespace = namespace)                

            except Exception as e:
                print(f"failed upsert/saving because: {e}; {i}")
                
            try:
                with lock:
                    save_to_tracker_v2(upserted_paths, judgement_path, vectors = namespace_vectors, namespace = namespace)
                    upserted_paths.append(judgement_path)
            except Exception as e:
                print(f"Failed to save tracker path because {e}; {namespace}")


    def _upsert_namespace(namespace):
        if judgement_path in upserted_paths:
            judgement_data = read_json(judgement_path)

            if namespace in judgement_data:
                print(f"continuing {namespace} since it exists")

            else:
                _prepare_vectors_and_upsert(namespace)

        else:
            _prepare_vectors_and_upsert(namespace)


    judgements = read_json(judgements_path)
    os.makedirs(tracker_path, exist_ok = True)

    upserted_paths = [os.path.join(tracker_path, judgement) for judgement in os.listdir(tracker_path)]

    model = init_embedding_model(model_path = "/mnt/d/work/projects/agents/playbooks/models/matryoshka_models_raw/checkpoint-130", device = "cuda", truncate_dim=512) # using 512 since this model was trained with matryoshka loss -> https://sbert.net/examples/training/matryoshka/README.html
    bm25 = init_sparse_embedding_model(model_path = "./all_sc.json")

    offset = 0

    for i, judgement in enumerate(judgements):
        
        if i < offset:
            continue

        if i % 100 == 0 and i != 0:
            print(f"------------------------; {i}")
            sleep(5)

        if "indexed_file_path" not in judgement:
            print(f"Continuing on {i}th judgement")
            continue

        stime = time()
        case_id = judgement["case_id"]
        case_title = judgement["case_title"]
        doj = judgement["doj"]
        case_type = judgement["case_type"]
        normal_citation = judgement["normal_citation"]
        neutral_citation = judgement["neutral_citation"]
        doc_source = judgement["download_link"][0] # this might be changed in future
        indexed_file_path = judgement["indexed_file_path"]

        indexed_data = read_json(indexed_file_path)

        print(tracker_path, normal_citation.replace(" ", "_") + ".json")
        judgement_path = os.path.join(tracker_path, normal_citation.replace(" ", "_") + ".json")

        if indexed_data:

            with ThreadPoolExecutor(max_workers = 20) as executor:
                _ = executor.map(_upsert_namespace, namespaces)

        ftime = time()
        
        print(f"judgement done in {ftime-stime}; {i}")
        print()
        


def fit_bm25(judgements_path, save_path):
    
    judgements = read_json(judgements_path)
    # judgements expected to be sanitized by the time they reach this step

    corpus = []
    skipped = 0

    for i, judgement in enumerate(judgements):
        
        if "indexed_file_path" not in judgement:
            print(f"Continuing on {i}th judgement")
            skipped += 1
            continue

        indexed_judgement = read_json(judgement["indexed_file_path"])
        for namespace in namespaces:
            if namespace in indexed_judgement:
                content = indexed_judgement[namespace]
                
                if isinstance(content, str):
                    if content:
                        content = [content]
                        corpus.extend(content)

                elif isinstance(content, dict):
                    # arguments case
                    _keys = list(content.keys())
                    for _key in _keys:
                        _key_content = content[_key] 
                        if _key_content:
                            corpus.extend([x for x in _key_content if isinstance(x, str)])

                elif isinstance(content, list):
                    corpus.extend([x for x in content if isinstance(x, str)])
        
    print(f"fitting on {len(corpus)} data; skipped {skipped} ...")
    
    # write_json(corpus, "./mycorpus.json")
    bm25 = BM25Encoder()
    bm25.fit(corpus)
    
    print("Done !")
    bm25.dump(save_path)


def hybrid_score_norm(dense, sparse, alpha: float):
    """Hybrid score using a convex combination

    # alpha being 1 is purely semantic and alpha being 0 is purely sparse

    alpha * dense + (1 - alpha) * sparse

    Args:
        dense: Array of floats representing
        sparse: a dict of `indices` and `values`
        alpha: scale between 0 and 1
    """
    if alpha < 0 or alpha > 1:
        raise ValueError("Alpha must be between 0 and 1")
    hs = {
        'indices': sparse['indices'],
        'values':  [v * (1 - alpha) for v in sparse['values']]
    }
    return [v * alpha for v in dense], hs


def test_retrieve():
    query = "find case law where section 24 (2) of the Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act, 2013 was part of the ratio"
    
    model = init_embedding_model(model_path = "/mnt/d/work/projects/agents/playbooks/models/matryoshka_models_raw/checkpoint-130", device = "cuda", truncate_dim=512) # using 512 since this model was trained with matryoshka loss -> https://sbert.net/examples/training/matryoshka/README.html
    bm25 = init_sparse_embedding_model(model_path = "./all_sc.json")

    while True:
        query = input("enter: ")
        embedding = model.encode(query, normalize_embeddings=True).tolist()
        sparse_embedding = bm25.encode_queries(query)

        embedding, sparse_embedding = hybrid_score_norm(embedding, sparse_embedding, alpha = 0.8)

        results = index.query(vector = embedding, top_k = 10, sparse_vector = sparse_embedding, include_metadata = True, namespace = "ratio")
        print(results)
        print("----------------------------------------")
        print()
        print()
        


if __name__ == "__main__":
    judgements_path = "./final_mapping.json"
    # fit_bm25(judgements_path = judgements_path, save_path = "./all_sc.json")
    upsert_judgements(judgements_path, tracker_path = "/mnt/d/work/projects/agents/scripts/upsert_tracker")
    # test_retrieve()


