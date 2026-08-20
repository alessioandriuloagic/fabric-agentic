# 07 — Architecture review

> Review architetturale critica del design funzionale prodotto da @karl, condotta prima
> dell'avvio dello Slice 0. **Non è una conferma**: è un tentativo di rompere il design finché
> costa poco romperlo.

| Campo | Valore |
|---|---|
| Versione | 1.1 |
| Data | 2026-08-20 (v1.0) · 2026-08-20b (addendum §13) |
| Autore | Ralph (Fabric Solution Architect) |
| Oggetto | `docs/prd/PRD-agentic-cicd-fabric.md` v0.1 · `CONTEXT.md` v0.1 · `docs/functional/` · `docs/technical/01–06` · `docs/backlog/slice-0-1.md` |
| Documenti generati | `docs/adr/ADR-0001` … `ADR-0009` |

> **Leggere prima §13.** Dopo la stesura della v1.0 è emerso un asset di deploy Fabric già
> funzionante (`IP.dai_fabric_environments`) che nessuno dei documenti recensiti citava.
> L'addendum §13 recepisce quel fatto, **supera ADR-0002**, riformula RB-1 e RB-3 e introduce un
> nuovo rilievo bloccante **RB-4**. Dove §3 e §5 divergono da §13, **vale §13**.

---

## 0. Metodo e regole di verifica

Ogni affermazione su Microsoft Fabric, Power BI e Azure DevOps contenuta in questo documento è
stata verificata sulla documentazione ufficiale Microsoft Learn il 2026-08-20. Le fonti sono
elencate in §12.

Tre livelli di marcatura, usati in modo rigoroso:

| Marca | Significato |
|---|---|
| **[V]** | Verificato su documentazione ufficiale, con fonte citata in §12 |
| **[NV]** | **Non verificato** in questa review. Va verificato prima di trasformarlo in decisione |
| **[D]** | Derivato per calcolo da fatti **[V]**. L'aritmetica è mia, gli input sono documentati |

> Dove ho trovato **due pagine ufficiali in contraddizione tra loro**, l'ho dichiarato invece di
> scegliere quella comoda. Vedi §5.2 e §12.

### Esiti usati

`CONFERMATO` · `DA CORREGGERE` (rilievo con raccomandazione) · `DA VERIFICARE` (non decidibile
con le informazioni disponibili).

---

## 1. Sintesi esecutiva

| # | Area | Esito |
|---|---|---|
| 1 | Sizing e sostenibilità F32 (Q-5) | **DA CORREGGERE** — la F32 regge il carico, non regge la *convivenza* con la produzione |
| 2 | Topologia workspace e ALM | **DA CORREGGERE** — manca `test`, e la promozione via Deployment Pipelines è incompatibile con PBIR |
| 3 | Contratto di connettore | **DA CORREGGERE** — corretto nel principio, incompleto per l'implementazione (4 elementi mancanti) |
| 4 | Matrice dei permessi | **DA CORREGGERE** — due falle: uno switch di tenant non separabile e una precondizione Azure DevOps ignorata |
| 5 | Q-9 cartelle e task flow | **RISOLTA** — cartelle sì via API (preview), task flow no |
| 6 | Q-7 hosting degli agenti | **RISPOSTA CON RISERVA** — la domanda del PRD è posta male: non è l'hosting il problema |
| 7 | Rischi non identificati | **9 nuovi rischi**, di cui 3 bloccanti |

### Rilievi bloccanti

| ID | Rilievo | Blocca |
|---|---|---|
| **RB-1** | Lo switch di tenant che abilita `Create Workspace` al service principal abilita **contestualmente** `Create Connection` e `Create Deployment Pipeline`. Il "deploy NEGATO" della matrice non è imponibile a quel livello | S0-07 |
| **RB-2** | Un service principal **non** ottiene accesso ad Azure DevOps entrando in un gruppo di sicurezza Entra: va aggiunto esplicitamente all'organizzazione da un Project Collection Administrator e **consuma una licenza Basic ciascuno**. Assente da PRD, doc 04 e backlog | S0-05 |
| **RB-3** | RF-18 (cleanup del feature workspace dopo il merge) **non ha alcun trigger che possa attivarlo**: i tre trigger del dispatcher Dev non includono "PR mergiata". Il requisito è inattuabile per costruzione | S1 (non S0) |

Nessuno dei tre impedisce di avviare il **Gruppo A** dello Slice 0 (repo, documentazione, board).
Tutti e tre stanno sul **percorso critico**. Dettaglio in §10.

---

## 2. Area 1 — Sizing e sostenibilità della capacity F32 (Q-5)

### 2.1 Cosa dice il design

A-2 assume che «il volume dei feature workspace è sostenibile sulla F32 senza impatto sui carichi
esistenti», da validare per monitoraggio (R-4, RNF-06). Q-5 chiede strategia di cleanup e soglia
di allarme.

### 2.2 Verifica

**Fatti stabiliti.**

| Fatto | Valore | Fonte |
|---|---|---|
| F32 | 32 CU · 4 v-core Power BI | **[V]** licenses |
| Rapporto Spark | 1 CU = **2 Spark VCore** | **[V]** concurrency |
| F32 Spark | **64 VCore base**, **192 con burst 3×**, coda **32** | **[V]** concurrency |
| Smoothing | background su **24 ore**, interactive 5–64 minuti | **[V]** throttling |
| Stadi di throttling | ≤10 min protezione · 10–60 min ritardo 20s sull'interattivo · 60 min–24h **rifiuto** interattivo · >24h rifiuto di tutto | **[V]** throttling |
| Warehouse | quasi tutte le operazioni classificate **background** | **[V]** throttling |

**Il fatto che cambia il progetto**, e che il PRD non contiene:

> «Queueing doesn't apply to interactive notebook jobs **or notebook jobs submitted through the
> notebook public API**.» — e, se la capacity è già in throttling, «new Spark jobs are **rejected**
> instead of queued». **[V]** concurrency

Tradotto: se il rail *Run load* lanciasse il **notebook** via API, un carico avviato con la
capacity satura non verrebbe accodato — verrebbe **rifiutato** con `430 TooManyRequestsForCapacity`.
L'agente lo interpreterebbe come fallimento tecnico (blocco B1), tenterebbe fino a 3 volte,
fallirebbe 3 volte, ed escalerebbe all'umano un problema che non è né suo né del ticket.
I job avviati **da pipeline**, invece, vengono accodati. **[V]** concurrency

Il contratto del rail in `03-rail-script.md` §4 dice già «Avvia la **pipeline** di ingestion»: la
scelta giusta è già scritta, ma **per caso, non per ragione documentata**. Va resa vincolante e
motivata, perché è esattamente il tipo di dettaglio che un agente "ottimizza" alla prima
occasione ("chiamo direttamente il notebook, è più veloce").

### 2.3 Sizing quantitativo

**[D]** F32 = 32 CU × 24 h = **768 CU-ora al giorno** di budget smoothed.
Un carico Spark che occupa 16 VCore (= 8 CU) per 10 minuti consuma ≈ **1,33 CU-ora**, cioè lo
**0,17%** del budget giornaliero. Anche 50 esecuzioni al giorno resterebbero sotto il 9%.

**Conclusione sul volume: la F32 regge ampiamente il consumo dei feature workspace.** Il PRD
teme la cosa sbagliata.

**Il vincolo vero è la concorrenza, non il volume.** **[D]** con 64 VCore base e una sessione
Spark minimale da 16 VCore (driver + 1 executor su nodi da 8 VCore — **[NV]**, dipende dalla node
size del pool effettivamente configurato), si ottengono **~4 sessioni concorrenti a regime base** e
**~12 in burst**. Il dispatcher impone già "una sola sessione attiva per agente", quindi in fase 1
la concorrenza generata dagli agenti è **1**. Il rischio di saturazione non viene dagli agenti:
viene dal **sommarsi degli agenti a un carico di produzione sulla stessa capacity**.

### 2.4 Il rischio che il PRD non vede

Il throttling in Fabric è **per capacity, non per workspace** **[V]** throttling. E lo smoothing
background distribuisce il consumo su **24 ore**. Ne discendono due conseguenze che il design non
considera:

1. **Un agente impazzito degrada la produzione.** Un ticket che rilancia il carico in loop, o un
   notebook con una join esplosiva, consuma CU sulla stessa F32 su cui gira `ws_agentic_prod`.
   Non esiste isolamento: è la definizione stessa di capacity condivisa.
2. **Il danno si manifesta il giorno dopo.** Con smoothing a 24 ore, una serata di lavoro agentico
   intenso non satura la sera: satura **la mattina successiva**, quando la produzione parte e
   trova il carryforward già acceso. È il tipo di incidente che nessuno collega alla causa.

Finché il progetto è un laboratorio interno su dati sintetici, è accettabile. Nel momento in cui
l'asset viene istanziato su un cliente (RF-80), **non lo è più** — e l'architettura non ha oggi
alcun punto in cui quella decisione viene presa.

### 2.5 Esito e raccomandazioni

**Esito: DA CORREGGERE.**

| # | Raccomandazione |
|---|---|
| R1.1 | **I feature workspace non condividono la capacity con la produzione.** Decisione formalizzata in **ADR-0001**, con tre opzioni valutate (capacity dedicata, Autoscale Billing for Spark, accettazione del rischio in fase 1) |
| R1.2 | Rendere **vincolante nel contratto del rail** che l'esecuzione avvenga tramite **pipeline** e mai tramite chiamata diretta al notebook, citando la ragione (accodamento vs rifiuto). È un criterio di review, non un dettaglio implementativo |
| R1.3 | Il rail deve **distinguere `RequestBlocked` da `CapacityLimitExceeded`** (entrambi HTTP 429, `errorCode` diverso **[V]** api-throttling) e da `430 TooManyRequestsForCapacity`: il primo si ritenta rispettando `Retry-After`, gli altri due **non sono errori dell'agente** e vanno escalati come blocco **B6**, non come B1. Oggi il protocollo di escalation non li distingue |
| R1.4 | Tetto rigido: **massimo 5 feature workspace esistenti contemporaneamente**. Il rail *Branch out* rifiuta la creazione del sesto ed escala. Un tetto che non è imposto da uno script non è un tetto |
| R1.5 | **Cleanup a TTL, non al merge** — vedi RB-3 e **ADR-0004** |
| R1.6 | Soglie di allarme (risposta operativa a Q-5): (a) email alert su Capacity Overview Events **[V]** throttling; (b) allarme a **qualunque** occorrenza della fascia "ritardo interattivo" in una giornata senza carichi di produzione pianificati; (c) revisione settimanale del grafico *Throttling* e *Overages* nella Capacity Metrics App |

---

## 3. Area 2 — Topologia dei workspace e ALM

### 3.1 Cosa dice il design

`CONTEXT.md` §3.2 ammette gli ambienti `dev`, `test`, `prod`; il PRD ne nomina due
(`ws_agentic_dev`, `ws_agentic_prod`); RF-72 e NO-1 parlano di «deploy verso **test** e
produzione» come attività umana. Il feature workspace è `ws_agentic_feature_wi<id>`.

### 3.2 Rilievo 1 — l'ambiente `test` è citato tre volte e non esiste

Non è una svista lessicale: RF-72 vieta agli agenti un'azione (**deploy verso test**) verso un
ambiente che nessun documento crea, e il ticket S1-04 crea esplicitamente solo DEV e PROD. Un
divieto verso un bersaglio inesistente è decorativo, e la matrice dei permessi ne eredita
l'ambiguità.

Due strade oneste, nessuna delle quali è "lasciare com'è":

- **(a)** dichiarare che la fase 1 ha **due ambienti** e rimuovere `test` da `CONTEXT.md` §3.2 e
  da RF-72;
- **(b)** introdurre `ws_agentic_test` fin dallo Slice 1.

Raccomando **(b)**, per una ragione che non è di completezza ma di credibilità: l'asset è anche una
**demo commerciale** (OB-4), e un cliente enterprise che vede una catena CI/CD con dev→prod
diretto smette di ascoltare in quel momento. Il costo marginale è un workspace vuoto.

### 3.3 Rilievo 2 — Deployment Pipelines è incompatibile con la scelta PBIR

`CONTEXT.md` §6 impone il formato **TMDL/PBIP e PBIR**, «mai `.pbix` binario nel repo». RF-40 e
RF-43 lo ribadiscono. È la scelta giusta per il versionamento.

Ma la documentazione ufficiale delle Deployment Pipelines elenca, tra le limitazioni generali:

> «**PBIR reports aren't supported.**» **[V]** deployment-process

Quindi il canale di promozione `dev → test → prod` che chiunque assumerebbe di default —
Deployment Pipelines — **non può trasportare i report del progetto**. Nessun documento del design
se ne accorge, perché nessun documento dice mai *come* avviene la promozione: RF-72 dice solo che
è umana.

Altre limitazioni verificate che pesano sulla stessa scelta:

| Limitazione | Impatto | Fonte |
|---|---|---|
| Un semantic model **Direct Lake** non si ri-aggancia automaticamente al lakehouse dello stage di destinazione: resta legato a quello di origine, servono *datasource rules* | Il layer semantic promosso punterebbe silenziosamente ai dati di DEV | **[V]** deployment-process |
| Massimo **300 item** per singolo deployment | Non vincolante oggi | **[V]** deployment-process |
| Il workspace deve risiedere su capacity Fabric | Coerente | **[V]** deployment-process |
| Git integration per **Report e Semantic model è in preview** | Rischio su S6 | **[V]** git-supported-items |

### 3.4 La topologia corretta

Fabric impone che **un workspace sia connesso a un solo branch** **[V]** manage-branches. Il
pattern documentato per lo sviluppo isolato è esattamente il "branched workspace" che il design
già adotta. Su questo il design è **corretto**.

La promozione, invece, va fatta **per Git** e non per Deployment Pipelines:

```
                    main ──────────────► ws_agentic_dev      (sync automatico)
                      │
                      ├── tag/branch release ──► ws_agentic_test   (update from Git, umano)
                      │
                      └── tag/branch release ──► ws_agentic_prod   (update from Git, umano)

feature/wi-<id> ─────────────────────► ws_agentic_feature_wi<id>   (effimero)
```

Questo modello ha due proprietà che le Deployment Pipelines non hanno, e che contano più della
comodità dell'interfaccia:

1. **è compatibile con PBIR** (il formato è quello che Git già sincronizza);
2. **ciò che è in produzione è un commit identificabile**, non il risultato di una copia
   metadata-to-metadata di cui non resta traccia in Git.

Il prezzo: la parametrizzazione per ambiente (connection string, id di lakehouse, path) non può
più appoggiarsi alle *deployment rules*. Va risolta con **Variable Library**, che è item
supportato sia da Git integration sia da Deployment Pipelines **[V]** git-supported-items. Va
introdotta nel design: oggi `CONTEXT.md` non la prevede tra i prefissi di naming.

### 3.5 Esito e raccomandazioni

**Esito: DA CORREGGERE.**

| # | Raccomandazione |
|---|---|
| R2.1 | Introdurre `ws_agentic_test` nello Slice 1 (ticket S1-04), oppure rimuovere `test` da `CONTEXT.md` e da RF-72. **Non lasciare la terza via** |
| R2.2 | Adottare la **promozione via Git**, non via Deployment Pipelines — formalizzato in **ADR-0002** |
| R2.3 | Aggiungere **Variable Library** alle convenzioni di naming e alla struttura del repo, come punto unico della parametrizzazione per ambiente (serve anche a RF-80) |
| R2.4 | Registrare nel runbook che i semantic model **Direct Lake** richiedono un ri-aggancio esplicito al lakehouse dell'ambiente di destinazione, qualunque sia il canale di promozione |
| R2.5 | Aggiungere alla checklist di review una voce che intercetti il **superamento del limite di 1.000 item per workspace** **[V]** git-limitations — oggi lontano, ma è un limite che non dà preavviso |

---

## 4. Area 3 — Contratto di connettore

### 4.1 Giudizio complessivo

La separazione **orchestrazione / connettore / carico** è corretta, ed è la parte migliore del
design tecnico. Il criterio di verifica proposto («cerca il nome della tipologia di sorgente nel
codice di orchestrazione: se compare, il contratto è rotto») è il tipo di test binario che
distingue un'architettura da un'intenzione.

È implementabile con gli strumenti Fabric: pipeline come orchestratore, notebook di carico
condiviso e parametrizzato, configurazione JSON come contratto. Nessun ostacolo di piattaforma.

**Ma il contratto non è implementabile così com'è**, perché mancano quattro elementi senza i quali
il primo agente che lo legge dovrà inventarseli — e inventerà quattro cose diverse in quattro
sessioni diverse.

### 4.2 Le quattro lacune

#### L1 — Dove vive fisicamente il codice del connettore

Il documento definisce l'interfaccia (validazione, estrazione, conteggio, schema) ma **mai
l'artefatto**. In Fabric le opzioni sono tre, e non sono equivalenti:

| Opzione | Conseguenza |
|---|---|
| Notebook `nb_connector_<tipo>` richiamato da quello di carico | Semplice, versionabile via Git, nessuna dipendenza di build. Il "codice condiviso" è un notebook, il che è brutto ma funziona |
| Wheel Python pubblicato su un **Environment** (`env_`) | Pulito, ma l'Environment è una risorsa **di workspace**: ogni feature workspace effimero dovrebbe pubblicarlo, e la pubblicazione ha un costo e una latenza non trascurabili |
| File nelle *Resources* del lakehouse | Fuori dal perimetro di Git integration: **incompatibile** con il principio "la verità è in Git" |

La scelta ha impatto diretto sul lead time di ogni ticket (KPI-2) e sulla riproducibilità del
feature workspace. Va decisa da un umano, ora. Vedi **ADR-0006**.

#### L2 — Il metadata store non è definito da nessuna parte

`03-rail-script.md` §4 dice che il rail *Run load* «pubblica la configurazione nel **metadata
store del workspace**». Quel componente **non compare né in `CONTEXT.md`, né in
`06-contratto-connettore.md`, né in `05-struttura-repository.md`**. Non se ne conosce la
tecnologia, la collocazione, il ciclo di vita.

Il problema diventa concreto sull'incrementalità: la modalità `incremental` con watermark column
richiede che **lo stato del watermark sia persistito da qualche parte**. In un feature workspace
creato ex novo per ogni ticket, quello stato **non esiste**: il primo carico incrementale in un
feature workspace è, di fatto, un full. Se nessuno lo dichiara, l'agente lo scoprirà da solo e
concluderà — ragionevolmente e sbagliando — che l'incrementalità è rotta.

#### L3 — Il contratto di output dell'estrazione non è dichiarato

«Recupera i dati e li deposita nell'area di staging convenzionale»: non è detto **in quale
formato**, con quale partizionamento, né se l'output debba essere **tabellare**.

Non è pedanteria: **Open-Meteo non restituisce record**. Restituisce un oggetto JSON con array
paralleli (`time[]`, `temperature_2m_max[]`, …). Trasformarlo in righe è una normalizzazione
**specifica della sorgente**. Se quella normalizzazione finisce nel notebook di carico condiviso,
il contratto è rotto al primo dataset — esattamente il fallimento che il documento §7 elenca come
segnale d'allarme, e che si verificherebbe **allo Slice 2**, non allo Slice 4.

Va scritto esplicitamente: **l'output dell'estrazione è un set di record tabellare; la
normalizzazione di payload non tabellari è responsabilità del connettore.**

#### L4 — Il "conteggio alla sorgente" è, per REST e File, una tautologia

Questa è la critica più seria, perché tocca **l'evidenza che il Review Agent deve giudicare**.

Il contratto dichiara obbligatorio il *conteggio alla sorgente* «per la riconciliazione», e
RF-22 / checklist C3 lo trattano come controllo indipendente. Ma il documento stesso, nelle
schede dei due connettori di fase 1, lo definisce così:

- REST: «Conteggio: numero di record **restituiti dopo l'estrazione**»
- File: «Conteggio: numero di righe **lette**»

Se il conteggio sorgente *è* il conteggio dell'estrazione, allora la riconciliazione
sorgente↔destinazione verifica soltanto che la scrittura non abbia perso righe. È un controllo
utile, ma **non è quello che il documento dichiara di essere**, e soprattutto **non può fallire
per la causa che ci si aspetta** (dato incompleto alla sorgente).

Il Review Agent giudicherà `C3 PASSATO` su un controllo che, per queste due sorgenti, non può
fare altro che passare. Il sistema di verifica ha un buco esattamente dove crede di avere una
prova.

Correzione: distinguere in configurazione e in evidenza tre grandezze — `source_count`
(indipendente, **solo se la sorgente lo supporta**), `extracted_count`, `loaded_count` — e
introdurre in configurazione un flag esplicito `supports_source_count`. Quando è `false`, il
controllo di riconciliazione va riportato come **`NON APPLICABILE` motivato**, non come
`PASSATO`. La checklist §1 già prevede che un `NON APPLICABILE` non motivato sia esso stesso un
rilievo: il meccanismo esiste, basta usarlo.

### 4.3 Rilievi minori

| # | Rilievo |
|---|---|
| m1 | Il PK check «prima di qualsiasi scrittura» è corretto sul full load. Su un **incremental con merge**, verificare l'unicità sul solo delta non garantisce l'unicità globale della tabella bronze. Va dichiarato quale delle due garanzie si sta dando |
| m2 | La regola «i nomi dei file non contengono informazioni semantiche indispensabili» è giusta, ma il connettore File dichiara «incrementalità **per data del file**»: è una contraddizione interna al documento |
| m3 | Il criterio «cerca il nome della tipologia nel codice di orchestrazione» non intercetta la rottura più probabile, che passa dalla **configurazione**: un campo di primo livello aggiunto "solo per questa sorgente". Aggiungere alla checklist: nessun campo nuovo fuori dal blocco isolato del connettore |

### 4.4 Esito

**Esito: DA CORREGGERE.** Il contratto regge come principio; non regge come specifica. Le quattro
lacune vanno chiuse **prima dello Slice 2**, non prima dello Slice 4: L3 e L4 si manifestano già
sul primo connettore. Formalizzato in **ADR-0006**.

---

## 5. Area 4 — Identità, permessi e modello di sicurezza

### 5.1 Cosa è confermato

Il principio «i permessi, non le istruzioni, definiscono il perimetro» è corretto e la difesa in
profondità su `main` (deny esplicito **+** branch policy) è la scelta giusta. La verifica pratica
obbligatoria di S0-06 è il singolo item di maggior valore dell'intero Slice 0. Su questo non ho
rilievi: ho rilievi su ciò che manca intorno.

Confermato **[V]**:

- Esiste il tenant setting **«Service principals can call Fabric public APIs»**, restringibile a
  un gruppo di sicurezza, **abilitato per default** per i nuovi tenant.
- Esiste il tenant setting **«Service principals can create workspaces, connections, and
  deployment pipelines»**, restringibile a un gruppo di sicurezza, **disabilitato per default**.
- L'esecuzione di notebook via service principal è **supportata** (Items API e Job Scheduler API),
  con il service principal aggiunto al workspace come Admin, Member o Contributor.
- L'assegnazione di un workspace a una capacity via API richiede **capacity contributor o capacity
  admin** *e* **workspace admin**.

### 5.2 RB-1 — Lo switch che non si può separare

Il backlog (S0-07) e il documento 04 parlano al singolare dello «switch di tenant per la creazione
di workspace via identità applicativa». In realtà ce ne sono **due**, e il secondo è un pacchetto
indivisibile:

> «Service principals can create workspaces, **connections, and deployment pipelines**» — abilita
> `Create Workspace`, `Create Connection` e `Create Deployment Pipeline`. **[V]** admin-developer

Conseguenza diretta: **non è possibile concedere al Dev Agent la creazione di workspace negandogli
la creazione di deployment pipeline.** La riga «Deploy verso test/prod: **NEGATO**» della matrice
è, a quel livello, non imponibile.

Non è fatale — la creazione di una deployment pipeline vuota è innocua — ma va imposta altrove, e
oggi non lo è da nessuna parte:

1. il service principal del Dev Agent **non deve essere pipeline admin** di alcuna deployment
   pipeline esistente (`dp_agentic`);
2. il service principal del Dev Agent **non deve avere alcun ruolo** su `ws_agentic_test` e
   `ws_agentic_prod` — il deploy richiede il ruolo di contributor su **entrambi** gli stage
   **[V]** deployment-process, quindi l'assenza di ruolo su prod è il controllo che davvero
   impedisce il deploy;
3. la verifica pratica di S0-06 va estesa con un quinto controllo: *tentare un deploy verso prod
   con l'identità del Dev Agent → deve fallire*.

Questo cambia anche la lettura del principio «ciò che l'agente può tecnicamente fare, prima o poi
lo farà»: qui **potrà** creare deployment pipeline. Meglio saperlo e sorvegliarlo (voci F3/F4
della checklist) che credere di averlo vietato.

### 5.3 RB-2 — La precondizione Azure DevOps che nessun documento nomina

Il documento 04 §2 afferma: «Le identità sono raccolte in un gruppo di sicurezza dedicato — gli
switch di tenant si applicano al gruppo, non al mondo». Vero **per Fabric**. **Falso per Azure
DevOps**, e la documentazione è esplicita:

> «Service principals don't automatically appear in Azure DevOps. **Adding a service principal to
> a Microsoft Entra security group doesn't grant access to your organization.** A Project
> Collection Administrator or Project Administrator **must explicitly add the service principal to
> the organization** and grant it the permissions required.» **[V]** ado-spn

E ancora **[V]** ado-spn:

- ogni identità **consuma una licenza in ogni organizzazione** a cui appartiene, senza sconti
  multi-organizzazione;
- **Stakeholder non basta**: l'errore «The Git repository with name or identifier doesn't exist or
  you don't have permissions» si risolve assegnando almeno una licenza **Basic**;
- i service principal **non possono creare PAT** né autenticarsi interattivamente;
- i rate limit sono gli stessi degli utenti.

Impatto concreto: **due licenze Basic Azure DevOps** non previste nel PRD, un passaggio da PCA non
previsto nel percorso critico (che oggi identifica come collo di bottiglia solo l'amministratore di
tenant, in S0-04), e la conferma che V-3 (impossibile assegnare un work item a un service
principal) è corretto — il tag come marcatore resta la soluzione giusta.

### 5.4 Rilievo — "sola lettura + voto" non è un ruolo, è una combinazione

La matrice assegna al Review Agent «**sola lettura** + commento e voto» e S0-05 chiede di
rimuoverlo «dai contributori del repo». Presa alla lettera, la configurazione produrrebbe un
agente **che non può votare**: in Azure Repos il voto su una pull request è governato dal permesso
*Contribute to pull requests*, distinto da *Contribute* (push). **[NV]** — non ho verificato la
tassonomia dei permessi Azure Repos su Learn in questa review.

È un rilievo che vale la pena chiudere subito perché il fallimento sarebbe **silenzioso e tardivo**:
non si manifesta in S0-05, si manifesta allo Slice 3, quando il Review Agent commenterà senza
riuscire a votare e il ciclo non convergerà mai.

Raccomandazione: riformulare il criterio di accettazione di S0-05 in termini di **capacità
verificate**, non di ruoli — «con l'identità del Review Agent: `git push` fallisce, il voto sulla
PR riesce» — e aggiungere entrambe le prove alla verifica pratica.

### 5.5 Rilievo — la connessione Git a service principal è un artefatto che nessuno ha previsto

Il rail *Branch out* (passo 5, «collega il workspace al branch») nasconde una precondizione non
banale. L'API `Git - Connect` **[V]** git-connect:

- richiede il ruolo **Admin** sul workspace (il Dev Agent lo è, perché lo crea: **confermato**);
- con service principal è supportata **solo** con `myGitCredentials.source = ConfiguredConnection`
  — la modalità `Automatic` è **bloccata** per i service principal;
- fallisce con `WorkspaceHasNoCapacityAssigned` se la capacity non è già assegnata: l'ordine dei
  passi 3→5 del rail è quindi **corretto**;
- per Azure DevOps la connessione va creata con `credentialType = ServicePrincipal`, perché
  «AzureDevOps for UserPrincipal is not supported (since it requires interactive OAuth2)».

Quindi **esiste un oggetto Connection Fabric che contiene client id e secret del service
principal**, creato via `Create Connection` — API governata dallo stesso tenant setting di RB-1.
Questo artefatto:

- non compare in `05-struttura-repository.md` §3 ("cosa NON sta nel repo"), che pure elenca dove
  vivono le credenziali;
- non ha un proprietario dichiarato nel backlog: chi lo crea, con quale identità, e quando si
  ruota il segreto che contiene;
- introduce un limite operativo verificato: **la dimensione massima di un commit via connettore
  Azure DevOps con service principal è 25 MB**, contro 125 MB con identità utente **[V]**
  git-limitations.

### 5.6 Esito e raccomandazioni

**Esito: DA CORREGGERE.**

| # | Raccomandazione |
|---|---|
| R4.1 | Riscrivere S0-07 riconoscendo **due** tenant setting distinti, entrambi ristretti al gruppo, e spostare il divieto di deploy dal livello "tenant setting" al livello **ruoli di workspace e pipeline admin** |
| R4.2 | Aggiungere allo Slice 0 un item «abilitare i service principal su Azure DevOps»: aggiunta esplicita da PCA, licenza Basic, permessi minimi. **Va prenotato insieme all'amministratore di tenant**: sono due colli di bottiglia, non uno |
| R4.3 | Estendere la verifica pratica di S0-06 da 4 a **7 controlli**: + deploy verso prod negato, + push del Review Agent negato ma **voto riuscito**, + lettura variabili d'ambiente negata |
| R4.4 | Aggiungere al backlog la creazione e la rotazione della **Connection Git a service principal**, e censirla in `05-struttura-repository.md` §3 |
| R4.5 | Documentare il limite di **25 MB per commit** come vincolo noto |

---

## 6. Area 5 — Q-9: cartelle e task flow via API

**Domanda**: cartelle del workspace e task flow sono creabili e mantenibili via API/CLI, o restano
un passo manuale?

### 6.1 Cartelle — **SÌ**, con tre riserve

Esiste l'API `POST /v1/workspaces/{workspaceId}/folders` **[V]** folders-api:

- **supporta service principal e managed identity**;
- richiede ruolo **contributor o superiore** sul workspace;
- accetta `parentFolderId` per l'annidamento;
- **è in Preview** — «not recommended for production use».

Riserve, tutte verificate:

| # | Riserva | Fonte |
|---|---|---|
| 1 | Annidamento massimo **10 livelli**; errore `TooManyFolders` se il workspace raggiunge il numero massimo di cartelle (valore numerico **non documentato**) | **[V]** folders-api |
| 2 | Vincoli sul nome: niente spazi iniziali/finali, vietati i caratteri `~"#.&*:<>?/{\|}`. La cartella `Full and Incremental Load` di `CONTEXT.md` è **valida**; scritta `Full & Incremental Load` **non lo sarebbe**. Da annotare, perché è esattamente il tipo di "correzione estetica" che qualcuno farà | **[V]** folders-limits |
| 3 | **Alcuni item non possono essere creati dentro una cartella**: Dataflow Gen2, streaming semantic model, streaming dataflow. Inoltre gli item creati dalla home o dal Create hub nascono **alla radice** | **[V]** folders-limits |

La riserva 3 ha una conseguenza diretta: **RF-19 («nessun item alla radice del workspace») non è
soddisfacibile per i Dataflow Gen2**, che `CONTEXT.md` §3.1 prevede esplicitamente con il prefisso
`df_`. Il requisito va riformulato con l'eccezione documentata, altrimenti la voce A2 della
checklist genererà un rilievo insanabile.

**Contraddizione tra due pagine ufficiali Microsoft**, che segnalo invece di risolverla a mio
comodo: la pagina *Create folders in workspaces* afferma «**Git doesn't currently support workspace
folders**», mentre la pagina *Git integration process* — più recente — documenta in dettaglio il
mirroring della struttura a cartelle tra workspace e repo. Assumo la seconda come valida (è
aggiornata al 2026-08-03 contro il 2024-12-16 della prima) e raccomando **verifica pratica in
S1-01**.

Dalla stessa pagina, un dettaglio che cambia il rail: **«Empty folders aren't copied to Git»** e
«empty folders in Git are deleted automatically» **[V]** git-folders. Quindi lo scheletro di sei
cartelle vuote previsto da `CONTEXT.md` §3.3 **non può materializzarsi via sync da Git**: va
creato con l'API Folders in ogni workspace, feature workspace inclusi.

### 6.2 Task flow — **NO**

La documentazione ufficiale descrive il task flow **esclusivamente come funzionalità di
interfaccia**: canvas nella list view del workspace, pannello laterale, aggiunta e connessione
delle task, assegnazione degli item. L'unica forma di riuso documentata è
**esportazione/importazione di un file `.json` tramite la finestra di dialogo del browser**
**[V]** task-flow-create.

**Non risulta alcuna API REST Fabric per i task flow** nella reference consultata. Questa è
un'affermazione di *assenza di evidenza*, non una prova di impossibilità: la formulo come
**[NV] in senso negativo** e raccomando che S1-01 la riverifichi al momento dell'esecuzione, perché
è esattamente il tipo di gap che Microsoft colma senza annunci.

### 6.3 Esito e raccomandazioni

**Esito: Q-9 CHIUSA**, con esito asimmetrico.

| # | Raccomandazione |
|---|---|
| R5.1 | **RF-19 resta bloccante in review**, con l'eccezione documentata per Dataflow Gen2 e streaming item |
| R5.2 | **RF-20 (task flow) declassato a passo manuale documentato nel runbook, non bloccante in review** — formalizzato in **ADR-0003** |
| R5.3 | Il task flow si applica **solo ai workspace di lungo periodo** (dev/test/prod), mai ai feature workspace effimeri: sarebbe lavoro manuale ricorrente su un artefatto usa-e-getta |
| R5.4 | Versionare comunque il task flow canonico esportato in `fabric/task-flow/agentic.json`, così l'importazione manuale è una procedura di 30 secondi e non una ricostruzione a memoria |
| R5.5 | Il rail *Branch out* acquisisce un passo esplicito: **creazione delle cartelle via Folders API**, perché il sync da Git non le porta se vuote. Dichiarare la dipendenza da un'API in **Preview** come rischio noto |

---

## 7. Area 6 — Q-7: hosting degli agenti su dati di cliente

### 7.1 La domanda del PRD è posta male

Q-7 chiede «quale opzione di hosting degli agenti» prima dell'uso su dati reali. Ma spostare il
dispatcher dalla macchina dell'owner ad Azure **non cambia nulla** rispetto al rischio che la
domanda vuole coprire: il prompt continua a partire verso un endpoint di vendor esterno.

Il documento 04 §6 lo dice già con precisione — «il Dev Agent, eseguendo i carichi e leggendo gli
esiti dei controlli, **vede i dati**» — ma poi conclude che «la questione di dove risieda il
modello diventa dirimente», e Q-7 traduce quella conclusione in "hosting", che è un'altra cosa.

Le variabili indipendenti sono **tre**, non una:

| # | Variabile | Cosa protegge |
|---|---|---|
| V1 | Dove gira il **dispatcher/agente** (macchina locale, Azure, rete del cliente) | Disponibilità, gestione dei segreti, superficie di rete |
| V2 | Dove risiede il **modello** e quali sono i termini contrattuali | Residenza del dato, training, retention |
| V3 | **Cosa entra nel prompt** | Tutto il resto |

**V3 è quella che il progetto controlla per intero, costa zero, ed è l'unica che rende le altre
due meno critiche.** È anche l'unica che il design non ha ancora considerato.

### 7.2 La raccomandazione principale: i rail non restituiscono dati

Il principio 6 del progetto («le regole di qualità dato vivono nel framework, l'agente ne cita
l'esito») è già la premessa corretta. Basta portarlo alla conseguenza:

> **I rail restituiscono esclusivamente evidenze aggregate — esito binario, conteggi, nomi di
> colonna, run id — e mai valori di dato.**

L'esempio del protocollo di escalation (§4 di `05-protocollo-escalation.md`) è già conforme:
«righe totali 48.512, valori distinti di member_id 6.043» è un'evidenza sufficiente a diagnosticare
il problema **senza che un solo valore di `member_id` raggiunga il modello**. È un ottimo esempio,
ed è quello che va promosso da esempio a **regola vincolante del contratto dei rail e voce della
checklist**.

Con questa regola, il perimetro dei dati verso i vendor si riduce a: nomi di tabelle e colonne,
descrizioni del ticket, codice, conteggi. È metadato di business, non dato. La valutazione di
rischio residuo per un cliente cambia natura.

### 7.3 Le opzioni di hosting, una volta ridimensionate

| Opzione | Quando | Note verificate |
|---|---|---|
| **A** — Macchina locale dell'owner (oggi) | Fase 1, dati sintetici | Nessuna disponibilità a macchina spenta; segreti su disco. Accettabile per asset interno, **non** per un impegno di servizio |
| **B** — Azure Container Apps job / VM nel tenant AGIC con **user-assigned managed identity** | Target raccomandato per la fase 2 | Le API Fabric supportano le managed identity **[V]** identity-support; Azure DevOps supporta le managed identity aggiunte all'organizzazione **[V]** ado-spn. Beneficio decisivo: **spariscono i client secret** — niente più segreto nella Connection Git, niente più cache su disco |
| **C** — Esecuzione nella rete del cliente | Solo se il cliente impone che nulla esca dal proprio perimetro | Contraddice V-9 (tutto sul tenant AGIC) e va trattata come variante commerciale, non come architettura di default |

### 7.4 La tensione che nessuno ha ancora nominato

RF-60 impone **vendor diversi** per Dev Agent e Review Agent. Se un cliente esige che i dati non
escano da un perimetro Azure/enterprise, l'insieme dei vendor eleggibili si restringe — e il
vincolo "vendor diverso" e il vincolo "dato nel perimetro" possono diventare **mutuamente
esclusivi**.

È una decisione commerciale prima che tecnica, e non ha una risposta oggi. Ma va posta **prima**
del primo cliente, non durante. Motivo in più per adottare la regola di §7.2: se nel prompt non
entra dato, la tensione si scioglie da sola.

### 7.5 Esito

**Esito: Q-7 RISPOSTA CON RISERVA.** Riformulata e formalizzata in **ADR-0005**. Resta aperta la
sola parte contrattuale (termini di no-training e retention per ciascun vendor), che non è una
decisione architetturale.

---

## 8. Area 7 — Rischi architetturali non identificati nel PRD

Nove rischi assenti dalla tabella §13 del PRD. Ordinati per impatto.

### R-9 — RF-18 non ha un trigger che possa attivarlo *(bloccante, RB-3)*

RF-18 assegna al Dev Agent il cleanup del feature workspace «dopo il merge». I trigger del Dev
Agent sono tre (`02-dispatcher.md` §3): work item taggato in *To Do*, commento umano su *Waiting
input*, thread aperti sulla PR. **Nessuno di questi si verifica dopo un merge.**

Il requisito è inattuabile per costruzione, e il modo in cui fallisce è il peggiore possibile:
silenziosamente. I workspace restano, il consumo cresce, e nessuno riceve un errore.

Peggiora nel caso che conta davvero: un ticket **abbandonato o bloccato per sempre** non viene mai
mergiato, quindi il suo workspace non sarebbe rimosso nemmeno da un trigger corretto. Il cleanup
non può dipendere dal merge: deve dipendere dal **tempo**. Vedi **ADR-0004**.

### R-10 — F32 è sotto la soglia F64 per la fruizione Power BI

**[V]** licenses: su capacity inferiori a F64, ogni utente che **visualizza** contenuti Power BI
deve avere una licenza **Pro o PPU**; la licenza gratuita con ruolo Viewer basta solo da F64 in su.

Impatto diretto su OB-4 e sull'uso in prevendita: gli stakeholder a cui si mostra il report
`rpt_*` prodotto dagli agenti **devono avere una licenza Pro**. Non blocca nulla, ma è il tipo di
sorpresa che si scopre venti minuti prima della demo.

### R-11 — Nessun isolamento tra carico agentico e produzione

Già trattato in §2.4. Il throttling è per capacity: un difetto dell'agente degrada
`ws_agentic_prod`. **ADR-0001**.

### R-12 — Conflitti di logical ID alla ricreazione di un feature workspace

Il rail *Branch out* è dichiarato idempotente: «se branch e workspace esistono già per quell'ID,
si riconnette invece di duplicare». Corretto come intenzione, ma la piattaforma ha due
comportamenti verificati che lo insidiano **[V]** git-automation / git-recycle-bin:

- `InitializeGitConnection` può restituire **`Items with conflicting logical IDs detected`**;
- le operazioni Git ricreano gli item cancellati **assegnando un nuovo item ID**, mentre il
  ripristino dal cestino conserva l'ID originale: la combinazione produce **duplicati con identità
  diverse** che «may cause Git Integration to stop working as expected».

Scenario realistico: workspace `wi42` cancellato, ticket riaperto, rail rilanciato. Va provato
esplicitamente in S1-02, non scoperto in esercizio.

### R-13 — Unicità del nome di workspace e cestino

**[NV]** Non ho verificato se i nomi di workspace debbano essere univoci a livello di tenant né la
durata di ritenzione nel cestino. Se lo fossero, il naming deterministico `ws_agentic_feature_wi<id>`
— che è una scelta giusta e che non metto in discussione — renderebbe **impossibile ricreare** un
workspace il cui omonimo è ancora nel cestino. Da verificare in S1-01, con l'idempotenza del rail
come criterio di accettazione.

### R-14 — Nessun debounce tra Dev Agent e Review Agent

Il Review Agent si attiva su «PR attiva in cui il voto non è approvato». Il Dev Agent può stare
pushando correzioni in quel momento. Il risultato è una review su uno stato intermedio, che
produce rilievi già superati, che risvegliano il Dev Agent, che ripusha: è il **loop a costo pieno**
che RF-66 vuole evitare, innescato però da una race condition e non da un disaccordo — quindi il
contatore delle due iterazioni non lo intercetta.

Mitigazione: il dispatcher Review non avvia la sessione se l'ultimo commit ha meno di N minuti, o
se risulta attiva una sessione del Dev Agent sulla stessa PR. Va in S0-10 come criterio di
accettazione.

### R-15 — Il quota delle API Fabric è per identità, non per sessione

**[V]** api-throttling: **200 chiamate al minuto** per identità, su tre bucket indipendenti
(Platform, Job Scheduler, Long-Running Operations), finestra fissa di 60 secondi senza recupero
graduale.

Non è un problema oggi (una sessione attiva per agente), ma **diventa il primo collo di bottiglia**
se un giorno si volesse parallelizzare il Dev Agent su più ticket: il limite è **sull'identità**,
quindi due sessioni concorrenti condividono lo stesso bucket. È un vincolo di scalabilità da
conoscere prima di progettare la parallelizzazione, non dopo.

### R-16 — Git integration per Report e Semantic model è in preview

**[V]** git-supported-items. L'intera lane Power BI (S6, RF-40..RF-44) poggia su funzionalità in
preview. Non è un motivo per non farla — è un motivo per **non prometterla in un contratto** e per
tenere lo spike A-4 dove sta.

### R-17 — Il costo del progetto non è solo in token

KPI-5 misura il costo token. Non sono censiti: **due licenze Basic Azure DevOps** per i service
principal (§5.3), le **licenze Pro** per la fruizione Power BI sotto F64 (R-10), e l'eventuale
**capacity aggiuntiva** per l'isolamento (ADR-0001). Per un asset venduto come riduzione di costo,
il conto va tenuto intero.

---

## 9. Incoerenze interne alla documentazione

Rilievi che non richiedono verifica esterna: bastano i documenti tra loro.

| # | Incoerenza | Dove |
|---|---|---|
| i1 | L'ambiente `test` è ammesso e regolato ma non esiste | `CONTEXT.md` §3.2 vs PRD §6.1 e S1-04 |
| i2 | RF-18 senza trigger | PRD §8.2 vs `02-dispatcher.md` §3 |
| i3 | Il **metadata store** è invocato da un rail ma non definito da nessuna parte | `03-rail-script.md` §4 vs `06` e `05` |
| i4 | Il conteggio alla sorgente è "obbligatorio per la riconciliazione" ma definito come conteggio dell'estrazione | `06-contratto-connettore.md` §3 vs §4 e §5 |
| i5 | «I nomi dei file non contengono informazioni semantiche indispensabili» ma l'incrementalità File è «per data del file» | `06-contratto-connettore.md` §5 |
| i6 | La knowledge base è un repo separato in `01`, mentre `05` dice che `/docs` nel repo soluzione è la fonte di verità e la wiki è generata. Coesistono ma la relazione tra "secondo clone Git" e "wiki generata" non è esplicitata | `01-architettura-agenti.md` §4 vs `05-struttura-repository.md` §4 |
| i7 | Il ticket S1-04 chiede il task flow «se S1-01 lo ha dichiarato automatizzabile»: un criterio di accettazione condizionale a uno spike è ambiguo per un agente non interattivo, che non può chiedere. Va risolto **prima** di scrivere il ticket | `slice-0-1.md` S1-04 |

---

## 10. Cosa impedisce di aprire lo Slice 0

**Lo Slice 0 può partire oggi, limitatamente al Gruppo A** (S0-01 repository, S0-02 documentazione,
S0-03 board). Nessun rilievo li tocca.

**Il Gruppo B — identità e sicurezza — non va avviato prima di tre correzioni**, perché sono
correzioni al *disegno* dei permessi, e configurare permessi sbagliati costa più che ritardare di
un giorno:

| # | Correzione richiesta | Item impattati |
|---|---|---|
| C1 | Riscrivere S0-07 riconoscendo i **due** tenant setting e spostando il divieto di deploy sui ruoli di workspace e pipeline admin (RB-1, §5.2) | S0-07 |
| C2 | Aggiungere l'item «abilitare i service principal su Azure DevOps» (PCA + licenze Basic) e inserirlo nel percorso critico accanto a S0-04 (RB-2, §5.3) | S0-04, S0-05 |
| C3 | Riformulare i criteri di accettazione di S0-05 e S0-06 in termini di **capacità verificate** anziché di ruoli, portando la verifica pratica da 4 a 7 controlli (§5.4, §5.6) | S0-05, S0-06 |

**Da chiudere prima dello Slice 1**, non prima dello Slice 0:

- ADR-0001 (isolamento della capacity), perché S1-04 crea i workspace e l'assegnazione a capacity
  è parte del ticket;
- ADR-0004 (TTL e cleanup) e il quarto trigger del dispatcher, perché senza di essi il primo
  feature workspace creato non ha una via d'uscita;
- risoluzione di i7 — il ticket S1-04 non può contenere un criterio di accettazione condizionale.
  ADR-0003 lo risolve dichiarando **ora** che il task flow è manuale.

**Da chiudere prima dello Slice 2**: ADR-0006, in particolare le lacune L3 e L4, che si
manifestano già sul primo connettore e non allo Slice 4 come il PRD assume.

---

## 11. ADR generati da questa review

| ADR | Titolo | Perché è difficile da invertire |
|---|---|---|
| **ADR-0001** | Isolamento della capacity per i feature workspace | Assegnazione dei workspace, billing, topologia |
| **ADR-0002** | Promozione degli ambienti via Git anziché Deployment Pipelines | Modello di branch, struttura del repo, parametrizzazione |
| **ADR-0003** | Cartelle via API, task flow come passo manuale | Contratto dei rail, criteri bloccanti di review |
| **ADR-0004** | Ciclo di vita dei feature workspace: TTL e cleanup schedulato | Aggiunge un componente e un trigger al dispatcher |
| **ADR-0005** | Perimetro dei dati verso i vendor LLM: solo evidenze aggregate | Vincola il contratto di output di **tutti** i rail |
| **ADR-0006** | Completamento del contratto di connettore | Formato di configurazione e interfaccia del framework |

---

## 12. Fonti

### Verificate su Microsoft Learn il 2026-08-20

| Sigla | Pagina |
|---|---|
| throttling | *Understand capacity throttling and smoothing* — `/fabric/enterprise/throttling` |
| licenses | *Understand Microsoft Fabric licenses and capacity* — `/fabric/enterprise/licenses` |
| concurrency | *Concurrency limits and queueing in Apache Spark for Fabric* — `/fabric/data-engineering/spark-job-concurrency-and-queueing` |
| git-supported-items | *Overview of Fabric Git integration* — `/fabric/cicd/git-integration/intro-to-git-integration` |
| git-limitations, git-folders, git-recycle-bin | *Git integration process* — `/fabric/cicd/git-integration/git-integration-process` |
| manage-branches | *Development Process in Microsoft Fabric* — `/fabric/cicd/git-integration/manage-branches` |
| git-automation | *Automate Git integration by using APIs* — `/fabric/cicd/git-integration/git-automation` |
| git-connect | *Git - Connect* — `/rest/api/fabric/core/git/connect` |
| folders-api | *Folders - Create Folder* — `/rest/api/fabric/core/folders/create-folder` |
| folders-limits | *Create folders in workspaces* — `/fabric/fundamentals/workspaces-folders` |
| task-flow-create | *Set up a task flow* / *Task flows overview* — `/fabric/fundamentals/task-flow-create`, `task-flow-overview` |
| deployment-process | *The Microsoft Fabric deployment pipelines process* — `/fabric/cicd/deployment-pipelines/understand-the-deployment-process` |
| deployment-items | *Overview of Fabric deployment pipelines* — `/fabric/cicd/deployment-pipelines/intro-to-deployment-pipelines` |
| identity-support | *Identity support for logging into Microsoft Fabric* — `/rest/api/fabric/articles/identity-support` |
| api-throttling | *Throttling in Microsoft Fabric* — `/rest/api/fabric/articles/throttling` |
| admin-developer | *Developer admin settings* — `/fabric/admin/service-admin-portal-developer` |
| job-scheduler | *Run On Demand Item Job* — `/rest/api/fabric/core/job-scheduler/run-on-demand-item-job` |
| notebook-api | *Manage and execute Fabric notebooks with public APIs* — `/fabric/data-engineering/notebook-public-api` |
| assign-capacity | *Workspaces - Assign To Capacity* — `/rest/api/fabric/core/workspaces/assign-to-capacity` |
| ado-spn | *Use Service Principals and Managed Identities* — `/azure/devops/integrate/get-started/authentication/service-principal-managed-identity` |

### Dichiarate NON verificate

| Rif. | Affermazione non verificata |
|---|---|
| §2.3 | Node size del pool Spark (assunta 8 VCore/nodo) e conseguente numero di sessioni concorrenti |
| §5.4 | Tassonomia dei permessi Azure Repos: relazione tra *Contribute* e *Contribute to pull requests* |
| §6.2 | Assenza di API REST per i task flow: è assenza di evidenza nella reference consultata, **non** prova di impossibilità |
| §8 R-13 | Unicità dei nomi di workspace a livello di tenant e ritenzione nel cestino |
| §6.1 | Numero massimo di cartelle per workspace (errore `TooManyFolders`, valore non documentato) |
| — | Comportamento reale della sincronizzazione Git delle cartelle, data la contraddizione tra due pagine ufficiali (§6.1) |

> Ognuna di queste sei righe è un candidato naturale per lo spike S1-01, che il backlog già
> prevede e questa review conferma essere l'item giusto al posto giusto.

---

# 13. Addendum 2026-08-20b — le pipeline CI/CD esistenti come rail

> Revisione della review alla luce di un fatto che la v1.0 non conosceva. Non è un'aggiunta
> cosmetica: cambia due dei tre rilievi bloccanti, supera un ADR e ne apre uno nuovo.

## 13.1 Il fatto nuovo

Esiste già, ed è funzionante, un asset di deploy Fabric multi-tenant:
`IP.dai_fabric_environments`. L'ho ispezionato direttamente (`README.md`, `docs/ARCHITECTURE.md`,
`deploy/`, `.github/workflows/`, `config/`, `scripts/`, `fabric-items/`). Ciò che segue è
**verificato sul codice**, non riferito:

| Elemento | Riscontro nel repo |
|---|---|
| Deploy multi-tenant via GitHub Actions con **OIDC** | `deploy.yml`, job `deploy`: `permissions: id-token: write` solo su quel job, `environment: deploy-${{ inputs.tenant }}`, `azure/login@v2` senza secret |
| **Nessun secret persistente per il deploy** | Il token OIDC è scritto su file temporaneo e consumato da `WorkloadIdentityCredential` |
| **Due service principal** | SP di Deploy (OIDC effimero; Admin sui workspace, Capacity Contributor, owner/scheduler SJD, Key Vault Secrets User) e SP di Runtime (secret nel KV del cliente). Loro ADR-1 |
| Moduli Python di deploy | `workspace_manager` (preflight + ensure idempotente + governance), `connection_manager`, `shortcut_manager`, `lake_manager`, `onelake_uploader`, `sjd_scheduler`, `fabric_link_manager`, `lakehouse_refresh` |
| Item deployati con **fabric-cicd** | `pip install "fabric-cicd==1.1.0"`, sorgenti in `fabric-items/`, parametrizzazione via `parameter.yml` |
| Parametrizzazione per istanza | `config/<cliente>/tenant.json` + `parameter.yml` + `scripts/validate_config.py` con jsonschema, e materializzazione da variabili d'ambiente del GitHub Environment |
| Idempotenza come principio | Loro ADR-6: ogni step è create-or-update, il rimedio standard è il re-run (roll-forward) |
| Preflight **anti cross-tenant** | Confronto tra il claim `tid` del token e `TENANT_ID` di configurazione, prima di qualunque scrittura |
| Concorrenza | `concurrency: deploy-${{ inputs.tenant }}`, `cancel-in-progress: false` |
| Qualità | 7 ADR, 56 test, 89% di coverage su `deploy/` |

**Tre elementi che il briefing non menzionava e che contano più di quanto sembri:**

1. Esistono già **workflow separati per le operazioni distruttive e diagnostiche**:
   `delete-workspace.yml`, `delete-connection.yml`, `fabric-link-diagnose.yml`,
   `lake-metadata-diagnose.yml`. `delete-workspace.yml` è un `workflow_dispatch` parametrico che
   cancella un workspace via `DELETE /v1/workspaces/{id}` con l'identità OIDC. **È già, di fatto,
   il rail *Sweep* di ADR-0004** — manca solo lo scheduler e il criterio di selezione.
2. Il repo ha **TODO di sicurezza aperti e dichiarati**: action di terze parti non pinnate per
   commit SHA, dipendenze `pip install` non pinnate per hash. Sono scritti nel file, non nascosti.
   Chi copia il pattern **copia anche i TODO**.
3. L'asset dimostra di saper già risolvere il problema «condividere codice tra repo senza
   condividere il sorgente»: loro ADR-7 distribuisce un wheel come asset di GitHub Release e lo
   consuma cross-repo. La decisione di duplicare i pattern nel repo Agentic è quindi una scelta
   **contro un meccanismo interno già collaudato**, non l'assenza di alternative.

**Non verificato [NV]**: le pipeline equivalenti su Azure DevOps con `scripts/deploy.ps1`. In
questo repository non esiste alcun `.ps1` di deploy né alcun `azure-pipelines.yml`: gli unici
`.ps1` presenti stanno nei submodule e non riguardano il deploy. L'esistenza di quelle pipeline è
un'affermazione dell'owner che non ho potuto ispezionare, e **il progetto Agentic usa Azure DevOps
in fase 1**: è quindi il ramo ADO — non quello GitHub — a dover essere verificato per primo.

## 13.2 La domanda: il Dev Agent deve avere permessi su Fabric?

### Risposta

**Sì, ma solo `Viewer`, solo sui workspace effimeri e su `dev`, e solo come canale di diagnosi in
eccezione — mai come canale primario di esito.**

L'ipotesi di @karl («nessun permesso Fabric, solo lanciare una pipeline e leggerne l'esito») è
**corretta nel nucleo e sbagliata nell'assoluto**. È corretta nel dire che il canale primario
dell'esito deve essere l'artefatto della pipeline e che l'agente non deve poter *cambiare* nulla
in Fabric. È sbagliata nel dire *zero permessi*, per due ragioni indipendenti:

1. l'owner ha chiesto esplicitamente la lettura diretta da Fabric, e togliergliela significa
   rendere l'agente **cieco esattamente quando le cose vanno male** — cioè nel caso in cui il suo
   giudizio serve;
2. `Viewer` è, verificato, **l'unico ruolo Fabric che è davvero di sola lettura** e che copre già
   il fabbisogno diagnostico.

### Perché `Viewer` funziona — verificato

Dalla tabella ufficiale dei ruoli di workspace **[V]** roles-workspaces (pagina aggiornata al
2026-08-18):

| Capacità | Viewer |
|---|---|
| Visualizzare l'output di esecuzione di pipeline e notebook | **sì** |
| Monitorare lo stato dei run via **Job Scheduler API**, inclusi metadati di run ed **exit value dei notebook** | **sì** (nota esplicita della pagina: «all roles including Viewer») |
| Eseguire o annullare pipeline e notebook | **no** |
| Scrivere o cancellare item | **no** |
| Collegare il workspace a un repository Git | **no** — è Admin |
| Aggiornare o cancellare il workspace | **no** — è Admin |
| Leggere Lakehouse/Warehouse via **OneLake API e Spark** (ReadAll) | **no** |

E, sempre **[V]** roles-workspaces: «Microsoft Entra ID service principals (app registrations) can
also be assigned to workspace roles and **inherit the same permissions as users** for API-based
operations in Fabric, including the Items REST API and the Job Scheduler API.»

Quindi: un service principal in ruolo `Viewer` può leggere `state`, `status`, output ed exit value
di un run — che è precisamente ciò che serve al Dev Agent per diagnosticare — e **non** può
eseguire, scrivere, cancellare o collegare Git. La sola lettura è imponibile in modo effettivo.

### I buchi nell'ipotesi di @karl

**Buco 1 — `Viewer` legge i dati.** **[V]** roles-workspaces: il Viewer può «Connect to SQL
analytics endpoint of Lakehouse or the Warehouse» e «Read Lakehouse and Data warehouse data and
shortcuts with T-SQL through TDS endpoint (**ReadData**)». Il divieto ADR-0005 («nell'agente non
entra dato») **non è imposto dal ruolo**: sul canale SQL endpoint resta una regola di prompt, cioè
esattamente il tipo di limite che `04-identita-e-permessi.md` §1 dichiara inaffidabile. Il punto
(b) di @karl — «risolve buona parte di Q-7» — è quindi **vero solo se `Viewer` non viene
concesso**, e diventa falso nel momento in cui lo si concede. La conseguenza operativa non è
rinunciare a `Viewer`: è **legare la concessione di `Viewer` alla classificazione del dato del
workspace**. Formalizzato in ADR-0008 e recepito come revisione di ADR-0005.

**Buco 2 — il permesso Fabric non sparisce, si sposta di identità.** L'identità della pipeline
resta Admin sui workspace e Contributor sulla capacity. Quello che cambia non è l'esistenza del
privilegio, ma **chi lo detiene e come lo si ottiene**: un'identità non pilotata da un LLM, con
credenziale emessa per singolo job e non conservata. È un guadagno reale, ma va detto per quello
che è.

**Buco 3 — la credenziale locale non sparisce, cambia bersaglio.** Il punto (a) di @karl è vero a
metà. **[V]** ado-spn: un service principal **non può creare PAT**, **non può autenticarsi
interattivamente** e **non supporta i flussi OAuth di Azure DevOps**; le sue credenziali sono
«certificates or client secrets» (il certificato è la modalità raccomandata). OIDC federato non è
disponibile per un processo che non gira in CI, perché non esiste un issuer di cui Entra si fidi.
Quindi sulla macchina dell'owner **resta una credenziale long-lived**: non più verso Fabric, ma
verso Azure DevOps.

Il guadagno vero è il **raggio d'azione**, e va misurato così:

| | Prima (progetto @karl) | Dopo (rail = pipeline) |
|---|---|---|
| Cosa vale la credenziale rubata | Contributor sulla capacity, creazione workspace, esecuzione notebook, scrittura su Fabric | Accodare **N pipeline nominate**, leggere run e artefatti, e (se concesso) leggere in `Viewer` |
| Con quale switch di tenant | «Service principals can create workspaces, **connections, and deployment pipelines**» | Solo «Service principals can use Fabric APIs», e solo se si concede `Viewer` |

**Il collasso del raggio d'azione è la vera ragione per adottare il modello.** Non l'eliminazione
della credenziale, che non avviene.

Resta un rischio residuo che **nessuno dei due modelli chiude**: la macchina che custodisce la
credenziale è la stessa su cui gira l'agente, che ha una shell. RNF-02 («accesso negato a
variabili d'ambiente e token cache») è una regola di tooling, non di piattaforma. Il modello a
pipeline **non lo risolve, ne riduce il valore del bottino**. Va scritto così nel PRD invece di
lasciarlo implicito, e va esteso esplicitamente all'archivio certificati di Windows, che oggi
RNF-02 non nomina.

**Buco 4 — RB-4, la nuova falla: chi controlla lo YAML controlla l'identità della pipeline.**
È il rilievo più serio di questo addendum, e non compare né nel briefing né nell'asset ispezionato.

Il Dev Agent scrive codice su un branch di feature. Se una pipeline privilegiata è eseguibile
**con la definizione YAML presa da quel branch**, l'agente può riscrivere la pipeline e farle fare
qualunque cosa l'identità della pipeline possa fare — cioè **Admin su tutti i workspace e
Contributor sulla capacity**. L'intero modello «l'agente non tocca Fabric» verrebbe aggirato senza
che nessun permesso sia stato violato: sarebbe l'agente a scrivere il codice che gira con
un'identità più potente della sua. È la definizione manualistica di escalation di privilegio, ed è
il modo in cui questo design fallirebbe davvero.

Le contromisure esistono e sono verificate **[V]** approvals / ado-permissions:

1. gli **approvals & checks non stanno nello YAML**: «Approvals and other checks aren't defined in
   the yaml file. **Users modifying the pipeline yaml file can't modify the checks** performed
   before start of a stage.» Sono configurati dal proprietario della risorsa nell'interfaccia;
2. il check **Branch control** impone che tutte le risorse collegate al run provengano da branch
   consentiti (`refs/heads/main`), e il check **Required template** impone che la pipeline estenda
   un template specifico preso da un ref dichiarato;
3. **service connection ed environment** possono essere ristretti a pipeline nominate
   («Restrict access» → «Add pipeline»), non aperti a tutte le pipeline del progetto;
4. «Edit build pipeline» è un permesso **distinto** da «Queue builds», e va negato.

La conseguenza per il contratto dei rail è vincolante e va scritta: **il rail invoca una pipeline
la cui definizione è ancorata a `main` e parametrizzata; non invoca mai una pipeline la cui
definizione provenga dal branch di feature.** Il branch di feature è un *parametro* del run, non
la sua definizione.

**Buco 5 — lanciare una pipeline è un privilegio, e va separato per pipeline.** Verificato
**[V]** ado-permissions: «Queue builds» è un permesso **impostabile a livello di oggetto** (la
singola pipeline), con `Allow`/`Deny`/`Not set` e possibilità di disattivare l'ereditarietà. Ma —
ed è il dettaglio che si sbaglia — **il gruppo `Contributors` ha «Queue builds» per default**:
mettere il service principal fra i Contributors gli darebbe l'accodamento su **tutte** le
pipeline, compresa quella di produzione.

Ne discende una regola di progetto, non un suggerimento:

> Due famiglie di pipeline, distinte nel nome e nella sicurezza.
> **`pipe_agent_*`** — accodabili dagli agenti, bersaglio esclusivo `feature`/`dev`, non consumano
> alcun environment protetto.
> **`pipe_human_*`** — `Deny` esplicito su «Queue builds» per le identità degli agenti con
> ereditarietà disattivata, **e** stage che consuma un environment con check di **Approvals** e
> **Branch control**.

I due livelli sono indipendenti, che è la condizione posta da `04-identita-e-permessi.md` §4:
perché un agente deployi in produzione servirebbero **due errori distinti** — una regola di
permesso sbagliata *e* un check di environment rimosso.

Sul ramo GitHub il controllo è ancora più forte, ed è già nel pattern dell'asset: **[V]** gh-oidc
il claim `sub` del token OIDC vale `repo:org/repo:environment:prod` e il token viene emesso
**per job**; **[V]** gh-environments un job che referenzia un environment con *required reviewers*
non parte finché un umano non approva, e i secret dell'environment sono accessibili «only after
any configured rules pass». Tradotto: **niente approvazione umana, niente token Fabric.** Il
divieto di deploy in produzione diventa una proprietà del protocollo di autenticazione, non una
riga in una matrice. Nell'asset `deploy.yml` usa già `environment: deploy-<tenant>`; il README
dichiara però che la configurazione dell'environment è ancora da fare — quindi il controllo
**esiste come struttura e non come stato**. Va verificato, non assunto.

**Buco 6 — latenza e opacità.** Un rail che invoca una pipeline aggiunge: accodamento, avvio
dell'agente di build, checkout, installazione delle dipendenze. Nell'asset ispezionato il job di
deploy fa `pip install fabric-cicd azure-identity requests jsonschema pytest pyyaml responses` a
ogni run, senza cache e senza pin per hash. **[NV]** non ho misurato i tempi reali; **[D]** una
sequenza checkout + install + login su agente ospitato è nell'ordine dei minuti, e il rail
*Run load* viene invocato più volte per ticket. È un rischio diretto su **KPI-2 (< 30 minuti)** che
il PRD non censisce.

Mitigazioni, nell'ordine in cui vanno provate: pipeline **piccole e dedicate** per ogni rail
(non riusare la pipeline di deploy monolitica), cache delle dipendenze, e solo in ultima istanza
un agent pool self-hosted.

Sull'**opacità** la correzione è più importante della latenza, perché tocca il contratto del rail
*Run load* e il rilievo §4.2 L4:

> Ogni pipeline invocabile da un agente pubblica un artefatto `rail-result.json` con schema
> versionato. **Il rail restituisce quell'artefatto, non i log.** L'assenza dell'artefatto è essa
> stessa un fallimento del rail, distinto dal fallimento del job.

Lo schema minimo deve contenere: `outcome` ∈ {`success`, `technical_failure`, `quality_failure`},
`run_id`, `workspace_id`, e per dataset `extracted_count`, `loaded_count`, `source_count`,
`supports_source_count`, `pk_check`. Due conseguenze non ovvie:

- la distinzione **fallimento tecnico / fallimento di qualità** (contratto *Run load*, §4 di
  `03-rail-script.md`) viene calcolata **dentro la pipeline**, che ha l'accesso a Fabric e i
  conteggi, e serializzata. **L'agente non ha bisogno di Fabric per distinguere B1 da B2.** È
  questo che rende `Viewer` un canale di eccezione e non il canale primario;
- la tautologia del conteggio alla sorgente (§4.2 L4) **non è risolta** dal cambio di trasporto:
  è un difetto del contratto di connettore, non del rail. Il flag `supports_source_count` entra
  nello schema dell'artefatto, e `NON APPLICABILE` motivato resta l'esito corretto.

Va inoltre recepito nel contratto un fatto verificato **[V]** api-throttling già presente in §8
R-15: il rifiuto per capacity satura non è un errore dell'agente. Con il rail a pipeline il
comportamento migliora — **[V]** concurrency i job avviati da pipeline vengono **accodati**,
quelli avviati via API del notebook vengono **rifiutati** — il che trasforma la raccomandazione
R1.2 da buona pratica a **conseguenza necessaria del modello**. È l'unico punto in cui il fatto
nuovo rende il design *più* solido senza costi.

**Buco 7 — lo Sweep.** La domanda «chi esegue lo Sweep se l'agente non ha permessi Fabric?» ha una
risposta migliore di quella di ADR-0004: **nessuno lo esegue, lo esegue lo scheduler.** Cancellare
un workspace richiede `Admin` **[V]** roles-workspaces, che l'agente non avrà mai; una pipeline
schedulata con l'identità di deploy lo ha già. `delete-workspace.yml` nell'asset dimostra che
l'operazione è già implementata e funzionante.

Due trappole verificate, entrambe capaci di rendere lo Sweep silenziosamente inerte:

- **[V]** ado-schedules una pipeline schedulata **non parte se il codice non è cambiato** dalla
  precedente esecuzione riuscita: senza `always: true` lo Sweep smetterebbe di girare esattamente
  nei periodi di inattività, cioè quando serve;
- **[V]** ado-schedules le schedulazioni definite nell'interfaccia **prevalgono** su quelle YAML, e
  la schedulazione è letta dallo YAML **del branch a cui si applica**: lo Sweep va schedulato su
  `main` e nessuno deve aggiungere schedulazioni da UI.

Terza raccomandazione, di merito: lo Sweep **non deve dipendere dal tracker** per decidere. Il
criterio primario sia deterministico — nome conforme al pattern, età oltre TTL — e la
consultazione del work item resti un filtro di sicurezza per non cancellare lavoro in corso. Così
lo Sweep continua a funzionare anche quando l'astrazione del tracker (RF-06) cambia.

**Buco 8 — il repo separato.** Il costo della divergenza non è teorico ed è già visibile: l'asset
ha TODO di sicurezza aperti (SHA pinning delle action, pin per hash delle dipendenze). Copiando i
pattern si copiano i TODO, e la loro chiusura andrà fatta **due volte**. Lo stesso vale per
l'adeguamento alle API Fabric in preview (Folders API, ADR-0003) e per l'ammontare di hardening
rappresentato dai 56 test dell'asset, che nel repo Agentic ripartirà da zero.

Ciò che **va copiato per forza**, perché è controllo di sicurezza o presupposto di un requisito
già scritto, non comodità:

| Pattern | Perché è obbligatorio |
|---|---|
| OIDC + un environment per bersaglio, con federated credential vincolata all'environment | È il meccanismo che rende «deploy umano» una proprietà del protocollo (RF-72) |
| Separazione SP di deploy / SP di runtime | Loro ADR-1. Senza, l'esecuzione schedulata dipende da un token scaduto |
| Idempotenza e roll-forward su ogni step | Loro ADR-6 = il nostro RNF-07 |
| `config/<istanza>/` + jsonschema + `validate_config` fail-fast | È l'attuazione di RF-80 e RNF-11, non un dettaglio di stile |
| Preflight anti cross-tenant prima di ogni scrittura | Nel nostro caso: verifica che il workspace bersaglio corrisponda al work item. È il controllo che impedisce a un agente confuso di scrivere nel workspace sbagliato |
| Concorrenza per bersaglio | Race condition sul workspace. Su ADO l'equivalente è il check **Exclusive lock** **[V]** approvals |

La mitigazione onesta della divergenza è dichiararla: un `PROVENANCE.md` che registri, per ogni
modulo copiato, repository e commit di origine, e una revisione periodica. Una divergenza tracciata
è una decisione; una divergenza non tracciata è un incidente rimandato. Formalizzato in ADR-0009.

## 13.3 Effetto sui rilievi bloccanti

| ID | Stato precedente | Stato dopo l'addendum |
|---|---|---|
| **RB-1** — lo switch di tenant non separabile | Bloccante su S0-07 | **Declassato.** Il Dev Agent non crea più workspace: non gli serve lo switch «create workspaces, connections, and deployment pipelines», ma solo «Service principals can use Fabric APIs», e **solo se** gli si concede `Viewer`. Lo switch pericoloso resta necessario alla sola identità di deploy, che non è pilotata da un LLM. Il controllo di S0-06 cambia di segno: non più «il deploy in prod deve fallire» ma **«`POST /v1/workspaces` con l'identità dell'agente deve fallire»** |
| **RB-2** — service principal su Azure DevOps | Bloccante su S0-05 | **Invariato e più centrale.** L'agente ora vive *dentro* Azure DevOps: accodare pipeline, leggere run e artefatti, work item, repo. **[V]** ado-spn restano necessari l'aggiunta esplicita da PCA e una licenza **Basic** per identità, senza sconto multi-organizzazione. È il primo collo di bottiglia del percorso critico |
| **RB-3** — RF-18 senza trigger | Bloccante su S1 | **Risolto.** Lo Sweep diventa una pipeline schedulata: non serve un quarto trigger del dispatcher, non serve che l'agente abbia `Admin`. ADR-0004 resta valido nella decisione (TTL, non merge) e cambia esecutore |
| **RB-4** — escalation via definizione YAML | — | **Nuovo, bloccante su S0-07 e sul contratto dei rail.** Vedi §13.2 buco 4 |

## 13.4 Effetto sulle domande aperte

| Domanda | Effetto |
|---|---|
| **Q-5** (sizing e cleanup) | Migliora. Il carico agentico passa da chiamate API dirette a job avviati da pipeline, che **[V]** concurrency vengono accodati anziché rifiutati sotto throttling. ADR-0001 resta necessario: il throttling è per capacity, e questo non cambia |
| **Q-7** (perimetro dei dati) | **Migliora sul canale primario, peggiora sul canale di eccezione.** Se l'esito arriva da un artefatto strutturato, nel prompt entrano solo conteggi ed esiti. Ma `Viewer` apre l'endpoint SQL: la regola ADR-0005 su quel canale torna a essere una convenzione. Da qui la condizione di ADR-0008 |
| **Q-9** (cartelle e task flow) | Invariata nel merito, cambia l'esecutore: le cartelle le crea la pipeline con la Folders API in preview, non l'agente |

## 13.5 Cosa cambia nel backlog dello Slice 0

**Il Gruppo A resta invariato e può partire.** Il Gruppo B cambia in modo sostanziale: le tre
correzioni C1–C3 di §10 restano valide ma si riformulano, e se ne aggiungono tre.

| # | Item | Natura |
|---|---|---|
| C1′ | **Riscrivere S0-07**: al Dev Agent **non** si concede lo switch «create workspaces, connections, and deployment pipelines». Si valuta il solo «Service principals can use Fabric APIs», ristretto al gruppo, e **subordinato** alla decisione di ADR-0008 | Sostituisce C1 |
| C2 | Abilitare i service principal su Azure DevOps: aggiunta da PCA, licenza Basic, permessi minimi | Invariato (RB-2) |
| C3′ | Portare la verifica pratica di S0-06 da 4 a **9 controlli** — vedi sotto | Sostituisce C3 |
| **N1** | **Nuovo item: separazione delle famiglie di pipeline.** Creare `pipe_agent_branch_out`, `pipe_agent_run_load`, `pipe_agent_sync`, `pipe_human_promote_test`, `pipe_human_promote_prod`, `pipe_sched_sweep`. Impostare «Queue builds» a livello di oggetto: `Allow` sulle `pipe_agent_*`, **`Deny` con ereditarietà disattivata** sulle `pipe_human_*`. Il service principal **non** entra nel gruppo `Contributors` | Nuovo, da RB-4 e buco 5 |
| **N2** | **Nuovo item: protezione delle pipeline privilegiate.** Environment `prod` con check **Approvals** (approvatore = owner) e **Branch control** su `refs/heads/main`; service connection e environment ristretti alle pipeline nominate; verifica che «Edit build pipeline» sia negato agli agenti | Nuovo, da RB-4 |
| **N3** | **Nuovo item: schema dell'artefatto `rail-result.json`**, versionato nel repo, con i campi di §13.2 buco 6. È una precondizione del contratto dei rail, non un dettaglio implementativo | Nuovo, da buco 6 |
| **N4** | **Nuovo item: credenziale dell'agente verso Azure DevOps.** Certificato anziché client secret **[V]** ado-spn, collocazione dichiarata, rotazione pianificata, ed estensione esplicita di RNF-02 all'archivio certificati | Nuovo, da buco 3 |

**Verifica pratica di S0-06 — da 4 a 9 controlli.** Con l'identità del Dev Agent:

1. `git push` su `main` → deve fallire;
2. merge di una PR → deve fallire;
3. lettura di variabili d'ambiente e token cache → deve fallire;
4. **`POST /v1/workspaces`** (creazione workspace Fabric) → deve fallire;
5. **`POST /v1/workspaces/{id}/items`** su un workspace effimero → deve fallire (`Viewer` non
   scrive);
6. **`GET` dello stato di un job** su un workspace effimero → deve **riuscire**, se ADR-0008 è
   accettato;
7. **accodamento di `pipe_agent_run_load`** → deve riuscire;
8. **accodamento di `pipe_human_promote_prod`** → deve fallire;
9. con l'identità del Review Agent: `git push` → deve fallire, **voto sulla PR → deve riuscire**.

I controlli 7 e 8 sono la prova che la separazione delle due famiglie esiste davvero. Senza di
essi, RB-4 resta aperto qualunque cosa dica la configurazione.

## 13.6 ADR generati o modificati da questo addendum

| ADR | Azione |
|---|---|
| **ADR-0002** | **Superato** da ADR-0007. Il suo *negativo* (non usare le Deployment Pipelines) è confermato e rafforzato; il suo *positivo* (promozione per *update from Git* manuale) è sostituito |
| **ADR-0004** | **Rivisto**: la decisione (TTL, non merge) resta; l'esecutore passa da rail invocato dallo scheduler locale a **pipeline schedulata** |
| **ADR-0005** | **Rivisto**: il perimetro include l'artefatto della pipeline; si dichiara che `Viewer` apre un canale su cui la regola è convenzione e non permesso |
| **ADR-0007** | **Nuovo**: le pipeline CI/CD esistenti come rail e come canale di promozione |
| **ADR-0008** | **Nuovo**: permessi Fabric del Dev Agent — `Viewer` condizionato, nessuna scrittura |
| **ADR-0009** | **Nuovo**: repository separato con copia dei pattern e provenienza dichiarata |

## 13.7 Fonti aggiuntive, verificate su Microsoft Learn e GitHub Docs il 2026-08-20

| Sigla | Pagina |
|---|---|
| roles-workspaces | *Roles in workspaces in Microsoft Fabric* — `/fabric/fundamentals/roles-workspaces` (aggiornata 2026-08-18) |
| ado-permissions | *Manage security in Azure Pipelines* — `/azure/devops/pipelines/policies/permissions` |
| approvals | *Pipeline deployment approvals* — `/azure/devops/pipelines/process/approvals` |
| ado-schedules | *Configure schedules to run pipelines* — `/azure/devops/pipelines/process/scheduled-triggers` |
| ado-run-pipeline | *Runs - Run Pipeline* — `/rest/api/azure/devops/pipelines/runs/run-pipeline` (scope `vso.build_execute`) |
| gh-dispatch | *REST API endpoints for workflows — Create a workflow dispatch event* — `docs.github.com/rest/actions/workflows` |
| gh-environments | *Managing environments for deployment* — `docs.github.com/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments` |
| gh-oidc | *OpenID Connect* — `docs.github.com/actions/concepts/security/openid-connect` |

### Nuove affermazioni dichiarate NON verificate

| Rif. | Affermazione |
|---|---|
| §13.1 | Esistenza e contenuto delle pipeline Azure DevOps equivalenti (`scripts/deploy.ps1`): non presenti nel repository ispezionato |
| §13.2 buco 6 | Tempi reali di avvio di una pipeline ADO su agente ospitato, e quindi l'entità effettiva dell'impatto su KPI-2 |
| ADR-0007 | Supporto di **fabric-cicd** per gli item **Report in formato PBIR** e per i semantic model TMDL. È la stessa incompatibilità che ha motivato ADR-0002: cambiare canale **non** la risolve automaticamente. **Spike obbligatorio in S1-01** prima di considerare chiusa la lane Power BI |
| §13.2 buco 5 | Comportamento del `Deny` su «Queue builds» quando l'identità appartiene anche a un gruppo con `Allow`: la precedenza dichiarata del deny va provata, non assunta |

