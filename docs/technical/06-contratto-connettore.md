# 06 — Contratto di connettore

> Il cuore dell'agnosticismo rispetto alla sorgente. Se questo contratto è giusto, aggiungere
> una sorgente è configurazione. Se è sbagliato, ogni sorgente nuova è un progetto.

---

## 1. Il problema che risolve

Un framework metadata-driven costruito attorno a **una sola** tipologia di sorgente sembra
generico ma non lo è: la tipologia è cablata nell'orchestrazione, e si scopre solo alla seconda
sorgente.

La separazione è netta:

| Livello | Cosa sa | Cosa non sa |
|---|---|---|
| **Orchestrazione** | Quali dataset caricare, con quali chiavi, in quale modalità | **Nulla** su come si raggiunge la sorgente |
| **Connettore** | Come parlare con una specifica tipologia di sorgente | Nulla sul layer bronze, sui controlli, sull'audit |
| **Carico** | Come scrivere in bronze, controllare le chiavi, produrre l'audit | Nulla sulla provenienza del dato |

> **Criterio di verifica, secco**: cerca il nome della tipologia di sorgente nel codice di
> orchestrazione. Se compare, il contratto è già rotto.

---

## 2. Struttura della configurazione

Un file per source system: `configuration/<source_system>.json`.

### Livello source system

| Campo | Obbligatorio | Descrizione |
|---|---|---|
| Nome del source system | Sì | `snake_case`, coincide col nome del file |
| Tipologia di connettore | Sì | Deve corrispondere a un connettore registrato |
| Parametri di connessione | Dipende | Specifici della tipologia. **Solo riferimenti al secret store** |
| Descrizione | Sì | Alimenta la documentazione generata |

### Livello dataset

| Campo | Obbligatorio | Descrizione |
|---|---|---|
| Nome del dataset | Sì | `snake_case`, plurale |
| Riferimento alla sorgente | Sì | Endpoint, path, tabella — la forma dipende dal connettore |
| Chiavi primarie | Sì | Elenco di colonne. Guidano il controllo di unicità e il merge |
| Modalità di carico | Sì | `full` o `incremental` |
| Watermark column | Se incrementale | Colonna che guida l'incrementalità |
| Parametri specifici del connettore | Dipende | Blocco isolato, **non interpretato dall'orchestrazione** |

### Il punto chiave

I parametri specifici del connettore vivono in un **blocco isolato**, che l'orchestrazione
trasporta senza leggere.

> È il confine che tiene in piedi l'astrazione. Nel momento in cui l'orchestrazione comincia a
> guardare dentro quel blocco — anche solo per un caso particolare — la separazione è persa, e
> lo scoprirai solo alla sorgente successiva.

---

## 3. Interfaccia del connettore

Ogni connettore espone le stesse operazioni, indipendentemente dalla tipologia:

| Operazione | Responsabilità |
|---|---|
| **Validazione** | Verifica che la configurazione del dataset sia completa e coerente per questa tipologia |
| **Estrazione** | Recupera i dati e li deposita nell'area di staging convenzionale |
| **Conteggio alla sorgente** | Restituisce il numero di record attesi, per la riconciliazione |
| **Descrizione dello schema** | Dichiara le colonne prodotte, in modo esplicito |
| **Diagnostica** | Esegue controlli consentiti su sorgente e restituisce solo evidenze aggregate o mascherate |

### Registry e capacità dichiarate

L'implementazione di questo contratto vive in `fabric_agentic/connectors.py`, che è l'**unico**
elenco dei connettori ammessi: `instance_profile` lo deriva da lì invece di ridichiararlo.

Ogni connettore dichiara le proprie capacità, e il profilo viene rifiutato in validazione se ne
chiede una assente:

| Campo | Significato |
|---|---|
| `supports_incremental` | La sorgente espone un marcatore di modifica utilizzabile come watermark |
| `supports_source_count` | La sorgente sa dire quanti record ci si aspetta, per la riconciliazione |
| `connection_fields` | Campi di connessione obbligatori per questa tipologia |

`plan_request(connector, connection, DatasetRequest, watermark)` risolve la lettura di un dataset
passando dal registry: è il punto che permette all'orchestrazione di non avere rami per sorgente.
`DatasetRequest` trasporta solo ciò che il profilo già conosce — nome, chiave primaria, colonne,
colonna di watermark — senza specificità di connettore. Vedi ADR-0016.

### Regole

| Regola | Motivo |
|---|---|
| Nessun connettore scrive nel layer bronze | La scrittura è responsabilità del carico condiviso, per tutti allo stesso modo |
| Nessun connettore implementa controlli di qualità | I controlli sono uniformi e vivono nel framework |
| Ogni connettore dichiara lo schema in modo esplicito | **Niente inferenza silenziosa**: è tra le cause più frequenti di rotture intermittenti in produzione |
| Il conteggio alla sorgente è obbligatorio | Senza, la riconciliazione non è possibile e l'evidenza per la PR è incompleta |
| La diagnostica non restituisce dati grezzi | Il modello deve analizzare evidenze, non ricevere indiscriminatamente righe della sorgente |

---

## 4. Connettore REST — progettazione, non registrato

> **Questa tipologia non è nel registry.** `rest` non è un valore ammesso per `connector` in un
> profilo di istanza: `get_connector` lo rifiuta. La sezione resta come materiale di progettazione
> per una fase successiva, non come contratto disponibile.

| Aspetto | Trattamento |
|---|---|
| Endpoint | Dichiarato in configurazione |
| Autenticazione | Per riferimento al secret store. Open-Meteo non ne richiede |
| Paginazione | Gestita dal connettore, dichiarata a metadato |
| Incrementalità | Il watermark si traduce in parametri della chiamata |
| Parametri per riga | Se la sorgente richiede parametri (es. coordinate), l'elenco è dichiarato in configurazione |
| Conteggio | Numero di record restituiti dopo l'estrazione |

### Nota su Open-Meteo

L'API richiede latitudine e longitudine come parametri: non esiste un endpoint "tutte le città".

**Decisione MVP**: elenco ristretto di città dichiarato in configurazione. L'anagrafica città
completa resta la dimensione per la join in silver, **non** il driver dell'estrazione.

> L'alternativa (*parameter-driven extraction*, con l'elenco letto da una tabella) è elegante ma
> introduce una dipendenza tra due connettori proprio nel punto in cui vogliamo dimostrarne
> l'indipendenza — oltre a centinaia di chiamate per esecuzione. Va decisa con ADR.

---

## 5. Connettore CRM / Dataverse

| Aspetto | Trattamento |
|---|---|
| Origine | Fabric Connection `CommonDataService`, referenziata per ID in configurazione |
| Entità | Dichiarata in configurazione; primo tracer: `account` |
| Chiave primaria | `accountid` |
| Incrementalità | Watermark `modifiedon` |
| Semantica watermark | `modifiedon >= ultimo watermark confermato`; nuovo watermark solo dopo merge Bronze e audit |
| Conteggio | Numero di record estratti dall'entità dopo i filtri dichiarati |
| Dati verso il modello | Solo esiti, conteggi, nomi di colonna e identificativi mascherati |

Il primo tracer usa la connection `b838644d-afd9-4ec3-973d-e36ed85ad167` verso l'ambiente CRM
demo/sintetico. L'ID è configurazione di istanza, non un segreto; credenziali e token restano
custoditi nella Fabric Connection.

La riestrazione inclusiva è assorbita da un merge idempotente su `accountid`. Il watermark è il
massimo `modifiedon` del batch riuscito e non avanza in caso di fallimento di staging, PK check,
Bronze o audit. Vedi ADR-0012.

---

## 6. Connettore File

| Aspetto | Trattamento |
|---|---|
| Percorso | Dichiarato in configurazione |
| Formato | Dichiarato esplicitamente (CSV, Parquet) |
| Schema | **Dichiarato, non inferito** |
| Incrementalità | **Assente**: `supports_incremental = False`. Un file depositato non espone un marcatore di modifica lato sorgente, quindi è ammesso il solo carico completo. Un profilo che chiede un carico incrementale su `file` viene rifiutato in validazione (ADR-0016) |
| Conteggio | Numero di righe lette |

### Regola sui nomi dei file

Il percorso e il nome del file **non devono contenere informazioni semantiche indispensabili al
carico**. Se un'informazione serve (data di riferimento, entità, versione), va dichiarata in
configurazione.

> Le convenzioni implicite sui nomi dei file sono il debito tecnico più silenzioso che esista:
> funzionano finché qualcuno non rinomina un file, e allora il carico fallisce in un punto che
> non c'entra nulla con la causa.

---

## 7. Registrazione di un nuovo connettore

Aggiungere una **tipologia** di connettore non è un ticket di onboarding: è un intervento
architetturale.

| Passo | Nota |
|---|---|
| 1 | Decisione registrata come ADR |
| 2 | Implementazione dell'interfaccia completa |
| 3 | Registrazione in `fabric_agentic/connectors.py`: capacità dichiarate e planner associato |
| 4 | Documentazione dei parametri specifici |
| 5 | Onboarding di un dataset di prova |
| 6 | **Verifica che l'orchestrazione non sia stata toccata** |

> Il passo 6 è il vero criterio di accettazione. Se aggiungere un connettore richiede modifiche
> all'orchestrazione, il contratto va corretto prima di procedere — non dopo.

---

## 8. Come si accorge un agente che il contratto è rotto

Segnali che il Dev Agent deve riconoscere e **segnalare come rilievo architetturale**, invece di
aggirare:

| Segnale | Cosa significa |
|---|---|
| Serve codice nuovo per onboardare un dataset | Manca un'astrazione |
| Serve un ramo condizionale sulla sorgente nel carico condiviso | La separazione dei livelli è compromessa |
| Serve duplicare il notebook di carico | Stesso problema, forma più grave |
| L'orchestrazione deve leggere i parametri specifici del connettore | Il confine è stato attraversato |
| Un connettore deve scrivere direttamente in bronze | Le responsabilità sono confuse |

Vedi `../functional/05-protocollo-escalation.md`, blocco **B3 — astrazione mancante**.
