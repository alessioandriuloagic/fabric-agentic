---
title: "ADR-0011: Primo ticket agentico su dati sintetici"
status: "Accepted"
date: "2026-08-21"
authors: "Alessio Andriulo"
tags: ["scope", "mvp", "agentic-workflow"]
supersedes: ""
superseded_by: ""
---

# ADR-0011: Primo ticket agentico su dati sintetici

## Status

**Accepted**

## Context

La roadmap S1 assumeva che il primo ticket agentico dovesse creare `ws_agentic_dev` e
`ws_agentic_prod`. Durante lo Slice 0, `ws_agentic_dev` è stato già predisposto e i rail
`branch_out` e `sync_workspace` sono stati verificati su un feature workspace effimero.

Il workspace `prod` e le sue credenziali dedicate non esistono ancora. Provisionarlo ora
contraddirebbe il perimetro esplicito dell'MVP: nessuna configurazione `test` o `prod` prima di
workspace, identità e controlli dedicati.

## Decision

Il primo ticket agentico reale non crea workspace di ambiente. Usa i rail verificati per creare
il proprio feature workspace e realizza un tracer bullet su dati demo/sintetici: onboarding
dell'entità CRM `account` nel layer Bronze.

Il tracer usa la Fabric Connection `b838644d-afd9-4ec3-973d-e36ed85ad167`
(`CommonDataService`), già disponibile per il CRM demo. La chiave primaria è `accountid`; il
carico è incrementale con watermark `modifiedon`.

Il ticket deve essere preceduto dalla verifica che il framework metadata-driven e il contratto
del connettore siano presenti nel repository della soluzione. Se il framework manca, il Dev Agent
deve escalare B3 anziché implementare un flusso ad hoc.

`ws_agentic_dev` resta un prerequisito già esistente. `test` e `prod` restano non provisionati e
fuori dal perimetro dei rail agentici.

## Consequences

### Positive

- Il primo ciclo dimostra il valore reale dell'agente: branch, feature workspace, configurazione,
  esecuzione, qualità dati, documentazione e PR.
- Non introduce privilegi o ambienti permanenti non ancora governati.
- La baseline manuale e agentica di onboarding diventa misurabile sullo stesso caso.

### Negative

- La creazione automatica degli ambienti non è più il primo caso d'uso agente.
- Il primo ticket dipende dalla disponibilità effettiva del framework metadata-driven nel repo.
- La pubblicazione automatica su DEV e ogni promozione oltre DEV restano lavori successivi.

## Alternatives Considered

### Creare subito `ws_agentic_prod`

**Why rejected**: manca un workspace/credenziale dedicata e la scelta violerebbe il vincolo
esplicito di non configurare ambienti ulteriori prima dei relativi controlli.

### Usare Open-Meteo `daily_weather`

**Why rejected**: il framework candidato non espone un connettore REST/Open-Meteo. Introdurlo
prima del primo ticket richiederebbe una nuova decisione architetturale e ritarderebbe la prova
del ciclo agente su un connettore già disponibile.

### Usare un ticket solo documentale

**Why rejected**: S0-14 ha già validato dispatcher, sessione e tracker; non dimostrerebbe i rail
e il ciclo dati che costituiscono l'obiettivo dell'MVP.

## References

- ADR-0007 - Pipeline CI/CD come rail
- ADR-0008 - Permessi Fabric del Dev Agent
- ADR-0010 - GitHub Flow senza protection rules
- `docs/technical/09-framework-gate.md`