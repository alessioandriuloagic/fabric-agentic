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
