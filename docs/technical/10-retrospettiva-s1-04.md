# 10 - Retrospettiva S1-04

> Retrospettiva del primo ciclo agentico CRM `accounts`, chiusura S1-05.

## 1. Esito

S1-04 è concluso: il Dev Agent ha portato il tracer CRM fino al run riuscito e alla PR mergiata.
Il ciclo ha richiesto interventi tecnici umani durante la diagnosi e la correzione del binding
Lakehouse, dell'autenticazione CRM e della pubblicazione dell'evidenza. Questi interventi non
sono stati nascosti dentro il risultato del ticket: sono difetti di automazione da eliminare nei
cicli successivi.

## 2. KPI osservati

| KPI | Evidenza | Risultato | Stato |
|---|---|---:|---|
| KPI-1 Autonomia | PR #38, #39, #40 e #41; correzioni necessarie prima del run finale | Non calcolabile come percentuale | Gap |
| KPI-2 Lead time | Run load finale `32648994929`: 15:34:51Z–15:36:18Z; timestamp To Do e apertura PR non disponibili | 87 s di esecuzione CI, non lead time ticket | Parziale |
| KPI-3 Cicli review | PR del primo ciclo mergiate con review umana; Review Agent non ancora attivo | Non rilevato | Gap |
| KPI-4 Copertura documentale | Evidenza in `docs/sources/crm_demo.md` e `docs/technical/09-framework-gate.md` | Presente | Pass |
| KPI-5 Costo | Nessun `total_cost_usd` o conteggio token disponibile nei log versionati | Non misurabile | Gap |
| KPI-6 Difetti sfuggiti | Nessun difetto post-merge osservato alla data della retrospettiva | 0 osservati | Baseline |
| KPI-7 Costo idle | Due cicli senza task: 0 sessioni Claude, 0 token, $0 | 0 | Pass |

I tempi dei workflow sono operational timings e non sostituiscono il lead time richiesto dal PRD,
che va misurato da creazione o presa in carico del work item fino all'apertura della PR.

## 3. Interventi umani non previsti

| Intervento | Impatto | Azione |
|---|---|---|
| Diagnosi del notebook riusato senza binding Lakehouse | Job verde senza tabelle visibili | Rendere il binding dinamico obbligatorio nel deployer |
| Diagnosi dell'errore Fabric Key Vault Connection | Autenticazione non affidabile | Usare secret diretto da Key Vault e documentare il confine |
| Verifica e propagazione manuale dell'evidenza | Rail result inizialmente incompleto | Persistenza OneLake + lettura automatica nel deployer |

Le correzioni sono state portate nel codice e provate con i run `32648577263` e `32648994929`.
L'issue #42 mantiene aperta la distinzione contrattuale tra delta caricato e totale destinazione.

## 4. Decisioni per il ciclo successivo

- Aggiungere al dispatcher e al rail timestamp correlabili al work item e alla PR.
- Conservare per ogni sessione agentica metadati di costo non sensibili: durata, token aggregati
  e `total_cost_usd`, se il runtime li espone.
- Attivare il Review Agent prima di usare KPI-3 come misura comparabile.
- Chiudere la semantica `loaded_count`/`total_destination_count` tramite issue #42.
- Usare come baseline corrente: KPI-7 = 0, KPI-6 = 0 osservati; KPI-1, KPI-2, KPI-3 e KPI-5
  restano da rilevare con strumentazione completa.

**Stato S1-05: completato con gap KPI registrati.**