from tr_ars import ranker_fusion


def make_result(*ids):
    return {
        "node_bindings": {
            "n%s" % index: [{"id": node_id}]
            for index, node_id in enumerate(ids)
        },
        "analyses": [{"score": 0.1}],
    }


def test_parse_ranker_weights_csv():
    weights = ranker_fusion.parse_ranker_weights(
        "infores:aragorn=0.8,infores:arax=0.2"
    )

    assert weights == {
        "infores:aragorn": 0.8,
        "infores:arax": 0.2,
    }


def test_parse_ranker_weights_json():
    weights = ranker_fusion.parse_ranker_weights(
        '{"infores:aragorn": 0.75, "infores:arax": 0.25}'
    )

    assert weights == {
        "infores:aragorn": 0.75,
        "infores:arax": 0.25,
    }


def test_configured_source_accepts_ara_agent_alias():
    source = ranker_fusion.configured_source(
        None,
        "ara-aragorn",
        {"infores:aragorn": 0.8},
    )

    assert source == "infores:aragorn"


def test_configured_source_accepts_short_name_alias():
    source = ranker_fusion.configured_source(
        "infores:arax",
        "ara-arax",
        {"arax": 0.2},
    )

    assert source == "arax"


def test_weighted_rrf_sorts_results_and_adds_metadata():
    result_a = make_result("CHEBI:1", "MONDO:1")
    result_b = make_result("CHEBI:2", "MONDO:1")
    result_c = make_result("CHEBI:3", "MONDO:1")
    data = {"message": {"results": [result_a, result_b, result_c]}}

    summary = ranker_fusion.apply_weighted_rrf(
        data,
        {
            "infores:aragorn": [result_a, result_b],
            "infores:arax": [result_b, result_c],
        },
        {"infores:aragorn": 0.5, "infores:arax": 0.5},
        60,
    )

    assert summary["applied"] is True
    assert [r["node_bindings"]["n0"][0]["id"] for r in data["message"]["results"]] == [
        "CHEBI:2",
        "CHEBI:1",
        "CHEBI:3",
    ]
    assert data["message"]["results"][0]["rrf_rank"] == 1
    assert data["message"]["results"][0]["rrf_ranker_ranks"] == {
        "infores:aragorn": 2,
        "infores:arax": 1,
    }
    assert data["message"]["results"][0]["rrf_score"] > data["message"]["results"][1]["rrf_score"]


def test_weighted_rrf_keeps_unmatched_results_at_end_stably():
    result_a = make_result("CHEBI:1")
    result_b = make_result("CHEBI:2")
    result_c = make_result("CHEBI:3")
    data = {"message": {"results": [result_c, result_b, result_a]}}

    summary = ranker_fusion.apply_weighted_rrf(
        data,
        {"infores:aragorn": [result_a]},
        {"infores:aragorn": 1.0},
        60,
    )

    assert summary["applied"] is True
    assert [r["node_bindings"]["n0"][0]["id"] for r in data["message"]["results"]] == [
        "CHEBI:1",
        "CHEBI:3",
        "CHEBI:2",
    ]
    assert data["message"]["results"][1]["rrf_score"] == 0.0
    assert data["message"]["results"][2]["rrf_score"] == 0.0


def test_weighted_rrf_noops_without_matching_ranker_results():
    result_a = make_result("CHEBI:1")
    data = {"message": {"results": [result_a]}}

    summary = ranker_fusion.apply_weighted_rrf(
        data,
        {"infores:other": [result_a]},
        {"infores:aragorn": 1.0},
        60,
    )

    assert summary == {"applied": False, "reason": "missing_ranker_results"}
    assert data["message"]["results"] == [result_a]


def test_weighted_rrf_noops_without_matching_answers():
    result_a = make_result("CHEBI:1")
    result_b = make_result("CHEBI:2")
    data = {"message": {"results": [result_a]}}

    summary = ranker_fusion.apply_weighted_rrf(
        data,
        {"infores:aragorn": [result_b]},
        {"infores:aragorn": 1.0},
        60,
    )

    assert summary == {"applied": False, "reason": "no_matching_results"}
    assert data["message"]["results"] == [result_a]
    assert "rrf_score" not in result_a
