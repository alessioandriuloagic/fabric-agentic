# Un processo attivo non dimostra una delivery riuscita

**Date**: 2026-09-08 | **Context**: Dev Agent issue #182 e demo della catena end-to-end

## What happened
Il dispatcher e il processo Claude risultavano attivi, ma le sessioni terminarono con `no_work` o `HTTP 429` senza branch, PR o evidenza terminale.

## Why it was wrong
La presenza del processo e un exit code positivo non provano che il Dev Agent abbia eseguito il ticket. Il limite esterno di Claude non era verificato prima del dispatch.

## What to do instead
Considerare una delivery riuscita solo con manifest, branch, test, evidenza e PR verificabili. Aggiungere un preflight del runtime e classificare quota, autenticazione, capacity e no-op come stati bloccanti distinti.