const METRIC_LABELS: Record<string, string> = {
  scrap_rate: 'Taux de rebut',
  early_scrap_rate: 'Taux de rebut en début de période',
  defect_count: 'Nombre de défauts',
  cycle_time_s: 'Temps de cycle',
  dosing_time_s: 'Temps de dosage',
  injection_time_s: 'Temps d’injection',
  cooling_time_s: 'Temps de refroidissement',
  peak_pressure_bar: 'Pression maximale',
  switchover_pressure_bar: 'Pression de commutation',
  clamp_force_kn: 'Force de fermeture',
  cushion_mm: 'Coussin matière',
  barrel_temp_zone1_c: 'Température zone 1',
  barrel_temp_zone2_c: 'Température zone 2',
  barrel_temperature_stability: 'Stabilité des températures',
  mold_temperature_c: 'Température du moule',
  oil_temperature_c: 'Température de l’huile',
  energy_kwh: 'Énergie consommée',
  dimension_deviation_mm: 'Écart dimensionnel',
  measured_weight_g: 'Poids mesuré',
  operator_note: 'Note opérateur',
  maintenance_event: 'Intervention de maintenance',
};

export function metricLabel(value: string): string {
  return METRIC_LABELS[value] ?? value.split('_').join(' ');
}
