-- Allow an explicitly authorised tenant deletion while keeping history
-- immutable for every normal request.
CREATE OR REPLACE FUNCTION reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' AND current_setting('iddrv.allow_tenant_delete', true) = 'on' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'immutable_history';
END $$;
