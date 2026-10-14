# Evaluation

Repeatable evaluation of retrieval and answer quality. Source: `MASTER_PLAN.md` §26 (methodology there is not final; this is the Milestone 10 implementation).

## Files

- `evaluation/questions.json` — the dataset (30 questions, version 1).
- `evaluation/results/<run id>.json` — saved runs (`<UTC timestamp>-<mode>`).
- `backend/app/rag/evaluation.py` — validation, metrics, checks, runner.
- Admin UI: `/admin/evaluation` (read-only; protected by the admin JWT).

## Running

From `backend/`, with documents indexed and `OPENAI_API_KEY` set:

```bash
uv run python -m scripts.run_evaluation --mode retrieval   # embeddings only (cheap)
uv run python -m scripts.run_evaluation --mode full        # also generates answers
```

The runner first **validates the dataset against SQLite** and refuses to run if a labelled phrase is missing from the indexed chunks, a document is not `READY`, or a term declared absent actually appears. It never indexes, edits or deletes anything, never retries a failed request, and stops after 3 consecutive API errors. Retrieval always uses top-K = 5; production settings are not changed.

## Dataset

Documents: `sample_company_policy` (Northstar Labs handbook, 14 chunks) and `Company Policy (smoke test)` (1 chunk). Categories: direct (9), paraphrase (8), multi-part (7), unsupported (6).

Each answerable question lists **facts**; a retrieved chunk is relevant to a fact when it comes from the named document and contains the phrase (case/whitespace-insensitive). A fact may list several acceptable (document, phrase) pairs. `answer_checks` are groups of alternative substrings; the answer must match every group. Unsupported questions declare `absent_terms` that must not occur in any indexed chunk.

## Metrics

Retrieval (answerable questions only):

- **Recall@5** — mean share of a question's required facts found in the top 5 chunks.
- **Hit@5** — share of questions with at least one relevant chunk in the top 5.
- **MRR** — mean of 1 / rank of the first relevant chunk (0 if none).

Answers (full mode, deterministic, no LLM judge):

- **Correct** — not a refusal and every `answer_checks` group matches.
- **Correct refusal / false refusal** — unsupported questions refused; answerable questions wrongly refused (refusal = the standard "couldn't find" message or a "does not specify / not covered" style phrase).
- **Citation valid / supported** — the answer cites `[Source N]` with N in range; at least one cited chunk contains the expected evidence.
- **Numbers grounded** — every number in the answer appears in the retrieved context or the question. This is a heuristic for invented figures.

Each failing question is tagged `retrieval` (a required fact is missing from the top 5) or `generation` (retrieval was fine but the answer or its citations failed).

## Limitations

- Faithfulness is only approximated (numbers and citations). A fluent answer with a wrong non-numeric claim can pass; catching that needs a human or LLM judge.
- `answer_checks` use substring matching, so a differently phrased correct answer can fail and a keyword-stuffed wrong one can pass.
- Small, single-author dataset over two short fictional documents (one is a one-chunk smoke-test file). Results do not generalize to large or noisy corpora, and similarity scores of unsupported and answerable questions overlap, so a score threshold would not separate them.
- The chat model is not run at a fixed temperature, so answers can vary between runs; one run is one sample.
- Cost is not computed: token usage is recorded from the API responses, but no price table is configured.
