# Reduce database reads and writes during a query

Two small changes that cut how much data the ARS moves to and from the database while a
query runs. Results and behavior are unchanged.

## Changes

- **`remove_blocked` no longer saves.** Post-processing compressed and saved the whole
  merged message once for block-list removal, then again at the end. Now it is stored
  once. The `block/<pk>` endpoint, the only other caller, does its own save.
- **The "is the query done?" check reads only what it needs.** Every time a child message
  was saved, the signal loaded every sibling message in full, including its stored
  response, just to look at statuses. It now fetches the status fields and agent name in
  one query.
- Added unit tests for block-list removal and for when a query is marked Done.

## Results

One recorded CI query (MVP1, 391 merged results) replayed locally, before and after:

| | Before | After |
|---|---|---|
| Read from the database | 73 MB | 14 MB |
| Written to the database | 24 MB | 18 MB |
| Database queries | 202 | 157 |
| Total time | 10.8 s | 10.3 s |

The merged output was identical. The replay uses SQLite in one process, where reads are
nearly free, so the time saved against MySQL should be larger than shown here.