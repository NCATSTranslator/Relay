import json
import logging
import os
import re

logger = logging.getLogger(__name__)

DEFAULT_RRF_C = 60
DEFAULT_RRF_WEIGHTS = {
    "infores:aragorn": 0.5,
    "infores:arax": 0.5,
}


def is_enabled():
    raw = os.getenv("ARS_RRF_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def parse_ranker_weights(raw=None):
    """
    Parse ARS_RRF_RANKER_WEIGHTS.

    Supported forms:
      - infores:aragorn=0.8,infores:arax=0.2
      - {"infores:aragorn": 0.8, "infores:arax": 0.2}
    """
    if raw is None or not raw.strip():
        return dict(DEFAULT_RRF_WEIGHTS)

    raw = raw.strip()
    parsed = {}
    try:
        if raw.startswith("{"):
            loaded = json.loads(raw)
            items = loaded.items()
        else:
            parts = [part.strip() for part in re.split(r"[;,]", raw) if part.strip()]
            items = []
            for part in parts:
                if "=" not in part:
                    raise ValueError("weight entries must use key=value")
                key, value = part.split("=", 1)
                items.append((key, value))

        for key, value in items:
            normalized_key = str(key).strip().lower()
            weight = float(value)
            if not normalized_key:
                raise ValueError("ranker source cannot be empty")
            if weight < 0:
                raise ValueError("ranker weights must be non-negative")
            parsed[normalized_key] = weight
    except Exception as e:
        logger.warning(
            "Invalid ARS_RRF_RANKER_WEIGHTS=%r; using defaults: %s", raw, e
        )
        return dict(DEFAULT_RRF_WEIGHTS)

    if not parsed or sum(parsed.values()) <= 0:
        logger.warning(
            "ARS_RRF_RANKER_WEIGHTS must contain at least one positive weight; "
            "using defaults."
        )
        return dict(DEFAULT_RRF_WEIGHTS)
    return parsed


def get_c_value(raw=None):
    if raw is None:
        raw = os.getenv("ARS_RRF_C", str(DEFAULT_RRF_C))
    try:
        c_value = int(raw)
        if c_value < 0:
            raise ValueError("C must be non-negative")
        return c_value
    except Exception as e:
        logger.warning("Invalid ARS_RRF_C=%r; using %s: %s", raw, DEFAULT_RRF_C, e)
        return DEFAULT_RRF_C


def get_config():
    return {
        "enabled": is_enabled(),
        "weights": parse_ranker_weights(os.getenv("ARS_RRF_RANKER_WEIGHTS")),
        "c_value": get_c_value(),
    }


def source_candidates(inforesid=None, agent_name=None):
    candidates = []
    for value in (inforesid, agent_name):
        if value:
            source = str(value).strip().lower()
            candidates.append(source)
            if source.startswith("infores:"):
                candidates.append(source.split(":", 1)[1])
            if source.startswith("ara-"):
                short_name = source[4:]
                candidates.append(short_name)
                candidates.append("infores:" + short_name)
    return candidates


def configured_source(inforesid, agent_name, weights):
    for candidate in source_candidates(inforesid, agent_name):
        if candidate in weights:
            return candidate
    return None


def result_key(result):
    """
    Build the same practical answer identity ARS uses for result merging:
    a frozenset of bound node IDs.
    """
    node_bindings = result.get("node_bindings") or {}
    ids = set()
    for bindings in node_bindings.values():
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            if isinstance(binding, dict) and binding.get("id") is not None:
                ids.add(binding["id"])
    if not ids:
        return None
    return frozenset(ids)


def rank_map_from_results(results):
    rank_map = {}
    for index, result in enumerate(results or [], start=1):
        key = result_key(result)
        if key is not None and key not in rank_map:
            rank_map[key] = index
    return rank_map


def apply_weighted_rrf(data, ranker_results_by_source, weights, c_value):
    """
    Sort data["message"]["results"] in-place with weighted Reciprocal Rank Fusion.

    Returns a summary dict suitable for logging. The function is intentionally
    pure with respect to external services; callers provide ranker result lists.
    """
    message = data.get("message") if isinstance(data, dict) else None
    if not isinstance(message, dict):
        return {"applied": False, "reason": "missing_message"}

    results = message.get("results")
    if not results:
        return {"applied": False, "reason": "missing_results"}

    rank_maps = {}
    for source, source_results in ranker_results_by_source.items():
        source_key = str(source).strip().lower()
        if source_key in weights:
            rank_map = rank_map_from_results(source_results)
            if rank_map:
                rank_maps[source_key] = rank_map

    if not rank_maps:
        return {"applied": False, "reason": "missing_ranker_results"}

    scored = []
    matched = 0
    for original_index, result in enumerate(results):
        key = result_key(result)
        score = 0.0
        source_ranks = {}
        source_contributions = {}
        if key is not None:
            for source, rank_map in rank_maps.items():
                rank = rank_map.get(key)
                if rank is None:
                    continue
                contribution = weights[source] / (c_value + rank)
                score += contribution
                source_ranks[source] = rank
                source_contributions[source] = contribution

        if source_ranks:
            matched += 1
        scored.append((score, original_index, result, source_ranks, source_contributions))

    if matched == 0:
        return {"applied": False, "reason": "no_matching_results"}

    scored.sort(key=lambda item: (-item[0], item[1]))
    for rank, (score, _, result, source_ranks, source_contributions) in enumerate(
        scored, start=1
    ):
        result["rrf_score"] = score
        result["rrf_ranker_ranks"] = source_ranks
        result["rrf_ranker_contributions"] = source_contributions
        result["rrf_rank"] = rank

    message["results"] = [result for _, _, result, _, _ in scored]
    return {
        "applied": True,
        "ranker_sources": sorted(rank_maps.keys()),
        "matched_results": matched,
        "result_count": len(results),
        "c_value": c_value,
        "weights": {source: weights[source] for source in sorted(rank_maps.keys())},
    }
