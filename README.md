# Search for legal precedents with the help of LLM's and Embedding Models

## Overview:
Access to legal precedents is not easy as they are either hidden behind an expensive pay wall or they are scattered across the internet (due to lack of organization). We are currently working with an NGO called OpenNyAI (Nyai - the hindi word for "justice") in India to solve this problem. 

## Motive:
It is to develop a cost-effective alternative to Indian legal databases so that access to these judgements can be seemless for lawyers and paralegals. We were able to develop this with ~$250 (for all supreme court cases, 1950 - 2024)

## Implementation:
This is done primarily in 3 steps:
<br><br>
<b>Step 1 -</b>
<ul>
<li>Multi-angle summarization: We first process each judgement and extract information such as case brief, case timeline, ratio, obiter, interpretations, trial proceedings etc. This was done with the help of claude, where we indexed ~36k judgements.</li>
<li>We used the speak-for-claude feature to produce valid JSON. It produced the desired schema ~85% of the time. The remaining judgements had to be sanitized with the help of other post processing scripts.</li>
<li>claude-3-haiku and claude-3-5-sonnet were used with different probabilities. About 90% of the judgements were indexed with haiku</li>
<li>Typically, answers to questions posed by lawyers/paralegals extend across multiple chunks or pages. We could not rely on traditional chunking-based RAG because we found that unless the chunk is rich in information/facts, they don't usually contain the answer to the user's query. This is the reason we decided to extract information so as to remove noise.</li>
</ul>
<b>Step 2 -</b> Generating synthetic data to fine tune an embedding model: <br>
An out of the box embedding model does not fare well with our specific use case of catering to indian law and so a result we resort to fine tuning an embedding model. We provided random excerpts from judgements, and claude was instructed to generate a question out of it in telegraphic style or in natural language. This was done to generalize for both natural language queries and keyword based queries. We leveraged SBERT and BAAI/bge-base-en-v1.5. It has been fine-tuned with matryoshka loss so as to retain performance even after truncating the number of dimensions. The model was truncated to 512 dimensions and acheived a top-10 retrieval accuracy of ~90% (more work can be done here)<br><br>
<b>Step 3 -</b> Upserting data with dense and sparse embeddings:<br>
We use BM25 as the sparse encoder and the fine-tuned model as the dense embedding model. Dense embeddings don't accurately capture certain phrases like "Section 9A of the companies act". This is where we introduce sparse embeddings to enable us to retrieve relevant information based off of keywords. We used pinecone as our vector database<br><br>

<b>Step 4 -</b> Inference: <br>
This is strictly done with claude-3.5-sonnet as it proved to be quite robust in extracting information out of the user's query. This model is instructed to analyse the query by thinking step-by-step (as per <a href = "https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-prompts">this anthropic doc</a>) and then formulate a search query in a style similar to how we have trained our embedding model. The model then tells us the various "angles" the query needs to be searched in. These are also called "namespaces" in pinecone. The results are then sorted based on similarity score and finally sent back to the user.

## Future Scope of work:
<ul>
  <li>Semantic Deduplication: There seems to be some indexed data which is vague and shallow. For example, the judgement for a handful of cases were along the lines of "the appellant's petition was rejected". This does not provide us enough information; so to get rid of near duplicates, a promising method seems to be using semantic deduplication. This would help us get a wider variety of data points which can help us train better embedding models and have stronger generalization</li>
  <li>Scaling this to the high courts: The scale that we have worked on is a relatively small dataset (~36k judgements). There are about 13M judgements in the highcourt. It would be interesting to see how this would scale out !</li>
</ul>


## Quick Demo
![](https://github.com/aditya-nutakki/claude-search/blob/main/demo.gif)
