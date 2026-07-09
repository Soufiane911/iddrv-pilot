from ingest.reconciler import derive_part_quality


def test_quality_sentinels_are_canonical():
    assert derive_part_quality({"quality_flag": "good"}, False) == ("good", None)
    assert derive_part_quality({"quality_flag": "short_shot"}, True) == ("scrap", "short_shot")
