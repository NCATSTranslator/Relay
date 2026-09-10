import logging
import os

logger = logging.getLogger(__name__)


def _get_enabled():
    return os.getenv("ARS_RRF_ENABLED", "true").strip().lower() == "true"


def _parse_ranker_weights():
    default_weights = {
        "infores:aragorn": 0.9,
        "infores:arax": 0.1,
    }

    try:
        aragorn_weight = float(
            os.getenv("ARS_RRF_ARAGORN_WEIGHT", default_weights["infores:aragorn"])
        )
        if aragorn_weight < 0 or aragorn_weight > 1:
            raise ValueError("ARAGORN weight must be between 0 and 1")

        return {
            "infores:aragorn": aragorn_weight,
            "infores:arax": round(1.0 - aragorn_weight, 8),
        }
    
    except ValueError as e:
        logger.warning(
            f"Invalid environment variable ARS_RRF_ARAGORN_WEIGHT set; using default weights "
            f"0.9 and 0.1, respectively: {e}"
        )
        return default_weights


def _get_c_value():
    default_c = 40
    rrf_c = str(os.getenv("ARS_RRF_C", default_c))
    try:
        c_value = int(rrf_c)
        if c_value < 0:
            raise ValueError("C must be non-negative")
        
        return c_value
    
    except Exception as e:
        logger.warning(f"Invalid environment variable ARS_RRF_C set; using default {default_c}: {e}")
        return default_c


def get_config():
    return {
        "enabled": _get_enabled(),
        "weights": _parse_ranker_weights(),
        "c_value": _get_c_value()
    }


def configured_source(inforesid, agent_name, weights):
    if inforesid:
        source = str(inforesid).strip().lower()
        if source in weights:
            return source

    if agent_name:
        source = str(agent_name).strip().lower()
        if source in weights:
            return source
        if source.startswith("ara-"):
            source = "infores:" + source[4:]
            if source in weights:
                return source

    return None


def _result_key(result):
    """
    Build a frozenset of bound node IDs for a single input result dict with "node_bindings" key.
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


def _rank_map_from_results(results):
    """
    converts a ranker's ordered result list into a lookup table by building a lookup dict 
    mapping node_binding id frozenset in a result item to its index or ranked position in result list
    Args:
        results (list): a ordered list of ranked results by a ranker

    Returns:
        dict: a lookup dict with node binding id frozenset as keys. Note that if two results 
        produce the same frozenset key, only the first rank is kept. That preserves the best 
        rank from that ranker for duplicate-equivalent answers.
    """
    rank_map = {}
    for index, result in enumerate(results or [], start=1):
        key = _result_key(result)
        if key is not None and key not in rank_map:
            rank_map[key] = index
    return rank_map


def apply_weighted_rrf(data, ranker_results_by_source, weights, c_value):
    """
    Sort data["message"]["results"] in-place with weighted Reciprocal Rank Fusion.
    Args:
        data (_type_): input data["message"]["results"] to be sorted in place
        ranker_results_by_source (_type_): dict of already-ranked result lists from each ranker 
        source "infores:aragorn" and "infores:arax" with the list order reflecting that 
        ranker's ranking order.
        weights (_type_): weights dict controlling each ranker's contribution for two rankers 
        "infores:aragorn" and "infores:arax"
        c_value (_type_): RRF dampening constant. Each matched result gets contribution of weight / (c_value + rank)

    Returns: a summary dict suitable for logging.
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
            rank_map = _rank_map_from_results(source_results)
            if rank_map:
                rank_maps[source_key] = rank_map

    if not rank_maps:
        return {"applied": False, "reason": "missing_ranker_results"}

    scored = []
    matched = 0
    for original_index, result in enumerate(results):
        key = _result_key(result)
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
    for rank, (score, _, result, source_ranks, source_contributions) in enumerate(scored, start=1):
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
