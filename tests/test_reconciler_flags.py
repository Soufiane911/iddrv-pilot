from ingest.reconciler import normalize_bool_flag, normalize_good_parts


def test_csv_boolean_flags_are_sql_safe():
    assert normalize_good_parts("True") == 1
    assert normalize_good_parts("False") == 0
    assert normalize_bool_flag("True") is True
    assert normalize_bool_flag("False") is False
    assert normalize_bool_flag("0") is False
    assert normalize_bool_flag("1") is True
