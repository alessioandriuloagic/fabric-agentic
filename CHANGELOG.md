# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- I notebook creati con definizione inline in Fabric non supportano updateDefinition.
  Il rail CRM ora passa la definizione inline al momento della creazione e non tenta mai un update
  successivo. Questo risolve i delta che fallivano con HTTP 404 al stage "definition".

- Il rail CRM classifica i failure con uno stage preciso (workspace, lakehouse, notebook,
  submission, storage_token, notebook_run, evidence) così i retry diagnostici non esigono accesso ai
  log GitHub; il messaggio non espone body API, token o ID sensibili.

- Il rail CRM acquisisce ora il token OneLake subito dopo la sottomissione del notebook, prima
  dell'attesa lunga dell'operazione Fabric, e lo riusa in memoria per leggere l'evidenza per-run.
  Nel delta reale il token richiesto solo dopo il job non era più acquisibile dall'identità OIDC.

- Il notebook CRM mantiene ora `RUN_ID` in una parameter cell Fabric dedicata, senza import o
  configurazione aggiuntivi. Il run reale generava un ID fallback invece di ricevere quello del
  Job Scheduler, impedendo al rail di leggere la corrispondente evidenza per-run.

- Il rail `run_load` attende ora fino a 60 secondi la visibilità OneLake della sola evidenza
  per-run richiesta dopo il completamento del notebook. Un HTTP 404 transitorio non genera un
  secondo load e non consente il fallback al file condiviso; gli altri errori restano fallimenti
  tecnici immediati.

- Il rail CRM calcola ora `reconciliation` confrontando i record estratti e riletti dallo
  staging; una divergenza produce un artefatto `quality_failure` e non avanza Bronze, audit o
  watermark. L'evidenza Fabric è inoltre identificata dal `run_id` generato prima della
  sottomissione e scritta/letta nel percorso per-run `Files/agentic/run_load_results/<run_id>.json`.

- Il rail `run_load` pubblica ora un artefatto conforme **anche quando fallisce** (#158).
  `scripts/run_load.py` dichiarava `schema_version: "1.0"` portando però i campi dataset della
  v1.3: il risultato non validava contro nessuno dei due schemi, proprio nel caso
  `quality_failure` su cui poggia l'escalation. Lo stesso valeva per il fallback scritto da
  `pipe_agent_crm_run_load.yml`, che emetteva `workspace_id: null` dove la v1.0 richiede una
  stringa non vuota. `scripts/validate_rail_result_schema.py` valida ora anche la v1.3 — finora
  l'unica versione senza guard, pur essendo quella realmente emessa dal rail — e il workflow di
  validazione del contratto si innesca anche sulle modifiche a `pipe_agent_crm_run_load.yml`.
  I test che presidiano staging, PK check, merge idempotente, audit e ordine del watermark sono
  stati aggiunti all'elenco eseguito dalla CI: esistevano ma non venivano eseguiti.

### Added

- Aggiunto `docs/technical/14-inventario-catena-crm-accounts.md` (#158): inventario verificato
  anello per anello della catena CRM `accounts`, con la classificazione esplicita di ogni
  affermazione in verificata, documentale o non verificabile. Registra le discrepanze corrette e
  le due lasciate aperte di proposito — `reconciliation` scritta come letterale invece che
  calcolata dai conteggi, ed evidenza Fabric letta da un percorso fisso non legato al run appena
  sottomesso — perché la loro correzione va provata da un carico reale, non da un test. Allineati
  `CONTEXT.md`, `docs/sources/crm_demo.md`, `docs/technical/03-rail-script.md` e il backlog S1-00,
  che descrivevano ancora la catena come da implementare e la v1.0 come schema di `run_load`.

### Changed

- Separato il catalogo aperto delle tecnologie sorgente dal registry degli adapter eseguibili
  (ADR-0018). Un profilo può ora descrivere Business Central, CRM, database SQL, Oracle,
  PostgreSQL, SharePoint, file o un identificatore futuro; se non esiste un adapter, dichiara
  esplicitamente capacità incrementali e conteggio alla sorgente. Render e UI mostrano che
  l'adapter è ancora da implementare, mentre `plan_request` continua a rifiutarne l'esecuzione.
  Il form usa suggerimenti modificabili anziché una select chiusa.

### Fixed

- Il controller del preflight CRM attende ora fino a cinque minuti l'operazione lunga del notebook
  Fabric, anziché dichiarare un falso timeout dopo 100 secondi mentre l'avvio Spark era ancora in
  corso. Il polling resta bounded e non ritenta la sottomissione del job.

- Il budget del controller CRM è esteso a 30 minuti dopo che il run `33637234261` ha prodotto un
  `ExitValue` valido ma ha oltrepassato la finestra di cinque minuti prima della conclusione
  dell'operazione Fabric. Il timeout resta bounded e non avvia un secondo notebook.

- Il preflight CRM decodifica il conteggio Dataverse come `utf-8-sig`, eliminando il BOM
  osservato nella risposta reale (`ï»¿10`) prima della conversione a intero.

- Il preflight CRM usa l'endpoint Dataverse `accounts/$count`, che restituisce esclusivamente il
  conteggio, al posto della query `$top=0` rifiutata con HTTP 400 nel run reale.

- Il notebook CRM di preflight usa ora il flusso service principal custodito in Key Vault, già
  adottato dal load, invece dell'API `notebookutils.connections` non disponibile nel runtime
  NotebookUtils. Il controllo resta privo di lettura record (`$top=0`).

- Il rail `branch_out` invia ora a Fabric la policy richiesta per inizializzare la connessione
  Git di un workspace feature (`PreferRemote`), allineando il workspace appena creato al branch
  deterministico anziché ricevere il rifiuto `MissingInitializationPolicy`.

- I rail locali CRM risolvono Azure CLI come `az.cmd` su Windows e `az` sugli altri sistemi,
  evitando `WinError 2` durante l'acquisizione dei token Fabric e OneLake da `subprocess`.

- Il fallback di `pipe_agent_crm_run_load` emette ora un artefatto conforme a
  `rail-result-v1.3` anche quando il processo termina prima del risultato. Le modifiche al workflow
  CRM attivano la validazione CI e la suite obbligatoria include i test di staging, Bronze, audit,
  watermark e artefatto Fabric. Questi file workflow sono separati dalla PR del Dev Agent perché
  la relativa GitHub App non possiede, correttamente, il permesso `workflows`.

- I tre dispatcher risolvono ora il comando agentico configurato (`claude`) con il resolver di
  sistema prima di avviare il processo. Su Windows PowerShell trovava `claude.exe`, ma
  `subprocess` riceveva il nome senza suffisso e falliva con `WinError 2`; la configurazione resta
  portabile e non contiene percorsi specifici della macchina. L'output Claude viene inoltre
  decodificato esplicitamente come UTF-8: il fallback CP1252 di Windows interrompeva il reader su
  caratteri validi non rappresentabili e lasciava `stdout` nullo. L'Issue Agent richiede infine
  `work_package` tramite `--json-schema`, invece di affidarsi a testo lungo non vincolato dentro
  l'envelope CLI.

### Added

- Aggiunta `docs/technical/13-issue-agent-guida-operativa.md`: guida completa al punto di ingresso
  del ciclo, dalla creazione dell'intake GitHub all'avvio del dispatcher, lettura del pacchetto,
  approvazione con label `dev-agent`, passaggio al Dev Agent, anti-duplicazione, troubleshooting e
  confini di sicurezza. Chiarita la differenza tra agente “pronto” e processo effettivamente in
  polling, e tra custom agent VS Code e flusso operativo sul tracker. Documentato il limite reale
  emerso sulla #150: `karl` e `ralph` sono disponibili in VS Code ma non nel runtime Claude Code
  locale; il percorso temporaneo verificato usa custom Issue Agent e publisher deterministico.

- Pubblicata la pagina di onboarding su `https://alessioandriuloagic.github.io/fabric-agentic/`;
  verificato il workflow GitHub Pages con il run `33501784788` (tentativo 3) dopo l'abilitazione
  del repository con sorgente GitHub Actions.

- Aggiunta la pagina statica di onboarding (#129) in `onboarding/`: scelta tra nuovo progetto e
  profilo cliente esistente, import locale, form guidato, validazione dei campi non sensibili,
  anteprima dei workspace e download di `instance.json`. Non usa backend, API autenticate o
  dipendenze runtime esterne. Schema, connector e starter vengono generati dal contratto Python
  durante la build, così la UI non mantiene un secondo elenco di regole. Il workflow
  `publish-onboarding-pages.yml` pubblica l'artifact su GitHub Pages dopo il merge su `main`.

- Aggiunto `python -m fabric_agentic init --directory <path>` (#128): genera un `instance.json` di
  partenza (slug e nome derivati dalla cartella se non passati esplicitamente, sempre con
  placeholder `REPLACE_WITH_*`, mai un segreto) e una `CHECKLIST.md` con i passaggi umani —
  identità e permessi, Fabric, Git, secret store — parametrizzata sul progetto e con un rimando a
  `docs/functional/06-onboarding-nuovo-cliente.md`. Nessuna chiamata esterna: solo scrittura su
  filesystem locale. Ripetibile e idempotente — un file già presente non viene sovrascritto a meno
  di `--force`, così un collega non rischia di perdere una modifica fatta a mano rilanciando il
  comando. L'output è verificabile da `validate` e `doctor` come qualunque altro profilo.

- Aggiunto un `README.md` alla radice: sommario compatto di cosa fa il kit, avvio rapido, struttura
  del repository, come si porta su un cliente o un collega, stato e limiti noti, con link a ogni
  documento di approfondimento. `pyproject.toml` torna a dichiararlo come `readme` del pacchetto,
  ora che il file esiste.

- Registrato `ADR-0017`: il runtime target dei tre dispatcher è event-driven su runner
  self-hosted, non un supervisore locale né un servizio always-on. Issue e Review sono di fatto
  stateless e migrano per primi; il Dev Agent, con stato locale reale, migra per ultimo. La
  decisione dipende da un prerequisito bloccante indipendente: un'identità di inferenza non
  legata a un login personale.

- Registrato come voce aperta (PRD Q-13, `CONTEXT.md`, checklist di onboarding) che Issue, Dev e
  Review invocano oggi lo stesso Claude Code sotto l'account **personale** dell'operatore, non
  un'identità aziendale: blocca l'uso del flusso su un cliente reale o l'esecuzione da parte di
  un collega finché non viene risolto.

- Completata la CLI del kit: `validate` verifica il profilo di istanza prima di qualsiasi chiamata
  esterna, `render` genera il piano di deployment (`plan.json` e `README.md`) in modo riproducibile
  byte per byte, e `doctor --config` unisce identità provisionate e profilo valido. Il pacchetto
  espone l'entry point `fabric-agentic` quando installato, restando eseguibile come
  `python -m fabric_agentic` senza installazione.

- I dispatcher Issue e Review hanno ora un ciclo continuo (`--poll`, con `--cycles` per limitarlo),
  costruito su un loop condiviso in `fabric_agentic/polling.py`. Il loop si ferma dopo tre cicli
  falliti consecutivi: uno stato anti-loop che non avanza renderebbe il retry una riesecuzione
  ripetuta della stessa sessione, non un semplice tentativo.

- Aggiunta la superficie di avvio del kit: `python -m fabric_agentic doctor` verifica cosa è
  provisionato su una macchina e stampa il comando di avvio di ogni agente, mentre
  `python -m fabric_agentic console` espone la stessa vista in una pagina locale in sola lettura,
  su loopback, senza avviare processi né leggere materiale crittografico. Il layout canonico degli
  agenti e i vincoli della console sono documentati in `docs/technical/12-console-e-avvio.md`.

- Aggiunto il registry dei connector in `fabric_agentic/connectors.py`: ogni connector dichiara le
  proprie capacità e `plan_request` risolve la lettura di un dataset senza rami per sorgente. Il
  profilo di istanza deriva da qui l'elenco ammesso e rifiuta un carico incrementale su un connector
  che non lo supporta. `ADR-0016` registra la decisione, incluso `file` come connector supportato
  ma a solo carico completo.

- Estratto il core riutilizzabile nel pacchetto `fabric_agentic/`, con `pyproject.toml` e versione
  dichiarata. `scripts/` resta il perimetro operativo e un test verifica che il core non importi
  mai gli script. Aggiunto `ADR-0015` sulla scelta del pacchetto alla radice invece di `src/`,
  motivata dall'esecuzione immediata dopo il clone e dalla CI senza step di installazione.

- Completato lo smoke end-to-end dell'Issue Agent sull'intake usa-e-getta #134: discovery,
  sessione, pacchetto A-G completo e commento pubblicato dall'identità `fabric-agentic-issue-agent`,
  senza intervento umano. Nessun work item creato e nessun ricandidamento alla riesecuzione.

- Aggiunto il contratto portabile del profilo di istanza: `fabric_agentic/instance_profile.py` valida
  progetto, tracker, ambienti, connector, dataset, chiavi, modalità di carico e watermark, rifiuta
  credenziali inline e deriva i nomi workspace dallo slug di progetto. Aggiunto il profilo template
  in `profiles/template/instance.json`. Nessuna dipendenza esterna, così la CI resta senza install.

- Aggiunta la catena deterministica dell'Issue Agent: dispatcher su intake etichettate
  `issue-agent`, istruzioni versionate in `agents/issue/INSTRUCTIONS.md` e rail
  `scripts/issue_package_publish.py` che valida il pacchetto e pubblica un solo commento. Il rail
  non crea work item: il ticket nasce solo dopo l'approvazione umana.

- Aggiunto `ADR-0014`: innesco dell'Issue Agent tramite issue di intake, pubblicazione via rail
  deterministico, identità applicativa dedicata e cancello umano prima del work item.

### Fixed

- Allineata la documentazione al codice dopo l'estrazione del core e l'arrivo di registry, CLI e
  ciclo continuo: percorsi dei moduli spostati, albero del repository, connettore `file` a solo
  carico completo, connettore REST marcato come non registrato, checklist di onboarding a tre
  agenti e indice dei documenti tecnici. `pyproject.toml` non dichiara più un `README.md`
  inesistente, che faceva fallire la build del pacchetto.

- I tre dispatcher leggono la configurazione con un lettore condiviso che accetta il BOM scritto
  dagli editor e dalle shell Windows: un JSON valido non viene più rifiutato all'avvio. Il Dev Agent
  segnala inoltre il tracker non dichiarato, che prima ripiegava in silenzio su Azure DevOps.

- I dispatcher Review e Issue preparano ora la clone con la propria identità applicativa invece che
  con le credenziali ambientali dell'utente: `credential.helper` è azzerato e il token arriva solo
  dal broker. Il broker è stato estratto in `fabric_agentic/credential_broker.py` ed è condiviso dai tre
  agenti, non duplicato.

- Reso il rail del pacchetto tollerante alla prosa che la sessione antepone all'intestazione,
  allineandolo al publisher del voto di review. Il contratto delle sezioni resta invariato.

- Resa portabile l'espansione dei percorsi di configurazione: `%VAR%` e `$VAR` sono entrambi
  supportati e `%USERPROFILE%` ricade sulla home anche su POSIX. La sintassi Windows restava
  letterale su Linux, quindi la stessa configurazione non era distribuibile.

- Estesa la copertura CI ai dispatcher Review e Issue e all'espansione dei percorsi, che prima non
  erano protetti dal workflow.

- Completato lo smoke end-to-end del Review Agent sulla PR usa-e-getta #130: discovery,
  preparazione della clone, sessione, esito A1-F4 e voto `CHANGES_REQUESTED` pubblicato
  dall'identità `fabric-agentic-review-agent`, senza intervento umano e senza merge.

### Fixed

- Resa portabile la guardia `pre-push` del Dev Agent: l'hook viene reso eseguibile e gli shim sono
  generati anche in forma POSIX. Senza il permesso di esecuzione Git ignorava l'hook, quindi su
  Linux il push su `main` non era bloccato.

- Isolate le credenziali di sessione azzerando `credential.helper`: la sessione può autenticarsi
  solo con il token intermediato dal broker, mai con credenziali ambientali dell'utente. L'askpass
  risponde ora un valore per invocazione, come previsto dal contratto `GIT_ASKPASS`.

- Corretti due difetti del dispatcher Review emersi dallo smoke reale: il publisher viene ora
  invocato come modulo e la clone recupera l'head della PR in `refs/remotes/origin/pr/<n>` restando
  su `main`, così la sessione legge il diff e la copia di pubblicazione resta allineata.

- Reso ermetico il test della guardia `pre-push`: usa un repository temporaneo e verifica sia il
  rifiuto del push su `main` sia il push consentito su `feature/*`, senza dipendere dallo stato del
  repository corrente.

- Integrata l'evidenza S0-07 di lettura API del Dev Agent: workspace, item e istanze job leggibili
  con HTTP `200`; i probe di scrittura restano separati perché quelli invalidi non dimostrano il
  permesso.

- Registrati i probe S0-07 del 2026-08-27: Dev Agent legge `ws_agentic_dev` con HTTP `200`, la
  creazione workspace è rifiutata con HTTP `401`; i probe item/job e tenant settings restano non
  conclusivi o non leggibili nel contesto disponibile.

- Registrata l'evidenza UI dei ruoli S0-07: `fabric-agentic-deploy` è `Contributor`,
  `fabric-agentic-dev-agent` è `Viewer` e il Review Agent non è assegnato al workspace.

- Chiuso il ticket #98 e riallineato il backlog: prove Review Agent di scrittura negata (`403`),
  voto consentito e merge negato (`403`) registrate senza side effect.

- Aggiunto il broker di credenziali localhost per la sessione Dev Agent: Git e `gh` ricevono il
  token solo nei rispettivi helper, mentre il modello non riceve token nell'ambiente o nei
  parametri; il push resta limitato ai branch `feature/*`.

- Aggiunta la allowlist esplicita per la sessione Dev Agent: test, branch, commit, push solo verso
  `feature/*` e apertura PR, senza bypass dei permessi; il credential broker e la guardia
  `pre-push` impediscono anche l'accesso a `main`.

- Resa diagnosticabile la sessione Dev Agent a vuoto: il dispatcher registra `productive`,
  `no_work` o `failed` nell'evento `session_completed`, con test di regressione e senza loggare
  l'output integrale della sessione.

- Allineato il rail di pubblicazione alla checklist: lo stato `CORRETTO` è accettato nelle
  re-review, non conta come rilievo aperto ed è coperto da un test di contratto sugli stati.

- Aggiunto il dispatcher deterministico del Review Agent: discovery delle PR aperte, filtro draft e
  head SHA già revisionati, dry-run senza scritture, lock di sessione e handoff al publisher #97.

- Registrata la prova negativa #98 dell'identità Review Agent: lettura repository HTTP `200`,
  tentativo `contents:write` su ref di probe negato con HTTP `403` e tentativo di merge della PR
  usa-e-getta #109 negato con HTTP `403`, entrambi senza effetti permanenti.

- Versionati i due kaizen del 2026-08-26 già referenziati da `AGENTS.md`, i cui link puntavano a
  file inesistenti, e registrata nel backlog Slice 0/1 la cronologia diagnostica del rail
  `sync_workspace` e delle riparazioni degli artifact Fabric.

- Aggiunto `ADR-0013`: identità GitHub dedicata al Review Agent e pubblicazione del voto tramite
  rail deterministico, con le alternative scartate e i limiti accettati.

- Prima review reale del Review Agent sulla PR #94: checklist A1-F4 completa, tre rilievi aperti
  (`E1`, `E5`, `F3`) e voto GitHub rifiutato perché l'agente non ha ancora un'identità distinta
  dall'autore della PR.

- Aggiunto l'Issue Agent come orchestratore di avvio lavoro: delega i requisiti a `karl` e
  l'architettura a `ralph`, produce un pacchetto approvabile e non crea work item prima
  dell'approvazione umana.

- Aggiunti il custom agent condiviso del Review Agent e il prompt parametrizzato per avviare una
  review indipendente A1-F4 su una pull request.

- Corretto il rail `branch_out` per riusare una Git connection GitHub esistente: ora confronta
  `ownerName` (con fallback Azure DevOps) e non fallisce su feature workspace già collegati.

- Registrato il run OIDC `pipe_agent_branch_out` `32945217566`: checkout e login Deploy SP
  riusciti, ma rail bloccato nello stage `git_connection` senza creare risorse.

- Verificato il Deploy SP OIDC: run manuale `32943998407` da `main` riuscito con lettura metadata
  di `ws_agentic_dev` tramite `pipe_human_test_azure_oidc_dev`.

- Applicato il naming delle famiglie GitHub Actions: workflow operativi `pipe_agent_*` e test
  manuale `pipe_human_*`; non esistono workflow schedulati nel perimetro corrente.

- Nuova prova S0-07 dopo la configurazione del gruppo: GET workspace Dev Agent HTTP `200`, POST
  creazione workspace negato con HTTP `401`, nessuna risorsa creata. Il blocco sembra applicato;
  resta da verificare il Deploy SP e il codice `403` atteso.

- Registrato il fallimento del probe S0-07: il Dev Agent legge il workspace con HTTP `200`, ma può
  ancora creare un workspace con HTTP `201`; la risorsa temporanea è stata eliminata. Il setting
  di creazione va ristretto al gruppo `FabricAgentDeploy`. Il portale mostra il Dev Agent nel
  gruppo, ma il probe continua a restituire HTTP `201`: propagazione o semantica da chiarire.

- Aggiornato il risultato della prova S0-07: il Service Principal Dev Agent legge il workspace
  Fabric con HTTP `200`; il setting di creazione workspace/connection/deployment pipeline resta
  però abilitato per l'intera organizzazione e va ristretto al deploy SP.

- Registrata la verifica parziale dei permessi Fabric: Dev Agent `Viewer` su `ws_agentic_dev` e
  Review Agent senza accesso Fabric; restano le prove negative e gli switch tenant da verificare.

- Aggiunte le istruzioni versionate del Review Agent in `agents/review/INSTRUCTIONS.md`, con
  checklist A-F, formato di voto e confini di sicurezza.

- Aggiornato il backlog S0: S0-06 resta TODO per il limite di licenza GitHub; S0-07, S0-N1/N2
  e S0-12 restano da verificare o completare; S0-15 include la durata del run pagamenti e il
  costo monetario non attribuibile.

- Aperto il ticket amministrativo GitHub #83 per verificare separazione e autorizzazioni delle
  famiglie di pipeline S0-N1/S0-N2.

- Registrato il primo run Fabric del tracer `pagamenti`: 10 righe caricate e 10 in destinazione,
  `pk_check` e riconciliazione passati, run `20260825T141929Z-70aacec7`, durata osservata 21 s.
  Il costo monetario della capacity e il costo LLM non sono attribuibili dall'evidenza disponibile.

- Aggiunto il notebook Fabric `nb_ingest_pagamenti` (issue #72): legge
  `Files/raw/pagamenti/pagamenti.csv` con schema esplicito in `FAILFAST`, tipizza `Data` come data
  e `Importo` come `decimal(18, 2)`, verifica l'unicità di `ID_Pagamento` prima di qualsiasi
  scrittura e fa merge sulla tabella Delta `pagamenti` del Lakehouse `lh_bronze_crm_demo`, così una
  riesecuzione aggiorna invece di duplicare. Aggiunti il runtime deterministico
  `scripts/pagamenti_load.py`, i test `tests/test_pagamenti_load.py` e l'inventario
  `docs/sources/pagamenti.md`. La sorgente File resta fuori dal framework metadata-driven: il
  blocco B3 di `docs/technical/09-framework-gate.md` non è chiuso da questa modifica.

- Aggiunta la cartella `attachments/<issue-number>/` come canale versionato e riproducibile per
  trascrizioni e file che il Dev Agent deve leggere.

- Il dispatcher ora solleva `DispatcherError` quando la sessione Dev Agent termina con exit code
  non riuscito, evitando di registrare il ciclo come completato senza successo.

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
  da Power BI Desktop (`gitIntegration/platformProperties/2.0.0`). **Superato il 2026-08-26**: per
  la sincronizzazione Git di Fabric vale `platform/platformProperties.json` con `version` alla
  radice.

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
  e aggiunto il workflow manuale `pipe_human_test_azure_oidc_dev.yml` per verificare login OIDC e lettura dei
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

### Fixed

- Il voto di review diventa un oggetto GitHub reale: `scripts/review_vote_publish.py` valida l'esito
  A1-F4 prodotto dalla sessione e invia **una sola** review submission con l'identità applicativa del
  Review Agent. `VOTO: APPROVATO` produce `APPROVE`, `VOTO: NON APPROVATO` produce `REQUEST_CHANGES`;
  un esito malformato termina con errore prima di coniare qualunque token, quindi non esistono voti
  parziali. L'operazione è idempotente sulla coppia (numero PR, head sha) e il publisher rifiuta
  l'esecuzione da una copia non allineata a `main` o con modifiche non committate. Il token è coniato
  al momento e resta solo in memoria del processo: la sessione di review non conia token, non firma
  il JWT e non conosce il percorso della private key. Prima il voto veniva tentato con l'identità
  umana dell'owner e GitHub lo rifiutava (`Review Can not request changes on your own pull request`
  su PR #94 e #95, con `gh pr view <n> --json reviews` vuoto). Aggiornati di conseguenza
  `agents/review/INSTRUCTIONS.md`, il custom agent e il prompt del Review Agent,
  `docs/technical/03-rail-script.md` e `docs/technical/04-identita-e-permessi.md`, che registra anche
  il rischio accettato sulla collocazione della private key.

- `waiting_input_items` impone la congiunzione delle label: il filtro GraphQL di GitHub si comporta
  come OR, quindi la congiunzione fra `dev-agent` e `waiting-input` viene ora applicata lato client.
  Prima ogni issue con la sola `dev-agent` risultava in attesa di risposta umana.

- Il dispatcher registra l'esito della sessione Dev Agent con `session_completed`, includendo
  `returncode`, `is_error`, `session_id`, `num_turns` e `changed_repository`. Una sessione che non
  lascia lavoro nel clone non e' piu' indistinguibile da una riuscita.

- Il dispatcher concede alla sessione Dev Agent l'accesso alla directory del task record tramite
  `--add-dir`. Senza di esso la sessione partiva dentro il clone isolato e non poteva leggere il
  proprio task record, terminando con codice `0` senza implementare nulla.

- Chiusi i rilievi della review sulla PR #94: rimosso il permesso `edit` dall'Issue Agent, aggiunto
  l'Issue Agent al glossario vincolante di `CONTEXT.md` e corretto il ciclo di vita del ticket, che
  attribuiva la stesura al solo owner umano.

### Changed

- Il tracker predefinito del dispatcher passa da `azure_devops` a `github_issues`: GitHub Issues
  diventa il backend operativo dei work item e Azure Boards resta legacy. Verificato con un
  `--once --dry-run` sul tracker GitHub.

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
