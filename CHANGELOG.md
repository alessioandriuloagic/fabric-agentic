# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Aggiunto il passaggio del contesto GitHub al task record: body dell'issue e allegati
  `github.com/user-attachments` vengono messi nella directory temporanea del task, con limite
  dimensionale per file e senza esporre token nei log.

- Corretto il flusso JWT della GitHub App: l'App ID numerico viene normalizzato a stringa
  per il claim `iss`, come richiesto da PyJWT.

- Implementata astrazione `WorkItemTracker` per supporto multi-backend tracker (issue #61):
  - Interfaccia `WorkItemTracker` con metodi comuni (new_items, waiting_input_items, comments, add_comment, set_state)
  - Adapter `GitHubIssuesTracker` per GitHub Issues via API REST + GraphQL
  - Adapter `AzureDevOpsTracker` migrato dal dispatcher
  - Tipo `WorkItemComment` normalizzato tra tracker
  - Factory `create_tracker()` per selezione backend configurabile via `dispatcher.tracker_type`
  - Configurazione template in `configuration/dispatcher.json`
  - Test completi per adapter (10 test) e dispatcher (9 test aggiornati)
  - Backward compatible: Azure Boards rimane default

### Sospeso lo sviluppo Report Power BI come TODO futuro: l'errore Desktop di rendering
  `visualContainers` con live connection è documentato e rimosso dal percorso critico.
- Definita come prossima priorità l'integrazione GitHub Issues per sostituire progressivamente
  Azure Boards nella gestione del ciclo di vita delle issue.

- Aggiunto `reportSource: Default` ai metadati PBIR del report CRM Demo per inizializzare
  esplicitamente l'esplorazione durante il rendering della live connection.

- Aggiunta una textbox statica al report PBIR CRM Demo: una pagina senza visual containers causava
  il crash JavaScript `visualContainers` durante l'attivazione del report live-connected.

- Rimosse le visuali PBIR pre-associate dal report CRM Demo per evitare `Missing_References` con
  il Semantic Model live: il report resta collegato via `byConnection` e le visuali saranno
  ricreate in Desktop dopo la verifica degli oggetti effettivamente esposti dal modello remoto.

- Corretto lo schema `$schema` dei file `.platform` PBIP/PBIR al formato Git Integration richiesto
  da Power BI Desktop (`gitIntegration/platformProperties/2.0.0`).

- Corretto il layout dei file `.platform` Power BI: `version` è ora dentro `config`, insieme a
  `logicalId`, come richiesto dal validatore PBIP di Desktop.

- Corretto `definition.pbism`: rimossa la proprietà non supportata
  `defaultPowerBIDataSourceVersion`, già presente nel `model.tmdl` dove è prevista.

- Collegato `CRM Demo.Report` al Semantic Model Fabric remoto tramite `datasetReference.byConnection`
  e `pbiServiceXmlaStyleLive`, usando il workspace `ws_agentic_test` e l'ID del modello pubblicato.

- Allineati gli schema metadata PBIR: `version.json` usa `versionMetadata/1.0.0` e `pages.json`
  usa `pagesMetadata/1.0.0`; validazione locale conclusa con 0 errori e 0 warning.

- Allineata anche la versione del contenuto PBIR in `version.json` a `1.0.0`, compatibile con
  Power BI Desktop August 2026; `definition.pbir` resta a versione `4.0`.

- Aggiunto lo schema ufficiale `fabric/pbip/pbipProperties/1.0.0` al manifest `CRM Demo.pbip`,
  evitando che Desktop interpreti il progetto con il parser legacy.

- Allineata la versione del manifest shortcut PBIP a `1.0`, perché Power BI Desktop August 2026
  rifiuta `1.0.0` come minor version non supportata; le versioni PBIR interne restano invariate.

- Ripristinata la versione PBIR `4.0.0` in `definition/version.json`: il formato PBIR con cartella
  `definition/` richiede `4.0` o superiore; `1.0.0` faceva ignorare i visual containers e causava
  l'errore JavaScript `visualContainers` durante il rendering.
- S1-01: predisposto il progetto PBIP/TMDL CRM Demo con Direct Lake verso `lh_bronze_crm_demo`.
  Il Semantic Model è stato creato nel workspace test; il manifest PBIP è stato corretto per usare
  un solo artifact `report`, con il modello collegato da `definition.pbir`.
- Creato e verificato il workspace Fabric `ws_agentic_test` nel tenant corrente, assegnato alla
  capacity `fabricalessiodev` con SKU F2; restano da predisporre gli item e le credenziali dello
  spike Power BI S1-01.

- Issue #42: introdotto il contratto rail-result v1.3 per `run_load`, con distinzione esplicita
  tra `loaded_count` del batch e `total_destination_count` dopo il merge.

- S1-05: registrata la retrospettiva del primo ciclo CRM in `docs/technical/10-retrospettiva-s1-04.md`,
  con KPI osservati, interventi umani non previsti e gap di strumentazione senza stime.

- Verificato il run reale CRM `32648577263`: nel feature Lakehouse sono state materializzate le
  tabelle `crm_demo_accounts`, `crm_demo_load_audit` e `crm_demo_watermark`. La riconciliazione
  quantitativa via SQL e la propagazione di conteggi/watermark nel `rail-result` restano aperte.
- Registrata l'evidenza quantitativa del run: 10 record `accounts`, una riga audit e una riga
  watermark.
- Il notebook CRM ora persiste l'evidenza aggregata in OneLake e il deployer la propaga nel
  `rail-result`, includendo conteggi, PK, riconciliazione e watermark.
- Verificato il run post-merge `32648994929`: delta incrementale di 5 record, Bronze totale di 10,
  PK/reconciliation passati e watermark `2026-08-21T17:39:25Z`. Da chiarire nel contratto la
  distinzione tra conteggio del batch e totale destinazione.
- Aggiornato `nb_crm_load` per il nuovo CRM `org12202591`: il notebook recupera direttamente la
  client secret dal Key Vault con `notebookutils.credentials.getSecret` e ottiene il token
  Dataverse con client credentials, senza dipendere dalla Fabric Key Vault Connection che
  restituiva `DMTS_KeyVaultInternalErrorCode`.
- Generata e salvata nel Key Vault DEV la client secret annuale `fabric-agentic-key` per lo SP
  `fabric-agentic-deploy`; il valore non è presente nel repository o nei log.
- Autorizzato lo SP `fabric-agentic-deploy` con `Key Vault Secrets User` sul vault
  `kv-fabric-agentic-dev-01`; la Fabric Connection CRM deve ancora essere modificata per usare
  questa identità del tenant corrente.
- Creato il Key Vault DEV `kv-fabric-agentic-dev-01` in `alessio_dev` con RBAC abilitato. Il
  vault appartiene al tenant `1cf6...`; l'accesso dello SP CRM nel tenant `d5e...` resta da
  configurare in modo esplicito prima di inserire o usare secret.
- Corretto `crm-run-load`: il deployer aggiorna anche il notebook `nb_crm_load` già esistente e
  materializza il binding dinamico al Lakehouse del feature workspace prima di eseguirlo. Il run
  reale del 2026-08-23 aveva avuto esito tecnico positivo ma nessuna tabella visibile perché il
  notebook era stato riusato senza Lakehouse predefinito.
- Corretto il payload REST dei notebook: il deployer converte il sorgente Fabric in `ipynb` con
  celle reali e metadata del Lakehouse. La definizione remota precedente risultava `cells: []`,
  spiegando il job verde senza file o tabelle.
- Implementato il primo runtime deterministico CRM: estrazione staged JSONL con watermark
  inclusivo, controllo PK, merge idempotente Bronze, audit per `run_id` e persistenza del
  watermark solo dopo l'audit. Aggiunto il rail locale `run_load` con risultato `rail-result`
  v1.0 e test del contratto. Il deploy Fabric/OIDC del notebook di carico resta da verificare.
- Aggiunti notebook Fabric `nb_crm_load`, deployer e workflow OIDC `crm-run-load`, limitato
  all'environment `dev`: il notebook esegue staging CRM, merge Delta Bronze, audit e watermark;
  la verifica end-to-end sul feature workspace resta da eseguire.
- S1-00: il tracer dati è riallineato su CRM `accounts`, tipologia già supportata e Fabric
  Connection `CommonDataService` esistente. Resta bloccato solo dal porting riproducibile del
  framework CRM con `PROVENANCE.md`.
- Avviato S1-00: provenienza del framework CRM registrata al commit pulito, configurazione
  `crm_demo`, schema fail-fast, builder OData incremental e collocazioni notebook/pipeline creati.
  Il framework non esegue ancora estrazioni o scritture Bronze.
- ADR-0012: definita la semantica CRM `accounts` per watermark inclusivo, merge idempotente e
  avanzamento del watermark solo dopo Bronze e audit riusciti.
- Aggiunto l'artifact `nb_crm_preflight` in formato FabricGitSource: valida la connection CRM
  tramite OData `$top=0` e restituisce solo evidenze aggregate, senza record o credenziali.
- Aggiunto workflow OIDC `crm-preflight`: crea/riusa Lakehouse e notebook nel feature workspace,
  esegue `RunNotebook` e pubblica un artifact strutturato senza token o dati CRM.
- Corretto l'avvio del deployer `crm-preflight` come modulo Python e garantita la pubblicazione
  di un risultato tecnico strutturato anche per errori di bootstrap.
- Preflight CRM eseguito con successo sul feature workspace del work item `6`: Lakehouse e
  notebook deployati, autorizzazione OData `$top=0` su `accounts` verificata senza esporre dati
  CRM o credenziali.
- ADR-0011: il primo ticket agentico reale diventa il tracer bullet CRM `accounts` in feature
  workspace. `ws_agentic_dev` è già predisposto; `test` e `prod` restano non
  provisionati/configurati fino a disponibilità di workspace e credenziali dedicate.
- Primo vertical slice S0-09: dispatcher locale del Dev Agent con token Azure DevOps a breve
  durata via certificato, stato anti-duplicazione fuori dal repo e Trigger A verificato in
  modalità read-only sul work item `#6`. Completati anche Trigger B/C con deduplicazione di
  commenti e review thread. Aggiunti loop configurabile a 30 secondi e log JSONL locale privo di
  token/credenziali; smoke S0-14 con sessione reale resta da completare.
- Aggiunta modalità S0-14 controllata: una sessione Claude read-only restituisce i documenti
  letti in JSON, mentre il dispatcher Dev Agent pubblica il commento e chiude il work item.
- S0-14 verificato sul campo (work item `#7`): trigger, sessione Claude, commento del Dev Agent,
  transizioni di stato e log senza token completati senza toccare Fabric.
  Corretto inoltre il client Azure Boards: i body JSON Patch usano `application/json-patch+json`
  anche nella creazione `POST` dei work item.
- S0-15: misurato il costo idle del dispatcher (due cicli senza task, 0 sessioni Claude e $0/0
  token LLM) e documentato il metodo per i KPI restanti. Il dispatcher accetta anche state file
  UTF-8 con BOM prodotti da PowerShell.
- S0-11: istruzioni versionate del Dev Agent e contratto JSON fra dispatcher e sessione in
  `agents/dev/`; vincolano lettura del contesto, uso dei rail, escalation, sicurezza,
  documentazione e divieto di merge o modifiche dirette a Fabric.
- Installato e verificato Claude Code `2.1.228` per il Dev Agent: una sessione headless minimale
  ha completato l'autenticazione locale con esito `READY`; il dispatcher attende clone isolato e
  credenziale Azure DevOps non interattiva del service principal Dev Agent.
- Configurata e provata la credenziale Azure DevOps non interattiva del Dev Agent: certificato
  client non esportabile nel certificate store locale e token Entra a breve durata per
  `app.vssps.visualstudio.com`; lettura del progetto tracker verificata senza PAT o client secret.
- Registrata la GitHub App del Dev Agent (App ID e Installation ID) e predisposto il percorso
  locale ACL-protetto per la private key PEM; la chiave resta fuori dal repository e dai log.
- Aggiunto il provider GitHub App del Dev Agent: firma JWT e ottiene installation token brevi in
  memoria; testato contro il repository autorizzato senza stampare token o materiale della key.
- Rail `sync_workspace` (S1-03): workflow GitHub Actions DEV-only, ancorato a `main`, che
  sincronizza il feature workspace deterministico soltanto per modifiche remote e pubblica un
  artefatto `rail-result.json` v1.2. Conflitti e divergenze locali falliscono esplicitamente
  senza sovrascrittura.
- Smoke test reale `sync_workspace` completato con successo (run `32488530726`): il feature
  workspace del work item `6` era già allineato, senza item aggiornati o scritture superflue.
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
