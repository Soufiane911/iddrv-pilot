-- Operators may enter actual scrap without receiving planning or machine-control rights.
ALTER TABLE user_site_roles DROP CONSTRAINT IF EXISTS user_site_roles_role_check;
ALTER TABLE user_site_roles ADD CONSTRAINT user_site_roles_role_check
    CHECK (role IN ('viewer','operator','analyst','supervisor','admin'));
