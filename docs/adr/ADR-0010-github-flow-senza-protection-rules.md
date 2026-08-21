---
title: "ADR-0010: GitHub Flow obbligatorio senza protection rules"
status: "Accepted"
date: "2026-08-21"
authors: "Alessio Andriulo"
tags: ["github-flow", "ci-cd", "governance"]
supersedes: ""
superseded_by: ""
---

# ADR-0010: GitHub Flow obbligatorio senza protection rules

## Status

**Accepted**

## Context

Il repository `alessioandriuloagic/fabric-agentic` è privato e appartiene a un account GitHub
personale con piano Free. Il piano non consente di applicare branch protection su `main` né
protection rules sugli environment. Il progetto deve comunque mantenere merge umano e tracciabilità
delle modifiche.

## Decision

Ogni modifica deve seguire sempre GitHub Flow:

1. creare un branch dedicato dal branch aggiornato;
2. sviluppare e validare la modifica sul branch;
3. aprire una pull request verso `main`;
4. attendere la review prevista;
5. eseguire il merge solo manualmente da parte dell'owner.

Nessun agente deve modificare direttamente `main` o eseguire merge. La disciplina di processo è il
controllo operativo corrente; protection rules e branch policy saranno abilitate se il repository
passerà a GitHub Pro o a una Organization.

## Consequences

### Positive

- Il flusso resta tracciabile e coerente con GitHub Flow.
- Il merge umano resta una regola chiara e verificabile nella revisione.
- Non si bloccano i lavori in attesa di cambiare piano GitHub.

### Negative

- GitHub non impedisce tecnicamente un push diretto o un merge accidentale.
- La conformità dipende dall'attenzione dell'owner e dai controlli di review.
- Gli environment `test` e `prod` non possono imporre approvazioni automatiche sul piano corrente.

## Implementation Notes

- Il workflow OIDC `dev` è già stato validato con successo.
- I workflow agentici devono restare limitati a `dev` finché non esistono protection rules e
  credenziali/workspace dedicati per `test` e `prod`.
- Ogni PR deve includere evidenza dei test eseguiti e aggiornare la documentazione quando cambia
  il comportamento operativo.
