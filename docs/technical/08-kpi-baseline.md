# 08 - KPI baseline

> Baseline misurata prima del primo ticket agentico reale.

---

## 1. Metodo

La baseline distingue le misure osservate dalle misure ancora da rilevare. Nessun valore stimato
viene usato come dato di confronto senza dichiararlo.

| KPI | Metodo | Stato |
|---|---|---|
| KPI-1 Autonomia | Conteggio ticket dalla presa in carico alla PR approvata senza interventi tecnici umani | Da rilevare con S1-04 |
| KPI-2 Lead time | Timestamp work item `To Do` -> apertura PR | Da rilevare con S1-04 |
| KPI-3 Cicli review | Conteggio iterazioni Dev/Review su PR | Da rilevare con Review Agent attivo |
| KPI-4 Copertura documentale | Review della PR contro checklist E1-E5 | Attiva dalla prima PR agentica |
| KPI-5 Costo | Metadati `total_cost_usd` dell'output JSON Claude per sessione | Da rilevare con S1-04 |
| KPI-6 Difetti sfuggiti | Rilievi post-merge attribuiti a una PR agentica | Baseline iniziale: 0 osservati |
| KPI-7 Costo idle | Sessioni Claude avviate durante polling senza task | Misurato |

## 2. Misura idle

| Campo | Valore |
|---|---|
| Data | 2026-08-21 |
| Dispatcher | Dev Agent locale, configurazione `poll_seconds: 30` |
| Cicli osservati | 2 |
| Task rilevati | 0 in entrambi i cicli |
| Sessioni Claude avviate | 0 |
| Consumo LLM idle | 0 token / $0 misurato |
| Durata ciclo 1 | 9.985 s |
| Durata ciclo 2 | 14.406 s |

Le durate includono l'acquisizione del token Azure DevOps e le query Azure Boards/GitHub. Il log
locale del dispatcher registra solo contatori, work item, trigger, esiti e durata; non registra
token, contenuti di task o output di Claude.

## 3. Baseline manuale da rilevare

Il tempo-uomo per l'onboarding manuale di un dataset non è stato ancora osservato in condizioni
comparabili. Va rilevato sul primo onboarding Open-Meteo o City Registry con questo metodo:

1. Avviare il timer quando l'owner inizia la configurazione tecnica.
2. Fermare il timer dopo esecuzione, controlli qualità, documentazione e PR pronta per review.
3. Annotare separatamente attese esterne e interventi non pianificati.
4. Confrontare il valore con il lead time e il costo della prima esecuzione agentica S1-04.

Finché questa misura non esiste, KPI-1, KPI-2 e KPI-5 non hanno un baseline quantitativo.
