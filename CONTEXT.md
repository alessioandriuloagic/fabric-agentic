# CONTEXT.md — Glossario di dominio e convenzioni

> **Questo documento è vincolante.** È il *shared context* che Dev Agent e Review Agent
> leggono all'inizio di ogni sessione. Ciò che non è scritto qui non è una convenzione:
> è un'improvvisazione, e in code review va segnalata come rilievo.
>
> Fonte di verità: questo file nel repo. La wiki del tracker è **generata** da qui.

| Campo | Valore |
|---|---|
| Versione | 0.7 |
| Ultimo aggiornamento | 2026-08-21 |
| Documenti collegati | `docs/prd/PRD-agentic-cicd-fabric.md`, `docs/adr/` |

---

## 1. Glossario dei ruoli agentici

| Termine | Definizione |
|---|---|
| **Dev Agent** | Agente AI che esegue il ciclo di sviluppo end-to-end su un work item: branch, feature workspace, implementazione, test reale, documentazione, apertura PR. **Non merge mai.** |
| **Review Agent** | Agente AI, di vendor diverso, che revisiona la PR contro una checklist chiusa. **Non scrive codice di feature, non merge.** Non ha accesso a Fabric. |
| **Dispatcher** | Script deterministico in polling sul tracker. Rileva i trigger e avvia una sessione fresca dell'agente. **Non usa LLM**: da fermo il costo è zero. |
| **Rail (script deterministico)** | Script versionato che esegue un'operazione procedurale ripetitiva al posto dell'LLM. Gli agenti orchestrano, i rail eseguono. Nel nostro caso **un rail invoca una pipeline CI/CD**, non chiama direttamente le API |
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
| Data Pipeline | `pl_` | `pl_ingest_open_meteo_bronze` |
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
| Source system | `snake_case`, singolare | `open_meteo`, `city_registry` |
| Dataset | `snake_case`, plurale | `daily_weather`, `cities` |
| File di configurazione | `configuration/<source_system>.json` | `configuration/open_meteo.json` |
| Tabella bronze | `<source_system>_<dataset>` | `open_meteo_daily_weather`, `city_registry_cities` |
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
| Branch feature | `feature/wi-<id>-<slug>` | `feature/wi-42-onboard-open-meteo-daily` |
| Branch di release | `chore/release-v<x.y.z>` | `chore/release-v0.2.0` |
| Commit | Conventional Commits | `feat(bronze): onboard open_meteo daily_weather` |
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

### 7.1 Connettori in fase 1

| # | Tipologia | Sorgente concreta | Note |
|---|---|---|---|
| 1 | **REST API** | **Open-Meteo** — archivio storico meteo | Nessuna autenticazione, watermark naturale su data, chiamate parametriche per coordinate |
| 2 | **File** | **Anagrafica città sintetica** (~1.000 righe) CSV/Parquet su OneLake Files | Generata da noi, con coordinate geografiche |

I due dataset sono **correlati**: le coordinate dell'anagrafica città si agganciano alle
rilevazioni meteo e abilitano la join nel layer silver.

> L'anagrafica città è la **dimensione** della join, non il driver delle chiamate REST.
> L'estrazione parametrizzata sulla tabella città è un'evoluzione da decidere con ADR.

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
| Review Agent app ID | `a6d3e2af-92e5-447a-bb1e-9a466e1bdaed` (`fabric-agentic-review-agent`) |
| Deploy app ID | `33e53b67-3872-4bc0-8d20-ed76a3c85ae7` (`fabric-agentic-deploy`); service principal senza secret, federated credential e Configured Connection Git predisposte. Per assegnare feature workspace alla capacity deve essere **Capacity administrator nel portale Fabric**; Azure RBAC `Contributor` non basta |
| Workspace DEV | `ws_agentic_dev` — `abb3a689-6a8a-4a98-88da-b3f7c6de05c5`; ricreato il 2026-08-21 e assegnato a `fabricalessiodev` |
| Ruolo Dev Agent nel workspace DEV | `Contributor`; nessun ruolo sulla capacity |
| Federated credential OIDC | GitHub environment `dev`, subject con Organization ID `218064009` e Repository ID `1340835193`; test riuscito senza ruolo subscription |
| GitHub environments | `dev`, `test`, `prod` presenti; protection rules non disponibili sul piano GitHub Free |
| Governance Git | Branch dedicato obbligatorio, PR verso `main`, review e merge umano; vedi ADR-0010 |
| Rail `branch_out` | Workflow manuale `.github/workflows/branch-out.yml`, avviato da `main`; accetta solo work item e slug, deriva `feature/wi-<id>-<slug>` e `ws_agentic_feature_wi<id>`, e pubblica l'artefatto `rail-result.json` v1.1 |
| Configurazione rail DEV | Configurate nell'environment `dev`: `FABRIC_DEPLOY_CLIENT_ID`, `FABRIC_DEPLOY_TENANT_ID`, `FABRIC_CAPACITY_ID`, `FABRIC_OWNER_OBJECT_ID`, `FABRIC_GIT_CONNECTION_ID` (`GitHubRepo`: `b0dc937b-99fa-46a2-9dd4-93940d57f075`), `FABRIC_GIT_ORGANIZATION`, `FABRIC_GIT_REPOSITORY`; sono tutti identificativi/configurazione, mai credenziali o segreti |
| Identita' rail | L'OIDC del rail usa un service principal di deploy distinto dal Dev Agent; ha i soli privilegi necessari per feature workspace e capacity, mentre il Dev Agent puo' solo accodare il workflow e leggere l'artefatto |
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
