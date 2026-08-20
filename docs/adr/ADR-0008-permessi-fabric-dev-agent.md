# ADR-0008 — Permessi Fabric del Dev Agent: `Viewer` condizionato, nessuna scrittura

| Campo | Valore |
|---|---|
| Stato | **Accettato** — decisione dell'owner 2026-08-20 |
| Data | 2026-08-20b |
| Autore | Ralph (Fabric Solution Architect) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §13.2 |
| Decisori | Owner |
| Correlati | ADR-0005 (revisione 2026-08-20b) · ADR-0007 |

---

## Contesto

Il design originale (`04-identita-e-permessi.md` §3.1) attribuisce al Dev Agent: creazione di
workspace Fabric, `Contributor` sulla capacity, utente delle connessioni dati. Con ADR-0007 i rail
diventano pipeline: chi tocca Fabric è l'identità di deploy della pipeline, e quella matrice non
descrive più il sistema.

@karl ha proposto l'assetto opposto: **il Dev Agent non ha alcun permesso Fabric**; ha solo il
permesso di lanciare una pipeline e leggerne l'esito. L'owner ha però posto un requisito
esplicito: **l'agente deve poter leggere gli esiti anche interrogando Fabric direttamente**, non
solo dagli artefatti della pipeline.

Le due posizioni sono conciliabili solo se esiste, su Fabric, un permesso di lettura che sia
davvero tale. Verificato **[V]** roles-workspaces (pagina aggiornata al 2026-08-18):

| Capacità | Admin | Member | Contributor | **Viewer** |
|---|:--:|:--:|:--:|:--:|
| Aggiornare o cancellare il workspace | ✅ | | | |
| Collegare il workspace a un repository Git | ✅ | | | |
| Scrivere o cancellare pipeline, notebook, SJD, lakehouse | ✅ | ✅ | ✅ | |
| Eseguire o annullare l'esecuzione di notebook e pipeline | ✅ | ✅ | ✅ | |
| **Visualizzare l'output di esecuzione di pipeline e notebook** | ✅ | ✅ | ✅ | **✅** |
| Leggere Lakehouse/Warehouse via OneLake API e Spark (ReadAll) | ✅ | ✅ | ✅ | |
| **Leggere Lakehouse/Warehouse con T-SQL via TDS endpoint (ReadData)** | ✅ | ✅ | ✅ | **✅** |

E, nella stessa pagina: «For Job Scheduler API execution, Admin, Member, and Contributor can start
and cancel runs; **all roles including Viewer can monitor run status and view execution output,
including run metadata such as status and exit values returned by notebook runs**». I service
principal «inherit the same permissions as users for API-based operations».

Due conclusioni, una favorevole e una scomoda:

1. **`Viewer` copre il fabbisogno diagnostico** — stato del run, output, exit value del notebook —
   ed è genuinamente incapace di eseguire, scrivere, cancellare o collegare Git;
2. **`Viewer` legge i dati** attraverso l'endpoint SQL. Il divieto di ADR-0005 su quel canale
   **non è imposto dal ruolo**: resta una regola di prompt, cioè il tipo di limite che
   `04-identita-e-permessi.md` §1 dichiara inaffidabile.

## Decisione

**1. Il Dev Agent non ha alcun permesso di scrittura su Fabric, in modo permanente.** Nessun ruolo
`Admin`, `Member` o `Contributor` su alcun workspace; nessun ruolo sulla capacity; nessuna capacità
di creare workspace, connessioni o deployment pipeline. Il rail crea e scrive **tramite pipeline**,
con l'identità di deploy che l'agente non può impersonare.

**2. Il Dev Agent ha il ruolo `Viewer`, e solo `Viewer`, sui soli workspace effimeri
`ws_agentic_feature_wi<id>` e su `ws_agentic_dev`.** Nessun ruolo su `ws_agentic_test` e
`ws_agentic_prod` — è l'assenza di ruolo, non un divieto dichiarato, a rendere impossibile il
deploy (RF-72).

**3. La concessione di `Viewer` è legata alla classificazione del dato, non al ruolo dell'agente.**

| Dati nel workspace | `Viewer` al Dev Agent |
|---|---|
| Sintetici o open data (fase 1) | **Concesso** |
| Dati reali di cliente | **Revocato.** La diagnosi passa esclusivamente dall'artefatto della pipeline |

È la regola che rende accettabile il punto 2: si accetta che l'agente veda dati **perché quei dati
non contano**, e il giorno in cui contano il permesso cade. La verifica di questa condizione entra
nel runbook di onboarding di un nuovo cliente (`docs/functional/06`).

**4. Fabric è un canale di eccezione, non il canale primario.** L'esito di un rail proviene
**sempre** dall'artefatto `rail-result.json` (ADR-0007 punto 5). L'interrogazione diretta di Fabric
è ammessa in **diagnosi**, quando l'artefatto non basta a spiegare un fallimento. **L'evidenza
allegata alla PR proviene sempre dall'artefatto**, mai da una lettura ad hoc dell'agente: è
riproducibile, è firmata da un run id, e il Review Agent può giudicarla senza accedere a Fabric
(RF-64).

**4-bis. Le analisi quotidiane di dati sono eseguite dal rail `diagnose_data`, non dal modello.**
La pipeline interroga Bronze, Silver o sorgente con la credenziale tecnica del cliente e restituisce
all'agente solo evidenze approvate: conteggi, distribuzioni, null/duplicati, drift di schema,
watermark, riconciliazioni e chiavi mascherate. Per dati reali il rail non pubblica righe grezze,
valori PII o segreti. Un caso che richieda tali valori escala a un umano autorizzato o a un canale
di analisi esplicitamente approvato dal cliente.

**5. Il tenant setting «Service principals can use Fabric APIs» è ristretto al gruppo di sicurezza
degli agenti**, ed è l'**unico** switch di tenant richiesto dall'identità del Dev Agent. Lo switch
«Service principals can create workspaces, connections, and deployment pipelines» **non gli viene
concesso**: serve alla sola identità di deploy, che non è pilotata da un LLM.

**6. Il Review Agent resta a zero permessi Fabric**, senza eccezioni (RF-64). Non cambia nulla:
giudica la verità di Git e le evidenze allegate.

**7. La concessione è verificata praticamente**, non solo configurata. Con l'identità del Dev
Agent, al bootstrap e a ogni modifica dei permessi:

- `POST /v1/workspaces` → **deve fallire**;
- `POST /v1/workspaces/{id}/items` su un workspace effimero → **deve fallire**;
- `POST .../jobs/instances` (esecuzione di un job) → **deve fallire**;
- `GET .../jobs/instances/{id}` (stato di un run) → **deve riuscire**;
- qualunque chiamata su `ws_agentic_prod` → **deve fallire**.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Zero permessi Fabric** (ipotesi @karl in forma pura) | Contraddice un requisito esplicito dell'owner e rende l'agente cieco proprio nel caso in cui il suo giudizio serve: quando l'artefatto non spiega il fallimento. Il guadagno di sicurezza rispetto a `Viewer` è reale ma limitato al canale dati, che il punto 3 chiude in altro modo |
| **`Contributor` sui soli workspace effimeri** | Permetterebbe all'agente di eseguire notebook direttamente, aggirando la pipeline — e quindi il rilevamento del throttling, la produzione dell'artefatto e ogni tracciabilità. È la scorciatoia che un agente prende alla prima occasione: «chiamo direttamente il notebook, è più veloce» |
| **`Viewer` su tutti i workspace, `prod` incluso** | L'assenza di ruolo su `prod` è l'unico controllo che rende il divieto di deploy verificabile. La lettura di produzione non serve a nessuno dei casi d'uso dell'agente |
| **Permesso di lettura tramite un'identità terza condivisa** | Rompe la tracciabilità nell'audit log (RF-74): due agenti indistinguibili sono un agente solo |
| **Concedere `Viewer` e vietare l'endpoint SQL per configurazione** | **[NV]** non risulta un controllo Fabric che disattivi l'endpoint SQL per un singolo principal mantenendo `Viewer`. Se emergesse, sarebbe la soluzione migliore e questo ADR andrebbe rivisto |

## Conseguenze

**Positive**
- Il perimetro di scrittura dell'agente su Fabric è **vuoto**, e lo è per costruzione: non esiste
  una configurazione errata che possa concederglielo per sbaglio, perché la concessione
  richiederebbe un secondo switch di tenant che nessuno gli ha dato.
- **RB-1 è declassato**: lo switch indivisibile che concedeva contestualmente `Create Workspace`,
  `Create Connection` e `Create Deployment Pipeline` non riguarda più l'agente.
- La credenziale sulla macchina dell'owner, se esfiltrata, **non consente di scrivere su Fabric**.
- L'agente conserva la capacità di diagnosticare, che è la ragione per cui esiste.

**Negative**
- **`Viewer` legge i dati**, e su quel canale ADR-0005 è una convenzione, non un permesso.
  Il punto 3 lo rende accettabile in fase 1 e lo chiude quando smette di esserlo — ma va detto
  che è un limite **noto e accettato**, non un problema risolto.
- La revoca del punto 3 è un'azione umana che qualcuno deve ricordarsi di fare. Va messa nel
  runbook di onboarding cliente come **voce bloccante**, altrimenti è la classica concessione che
  nessuno revoca (cfr. `04-identita-e-permessi.md` §7).
- L'agente resta comunque dipendente dalla pipeline per ogni azione: un difetto della pipeline lo
  blocca del tutto. È il prezzo dell'asimmetria, ed è accettato.

**Da fare**
- Riscrivere la matrice dei permessi in `04-identita-e-permessi.md` §3.1: cadono «Creazione
  workspace Fabric: consentita» e «Capacity: Contributor»; entra «Workspace effimeri e `dev`:
  **Viewer**, condizionato alla classificazione del dato»; entrano i permessi Azure DevOps di
  accodamento (ADR-0007).
- Portare la verifica pratica di S0-06 da 4 a **9 controlli** (§13.5 della review).
- Aggiungere al runbook `docs/functional/06-onboarding-nuovo-cliente.md` la voce bloccante sulla
  revoca di `Viewer` in presenza di dati reali.
- Aggiornare RF-13 e il modello di permessi del PRD §11.
