# ADR-0006 — Completamento del contratto di connettore

| Campo | Valore |
|---|---|
| Stato | **Proposto** — richiede decisione prima dello Slice 2 |
| Data | 2026-08-20 |
| Autore | Ralph (Fabric Solution Architect) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §4 |
| Decisori | Owner · @reza (Data Engineering) |

---

## Contesto

`06-contratto-connettore.md` definisce la separazione **orchestrazione / connettore / carico** ed
è la parte migliore del design tecnico: il criterio di verifica proposto («cerca il nome della
tipologia di sorgente nel codice di orchestrazione: se compare, il contratto è rotto») è un test
binario, non un'intenzione.

Il contratto è implementabile in Fabric — pipeline come orchestratore, notebook di carico condiviso
e parametrizzato, configurazione JSON — e non incontra ostacoli di piattaforma. **Ma non è
implementabile così com'è**: mancano quattro elementi che il primo agente che lo legge dovrà
inventarsi, inventandone quattro versioni diverse in quattro sessioni diverse.

Il PRD assume che il contratto venga messo alla prova allo **Slice 4**, con il secondo connettore.
Due delle quattro lacune si manifestano già allo **Slice 2**, sul primo.

## Decisione

Il contratto di connettore viene completato con quattro elementi, prima dello Slice 2.

### 1. Collocazione del codice del connettore

I connettori sono implementati come **notebook `nb_connector_<tipologia>`**, invocati dal notebook
di carico condiviso, e collocati nella cartella `Full and Incremental Load`.

Motivazione: è l'unica opzione che sia contemporaneamente versionabile via Git integration, priva
di passi di build, e priva di costi di pubblicazione nei feature workspace effimeri. La soluzione
"pulita" — un wheel Python su un **Environment** — introduce nel ciclo di ogni ticket una
pubblicazione di Environment, che è una risorsa di workspace e ha un costo e una latenza non
trascurabili, con impatto diretto su KPI-2. I file nelle *Resources* del lakehouse sono esclusi
perché fuori dal perimetro di Git.

La decisione è **rivedibile** quando i connettori saranno più di tre o quando esisterà un
ambiente di test unitario per il framework: a quel punto il wheel su Environment diventa la scelta
giusta, e questo ADR va superato.

### 2. Metadata store

Il **metadata store** — oggi invocato da `03-rail-script.md` §4 e definito da nessuna parte —
è una **tabella Delta nel lakehouse bronze** del workspace, con due responsabilità distinte:

| Contenuto | Scopo |
|---|---|
| Configurazione pubblicata | Copia della configurazione JSON validata, letta dall'orchestrazione a runtime |
| **Stato del watermark** per dataset | Guida l'incrementalità |
| Righe di **audit run** | Evidenza allegata alla PR |

**Conseguenza dichiarata esplicitamente**: in un feature workspace creato ex novo, lo stato del
watermark **non esiste**. Il primo carico incrementale in un feature workspace si comporta quindi
come un full load. Non è un difetto: è il comportamento corretto in un ambiente vuoto, e va scritto
nel runbook perché altrimenti l'agente lo scoprirà da solo e concluderà — ragionevolmente e
sbagliando — che l'incrementalità è rotta.

### 3. Contratto di output dell'estrazione

L'operazione di **Estrazione** produce un **set di record tabellare**, scritto in
`Files/raw/<source_system>/<dataset>/<run_timestamp>/` in formato **Parquet**, con lo schema
dichiarato dal connettore.

**La normalizzazione di payload non tabellari è responsabilità del connettore.** Non è pedanteria:
Open-Meteo non restituisce record ma un oggetto JSON con array paralleli (`time[]`,
`temperature_2m_max[]`, …). Se quella normalizzazione finisse nel notebook di carico condiviso, il
contratto sarebbe rotto **al primo dataset dello Slice 2**, non al secondo connettore dello Slice 4.

### 4. Semantica del conteggio alla sorgente

Il contratto dichiara obbligatorio il *conteggio alla sorgente* «per la riconciliazione», ma poi
lo definisce, per entrambi i connettori di fase 1, come «numero di record restituiti dopo
l'estrazione» (REST) e «numero di righe lette» (File). **Il controllo di riconciliazione, così,
non può fallire per la causa che ci si aspetta**: verifica soltanto che la scrittura non abbia
perso righe.

Il Review Agent registrerebbe `C3 PASSATO` su una prova che, per queste sorgenti, non può fare
altro che passare. Il sistema di verifica avrebbe un buco esattamente dove crede di avere una prova.

Si distinguono quindi **tre grandezze**, riportate separatamente nell'evidenza:

| Grandezza | Definizione |
|---|---|
| `source_count` | Conteggio ottenuto **indipendentemente** dall'estrazione, **solo** se la sorgente lo supporta |
| `extracted_count` | Record prodotti dall'estrazione nell'area di staging |
| `loaded_count` | Record scritti nel layer bronze |

La configurazione dichiara per ogni dataset un flag `supports_source_count`. Quando è `false`, il
controllo di riconciliazione sorgente↔destinazione è riportato come **`NON APPLICABILE` motivato**,
mai come `PASSATO`. Il meccanismo esiste già: `04-checklist-review.md` §1 stabilisce che un
`NON APPLICABILE` non motivato è esso stesso un rilievo.

### 5. Rilievi minori recepiti

- Il **PK check** su carico incrementale verifica l'unicità **sul delta**, non sull'intera tabella
  bronze. Va dichiarato quale garanzia si sta dando, perché sono due garanzie diverse.
- Il connettore File dichiara «incrementalità per data del file», in contraddizione con la regola
  «i nomi dei file non contengono informazioni semantiche indispensabili». Si sceglie la regola: la
  data di riferimento è **dichiarata in configurazione**, non dedotta dal nome del file.
- Alla checklist di review si aggiunge: **nessun campo nuovo di primo livello nella configurazione**
  fuori dal blocco isolato del connettore. È la forma più probabile di rottura del contratto, e il
  criterio "cerca il nome della tipologia nel codice" non la intercetta.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Wheel Python su Environment** per i connettori | Tecnicamente superiore, ma il costo di pubblicazione dell'Environment in ogni feature workspace effimero è incompatibile con il lead time obiettivo. Da riconsiderare oltre i tre connettori |
| **Metadata store esterno** (Warehouse o SQL Database dedicato) | Introdurrebbe una dipendenza cross-workspace proprio dove serve isolamento: il feature workspace deve essere autosufficiente |
| **Rendere facoltativo il conteggio alla sorgente** | Toglierebbe il controllo anche dove è possibile e utile (database, warehouse). La distinzione a tre grandezze conserva il valore dove esiste e dichiara l'assenza dove non esiste |
| **Lasciare che il carico condiviso normalizzi i payload non tabellari** | È esattamente il ramo condizionale per sorgente che il documento §7 elenca come segnale di contratto rotto |

## Conseguenze

**Positive**
- Il contratto diventa una specifica implementabile senza interpretazione.
- L'evidenza allegata alla PR diventa onesta: dichiara ciò che ha verificato e ciò che non poteva
  verificare, invece di presentare come prova un controllo tautologico.
- La rottura del contratto è resa rilevabile allo Slice 2, non allo Slice 4.

**Negative**
- La scelta del notebook come artefatto di connettore è un compromesso: paga in leggibilità e
  testabilità ciò che guadagna in semplicità operativa. È esplicitamente temporanea.
- Tre conteggi anziché uno appesantiscono il formato dell'evidenza e la checklist.
- Il metadata store nel lakehouse bronze mescola dati tecnici e dati di business nello stesso
  contenitore: accettabile in fase 1, da rivedere se il framework crescerà.

**Da fare**
- Aggiornare `06-contratto-connettore.md` con le quattro sezioni.
- Aggiornare `03-rail-script.md` §4 con la definizione del metadata store.
- Aggiornare `04-checklist-review.md`: voce C3 con `NON APPLICABILE` motivato, nuova voce D5 sui campi di configurazione.
- Aggiornare `03-runbook-onboarding-sorgente.md`: comportamento del primo carico incrementale in un feature workspace vuoto.
- Aggiornare `CONTEXT.md` §7.3 con la regola sulla normalizzazione.
