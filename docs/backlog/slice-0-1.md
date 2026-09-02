# Backlog — Slice 0 e Slice 1

> Work item pronti per la board, con tracciabilità ai requisiti del PRD.
>
> **Slice 0** è quasi interamente umano: costruisce le fondamenta su cui gli agenti potranno
> lavorare. **Slice 1** è il primo ticket agentico reale.

| Campo | Valore |
|---|---|
| Versione | 0.2 |
| Data | 2026-08-20 |
| Documenti di riferimento | `../prd/PRD-agentic-cicd-fabric.md` · `../../CONTEXT.md` · `../functional/` · `../technical/` |

---

## Come leggere questo backlog

| Colonna | Significato |
|---|---|
| **Esecutore** | `Umano` · `Agente` · `Umano + script` |
| **Taglia** | `S` (lineare) · `M` (più passi o verifiche) · `L` (comporta progettazione) |
| **RF** | Requisiti del PRD coperti |

**Ordine**: le dipendenze sono esplicite. Dove non c'è dipendenza, gli item sono parallelizzabili.

---

## Definition of Ready

Un work item è pronto per essere preso in carico quando:

- [ ] Ha obiettivo, criteri di accettazione verificabili e sezione "fuori scope"
- [ ] Le dipendenze dichiarate sono completate
- [ ] Se destinato a un agente: ha il tag `dev-agent` ed è in *To Do*

## Definition of Done

Un work item è concluso quando:

- [ ] I criteri di accettazione sono tutti verificati **praticamente**, non solo configurati
- [ ] La documentazione impattata è aggiornata
- [ ] `CHANGELOG.md` contiene la voce (se la modifica cambia comportamento)
- [ ] Nessun segreto è finito nel repo o nel tracker

---

# SLICE 0 — Fondamenta e knowledge base

**Obiettivo dello slice**: al termine, un agente può essere avviato, autenticarsi, leggere il
contesto e scrivere sul tracker — e **non** può raggiungere `main`.

**Criterio di uscita**: lo smoke test S0-14 passa.

---

## Gruppo A — Tracker e repository

### S0-01 · Creare progetto e repository

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | S |
| **Dipendenze** | — |
| **RF** | RF-82 |

**Obiettivo**: esistono il progetto sul tracker, il repository della soluzione e lo spazio della
knowledge base.

**Criteri di accettazione**
- Progetto Azure Boards `fabric-agentic` creato nell'organizzazione `alessioandriulo`
- Repository della soluzione creato, con `main` inizializzato
- Spazio della knowledge base disponibile
- L'owner ha i permessi amministrativi

**Fuori scope**: permessi degli agenti (S0-05), branch policy (S0-06).

---

### S0-02 · Portare la documentazione nel repository

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | S |
| **Dipendenze** | S0-01 |
| **RF** | RF-50, RF-52, RF-85 |

**Obiettivo**: la knowledge base è nel repo ed è consultabile.

**Criteri di accettazione**
- `CONTEXT.md`, `CHANGELOG.md`, `docs/prd/`, `docs/functional/`, `docs/technical/` presenti su `main`
- La struttura di cartelle prevista da `docs/technical/05-struttura-repository.md` è creata
- La wiki è generata dalla documentazione versionata
- Il meccanismo di generazione è documentato

**Fuori scope**: istruzioni degli agenti (S0-11, S0-12).

> **Nota**: chiude parzialmente Q-6 (dove vive la checklist di review). Decidere in questo item
> e registrare la scelta.

---

### S0-03 · Configurare la board

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | S |
| **Dipendenze** | S0-01 |
| **RF** | RF-01, RF-12 |

**Obiettivo**: la board Basic riflette il ciclo di vita definito in `docs/functional/01`.

**Criteri di accettazione**
- Stati disponibili e verificati: *To Do*, *Doing*, *Done*
- Tag `dev-agent` e `waiting-input` creati
- Un work item di prova percorre *To Do* → *Doing* → *Done*
- Un blocco è rappresentato da *Doing* + `waiting-input`; un commento umano rimuove il tag e riattiva l'agente

**Esito 2026-08-20**: work item Azure Boards `#19` ha verificato il flusso *To Do* → *Doing* →
*Done*. I tag non sono ancora creati: l'identità dell'owner deve ricevere il permesso Azure DevOps
**Create tag** nel progetto `fabric-agentic`.

---

## Gruppo B — Identità e sicurezza

### S0-04 · Creare le identità applicative

| | |
|---|---|
| **Esecutore** | Umano (richiede amministratore di tenant) |
| **Taglia** | M |
| **Dipendenze** | — |
| **RF** | RF-81, RNF-01 |

**Obiettivo**: esistono due identità applicative distinte e un gruppo di sicurezza dedicato.

**Criteri di accettazione**
- Service principal del Dev Agent creato
- Service principal del Review Agent creato, **distinto**
- Gruppo di sicurezza degli agenti creato, con entrambi come membri
- Credenziali registrate nel secret store
- **Nessuna credenziale in file di configurazione o nel repo**

**Fuori scope**: assegnazione dei permessi (S0-05, S0-07).

> **Vincolo di pianificazione**: richiede la disponibilità di un amministratore di tenant.
> Va prenotata in anticipo — è il collo di bottiglia dell'intero Slice 0.

---

### S0-05 · Assegnare i permessi sul tracker

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | M |
| **Dipendenze** | S0-01, S0-04 |
| **RF** | RF-73, RNF-01 |

**Obiettivo**: ciascun agente ha esattamente i permessi previsti dalla matrice, e nulla di più.

**Criteri di accettazione**
- Dev Agent: contribuisci sul repo soluzione, contribuisci alla knowledge base, lettura e scrittura sui work item
- Review Agent: **sola lettura** sul repo, commento e voto sulle PR, sola lettura sui work item
- Review Agent **rimosso** dai contributori del repo
- La matrice di `docs/technical/04-identita-e-permessi.md` è rispettata voce per voce

---

### S0-06 · Proteggere il ramo principale — e verificarlo

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | M |
| **Dipendenze** | S0-05 |
| **RF** | RF-70, RF-71, RF-73, RF-83 |

**Obiettivo**: nessun agente può raggiungere `main`, e **lo abbiamo dimostrato**.

**Criteri di accettazione — configurazione**
- Push diretto su `main` negato a entrambi gli agenti
- Pull request obbligatoria per ogni modifica
- Approvazione umana obbligatoria, in aggiunta a quella del Review Agent
- Deny esplicito sul permesso **oltre** alla branch policy (difesa in profondità)

**Criteri di accettazione — verifica pratica** *(obbligatoria — 9 controlli)*
- [ ] Push su `main` con l'identità del Dev Agent → **rifiutato**
- [x] Push su `main` con l'identità del Review Agent → **rifiutato** — prova #98, HTTP `403`
- [ ] Merge con l'identità del Dev Agent → **rifiutato**
- [ ] Creazione workspace da Dev Agent con identità Fabric → **rifiutato**
- [ ] Scrittura su workspace Fabric da Dev Agent → **rifiutato**
- [ ] Accodamento pipeline human-only da Dev Agent → **rifiutato**
- [ ] Accodamento pipeline agentica da Dev Agent → **consentito**
- [ ] Review Agent non vede alcun workspace Fabric → **elenco vuoto**
- [x] Review Agent riesce a votare una PR → **consentito** — verificato su PR #105
- [x] Esito delle prove registrato nel work item — issue #98

> **È l'item più importante dello Slice 0.** Una policy configurata e mai provata è una policy
> di cui non sai nulla. Se questo item non è verde, nessun agente va avviato.

**Stato 2026-08-27 — parziale**: la prova runtime del Review Agent ha confermato il divieto di
scrittura sul repository con `POST /git/refs` → HTTP `403`, senza creare il ref di probe, e il
divieto di merge con `PUT /pulls/109/merge` → HTTP `403`, `merged: false`, su una PR usa-e-getta
poi chiusa e rimossa. I controlli Review Agent relativi a push, voto e registrazione dell'esito
sono ora spuntati; gli altri controlli restano non verificati. L'enforcement tecnico delle protection rules richiede un
piano GitHub più alto non disponibile nell'attuale sottoscrizione. Il processo GitHub Flow e la
revisione umana restano obbligatori, ma i 9 controlli pratici non sono marcati come verificati.

---

### S0-07 · Abilitare i permessi sulla piattaforma dati

| | |
|---|---|
| **Esecutore** | Umano (richiede amministratore di tenant) |
| **Taglia** | M |
| **Dipendenze** | S0-04 |
| **RF** | RF-13, RF-72, RNF-01 |

**Obiettivo**: il Dev Agent può diagnosticare solo in lettura; ogni operazione Fabric in scrittura
è eseguita dall'identità di deploy della pipeline CI/CD.

**Criteri di accettazione**
- Dev Agent: `Viewer` solo su feature workspace e `ws_agentic_dev`, esclusivamente con dati sintetici o open data
- Dev Agent: nessun ruolo `Admin`, `Member` o `Contributor` su alcun workspace e nessun ruolo sulla capacity
- Dev Agent: nessun ruolo su `ws_agentic_test` e `ws_agentic_prod`
- Switch "Service principals can use Fabric APIs" ristretto al gruppo agenti
- Switch "Service principals can create workspaces, connections, and deployment pipelines" **non** concesso al Dev Agent
- Review Agent: **nessun ruolo**, su nessun workspace e sulla capacity
- Verifiche: Dev Agent legge uno stato di run ma non può creare workspace, scrivere item o avviare job; Review Agent vede un elenco workspace vuoto

> La pipeline usa una distinta identità di deploy. Il Dev Agent può accodarla ma non può
> impersonarla né modificarne la definizione. Vedi ADR-0007 e ADR-0008.

**Stato aggiornato 2026-08-27**: membership del workspace verificata dalla UI. `fabric-agentic-deploy`
risulta `Contributor`, `fabric-agentic-dev-agent` risulta `Viewer` e il Review Agent non compare.
Il contesto Azure locale è autenticato come `fabric-agentic-dev-agent` nel tenant Agic Dev: la GET
di `ws_agentic_dev`, l'elenco workspace, l'elenco item e la lettura delle istanze job hanno
restituito HTTP `200`; la creazione workspace con payload `{}` è stata rifiutata con HTTP `401`,
senza creare risorse. Restano da verificare runtime di scrittura e switch tenant; il
codice `401` va riconfermato con il test del Deploy SP e, se necessario, dopo la finestra completa
di propagazione.

---

### S0-N1 · Separare le famiglie di pipeline

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | S |
| **Dipendenze** | S0-01, S0-05 |
| **RF** | RF-72, RNF-01 |

**Obiettivo**: le pipeline CI/CD sono suddivise in `pipe_agent_*`, `pipe_human_*` e `pipe_sched_*`.

**Criteri di accettazione**
- Dev Agent può accodare solo `pipe_agent_*`
- Pipeline `pipe_human_*` accodabili solo da umani, verso test/prod
- Pipeline `pipe_sched_*` non accodabili dagli agenti
- Il Dev Agent non appartiene al gruppo `Contributors`, che concede `Queue builds` per default
- Tentativo pratico di accodare `pipe_human_*` dal Dev Agent → **rifiutato**

**Stato aggiornato 2026-08-26**: naming applicato nei workflow GitHub Actions. I quattro workflow
operativi sono `pipe_agent_branch_out.yml`, `pipe_agent_sync_workspace.yml`,
`pipe_agent_crm_preflight.yml` e `pipe_agent_crm_run_load.yml`; il test manuale OIDC è
`pipe_human_test_azure_oidc_dev.yml`. Non esistono workflow schedulati, quindi non è stata creata
una famiglia `pipe_sched_*`. Il run OIDC manuale `32943998407` da `main` ha verificato login
Deploy SP e lettura metadata di `ws_agentic_dev`. Restano da verificare i permessi effettivi di
dispatch e environment.

---

### S0-N2 · Proteggere le pipeline privilegiate

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | M |
| **Dipendenze** | S0-N1 |
| **RF** | RF-72, RNF-01 |

**Obiettivo**: un branch di feature non può cambiare i privilegi dell'identità di deploy (RB-4).

**Criteri di accettazione**
- La definizione di ogni pipeline privilegiata è letta da `main`; il branch di feature è solo parametro
- `targetEnvironment` non è un parametro delle pipeline agentiche
- Check fuori YAML: Branch control, Required template e approvazioni per gli environment protetti
- Service connection ed environment sono autorizzati solo alle pipeline nominate
- Verifica: modifica YAML su feature branch non altera il run della pipeline privilegiata

**Stato aggiornato 2026-08-26**: da completare con il ticket amministrativo GitHub #83. I workflow
privilegiati restano ancorati a `main` e senza `targetEnvironment`; protection rules, autorizzazioni
di environment e prova d'immutabilità della definizione fuori YAML non sono ancora verificabili
con il piano GitHub corrente.

**Evidenza OIDC 2026-08-26**: il run GitHub Actions `32943998407` ha completato con successo
l'autenticazione OIDC e la lettura metadata di `ws_agentic_dev` tramite il Deploy SP.

---

### S0-N3 · Versionare lo schema `rail-result.json`

| | |
|---|---|
| **Esecutore** | Umano + script |
| **Taglia** | S |
| **Dipendenze** | S0-N2 |
| **RF** | RF-16, RNF-05 |

**Obiettivo**: ogni pipeline agentica pubblica un artefatto strutturato, non solo log.

**Criteri di accettazione**
- Schema JSON versionato in `schemas/rail-result-v1.0.json`
- Campi minimi: versione, rail, outcome, run ID, workspace ID, dataset, messaggi
- Outcome ammessi: `success`, `technical_failure`, `quality_failure`
- Ogni dataset dichiara `supports_source_count`
- Assenza dell'artefatto classificata come fallimento tecnico

---

### S0-N4 · Configurare la credenziale ADO del Dev Agent

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | S |
| **Dipendenze** | S0-04 |
| **RF** | RNF-01, RNF-05 |

**Obiettivo**: l'identità del Dev Agent accede ad Azure DevOps con una credenziale ruotabile e con il minimo privilegio.

**Criteri di accettazione**
- Credenziale non interattiva e ruotabile, custodita fuori dal repo
- Scope limitato a work item, branch/PR e `Queue builds` sulle sole pipeline agentiche
- Nessuna credenziale Fabric nel runtime del Dev Agent
- Procedura di rotazione e revoca registrata nel runbook operativo

**Esito 2026-08-21**: certificato client non esportabile creato nel certificate store locale e
chiave pubblica registrata su `fabric-agentic-dev-agent`. Testata l'acquisizione di token Entra
per Azure DevOps e la lettura del progetto `fabric-agentic`; nessun PAT, client secret o token è
stato scritto nel repository o nei log.

---

### S0-N5 · Configurare la `ExecutionCredential` del cliente

| | |
|---|---|
| **Esecutore** | Umano + amministratore cliente |
| **Taglia** | M |
| **Dipendenze** | S0-04, S0-N2 |
| **RF** | RF-37, RF-38, RNF-01, RNF-03 |

**Obiettivo**: una sola credenziale tecnica per cliente è disponibile alle pipeline, mai agli agenti.

**Criteri di accettazione**
- Tipo scelto e registrato: SP OIDC, SP con secret o utenza di servizio
- Se secret o utenza di servizio: valore custodito nel Key Vault/secret store, repository e runtime agentico non lo contengono
- La pipeline accede alla credenziale; Dev e Review Agent non possono leggerla o impersonarla
- Permessi minimi verificati su workspace e sorgente; nessun riuso tra clienti
- Se utenza di servizio: autenticazione non interattiva provata prima dell'avvio dei dispatcher

---

## Gruppo C — Agenti e dispatcher

### S0-08 · Predisporre gli ambienti di esecuzione

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | M |
| **Dipendenze** | S0-04 |
| **RF** | RNF-01, V-2 |

**Obiettivo**: i due runtime agentici girano in ambienti **isolati** sulla macchina dell'owner.

**Criteri di accettazione**
- Runtime del Dev Agent installato, vendor A
- Runtime del Review Agent installato, vendor B, in ambiente separato
- Ciascuno autenticato con **il proprio** service principal
- I due cloni Git predisposti per ciascun agente
- Verifica: nessuna condivisione di credenziali o cache tra i due ambienti

---

### S0-09 · Dispatcher del Dev Agent

| | |
|---|---|
| **Esecutore** | Umano + script |
| **Taglia** | L |
| **Dipendenze** | S0-03, S0-05, S0-08 |
| **RF** | RF-02, RF-03, RF-05, RNF-05, RNF-08 |

**Obiettivo**: uno script deterministico rileva i tre trigger e avvia una sessione fresca.

**Criteri di accettazione**
- Polling a ~30 secondi, **senza consumo di token**
- Trigger A: work item in *To Do* con tag `dev-agent`
- Trigger B: nuovo commento **umano** su work item in *Doing* con tag `waiting-input`
- Trigger C: thread **non risolti** sulla PR dell'agente
- Una sola sessione attiva per volta
- Token rinnovato a ogni ciclo e a ogni avvio
- Log di sessione con: identificativo, trigger, work item, esito, durata
- **Nessun token compare nei log**

**Verifiche anti-loop** *(obbligatorie)*
- [ ] Un commento **dell'agente stesso** non lo risveglia
- [ ] Un thread **risolto** non lo risveglia

> Le due verifiche anti-loop non sono opzionali: sono le due cause più probabili di consumo
> token incontrollato, e si manifestano solo in esercizio se non le cerchi ora.

**Stato 2026-08-25**: trigger A/B/C, anti-loop, loop configurabile a 30 secondi e logging locale
implementati. `--once --dry-run` è stato verificato su Azure DevOps e GitHub Issues; S0-14 è verde
con il ciclo reale GitHub e il tracer `pagamenti` ha completato il primo flusso agentico.

---

### S0-10 · Dispatcher del Review Agent

| | |
|---|---|
| **Esecutore** | Umano + script |
| **Taglia** | M |
| **Dipendenze** | S0-05, S0-08 |
| **RF** | RF-04, RF-05, RNF-05 |

**Obiettivo**: uno script rileva l'unico trigger previsto e avvia una sessione fresca.

**Criteri di accettazione**
- Polling a ~30 secondi, senza consumo di token
- Trigger unico: PR attiva in cui il voto del Review Agent non è "approvato"
- Verifica: una nuova push su una PR già approvata **rimette** l'agente in condizione di trigger
- Log di sessione conforme a S0-09

---

### S0-11 · Istruzioni del Dev Agent

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | L |
| **Dipendenze** | S0-02 |
| **RF** | RF-10, RF-11, RF-16, RF-23, RF-65, RNF-10 |

**Obiettivo**: le istruzioni del Dev Agent sono versionate in `agents/dev/` e vincolano il
comportamento previsto dalla documentazione funzionale.

**Criteri di accettazione**
- All'avvio: aggiornamento di entrambi i cloni, lettura di `CONTEXT.md` e del runbook pertinente
- Uso obbligatorio dei rail per le operazioni procedurali
- Protocollo di escalation recepito (`docs/functional/05`)
- Regola di verifica sulla documentazione ufficiale recepita
- Divieti espliciti: mai merge, mai modifica di permessi o policy, mai segreti in chiaro
- Le istruzioni sono nel repo e modificabili **solo per PR**

**Stato 2026-08-21**: istruzioni e contratto task versionati in `agents/dev/`; Claude Code
`2.1.228` è installato e una sessione headless minimale ha restituito `READY`. Restano il clone
isolato e la credenziale Azure DevOps non interattiva del Dev Agent prima del dispatcher S0-09.

---

### S0-12 · Istruzioni del Review Agent

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | M |
| **Dipendenze** | S0-02 |
| **RF** | RF-60, RF-61, RF-62, RF-63, RF-64, RNF-10 |

**Obiettivo**: le istruzioni del Review Agent sono versionate in `agents/review/`.

**Criteri di accettazione**
- Review condotta **esclusivamente** contro la checklist chiusa
- Verifica del diff sulla propria copia, mai sulla descrizione della PR
- Esito strutturato per ogni voce, nel formato previsto
- Divieti espliciti: mai scrivere codice di feature, mai approvare con rilievi aperti
- Regola: un rilievo non riconducibile alla checklist non è un rilievo

**Stato 2026-08-25**: istruzioni versionate create in `agents/review/INSTRUCTIONS.md`. Il
contratto definisce lettura indipendente del diff, checklist A-F completa, formato dell'esito e
divieti di scrittura, merge, accesso a Fabric e accesso a credenziali. Resta da provare il Review
Agent in esercizio su una PR reale.

---

### S0-13 · Checklist di review, versione 1

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | S |
| **Dipendenze** | S0-02 |
| **RF** | RF-61 |

**Obiettivo**: la checklist è versionata nella posizione decisa in S0-02 ed è la fonte unica dei
criteri di review.

**Criteri di accettazione**
- Le sezioni A–F di `docs/functional/04-checklist-review.md` sono attive
- La modifica della checklist richiede una PR
- Chiude Q-6

---

## Gruppo D — Collaudo

### S0-14 · Smoke test della catena

| | |
|---|---|
| **Esecutore** | Umano + Agente |
| **Taglia** | S |
| **Dipendenze** | S0-06, S0-09, S0-11 |
| **RF** | RF-01, RF-02, RF-03, RF-05, RF-12 |

**Obiettivo**: validare autenticazione, trigger, avvio sessione e scrittura sul tracker
**senza toccare Fabric**.

**Contenuto**: un work item taggato che chiede all'agente solo di leggere il contesto, dichiarare
in un commento quali documenti ha letto, e chiudere.

**Criteri di accettazione**
- Il ticket viene rilevato entro un ciclo di polling
- L'agente sposta il ticket in *Doing*
- L'agente commenta citando `CONTEXT.md` e i documenti letti
- La sessione termina e il dispatcher torna in polling
- Il log di sessione è completo
- **Nessun token nei log**

> Vale la pena isolare questo test: se fallisce, sai che il problema è nella catena
> identità/trigger/sessione e **non** in Fabric. Diagnosticare le due cose insieme costa
> molto di più.

**Implementazione 2026-08-21**: dispatcher con modalità `--smoke-work-item-id`, sessione Claude
read-only a output JSON strutturato e commento/chiusura del work item eseguiti dal dispatcher con
l'identità Dev Agent.

**Esito 2026-08-21**: verificato sul work item `#7`: rilevamento, transizione `To Do` → `Doing`
→ `Done`, sessione Claude read-only, commento dell'identità Dev Agent e log locale senza token.
S0-14 è verde.
---

### S0-15 · Rilevare la baseline dei KPI

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | S |
| **Dipendenze** | S0-14 |
| **RF** | KPI-1..7 |

**Obiettivo**: esiste un punto di partenza misurabile.

**Criteri di accettazione**
- Tempo-uomo attuale per un onboarding manuale di un dataset, rilevato o stimato con metodo dichiarato
- Consumo token del sistema in idle, misurato: **deve risultare ≈ 0**
- Modalità di raccolta dei KPI documentata

**Esito aggiornato 2026-08-25**: il run Fabric `20260825T141929Z-70aacec7` ha richiesto 21 s e
ha caricato 10 righe con riconciliazione passata. Il costo monetario della capacity e il costo
LLM non sono attribuibili dall'evidenza disponibile; il tempo-uomo manuale resta da rilevare.

**Esito parziale 2026-08-21**: costo idle misurato con due cicli senza task: 0 sessioni Claude,
0 token e $0; durate 9.985 s e 14.406 s. Metodo e KPI residui in
`docs/technical/08-kpi-baseline.md`. Il tempo-uomo manuale resta da rilevare sul primo onboarding
comparabile, quindi S0-15 si completa con tale osservazione.

---

# SLICE 1 — Primo ticket agentico: tracer bullet dati

**Obiettivo dello slice**: il Dev Agent completa un onboarding sintetico/open data in un feature
workspace isolato, dall'input del ticket alla PR.

**Criterio di uscita**: il dataset CRM `accounts` è caricato e verificato nel feature workspace;
la PR contiene evidenze, documentazione e changelog. `test` e `prod` restano fuori scope.

### S1-00 · Gate framework metadata-driven e REST

| | |
|---|---|
| **Esecutore** | Umano + architetto |
| **Taglia** | L |
| **Dipendenze** | ADR-0009, S0-14 |
| **RF** | RF-30..RF-35, RF-50 |

**Obiettivo**: rendere disponibile nella soluzione Agentic un framework metadata-driven CRM
riproducibile.

**Criteri di accettazione**
- `PROVENANCE.md` registra repository e commit pulito della fonte dei pattern copiati
- La collocazione di configurazione, runtime, orchestrazione e qualità è definita nel repository
- Il connettore CRM e la Fabric Connection `b838644d-afd9-4ec3-973d-e36ed85ad167` sono
  referenziati nel contratto e nella configurazione di istanza
- Watermark inclusivo, merge su `accountid` e commit post-Bronze/audit sono implementati secondo
  ADR-0012
- Nessun codice del framework viene copiato prima della decisione e della provenienza

**Esito 2026-08-21**: B3 confermato. Il clone Agentic non contiene framework/configurazione;
il tracer è stato spostato su CRM `account`, tipologia già supportata. Resta da portare il
framework da una fonte pulita con `PROVENANCE.md`. Vedi `docs/technical/09-framework-gate.md`.

**Avanzamento 2026-08-21**: commit sorgente pulito registrato in `PROVENANCE.md`; configurazione
CRM, schema fail-fast, builder request incremental e collocazioni target creati. Restano staged
extraction, Bronze merge, audit, watermark, notebook/pipeline e rail `run_load`.

**Avanzamento 2026-08-21 (preflight)**: notebook FabricGitSource `nb_crm_preflight` validato
localmente. Il deploy OIDC, Lakehouse e job `RunNotebook` restano da verificare prima di leggere
dati CRM.

**Avanzamento 2026-08-21 (deployer)**: workflow `crm-preflight` e deployer idempotente creati;
creano/riusano Lakehouse e notebook nel feature workspace e usano `RunNotebook`. La prova OIDC
post-merge resta aperta.

**Inventario 2026-09-01 (#158)**: staging per run, PK check, merge Bronze idempotente, audit per
`run_id`, watermark post-audit e rail `run_load` risultano implementati e coperti da test; lo
stato anello per anello è in `../technical/14-inventario-catena-crm-accounts.md`. Corrette in
quella PR: artefatto di fallimento del rail non conforme ad alcuno schema, fallback del workflow
con `workspace_id: null`, guard di contratto cieco sulla v1.3, e i test dei criteri 2-6 assenti
dall'elenco della CI. Restano aperti `reconciliation` asserita invece che calcolata, evidenza
Fabric non legata al run sottomesso, e la sequenza run iniziale/idempotente/delta con verifica
SQL: quest'ultima è un blocco B4, perché una sessione dispatchata non può accodare il workflow
del rail né leggere Fabric.

---

### S1-01 · Spike: deploy e binding Power BI con `fabric-cicd`

| | |
|---|---|
| **Esecutore** | Umano + script |
| **Taglia** | M |
| **Dipendenze** | S0-N2 |
| **RF** | RF-40, RF-43, RF-79 · chiude Q-3 |

**Obiettivo**: convalidare il deploy reale di semantic model TMDL e report PBIR nel canale CI/CD.

**Criteri di accettazione**
- `fabric-cicd` è pinato a `1.3.0` per lo spike
- Workspace di test contiene un `SemanticModel` TMDL e un `Report` PBIR con riferimento `byPath`
- Deploy crea entrambi gli item in un workspace Fabric vuoto
- Report è associato al semantic model di destinazione e si apre senza errore
- Scenario `byConnection` validato con la parametrizzazione necessaria
- Esito e versione del package registrati nel work item; i limiti noti sui binding entrano nel runbook Power BI

> Evidenza primaria: documentazione e sorgente `fabric-cicd` supportano `Report` (PBIR) e
> `SemanticModel` (TMDL). PBIP non è un tipo deployabile: è il contenitore Desktop dei due item.

**Stato 2026-08-24 — TODO futuro**: workspace `ws_agentic_test` creato e assegnato alla capacity
`fabricalessiodev` nel tenant corrente. Semantic Model `CRM Demo` creato nel workspace con Direct
Lake verso `lh_bronze_crm_demo`. Lo sviluppo Report Power BI è sospeso: Desktop continua a
segnalare un errore JavaScript di rendering (`visualContainers`) con la live connection, nonostante
la validazione PBIR locale. L'errore è registrato nel runbook con ID attività
`f46caa69-5f7f-46d4-ab27-854dca94a8e2`. La pubblicazione e la verifica `byConnection` restano
fuori dal percorso critico fino a una futura attività dedicata.

**Priorità corrente**: integrare GitHub Issues per issue, stato, commenti, trigger del dispatcher e
tracciabilità PR; Azure Boards resta il tracker legacy da dismettere.

---

### S1-02 · Rail: branch out

| | |
|---|---|
| **Esecutore** | Umano + script |
| **Taglia** | L |
| **Dipendenze** | S0-N3 |
| **RF** | RF-13, RF-14, RF-16 |

**Obiettivo**: un solo comando predispone branch, feature workspace e collegamento Git.

**Criteri di accettazione**
- Contratto rispettato secondo `docs/technical/03-rail-script.md`
- Nome di branch e workspace **derivati dall'ID del work item**
- L'owner è amministratore del workspace creato
- **Idempotente**: rilanciato sullo stesso ID, si riconnette invece di duplicare
- Esito binario esplicito e output strutturato
- Nessun segreto in output

**Esito 2026-08-21**: verificato con successo dal run GitHub Actions `32487821272` sul work
item `6`. Il rail ha riusato branch e workspace deterministici, confermato l'assegnazione alla
capacity, collegato Git e sincronizzato; l'artefatto `rail-result.json` ha `outcome: success`.

**Riprova 2026-08-26**: il run `32945217566` ha confermato checkout da `main` e login OIDC del
Deploy SP, ma il rail ha restituito `technical_failure` allo stage `git_connection`, senza creare
branch o workspace. Prima di riavviare il rail va verificata la Configured Connection Git, inclusi
repository/branch e il ruolo `User` del Deploy SP sulla connection.

**Correzione 2026-08-26**: il workspace esistente `ws_agentic_feature_wi6` risulta già collegato
a `feature/wi-6-smoke-branch-out`. Il rail confrontava però `organizationName` invece di
`ownerName` per GitHub e classificava la connection esistente come incompatibile. Il confronto è
stato corretto e richiede un nuovo run idempotente.

**Verifica sync 2026-08-26**: il run `32951020367` (attempt 2) ha completato checkout `main`,
OIDC e lo step applicativo, ma ha prodotto `technical_failure` con `workspace_id: null`,
`failure_stage: unknown` e `failure_code: bad_request`. Il runner non ha quindi risolto il
workspace tramite `/workspaces`; la schermata Fabric che mostra GitHub e il branch corretto
conferma la configurazione Git dell'utente, ma non la visibilita' del workspace per l'identita'
OIDC. S1-03 resta aperto: serve verificare l'accesso API del Deploy SP al workspace e migliorare
la classificazione dello stage `workspace` prima di un nuovo run. **Superato**: la causa era il
workspace non ripulito, e il rail e' stato poi validato dal run `32955618009` registrato in S1-03.

**Evidenza membership 2026-08-26**: nel pannello Manage access di `ws_agentic_feature_wi6`
il service principal `fabric-agentic-deploy` risulta presente con ruolo `Contributor`. La
membership conferma l'accesso applicativo al workspace, ma non spiega ancora perche' la ricerca
via `/workspaces` del run non lo abbia restituito; resta da verificare il comportamento API e,
come controllo discriminante, un `Update from Git` manuale nel medesimo workspace.

**Riparazione system files 2026-08-26**: il branch collegato conteneva i cinque artifact, ma i
`.platform` di `CRM Demo.Report` e `CRM Demo.SemanticModel` non avevano il campo root obbligatorio
`version: "2.0"`; i notebook lo avevano gia'. Il campo e' stato aggiunto ai due artifact Power BI
e validato insieme a `logicalId` e JSON parsing. La correzione deve essere pubblicata sulla branch
feature prima di ripetere `Update from Git`.

**Seconda riparazione system files 2026-08-26**: l'errore e' rimasto dopo l'aggiunta della versione
root. Tutti i cinque `.platform` usavano inoltre uno `$schema` non conforme al formato Fabric V2
documentato. Il riferimento e' stato uniformato a
`https://developer.microsoft.com/json-schemas/fabric/platform/platformProperties.json`, mantenendo
versione root e `logicalId`; i cinque file passano il parsing JSON e il controllo strutturale.

**Rimozione Power BI 2026-08-26**: su richiesta sono stati eliminati dal Git provider il report
`CRM Demo`, il semantic model `CRM Demo` e il contenitore `CRM Demo.pbip`, inclusi i rispettivi
file di definizione. I tre notebook Fabric restano nel branch. Dopo il push va ripetuto `Update
from Git` nel workspace per applicare la rimozione degli artifact Power BI.

**Allineamento workspace feature 2026-08-26**: `nb_ingest_pagamenti` appartiene a
`ws_agentic_dev`, non a `ws_agentic_feature_wi6`. La directory del notebook e' stata quindi
rimossa dalla feature branch collegata, mentre il notebook resta nel progetto principale per
l'esecuzione in `ws_agentic_dev`. `Update from Git` nel workspace feature va ripetuto dopo il push.

**Rimozione notebook CRM dalla feature branch 2026-08-26**: dopo la rigenerazione dei file
`.platform`, Fabric ha continuato a segnalare `nb_crm_load.Notebook` e
`nb_crm_preflight.Notebook` come system files corrotti. Le due directory sono state quindi
rimosse dalla feature branch collegata; i notebook CRM restano su `main` e non vengono rimossi
dal progetto DEV. Il workspace feature non contiene piu' artifact notebook da sincronizzare.

---

### S1-03 · Rail: sync workspace

| | |
|---|---|
| **Esecutore** | Umano + script |
| **Taglia** | M |
| **Dipendenze** | S1-02 |
| **RF** | RF-15, RF-16 |

**Obiettivo**: materializzare nel workspace lo stato del branch.

**Criteri di accettazione**
- Contratto rispettato
- Idempotente: senza differenze, non fa nulla
- Riporta gli item aggiornati e segnala quelli divergenti

**Esito 2026-08-21**: verificato con successo dal run GitHub Actions `32488530726` sul work
item `6`. Il workspace risultava già allineato al branch; il rail ha restituito
`already_aligned`, nessun item aggiornato e nessuna divergenza.

**Esito finale 2026-08-26**: dopo la pulizia degli artifact corrotti nel workspace, il run
`32955618009` ha restituito `outcome: success`, workspace `ws_agentic_feature_wi6` risolto,
`status: synchronized`, `updated_items: []` e nessun `failure_stage` o `failure_code`. Il rail
`sync_workspace` e' quindi validato sul work item `6` a partire da uno stato pulito.

**Correzione CRM preflight 2026-08-26**: il run `32955814916` ha fallito durante l'esecuzione
del notebook `nb_crm_preflight`. Il notebook usava l'ambiente Dataverse errato
`org4009cd0e`, mentre `configuration/crm_demo.json` e la connessione validata usano
`org12202591`. L'endpoint e' stato corretto nel notebook e coperto da un test di regressione;
il preflight deve essere rilanciato dal workflow ancorato a `main` dopo la pubblicazione della
modifica.

**Diagnostica preflight 2026-08-26**: il run `32956308346` ha confermato un fallimento durante
la run del notebook anche con l'endpoint corretto, ma l'artefatto esponeva solo il messaggio
generico `Fabric long-running operation failed`. Il runner ora conserva soltanto il nome
dell'operazione, lo stato (`Failed`/`Cancelled`) e il codice tecnico Fabric, escludendo il
response body; la suite mirata passa con 7 test.

**Correzione binding Lakehouse 2026-08-26**: l'esecuzione successiva ha fallito nel notebook
runtime (`Fabric notebook run failed`) e il notebook mostrava `No data sources added`. Il runner
creava `lh_bronze_crm_demo` ma non lo passava alla definizione del notebook e non aggiornava la
definizione quando l'item esisteva gia'. Il preflight ora associa esplicitamente il Lakehouse
predefinito e aggiorna sempre la definizione prima dell'avvio; il test mirato passa con 7 test.

---

### S1-04 · Ticket agentico: ingestion `pagamenti`

| | |
|---|---|
| **Esecutore** | **Agente** |
| **Taglia** | M |
| **Dipendenze** | S1-00, S1-02, S1-03, S0-14 |
| **RF** | RF-10..RF-20, RF-50, RF-84 |

**Obiettivo**: il primo ticket reale del progetto, eseguito dall'agente su dati sintetici nel
workspace `ws_agentic_dev`.

**Esito 2026-08-25**: il notebook `nb_ingest_pagamenti` è stato pubblicato ed eseguito con
successo. Run ID `20260825T141929Z-70aacec7`: 10 righe caricate, 10 righe in destinazione,
`pk_check: passed`, `reconciliation: passed`. La durata osservata è 21 s; il costo monetario
della capacity non è attribuibile dal run e non viene stimato. La PR #78 è stata mergiata.

**Descrizione del ticket** *(da scrivere secondo `docs/functional/02`)*

> **Obiettivo**: il dataset sintetico `pagamenti` è disponibile nel layer Bronze del feature
> workspace, con carico verificato e configurazione dichiarativa.
>
> **Criteri di accettazione**
- Trigger A: work item in *To Do* con tag `dev-agent`
- Trigger B: nuovo commento **umano** su work item in *Doing* con tag `waiting-input`
- Trigger C: thread **non risolti** sulla PR dell'agente
> - Il feature workspace è ottenuto tramite `branch_out` e allineato tramite `sync_workspace`
> - Source system: `pagamenti_demo`; connettore: File/CSV; dataset: `pagamenti`
> - Sorgente: `attachments/72/pagamenti.csv`
> - Chiave primaria: `ID_Pagamento`; watermark: `Data`
> - Chiavi primarie, modalità di carico, watermark ed endpoint sono dichiarati nella configurazione
> - Il carico è eseguito nel feature workspace e le evidenze qualità sono allegate alla PR
> - La documentazione della sorgente e del dataset è aggiornata
> - `CHANGELOG.md` contiene la voce
>
> **Fuori scope**: `test`, `prod`, semantic model, report e modifiche al
> framework condiviso. Il ticket non parte finché S1-00 non è chiuso.

**Criteri di accettazione del work item (lato sistema)**
- Il ticket è preso in carico entro un ciclo di polling
- L'agente crea branch e feature workspace conformi tramite i rail
- L'agente apre la PR con evidenza di esecuzione e qualità dati
- **Nessun intervento tecnico umano** durante il ciclo
- La PR è mergiata dall'owner

> La review di questa PR è **umana**: il Review Agent entra in gioco dallo Slice 3. Va detto
> esplicitamente nel ticket, altrimenti l'agente resterà in attesa di un revisore che non arriva.

---

### S1-05 · Retrospettiva del primo ciclo

| | |
|---|---|
| **Esecutore** | Umano |
| **Taglia** | S |
| **Dipendenze** | S1-04 |
| **RF** | KPI-1, KPI-2, KPI-5 |

**Obiettivo**: capitalizzare il primo giro reale prima di procedere.

**Criteri di accettazione**
- Rilevati: lead time, consumo token, numero di interventi umani non previsti
- Ogni intervento umano non previsto è tracciato come difetto del sistema, **non assorbito**
- Le lacune emerse nella knowledge base sono colmate
- Ogni ambiguità che ha bloccato l'agente è recepita in `CONTEXT.md` o nei runbook

> Le decisioni prese a voce durante questo primo ciclo e non scritte **si ripresenteranno
> identiche** al ticket successivo. La retrospettiva serve esattamente a impedirlo.

**Esito 2026-08-25**: completata in `docs/technical/10-retrospettiva-s1-04.md`. Il ciclo ha
confermato KPI-7 a zero e nessun difetto post-merge osservato; KPI-1, KPI-2, KPI-3 e KPI-5 restano
parziali o non misurabili per gap di strumentazione esplicitamente registrati. Gli interventi
tecnici umani necessari sono stati classificati come difetti del sistema e corretti nei rail.

---

## Riepilogo

| Slice | Item | Umani | Agentici | Criterio di uscita |
|---|---|---|---|---|
| **S0** | 15 | 15 | 1 (smoke test) | S0-14 verde |
| **S1** | 6 | 5 | 1 | Tracer bullet CRM `accounts` completato da un ticket |

### Percorso critico

```
S0-04 (identità · richiede amministratore)
  → S0-05 (permessi tracker)
    → S0-06 (branch policy + VERIFICA)
      → S0-09 (dispatcher Dev)
        → S0-14 (smoke test)
          → S1-04 (primo ticket agentico)
```

**Il vincolo è S0-04**: richiede un amministratore di tenant. Va prenotato in anticipo, tutto il
resto dipende da lì.

### Item non negoziabili

| Item | Perché |
|---|---|
| **S0-06** | Se non è verde, nessun agente va avviato |
| **S0-14** | Separa i problemi della catena da quelli di Fabric |
| **S1-05** | Senza retrospettiva, gli stessi blocchi si ripresentano a ogni ticket |
