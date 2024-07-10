qna_case_law_tools = [
    {
        "name": "find_caselaw",
        # "description": "what namespace does this query look for ? namespace is defined as the class of question asked. You have access to only the following namespaces: judgement, cause_of_action, case_type, court, interpretations, provisions, ratio, obiter. Depending on the query asked, predict the namespace it belongs to. It can belong to multiple namespaces. If the query is about talking about the cause of action for a case, then look for it in the cause_of_action namespace",
        "description": "what namespace does this query look for ? namespace is defined as the class of question asked. You have access to only the following namespaces: judgement, cause_of_action, interpretations, ratio, obiter, trial_proceedings, misc_details, interpretations. Depending on the query asked, predict the namespace it belongs to. It can belong to multiple namespaces. If the query is about talking about the cause of action for a case, then look for it in the cause_of_action namespace",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "This argument is for searching for the query asked by the user. Paraphrase this into telegraphic style"
                },
                "namespaces": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "uniqueItems": True,
                    "description": "namespaces to be checked for. namespaces denote what the query is looking for. For example: 1. 1. Query: Find case law where a sale deed was given in mala fide for transacting a piece of land. Namespaces: [obiter, cause_of_action, case_timeline, misc_details];"
                },
                "date":{
                    "type": "string",
                    "description": "Lower bound of date mentioned in the query (only if mentioned), with DD-MM-YYYY format, if no date is mentioned, round it down to January 1st of the said year"
                },
                "kwords":{
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "uniqueItems": True,
                    "description": "Strictly use this only when name or provisions or case law titles are mentioned in the query"
                }
            },
            "required": ["query", "namespaces"]
        }
    }
]




