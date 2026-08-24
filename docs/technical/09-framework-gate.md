# 09 - Framework gate

> Verifica B3 prima del primo ticket agentico dati.

---

## 1. Verifica 2026-08-21

Il clone isolato della soluzione Agentic non contiene le superfici richieste dal runbook di
onboarding:

| Percorso / artefatto | Esito |
|---|---|
| `configuration/` | Assente |
| `fabric/` | Assente |
| `pipelines/` | Assente |
| configurazione CRM | Assente |
| runtime o dipendenze ingestion | Assenti |

Il framework locale candidato è `fabric-universal-connector`, commit
`3303149c809172d0d320bfec353b5d81d9f7a81a`. Il worktree principale contiene modifiche non
committate, ma è stato creato un worktree detached e pulito sul commit indicato: è la fonte
riproducibile registrata in `PROVENANCE.md`.

## 2. Compatibilità del connettore

Il framework candidato include connettori Dataverse/CRM, Business Central e SQL. Non include un
connettore REST generico o Open-Meteo. L'owner ha quindi scelto il tracer CRM `account`, che usa
una tipologia già supportata e la Fabric Connection `b838644d-afd9-4ec3-973d-e36ed85ad167`.

## 3. Esito

Classificazione: **B3 - astrazione mancante**.

Il Dev Agent non deve creare configurazione, notebook o pipeline ad hoc per aggirare il gate.
S1-04 resta bloccato da S1-00: il framework CRM deve essere portato nella soluzione con
provenienza riproducibile prima dell'onboarding.

## 4. Decisione richiesta

Decisione chiusa: il tracer usa CRM `account` con chiave `accountid` e watermark `modifiedon`.
La fonte CRM deve restare demo/sintetica. S1-00 richiede `PROVENANCE.md` e un commit pulito del
framework, secondo ADR-0009, prima di copiare codice o configurazione.

## 5. Porting iniziale

Il primo slice di S1-00 ha creato nel repository Agentic:

- `PROVENANCE.md` con commit e divergenze dalla fonte;
- `configuration/crm_demo.json` e `schemas/crm-source-v1.0.json`;
- validator fail-fast e builder OData `modifiedon` in `scripts/crm_framework.py`;
- inventario `docs/sources/crm_demo.md`;
- collocazioni versionate per futuri notebook e pipeline in `fabric/`;
- notebook FabricGitSource `nb_crm_preflight`, validato localmente senza esecuzione CRM.

Il runtime locale è ora eseguibile per il tracer: `scripts/crm_load.py` implementa estrazione
staged JSONL, PK check, merge Bronze idempotente, audit per run e watermark post-audit; il rail
`scripts/run_load.py` produce `rail-result` v1.0. Il notebook Fabric `nb_crm_load`, il deployer
OIDC e il workflow `crm-run-load` sono ora versionati e limitati a `dev`. S1-04 resta bloccato
fino alla prova sul feature workspace.

La semantica del watermark CRM è definita in ADR-0012: filtro inclusivo, merge su `accountid` e
avanzamento solo dopo Bronze e audit riusciti. I notebook/pipeline futuri devono implementare
questa sequenza senza fallback append.

## 6. Preflight deployabile

Il workflow manuale `.github/workflows/crm-preflight.yml` usa l'identità OIDC di deploy su
`dev`, deriva il feature workspace dal work item e crea/riusa `lh_bronze_crm_demo` e
`nb_crm_preflight`. Avvia il job con `RunNotebook` e pubblica `crm-preflight-result.json`.
Il notebook esegue una richiesta CRM `$top=0`; non legge righe account e non espone credenziali.
L'esecuzione sul workspace resta la verifica successiva al merge.

Il workflow invoca il deployer come modulo Python e garantisce un risultato tecnico strutturato
anche se il processo non riesce ad avviarsi, così l'artifact rimane il canale di diagnosi primario.

### Esito operativo 2026-08-21

Il run GitHub Actions `32499002240`, sul commit `b1d47e26efd943334184640a4dd708bfc48c3731`,
ha completato il preflight con `outcome: success` per il work item `6`. Nel feature workspace
`c3465ab0-210b-4b31-86fd-03d9611fc037` il deployer ha creato o riusato:

- Lakehouse `lh_bronze_crm_demo`: `742c052b-6b30-4dd1-bcec-94908dc670cd`;
- notebook `nb_crm_preflight`: `898df1af-7e9e-437e-aba3-ca8966404392`.

Il notebook ha completato la verifica OData `$top=0` sull'entity set `accounts` tramite la
connection CRM configurata. L'evidenza non contiene record CRM, token o altri segreti.

Il preflight rimuove il blocco di compatibilità della connection per S1-00. Il run reale del
2026-08-23 ha verificato OIDC, deploy e job `RunNotebook`, ma non ha prodotto tabelle visibili: il
notebook esistente era stato riusato senza binding al Lakehouse. Il deployer ora aggiorna sempre
la definizione con il Lakehouse dinamico prima del run; resta necessaria una riesecuzione end-to-end
con verifica SQL di staging, Bronze, audit e watermark. S1-04 rimane bloccato fino a quella prova.

### Esito operativo 2026-08-23 — run CRM `32648577263`

Il run sul commit `f0ca7b6d7c6d440531ffea13d225382ab1169977` è terminato con successo dopo il
passaggio al secret Key Vault diretto e al nuovo ambiente `org12202591`. Nel Lakehouse
`lh_bronze_crm_demo` del feature workspace `c3465ab0-210b-4b31-86fd-03d9611fc037` sono presenti
le tabelle `crm_demo_accounts`, `crm_demo_load_audit` e `crm_demo_watermark`.

Questo chiude la verifica di materializzazione tecnica. Il notebook scrive anche l'evidenza
aggregata in `Files/agentic/run_load_result.json`; il deployer la recupera per valorizzare il
`rail-result` con conteggi, PK, riconciliazione e watermark.

### Evidenza quantitativa fornita dall'esecuzione

La verifica delle tabelle ha rilevato 10 record in `crm_demo_accounts`, una riga in
`crm_demo_load_audit` e una riga in `crm_demo_watermark`. Il prossimo run deve confermare che
questi valori siano presenti anche nel `rail-result` pubblicato.

### Esito rail con evidenza aggregata — run `32648994929`

Il run post-merge sul commit `5c8ca12f46107603d6a1d4465207b5439bcbef16` ha pubblicato un
`rail-result` completo: `loaded_count=5`, `total_destination_count=10`, `pk_check=passed`,
`reconciliation=passed` e watermark `2026-08-21T17:39:25Z`. Nel carico incrementale il valore 5
è il delta estratto, mentre 10 è il totale Bronze dopo il merge; il contratto dovrà distinguere
esplicitamente conteggio caricato e totale destinazione per evitare ambiguità. La versione v1.3
del contratto formalizza questa distinzione.
## 8. S1-01 — Spike Power BI

Il workspace `ws_agentic_test` è stato creato il 2026-08-24. Nel workspace è stato creato il
Semantic Model `CRM Demo` (`c405057b-6ebe-4043-8126-a23d035fab33`) in Direct Lake verso il
Lakehouse `lh_bronze_crm_demo`. La validazione locale del Report PBIR ha prodotto 0 errori.

L'import del Report tramite Fabric Items REST API non è riuscito: il servizio ha restituito
`Report_Import_FailedToImportReport` con un errore sulla risoluzione dello schema/versione di
`version.json`. La verifica read-only successiva conferma che nel workspace è presente solo il
Semantic Model e nessun Report. La pubblicazione del Report è stata assegnata manualmente
all'utente. S1-01 resta quindi parzialmente completato fino alla pubblicazione e alla verifica
`byConnection`.

### Blocco `Missing_References` — 2026-08-24

Desktop ha restituito `Missing_References` durante il caricamento delle visuali PBIR. La
definition del Semantic Model live non è interrogabile tramite gli endpoint disponibili e non ha
refresh registrati; per evitare riferimenti dati non verificati, le visuali pre-associate sono
state rimosse. Il report mantiene il binding `byConnection` e si apre senza dipendere da query
PBIR locali; le visuali vanno ricreate in Desktop dopo la verifica del modello remoto.

I metadata PBIR sono ora allineati agli schema supportati: `version.json` usa
`versionMetadata/1.0.0` e `pages/pages.json` usa `pagesMetadata/1.0.0`. Il validator locale
restituisce `succeeded`, con 0 errori e 0 warning.
Il contenuto di `version.json` è `1.0.0`; `definition.pbir` mantiene `4.0` perché sono versioni
di file differenti.
Il manifest `CRM Demo.pbip` include inoltre lo schema ufficiale
`fabric/pbip/pbipProperties/1.0.0`, necessario per evitare il parsing legacy della proprietà
`version`.
La versione dello shortcut è `1.0`, compatibile con la build Desktop August 2026; non va confusa
con `definition.pbir` a versione `4.0`.
La versione di `definition/version.json` è `4.0.0`, necessaria perché il report usa il formato PBIR
con cartella `definition/`; usare `1.0.0` fa ignorare i visual containers e rompe il rendering.

### Correzione apertura PBIP — 2026-08-24

Power BI Desktop rifiutava `powerbi/CRM Demo.pbip` perché il manifest dichiarava un secondo
artifact `dataset`. Il formato PBIP del Desktop richiede un solo artifact `report`; il semantic
model resta collegato dal `datasetReference` in `definition.pbir`. La validazione del Report ora
restituisce 0 errori; restano solo warning per schemi remoti non raggiungibili.
### Correzione schema `.platform` — 2026-08-24

Power BI Desktop ha poi rifiutato il progetto perché i file `.platform` usavano lo schema
`item/platformProperties`. Entrambi sono stati aggiornati al formato Git Integration
`gitIntegration/platformProperties/2.0.0/schema.json`, richiesto dal PBIP/PBIR corrente.
La versione dell'artifact è valorizzata dentro `config.version`; una proprietà `version` alla
radice viene rifiutata da Power BI Desktop.

Il successivo errore su `definition.pbism` è stato corretto rimuovendo
`defaultPowerBIDataSourceVersion` da quel file: la proprietà resta nel `model.tmdl`, mentre
`definition.pbism` contiene solo `version`.

### Binding live al Semantic Model — 2026-08-24

Il report usa ora `datasetReference.byConnection` in `definition.pbir` verso il Semantic Model
`CRM Demo` (`c405057b-6ebe-4043-8126-a23d035fab33`) nel workspace `ws_agentic_test`
(`782a3048-e181-4138-bb2c-e87f4c75f013`). Il binding live evita che Desktop apra il modello locale
in full edit mode; la connessione usa `pbiServiceXmlaStyleLive`.
