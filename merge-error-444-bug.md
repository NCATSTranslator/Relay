# Merge errors: 444 vs. other codes in the query-completion check

Found while reviewing `tr_sys/tests/unit/test_query_completion.py`. The behaviour predates the `db-performance` branch; nothing here was introduced by it.

## Summary

When a merged message (a child owned by `ars-ars-agent`) ends in status `E`, `message_post_save` handles code 444 differently from every other code. The two branches give the same result in almost every case, and in the one case where they differ, the 444 branch crashes and leaves the query stuck at `R`.

## The code

`tr_sys/tr_ars/signals.py:72-77`, inside the loop over the parent's children:

```python
if child_status == 'E' and child_agent == 'ars-ars-agent':
    if child['code'] == 444:
        merge_count += 1      # count the failed merge as a merge
    else:
        orig_count -= 1       # stop waiting for a merge of that ARA's answer
```

The parent is marked Done when `finished and merge_count == orig_count`.

444 is the code `post_process` in `tr_ars/utils.py` assigns when blocklist removal, node annotation, or score-stat calculation fails.

## Issue 1: the two branches are equivalent for the completion decision

`merge_count + 1 == orig_count` and `merge_count == orig_count - 1` are the same condition. Whichever branch runs, the parent completes at exactly the same moment.

The only thing the branches change is which completion path runs afterwards (`signals.py:85`):

| Counts at completion | Path taken |
|---|---|
| both zero | create an empty merged message, mark parent Done |
| otherwise | read `pmessage.merged_version`, send `last_merged_completed`, mark parent Done |

So the distinction only matters when no merge has succeeded.

## Issue 2: 444 crashes when no merge has succeeded

Scenario: one ARA returns results, and its merge fails.

| Merge error code | Counts | Result |
|---|---|---|
| 500 (any non-444) | `orig_count` 0, `merge_count` 0 | Empty merged message created, parent goes to `D` |
| 444 | `orig_count` 1, `merge_count` 1 | `AttributeError: 'NoneType' object has no attribute 'id'` at `signals.py:112` |

In the 444 case the handler takes the "otherwise" path and reads `pmessage.merged_version.id`, but no merge ever succeeded, so `merged_version` is `None`. The exception is raised out of the merged message's `save()`, before the parent is marked Done, so the parent stays at `R`.

The general condition is: the query reaches completion with no successful merge and at least one merge that failed with 444. A mix of 444 and non-444 failures with no successes hits it too.

Both rows were reproduced with a scratch test against the current handler. I have not confirmed how often this happens in production; it needs a post-processing failure on the merged message before any merge for that query has succeeded.

## Suggested fix

Pick the completion path from what it actually depends on: take the empty-merged-message path when `pmessage.merged_version is None`, instead of when both counts are zero. That covers the 444 case and leaves every currently working case unchanged. This is a suggestion; I have not implemented or tested it.

With that in place, the 444 / non-444 split in the counting loop no longer affects anything and could be collapsed into one branch.

## Tests

- `test_query_is_done_when_the_last_merge_errors[444, 500]` passes for both codes, but it cannot tell the branches apart (Issue 1). Its docstring describes a distinction the test does not check and should be reworded to "a failed merge does not hang the query".
- No current test covers Issue 2. The fix should come with one: a single ARA with results, a merge that errors with 444, and an assertion that the parent ends at `D` with an empty merged message.