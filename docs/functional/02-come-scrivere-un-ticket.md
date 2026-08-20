# 02 — Come scrivere un ticket

> Il ticket è **l'unica interfaccia** tra te e il sistema. La qualità del risultato dipende
> quasi interamente dalla qualità di questo documento.

---

## 1. Il principio

Un agente non chiede chiarimenti "a voce" e non intuisce il contesto implicito che un collega
umano darebbe per scontato. Ma **si ferma e chiede** se la specifica è ambigua — il che è
corretto, ma costa un giro completo di sessione e un'attesa.

> Il tempo che risparmi scrivendo un ticket approssimativo lo ripaghi con gli interessi nel
> ciclo di chiarimento.

Un ticket ben scritto non è un ticket lungo. È un ticket **che non lascia decisioni implicite**.

---

## 2. Requisiti minimi di attivazione

Perché il sistema prenda in carico un ticket devono valere **tutte** queste condizioni:

| # | Condizione |
|---|---|
| 1 | Il ticket è nello stato *To Do* |
| 2 | Il ticket ha il tag riservato al Dev Agent |
| 3 | Il ticket ha un titolo che descrive il risultato atteso, non l'attività |
| 4 | La descrizione contiene le sezioni obbligatorie previste dal tipo di ticket |

Se manca il tag, il ticket resta invisibile al sistema: è il meccanismo con cui decidi cosa
delegare e cosa no.

---

## 3. Struttura della descrizione

### 3.1 Sezioni obbligatorie (tutti i tipi)

| Sezione | Contenuto |
|---|---|
| **Obiettivo** | Cosa deve essere vero alla fine, in una frase. Il risultato, non i passi |
| **Contesto** | Perché serve, e quali artefatti esistenti sono coinvolti |
| **Criteri di accettazione** | Elenco verificabile. Se non è verificabile, non è un criterio |
| **Fuori scope** | Ciò che l'agente **non** deve toccare. Sezione più utile di quanto sembri |

### 3.2 Sezioni aggiuntive per tipo di ticket

**Onboarding di una sorgente o di un dataset**

| Campo | Obbligatorio | Note |
|---|---|---|
| Source system | Sì | Nome del sistema sorgente, esistente o nuovo |
| Tipologia di connettore | Sì | REST, File, … |
| Dataset da onboardare | Sì | Uno o più, con nome |
| Chiavi primarie | Sì | Elenco di colonne per dataset. **Se sbagliate, il carico si ferma sul controllo di unicità** |
| Modalità di carico | Sì | Full o incremental |
| Watermark column | Se incrementale | Colonna che guida l'incrementalità |
| Endpoint / percorso | Sì | Indirizzo REST o path dei file |
| Credenziali | Se necessarie | **Per riferimento, mai in chiaro** |

**Change request su artefatto esistente**

| Campo | Obbligatorio |
|---|---|
| Artefatto impattato (nome esatto) | Sì |
| Comportamento attuale | Sì |
| Comportamento atteso | Sì |
| Impatti a valle noti (semantic model, report) | Sì |

**Bug fix**

| Campo | Obbligatorio |
|---|---|
| Comportamento osservato | Sì |
| Comportamento atteso | Sì |
| Come riprodurlo | Sì |
| Evidenza (messaggio d'errore, run id, screenshot) | Sì |
| Regression test atteso | Sì |

**Analisi dati / anomalia operativa**

| Campo | Obbligatorio | Note |
|---|---|---|
| Perimetro | Sì | `source`, `bronze` o `silver`; un dataset per ticket salvo riconciliazione dichiarata |
| Anomalia osservata | Sì | Conteggio, run ID, watermark o altro indicatore verificabile; mai righe o PII nel ticket |
| Domanda da risolvere | Sì | Una domanda precisa, ad esempio “perché Bronze e sorgente divergono?” |
| Controlli autorizzati | Sì | Null, duplicati, schema drift, watermark, conteggi, riconciliazione, distribuzioni |
| Limiti dati | Sì | Conferma che sono ammessi solo output aggregati/mascherati |
| Fuori scope | Sì | Ad esempio: nessuna modifica al carico finché la causa non è confermata |

> Questo tipo di ticket invoca il rail `diagnose_data`. Il Dev Agent interpreta l'evidenza
> prodotta dalla pipeline; non richiede né riceve credenziali, righe grezze o estratti PII.

**Refactoring**

| Campo | Obbligatorio |
|---|---|
| Cosa va riorganizzato e perché | Sì |
| Comportamento che deve restare **identico** | Sì |
| Come si verifica l'invarianza | Sì |

---

## 4. Esempio — ticket ben scritto

> **Titolo**: Onboarding del dataset `daily_weather` da Open-Meteo nel layer bronze
>
> **Obiettivo**
> Il dataset meteo giornaliero di Open-Meteo è disponibile come tabella bronze, caricabile in
> modalità incrementale.
>
> **Contesto**
> Primo dataset del source system `open_meteo`, connettore REST. Segui il runbook
> *Onboarding di una sorgente*. Il framework di ingestion e il notebook di carico esistono già
> e non vanno modificati.
>
> **Specifiche del dataset**
> - Source system: `open_meteo` (nuovo)
> - Connettore: REST
> - Dataset: `daily_weather`
> - Chiavi primarie: `city_id`, `date`
> - Modalità di carico: incrementale
> - Watermark column: `date`
> - Elenco città da estrarre: come da configurazione (vedi runbook)
>
> **Criteri di accettazione**
> - La tabella bronze esiste ed è popolata
> - Il controllo di unicità sulle chiavi primarie è verde
> - I conteggi di audit sorgente e destinazione coincidono
> - La documentazione della sorgente e l'inventario dei dataset sono aggiornati
> - La configurazione rispetta le convenzioni di `CONTEXT.md`
>
> **Fuori scope**
> - Layer silver, semantic model, report
> - Modifiche al notebook di carico condiviso

---

## 5. Errori ricorrenti

| Errore | Conseguenza | Rimedio |
|---|---|---|
| Chiavi primarie sbagliate | Il carico si ferma sul controllo di unicità, un giro perso | Verificale sulla sorgente **prima** di scrivere il ticket |
| Criteri di accettazione non verificabili ("deve funzionare bene") | L'agente decide da solo cosa significa | Scrivi criteri osservabili |
| Nessuna sezione "fuori scope" | L'agente allarga il perimetro con iniziative non richieste | Dichiara esplicitamente cosa non toccare |
| Più obiettivi eterogenei nello stesso ticket | PR grande, review difficile, rollback complicato | Un ticket, un risultato |
| Riferimenti impliciti ("come l'altra volta") | L'agente non ha memoria tra sessioni | Rendi esplicito il riferimento, con nome dell'artefatto |
| Credenziali incollate nella descrizione | Segreto esposto nel tracker, non revocabile a posteriori | Riferimento al secret store, mai il valore |

---

## 6. Regola d'oro

> **Se due persone del team leggendo il ticket implementerebbero due cose diverse, l'agente ne
> implementerà una terza.**

Prima di salvare, rileggi la descrizione e chiediti dove restano decisioni non prese. Quelle
sono esattamente i punti in cui il sistema ti chiederà un chiarimento — o, peggio, non te lo
chiederà.
