# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Rail `sync_workspace` (S1-03): workflow GitHub Actions DEV-only, ancorato a `main`, che
  sincronizza il feature workspace deterministico soltanto per modifiche remote e pubblica un
  artefatto `rail-result.json` v1.2. Conflitti e divergenze locali falliscono esplicitamente
  senza sovrascrittura.
- Primo rail reale `branch_out`: workflow GitHub Actions ancorato a `main`, limitato
  all'environment `dev`, con creazione/riuso deterministico di branch e feature workspace,
  assegnazione owner, capacity, connessione Git, cartelle e artefatto `rail-result.json`; usa
  un'identita' OIDC di deploy distinta dal Dev Agent.
- Creato nel tenant Agic Dev il service principal `fabric-agentic-deploy`, senza secret, e
  configurate nell'environment GitHub `dev` le variabili non sensibili del rail per identità,
  capacity, owner e repository. Restano da aggiungere la federated credential, i permessi
  Fabric minimi e l'identificativo della Configured Connection Git.
- Documentata la Configured Connection GitHub: custodisce in Fabric un fine-grained PAT limitato
  al repository, con `Metadata: Read` e `Contents: Read and write`; il PAT non entra in GitHub
  variables, repository, workflow o log.
- Configurata la Configured Connection Fabric `GitHubRepo` per il repository e registrato il suo
  identificativo nell'environment GitHub `dev`. Ricreato `ws_agentic_dev` sulla capacity
  `fabricalessiodev`; i workflow OIDC ora usano il nuovo ID del workspace.
- Contratto `rail-result` v1.1 specializzato per `branch_out`, con stato strutturato di branch,
  workspace, connessione Git e sincronizzazione; consente `workspace_id: null` nei fallimenti
  precedenti alla creazione e identifica in modo sicuro lo step fallito. Aggiunti test locali e
  validazione CI del runner.
- Corretto `branch_out` per le risposte Fabric con connessione Git priva di
  `gitProviderDetails`: il workspace viene collegato anziché terminare con eccezione. Anche gli
  errori imprevisti ora pubblicano un `rail-result.json` con failure stage `unknown`.
- Corretto il rerun di `branch_out` dopo una creazione workspace interrotta: se il feature
  workspace esiste senza capacity, il rail assegna quella configurata; una capacity esistente
  diversa resta un fallimento tecnico esplicito.
- Aggiunto al risultato `branch_out` il `failure_code` sanitizzato per classificare rifiuti API
  senza pubblicare messaggi: consente di distinguere permessi insufficienti da errori di input.
- Corretto il payload Git Connect del rail per GitHub: usa ora `ownerName`,
  `gitProviderType: GitHub` e una directory root relativa, invece dei campi Azure DevOps e del
  path assoluto rifiutati dall'API Fabric.
- Documentata la condivisione necessaria della Configured Connection GitHub: il deploy SP deve
  avere ruolo `User` su `GitHubRepo`; il controllo ha rilevato che la connection era assegnata
  al solo owner umano.
- Primo smoke test reale del rail `branch_out` completato con successo (run `32487821272`): il
  work item `6` ha prodotto un feature workspace con capacity, Git e sincronizzazione verificati.
- Corretto il requisito per `assignToCapacity` dopo il confronto con il progetto IP: il deploy SP
  usa Azure RBAC `Contributor` sulla capacity e la membership del proprio Object ID in
  `properties.administration.members`; il secondo requisito era assente su `fabricalessiodev`.
- Scelta l'associazione dell'organizzazione Azure DevOps al tenant Agic Dev prima di aggiungere
  i service principal agentici a Boards; evita identità duplicate o configurazioni multi-tenant.
- Provisionate nel tenant Agic Dev le identità `fabric-agentic-dev-agent` e
  `fabric-agentic-review-agent`, senza secret o privilegi Fabric. Tenant, sottoscrizione,
  capacity e app ID non sensibili sono registrati in `CONTEXT.md` e nel runbook di onboarding.
- Primo controllo GitHub Actions: valida a ogni pull request e push su `main` lo schema
  `schemas/rail-result-v1.0.json`, contratto versionato fra workflow CI/CD e Dev Agent.
- Configurato il progetto Azure Boards `fabric-agentic` come tracker e verificato il ciclo
  *To Do* → *Doing* → *Done* sul work item `#19`. Il blocco agentico è standardizzato come tag
  `waiting-input`; la creazione dei tag attende il permesso Azure DevOps `Create tag`.
- Ricreato il progetto Azure Boards nella nuova organizzazione `AlessioAndriuloDev` e migrate le
  work item operative: #1 (S0-03), #2 (S0-04), #3 (S0-05), #4 (S0-N5), #5 (S0-N2), preservando
  stati e tag. La precedente organizzazione `alessioandriulo` resta solo come archivio storico.
- Aggiunti all'organizzazione `AlessioAndriuloDev` i service principal Dev Agent (`Basic`) e Review
  Agent (`Stakeholder`); la work item #3 e' stata chiusa. Il provisioning Azure DevOps risulta
  `pending` e sara' verificato prima dell'uso operativo.
- Creato `ws_agentic_dev`, assegnato il Dev Agent come `Contributor` senza permessi sulla capacity
  e aggiunto il workflow manuale `test-azure-oidc-dev.yml` per verificare login OIDC e lettura dei
  metadati del workspace.
- Test OIDC completato con successo su `main` (run `32468016615`): login federato e lettura dei
  metadati di `ws_agentic_dev` verificati senza ruoli sulla subscription o sulla capacity.
- Creati gli environment GitHub `test` e `prod`. Le protection rules e la branch protection di
  `main` restano bloccate dal piano GitHub Free sul repository privato personale; nessuna variabile
  OIDC è stata aggiunta agli ambienti senza workspace e credenziale dedicate.
- Accettata ADR-0010: GitHub Flow obbligatorio senza protection rules; ogni modifica usa branch
  dedicato e PR verso `main`, con merge umano, mentre gli enforcement tecnici restano rinviati.
- GitHub Actions scelto come motore CI/CD per il repository GitHub `alessioandriuloagic/fabric-agentic`.
- Dev Agent formalizzato come data engineer Fabric end-to-end: sviluppa gli item in Git e li
  valida nel feature workspace; dopo merge umano una pipeline CI/CD ancorata a `main` pubblica
  automaticamente su DEV. Coperti data pipeline, notebook, SJD, Dataflow, lakehouse/warehouse,
  Mirroring supportato e lane Power BI.
- Assistente quotidiano per la qualità dati: introdotti il rail `diagnose_data`, la
  `ExecutionCredential` pluggabile per cliente e i requisiti RF-26/RF-27/RF-37/RF-38. Le pipeline
  analizzano sorgente, Bronze e Silver; il modello riceve solo evidenze aggregate o mascherate.
- Allineamento post-review architetturale: RF-75..RF-79 nel PRD, backlog S0 consolidato con
  S0-N1..N4 e verifica pratica a nove controlli, schema `rail-result.json` allineato ai nomi
  `technical_failure` e `quality_failure`, struttura repository estesa con pipeline, schema e
  provenienza dei pattern copiati.
- Spike documentale `fabric-cicd`: `fabric-cicd==1.3.0` supporta `SemanticModel` TMDL e `Report`
  PBIR; S1-01 valida ora il deploy reale e i binding `byPath`/`byConnection`. PBIP non è un tipo
  deployabile autonomo.
- Addendum §13 alla review architetturale (`docs/technical/07-architecture-review.md`
  v1.1): recepisce l'asset di deploy Fabric preesistente
  `IP.dai_fabric_environments`, ispezionato direttamente, e risponde alla domanda
  se il Dev Agent debba avere permessi diretti su Microsoft Fabric. Introduce il
  rilievo bloccante **RB-4** (escalation di privilegio tramite la definizione YAML
  di una pipeline privilegiata), declassa **RB-1**, risolve **RB-3**, aggiorna
  Q-5/Q-7/Q-9 e porta la verifica pratica di S0-06 da 4 a 9 controlli.
- ADR-0007: le pipeline CI/CD esistenti (Azure DevOps e GitHub Actions) come rail
  degli agenti e come canale di promozione tra ambienti. Due famiglie di pipeline
  separate per permesso (`pipe_agent_*` / `pipe_human_*`), definizione ancorata a
  `main`, artefatto `rail-result.json` a schema versionato come unico canale di
  esito. **Supera ADR-0002**.
- ADR-0008: permessi Fabric del Dev Agent — nessuna scrittura in modo permanente,
  ruolo `Viewer` sui soli workspace effimeri e `dev`, condizionato alla
  classificazione del dato e limitato al canale di diagnosi in eccezione.
- ADR-0009: repository Agentic separato con copia dei pattern di deploy, sei
  pattern dichiarati obbligatori, `PROVENANCE.md` e revisione periodica della
  divergenza.
- Review architetturale in `docs/technical/07-architecture-review.md`: validazione
  del design funzionale contro la documentazione ufficiale Microsoft Learn, con
  esito per area (sizing F32, topologia e ALM, contratto di connettore, identità e
  permessi), 3 rilievi bloccanti, 9 rischi non identificati nel PRD, 7 incoerenze
  interne alla documentazione e l'elenco esplicito delle affermazioni **non**
  verificate. Rispondono Q-5, Q-7 e Q-9.
- ADR-0001: isolamento della capacity per i feature workspace, con attuazione in
  due fasi e tetto di 5 workspace concorrenti (`docs/adr/`).
- ADR-0002: promozione degli ambienti via Git anziché Deployment Pipelines —
  Deployment Pipelines non supporta i report PBIR — e introduzione di
  `ws_agentic_test`.
- ADR-0003: cartelle del workspace create via Folders API (in preview), task flow
  declassato a passo manuale documentato. Chiude Q-9 e A-5.
- ADR-0004: ciclo di vita dei feature workspace con TTL a 72 ore e rail *Sweep*
  schedulato, in sostituzione di un cleanup al merge che nessun trigger del
  dispatcher può attivare.
- ADR-0005: perimetro dei dati verso i vendor LLM — i rail restituiscono solo
  evidenze aggregate, mai valori di dato — e roadmap di hosting a managed identity.
  Chiude la parte architetturale di Q-7.
- ADR-0006: completamento del contratto di connettore con collocazione del codice,
  definizione del metadata store, contratto di output dell'estrazione e semantica
  a tre grandezze del conteggio alla sorgente.
- PRD v0.1 (draft) per l'Agentic CI/CD su Microsoft Fabric e Power BI, in
  `docs/prd/PRD-agentic-cicd-fabric.md`: scope, requisiti funzionali e non
  funzionali, modello di permessi, roadmap a slice e domande aperte.
- `CONTEXT.md`: glossario di dominio, convenzioni di naming Fabric (prefissi per
  tipo item, workspace, cartelle per layer, task flow), convenzioni Git/tracker,
  convenzioni Power BI e principi non negoziabili.

### Changed

- PRD allineato allo scope MVP e ADR-0003: Open-Meteo è la sorgente REST di test; le cartelle
  sono automatizzabili, mentre il task flow resta un passo manuale documentato.
- ADR-0002 marcato **superato** da ADR-0007: resta valido il rifiuto delle Fabric
  Deployment Pipelines (incompatibili con PBIR) e la topologia a tre ambienti; è
  superata la promozione come *update from Git* manuale.
- ADR-0004 rivisto: il rail *Sweep* diventa una **pipeline schedulata** eseguita
  con l'identità di deploy (cancellare un workspace richiede `Admin`, che il Dev
  Agent non avrà mai), con `always: true` obbligatorio e criterio di selezione
  deterministico indipendente dal tracker.
- ADR-0005 rivisto: il perimetro dei dati si estende all'artefatto della pipeline,
  e si dichiara esplicitamente che il ruolo `Viewer` apre l'endpoint SQL — su quel
  canale la regola è convenzione e non permesso. Corretta la roadmap di hosting:
  un service principal non può creare PAT né usare OIDC federato fuori dalla CI,
  quindi una credenziale long-lived resta finché il dispatcher gira in locale.
- PRD aggiornato con le decisioni di discovery: riuso del framework
  metadata-driven esistente, Business Central come sorgente REST di riferimento,
  naming convention e struttura a cartelle vincolanti. Chiuse le domande
  Q-1, Q-2 e Q-8.
- PRD e `CONTEXT.md` aggiornati con le decisioni finali su ambiente e sorgenti:
  tenant AGIC, progetto `agentic`, capacity F32, due connettori eterogenei in
  fase 1 (REST via Open-Meteo e File via dataset sintetico). Roadmap
  riorganizzata con uno slice dedicato al secondo connettore come verifica
  dell'astrazione. Chiusa la domanda Q-10.
- Documentazione funzionale in `docs/functional/`: ciclo di vita del ticket,
  contratto del ticket, runbook di onboarding di una sorgente, checklist chiusa
  di review, protocollo di escalation e onboarding di un nuovo cliente.
- PRD esteso con i requisiti di istanziazione su nuovo progetto/cliente
  (RF-80..RF-85) e con il dataset sintetico dell'anagrafica città correlato a
  Open-Meteo. Chiusa la domanda Q-11.
- Documentazione tecnica in `docs/technical/`: architettura degli agenti,
  dispatcher, contratti dei rail script, identità e matrice dei permessi,
  struttura dei repository e contratto di connettore.
- Backlog degli Slice 0 e 1 in `docs/backlog/slice-0-1.md`: 20 work item con
  criteri di accettazione, dipendenze, tracciabilità ai requisiti del PRD e
  percorso critico.
