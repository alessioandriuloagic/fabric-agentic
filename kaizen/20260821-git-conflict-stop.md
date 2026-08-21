# Stop on Git conflicts

**Date**: 2026-08-21 | **Context**: follow-up PR per il rail `branch_out`

## What happened
Un comando concatenato ha proseguito con commit e push dopo che `git stash pop` aveva segnalato conflitti.

## Why it was wrong
I marker di conflitto sono finiti nel commit e il risultato non era revisionabile ne' eseguibile.

## What to do instead
Dopo stash, merge o rebase, fermarsi al primo conflitto e verificarne la risoluzione.
Eseguire commit e push solo dopo `git diff --check` e la suite di test pertinente.