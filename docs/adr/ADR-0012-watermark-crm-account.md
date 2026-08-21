---
title: "ADR-0012: Watermark inclusivo per CRM account"
status: "Accepted"
date: "2026-08-21"
authors: "Alessio Andriulo"
tags: ["data", "watermark", "crm", "idempotency"]
supersedes: ""
superseded_by: ""
---

# ADR-0012: Watermark inclusivo per CRM account

## Status

**Accepted**

## Context

Il tracer CRM `accounts` usa `modifiedon` come watermark. Più record possono condividere lo
stesso timestamp; un filtro strettamente maggiore può quindi perdere record arrivati sul confine
del watermark. Il runtime sorgente usa delta token e un writer append-only, mentre Agentic deve
produrre una Bronze idempotente, audit riconciliabile e stato recuperabile dopo un fallimento.

## Decision

L'estrazione incrementale usa `modifiedon >= ultimo_watermark_confermato`, con timestamp UTC.
I record sono fusi in Bronze su `accountid`. Il nuovo watermark è il massimo `modifiedon`
osservato nel batch e viene salvato **solo dopo** il merge Bronze e la riga audit riusciti.

Un fallimento in staging, PK check, merge Bronze o audit lascia invariato il watermark confermato.
Il run successivo riestrae il confine, che il merge idempotente assorbe senza duplicare record.

## Consequences

### Positive

- Nessuna perdita di record con lo stesso `modifiedon` del confine precedente.
- Rerun sicuro dopo errori parziali o interruzioni.
- Audit e watermark rappresentano solo uno stato Bronze effettivamente committato.

### Negative

- Ogni run riestrae almeno i record del timestamp di confine.
- Il merge per `accountid` è obbligatorio; un writer append-only violerebbe la decisione.
- Il watermark richiede timestamp timezone-aware e normalizzati in UTC.

## Alternatives Considered

### Filtro strettamente maggiore

**Why rejected**: può omettere record con lo stesso timestamp del watermark precedente.

### Aggiornare il watermark dopo l'estrazione

**Why rejected**: un errore successivo nel merge o nell'audit farebbe perdere record non ancora
presenti in Bronze.

### Append Bronze senza merge

**Why rejected**: trasforma la riestrazione inclusiva in duplicati e invalida il controllo PK.

## References

- ADR-0006 - Contratto di connettore
- ADR-0009 - Provenienza dei pattern
- ADR-0011 - Primo ticket agentico CRM