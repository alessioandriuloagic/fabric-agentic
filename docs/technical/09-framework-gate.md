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
- collocazioni versionate per futuri notebook e pipeline in `fabric/`.

Il framework non è ancora eseguibile: mancano estrazione staged, merge Bronze, audit, watermark,
notebook/pipeline Fabric e rail `run_load`. S1-04 resta bloccato fino a questi artefatti.