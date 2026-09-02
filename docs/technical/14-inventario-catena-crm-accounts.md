# 14 — Inventario della catena CRM `accounts`

> Fotografia verificata della catena `accounts`: dove vive ogni anello, quale evidenza lo sostiene
> e quali discrepanze sono emerse fra ciò che la documentazione dichiarava e ciò che il repository
> contiene davvero.

| Campo | Valore |
|---|---|
| Work item | #158 (padre #150) |
| Data | 2026-09-02 |
| Documenti collegati | `../adr/ADR-0012-watermark-crm-account.md`, `03-rail-script.md`, `../sources/crm_demo.md` |

---

## 1. Metodo e limite dichiarato

L'inventario è stato prodotto **leggendo gli artefatti versionati** ed eseguendo la suite di test
del repository. Le affermazioni sono classificate in tre modi, e la classe non va mai promossa:

| Classe | Significato |
|---|---|
| **Verificato** | Osservato in questa sessione, su codice o test eseguiti |
| **Documentale** | Riportato da un run precedente registrato nella documentazione, non ri-osservato qui |
| **Non verificabile** | Richiede un accesso che la sessione non ha |

> **Metà Fabric dell'inventario: non verificabile.** Una sessione Dev Agent avviata dal dispatcher
> non può accodare un workflow (`gh workflow run`), scaricarne l'artefatto, né leggere Fabric o
> OneLake: l'envelope è `DEV_AGENT_ALLOWED_TOOLS` in `scripts/dev_dispatcher.py`. L'inventario
> degli item realmente presenti nel feature workspace e i conteggi delle tabelle Delta **non**
> fanno quindi parte di questo documento. È un blocco B4 secondo
> `../functional/05-protocollo-escalation.md`, non un percorso da aggirare.

---

## 2. Inventario per anello della catena

| # | Anello | Artefatto | Classe |
|---|---|---|---|
| 1 | Configurazione dichiarativa | `configuration/crm_demo.json`, validata fail-fast contro `schemas/crm-source-v1.0.json` | Verificato |
| 2 | Costruzione della request incrementale | `scripts/crm_framework.build_accounts_request` sopra `fabric_agentic/connectors.plan_request` | Verificato |
| 3 | Staging persistito per run — locale | `scripts/crm_load.extract_accounts`, un file JSONL per `run_id` | Verificato |
| 4 | Staging persistito per run — Fabric | `nb_crm_load.write_staging` → `Files/raw/crm_demo/accounts/<run_id>` | Verificato (codice) |
| 5 | PK check prima di ogni scrittura | `crm_load._validate_unique_keys`; nel notebook il conteggio dei duplicati precede ogni `write` | Verificato (codice) |
| 6 | Merge Bronze idempotente su `accountid` | `crm_load.load_staged_accounts`; nel notebook `DeltaTable.merge` con `whenMatchedUpdateAll` | Verificato (codice) |
| 7 | Audit unico per `run_id` | `crm_load` riscrive la riga dello stesso `run_id`; nel notebook merge su `target.run_id` | Verificato (codice) |
| 8 | Watermark committato solo dopo Bronze e audit | Ordine di scrittura in `crm_load.load_staged_accounts` e nel notebook, con guard di regressione in `tests/test_fabric_crm_load_artifact.py` | Verificato |
| 9 | Rail `run_load` locale | `scripts/run_load.py` | Verificato |
| 10 | Rail `run_load` su Fabric | `scripts/fabric_crm_load.py` + `.github/workflows/pipe_agent_crm_run_load.yml`; run `33643834028`, `33646578126` | Verificato sul campo |
| 11 | Contratto dell'artefatto | `schemas/rail-result-v1.3.json` | Verificato |
| 12 | Run reale iniziale, secondo run idempotente, delta controllato | Run iniziale `33643834028`; secondo run `33646578126`; delta da eseguire | Parziale — verificato sul campo |
| 13 | Verifica SQL e confronto con le evidenze sorgente | SQL endpoint del Lakehouse feature: Bronze, audit e watermark verificati; benchmark sorgente `10` | Verificato sul campo |

**Evidenza documentale degli anelli 10 e 12**: i run GitHub Actions `32648577263` e `32648994929`
del 2026-08-23 risultano registrati in `../sources/crm_demo.md` con `loaded_count=5`,
`total_destination_count=10`, PK e riconciliazione superate e watermark `2026-08-21T17:39:25Z`.
Sono citati come stato riportato: questa sessione non li ha ri-eseguiti né riletti dall'artefatto.

**Evidenza sul campo del 2026-09-02**: il preflight `33643527753` ha completato con `success`
nel workspace `ws_agentic_feature_wi158`; il notebook ha restituito `source_count=10`. Il load
iniziale `33643834028` ha restituito `loaded_count=10`, `total_destination_count=10`, `pk_check`
e `reconciliation` `passed`, con watermark `2026-08-21T17:39:25Z`. Il secondo load
`33646578126` ha restituito `loaded_count=5`, totale Bronze invariato a `10`, stessi controlli
passati e watermark invariato. Il batch di cinque record è la riestrazione inclusiva prevista da
ADR-0012 al confine del watermark; il merge su `accountid` ha impedito duplicati.

**Verifica SQL sul campo del 2026-09-02**: sul database `lh_bronze_crm_demo`, `crm_demo_accounts`
contiene `10` righe e `10` `accountid` distinti; la query duplicati non restituisce righe. Audit
contiene i run `20260902T144322Z-bb0290c4` (`extracted_count=10`, `loaded_count=10`,
`destination_count=10`) e `20260902T150838Z-a37c2cde` (`extracted_count=5`,
`loaded_count=5`, `destination_count=10`), entrambi `passed` e con watermark
`2026-08-21T17:39:25Z`. `crm_demo_watermark` contiene due commit con lo stesso watermark.

---

## 3. Discrepanze rilevate

### 3.1 Corrette in questa PR

| # | Discrepanza | Perché contava |
|---|---|---|
| **D1** | Il risultato di fallimento di `scripts/run_load.py` dichiarava `schema_version: "1.0"` ma portava i campi dataset della v1.3 (`loaded_count`, `total_destination_count`). Non validava contro **nessuno** dei due schemi | È esattamente il caso `quality_failure` su cui poggia l'escalation B2: il PK check fallisce e il rail pubblica un artefatto che il Review Agent non può validare |
| **D2** | L'artefatto di fallback del workflow (`Ensure rail result exists`) dichiarava `schema_version: "1.0"` con `workspace_id: null`, che la v1.0 vieta (`type: string`, `minLength: 1`) | È l'artefatto prodotto proprio quando il rail muore prima di scriverne uno: il caso in cui l'evidenza serve di più |
| **D3** | `scripts/validate_rail_result_schema.py` validava solo v1.0, v1.1 e v1.2. Il rail `run_load` emette v1.3, quindi il suo contratto non aveva alcun guard | Un contratto senza guard è una convenzione, non un vincolo |
| **D4** | `validate-rail-contract.yml` non elencava `pipe_agent_crm_run_load.yml` fra i path di innesco: il workflow del rail poteva cambiare senza far girare la validazione del contratto | Stessa classe di D3: il guard esisteva ma non veniva raggiunto |
| **D5** | I test che presidiano i criteri 2-6 (`test_crm_load.py`, `test_run_load.py`, `test_fabric_crm_load.py`, `test_fabric_crm_load_artifact.py`) non erano nell'elenco `unittest` della CI, pur essendo `scripts/**` e `fabric/notebook/**` path di innesco | Il guard sull'ordine staging → Bronze → audit → watermark non girava in CI |
| **D6** | `scripts/fabric_crm_load.py` ripeteva `schema_version` due volte nello stesso dict literal | Nessun effetto a runtime; rimosso perché segnala una modifica non riletta |
| **D7** | Deriva documentale: `../sources/crm_demo.md` dichiarava un risultato «v1.0» e conteneva due paragrafi in contraddizione sui conteggi in `rail-result.json`; `03-rail-script.md` §4b dava la v1.0 come normativa per `run_load`; `CONTEXT.md` affermava che staging, Bronze, audit, watermark e `run_load` «restano da implementare» | Il Dev Agent successivo legge questi documenti come contesto vincolante e reimplementerebbe ciò che esiste già |

### 3.2 Corrette, da validare nel delta controllato

| # | Discrepanza | Correzione |
|---|---|---|
| **D8** | `reconciliation` era asserita, non calcolata. | Il runner locale confronta `extracted_count` e `loaded_count`; il notebook confronta la sorgente estratta con lo staging riletto. Una divergenza restituisce `quality_failure` e non procede a merge, audit o watermark. |
| **D9** | L'evidenza proveniva da un percorso OneLake fisso e non era legata al job appena sottomesso. | Il rail genera `run_id` prima del job, lo passa come parametro al notebook e legge solo `Files/agentic/run_load_results/<run_id>.json`, verificando anche il `run_id` nel payload. Gestisce soltanto un 404 OneLake transitorio con retry bounded sullo stesso file. |

> Le correzioni D8/D9 sono verificate da test; il prossimo delta controllato le valida nel runtime
> Fabric con una prova di evidenza per-run.

---

## 4. Stato dei criteri di accettazione di #158

| Criterio | Stato |
|---|---|
| Inventario repo/Fabric e discrepanze documentate | **Parziale** — metà repo completa (§2, §3); metà Fabric non verificabile (§1) |
| Staging persistito per run | **Soddisfatto** nel codice (anelli 3-4) |
| `accountid` verificato univoco prima della scrittura | **Soddisfatto** nel codice (anello 5) |
| Merge Bronze idempotente | **Soddisfatto** nel codice (anello 6) |
| Audit unico per `run_id` | **Soddisfatto** nel codice (anello 7) |
| `modifiedon` avanza solo dopo Bronze e audit riusciti | **Soddisfatto** nel codice (anello 8), con guard in CI da D5 |
| Run iniziale, secondo run idempotente e delta controllato eseguiti realmente | **Parziale** — iniziale e idempotenza verificate; delta controllato da eseguire |
| Verifica SQL e confronto con le evidenze sorgente | **Soddisfatto** — benchmark sorgente `10`, artefatti e SQL Bronze/audit/watermark coerenti |

I quattro criteri «soddisfatti nel codice» restano tali: sono verificati da test deterministici e
da guard di CI. I due run e la verifica SQL sul campo confermano il comportamento iniziale e
idempotente; resta da eseguire il delta controllato.

---

## 5. Cosa serve per chiudere i due criteri bloccati

Nell'ordine, e con l'identità che li può eseguire:

1. Eseguire un delta controllato modificando un solo record CRM demo e rilanciando il rail.
2. Leggere il terzo `rail-result.json` e verificare con SQL `crm_demo_accounts`,
   `crm_demo_load_audit` e `crm_demo_watermark` il solo aggiornamento previsto.
3. Verificare che il percorso di evidenza sia `Files/agentic/run_load_results/<run_id>.json` e che
    il `run_id` dell'artefatto coincida con quello del rail.

Finché il punto 1 non è possibile da una sessione dispatchata, il ciclo richiede un intervento
tecnico umano — che `../functional/01-ciclo-di-vita-ticket.md` §1 impone di tracciare come
**difetto del sistema**, non di assorbire in silenzio.
