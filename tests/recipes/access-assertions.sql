INSERT INTO public.notes VALUES
 ('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000011','first owner'),
 ('00000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000022','second owner');
GRANT SELECT ON public.notes TO service_role;
SET ROLE anon;
DO $$ BEGIN
  BEGIN
    PERFORM * FROM public.notes;
    RAISE EXCEPTION 'anon unexpectedly read private notes';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
END $$;
RESET ROLE;
SET ROLE authenticated;
SET request.jwt.claim.sub = '00000000-0000-0000-0000-000000000011';
DO $$ BEGIN
  IF (SELECT count(*) FROM public.notes) <> 1 THEN RAISE EXCEPTION 'owner read failed'; END IF;
  IF (SELECT body FROM public.notes) <> 'first owner' THEN RAISE EXCEPTION 'wrong owner row'; END IF;
  BEGIN
    UPDATE public.notes SET body = 'unauthorized';
    RAISE EXCEPTION 'write unexpectedly allowed';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
END $$;
SET request.jwt.claim.sub = '00000000-0000-0000-0000-000000000033';
DO $$ BEGIN
  IF (SELECT count(*) FROM public.notes) <> 0 THEN RAISE EXCEPTION 'nonowner read allowed'; END IF;
END $$;
RESET ROLE;
SET ROLE service_role;
DO $$ BEGIN
  IF (SELECT count(*) FROM public.notes) <> 2 THEN RAISE EXCEPTION 'service role read failed'; END IF;
END $$;
RESET ROLE;
CREATE TABLE public.future_private (id int);
DO $$ BEGIN
  IF has_table_privilege('anon', 'public.future_private', 'SELECT') OR
     has_table_privilege('authenticated', 'public.future_private', 'SELECT') THEN
    RAISE EXCEPTION 'future private table exposed';
  END IF;
END $$;
SET ROLE anon;
DO $$ BEGIN
  BEGIN
    PERFORM * FROM public.future_private;
    RAISE EXCEPTION 'anon unexpectedly read future table';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
END $$;
RESET ROLE;
SELECT 'PASS: anon deny, owner allow, nonowner deny, service allow, writes deny, future-table deny';
