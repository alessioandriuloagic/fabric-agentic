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

Il framework non è ancora eseguibile: mancano estrazione staged, merge Bronze, audit, watermark,
deploy OIDC del notebook, Lakehouse target e rail `run_load`. S1-04 resta bloccato fino a questi
artefatti.

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