# 02 — Dispatcher

> Il componente che decide **quando** un agente deve svegliarsi. È volutamente il pezzo più
> stupido dell'intero sistema.

---

## 1. Il principio

> **Il modello non fa polling. Il polling lo fa uno script.**

Il dispatcher è un processo deterministico, senza LLM, che interroga periodicamente il tracker e
avvia una sessione **solo quando c'è effettivamente qualcosa da fare**.

Il risultato della sessione viene verificato: un exit code non riuscito produce un errore esplicito
(`Dev Agent session failed`) dopo la persistenza del dispatch. Il ciclo non viene quindi registrato
come completato con successo e lo stato conserva l'ID già assegnato per evitare duplicazioni. Il
log della sessione classifica inoltre l'esito come `productive`, `no_work` o `failed`, così una
sessione terminata senza modificare la clone non è più indistinguibile da una riuscita produttiva.

Per GitHub il handoff include il body dell'issue. Gli allegati destinati all'automazione sono
versionati in `attachments/<issue-number>/` e vengono letti direttamente dalla clone isolata;
non si dipende dal download degli URL `user-attachments`, che non ha un endpoint GitHub App
documentato. Ogni file è limitato a 10 MiB; token e contenuti non entrano nei log.

Conseguenza diretta: a sistema fermo il costo è **zero**. Se il polling fosse affidato al modello,
pagheresti token per scoprire ripetutamente che non c'è nulla da fare — che è la condizione in cui
il sistema si trova per la maggior parte del tempo.

---

## 2. Architettura

Un dispatcher **per agente**, in esecuzione nel rispettivo ambiente isolato.

| Aspetto | Valore |
|---|---|
| Frequenza di polling | ~30 secondi |
| Autenticazione | Con il service principal **del proprio agente**, mai un'identità condivisa |
| Gestione del token | Ottenuto per client credentials, in cache, rinnovato a ogni ciclo e a ogni avvio di sessione |
| Concorrenza | Una sola sessione attiva per agente: se una sessione è in corso, il ciclo di polling non ne avvia un'altra |
| Persistenza | Nessuna: lo stato è nel tracker |

### Ciclo di vita

```mermaid
flowchart LR
    P[Polling] -->|nessun trigger| P
    P -->|trigger rilevato| T[Rinnovo token]
    T --> S[Avvio sessione headless]
    S --> W[Attesa termine sessione]
    W --> P

    style P fill:#eef2f7,stroke:#7a8ba6
    style S fill:#fbe9e7,stroke:#c0553b
```

**Ogni sessione è nuova.** Il dispatcher non passa contesto tra una sessione e la successiva:
tutto ciò che serve viene riletto dal tracker e da Git.

### Implementazione corrente

`scripts/dev_dispatcher.py` è il dispatcher locale del Dev Agent. Viene eseguito come
`python -m scripts.dev_dispatcher` e legge la configurazione non segreta fuori dal repository in
`%USERPROFILE%\.fabric-agentic\dev-agent\dispatcher-config.json`. Il token Azure DevOps viene
acquisito al bisogno con il certificato client non esportabile del Dev Agent; i task e lo stato
anti-duplicazione vivono nella stessa directory locale, mai nel repository.

I trigger A, B e C sono implementati e il comando `--once --dry-run` è stato verificato il
2026-08-21: ha rilevato il work item `#6` senza creare task, avviare Claude o modificare Azure
Boards/GitHub. Trigger B ignora commenti dell'agente e già osservati; Trigger C ignora thread
risolti e già osservati. Il comando `--poll` esegue il ciclo alla frequenza configurata e scrive
metadati JSONL sicuri (ID work item, trigger, esito, durata) nel perimetro locale; non registra
token, credenziali o output della sessione. Resta da verificare il lancio operativo controllato
con lo smoke S0-14.

La classificazione viene scritta nell'evento `session_completed` insieme a exit code, errore,
identificativo sessione, numero di turni e `changed_repository`; non viene registrato l'output
integrale di Claude.

La sessione Dev Agent usa una allowlist versionata in `DEV_AGENT_ALLOWED_TOOLS`: consente lettura,
modifica, test, branch, commit, push esclusivamente verso `refs/heads/feature/*` e apertura di
pull request. Usa `dontAsk`, non `acceptEdits` e non `bypassPermissions`; il comando viene costruito
da `build_session_command` e verificato dai test. La credenziale necessaria al push e a `gh` viene
fornita da un broker localhost avviato dal dispatcher: il token resta nella memoria del dispatcher,
mentre helper temporanei per Git e `gh` lo richiedono per singola operazione. Il token non entra nel
comando Claude, nelle variabili `GH_TOKEN`/`GITHUB_TOKEN`, nei file del repository o nei log. Il
push autorizzato è solo verso `refs/heads/feature/*`; il merge e il push su `main` restano fuori
dall'allowlist. Il broker installa inoltre un `pre-push` hook in una directory temporanea esterna
al repository e lo impone con configurazione Git di processo: anche il vero `git.exe` rifiuta il
ref `main` prima del remote. L'hook viene reso eseguibile, perché Git ignora silenziosamente un
hook senza permesso di esecuzione; gli shim di `gh` e dell'askpass sono generati sia in forma
`.cmd` sia in forma POSIX. Nell'ambiente di sessione `credential.helper` viene azzerato, così la
sessione può autenticarsi solo con il token intermediato dal broker e non con credenziali
ambientali dell'utente.

Il broker vive in `scripts/credential_broker.py` ed è **condiviso dai tre agenti**, non duplicato.
Anche Review e Issue preparano la clone al suo interno, con il token della propria GitHub App: le
operazioni Git sono quindi attribuite all'identità dell'agente e i dispatcher non dipendono dalle
credenziali della macchina.

`scripts/review_dispatcher.py` è il dispatcher locale del Review Agent. La modalità
`--once --dry-run` interroga le PR aperte tramite la GitHub App dedicata, ignora le PR in draft e
gli head SHA già revisionati dall'identità applicativa, e non avvia sessioni né scrive su GitHub.
La configurazione e la clone sono esterne al repository; lo state locale indicizza numero PR e
head SHA. La modalità operativa prepara la clone, crea un solo task, avvia una sessione nuova nella
clone Review e consegna l'esito al publisher di #97; un lock locale impedisce sessioni concorrenti.

La preparazione della clone allinea `main` a `origin/main` e recupera l'head della PR in
`refs/remotes/origin/pr/<n>` **senza cambiare branch**: la sessione vede il diff reale e la copia di
pubblicazione resta allineata come richiede il publisher. Il publisher viene invocato come modulo
(`-m scripts.review_vote_publish`), non come percorso di file.

**Verifica sul campo 2026-08-27**: eseguito `--once --dry-run` contro il repository reale dalla
clone dedicata; risultato `{"tasks": []}`, exit code `0`. Non sono stati creati state file, task
directory o lock.

**Smoke end-to-end 2026-08-31**: sulla PR usa-e-getta #130 il ciclo completo è riuscito senza
intervento umano — discovery, preparazione clone, sessione, esito A1-F4, pubblicazione. Il voto
registrato è `CHANGES_REQUESTED` con 6 rilievi, autore `fabric-agentic-review-agent` e commit
coincidente con l'head della PR. Una seconda esecuzione sullo stesso head non ha prodotto candidati.
La PR e la branch di probe sono state chiuse e rimosse senza merge.

Il primo tentativo ha fallito e ha rivelato due difetti reali, entrambi corretti: il publisher era
invocato come percorso file e rompeva gli import di pacchetto; la clone non conteneva il commit
della PR, quindi la sessione non poteva leggere il diff.

### Smoke S0-14

La modalità `--smoke-work-item-id <id>` avvia una singola sessione Claude con il solo tool
`Read`. La sessione legge il task e quattro documenti di contesto obbligatori, poi restituisce un
JSON con l'elenco dei documenti letti. Il dispatcher, non il modello, pubblica il commento
marcato `fabric-agentic-dev-agent` e porta il work item a `Done` tramite il token Azure DevOps
del Dev SP. In questo smoke non sono consentiti Git, scritture file, Fabric, token o credenziali.

**Verifica sul campo 2026-08-21**: lo smoke sul work item Azure Boards `#7` ha completato
`To Do` → `Doing` → `Done`. Claude ha restituito task record, `CONTEXT.md`, `AGENTS.md`,
`01-ciclo-di-vita-ticket.md` e `02-come-scrivere-un-ticket.md`; il commento è stato pubblicato
da `fabric-agentic-dev-agent`. Il log locale contiene solo work item e documenti letti, senza
token o credenziali.

### Compatibilità Windows

Lo stato locale del dispatcher accetta UTF-8 con o senza BOM. Questo consente di inizializzare o
ispezionare lo state file con PowerShell senza far fallire il ciclo; lo state resta fuori dal repo
e contiene solo identificativi di work item, commenti e thread già osservati.

`scripts/issue_dispatcher.py` è il dispatcher locale dell'Issue Agent. La coda è una **issue di
intake** etichettata `issue-agent`, aperta, non ancora approvata e senza pacchetto già pubblicato.
La sessione produce il pacchetto di lavoro; il rail deterministico `scripts/issue_package_publish.py`
ne valida la struttura e pubblica **un solo commento** con l'identità applicativa dedicata. Il rail
non crea, non modifica e non chiude alcun work item: il pacchetto è una proposta e il ticket nasce
solo dopo l'approvazione umana, che applica l'etichetta `dev-agent`. Vedi ADR-0014.

Finché l'identità dedicata non è provisionata, `configuration/issue_dispatcher.json` contiene
identificativi a zero e il dispatcher si arresta con `the Issue Agent identity is not provisioned`
invece di tentare una chiamata con una credenziale inesistente.

**Identità verificata 2026-08-31**: App `fabric-agentic-issue-agent`, installazione limitata al solo
repository, permessi effettivi `contents:read`, `issues:write`, `metadata:read`. Il login del bot
viene letto dinamicamente da `/app`, quindi il rail non dipende da un nome scritto a mano.

Il pacchetto può essere preceduto da prosa della sessione: il rail individua l'intestazione e scarta
quanto la precede, come già fa il publisher del voto di review. Restano rifiutati intestazione
assente, modalità sconosciuta, sezioni mancanti, duplicate, fuori ordine o vuote.

**Smoke end-to-end 2026-08-31**: sull'intake usa-e-getta #134 il ciclo completo è riuscito senza
intervento umano — discovery, preparazione clone, sessione, pacchetto, pubblicazione. Esito
`status: published`, modalità `Work Item Design`, commento firmato `fabric-agentic-issue-agent` con
marcatore e fingerprint. Tutte e sette le sezioni del contratto sono presenti. Una seconda
esecuzione non ha prodotto candidati. **Nessun work item è stato creato**: il rail ha pubblicato
solo il commento, come previsto da ADR-0014.
---

## 3. Trigger del Dev Agent

Tre condizioni, valutate a ogni ciclo:

| # | Trigger | Condizione |
|---|---|---|
| **A** | Nuovo lavoro | Work item in stato *To Do* con il tag riservato al Dev Agent |
| **B** | Risposta umana | Nuovo commento su un work item in *Doing* con tag `waiting-input` e `dev-agent` |
| **C** | Rilievo di review | Thread attivi non risolti sulla PR aperta dall'agente |

### Note di progettazione

- Il **tag** è il meccanismo di delega esplicita: senza tag, il ticket è invisibile al sistema.
  Serve anche a compensare il fatto che il tracker non consente di assegnare un work item a
  un'identità applicativa.
- Il trigger B si attiva solo su commenti **umani**: al risveglio il dispatcher rimuove il tag
  `waiting-input`; i commenti prodotti dall'agente stesso non
  devono risvegliarlo, altrimenti si innesca un ciclo infinito.
- Il trigger C richiede di distinguere i thread **risolti** da quelli aperti, altrimenti l'agente
  riprocessa all'infinito rilievi già gestiti.

> Questi due ultimi punti sono le cause più probabili di loop. Vanno verificati esplicitamente
> nei test dello Slice 0/1, non scoperti in esercizio.

---

## 4. Trigger del Review Agent

**Uno solo**, deliberatamente:

| # | Trigger | Condizione |
|---|---|---|
| **1** | PR da revisionare | Pull request attiva in cui il voto del Review Agent **non** è "approvato" |

Una sola regola copre entrambi i casi: la prima review e ogni re-review dopo una nuova push
(che azzera il voto precedente).

> Tre trigger per il Dev Agent, uno per il Review Agent. L'asimmetria riflette i ruoli: lo
> sviluppatore reagisce a più sorgenti di lavoro, il revisore ha un solo compito e una sola
> condizione di attivazione. Meno stati, meno modi di sbagliare.

---

## 5. Trigger dell'Issue Agent

**Uno solo**, come per il Review Agent:

| # | Trigger | Condizione |
|---|---|---|
| **1** | Intake da istruire | Issue aperta con etichetta `issue-agent`, senza etichetta `dev-agent` e senza pacchetto già pubblicato dall'identità dell'Issue Agent |

### Note di progettazione

- Il commento del pacchetto è anche il **marcatore di completamento**: l'agente non può risvegliarsi
  sul proprio artefatto, quindi il loop è chiuso per costruzione come per il trigger B del Dev Agent.
- L'etichetta `dev-agent` esclude l'intake dalla coda: significa che il pacchetto è già stato
  approvato e il lavoro appartiene al Dev Agent.
- Il dispatcher può proporre, non decidere. La trasformazione da proposta a lavoro resta l'unico
  passaggio umano obbligatorio della catena.

---

## 6. Gestione dei token e delle credenziali

| Aspetto | Regola |
|---|---|
| Ottenimento | Credenziale verso il tracker (PAT Azure DevOps, certificato GitHub, ecc.) |
| Cache | Su file, nel perimetro dell'agente (mai nel repo) |
| Rinnovo | A ogni ciclo di polling e all'avvio di ogni sessione |
| Accesso a tracker | Il dispatcher accoda pipeline CI/CD per nome |
| Accesso a Fabric | **Nessuno diretto**: le pipeline usano la loro identità (OIDC o deploy SP) |

> **Cambio di modello**: il Dev Agent non conserva credenziali Fabric, solo credenziali verso il
> tracker. Chi tocca Fabric è l'identità della pipeline, che l'agente non può impersonare.
| Durata | La sessione dell'identità applicativa sul control plane dati ha vita limitata: va rinnovata a ogni avvio, mai riusata tra sessioni |
| Esposizione | **Mai** in log, output, commenti o messaggi. La lettura delle variabili d'ambiente e della cache è negata all'agente |

> Un token stampato in un log finisce nella cronologia della sessione, e da lì in qualunque
> artefatto che la citi. Va trattato come compromesso anche se scade in un'ora.

---

## 7. Osservabilità

Ogni sessione produce un log persistente, correlabile a work item e PR.

| Informazione | Obbligatoria |
|---|---|
| Identificativo di sessione | Sì |
| Trigger che l'ha attivata | Sì |
| Work item e PR di riferimento | Sì |
| Esito (completata, bloccata, fallita) | Sì |
| Consumo token stimato | Sì — alimenta il KPI di costo |
| Durata | Sì — alimenta il KPI di lead time |

**Nel log non compaiono mai**: token, credenziali, contenuti di variabili d'ambiente.

---

## 8. Modalità di esercizio

| Aspetto | Fase 1 | Fase 2 |
|---|---|---|
| Collocazione | Macchina locale dell'owner | Hosting dedicato (Q-7) |
| Disponibilità | Solo a macchina accesa | Continua |
| Avvio | Manuale | Servizio gestito |

> Limite noto della fase 1: se la macchina è spenta, i ticket restano in coda. È accettabile per
> un asset interno e per la demo; **non** lo è per un impegno di servizio verso un cliente.
> È il vincolo che rende Q-7 bloccante per l'uso commerciale reale.

---

## 9. Fallimenti e comportamento atteso

| Situazione | Comportamento del dispatcher |
|---|---|
| Tracker irraggiungibile | Ritenta al ciclo successivo, registra a log, non avvia sessioni |
| Ottenimento del token fallito | Ritenta con attesa crescente, poi si arresta con errore esplicito |
| Sessione terminata in errore | Registra l'esito e torna in polling. **Non rilancia automaticamente**: un rilancio cieco può ripetere l'errore all'infinito |
| Sessione bloccata oltre una soglia di durata | La interrompe e registra l'evento come anomalia |

> Il dispatcher **non interpreta** gli errori dell'agente: li registra. L'interpretazione è
> lavoro dell'agente o dell'owner. Un dispatcher che prova a essere intelligente diventa un
> secondo punto di decisione non tracciabile.
