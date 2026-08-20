# ADR-0001 — Isolamento della capacity per i feature workspace

| Campo | Valore |
|---|---|
| Stato | **Proposto** — richiede decisione dell'owner prima dello Slice 1 |
| Data | 2026-08-20 |
| Autore | Ralph (Fabric Solution Architect) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §2 · chiude Q-5 · rischio R-4, R-11 |
| Decisori | Owner · @mike (FinOps) |

---

## Contesto

Il design prevede che ogni work item generi un **feature workspace Fabric temporaneo** in cui il
Dev Agent esegue realmente il carico (RF-13, RF-21). Il tenant AGIC dispone di una sola capacity
**F32**, sulla quale sono previsti anche `ws_agentic_dev` e `ws_agentic_prod`.

L'assunzione A-2 del PRD («il volume dei feature workspace è sostenibile sulla F32 senza impatto
sui carichi esistenti») è stata verificata e risulta **vera sul volume, falsa sull'isolamento**.

Fatti verificati su documentazione ufficiale Microsoft (2026-08-20):

- F32 = 32 CU; per Spark, 1 CU = 2 Spark VCore → **64 VCore base, 192 con burst 3×**, coda 32.
- Il **throttling è applicato a livello di capacity**, non di workspace.
- Lo **smoothing** dei job background distribuisce il consumo su **24 ore**.
- Se la capacity è in stato di throttling, i **job Spark vengono rifiutati**, non accodati.

Il consumo generato dai feature workspace è marginale in termini di CU-ora (stima: un carico da
16 VCore per 10 minuti ≈ 1,33 CU-ora su un budget di 768 CU-ora/giorno). Il problema non è il
volume: è che **un difetto dell'agente degrada la produzione**, e che per effetto dello smoothing
il degrado si manifesta fino a 24 ore dopo la causa, rendendolo difficile da attribuire.

## Decisione

**I feature workspace non condividono la capacity con i workspace di produzione.**

Attuazione in due tempi, per non bloccare l'avvio del progetto:

**Fase 1 (laboratorio interno, dati sintetici) — rischio accettato con contromisure**
La F32 resta condivisa, ma con tre limiti imposti da script e non da istruzioni:

1. tetto rigido di **5 feature workspace esistenti** contemporaneamente; il rail *Branch out*
   rifiuta la creazione del sesto ed escala;
2. il rail *Run load* esegue **sempre tramite pipeline**, mai con chiamata diretta all'API del
   notebook, perché i job avviati da pipeline vengono accodati mentre quelli avviati via API del
   notebook vengono rifiutati;
3. monitoraggio con soglie di allarme: email alert su Capacity Overview Events e allarme a
   qualunque occorrenza della fascia di ritardo interattivo in giornate senza carichi di
   produzione pianificati.

**Fase 2 (istanziazione su cliente, RF-80) — isolamento obbligatorio**
Al primo utilizzo su un progetto cliente, i feature workspace vengono assegnati a una **capacity
distinta** da quella di produzione. La condizione di attivazione è l'istanziazione su cliente, non
una soglia di consumo.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Capacity dedicata (es. F2) fin dalla fase 1** | Costo non giustificato per un laboratorio interno su dati sintetici, dove la "produzione" da proteggere è essa stessa una demo. Diventa obbligatoria in fase 2 |
| **Autoscale Billing for Spark sulla F32** | Tecnicamente elegante: sposta lo Spark fuori dalla capacity in pay-as-you-go, eliminando alla radice il rischio di throttling. Ma disattiva **bursting e smoothing** per tutto lo Spark del tenant, produce un modello di costo variabile e non presidiato, e influenza anche i carichi non agentici. Da riconsiderare in fase 2 come alternativa alla capacity dedicata |
| **Pausa/ripresa della capacity per assorbire il carryforward** | È un rimedio a incidente avvenuto, non una misura di isolamento. Resta disponibile come procedura di emergenza |
| **Nessuna misura, monitoraggio soltanto** | Il monitoraggio rileva, non impedisce. Con lo smoothing a 24 ore rileva anche tardi |

## Conseguenze

**Positive**
- Il rischio è dichiarato, limitato numericamente e con una condizione di uscita esplicita, invece di essere rinviato a un generico "monitoraggio".
- Il tetto di 5 workspace è verificabile e imponibile da script: entra nel contratto del rail e nella checklist di review.
- La scelta pipeline-anziché-notebook diventa una regola motivata, non un dettaglio implementativo che qualcuno "ottimizzerà".

**Negative**
- La fase 2 comporta un costo di capacity aggiuntivo, oggi non nel piano economico del progetto.
- Il tetto di 5 workspace limita la parallelizzazione futura del Dev Agent (che oggi è comunque 1, per vincolo del dispatcher).
- Serve una procedura di riassegnazione dei workspace tra capacity al passaggio di fase.

**Da fare**
- Aggiornare `docs/technical/03-rail-script.md` (contratto *Branch out*: tetto e verifica; contratto *Run load*: esecuzione via pipeline con motivazione).
- Aggiungere a `docs/functional/04-checklist-review.md` la voce corrispondente all'esecuzione via pipeline.
- Aggiornare il PRD: A-2 chiusa, R-4 riformulato, Q-5 chiusa.
