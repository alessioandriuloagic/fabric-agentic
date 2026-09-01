# Documentazione tecnica

Descrive **come è costruito** il sistema: componenti, contratti, identità, permessi e struttura
dei repository.

Il "cosa fa e chi decide" vive in `docs/functional/`. Qui non si ripetono le regole funzionali:
si descrive come sono implementate.

## Indice

| Documento | Contenuto |
|---|---|
| [01 — Architettura degli agenti](01-architettura-agenti.md) | Anatomia di Dev Agent e Review Agent, toolbox, asimmetria delle capacità |
| [02 — Dispatcher](02-dispatcher.md) | Polling, trigger, ciclo di vita della sessione, gestione dei token |
| [03 — Rail script](03-rail-script.md) | Contratti degli script deterministici che gli agenti invocano |
| [04 — Identità e permessi](04-identita-e-permessi.md) | Service principal, matrice dei permessi, controlli di piattaforma |
| [05 — Struttura dei repository](05-struttura-repository.md) | Layout del repo soluzione e della knowledge base |
| [06 — Contratto di connettore](06-contratto-connettore.md) | Schema della configurazione metadata-driven e interfaccia dei connettori |
| [07 — Architecture review](07-architecture-review.md) | Validazione del design contro la documentazione ufficiale e rischi architetturali |
| [08 — KPI baseline](08-kpi-baseline.md) | Misure iniziali del dispatcher e metodo di raccolta dei KPI |
| [09 — Framework gate](09-framework-gate.md) | Verifica B3 e decisione necessaria prima del primo onboarding agentico |
| [10 — GitHub issue attachments](10-github-issue-attachments.md) | Ricerca ufficiale su allegati GitHub, installation token e permessi |
| [10 — Retrospettiva S1-04](10-retrospettiva-s1-04.md) | Esito e lezioni della sprint S1-04 |
| [11 — GitHub Copilot runtime](11-github-copilot-runtime.md) | Ricerca sui runtime Copilot utilizzabili dal dispatcher e verdetto per opzione |
| [12 — Console e avvio](12-console-e-avvio.md) | Layout canonico degli agenti, verifica di prontezza e console locale in sola lettura |
| [13 — Issue Agent: guida operativa](13-issue-agent-guida-operativa.md) | Intake GitHub, dispatcher, pacchetto, approvazione e passaggio al Dev Agent |

## Convenzione sulle affermazioni di piattaforma

> Ogni affermazione su capacità, limiti o comportamenti di Microsoft Fabric presente in questi
> documenti deve essere **verificabile sulla documentazione ufficiale**. Dove la verifica non è
> ancora stata fatta, il punto è marcato con **DA VERIFICARE** e collegato a una domanda aperta
> del PRD.
>
> Vale per noi esattamente come per gli agenti: è la stessa regola della checklist di review (E4).

## Documenti correlati

- `../../CONTEXT.md` — convenzioni di naming e principi non negoziabili
- `../functional/` — ciclo di vita, runbook, checklist, escalation
- `../prd/PRD-agentic-cicd-fabric.md` — requisiti e roadmap
