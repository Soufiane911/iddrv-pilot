-- =============================================================
-- IDDRV — Données de référence (machines + aliases)
-- =============================================================

-- Machines de référence (exemples basés sur les constructeurs majeurs)
INSERT INTO machines (site_id, erp_ref, name, brand, model, max_clamp_force_kn, max_shot_volume_cm3, controller_type)
VALUES
    (1, '1003', '1003 2 NOYAUX',       'arburg',       'Allrounder 370C',   1000.0, 210.0,  'Selogica'),
    (1, '606',  '606 PRESSE TUBES',    'arburg',        'Allrounder 630S',   2000.0, 780.0,  'Gestica'),
    (1, '152',  'PRESSE 152',          'engel',         'victory 280',        2800.0, 450.0,  'CC300'),
    (1, '252',  'PRESSE 252',          'haitian',       'Mars III 2680',      2680.0, 600.0,  'HaitiControl'),
    (1, '254',  'PRESSE 254',          'kraussmaffei',  'CX 160',             1600.0, 310.0,  'MC6')
ON CONFLICT (site_id, erp_ref) DO NOTHING;

-- Aliases (compatible with both pre-011 upgrades and fresh schemas).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='machine_aliases' AND column_name='site_id'
    ) THEN
        INSERT INTO machine_aliases (machine_id, site_id, alias_context, alias_value)
        SELECT id, site_id, 'file', alias_value
        FROM machines
        CROSS JOIN LATERAL (
            VALUES
                ('1003', CASE WHEN erp_ref='1003' THEN '1003' END),
                ('606', CASE WHEN erp_ref='606' THEN '606' END),
                ('152', CASE WHEN erp_ref='152' THEN 'machine_152' END)
        ) AS aliases(ref, alias_value)
        WHERE erp_ref=aliases.ref AND alias_value IS NOT NULL
        ON CONFLICT DO NOTHING;
    ELSE
        INSERT INTO machine_aliases (machine_id, alias_context, alias_value)
        SELECT id, 'file', alias_value
        FROM machines
        CROSS JOIN LATERAL (
            VALUES
                ('1003', CASE WHEN erp_ref='1003' THEN '1003' END),
                ('606', CASE WHEN erp_ref='606' THEN '606' END),
                ('152', CASE WHEN erp_ref='152' THEN 'machine_152' END)
        ) AS aliases(ref, alias_value)
        WHERE erp_ref=aliases.ref AND alias_value IS NOT NULL
        ON CONFLICT DO NOTHING;
    END IF;
END $$;
