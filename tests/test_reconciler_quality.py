from ingest.reconciler import derive_part_quality


def test_quality_sentinels_are_canonical():
    assert derive_part_quality({"quality_flag": "good"}, False) == ("good", None)
    assert derive_part_quality({"quality_flag": "short_shot"}, True) == ("scrap", "short_shot")


def test_absent_quality_remains_unknown():
    from ingest.reconciler import normalize_good_parts
    assert derive_part_quality({}, None) == (None, None)
    assert derive_part_quality({'quality_flag': 'valid'}, None) == (None, None)
    assert normalize_good_parts(None) is None
    assert normalize_good_parts('') is None
