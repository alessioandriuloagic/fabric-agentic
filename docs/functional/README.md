# Documentazione funzionale

Questa cartella descrive **come funziona il sistema dal punto di vista di chi lo usa e di chi
lo governa**: chi fa cosa, in quale ordine, con quali regole e con quali punti di controllo umani.

Non contiene dettagli implementativi: quelli vivono in `docs/technical/`.

## Indice

| Documento | A cosa serve | Lettore principale |
|---|---|---|
| [01 — Ciclo di vita del ticket](01-ciclo-di-vita-ticket.md) | Il flusso end-to-end da ticket a merge, stati e responsabilità | Tutti |
| [02 — Come scrivere un ticket](02-come-scrivere-un-ticket.md) | Il contratto minimo perché un agente possa lavorare | Owner umano |
| [03 — Runbook: onboarding di una sorgente](03-runbook-onboarding-sorgente.md) | La procedura che il Dev Agent segue per aggiungere un dataset | Dev Agent, owner |
| [04 — Checklist di review](04-checklist-review.md) | I criteri chiusi con cui il Review Agent giudica una PR | Review Agent, owner |
| [05 — Protocollo di escalation](05-protocollo-escalation.md) | Cosa fanno gli agenti quando sono bloccati o in disaccordo | Tutti |
| [06 — Onboarding di un nuovo cliente](06-onboarding-nuovo-cliente.md) | Come si istanzia la piattaforma su un nuovo progetto | Owner, prevendita |

## Documenti correlati

- `../../CONTEXT.md` — glossario, convenzioni di naming, principi non negoziabili
- `../prd/PRD-agentic-cicd-fabric.md` — requisiti e roadmap
- `../adr/` — decisioni architetturali
