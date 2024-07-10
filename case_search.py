import os, json
from dotenv import load_dotenv
from system_prompts import *
from bundles import *

load_dotenv()

from modules import *


class CaseLawSearch(BaseClaudeAgent):
    def __init__(self, bundle, embedding_bundle):
        super().__init__(bundle = bundle)
        self.embedding_engine = SBERTEmbedder(bundle = embedding_bundle)
        self.vdb = PineconeVDB(bundle = pinecone_all_sc_bundle, embedding_engine = self.embedding_engine)


    def pretty_print(self, retrieved_context):
        statements = []
        print()
        for i, result in enumerate(retrieved_context):
            statement = f"{i + 1}. {result['excerpt']}; source: {result['doc_source']}"
            print(statement)
            statements.append(statement)
            print()
        return "\n".join(statements)



    def find_caselaw(self, user_query, **kwargs):

        query, namespaces = kwargs["query"], kwargs["namespaces"] # function definition has these 2 parameters as "required" so not using 'get'
        kwords = kwargs.get("kwords", "")

        alpha = 0.2 if kwords else 0.4 # found that leaning more towards keywords search is more accurate

        retrieved_context = self.vdb.retrieve_namespaces(query = query, namespaces = namespaces, top_k = 10, alpha = alpha, threshold =  0.15)
        statements = self.pretty_print(retrieved_context)
        return "" # temporary only
        

    def __call__(self, context, **kwargs):
        response = self._process_call(context, **kwargs)
        print(response)
        return response


if __name__ == "__main__":
    search = CaseLawSearch(bundle = caselaw_search_claude, embedding_bundle = bge_finetuned_bundle)

    # query = "find case law where an application to amend written objections during evidence stage was rejected"
    # query = "case law where respondent was caught smuggling gold into India"
    # query = "can you find case laws that set out the guidelines or circumstances under which an amendment should be granted ?"

    while True:
        query = input("search for: ")
        context = [{"role": "user", "content": query}]
        
        response = search(context, stream = True)
        for x in response:
            print(x, end = "")

        print()
        print("-----------------------------------------------------------------------")
        print()


