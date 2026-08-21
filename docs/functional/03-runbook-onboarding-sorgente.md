# 03 — Runbook: onboarding di una sorgente

> Procedura che il Dev Agent segue per aggiungere un source system o un dataset al layer bronze.
> È vincolante: le deviazioni sono rilievi in code review.

---

## 1. Quando si applica

| Caso | Si applica |
|---|---|
| Nuovo source system (prima volta in assoluto) | Sì — percorso completo |
| Nuovo dataset in un source system esistente | Sì — solo passi 3, 5, 6, 7 |
| Nuova **tipologia** di connettore (REST, File, DWH…) | No — è un intervento architetturale, richiede ADR e decisione umana |

> Il terzo caso è il più importante da riconoscere. Se il ticket chiede una tipologia di
> sorgente per cui non esiste un connettore, l'agente **non** improvvisa un connettore nuovo:
> solleva il punto sul ticket ed escala.

---

## 2. Precondizioni

- Il ticket contiene tutti i campi obbligatori previsti da [02 — Come scrivere un ticket](02-come-scrivere-un-ticket.md)
- `CONTEXT.md` e questo runbook sono stati letti nella sessione corrente
- Esiste un connettore per la tipologia di sorgente richiesta
- Le eventuali credenziali sono già disponibili nel secret store, per riferimento

---

## 3. Procedura

### Passo 1 — Verifica di fattibilità

Prima di scrivere qualsiasi cosa, l'agente verifica che:

- la tipologia di connettore richiesta esista;
- l'onboarding sia realizzabile **per sola configurazione**.

> Se serve codice nuovo, **fermati**: significa che manca un'astrazione nel framework. Segnala
> il punto sul ticket ed escala. Non aggirare l'astrazione mancante con codice ad hoc:
> è così che un framework metadata-driven muore, un'eccezione alla volta.

### Passo 2 — Isolamento

Crea branch e feature workspace secondo le convenzioni di `CONTEXT.md`, con nome derivato
dall'ID del work item, e aggiungi l'owner come amministratore.

### Passo 3 — Configurazione dichiarativa

Aggiungi o estendi il file `configuration/<source_system>.json`.

Per ogni dataset devono essere dichiarati almeno:

| Elemento | Note |
|---|---|
| Nome del dataset | `snake_case`, plurale |
| Tipologia di connettore | Deve corrispondere a un connettore esistente |
| Riferimento alla sorgente | Endpoint REST o path dei file |
| Chiavi primarie | Come da ticket. Guidano il controllo di unicità e il merge |
| Modalità di carico | `full` o `incremental` |
| Watermark column | Obbligatoria se `incremental` |

**Nessun segreto nel file di configurazione**: solo riferimenti al secret store.

### Passo 4 — Orchestrazione

Predisponi la pipeline di ingestion per il source system seguendo il pattern esistente, con
naming e collocazione in cartella secondo `CONTEXT.md`.

Elementi che **devono** essere presenti perché il pattern sia rispettato:

- lettura della configurazione dal metadata store;
- iterazione sui dataset dichiarati;
- invocazione del notebook di carico condiviso, **parametrizzato e mai duplicato**;
- controllo di concorrenza impostato a esecuzione singola;
- conteggio di controllo alla sorgente per la riconciliazione.

> Il notebook di carico è **condiviso da tutti i source system**. Se ti trovi a doverlo
> duplicare o a inserirvi un ramo condizionale per la sorgente specifica, è un rilievo
> architetturale: segnalalo.

### Passo 5 — Esecuzione reale

Esegui il carico completo nel feature workspace. **Non si apre una PR su un carico non eseguito.**

### Passo 6 — Verifica

| Controllo | Criterio di superamento |
|---|---|
| Unicità delle chiavi primarie | Nessun duplicato sulle colonne dichiarate |
| Riconciliazione dei conteggi | Conteggio sorgente e conteggio destinazione coerenti |
| Esito della scrittura | Nessun errore, tabella presente e popolata |
| Audit | Una riga di audit per dataset e per esecuzione |

**Se il controllo di unicità fallisce**: nella grande maggioranza dei casi la causa è una
dichiarazione errata delle chiavi primarie nel ticket, non un difetto del framework.
Non aggirare il controllo, non rimuovere i duplicati arbitrariamente: **fermati, documenta
l'evidenza sul ticket e chiedi conferma**.

### Passo 7 — Documentazione

Aggiorna, nella stessa PR:

- la pagina del source system (descrizione, connettore, modalità di carico, note operative);
- l'inventario dei dataset, con chiavi primarie e watermark;
- `CHANGELOG.md` sotto `[Unreleased]`.

### Passo 8 — Pull request

Apri la PR allegando l'**evidenza dell'esecuzione**: esito dei controlli, conteggi,
identificativo del run. Assegna il Review Agent.

---

## 4. Caso specifico — connettore CRM / Dataverse

Il primo tracer usa l'entità CRM `account` dell'ambiente demo/sintetico collegato alla Fabric
Connection `b838644d-afd9-4ec3-973d-e36ed85ad167`.

| Campo | Valore del tracer |
|---|---|
| Source system | `crm_demo` |
| Entità / dataset | `accounts` |
| Chiave primaria | `accountid` |
| Modalità | Incremental |
| Watermark | `modifiedon` |
| Credenziale | Riferimento alla Fabric Connection esistente, mai valore di token/secret |

Prima dell'esecuzione, conferma che l'ambiente contiene solo dati demo/sintetici. Il rail e il
modello ricevono solo evidenze aggregate o mascherate.

---

## 5. Caso specifico — connettore REST (Open-Meteo)

Open-Meteo richiede **latitudine e longitudine come parametri di chiamata**: non esiste un
endpoint "tutte le città".

Ne discende una decisione di design da non subire inconsapevolmente:

| Opzione | Pro | Contro |
|---|---|---|
| **A — Lista di città in configurazione** (adottata per l'MVP) | Semplice, deterministica, poche chiamate | La lista va mantenuta a mano |
| B — Estrazione guidata dalla tabella città | Elegante, scala con la dimensione | Introduce dipendenza tra due connettori e centinaia di chiamate per run |

**Decisione MVP**: opzione A, con un sottoinsieme ristretto di città dichiarato in
configurazione. Il dataset completo delle città resta la **dimensione** usata per la join nel
layer silver, non il driver dell'estrazione.

> L'opzione B è un'evoluzione interessante (*parameter-driven extraction*), ma va introdotta
> come decisione architetturale esplicita con ADR, non come effetto collaterale di un ticket
> di onboarding.

---

## 6. Caso specifico — connettore File

- I file di origine risiedono in un percorso convenzionale del lakehouse bronze.
- Il connettore deve gestire lo schema in modo esplicito: **niente inferenza silenziosa**, che
  in produzione è una delle cause più frequenti di rotture intermittenti.
- Il nome file e il percorso non devono contenere informazioni semantiche indispensabili al
  carico: se l'informazione serve, va dichiarata in configurazione.

---

## 7. Criteri di completamento

Il runbook è completato quando **tutti** i punti sono veri:

- [ ] La configurazione dichiarativa è presente e conforme alle convenzioni
- [ ] Nessun codice nuovo è stato introdotto per gestire la sorgente specifica
- [ ] Il carico è stato eseguito realmente nel feature workspace
- [ ] Controlli di unicità e riconciliazione dei conteggi sono verdi
- [ ] Documentazione e inventario sono aggiornati nella stessa PR
- [ ] `CHANGELOG.md` contiene la voce
- [ ] L'evidenza dell'esecuzione è allegata alla PR
- [ ] Nessun segreto compare in configurazione, pipeline o notebook
