# CONTEXT.md — Glossario di dominio e convenzioni

> **Questo documento è vincolante.** È il *shared context* che Dev Agent e Review Agent
> leggono all'inizio di ogni sessione. Ciò che non è scritto qui non è una convenzione:
> è un'improvvisazione, e in code review va segnalata come rilievo.
>
> Fonte di verità: questo file nel repo. La wiki del tracker è **generata** da qui.

| Campo | Valore |
|---|---|
| Versione | 0.9 |
| Ultimo aggiornamento | 2026-08-27 |
| Documenti collegati | `docs/prd/PRD-agentic-cicd-fabric.md`, `docs/adr/` |

---

## 1. Glossario dei ruoli agentici

| Termine | Definizione |
|---|---|
| **Issue Agent** | Agente AI che orchestra `karl` (requisiti, KPI, UAT) e `ralph` (architettura, flussi, ambienti, CI/CD) e produce un pacchetto di lavoro approvabile con i ticket proposti. **Non crea work item senza approvazione umana, non scrive codice di feature.** Non ha accesso a Fabric. |
| **Dev Agent** | Agente AI che esegue il ciclo di sviluppo end-to-end su un work item: branch, feature workspace, implementazione, test reale, documentazione, apertura PR. **Non merge mai.** |
| **Review Agent** | Agente AI, di vendor diverso, che revisiona la PR contro una checklist chiusa. **Non scrive codice di feature, non merge.** Non ha accesso a Fabric. |
| **Dispatcher** | Script deterministico in polling sul tracker. Rileva i trigger e avvia una sessione fresca dell'agente. **Non usa LLM**: da fermo il costo è zero. |
| **Rail (script deterministico)** | Script versionato che esegue un'operazione procedurale ripetitiva al posto dell'LLM. Gli agenti orchestrano, i rail eseguono. I rail che toccano Fabric **invocano una pipeline CI/CD**, non chiamano direttamente le API; il rail che pubblica il voto di review chiama invece l'API GitHub con l'identità applicativa del Review Agent, perché il modello non deve tenere il token |
| **Rail-result** | Artefatto a schema versionato prodotto da ogni pipeline agentica. È il **canale primario** con cui l'agente conosce l'esito di un'esecuzione |
| **ExecutionCredential** | Credenziale tecnica di un cliente usata esclusivamente dalle pipeline CI/CD. Può essere SP OIDC, SP con secret o utenza di servizio in Key Vault; non è mai disponibile al modello |
| **Diagnose data** | Rail che analizza sorgente, Bronze o Silver e restituisce al modello solo evidenze aggregate o mascherate |
| **Pipeline agentica** | Pipeline CI/CD che gli agenti sono autorizzati ad accodare. Ancorata a `main`, parametrizzata, mai verso produzione |
| **Pipeline umana** | Pipeline CI/CD riservata all'owner. Gli agenti non possono accodarla |
| **Sweep** | Pipeline schedulata che rimuove i feature workspace scaduti. Gira con l'identità di deploy, non con quella dell'agente |
| **Feature workspace** | Workspace Fabric isolato e temporaneo, creato per un singolo work item e rimosso alla scadenza. |
| **Checklist chiusa** | Elenco versionato e finito di criteri di review. Il Review Agent non ne aggiunge di propri. |
| **Tracer bullet** | Slice verticale sottile che attraversa l'intera catena end-to-end per validarla. |

---

## 1-bis. Disambiguazione: la parola "pipeline"

> **Tre cose diverse si chiamano "pipeline".** È la principale fonte di fraintendimento del
> progetto: un agente che legge "pipeline" senza qualificatore implementerà la cosa sbagliata
> con piena convinzione.

| Termine da usare | Che cos'è | Nel nostro progetto |
|---|---|---|
| **Data pipeline** | Item Fabric di orchestrazione dati (prefisso `pl_`) | Sì, è ciò che gli agenti costruiscono |
| **Pipeline CI/CD** | Azure DevOps Pipeline o GitHub Actions workflow | Sì, è ciò che gli agenti **invocano** come rail |
| **Fabric Deployment Pipeline** | Funzionalità Fabric di promozione dev→test→prod tra workspace | **No: non usata.** La promozione avviene via pipeline CI/CD |

**Regola di scrittura**: nei documenti e nei ticket la parola "pipeline" non compare mai da
sola. Sempre qualificata.

---

## 1-ter. Dispatcher e Work-Item Tracker (tracking backend)

| Termine | Definizione |
|---|---|
| **Dispatcher** (`scripts/dev_dispatcher.py`) | Script deterministico in polling che monitora il tracker (Azure Boards o GitHub Issues) e accoda le sessioni Dev Agent. **Non usa LLM: da fermo il costo è zero.** Si configura via `configuration/dispatcher.json` con campo `tracker_type`. |
| **WorkItemTracker** | Interfaccia astratta (`scripts/tracker.py`) che astrae le operazioni di ciclo di vita del work item. Supporta backend multipli. |
| **Work-item** | Elemento atomico di lavoro nel tracker (Work Item in Azure Boards, Issue in GitHub). Ha `id`, `state`, titolo, commenti. |
| **Work-item state** | Stato del work item: `To Do`, `Doing`, `Done` (comune a entrambi i tracker). |
| **Tracker backend** | Implementazione concreta di `WorkItemTracker`: `AzureDevOpsTracker` (default) o `GitHubIssuesTracker`. |
| **AzureDevOpsTracker** | Adapter per Azure DevOps. Usa REST API + WIQL queries. Identità di dispatch via service principal (certificate-based). |
| **GitHubIssuesTracker** | Adapter per GitHub Issues. Usa REST API + GraphQL. Identità di dispatch via GitHub App (federated OIDC). |
| **Device-of-record tag** | Tag/label sul work item che qualifica quale agente detiene il lavoro. Default: `dev-agent` (Azure) e label `dev-agent` (GitHub). |
| **Waiting-input tag** | Tag/label aggiunto quando il work item è in `Doing` e attende feedback umano (commento da non-agente). Permette al dispatcher di discriminare tra agente bloccato e agente attivo. |
| **Issue attachment repository path** | Percorso versionato `attachments/<issue-number>/` per trascrizioni e file che il Dev Agent deve leggere nella clone isolata. |

### Stato verifica backend (2026-08-25)

- I test unitari mirati per autenticazione, adapter e dispatcher passano: `22 passed`.
- Il PEM GitHub locale è stato caricato come chiave RSA privata valida e il JWT viene firmato
   correttamente dopo la normalizzazione dell'App ID a stringa.
- Dopo l'update dei permessi sull'installazione, il test reale GitHub raggiunge l'API e il
   dispatcher legge correttamente una issue di prova (`#64`) con label `dev-agent`:
   `1 task found`, trigger `new_work`, in `dry-run`.
- L'issue di prova `#64` è stata chiusa dopo la validazione read-only.
- Lifecycle operativo GitHub verificato sull'issue temporanea `#66`: `new_work`, passaggio a
   `Doing`, sessione smoke S0-14, commento dell'identità GitHub App e passaggio finale a `Done`
   (issue chiusa). Il log dispatcher conferma il polling e il completamento del ciclo.
- Il test reale Azure DevOps passa con il work item `#6`: il service principal ottiene il token
   tramite il certificato locale e il dispatcher trova `1 task` con trigger `new_work`.
- Identità Azure DevOps individuata: App Registration/Service Principal Dev Agent con Application
   ID `e74ca724-e306-4ff3-ae02-77ef7368e673`; certificato locale `CN=fabric-agentic-dev-agent`,
   con chiave privata nello store `CurrentUser\My` e thumbprint configurato nel dispatcher.
- Non creare issue di prova né modificare stati finché il test read-only GitHub non passa.

---

## 2. Glossario di dominio dati

| Termine | Definizione |
|---|---|
| **Source system** | Sistema sorgente logico (es. `business_central`). Un source system ha **un solo** file di configurazione JSON. |
| **Dataset** | Singola entità estratta da un source system (es. `customers`). Corrisponde a un endpoint REST o a una tabella. |
| **Bronze Layer** | Dato grezzo persistito come arrivato dalla sorgente, arricchito solo di metadati tecnici. Nessuna regola di business. |
| **Silver Layer** | Dato pulito, deduplicato, conformato e tipizzato. Qui vivono le regole di qualità e le chiavi surrogate. |
| **Semantic Layer** | Semantic model Power BI: misure DAX, relazioni, gerarchie. Nessuna trasformazione strutturale. |
| **Full load** | Estrazione completa del dataset, con sostituzione integrale della destinazione. |
| **Incremental load** | Estrazione dei soli record modificati dopo un watermark. |
| **Watermark column** | Colonna che guida l'incrementalità (tipicamente una data di ultima modifica). |
| **Primary key columns** | Elenco di colonne che identificano univocamente un record. Guidano il controllo di unicità e la logica di merge. |
| **PK check** | Controllo di unicità delle chiavi primarie dichiarate, **eseguito prima di qualsiasi scrittura**. Se fallisce, il carico si ferma. |
| **Audit run** | Riga di audit per dataset e per esecuzione, con conteggi sorgente e destinazione. È l'evidenza allegata alla PR. |

---

## 3. Convenzioni di naming — Fabric

### 3.1 Prefissi per tipo di item

Regola generale: `<prefisso>_<nome_in_snake_case>`, tutto minuscolo.

| Tipo di item Fabric | Prefisso | Esempio |
|---|---|---|
| Workspace | `ws_` | `ws_agentic_dev` |
| Lakehouse | `lh_` | `lh_bronze` |
| Warehouse | `wh_` | `wh_gold` |
| Notebook | `nb_` | `nb_ingestion_bronze` |
| Data Pipeline | `pl_` | `pl_ingest_crm_accounts_bronze` |
| Dataflow Gen2 | `df_` | `df_staging_customers` |
| Semantic model | `sm_` | `sm_sales` |
| Report | `rpt_` | `rpt_sales_overview` |
| Environment | `env_` | `env_spark_default` |
| Spark Job Definition | `sjd_` | `sjd_batch_reprocess` |
| Eventstream | `es_` | `es_telemetry_ingest` |
| Eventhouse | `eh_` | `eh_realtime` |
| KQL Database | `kqldb_` | `kqldb_telemetry` |
| Activator (Reflex) | `act_` | `act_load_failure_alert` |
| Deployment pipeline | `dp_` | `dp_agentic` |

### 3.2 Workspace

| Scopo | Pattern | Esempio |
|---|---|---|
| Ambiente | `ws_<progetto>_<ambiente>` | `ws_agentic_dev`, `ws_agentic_prod` |
| Feature (temporaneo, creato dal Dev Agent) | `ws_<progetto>_feature_wi<id>` | `ws_agentic_feature_wi42` |

Ambienti ammessi: `dev`, `test`, `prod`. Progetto corrente: **`agentic`**.

> Il nome progetto è un **parametro**, non una costante: l'asset è riusabile su altri
> progetti o clienti cambiando solo quel segmento.

**Regola vincolante**: il nome del feature workspace è **derivato deterministicamente** dall'ID del work item. L'agente non sceglie il nome. Questo rende i workspace orfani identificabili e il cleanup automatizzabile.

### 3.3 Cartelle dentro il workspace

Ogni workspace segue la stessa struttura a cartelle, allineata al modello medallion:

```
ws_agentic_dev/
├── Bronze Layer/              # lakehouse e item del layer bronze
├── Full and Incremental Load/ # pipeline e notebook di orchestrazione del carico
├── Silver Layer/              # lakehouse/warehouse e item del layer silver
├── Semantic Layer/            # semantic model
├── Report/                    # report Power BI
└── Test Items/                # artefatti di test e validazione
```

**Regola vincolante**: nessun item alla radice del workspace. Ogni item nasce nella cartella del proprio layer.

### 3.4 Task flow

Il workspace espone un **task flow** che rende leggibile il flusso end-to-end anche a chi non conosce la soluzione. Sequenza di riferimento:

```
Get data from Source → Bronze Layer → Full & Incremental Load → Silver Layer → Semantic Layer → Data visualize (Report)
```

> **Da verificare (Q-9)**: se il task flow sia creabile e mantenibile via API/CLI o solo da interfaccia.
> Se non è automatizzabile, resta un passo manuale documentato nel runbook e **non** un criterio bloccante di review.

---

## 4. Convenzioni di naming — dati

| Elemento | Convenzione | Esempio |
|---|---|---|
| Source system | `snake_case`, singolare | `crm_demo`, `city_registry` |
| Dataset | `snake_case`, plurale | `accounts`, `cities` |
| File di configurazione | `configuration/<source_system>.json` | `configuration/crm_demo.json` |
| Tabella bronze | `<source_system>_<dataset>` | `crm_demo_accounts`, `city_registry_cities` |
| Path raw | `Files/raw/<source_system>/<dataset>/<run_timestamp>/` | — |
| Colonne di metadato tecnico | prefisso `_meta_` | `_meta_ingested_at` |

**Le colonne di business mantengono il nome della sorgente.** Non si rinominano in bronze: la rinomina, se serve, avviene in silver ed è una decisione esplicita.

---

## 5. Convenzioni di naming — Git e tracker

Azure Boards operativo: organizzazione `AlessioAndriuloDev`, progetto `fabric-agentic`.
Le work item storiche #19-#23 dell'organizzazione `alessioandriulo` sono state migrate come
Issue #1-#5 nel nuovo progetto, mantenendo stati e tag. Il nuovo progetto e' la sorgente operativa.
Nel progetto sono stati aggiunti i service principal del Dev Agent con access level `Basic` e del
Review Agent con access level `Stakeholder`; Azure DevOps li mostra in provisioning `pending`.

| Elemento | Pattern | Esempio |
|---|---|---|
| Branch feature | `feature/wi-<id>-<slug>` | `feature/wi-42-onboard-crm-accounts` |
| Branch di release | `chore/release-v<x.y.z>` | `chore/release-v0.2.0` |
| Commit | Conventional Commits | `feat(bronze): onboard crm_demo accounts` |
| Tag di release | `v<x.y.z>` | `v0.2.0` |
| Tag work item per il Dev Agent | `dev-agent` | — |

---

## 6. Convenzioni Power BI

| Elemento | Convenzione |
|---|---|
| Tabelle nel semantic model | `PascalCase`, singolare per le dimensioni (`Customer`), plurale per i fatti (`Sales`) |
| Colonne | `PascalCase`, leggibili dal business (`OrderDate`, non `order_dt`) |
| Misure | `PascalCase` con spazi ammessi (`Total Sales`, `Sales YoY %`) |
| Misure nascoste di supporto | prefisso `_` (`_Sales Base`) |
| Formato dei file | **TMDL/PBIP e PBIR** — testuale e versionabile. **Mai `.pbix` binario nel repo.** |
| Tabella misure | Tabella dedicata senza colonne, per raggruppare le misure |

---

## 7. Sorgenti dati

La piattaforma è **multi-sorgente per costruzione**. Il framework metadata-driven esistente
viene riusato: un file JSON di configurazione per source system, e un **connettore** per
tipologia di sorgente dietro un contratto comune.

### 7.4 Secret store CRM DEV

| Elemento | Valore |
|---|---|
| Key Vault | `kv-fabric-agentic-dev-01` |
| Resource group | `alessio_dev` |
| Subscription | `898b6a78-11dd-4e23-bf53-9e17f541d955` |
| Tenant del vault | `1cf6db06-3e00-48b6-a65c-be932526610e` |
| URI | `https://kv-fabric-agentic-dev-01.vault.azure.net/` |
| Autorizzazione | Azure RBAC abilitato |
| Secret SP | `fabric-agentic-key` (scadenza 2027-08-23) |

Lo SP interno `fabric-agentic-deploy` (`db9d4adb-db6a-4238-8e75-c69d21b1b37e`) ha il ruolo
`Key Vault Secrets User` sul vault. La Fabric Connection CRM esistente riferisce ancora uno SP
del tenant `d5e193bb-0b46-467d-9d95-03eb0d012c42`; va modificata o ricreata per usare lo SP
interno prima del prossimo run. Nessun secret viene versionato nel repository.

### 7.1 Connettori in fase 1

| # | Tipologia | Sorgente concreta | Note |
|---|---|---|---|
| 1 | **CRM / Dataverse** | **CRM demo Customer Insight Journeys** — entità `account` | Fabric Connection `CommonDataService`; chiave `accountid`, watermark `modifiedon` |
| 2 | **File** | **Anagrafica città sintetica** (~1.000 righe) CSV/Parquet su OneLake Files | Generata da noi, con coordinate geografiche |

Il dataset CRM è il tracer iniziale con dati demo/sintetici. L'anagrafica città File resta il
secondo connettore e la prova dell'astrazione; le join Silver sono un'evoluzione successiva.

### 7.2 Connettori previsti (fase 2)

Altro Lakehouse Fabric (shortcut) · Database / DWH · CRM (Dataverse) · SharePoint / Excel

### 7.3 Regole vincolanti

- Onboardare una nuova sorgente o un nuovo dataset è un'operazione di **configurazione
  dichiarativa**, non di scrittura di codice. Se un onboarding richiede codice nuovo, è il
  segnale che manca un'astrazione nel framework — va sollevato come rilievo, non aggirato.
- La logica di orchestrazione **non conosce** la tipologia di sorgente: la conosce solo il
  connettore.
- Ogni dataset dichiara esplicitamente in configurazione la modalità di carico
  (`full` o `incremental`) e, se incrementale, la watermark column.

> **Il secondo connettore è il vero test dell'architettura.** Con una sola sorgente qualsiasi
> framework sembra generico. Se aggiungere il connettore File richiede modifiche
> all'orchestrazione, il contratto va rivisto prima di andare avanti.

---

## 8. Ambiente

| Aspetto | Valore |
|---|---|
| Tenant Fabric | **Agic Dev** — `1cf6db06-3e00-48b6-a65c-be932526610e` |
| Sottoscrizione Azure | `898b6a78-11dd-4e23-bf53-9e17f541d955` |
| Capacity | **`fabricalessiodev`** |
| Nome progetto nel naming | **`agentic`** |
| Dev Agent app ID | `e74ca724-e306-4ff3-ae02-77ef7368e673` (`fabric-agentic-dev-agent`) |
| Dev Agent Azure DevOps credential | Certificato client non esportabile nel certificate store `CurrentUser\My`, thumbprint `89AB19F6EFD3CBE4CEB931F5E02A6833DD77E0F7`, registrato sull'app fino al 2027-08-21. Verificato token Entra per `https://app.vssps.visualstudio.com/.default` e lettura del progetto `fabric-agentic`; Az.Accounts usa il tenant domain `agicdev.onmicrosoft.com` |
| Dev Agent GitHub App | `fabric-agentic-dev-agent`, App ID `4672750`, Installation ID `155470382`; installata sul solo repository previsto. La private key PEM è in `%USERPROFILE%\.fabric-agentic\dev-agent\github-app-private-key.pem`, directory ACL limitata all'owner. Il provider locale ha verificato l'emissione di un installation token breve e lo scope del solo repository |
| Review Agent app ID | `a6d3e2af-92e5-447a-bb1e-9a466e1bdaed` (`fabric-agentic-review-agent`) |
| Review Agent GitHub App | `fabric-agentic-review-agent`, App ID `4735692`, Installation ID `156937328`; distinta dall'App del Dev Agent e installata sul solo repository previsto. Permessi verificati via API: `contents:read`, `issues:read`, `metadata:read`, `pull_requests:write`. La private key PEM è in `%USERPROFILE%\.fabric-agentic\review-agent\github-app-private-key.pem`, directory ACL limitata all'owner |
| Deploy app ID | `33e53b67-3872-4bc0-8d20-ed76a3c85ae7` (`fabric-agentic-deploy`); service principal senza secret, federated credential e Configured Connection Git predisposte. Assegnazione feature workspace verificata con il pattern IP: Azure RBAC `Contributor` sulla capacity e Object ID `db9d4adb-db6a-4238-8e75-c69d21b1b37e` in `properties.administration.members` |
| Workspace DEV | `ws_agentic_dev` — `abb3a689-6a8a-4a98-88da-b3f7c6de05c5`; ricreato il 2026-08-21 e assegnato a `fabricalessiodev` |
| Workspace TEST | `ws_agentic_test` — `782a3048-e181-4138-bb2c-e87f4c75f013`; creato il 2026-08-24 e assegnato alla capacity `fabricalessiodev` (`8626d394-40c1-4872-a1f1-25b8cfcbf6ad`), SKU F2 Active. Semantic Model `CRM Demo` creato: `c405057b-6ebe-4043-8126-a23d035fab33`; sviluppo Report PBIR sospeso come TODO futuro per errore renderer live |
| Ambienti non provisionati | Workspace `prod` e relative credenziali/configurazione restano non provisionati; nel workspace `test` il Semantic Model esiste, il Report resta TODO e manca la credenziale dedicata |
| Ruolo Dev Agent nel workspace DEV | `Viewer`; nessun ruolo sulla capacity; verificato dalla UI del workspace |
| Ruolo Deploy nel workspace DEV | `Contributor`; service principal `fabric-agentic-deploy`, verificato dalla UI del workspace |
| Ruolo Review Agent nel workspace DEV | Assente; nessun ruolo visibile nel workspace, verificato dalla UI |
| Federated credential OIDC | GitHub environment `dev`, subject con Organization ID `218064009` e Repository ID `1340835193`; test riuscito senza ruolo subscription |
| GitHub environments | `dev`, `test`, `prod` presenti; protection rules non disponibili sul piano GitHub Free |
| Governance Git | Branch dedicato obbligatorio, PR verso `main`, review e merge umano; vedi ADR-0010 |
| Rail `branch_out` | Workflow manuale `.github/workflows/pipe_agent_branch_out.yml`, avviato da `main`; accetta solo work item e slug, deriva `feature/wi-<id>-<slug>` e `ws_agentic_feature_wi<id>`, e pubblica l'artefatto `rail-result.json` v1.1 |
| Configurazione rail DEV | Configurate nell'environment `dev`: `FABRIC_DEPLOY_CLIENT_ID`, `FABRIC_DEPLOY_TENANT_ID`, `FABRIC_CAPACITY_ID`, `FABRIC_OWNER_OBJECT_ID`, `FABRIC_GIT_CONNECTION_ID` (`GitHubRepo`: `b0dc937b-99fa-46a2-9dd4-93940d57f075`), `FABRIC_GIT_ORGANIZATION`, `FABRIC_GIT_REPOSITORY`; sono tutti identificativi/configurazione, mai credenziali o segreti. La connection è condivisa con il deploy SP come `User` |
| Smoke rail `branch_out` | Run GitHub Actions `32487821272` del 2026-08-21: esito `success`, branch `feature/wi-6-smoke-branch-out`, workspace `ws_agentic_feature_wi6` (`c3465ab0-210b-4b31-86fd-03d9611fc037`), capacity assegnata, Git connesso e sincronizzato |
| Smoke rail `sync_workspace` | Run GitHub Actions `32488530726` del 2026-08-21: esito `success`, stesso work item/workspace, stato `already_aligned`, nessun item aggiornato e nessuna divergenza |
| Smoke dispatcher Dev Agent | Work item Azure Boards `#7` del 2026-08-21: il dispatcher ha verificato trigger, transizione `To Do` → `Doing` → `Done`, sessione Claude read-only e commento dell'identità `fabric-agentic-dev-agent`, senza toccare Fabric |
| Primo ticket agentico reale | ADR-0011: tracer bullet CRM `accounts` (entità `account`) in feature workspace. `ws_agentic_dev` è un prerequisito esistente, non un deliverable agente; `test` e `prod` restano fuori scope |
| Gate framework S1-00 | B3 confermato: la soluzione Agentic non contiene framework/configurazione metadata-driven. Il tracer CRM usa una tipologia supportata e la Fabric Connection `b838644d-afd9-4ec3-973d-e36ed85ad167`; nessun ticket prima di `PROVENANCE.md` e porting da fonte pulita |
| Framework CRM porting | Fonte pulita `fabric-universal-connector` commit `3303149c809172d0d320bfec353b5d81a`, registrata in `PROVENANCE.md`. Configurazione/schema/request builder sono presenti; staging, Bronze, audit, watermark e `run_load` restano da implementare |
| Watermark CRM `accounts` | ADR-0012: filtro `modifiedon >= watermark confermato`, merge Bronze su `accountid`, massimo `modifiedon` committato solo dopo Bronze e audit riusciti |
| Baseline KPI dispatcher | Due cicli idle il 2026-08-21: 0 task, 0 sessioni Claude e $0/0 token LLM; durate 9.985 s e 14.406 s. S1-05 registra KPI-7 a zero, KPI-6 con 0 difetti post-merge osservati e i gap di strumentazione in `docs/technical/10-retrospettiva-s1-04.md` |
| Identita' rail | L'OIDC del rail usa un service principal di deploy distinto dal Dev Agent; ha i soli privilegi necessari per feature workspace e capacity, mentre il Dev Agent puo' solo accodare il workflow e leggere l'artefatto |
| Runtime Dev Agent | Claude Code `2.1.228` installato nativamente su Windows, canale `stable`. Verificata sessione headless `claude -p` con esito `READY` il 2026-08-21; Azure DevOps non interattivo e GitHub App sono verificati. Resta il clone isolato prima del dispatcher completo |
| Identità | Un service principal per agente; nessun secret creato. Il workflow OIDC di test usa la `ExecutionCredential` configurata nell'environment GitHub `dev` |
| Dati | Esclusivamente sintetici o open data. **Nessun dato di cliente entra nel perimetro** |

---

## 9. Principi non negoziabili

1. **Il merge su `main` è umano.** Sempre. Nessuna eccezione per tipologia di modifica.
2. **Nessuna PR su codice non eseguito.** Il carico gira davvero nel feature workspace prima
   dell'apertura della PR, e l'evidenza viene allegata.
3. **I permessi, non le istruzioni, definiscono il perimetro.** Ciò che un agente può
   tecnicamente fare, prima o poi lo farà.
4. **Gli agenti non si parlano direttamente.** Ogni scambio passa da un artefatto tracciabile:
   commento su ticket, commento su PR, voto.
5. **Chi scrive non rivede.** Dev Agent e Review Agent sono di vendor e modello diversi.
6. **Le regole di qualità dato vivono nel framework**, non nelle istruzioni dell'agente.
   L'agente ne cita l'esito, non le reimplementa.
7. **Ogni affermazione sulla piattaforma Fabric va verificata sulla documentazione ufficiale**
   prima di essere dichiarata.
8. **In caso di ambiguità l'agente si ferma e chiede.** Non tira a indovinare.
9. **Nessun segreto nel repo.** Né nei notebook, né nelle definizioni di data pipeline, né nella
   configurazione degli agenti.
10. **La documentazione si aggiorna nella stessa PR della modifica.** È un criterio bloccante
    di review.
11. **Il rail invoca una pipeline CI/CD ancorata a `main`.** Il branch di feature è un
    *parametro*, mai la definizione della pipeline. Diversamente l'agente, riscrivendo lo YAML
    sul proprio branch, otterrebbe i privilegi della pipeline senza violare alcun permesso.
12. **L'ambiente di destinazione non è un parametro accessibile agli agenti.** Le pipeline
    agentiche puntano a un solo ambiente non produttivo. La produzione richiede una pipeline
    distinta, che gli agenti non possono accodare.
13. **L'esito di un'esecuzione si legge dall'artefatto della pipeline**, non interrogando
    Fabric. L'accesso diretto a Fabric è un canale di **eccezione diagnostica**, in sola
    lettura, e solo su ambienti con dati non riservati.
