# IDDRV — Contrat API v1 pour l'investigation

Ce contrat est la source partagée de G2. Les agents backend et frontend ne doivent pas inventer de champs hors de ce document.

## Conventions

- Préfixe : `/api/v1`.
- Dates : ISO-8601 avec fuseau.
- Les périodes historiques utilisent toujours `from`, `to` ou `as_of`.
- Les réponses d'erreur utilisent `{ "error": { "code": "...", "message": "...", "details": {} } }`.
- Les identifiants sont opaques pour le frontend.

## Incident

```json
{
  "id": "uuid",
  "site_id": 1,
  "machine_id": 3,
  "machine_erp_ref": "152",
  "production_order_id": "OF-2025-0012",
  "status": "open|reviewed|closed",
  "severity": "low|medium|high|critical",
  "symptom": "short_shot_increase",
  "defect_type": "short_shot",
  "started_at": "2025-02-12T00:21:43Z",
  "ended_at": "2025-02-12T01:52:40Z",
  "created_at": "2025-02-12T02:00:00Z",
  "data_cutoff": "2025-02-12T02:00:00Z",
  "confidence": "low|medium|high"
}
```

## Preuve

```json
{
  "id": "uuid",
  "source_kind": "cycle_aggregate|quality_check|maintenance_event|operator_note|production_order",
  "source_ref": "stable-reference",
  "metric": "barrel_temp_zone2_c",
  "window": { "start": "ISO-8601", "end": "ISO-8601" },
  "observation": { "stat": "median", "value": 194.9, "unit": "C", "n": 217 },
  "baseline": { "value": 210.1, "unit": "C", "n": 216 },
  "delta": -15.2,
  "supports": true,
  "excerpt": null
}
```

## Hypothèse

```json
{
  "cause_code": "low_barrel_temperature_zone_2",
  "label": "Température zone 2 trop basse",
  "confidence": 0.87,
  "supporting_evidence_ids": ["uuid"],
  "contradicting_evidence_ids": [],
  "missing_data": [],
  "next_check": "inspect_barrel_zone_2_heating"
}
```

## Endpoints G2

```text
GET  /api/v1/incidents?site_id=&from=&to=&status=
GET  /api/v1/incidents/{incident_id}
GET  /api/v1/incidents/{incident_id}/evidence
POST /api/v1/incidents/{incident_id}/investigations
POST /api/v1/incidents/{incident_id}/feedback
```

`POST investigations` utilise le moteur déterministe local pendant la phase sans quota. Il ne fait aucun appel OpenAI.

## Critères S001

Pour `OF-2025-0012` / machine `152`, l'investigation doit retourner une hypothèse compatible avec une baisse de température zone 2 et fournir des preuves recalculées depuis PostgreSQL : hausse de rebut, température avant/pendant, défauts qualité et note opérateur associée.
