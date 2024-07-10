from anthropic import Anthropic

from dotenv import load_dotenv
from system_prompts import *
from tool_defs import *
from utils import *
import os, json

from time import time, sleep
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from sentence_transformers import SentenceTransformer

from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder

load_dotenv()


class BaseClaudeAgent():

    def __init__(self, bundle):
        self.id = bundle["id"]
        self.model = bundle["model"]
        self.tools = bundle["tools"]
        self.temperature = bundle["temperature"]
        
        self.available_models = bundle["available_models"]
        self.base_url = bundle["base_url"]

        self.system = bundle["system_prompt"]
        self.client = self._init_client(base_url = self.base_url, key = os.getenv(bundle["key_env_variable"]))
        
        if not self.tools:
            self.tools = [] # Anthropic Client wants tools to be '[]' and not 'None'

        print(f"Initializing id with {self.id}\n")
        print(f"Initializing model with {self.model}\n")
        print(f"Initializing system_prompt with {self.system}\n")
        print(f"Initializing tools with {self.tools}\n")
        print(f"Initializing temperature with {self.temperature}\n")
        print("___________________________________________")


    def _init_client(self, base_url, key):
        if base_url:
            client = Anthropic(base_url = base_url, auth_token = key)
        else:
            client = Anthropic(auth_token = key)
        
        return client
    

    def _find_secondary_model(self, model):
        # in case you want to use a smaller/faster model for a task
        idx = self.available_models.index(model)
        if idx == 0:
            return model
        return self.available_models[idx - 1]


    def process_prompt(self, role, content):
        return [{"role": role, "content": content}]


    def _get_latest_user_query(self, context):
        for message in context:
            if message["role"] == "user":
                query = message["content"]
        return query


    def _unconditional_stream(self, response, user_query):
        text_response, json_stream = "", ""
        total_stream = ""
        for chunk in response:
            if chunk.type == "content_block_delta":
                if chunk.delta.type == "text_delta":
                    text_response += chunk.delta.text
                    total_stream += chunk.delta.text
                    yield chunk.delta.text
                    
                elif chunk.delta.type == "input_json_delta":
                    json_stream += chunk.delta.partial_json
                    total_stream += chunk.delta.partial_json

            elif chunk.type == "content_block_start":
                # could be either 'text' or 'tool_use'; but here we only look for tool_use
                if chunk.content_block.type == "tool_use":
                    func_name = chunk.content_block.name
                    func_input = chunk.content_block.input

        if json_stream:
            # execute whatever function call
            json_stream = json.loads(json_stream)
            print(f"calling {func_name} with {json_stream} ...")
            # eval(func_name)(**json_response) 
    
            func_response = getattr(self, func_name)(user_query, **json_stream) # this function should also take care of processing calls again and should exist within the object
            for chunk in func_response:
                total_stream += chunk
                yield chunk
   

    def _call_once(self, context, system = "", model = "", tools = [], temperature = None, stream = False, use_slave = False):
        
        system = system if system else self.system
        model = model if model else self.model
        temperature = temperature if temperature else self.temperature
        tools = tools if tools else self.tools

        if use_slave:
            model = self._find_secondary_model(self.model)

        # print(f"using model: {model}; use_slave: {use_slave}")
        # print(f"using system prompt: {system}")
        # print(f"using temperature: {temperature}")
        # print(f"using stream: {stream}")
        # print()
        
        # print(f"sending context: {context}")

        return self.client.messages.create(
            model = model,
            max_tokens = 4096 - 1,
            system = system,
            tools = tools,
            messages = context,
            temperature = temperature,
            stream = stream
            )
    

    def _process_call(self, context, **kwargs):

        # wrapper around _call_once
        user_query = self._get_latest_user_query(context = context)
        response = self._call_once(context = context, **kwargs)
        return self._unconditional_stream(response, user_query = user_query)
        


class SBERTEmbedder():
    def __init__(self, bundle) -> None:
        self.id = bundle["id"]
        self.model_path = bundle["model"]
        self.device = bundle["device"]
        self.truncate_dim = bundle["truncate_dim"]

        self.model = self.init_model()


    def init_model(self):

        if not os.path.exists(self.model_path):
            self.model_path = "BAAI/bge-base-en-v1.5" # in case you dont have the fine tuned embedding model; set it to default
            print("LOADING WITH DEFAULT, since fine-tuned model not available")
            
        if self.truncate_dim == -1:
            model = SentenceTransformer(self.model_path, device = self.device)
        else:
            # ensure model is trained with matryoshka loss before setting truncate_dim
            model = SentenceTransformer(self.model_path, device = self.device, truncate_dim = self.truncate_dim)
        return model


    def encode(self, queries):
        # queries can either be a single text of type str OR can be a list of strings
        return self.model.encode(queries, normalize_embeddings = True).tolist()

  
    def get_embedding(self, text):
        return self.encode(queries = text)



class PineconeVDB():
    def __init__(self, bundle, embedding_engine):

        self.id = bundle["id"]
        self.index_name = bundle["index_name"]

        self.client = Pinecone(api_key = os.getenv(bundle["key_env_variable"])) # maybe not pass this as an attribute ? directly init it ?
        self.metric = bundle.get("metric", "cosine")

        if "host_url" in bundle:
            self.host_url = bundle["host_url"]
            self.index = self.client.Index(host = self.host_url, metric = self.metric)

        else:
            self.index = self.client.Index(name = self.index_name, metric = self.metric)


        self.embedding_engine = embedding_engine
        self.index_type = bundle["index_type"]
        if self.index_type == "hybrid":
            self.sparse_encoder = BM25Encoder().load(bundle["sparse_model_path"])
            # print(f"loaded sparse model from {bundle['sparse_model_path']}")


    def hybrid_score_norm(self, dense, sparse, alpha: float):
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


    
    def retrieve(self, dense_embedding, sparse_embedding, namespace, alpha = 0.5,  top_k = 10):

        if self.index_type == "dense":
            # ignore sparse_embedding here
            results = self.index.query(
                namespace = namespace,
                vector = dense_embedding,
                top_k = top_k,
                include_metadata = True # it should always be set to True
            )


        elif self.index_type == "hybrid":
            
            dense_embedding, sparse_embedding = self.hybrid_score_norm(dense = dense_embedding, sparse = sparse_embedding, alpha = alpha)

            results = self.index.query(
                namespace = namespace,
                vector = dense_embedding,
                sparse_vector = sparse_embedding,
                top_k = top_k,
                include_metadata = True
            )

        return self.process_results(results)
        

    def process_results(self, results):
        processed_matches = []
        for result in results["matches"]:
            metadata = result["metadata"]
            metadata["score"] = result["score"]
            processed_matches.append(metadata)

        return processed_matches
    

    def rerank(self, results):
        results = sorted(results, key = lambda x: x["score"], reverse = True)
        unique_cases, visited = [], []

        for x in results:
            if x["case_id"] not in visited:
                visited.append(x["case_id"])
                unique_cases.append(x)

        return unique_cases


    def generate_embeddings(self, text):
        return self.embedding_engine.get_embedding(text = text) # by default always send normalized embeddings


    def retrieve_namespaces(self, query, namespaces, top_k = 10, alpha = 0.5, threshold = 0.15):
        dense_embedding = self.generate_embeddings(text = query)
        sparse_embedding = self.sparse_encoder.encode_queries(query) if self.index_type == "hybrid" else {}
    
        with ThreadPoolExecutor() as executor:    
            search_results = list(executor.map(lambda namespace: self.retrieve(dense_embedding, sparse_embedding, namespace, alpha = alpha, top_k = top_k), namespaces))
        

        search_results = [result for ns_search_result in search_results for result in ns_search_result if result["score"] >= threshold]
        return self.rerank(search_results)
