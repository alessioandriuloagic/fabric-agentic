# 04 — Identità e permessi

> Il perimetro reale del sistema. Le istruzioni testuali descrivono il comportamento atteso;
> **i permessi determinano quello possibile**.

Decisioni applicate: [ADR-0007](../adr/ADR-0007-pipeline-cicd-come-rail.md) e
[ADR-0008](../adr/ADR-0008-permessi-fabric-dev-agent.md).

---

## 1. Il principio

> **Ciò che un agente può tecnicamente fare, prima o poi lo farà.**

Non per malizia: per la natura probabilistica del modello, per un ticket formulato male, per una
situazione non prevista. Ogni capacità concessa "tanto non la userà mai" va considerata come
capacità che verrà usata.

Ne discendono due regole operative:

1. Ogni limite che conta deve essere imposto **dalla piattaforma**, non dal prompt.
2. Ogni limite imposto deve essere **verificato praticamente**, non solo configurato.

---

## 2. Identità

| Agente | Identità |
|---|---|
| Dev Agent | Service principal dedicato |
| Review Agent | Service principal dedicato, **distinto** |
| Deploy pipeline | Service principal dedicato, distinto dagli agenti; esegue i rail con OIDC GitHub |
| Dispatcher | Nessuna propria: usa quella dell'agente che serve |
| `ExecutionCredential` | Credenziale tecnica **del cliente**, disponibile solo alle pipeline CI/CD |

### Regole

| Regola | Motivo |
|---|---|
| Un service principal **per agente**, mai condiviso | Se condiviso, l'audit log non distingue chi ha fatto cosa e i permessi si sommano al massimo comune |
| Nessun agente gira con un'identità umana | L'attribuzione delle azioni deve restare inequivocabile |
| Credenziali solo nel secret store | Mai in file di configurazione, mai nel repo |
| Le identità sono raccolte in un **gruppo di sicurezza dedicato** | Gli switch di tenant si applicano al gruppo, non al mondo |
| La `ExecutionCredential` non è un'identità dell'agente | L'agente può accodare una pipeline ma non leggere, esportare o impersonare il segreto cliente |
| L'organizzazione Azure DevOps è associata al tenant Fabric | I service principal del Dev Agent e Review Agent sono nel tenant Agic Dev e devono poter accedere a Boards senza identità duplicate cross-tenant |
| Il deploy usa un'identità distinta | `fabric-agentic-deploy` esegue i rail; Dev Agent e Review Agent non possono impersonarla |
| Assegnazione alla capacity | Pattern verificato in `IP.dai_fabric_environments`: deploy SP con Azure RBAC `Contributor` sulla risorsa capacity **e** Object ID presente in `properties.administration.members`. Entrambi sono necessari per `assignToCapacity`; non dedurre ruoli ulteriori dal solo errore API |
| Credenziale tracker Dev Agent | Certificato client non esportabile nell'utente Windows dell'owner. Il dispatcher acquisisce token Entra brevi per `https://app.vssps.visualstudio.com/.default`; nessun PAT o client secret nel repo o nel runtime del modello |
| Credenziale GitHub Dev Agent | GitHub App installata sul solo repository `alessioandriuloagic/fabric-agentic`. Il dispatcher firma un JWT con una private key PEM locale protetta da ACL e ottiene un installation token breve; App ID e Installation ID non sono segreti, la private key non entra nel repository o nei log |
| Token GitHub Dev Agent | `scripts/github_app_auth.py` firma un JWT valido nove minuti e ottiene un installation token solo in memoria. Il comando `verify` può mostrare i repository autorizzati, mai token o contenuto PEM |
| Verifica PEM GitHub App | Il record della key nella UI GitHub prova solo che la key e' registrata. Prima di avviare il dispatcher, il file PEM locale deve esistere, avere ACL dell'owner, dimensione plausibile e caricarsi per la firma JWT; non si stampa o archivia mai il suo contenuto o hash |
| Credenziale GitHub Review Agent | GitHub App **distinta** da quella del Dev Agent, `fabric-agentic-review-agent`, App ID `4735692`, Installation ID `156937328`, installata sullo stesso repository con i soli permessi `contents:read`, `issues:read`, `metadata:read`, `pull_requests:write`. App ID e Installation ID non sono segreti; la private key PEM è in `%USERPROFILE%\.fabric-agentic\review-agent\github-app-private-key.pem`, con ACL dell'owner, e resta fuori dal repository, dai log e dal runtime del modello |
| Token GitHub Review Agent | `scripts/review_vote_publish.py` conia l'installation token al momento della pubblicazione, riusando `scripts/github_app_auth.py`, e lo tiene solo in memoria di processo. La sessione di review non conia token, non firma il JWT e non conosce il percorso della key |

> L'ultimo punto è spesso trascurato: abilitare la creazione di workspace via identità applicativa
> a livello di tenant senza restringerla a un gruppo significa concederla a **tutte** le
> applicazioni del tenant, non solo alle nostre.

### 2.1 Identità GitHub del Review Agent

Il voto di review è un oggetto GitHub, non un testo: GitHub rifiuta `REQUEST_CHANGES` sulla propria
pull request. Finché la sessione girava con l'identità umana dell'owner il voto non poteva esistere
(`Review Can not request changes on your own pull request`, osservato su PR #94 e #95, con
`gh pr view <n> --json reviews` vuoto in entrambi i casi). L'identità applicativa dedicata rende il
voto registrabile e attribuibile.

| Aspetto | Regola |
|---|---|
| Chi vota | L'identità applicativa del Review Agent, mai l'owner umano e mai l'identità del Dev Agent |
| Chi pubblica | Il publisher deterministico `scripts/review_vote_publish.py`, non il modello |
| Cosa riceve il modello | Nulla di credenziale: produce l'esito A1-F4 e termina |
| Dove vive la key | File PEM fuori dal repository, con ACL ristretta, come per il Dev Agent |

#### Rischio accettato — collocazione della private key

La private key del Review Agent **può risiedere sotto lo stesso utente Windows del Dev Agent**. In
quella configurazione la separazione fra le due identità è dichiarativa: un processo che gira con
quell'utente può leggere entrambe le key, quindi la separazione dei permessi GitHub non è sostenuta
da un confine tecnico.

> **Questa è una mitigazione dichiarata come rischio accettato dall'owner, non un isolamento
> tecnico.** La risoluzione reale è un utente OS separato o un host separato per il Review Agent.
> Fino ad allora l'ACL sul file e la separazione dei processi valgono come misura organizzativa,
> e vanno rilette a ogni revisione periodica (sezione 7).

È lo stesso principio della sezione 1 applicato a noi stessi: ciò che un processo può tecnicamente
leggere, prima o poi lo leggerà. Registrarlo come rischio accettato lo rende revisionabile; ometterlo
lo renderebbe invisibile.

---

## 3. Matrice dei permessi

### Verifica operativa 2026-08-25

L'owner conferma che il Dev Agent ha ruolo `Viewer` su `ws_agentic_dev` e che il Review Agent non
ha alcun accesso Fabric. Questa conferma non sostituisce le prove negative richieste per verificare
che il Dev Agent non possa creare workspace, scrivere item o avviare job.

La prova API del Service Principal Dev Agent ha ottenuto un token nel tenant corretto con audience
`https://api.fabric.microsoft.com` e la GET del workspace ha restituito HTTP `200`: la lettura
Viewer è verificata. Un POST di creazione workspace ha però restituito HTTP `201`; la risorsa di
probe è stata eliminata immediatamente. Il setting tenant di creazione deve essere ristretto al
gruppo `FabricAgentDeploy` prima di ripetere le prove di scrittura. Il portale Entra mostra il
Dev Agent come membro diretto. Nel probe successivo la GET workspace ha restituito HTTP `200`,
mentre il POST di creazione è stato negato con HTTP `401` e non ha creato risorse; il blocco sembra
applicato, ma va riconfermato con il Deploy SP e il codice `403` non è stato osservato.

### 3.1 Dev Agent

> **Rivisto dopo la review architetturale** (`07-architecture-review.md`, ADR-0008). Il Dev
> Agent **non tocca Fabric in scrittura**: agisce invocando pipeline CI/CD. Chi tocca Fabric è
> l'identità della pipeline, che l'agente non può impersonare.

| Ambito | Permesso | Note |
|---|---|---|
| Repo soluzione | Contribuisci, crea branch, contribuisci alle PR | Nessun permesso su `main` |
| Knowledge base | Contribuisci | La documentazione atterra direttamente |
| Work item | Lettura e scrittura | Serve per stato e commenti |
| **Accodamento pipeline CI/CD** | Consentito **solo sulle pipeline agentiche**, per nome | Vedi sezione 3.3 |
| **Lettura artefatti di pipeline** | Consentita | È il **canale primario** dell'esito |
| **Diagnostica dati** | Consentita solo via `pipe_agent_diagnose_data` | Riceve evidenze aggregate o mascherate, non righe grezze né segreti |
| Fabric — lettura | **`Viewer`, condizionato** | Solo su feature workspace e `dev`, solo come **eccezione diagnostica**, solo con dati non riservati |
| **Creazione workspace Fabric** | **NEGATO** | La creazione avviene tramite pipeline. Verifica: la chiamata di creazione con l'identità dell'agente **deve fallire** |
| **Scrittura su Fabric** | **NEGATO** | Nessun ruolo Contributor, Member o Admin su alcun workspace |
| **Capacity** | **NEGATO** | Non serve più: assegna la pipeline |
| **Push su `main`** | **NEGATO** | Deny esplicito **e** branch policy |
| **Merge** | **NEGATO** | Approvazione umana obbligatoria |
| **Accodamento pipeline verso test/prod** | **NEGATO** | Pipeline distinte, non accodabili dall'agente |
| **Variabili d'ambiente / cache token / archivio certificati** | **NEGATO** | Deny attivo anche in modalità non interattiva |
| **Modifica di permessi, policy, identità** | **NEGATO** | Vedi sezione 5 |

### Verifica pratica 2026-08-27 — Review Agent

La prova runtime con l'installation token della GitHub App `fabric-agentic-review-agent` ha
restituito `GET /repos/alessioandriuloagic/fabric-agentic` **HTTP 200** e il tentativo di
creare un ref tramite `POST /repos/alessioandriuloagic/fabric-agentic/git/refs`
**HTTP 403**. Il payload usava lo SHA volutamente inesistente `000000...000`; il ref
`refs/heads/review-agent-negative-probe-20260827` non è stato creato. Il divieto di
`contents:write` è quindi dimostrato senza side effect.

Per il merge è stata aperta la PR usa-e-getta #109 dalla branch
`review-agent-merge-probe-20260827`. Il tentativo `PUT /repos/alessioandriuloagic/fabric-agentic/pulls/109/merge`
con la stessa identità ha restituito **HTTP 403**, `merged: false`; la PR e la branch di probe
sono state poi chiuse e rimosse con l'identità umana, senza merge.
La private key è stata solo caricata dal percorso locale protetto; nessun token, JWT o contenuto
PEM è stato stampato o registrato.

**Evidenza workspace 2026-08-27**: la UI del workspace mostra `fabric-agentic-deploy` come
`Contributor`, `fabric-agentic-dev-agent` come `Viewer` e nessuna assegnazione per
`fabric-agentic-review-agent`. Questa evidenza conferma i ruoli/membership del workspace; non
sostituisce i probe runtime su scrittura, creazione item o avvio job.

**Probe runtime 2026-08-27**: con il contesto Azure autenticato come `fabric-agentic-dev-agent`
nel tenant Agic Dev, la GET di `ws_agentic_dev` ha restituito HTTP `200`. La POST di creazione
workspace con payload volutamente invalido `{}` ha restituito HTTP `401`, senza creare risorse.
Un tentativo di creazione item con tipo invalido ha restituito HTTP `400` e un avvio job su item
inesistente HTTP `404`: entrambi sono probe non conclusivi per il permesso di scrittura. La lettura
di `admin/tenantsettings` con audience Power BI ha restituito HTTP `404`; gli switch tenant restano
da verificare dal portale amministrativo corretto.

#### Sul ruolo `Viewer` — condizione d'uso

Il `Viewer` è l'unico ruolo Fabric realmente di sola lettura: non può eseguire, scrivere,
cancellare né collegare Git. **Ma può leggere i dati** attraverso l'endpoint SQL.

> Ne discende che la concessione va legata alla **classificazione del dato**, non al ruolo
> dell'agente. Con dati sintetici o open data è accettabile. Nel momento in cui l'ambiente
> contenesse dati di cliente, il `Viewer` va revocato — e l'agente torna a dipendere
> esclusivamente dall'artefatto della pipeline.

Regola operativa: **l'artefatto è il canale primario, sempre.** Se l'agente deve interrogare
Fabric per capire com'è andata un'esecuzione, l'artefatto è incompleto: il difetto sta nella
pipeline, non nei permessi.

### 3.2 Review Agent

| Ambito | Permesso | Note |
|---|---|---|
| Repo soluzione | **Sola lettura** + commento e voto | Rimosso dai contributori: la sola lettura va garantita, non solo dichiarata. Il voto è inviato dal publisher deterministico con l'identità applicativa del Review Agent (sezione 2.1), non dalla sessione |
| Knowledge base | Sola lettura | Verifica che la documentazione sia aggiornata |
| Work item | Sola lettura + commento | Non modifica lo stato |
| **Qualsiasi accesso a Fabric** | **NEGATO** | Nessun ruolo su workspace o capacity |
| **Scrittura su repo** | **NEGATO** | Non corregge ciò che revisiona |
| **Push, merge** | **NEGATO** | — |
| **Variabili d'ambiente / cache token** | **NEGATO** | — |

### 3.3 Il privilegio di accodare una pipeline

Lanciare una pipeline CI/CD **è un privilegio**, e va trattato come tale: la pipeline agisce con
la propria identità, molto più potente di quella dell'agente.

| Controllo | Requisito |
|---|---|
| **Separazione per nome** | Due famiglie distinte: pipeline **agentiche** e pipeline **umane**. Il permesso di accodamento è concesso per singola pipeline, non globalmente |
| **Attenzione all'ereditarietà** | Il gruppo dei contributori ha per default il permesso di accodamento su **tutte** le pipeline. Non basta non concederlo: va **negato** esplicitamente, con ereditarietà disattivata |
| **Ancoraggio a `main`** | La definizione della pipeline agentica viene sempre da `main`. Il branch di feature è un **parametro** |
| **Ambiente non parametrico** | Una pipeline agentica punta a un solo ambiente non produttivo. L'ambiente **non** è un parametro scelto da chi accoda |
| **Approvazioni fuori dallo YAML** | I controlli di approvazione e le restrizioni di branch non sono modificabili da chi modifica il file della pipeline |

#### Perché l'ancoraggio a `main` è non negoziabile

> L'agente ha per definizione il permesso di scrivere codice su un branch. Se una pipeline
> privilegiata girasse con la definizione presa da quel branch, **l'agente potrebbe riscrivere
> la pipeline e ottenere i privilegi dell'identità di deploy senza violare un solo permesso**.
>
> È un'escalation che non passa dai permessi ma dal codice — e nessuna matrice di permessi,
> per quanto stretta, la intercetta.

#### Perché l'ambiente non può essere un parametro

Una pipeline che accetta l'ambiente di destinazione come parametro con valori `dev` e `prod`
rende il principio «deploy verso produzione solo umano» aggirabile **da un valore di input**,
non da un permesso. Chi può accodare quella pipeline può deployare in produzione.

---

## 4. Governance del ramo principale

È il controllo su cui poggia tutto il resto. Sul piano GitHub corrente le protection rules non sono
disponibili; il controllo operativo è quindi GitHub Flow obbligatorio e merge umano.

| Controllo | Requisito |
|---|---|
| Push diretto su `main` | Vietato dal processo a **entrambi** gli agenti; enforcement tecnico non disponibile sul piano corrente |
| Pull request | Obbligatoria per ogni modifica |
| Approvazione umana | Obbligatoria, **in aggiunta** a quella del Review Agent |
| Modifica delle policy | Riservata all'owner; protection rules da abilitare con GitHub Pro/Organization |

### Regola operativa

Ogni modifica segue sempre questi passaggi:

1. creare un branch dedicato;
2. aprire una pull request verso `main`;
3. attendere la review;
4. eseguire il merge solo manualmente dall'owner.

> La regola è procedurale finché il piano GitHub non consente l'enforcement tecnico.

### Verifica pratica — obbligatoria

Al bootstrap, e a ogni modifica dei permessi:

- [ ] Push su `main` con l'identità del Dev Agent → **deve fallire**
- [ ] Push su `main` con l'identità del Review Agent → **deve fallire**
- [ ] Merge con l'identità del Dev Agent → **deve fallire**
- [ ] Creazione di un workspace Fabric con l'identità del Dev Agent → **deve fallire**
- [ ] Scrittura su un workspace Fabric con l'identità del Dev Agent → **deve fallire**
- [ ] Accodamento di una pipeline **umana** con l'identità del Dev Agent → **deve fallire**
- [ ] Accodamento di una pipeline **agentica** con l'identità del Dev Agent → **deve riuscire**
- [ ] Il Review Agent non vede alcun workspace Fabric → elenco vuoto
- [ ] Il Review Agent **riesce a votare** su una PR → la sola lettura non deve impedirlo

> L'ultimo controllo nasce da un errore reale di questa documentazione: «sola lettura + voto»,
> preso alla lettera in fase di configurazione, produce un revisore che non può votare. Ce ne si
> accorgerebbe solo alla prima review.

> Una policy configurata e mai provata è una policy di cui non sai nulla. Questi quattro
> controlli richiedono pochi minuti e sono l'unica prova che il modello di sicurezza esista
> davvero.

---

## 5. Il perimetro invalicabile

Alcune capacità restano fuori dalla portata degli agenti **in modo permanente**, non solo in
fase 1:

| Capacità | Motivo |
|---|---|
| Creare o modificare identità applicative | Un agente che crea identità può crearne una più potente di sé |
| Assegnare o modificare permessi | Renderebbe ogni altro limite revocabile dall'agente stesso |
| Modificare branch policy o regole di protezione | Stesso motivo |
| Accedere a token e variabili d'ambiente | Un token esfiltrato vanifica la separazione delle identità |

> Se questi quattro punti cadono, tutto il resto della matrice diventa decorativo. È la ragione
> per cui il bootstrap di un nuovo progetto richiede un intervento umano — vedi
> `../functional/06-onboarding-nuovo-cliente.md`.

### Trattamento delle violazioni

Un tentativo di compiere una di queste azioni **non è un errore da correggere**: è un incidente.

| Passo | Azione |
|---|---|
| 1 | La checklist di review lo intercetta (voci F3, F4) come rilievo bloccante |
| 2 | Escala immediatamente all'owner |
| 3 | Si verifica se sia stato un effetto del ticket, un difetto delle istruzioni o altro |
| 4 | L'esito viene recepito nelle istruzioni e nella checklist |

---

## 6. Dati

| Regola | Trattamento |
|---|---|
| Dati sintetici/open data | Il Dev Agent può avere `Viewer` diagnostico, oltre al rail |
| Dati di cliente | Il rail diagnostico accede ai dati; il modello riceve solo aggregati, chiavi mascherate e campioni ammessi dalla policy |
| Righe grezze, PII, segreti | Fuori dal flusso autonomo. Richiedono umano autorizzato o canale approvato dal cliente |
| Credenziale cliente | SP OIDC, SP con secret o utenza di servizio nel secret store; mai nel runtime dell'agente |

> L'agente può stabilire che una chiave non è univoca senza vedere le righe: gli bastano numero
> di righe, numero di chiavi distinte e identificativi mascherati. La pipeline calcola; il modello
> interpreta. Questo è il perimetro che rende possibile l'assistenza quotidiana su dati cliente.

---

## 7. Revisione periodica

| Attività | Frequenza |
|---|---|
| Rilettura della matrice dei permessi | A ogni slice completato |
| Verifica pratica delle branch policy | A ogni modifica di permessi |
| Controllo dei permessi concessi in emergenza | Mensile |
| Audit delle azioni degli agenti | A campione |

> **Il rischio più concreto non è un attacco: è la concessione fatta per sbloccare in fretta un
> ticket.** Nessuno la revoca, nessuno la ricorda, e sei mesi dopo il perimetro non assomiglia
> più a quello progettato.
