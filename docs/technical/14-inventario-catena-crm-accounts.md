# 14 — Inventario della catena CRM `accounts`

> Fotografia verificata della catena `accounts`: dove vive ogni anello, quale evidenza lo sostiene
> e quali discrepanze sono emerse fra ciò che la documentazione dichiarava e ciò che il repository
> contiene davvero.

| Campo | Valore |
|---|---|
| Work item | #158 (padre #150) |
| Data | 2026-09-01 |
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
| 10 | Rail `run_load` su Fabric | `scripts/fabric_crm_load.py` + `.github/workflows/pipe_agent_crm_run_load.yml` | Documentale |
| 11 | Contratto dell'artefatto | `schemas/rail-result-v1.3.json` | Verificato |
| 12 | Run reale iniziale, secondo run idempotente, delta controllato | — | Non verificabile |
| 13 | Verifica SQL e confronto con le evidenze sorgente | — | Non verificabile |

**Evidenza documentale degli anelli 10 e 12**: i run GitHub Actions `32648577263` e `32648994929`
del 2026-08-23 risultano registrati in `../sources/crm_demo.md` con `loaded_count=5`,
`total_destination_count=10`, PK e riconciliazione superate e watermark `2026-08-21T17:39:25Z`.
Sono citati come stato riportato: questa sessione non li ha ri-eseguiti né riletti dall'artefatto.

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

### 3.2 Rilevate e **non** corrette qui

| # | Discrepanza | Perché non corretta ora |
|---|---|---|
| **D8** | `reconciliation` è **asserita, non calcolata**. Sia `scripts/run_load.py` sia `nb_crm_load` scrivono `"reconciliation": "passed"` come letterale: nessuno dei due confronta il conteggio letto dalla sorgente con quello effettivamente messo in staging e fuso in Bronze. Il contratto in `03-rail-script.md` §4 richiede invece «conteggi riconciliati» perché l'esito sia `success` | La correzione tocca il percorso di carico. Il principio 2 di `CONTEXT.md` vieta di aprire una PR su codice di carico che non è stato realmente eseguito, e questa sessione non può eseguirlo |
| **D9** | L'evidenza letta da `scripts/fabric_crm_load.read_load_result` proviene da un percorso OneLake fisso (`Files/agentic/run_load_result.json`) sovrascritto a ogni run e **non è legata al run appena sottomesso**. Se il job notebook risultasse riuscito senza riscrivere il file, il rail ripubblicherebbe i conteggi del run precedente come evidenza di questo | Stessa ragione di D8 |

> D8 e D9 non sono ipotesi da confermare: si leggono direttamente nel codice citato. Sono
> deliberatamente lasciate aperte perché la loro correzione va validata da un run reale, non da un
> test.

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
| Run iniziale, secondo run idempotente e delta controllato eseguiti realmente | **Bloccato B4** |
| Verifica SQL e confronto con le evidenze sorgente | **Bloccato B4** |

I quattro criteri «soddisfatti nel codice» restano tali: sono verificati da test deterministici e
da guard di CI, **non** da un carico eseguito. La promozione a verificato sul campo richiede i due
criteri bloccati.

---

## 5. Cosa serve per chiudere i due criteri bloccati

Nell'ordine, e con l'identità che li può eseguire:

1. Accodare `pipe_agent_crm_run_load` sul work item 158 dopo `branch_out` — oggi eseguibile solo
   dall'owner o da una sessione con `gh workflow run` nell'envelope.
2. Rieseguirlo subito dopo, senza modifiche, per il secondo run idempotente.
3. Eseguire un delta controllato modificando un solo record CRM demo e rilanciando.
4. Leggere i tre `rail-result.json` come unica fonte di verità dell'esito (principio 13 di
   `CONTEXT.md`), poi confrontare `crm_demo_accounts`, `crm_demo_load_audit` e
   `crm_demo_watermark` con i conteggi sorgente.
5. Correggere D8 e D9 nello stesso ciclo, perché è l'unico in cui la correzione può essere provata.

Finché il punto 1 non è possibile da una sessione dispatchata, il ciclo richiede un intervento
tecnico umano — che `../functional/01-ciclo-di-vita-ticket.md` §1 impone di tracciare come
**difetto del sistema**, non di assorbire in silenzio.
