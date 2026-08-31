# 05 — Struttura dei repository

> Dove vive ogni cosa, e perché.

Decisione applicata: [ADR-0009](../adr/ADR-0009-repository-separato-copia-pattern.md).

---

## 1. I due repository

| Repo | Contenuto | Regime |
|---|---|---|
| **Soluzione** | Artefatti Fabric, configurazione, rail script, documentazione, istruzioni degli agenti | Protetto: PR + approvazione umana |
| **Knowledge base** | Documentazione consultabile dal tracker | Generata dal repo soluzione |

Entrambi vengono clonati da **ciascuno** dei tre agenti, nei rispettivi ambienti isolati.

---

## 2. Repo soluzione — layout

```
/
├── CONTEXT.md                      # convenzioni e principi · letto a ogni sessione
├── CHANGELOG.md                    # una voce per ogni PR che cambia comportamento
├── AGENTS.md                       # disciplina di lavoro del repo
├── PROVENANCE.md                   # pattern copiati dall'asset IP e relativo commit origine
├── pyproject.toml                  # dichiara il pacchetto riutilizzabile e la sua versione
│
├── docs/
│   ├── prd/                        # requisiti e roadmap
│   ├── functional/                 # ciclo di vita, runbook, checklist, escalation
│   ├── technical/                  # questi documenti
│   ├── adr/                        # decisioni architetturali
│   ├── backlog/
│   └── sources/                    # inventario delle sorgenti e dei dataset
│
├── agents/
│   ├── issue/                      # istruzioni dell'Issue Agent
│   ├── dev/                        # istruzioni del Dev Agent
│   └── review/                     # istruzioni del Review Agent
│
├── fabric_agentic/                 # core riutilizzabile · nessuna dipendenza, nessun valore di istanza
├── scripts/                        # perimetro operativo: dispatcher, rail, publisher
├── tests/
│
├── .github/workflows/              # definizioni CI/CD: sempre lette da main
│                                   # pipe_agent_* per feature e dev, pipe_human_* con approvazione
│
├── schemas/                        # contratto artefatto dei rail, versionato (rail-result v1.0–v1.3)
├── configuration/                  # metadata-driven · un file per source system
├── profiles/                       # profili di istanza · un progetto o cliente per file
│   └── template/instance.json
├── attachments/                    # allegati versionati per numero di issue
├── kaizen/                         # note di apprendimento, indicizzate da AGENTS.md
│
├── fabric/                         # artefatti Fabric versionati (git sync)
│   ├── notebook/
│   └── pipeline/
│
└── powerbi/                        # progetto PBIP in formato testuale
```

### Note sui punti non ovvi

| Percorso | Perché è dov'è |
|---|---|
| `CONTEXT.md` alla radice | Deve essere il primo file che chiunque — umano o agente — trova. Sepolto in `docs/` verrebbe letto meno |
| `agents/` versionato | **Le istruzioni degli agenti sono codice**: si modificano per PR e si revisionano. Un cambio di istruzioni non revisionato è un cambio di comportamento non tracciato |
| `fabric_agentic/` alla radice | È il core riutilizzabile, importabile subito dopo il clone senza installazione: un layout `src/` avrebbe imposto un build in CI e in locale. `scripts/` può importarlo, il core non importa mai `scripts`, e un test lo verifica (ADR-0015) |
| `profiles/` separato da `configuration/` | Il profilo descrive **l'istanza** (progetto, ambienti, tracker); `configuration/` descrive le **sorgenti**. Sono due assi che cambiano per motivi diversi |
| `configuration/` separato da `fabric/` | La configurazione è il **contratto di onboarding**: un dataset nuovo tocca solo questa cartella. Tenerla distinta rende evidente in review quando una modifica esce dal perimetro dichiarativo |
| `docs/sources/` | Inventario di sorgenti e dataset: è ciò che l'agente aggiorna a ogni onboarding, ed è il primo posto in cui un umano cerca "cosa c'è dentro" |
| `scripts/` in-repo | I rail devono versionare **insieme** alla soluzione: un rail disallineato dagli artefatti è una fonte di errori silenziosi |
| `.github/workflows/` | Le pipeline sono il confine di privilegio: la loro definizione deve essere ancorata a `main`, non al branch di feature |
| `schemas/` | Lo schema dell'artefatto è un contratto fra pipeline e agente, quindi va versionato insieme a entrambi |
| `PROVENANCE.md` | ADR-0009 richiede di tracciare i pattern copiati da `IP.dai_fabric_environments` per gestire deliberatamente la divergenza |

---

## 3. Cosa NON sta nel repo

| Elemento | Dove sta |
|---|---|
| Credenziali, token, stringhe di connessione | Secret store, referenziate per nome |
| Identificativi di tenant e capacity | Configurazione di istanza, in un unico punto parametrico |
| File Power BI binari (`.pbix`) | Da nessuna parte: si usa il formato testuale versionabile |
| Log di sessione degli agenti | Fuori dal repo, nel perimetro locale |
| Dati | In Fabric, mai nel repo |

---

## 4. Knowledge base

| Aspetto | Scelta |
|---|---|
| Fonte di verità | `docs/` e `CONTEXT.md` nel repo soluzione |
| Pubblicazione | Wiki del tracker, **generata** |
| Regime di modifica | Il Dev Agent scrive nella fonte di verità, la pubblicazione segue |

### Il punto di attenzione

Se la generazione si disallinea, gli agenti leggono un contesto obsoleto — e il problema è
particolarmente insidioso perché **non produce errori**: produce lavoro coerente con regole
sbagliate.

**DA VERIFICARE** — meccanismo e momento della generazione: al merge su `main`, oppure a ogni
push? (collegato a Q-6).

> Preferenza di design: generazione **al merge**, così la wiki riflette sempre e solo ciò che è
> stato approvato. Il rovescio della medaglia è che durante il lavoro l'agente deve leggere la
> fonte di verità nel proprio clone, non la wiki — che è comunque il comportamento corretto.

---

## 5. Parametrizzazione dell'istanza

Tutto ciò che è specifico del progetto o del cliente vive in **un unico punto**: il profilo di
istanza, un file JSON senza segreti. Il contratto è implementato in
`fabric_agentic/instance_profile.py` e il punto di partenza è `profiles/template/instance.json`.

| Parametro | Esempio |
|---|---|
| Nome progetto | `agentic` |
| Tenant e capacity | Identificativi di istanza |
| Progetto e repository del tracker | Riferimenti |
| Riferimenti alle credenziali | Nomi nel secret store, mai valori |

I nomi dei workspace **non** si scrivono a mano: sono derivati dallo slug di progetto
(`ws_<slug>_<ambiente>`, `ws_<slug>_feature_wi<id>`). Il profilo rifiuta credenziali inline, un
connettore sconosciuto e una modalità di carico che il connettore non supporta.

Due comandi rendono verificabile la parametrizzazione:

```
python -m fabric_agentic validate --config profiles/<cliente>/instance.json
python -m fabric_agentic render   --config profiles/<cliente>/instance.json --output .generated
```

`render` produce il piano di deployment ed è riproducibile byte per byte, così un diff segnala
solo cambiamenti reali. Vedi `12-console-e-avvio.md`.

> **Criterio di verifica**: se per istanziare un nuovo cliente devi cercare e sostituire un nome
> in più file, la parametrizzazione è già rotta. Il test è semplice — cerca il nome del progetto
> nel repo: deve comparire solo nel punto parametrico e negli esempi della documentazione.

---

## 6. Convenzioni Git

| Elemento | Convenzione |
|---|---|
| Workflow | GitHub Flow: `main` sempre rilasciabile, branch feature a vita breve |
| Branch | `feature/wi-<id>-<slug>` |
| Commit | Conventional Commits |
| Merge | Squash, solo umano |
| Tag | `v<x.y.z>` |

Dettaglio completo in `CONTEXT.md`, sezione 5.

---

## 7. Fase 2 — doppio tracker

Quando il flusso verrà replicato su GitHub, la struttura del repo **non cambia**. Cambia solo
l'implementazione dell'astrazione tracker.

| Elemento | Dipende dal tracker |
|---|---|
| Struttura del repo | No |
| Rail script | No |
| Documentazione funzionale | No |
| Checklist di review | No |
| Istruzioni degli agenti | Solo nella parte di interazione con il tracker |
| Dispatcher | **Sì** — è il punto di variabilità |

> È la verifica pratica del requisito RF-06: se aggiungere GitHub richiedesse di toccare i rail
> o la struttura del repo, l'astrazione non era dove serviva.
