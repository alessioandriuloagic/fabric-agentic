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
| `configuration/open_meteo.json` | Assente |
| runtime o dipendenze ingestion | Assenti |

Il framework locale candidato è `fabric-universal-connector`, commit
`3303149c809172d0d320bfec353b5d81d9f7a81a`. Il suo worktree contiene modifiche non committate,
quindi non è una fonte riproducibile da copiare finché l'owner non indica un commit pulito.

## 2. Compatibilità del connettore

Il framework candidato include connettori Dataverse/CRM, Business Central e SQL. Non include un
connettore REST generico o Open-Meteo. Il ticket `daily_weather` richiede quindi sia il porting
del framework nella soluzione Agentic sia una decisione sull'introduzione di una nuova tipologia
REST.

## 3. Esito

Classificazione: **B3 - astrazione mancante**.

Il Dev Agent non deve creare configurazione, notebook o pipeline ad hoc per aggirare il gate.
S1-04 resta bloccato da S1-00 e da una decisione architetturale sul connettore REST.

## 4. Decisione richiesta

L'owner deve scegliere una delle opzioni:

1. Portare i pattern del framework e progettare un connettore REST generico, con ADR dedicato.
2. Sostituire il tracer bullet Open-Meteo con una sorgente già supportata dal framework portato.
3. Rinviare il tracer bullet dati e scegliere un primo ticket agente non di ingestion.

Qualunque opzione richiede provenienza dichiarata in `PROVENANCE.md`, secondo ADR-0009, prima
di copiare codice o configurazione.