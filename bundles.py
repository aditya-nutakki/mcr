from system_prompts import *
from tool_defs import *

caselaw_search_claude = {
    "id": "gen6",
    "model": "claude-3-5-sonnet-20240620",
    "system_prompt": qna_system_prompt_v6,
    "tools": qna_case_law_tools,
    "temperature": 0.0,
    "available_models": ["claude-3-haiku-20240307", "claude-3-5-sonnet-20240620"],
    "base_url": "",
    "key_env_variable": "ANTHROPIC_API_KEY"
}


bge_finetuned_bundle = {
    "id": "first-sbert-model-123",
    "model": "./models/matryoshka_models_raw/checkpoint-130",
    "device": "cuda",
    "truncate_dim": 512
}

pinecone_all_sc_bundle = {
    "id": "my-unique-pineconevdb-123",
    "index_name": "all-sc-hybrid",
    "host_url": "",
    "metric": "dotproduct",
    "index_type": "hybrid", # can be dense or hybrid
    "sparse_model_path": "./all_sc.json",
    "key_env_variable" : "PINECONE_API_KEY"
}

claude_extraction_bundle_v2 = {
    "id": "my-unique-groq-123",
    "model" : "claude-3-haiku-20240307", # is overwritten later in the script with sonnet-3.5
    "system_prompt": case_extraction_prompt_v2,
    "tools": None,
    "temperature": 0.25,
    "stream_def": None, 
    "available_models": ["claude-3-haiku-20240307", "claude-3-5-sonnet-20240620", "claude-3-opus-20240229"],
    "base_url": "", # defaults to whatever the client has
    "key_env_variable": "ANTHROPIC_API_KEY"
}
