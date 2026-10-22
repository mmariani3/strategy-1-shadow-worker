-- No-scan preservation only. The authenticated host pins the connector project.
-- All rows are hashed in one read-only repeatable-read transaction; no row export.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '2s';
SET LOCAL row_security = off;
SET LOCAL timezone = 'UTC';
SET LOCAL datestyle = 'ISO, YMD';
SET LOCAL intervalstyle = 'postgres';
SET LOCAL extra_float_digits = 3;
SET LOCAL bytea_output = 'hex';
WITH fingerprints AS (
__FINGERPRINT_SELECTS__
), relations AS (
 SELECT c.* FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname IN (__TABLE_NAMES__) AND c.relkind='r'
), catalog AS (
 SELECT c.relname AS name, pg_get_userbyid(c.relowner) AS owner,
 c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls,
 c.relacl::text AS acl,
 (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
   'not_null',a.attnotnull,'default',pg_get_expr(d.adbin,d.adrelid),'acl',a.attacl::text) ORDER BY a.attnum)
   FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
   WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS columns,
 (SELECT coalesce(jsonb_agg(jsonb_build_object('name',conname,'definition',pg_get_constraintdef(oid),
   'validated',convalidated) ORDER BY conname),'[]'::jsonb) FROM pg_constraint WHERE conrelid=c.oid) AS constraints,
 (SELECT coalesce(jsonb_agg(jsonb_build_object('definition',pg_get_indexdef(indexrelid),'valid',indisvalid,
   'ready',indisready) ORDER BY indexrelid::regclass::text),'[]'::jsonb) FROM pg_index WHERE indrelid=c.oid) AS indexes,
 (SELECT coalesce(jsonb_agg(jsonb_build_object('name',tgname,'enabled',tgenabled,
   'definition',pg_get_triggerdef(oid),
   'function_sha256',encode(sha256(convert_to(pg_get_functiondef(tgfoid),'UTF8')),'hex'))
   ORDER BY tgname),'[]'::jsonb) FROM pg_trigger WHERE tgrelid=c.oid AND NOT tgisinternal) AS triggers,
 (SELECT coalesce(jsonb_agg(jsonb_build_object('name',polname,'command',polcmd,'roles',polroles::text,
   'permissive',polpermissive,'using',pg_get_expr(polqual,polrelid),
   'check',pg_get_expr(polwithcheck,polrelid)) ORDER BY polname),'[]'::jsonb)
   FROM pg_policy WHERE polrelid=c.oid) AS policies
 FROM relations c
)
SELECT jsonb_build_object(
 'kind','NO_SCAN_FULL_TABLE_FINGERPRINT_V1','nonce','__NONCE__','run_key','__RUN_KEY__',
 'checked_at',transaction_timestamp(),'finished_at',clock_timestamp(),
 'transaction_read_only',current_setting('transaction_read_only'),
 'transaction_isolation',current_setting('transaction_isolation'),
 'mvcc_snapshot',pg_current_snapshot()::text,'database',current_database(),'role',current_user,
 'complete_visibility',(SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname=current_user),
 'tables',(SELECT jsonb_agg(to_jsonb(f) ORDER BY name) FROM fingerprints f),
 'catalog',(SELECT jsonb_agg(to_jsonb(c) ORDER BY name) FROM catalog c),
 'matching_run_count',(SELECT count(*) FROM public.strategy_discovery_runs WHERE run_key='__RUN_KEY__'),
 'unfinished_run_count',(SELECT count(*) FROM public.strategy_discovery_runs
   WHERE status IS NULL OR status NOT IN ('COMPLETE','PARTIAL','FAILED')),
 'cron_installed',EXISTS(SELECT 1 FROM pg_extension WHERE extname='pg_cron'),
 'other_active_session_ids',(SELECT coalesce(jsonb_agg(pid ORDER BY pid),'[]'::jsonb)
   FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()
     AND (state='active' OR state LIKE 'idle in transaction%'))
) AS evidence;
COMMIT;
