# ADR-0005 — Perimetro dei dati verso i vendor LLM: solo evidenze aggregate

| Campo | Valore |
|---|---|
| Stato | **Accettato** — decisione dell'owner 2026-08-20 |
| Data | 2026-08-20 |
| Autore | Ralph (Fabric Solution Architect) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §7 · Q-7 · rischio R-5 |
| Decisori | Owner · Direzione (per la parte contrattuale) |

---

## Contesto

Q-7 chiede, prima di qualsiasi uso su dati di cliente, «quale opzione di hosting degli agenti».
La prima versione del documento `04-identita-e-permessi.md` §6 assumeva che il Dev Agent vedesse
necessariamente i dati per accorgersi, per esempio, che una chiave primaria non è univoca. Questa
assunzione è stata superata: la pipeline può calcolare il controllo e restituire conteggi, chiavi
mascherate e altre evidenze che consentono al modello di investigare senza ricevere righe grezze.

**La domanda però è posta male.** Spostare il dispatcher dalla macchina dell'owner ad Azure non
cambia nulla rispetto al rischio che la domanda intende coprire: il prompt continua a partire
verso l'endpoint di un vendor esterno.

Le variabili indipendenti sono tre:

| # | Variabile | Cosa protegge |
|---|---|---|
| V1 | Dove gira il dispatcher/agente | Disponibilità, gestione dei segreti, superficie di rete |
| V2 | Dove risiede il modello e con quali termini contrattuali | Residenza del dato, training, retention |
| V3 | **Cosa entra nel prompt** | Tutto il resto |

V3 è l'unica interamente sotto il controllo del progetto, costa zero, e riduce l'importanza delle
altre due. Ed è l'unica che il design non ha ancora considerato.

L'esempio contenuto in `05-protocollo-escalation.md` §4 è già conforme a ciò che serve: «righe
totali 48.512, valori distinti di member_id 6.043» diagnostica il problema **senza che un solo
valore di `member_id` raggiunga il modello**. È un ottimo esempio, ed è il caso di promuoverlo da
esempio a regola.

## Decisione

**1. I rail restituiscono esclusivamente evidenze aggregate.** Il contratto di output di ogni
rail può contenere: esiti binari, conteggi, nomi di tabella e di colonna, identificativi di run,
messaggi di errore della piattaforma. **Non può contenere valori di dato** — né righe di esempio,
né valori distinti, né estratti di file.

**2. L'agente non legge direttamente i dati.** Ogni informazione sul contenuto delle tabelle
raggiunge il modello attraverso un rail, in forma aggregata. È l'estensione naturale del principio
6 del progetto: le regole di qualità vivono nel framework, l'agente ne cita l'esito.

**3. Il divieto è un criterio di review.** Si aggiunge alla sezione F della checklist:
*«nessun output di rail, commento su ticket o commento su PR contiene valori di dato»*.

**4. Roadmap di hosting** (V1), che diventa una decisione operativa e non più di sicurezza:

| Fase | Collocazione | Motivazione |
|---|---|---|
| 1 — laboratorio interno | Macchina locale dell'owner | Accettabile: dati sintetici, nessun impegno di servizio |
| 2 — uso su cliente | Azure Container Apps job o VM nel tenant AGIC, con **user-assigned managed identity** | Le API Fabric e Azure DevOps supportano entrambe le managed identity. Beneficio decisivo: **spariscono i client secret** — nessun segreto nella Connection Git, nessuna cache token su disco |
| 3 — vincolo di perimetro del cliente | Esecuzione nella rete del cliente | Variante commerciale, non architettura di default: contraddice V-9 |

**5. Resta aperta, e non è una decisione architetturale**: la verifica dei termini contrattuali di
ciascun vendor (no-training, retention, residenza). Va chiusa prima del primo cliente, non prima
dello Slice 0.

**6. Il rail `diagnose_data` è il canale standard per l'analisi quotidiana.** Interroga sorgente,
Bronze o Silver usando la `ExecutionCredential` del cliente e produce solo evidenze consentite.
Il modello formula l'ipotesi e propone la correzione; la pipeline legge i dati. Vedi ADR-0007 e
ADR-0008.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Spostare gli agenti in cloud e considerare il problema risolto** | È la risposta che Q-7 suggerisce, ed è quella sbagliata: non tocca V3, che è dove il dato transita davvero |
| **Vietare del tutto agli agenti l'accesso a Fabric** | Renderebbe impossibile RF-21 («nessuna PR su codice non eseguito»), che è il cuore del progetto |
| **Anonimizzare o mascherare i dati prima dell'esecuzione** | Costoso, fragile e inutile: se le evidenze sono aggregate, non c'è nulla da mascherare |
| **Usare un solo vendor, ospitato nel tenant Azure, per entrambi gli agenti** | Violerebbe RF-60 («chi scrive non rivede»), che è un controllo di qualità sostanziale. Con la regola sulle evidenze aggregate, la tensione tra "vendor diverso" e "dato nel perimetro" si scioglie da sola |

## Conseguenze

**Positive**
- Il perimetro dei dati verso i vendor si riduce a metadati di business: nomi di tabelle e colonne,
  testo dei ticket, codice, conteggi. Cambia la natura della valutazione di rischio per un cliente.
- La tensione tra RF-60 (vendor diversi) e l'eventuale vincolo di residenza del dato viene disinnescata.
- Il passaggio a managed identity elimina la classe di rischio «segreto su disco», che oggi è
  presidiata solo da regole di deny.
- La regola è **verificabile in review**, non affidata alla buona volontà del modello.

**Negative**
- Vincola il contratto di output di **tutti** i rail, presenti e futuri: è un costo di progettazione
  ricorrente.
- In diagnosi, l'agente ha meno informazioni: un errore che si capirebbe guardando una riga di dato
  richiederà un'escalation all'owner. È un rallentamento accettato consapevolmente, e in linea con
  il principio «un agente bloccato costa un'attesa, un agente che indovina costa un difetto».
- La verifica in review è per sua natura parziale: si vede ciò che compare nel diff e nei commenti,
  non ciò che è transitato nel prompt. Il controllo forte resta il contratto dei rail.

**Da fare**
- Aggiungere la regola al contratto comune dei rail in `03-rail-script.md` §1.
- Aggiungere la voce F5 a `04-checklist-review.md`.
- Aggiungere il principio 11 a `CONTEXT.md` §9.
- Aggiornare il PRD: Q-7 riformulata e chiusa nella parte architetturale, R-5 aggiornato.

---

## Revisione 2026-08-20b — l'artefatto della pipeline, e il canale che il ruolo non chiude

> Origine: `docs/technical/07-architecture-review.md` §13.2, buchi 1 e 6. La **decisione resta**;
> se ne dichiara onestamente il limite.

### 1. Il perimetro si estende all'artefatto della pipeline

Con ADR-0007 i rail non chiamano più direttamente le API Fabric: invocano una pipeline e ne
leggono l'esito. La regola del punto 1 si applica quindi anche, e soprattutto, all'artefatto:

> L'artefatto `rail-result.json` prodotto da una pipeline invocabile da un agente **non contiene
> valori di dato**. Contiene esiti, conteggi, nomi di colonna, identificativi di run.

È un rafforzamento reale e non una formalità: il perimetro passa da «l'agente si comporta bene»
a «l'artefatto è uno schema versionato, e ciò che non è nello schema non raggiunge il modello».
Lo schema è la sede naturale del divieto, ed è verificabile in review sul repo.

Secondo effetto positivo: la distinzione tra **fallimento tecnico** e **fallimento di qualità** —
che in `03-rail-script.md` §4 richiede di guardare gli esiti dei controlli — viene calcolata
**dentro la pipeline**, che ha accesso ai dati, e serializzata come `outcome`. L'agente decide se
escalare senza aver visto un solo valore. È la migliore attuazione possibile di questo ADR.

### 2. Il limite: `Viewer` apre un canale che il ruolo non chiude

ADR-0008 concede al Dev Agent il ruolo **`Viewer`** su workspace effimeri e `dev`. Verificato
**[V]** roles-workspaces: il `Viewer` può «Connect to SQL analytics endpoint of Lakehouse or the
Warehouse» e «Read Lakehouse and Data warehouse data ... with T-SQL through TDS endpoint
(**ReadData**)».

Quindi, detto senza attenuazioni:

> Su quel canale, il divieto di questo ADR **non è imposto dai permessi**: è una regola di prompt
> e di review. È esattamente il tipo di limite che `04-identita-e-permessi.md` §1 dichiara
> inaffidabile.

Non è un motivo per rinunciare a `Viewer` — senza, l'agente è cieco quando serve — ma impone tre
condizioni, recepite in ADR-0008 e qui rese vincolanti per questo ADR:

1. **`Viewer` è concesso solo su workspace con dati sintetici o open data.** Nel momento in cui un
   workspace contiene dati reali di cliente, il ruolo va **revocato**, e la diagnosi passa
   esclusivamente dall'artefatto della pipeline. La concessione è legata alla classificazione del
   dato, non al ruolo dell'agente;
2. la voce **F5** della checklist si estende: *«nessun output di rail, artefatto, commento su
   ticket o commento su PR contiene valori di dato»*;
3. l'interrogazione diretta di Fabric da parte dell'agente è **canale di eccezione**: ammessa in
   diagnosi, mai come sorgente dell'evidenza allegata alla PR. L'evidenza che il Review Agent
   giudica proviene sempre dall'artefatto, che è riproducibile e firmato da un run id.

### 3. Effetto sulla roadmap di hosting (punto 4)

La fase 2 («managed identity, spariscono i client secret») **non è più raggiungibile per intero**
nella parte che riguarda gli agenti in sessione locale. Verificato **[V]** ado-spn: un service
principal non può creare PAT né autenticarsi interattivamente, e OIDC federato non è disponibile
fuori dalla CI. Finché il dispatcher gira sulla macchina dell'owner, **una credenziale long-lived
resta**: certificato o client secret verso Azure DevOps. La riga «fase 2» della tabella va letta
come valida solo se il dispatcher viene effettivamente spostato su una risorsa Azure con
user-assigned managed identity — che è il vero contenuto di quella fase.

Ciò che cambia comunque, e in meglio, è il **valore del bottino**: la credenziale non vale più
«Contributor sulla capacity», vale «accodare N pipeline nominate e leggere in sola lettura».
