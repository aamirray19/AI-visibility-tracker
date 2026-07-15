-- Remove the legacy IT asset-tracking schema (assets, employees, categories,
-- assignments, roles). BrandSightAI does not use this data model.
drop table if exists public.asset_assignments cascade;
drop table if exists public.assets cascade;
drop table if exists public.employees cascade;
drop table if exists public.asset_categories cascade;
drop table if exists public.user_roles cascade;

drop function if exists public.has_role(uuid, public.app_role) cascade;
drop function if exists public.handle_new_user_role() cascade;

drop type if exists public.asset_condition cascade;
drop type if exists public.app_role cascade;
