# 03 — Rail script

> Contratti degli script deterministici che il Dev Agent invoca al posto di ragionare
> sull'API plumbing.

Decisione applicata: [ADR-0007](../adr/ADR-0007-pipeline-cicd-come-rail.md).

---

## 1. Cosa qualifica un rail

Un'operazione diventa un rail quando soddisfa **tutte** queste condizioni:

| # | Condizione |
|---|---|
| 1 | È identica a ogni esecuzione, a meno dei parametri |
| 2 | Non richiede giudizio: non ci sono decisioni da prendere |
| 3 | Il suo esito è verificabile in modo binario |
| 4 | Sbagliarla è costoso o difficile da diagnosticare |

Se un'operazione richiede giudizio, **non** è un rail: incapsularla in uno script significherebbe
nascondere una decisione dentro codice non tracciato.

### Regole comuni a tutti i rail

| Regola | Motivo |
|---|---|
| **Idempotenza** | Una sessione interrotta va rilanciata senza effetti collaterali |
| **Esito binario esplicito** | L'agente deve poter distinguere successo e fallimento senza interpretare testo libero |
| **Output strutturato** | Ciò che l'agente deve allegare alla PR va restituito in forma leggibile da programma |
| **Nessun segreto in output** | I rail girano con l'identità applicativa e non devono mai stampare credenziali |
| **Fallimento esplicito** | Un rail non "prova un'alternativa": fallisce e riporta il motivo |

> L'ultima regola è la più importante. Un rail che tenta strade alternative reintroduce
> esattamente l'imprevedibilità che i rail esistono per eliminare.

---

## 2. Rail previsti

### 4 rail agentici per l'MVP

| Rail | Responsabilità |
|---|---|
| **Branch out** | Predispone l'isolamento: branch, feature workspace, collegamento a Git |
| **Run load** | Invoca pipeline agentica di carico, restituisce artefatto `rail-result.json` |
| **Sync workspace** | Materializza nel workspace le modifiche presenti sul branch |
| **Diagnose data** | Esegue controlli su sorgente, Bronze o Silver e restituisce evidenze aggregate/mascherate |

> Ogni rail è implementato come una pipeline CI/CD. Il contatto fra agente e pipeline è il
> contratto (input/output). La pipeline è deterministica e ancorata a `main`.

---

## 3. Contratto — Branch out

**Scopo**: creare in un'unica operazione tutto ciò che serve a isolare il lavoro su un work item.

| Aspetto | Contratto |
|---|---|
| **Input** | Identificativo del work item, descrizione breve per lo slug |
| **Passi** | 1. Crea il branch dal ramo principale, con nome derivato dall'ID<br>2. Crea il feature workspace, con nome derivato dall'ID<br>3. Assegna il workspace alla capacity<br>4. Aggiunge l'owner come amministratore<br>5. Collega il workspace al branch<br>6. Sincronizza il contenuto dal branch al workspace |
| **Output** | Nome del branch, nome e identificativo del workspace, esito della sincronizzazione |
| **Successo** | Workspace esistente, collegato al branch, con gli item attesi presenti |
| **Idempotenza** | Se branch e workspace esistono già per quell'ID, si riconnette invece di duplicare |
| **Fallimento tipico** | Capacity non disponibile, permessi insufficienti, nome già in uso con collegamento diverso |

> **Il passo 4 non è cortesia**: se qualcosa va storto, l'owner deve poter guardare dentro il
> workspace senza chiedere permessi a nessuno. È il presupposto pratico della supervisione umana.

### Implementazione iniziale

Il workflow `.github/workflows/pipe_agent_branch_out.yml` e il runner `scripts/branch_out.py` implementano
il primo rail reale. Il workflow viene avviato dalla definizione su `main`, usa esclusivamente
l'environment GitHub `dev` e accetta soltanto `work_item_id` e `slug`; non accetta un ambiente di
destinazione. L'owner, capacity e connessione Git sono configurazione dell'environment `dev`, non
input del chiamante e non segreti nel repository.

L'artefatto è `rail-result.json` conforme a
[`schemas/rail-result-v1.1.json`](../../schemas/rail-result-v1.1.json). La v1.1 specializza il
contratto per `branch_out`: `workspace_id` può essere `null` in un fallimento prima della
creazione e `branch_out` restituisce work item, nomi deterministici e stati di branch, workspace,
connessione Git e sincronizzazione. `datasets` è intenzionalmente vuoto.
In caso di fallimento, `failure_stage` identifica in modo sicuro il passo (`configuration`,
`branch`, `workspace`, `owner`, `git_connection`, `folders`, `sync` o `unknown`) senza
serializzare risposte API, token o credenziali. Un endpoint Git che risponde senza
`gitProviderDetails` viene trattato come workspace ancora non collegato e il rail esegue la
connessione, non lo considera un collegamento incompatibile.
`failure_code` espone soltanto la classe tecnica sicura della richiesta rifiutata (`forbidden`,
`unauthorized`, `bad_request`, `api_request_failed` o `unexpected`), mai il messaggio dell'API.

Per GitHub l'idempotenza confronta `ownerName` della connessione esistente; per Azure DevOps usa
il fallback `organizationName`. Questo evita di trattare un feature workspace GitHub già collegato
alla branch richiesta come incompatibile.

L'idempotenza è conservativa: al rilancio il rail riusa il branch e il workspace con lo stesso
nome, completa un'assegnazione capacity mancante, non riassegna un owner già `Admin` e verifica
che una connessione Git esistente punti allo stesso repository e branch. Una capacity diversa,
un'associazione Git diversa, un nome duplicato o configurazione DEV mancante terminano con
`technical_failure`; il rail non adotta risorse ambigue né genera suffissi.

Precondizione operativa: la `ConfiguredConnection` Git deve essere creata e gestita fuori dal
workflow. Per il connettore GitHub selezionato in Fabric, la Account key e' un fine-grained PAT
GitHub limitato al repository, con `Metadata: Read` e `Contents: Read and write`; il valore viene
inserito direttamente in Fabric, mai nel repository, nelle GitHub variables o nei log. L'OIDC del
rail identifica un service principal di deploy, distinto dal Dev Agent: il primo ha i privilegi
minimi per il solo perimetro feature/capacity, il secondo puo' accodare il workflow ma non
impersonarlo. Le cartelle richieste sono create con la Folders API; il task flow non viene creato
nei feature workspace, secondo ADR-0003.

La connection deve avere un role assignment che consenta al service principal di deploy di
usarla: per `GitHubRepo`, aggiungere `fabric-agentic-deploy` (Object ID
`db9d4adb-db6a-4238-8e75-c69d21b1b37e`) con ruolo `User`. Il PAT resta custodito nella
connection e non viene esposto al service principal o al workflow.

Il body `Git Connect` è specifico del provider: per GitHub usa `ownerName`,
`gitProviderType: GitHub`, `repositoryName`, `branchName` e `directoryName` relativo (vuoto per
la radice). I campi `organizationName` e `projectName` appartengono invece al provider Azure
DevOps e non devono comparire nel rail GitHub.

### Verifica sul campo

Il run GitHub Actions `32487821272` del 2026-08-21 ha validato il rail sul work item `6`:
ha riusato `feature/wi-6-smoke-branch-out` e `ws_agentic_feature_wi6`
(`c3465ab0-210b-4b31-86fd-03d9611fc037`), ha confermato la capacity, collegato Git e
sincronizzato il workspace. L'artefatto `rail-result.json` v1.1 riporta `outcome: success` e
stati `existing`, `existing`, `connected`, `synchronized`.

Il tentativo sul work item `158` del 2026-09-02 (run GitHub Actions `33623226689`) ha creato il
branch `feature/wi-158-crm-accounts-bronze-audit-watermark`, ma il provisioning del workspace
`ws_agentic_feature_wi158` ha restituito `technical_failure`, con `failure_stage: workspace` e
`failure_code: bad_request`. L'OIDC ha completato correttamente; nessun preflight o load CRM è
stato avviato. Il rail non serializza il body API: verificare fuori dal workflow nome workspace,
capacity e autorizzazioni del service principal prima del rilancio.

Dopo la riabilitazione della capacity, il retry `33623676980` ha raggiunto l'inizializzazione Git
ma ha terminato con `failure_stage: sync`, `failure_code: bad_request`, prima dell'esecuzione CRM.
La causa verificata era la POST `initializeConnection` priva della policy obbligatoria;
`branch_out` usa ora `initializationStrategy: PreferRemote` per il workspace feature appena
creato. Il sync dedicato `33624037289`, eseguito prima della correzione, non ha potuto verificare
lo stato del workspace e ha restituito `failure_stage: unknown`, `failure_code: bad_request`.

---

## 4. Contratto — Run load

**Scopo**: eseguire il carico via pipeline CI/CD e restituire l'evidenza strutturata per il Review Agent.

| Aspetto | Contratto |
|---|---|
| **Input** | Workspace, source system, elenco dataset |
| **Innesco** | Pipeline CI/CD agentica (ancorata a `main`, branch come parametro) |
| **Output** | Artefatto `rail-result.json` a schema versionato |
| **Successo** | Esito = `success` e controlli unicità superati e conteggi riconciliati |
| **Idempotenza** | Rilanciabile: carico ripetibile sullo stesso workspace |
| **Fallimento tipico** | Configurazione invalida, controllo unicità fallito, sorgente irraggiungibile |

### 4b. Artefatto `rail-result.json` — schema versionato

Ogni pipeline agentica produce questo artefatto: è il **canale primario** con cui l'agente riceve
l'esito. Mai dai log della pipeline, sempre da questo artefatto. La v1.0 resta il contratto
generico; per `run_load` lo schema normativo è
[`schemas/rail-result-v1.3.json`](../../schemas/rail-result-v1.3.json), che rinomina i due
conteggi in `loaded_count` e `total_destination_count`.

**La versione dichiarata vale anche sul percorso di fallimento.** `success`,
`technical_failure` e `quality_failure` sono lo stesso contratto: un artefatto di fallimento che
non valida è indistinguibile, per il Review Agent, da un artefatto assente. Vale anche per il
fallback che il workflow scrive quando il processo muore prima di produrne uno. Il guard è
`scripts/validate_rail_result_schema.py`, eseguito dalla CI su ogni versione pubblicata.

```json
{
  "schema_version": "1.3",
  "rail": "run_load",
  "run_id": "...",
  "workspace_id": "...",
  "outcome": "success|technical_failure|quality_failure",
  "datasets": [
    {
      "name": "dataset_name",
      "status": "loaded|skipped|failed",
      "loaded_count": 1000,
      "total_destination_count": 1000,
      "reconciliation": "passed|failed|not_applicable",
      "supports_source_count": true,
      "pk_check": "passed|failed|not_applicable"
    }
  ],
  "watermark": "2026-08-21T17:39:25Z",
  "messages": [],
  "diagnostics": {
    "schema_drift": false,
    "null_count": 0,
    "masked_key_samples": []
  },
  "timestamp": "2026-08-20T10:30:00Z"
}
```

**Campi critici:**
- **`outcome`**: categorizzazione semantica, non codice di uscita. `success` se tutto verde, `technical_failure` se errore esecuzione, `quality_failure` se controlli falliscono.
- **`supports_source_count`**: booleano. Se `false`, il Review Agent non deve forzare la riconciliazione dei conteggi per questo dataset.
- **`loaded_count`**: numero di record caricati o processati nel batch corrente.
- **`total_destination_count`**: numero totale di record presenti nella destinazione dopo il merge.
  Non rappresenta il delta del batch e può quindi essere maggiore di `loaded_count`.
- **`watermark`**: watermark confermato dopo il run, o `null`. Vale solo se Bronze e audit sono
  riusciti: è la trasposizione nell'artefatto della decisione di [ADR-0012](../adr/ADR-0012-watermark-crm-account.md).
- **`diagnostics`**: opzionale per i carichi, obbligatorio per `diagnose_data`; può contenere solo
  statistiche, indicatori e identificativi mascherati conformi alla policy dati dell'istanza.

### Implementazione e stato di verifica

`run_load` ha due runner: `scripts/run_load.py` per il carico locale deterministico e
`scripts/fabric_crm_load.py`, invocato da `.github/workflows/pipe_agent_crm_run_load.yml`, per
l'esecuzione reale nel feature workspace.

Lo stato anello per anello, le discrepanze corrette e quelle ancora aperte sono in
[`14-inventario-catena-crm-accounts.md`](14-inventario-catena-crm-accounts.md). Due limiti noti
riguardano direttamente questo contratto: `reconciliation` è oggi scritta come letterale invece
che calcolata dai conteggi, e l'evidenza Fabric è letta da un percorso fisso non legato al run
appena sottomesso.

### Nota critica sulla condizione di successo

Il rail **non** restituisce `success` se la pipeline termina senza errori ma i controlli di
qualità falliscono.

> Differenza fra "il codice ha girato" e "il risultato è corretto". Un rail che restituisse
> `success` sulla sola terminazione porterebbe l'agente ad aprire una PR su un carico sbagliato.

Per l'esecuzione locale dei soli rail CRM, il comando Azure CLI è risolto come `az.cmd` su Windows
e come `az` sugli altri sistemi. La differenza è necessaria perché `subprocess` di Python non
risolve automaticamente l'entry point `.cmd` di Azure CLI su Windows; non modifica la
configurazione dell'ambiente o i comandi eseguiti dal workflow Linux.

Il preflight CRM usa il medesimo flusso client-credentials del load: il secret rimane in Key Vault
e viene letto tramite `notebookutils.credentials.getSecret`. L'API `notebookutils.connections`
non è parte delle API NotebookUtils supportate dal runtime; il preflight non la utilizza. La query
usa `accounts/$count` e produce solo il conteggio aggregato, mai record o credenziali. Il
precedente `$top=0` è stato rifiutato dal run reale con HTTP 400.

L'esito distingue tre casi per una reazione diversa dell'agente:

| Esito | Significato | Reazione |
|---|---|---|
| **`success`** | Tutto verde | Procedi con documentazione e PR |
| **`technical_failure`** | Errore di esecuzione | Diagnostica e correggi (blocco B1) |
| **`quality_failure`** | Esecuzione riuscita, controlli falliti | **Escala** (blocco B2) — specifica probabilmente errata |

---

## 5. Contratto — Diagnose data

**Scopo**: analizzare un'anomalia dati senza esporre al modello righe grezze né credenziali.

| Aspetto | Contratto |
|---|---|
| **Input** | Work item, perimetro (`source`, `bronze`, `silver`), dataset, tipo controllo e filtri consentiti |
| **Innesco** | Pipeline CI/CD `pipe_agent_diagnose_data`, ancorata a `main` |
| **Esecuzione** | La pipeline usa la `ExecutionCredential` del cliente, custodita nel secret store e mai disponibile all'agente |
| **Output** | `rail-result.json` con statistiche, riconciliazioni, watermark, drift schema, null/duplicati e chiavi mascherate |
| **Successo** | Evidenze prodotte entro i limiti della policy dati; non implica che l'anomalia sia risolta |
| **Escalation** | Se per decidere servono righe grezze, PII o un segreto: blocco B4 e intervento umano autorizzato |

> Il rail esegue la query; l'agente interpreta l'evidenza e decide il prossimo passo. Questa
> separazione consente assistenza quotidiana senza trasformare il modello in un utente dati.

---

## 6. Contratto — Sync workspace

**Scopo**: portare nel workspace lo stato del branch dopo una modifica.

| Aspetto | Contratto |
|---|---|
| **Input** | Workspace, branch |
| **Passi** | 1. Verifica il collegamento Git<br>2. Applica gli aggiornamenti dal branch<br>3. Attende il completamento<br>4. Verifica che gli item risultino allineati |
| **Output** | Elenco degli item aggiornati, stato di sincronizzazione |
| **Successo** | Nessun item in stato divergente |
| **Idempotenza** | Sì: se non ci sono differenze, non fa nulla |
| **Fallimento tipico** | Conflitti, collegamento assente, item in stato non sincronizzabile |

### Implementazione iniziale

Il workflow `.github/workflows/pipe_agent_sync_workspace.yml` e il runner
`scripts/sync_workspace.py` implementano S1-03. Come `branch_out`, il workflow viene eseguito
da `main`, usa solo l'environment `dev` e riceve work item e slug, da cui deriva branch e
workspace. Non accetta un target environment né un workspace arbitrario.

Il rail verifica il collegamento Git verso il repository e branch deterministici, quindi legge
`Git Status`. Se non ci sono differenze restituisce `already_aligned`. Applica `Update From Git`
solo quando le differenze sono esclusivamente remote; modifiche locali e conflitti restituiscono
un `technical_failure` strutturato senza sovrascrivere il workspace. Il polling bounded attende
l'allineamento prima di restituire `synchronized`.

L'artefatto `rail-result.json` conforme a
[`schemas/rail-result-v1.2.json`](../../schemas/rail-result-v1.2.json) restituisce stato,
elenco degli item aggiornati e failure stage/code privi di log, righe dati o credenziali.

### Verifica sul campo

Il run GitHub Actions `32488530726` del 2026-08-21 ha validato il rail sul work item `6` e sul
workspace `ws_agentic_feature_wi6` (`c3465ab0-210b-4b31-86fd-03d9611fc037`). L'artefatto
`rail-result.json` v1.2 riporta `outcome: success`, `status: already_aligned` e nessun item
aggiornato: il rail non ha eseguito scritture quando il workspace era già allineato.

---

## 6-bis. Contratto — Review vote publish

**Scopo**: trasformare l'esito A1-F4 prodotto dalla sessione di review in **una sola** review
submission su GitHub, con l'identità applicativa del Review Agent.

| Aspetto | Contratto |
|---|---|
| **Input** | Percorso dell'esito strutturato, owner/repository, numero della pull request, App ID, Installation ID e percorso della private key del Review Agent |
| **Innesco** | Il runner della sessione di review, mai il modello |
| **Passi** | 1. Verifica la copia di pubblicazione<br>2. Valida l'esito A1-F4<br>3. Conia l'installation token<br>4. Legge il head sha della PR e le review esistenti<br>5. Invia una `POST /repos/{owner}/{repo}/pulls/{number}/reviews` |
| **Output** | JSON con numero PR, head sha, event, numero di rilievi e stato `published` o `already_published` |
| **Successo** | Esiste esattamente una review submission dell'identità del Review Agent per quel head sha |
| **Idempotenza** | Sulla coppia (numero PR, head sha): una seconda esecuzione sullo stesso head sha non crea una seconda review |
| **Fallimento tipico** | Esito malformato, copia non allineata a `main`, App non installata o permessi insufficienti |

L'implementazione è `scripts/review_vote_publish.py`.

**Validazione dell'esito**: ogni voce da A1 a F4 presente esattamente una volta, valore in
`PASSATO` / `RILIEVO` / `NON APPLICABILE`, motivazione obbligatoria per ogni `NON APPLICABILE` e
riga `VOTO` coerente con il numero di rilievi. La checklist è quella chiusa di
[`04-checklist-review.md`](../functional/04-checklist-review.md): il publisher non ne aggiunge voci.

**Mappatura del voto**: `VOTO: APPROVATO` produce `APPROVE`, `VOTO: NON APPROVATO` produce
`REQUEST_CHANGES`. Nessun altro event è ammesso. Un esito non valido termina con errore **prima**
di coniare qualunque token: non esistono voti parziali.

**Vincolo sulla copia di pubblicazione**: il publisher rifiuta l'esecuzione se la copia da cui gira
non è su `main`, ha modifiche non committate o non è allineata a `origin/main`. È lo stesso
principio dell'ancoraggio a `main` delle pipeline agentiche: il codice che pubblica un voto non può
essere quello che il branch in review sta modificando.

**Segreti**: il token è coniato al momento, vive solo in memoria del processo e non compare in
stdout, nel body della review o in file di stato — il publisher non ne scrive alcuno, perché
l'idempotenza si legge da GitHub. La sessione di review non conia token e non conosce il percorso
della private key; vedi [`04-identita-e-permessi.md`](04-identita-e-permessi.md) sezione 2.1.

> Non contraddice la sezione 8: il publisher non è un rail che il Review Agent può invocare per
> produrre evidenze. È il rail che **esegue** il suo voto, e gira fuori dalla sessione proprio
> perché il modello non deve poter maneggiare la credenziale con cui il voto viene firmato.

---

## 7. Evoluzione dei rail

| Situazione | Azione |
|---|---|
| L'agente riscopre ripetutamente la stessa procedura | Candidata a diventare un rail |
| Un rail richiede sempre più parametri condizionali | Segnale che sta assorbendo giudizio: va spezzato |
| Un rail fallisce in modo non diagnosticabile | Migliorare l'output prima di aggiungere logica |

> **Antipattern da evitare**: il rail che "gestisce i casi particolari". Un rail con rami
> decisionali è un agente scritto male — senza la capacità di giudizio di un agente e senza la
> prevedibilità di uno script.

---

## 8. Chi può usarli

| Attore | Accesso ai rail |
|---|---|
| Dev Agent | Sì |
| Review Agent | **No** — non deve poter produrre le evidenze che giudica |
| Owner | Sì, per diagnosi e intervento manuale |
