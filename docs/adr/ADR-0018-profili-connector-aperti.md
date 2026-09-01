# ADR-0018 — Profili connector aperti, adapter registrati

| Campo | Valore |
|---|---|
| Stato | Accettata |
| Data | 2026-09-01 |
| Contesto | Correzione successiva a #129; supera in parte ADR-0016 |

## Contesto

I primi tracer hanno implementato due adapter, Dataverse e file. Il profilo e la UI hanno usato il
registry di questi adapter come allowlist, impedendo di descrivere Business Central, CRM diversi,
database SQL, Oracle, PostgreSQL, SharePoint e tecnologie future finché non esisteva già codice di
estrazione. Questo confondeva due stati diversi: una sorgente nota al progetto e una sorgente già
eseguibile dal core.

## Decisione

1. `source.connector` è un identificatore aperto in formato slug. Il catalogo mostrato dalla UI è
   solo un insieme di suggerimenti e non limita i valori ammessi.
2. Il registry contiene gli **adapter eseguibili**. Per questi, capacità e campi di connessione
   derivano dal codice e non sono ridefinibili dal profilo.
3. Un connector senza adapter deve dichiarare nel profilo `supports_incremental` e
   `supports_source_count`. La validazione può così controllare dataset e watermark offline.
4. Dichiarare una tecnologia non rende disponibile l'esecuzione: `plan_request` continua a fallire
   esplicitamente finché non viene registrato un adapter con planner.

## Alternative scartate

| Alternativa | Motivo del rifiuto |
|---|---|
| Registrare subito adapter fittizi per ogni tecnologia | Dichiarerebbe supporto operativo inesistente e sposterebbe il fallimento a runtime |
| Mantenere l'allowlist e aggiungere voci a richiesta | Ogni nuovo cliente richiederebbe una modifica al core solo per descrivere la propria sorgente |
| Accettare connector aperti senza capacità | La validazione non potrebbe stabilire se incremental e conteggio sono coerenti |

## Conseguenze

- Profili e UI sono aperti a tecnologie future senza modifiche Python.
- La differenza tra “descrivibile” ed “eseguibile” è visibile nel piano renderizzato.
- Un profilo custom richiede due booleani in più; dichiarazioni errate restano responsabilità di chi
  configura l'istanza finché un adapter non rende le capacità autorevoli.
- Implementare un nuovo adapter resta un intervento di codice, test e documentazione.