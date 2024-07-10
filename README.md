# Find legal precedents with the help of claude

## Overview:
We are currently working with an NGO called OpenNyAI (nyai - the hindi word for "justice") in India. Access to legal precedents is not easy as they are either hidden behind an expensive pay wall or they are scattered across the internet (due to lack of organization)

## Motive:
Develop a cost-effective alternative to indian legal databases so that access these judgements can be easy for lawyers and paralegals. We were able to develop this with ~$250 (for all supreme court cases, 1950 onwards)

## Implementation:
This is done primarily in 3 steps:
<br><br>
<b>Step 1 -</b>
<ul>
<li>Multi-angle summarization: We first process each judgement and extract information such as case brief, case timeline, ratio, obiter, interpretations, trial proceedings etc. This was done with the help of claude and we indexed ~36k judgements</li>
<li>We used the speak for claude feature to produce valid JSON and it produced the desired schema ~85% of the time. The remaining ones had to be sanitized with the help of other post processing scripts.</li>
<li>claude-3-haiku and claude-3-5-sonnet were used with different probabilities. Since this was a pilot project, we didn't want to spend too much. About 90% of them were indexed with haiku</li>
<li>We could not rely on traditional chunking based RAG because we found that unless the chunk size is rich in information/facts, they don't usually contain the answer to the user's query. Typically, answers to questions posed by lawyers/paralegals extend across multiple chunks or pages. This is the reason we decided to extract information so as to remove noise </li>
</ul>
<b>Step 2 -</b> Generating synthetic data to fine tune an embedding model: <br>
An out of the box embedding model does not fare well with our specific use case of catering to indian law and so a result we resort to fine tuning an embedding model. We picked out judgements at random and then given a certain excerpt, claude was instructed to generate a question out of it in telegraphic style or in natural language. This was done to better generalize for both natural language queries and keyword based queries. We leveraged SBERT and BAAI/bge-base-en-v1.5. It has been fine-tuned with matryoshka loss so as to retain performance even after truncating the number of dimensions. The model was truncated to 512 dimensions and acheived a top-10 retrieval accuracy of ~90% (more work can be done here)<br><br>
<b>Step 3 -</b> Upserting data with dense and sparse embeddings:<br>
We use BM25 as the sparse encoder and the fine-tuned model as the dense embedding model. Dense embeddings alone don't capture certain phrases like "section 9A of the companies act" too well. This is where we introduce sparse embeddings to enable us to retrieve more relevant information. We used pinecone as our vector database<br><br>

<b>Step 4 -</b> Inference: <br>
This is strictly done with claude-3.5-sonnet as it proved to be quite robust in extracting information out of the prompt. This model is instructed to analyse the query thinking step-by-step (as per <a href = "https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-prompts">this anthropic doc </a>) and then formulate a search query in a style similar to how we have trained our embedding model. The model then tells us the various "angles" the query needs to be searched in. These are also called "namespaces" if you're coming from pinecone and "index" if you're coming from elasticsearch. The results are then sorted and finally sent back to the user.

## Future Scope of work:
<ul>
  <li>Semantic Deduplication: There seems to be some indexed data which is vague and shallow. For example, the judgement for a handful of cases were along the lines of "the appellant's petition was rejected". This does not provide us enough information; so to get rid of near duplicates, a promising method seems to be using semantic deduplication. This would help us get a wider variety of data points which can help us train better embedding models and have stronger generalization</li>
  <li>Scaling this to the high courts: The scale that we have worked on is a relatively small dataset (~36k judgements). There are about 13M judgements in the highcourt. It would be interesting to see how this would scale out !</li>
</ul>


## Quick Demo
![](https://github.com/aditya-nutakki/claude-search/blob/main/demo.gif)
