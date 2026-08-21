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

> L'ultimo punto è spesso trascurato: abilitare la creazione di workspace via identità applicativa
> a livello di tenant senza restringerla a un gruppo significa concederla a **tutte** le
> applicazioni del tenant, non solo alle nostre.

---

## 3. Matrice dei permessi

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
| Repo soluzione | **Sola lettura** + commento e voto | Rimosso dai contributori: la sola lettura va garantita, non solo dichiarata |
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
