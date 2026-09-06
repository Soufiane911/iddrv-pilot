from backend.app.order_repository import summarize_order


def test_reopened_order_uses_corrected_good_quantity_once():
    declarations = [{'good_parts': 5600}, {'good_parts': 4000}]
    observations = [
        {'values': {'order_target_quantity': 10000, 'order_status': 'open', 'coverage_complete': True}},
        {'values': {'order_status': 'closed'}},
        {'values': {'order_status': 'reopened', 'order_status_reason': 'defective lot'}},
    ]
    result = summarize_order('000012', declarations, observations)
    assert result['good_parts_net'] == 9600
    assert result['remaining_quantity'] == 400
    assert result['order_status'] == 'reopened'
    assert len(result['status_history']) == 3
    declarations.append({'good_parts': 400})
    result = summarize_order('000012', declarations, observations)
    assert result['remaining_quantity'] == 0
    assert result['order_status'] == 'reopened'


def test_unknown_target_or_incomplete_history_prevents_remaining():
    assert summarize_order('x', [{'good_parts': 4}], [])['remaining_quantity'] is None
    assert summarize_order('x', [{'good_parts': 4}], [{'values': {'order_target_quantity': 10}}])['remaining_quantity'] is None
    result = summarize_order('x', [{'good_parts': None}], [{'values': {'order_target_quantity': 10, 'coverage_complete': True}}])
    assert result['good_parts_net'] is None and result['remaining_quantity'] is None


def test_source_warning_prevents_certified_progress():
    result = summarize_order('x', [{'good_parts': -16, 'warnings': ['good_parts']}], [{'values': {'order_target_quantity': 10, 'coverage_complete': True}}])
    assert result['good_parts_net'] == -16
    assert result['remaining_quantity'] is None
    assert result['coverage']['warnings'] == 1
