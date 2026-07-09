def test_source_value_fallback_contract():
    cycle = {"raw_data": {"barrel_temp_zone2_c": 206.5, "cooling_time_s": 9.4}}
    raw = cycle["raw_data"]
    assert cycle.get("barrel_temp_zone2_c", raw.get("barrel_temp_zone2_c")) == 206.5
    assert (cycle.get("cooling_time_s") if cycle.get("cooling_time_s") is not None else raw.get("cooling_time_s")) == 9.4
    cycle["barrel_temp_zone2_c"] = 211.0
    assert cycle.get("barrel_temp_zone2_c", raw.get("barrel_temp_zone2_c")) == 211.0
