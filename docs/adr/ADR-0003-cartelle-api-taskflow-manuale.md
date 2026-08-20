# ADR-0003 — Cartelle del workspace via API, task flow come passo manuale

| Campo | Valore |
|---|---|
| Stato | **Proposto** — chiude Q-9 e A-5, richiede decisione prima dello Slice 1 |
| Data | 2026-08-20 |
| Autore | Ralph (Fabric Solution Architect) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §6 |
| Decisori | Owner · @reza |

---

## Contesto

`CONTEXT.md` §3.3 impone una struttura a sei cartelle in ogni workspace e §3.4 un **task flow**
che rappresenta il flusso end-to-end. RF-19 («nessun item alla radice») e RF-20 (task flow) ne
discendono. Q-9 chiedeva se entrambi siano creabili e mantenibili via API o CLI, e da quella
risposta dipende se siano criteri **bloccanti** in code review.

Il ticket S1-04 del backlog conteneva un criterio di accettazione condizionale — «il task flow
è presente *se S1-01 lo ha dichiarato automatizzabile*» — che un agente non interattivo non può
risolvere: non può chiedere, e il protocollo di escalation gli imporrebbe di fermarsi. La domanda
andava chiusa **prima** di scrivere il ticket, non durante. Il backlog è stato corretto: il task
flow è ora un passo manuale esplicito, non un criterio condizionale.

Fatti verificati su documentazione ufficiale Microsoft (2026-08-20):

**Cartelle — automatizzabili**
- Esiste `POST /v1/workspaces/{workspaceId}/folders`, che **supporta service principal e managed
  identity** e richiede ruolo contributor o superiore.
- L'API è in **Preview** («not recommended for production use»).
- Annidamento massimo 10 livelli; errore `TooManyFolders` oltre un massimo non documentato
  numericamente.
- Vincoli sul nome: vietati i caratteri `~"#.&*:<>?/{|}`; `Full and Incremental Load` è valido,
  `Full & Incremental Load` **non lo sarebbe**.
- **Alcuni item non possono essere creati dentro una cartella**: Dataflow Gen2, streaming semantic
  model, streaming dataflow. Gli item creati dalla home o dal Create hub nascono alla radice.
- **Le cartelle vuote non vengono copiate in Git**, e le cartelle vuote in Git sono cancellate
  automaticamente.
- Due pagine ufficiali sono **in contraddizione** sul supporto Git alle cartelle: assumiamo valida
  quella più recente (*Git integration process*, che documenta il mirroring) e la verifichiamo
  praticamente in S1-01.

**Task flow — non automatizzabile**
- La documentazione descrive il task flow **esclusivamente** come funzionalità di interfaccia:
  canvas, pannello laterale, assegnazione item.
- L'unica forma di riuso documentata è **esportazione/importazione di un file `.json` tramite
  finestra di dialogo del browser**.
- Non risulta alcuna API REST Fabric per i task flow nella reference consultata. È **assenza di
  evidenza**, non prova di impossibilità.

## Decisione

**1. Le cartelle sono create dal rail *Branch out* tramite Folders API**, in ogni workspace,
feature workspace compresi. Non ci si affida al sync da Git, che non trasporta cartelle vuote.

**2. RF-19 resta un criterio bloccante di review**, con un'**eccezione documentata**: gli item che
la piattaforma non consente di creare dentro una cartella (Dataflow Gen2, streaming semantic
model, streaming dataflow) possono risiedere alla radice. La voce A2 della checklist va
riformulata di conseguenza, altrimenti produrrà un rilievo insanabile alla prima Dataflow Gen2.

**3. RF-20 è declassato da *Should* a passo manuale documentato nel runbook, non bloccante in
review.**

**4. Il task flow si applica soltanto ai workspace di lungo periodo** (`dev`, `test`, `prod`) e
**mai** ai feature workspace effimeri.

**5. Il task flow canonico è versionato** come `fabric/task-flow/agentic.json`, esportato una volta
dall'interfaccia. L'importazione manuale diventa una procedura di trenta secondi anziché una
ricostruzione a memoria.

**6. Il criterio condizionale del ticket S1-04 viene rimosso** e sostituito da un criterio secco:
le cartelle devono esistere, il task flow non è oggetto del ticket.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Rimuovere il task flow dalle convenzioni** | Ha valore reale: rende leggibile la soluzione a chi non la conosce, ed è un elemento efficace in demo. Il fatto che non sia automatizzabile non lo rende inutile |
| **Rendere RF-20 bloccante comunque, con esecuzione manuale prima della PR** | Renderebbe manuale un passo del ciclo agentico, violando il principio del documento `01-ciclo-di-vita-ticket.md` §1 secondo cui ogni intervento umano tecnico è un difetto del sistema. Meglio dichiararlo fuori dal ciclo che dentro e disatteso |
| **Attendere che Microsoft rilasci un'API per i task flow** | Bloccherebbe lo Slice 1 su una data non nota. La decisione è comunque reversibile: se l'API arriva, RF-20 può tornare bloccante |
| **Creare le cartelle solo nei workspace di lungo periodo** | Il feature workspace deve essere una replica fedele di quello di destinazione, altrimenti la verifica di RF-19 nel feature workspace non prova nulla su dev |

## Conseguenze

**Positive**
- Q-9 e A-5 sono chiuse con evidenza documentale; il ticket S1-04 diventa scrivibile.
- Il rail acquisisce un passo esplicito e verificabile invece di una dipendenza implicita dal sync Git.
- RF-19 resta bloccante — cioè conserva valore — perché ha un'eccezione onesta anziché un buco.

**Negative**
- Dipendenza da un'**API in Preview**: va censita come rischio noto e ricontrollata periodicamente.
- Il task flow resta disallineabile dalla realtà del workspace, perché nessun controllo automatico
  lo verifica. È il prezzo consapevole di non renderlo bloccante.
- Un umano deve importare il task flow ogni volta che si istanzia un nuovo progetto o cliente
  (RF-84): va inserito nella checklist di `06-onboarding-nuovo-cliente.md`.

**Da fare**
- Aggiornare `CONTEXT.md` §3.4 (task flow: manuale, solo ambienti di lungo periodo).
- Aggiornare `03-rail-script.md` (*Branch out*: passo di creazione cartelle; rimuovere il "DA VERIFICARE").
- Aggiornare `04-checklist-review.md` voce A2 con l'eccezione.
- Aggiornare il PRD: RF-19 con eccezione, RF-20 non bloccante, Q-9 e A-5 chiuse.
- Riscrivere il criterio di accettazione di S1-04.
