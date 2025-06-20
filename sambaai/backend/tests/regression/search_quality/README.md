# Search Quality Test Script

This Python script evaluates the search results for a list of queries.

Unlike the script in answer_quality, this script is much less customizable and runs using currently ingested documents, though it allows for quick testing of search parameters on a bunch of test queries that don't have well-defined answers.

## Usage

1. Ensure you have the required dependencies installed and sambaai running.

2. Ensure a reranker model is configured in the search settings.
This can be checked/modified by opening the admin panel, going to search settings, and ensuring a reranking model is set.

3. Set up the PYTHONPATH permanently:
   Add the following line to your shell configuration file (e.g., `~/.bashrc`, `~/.zshrc`, or `~/.bash_profile`):
   ```
   export PYTHONPATH=$PYTHONPATH:/path/to/sambaai/backend
   ```
   Replace `/path/to/sambaai` with the actual path to your SambaAI repository.
   After adding this line, restart your terminal or run `source ~/.bashrc` (or the appropriate config file) to apply the changes.

4. Navigate to SambaAI repo, search_quality folder:

```
cd path/to/sambaai/backend/tests/regression/search_quality
```

5. Copy `search_queries.json.template` to `search_queries.json` and add/remove test queries in it

6. Run `generate_search_queries.py` to generate the modified queries for the search pipeline

```
python generate_search_queries.py
```

7. Copy `search_eval_config.yaml.template` to `search_eval_config.yaml` and specify the search and eval parameters
8. Run `run_search_eval.py` to evaluate the search results against the reranked results

```
python run_search_eval.py
```

9. Repeat steps 7 and 8 to test and compare different search parameters

## Metrics
- Jaccard Similarity: the ratio between the intersect and the union between the topk search and rerank results. Higher is better
- Average Rank Change: The average absolute rank difference of the topk reranked chunks vs the entire search chunks. Lower is better
- Average Missing Chunk Ratio: The number of chunks in the topk reranked chunks not in the topk search chunks, over topk. Lower is better

Note that all of these metrics are affected by very narrow search results.
E.g., if topk is 20 but there is only 1 relevant document, the other 19 documents could be ordered arbitrarily, resulting in a lower score.


To address this limitation, there are score adjusted versions of the metrics.
The score adjusted version does not use a fixed topk, but computes the optimum topk based on the rerank scores.
This generally works in determining how many documents are relevant, although note that this approach isn't perfect.