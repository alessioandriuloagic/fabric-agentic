# 04 — Checklist di review

> Criteri **chiusi** con cui il Review Agent giudica ogni pull request.
> Chiusi significa: il Review Agent non ne aggiunge di propri e non ne salta nessuno.

---

## 1. Come funziona

- La checklist è **versionata**: modificarla richiede una PR, come per il codice.
- Il Review Agent produce un esito per **ogni** voce: `PASSATO`, `RILIEVO` o `NON APPLICABILE`.
- `NON APPLICABILE` va motivato. Un `NON APPLICABILE` non motivato è esso stesso un rilievo.
- Anche **un solo** `RILIEVO` impedisce l'approvazione.
- Alla re-review, le voci già corrette assumono lo stato `CORRETTO`.

### Cosa il Review Agent può e non può

| Può | Non può |
|---|---|
| Leggere il diff sulla propria copia del repo | Accedere a Fabric |
| Leggere la knowledge base e la documentazione ufficiale | Eseguire carichi o script di build |
| Commentare e votare | Modificare il codice di feature |

> Il Review Agent **non si fida della descrizione della PR**: verifica il diff. E poiché non
> può produrre evidenze, un'evidenza mancante è sempre un rilievo — non può andarsela a prendere.

---

## 2. La checklist

### A — Conformità alle convenzioni

| # | Criterio |
|---|---|
| A1 | Ogni item creato o rinominato rispetta i prefissi e le convenzioni di naming di `CONTEXT.md` |
| A2 | Ogni item è collocato nella cartella del proprio layer: nessun item alla radice del workspace |
| A3 | Il nome del branch e del feature workspace è derivato dall'ID del work item |
| A4 | I nomi di source system, dataset, tabelle e colonne rispettano le convenzioni dati |

### B — Aderenza al ticket

| # | Criterio |
|---|---|
| B1 | Tutti i criteri di accettazione del ticket sono soddisfatti |
| B2 | Nulla di ciò che il ticket dichiara **fuori scope** è stato toccato |
| B3 | Non sono state introdotte modifiche non richieste dal ticket |
| B4 | Le chiavi primarie, la modalità di carico e il watermark corrispondono a quanto dichiarato nel ticket |

> B3 è la voce che intercetta l'iniziativa non richiesta. Una modifica utile ma non chiesta
> resta un rilievo: va tracciata in un ticket proprio, non infilata in questa PR.

### C — Evidenza dell'esecuzione

| # | Criterio |
|---|---|
| C1 | La PR allega l'evidenza di un'esecuzione reale, non solo la descrizione dell'intenzione |
| C2 | Il controllo di unicità delle chiavi primarie risulta superato |
| C3 | I conteggi di riconciliazione sorgente/destinazione sono coerenti |
| C4 | L'identificativo del run è riportato ed è riconducibile al feature workspace del ticket |

### D — Integrità architetturale

| # | Criterio |
|---|---|
| D1 | L'onboarding è avvenuto per **sola configurazione**: nessun codice ad hoc per la sorgente specifica |
| D2 | Il notebook o la logica di carico condivisa non è stata duplicata né ramificata per sorgente |
| D3 | Il controllo di concorrenza della pipeline è impostato a esecuzione singola |
| D4 | La logica di orchestrazione non contiene riferimenti alla tipologia di sorgente |

### E — Documentazione

| # | Criterio |
|---|---|
| E1 | La documentazione impattata è aggiornata **nella stessa PR** |
| E2 | L'inventario delle sorgenti e dei dataset riflette lo stato reale dopo la modifica |
| E3 | `CHANGELOG.md` contiene una voce sotto `[Unreleased]` |
| E4 | Ogni affermazione sulla piattaforma Fabric presente nei documenti modificati è verificabile sulla documentazione ufficiale. Una contraddizione è un rilievo |
| E5 | La documentazione non è stata aggiornata solo in aggiunta: le parti rese obsolete dalla modifica sono state corrette |

### F — Sicurezza

| # | Criterio |
|---|---|
| F1 | Nessun segreto in chiaro: né in configurazione, né in pipeline, né in notebook, né nei documenti |
| F2 | Le credenziali sono referenziate dal secret store, mai incorporate |
| F3 | Il diff non contiene modifiche a permessi, policy o identità |
| F4 | Il diff non contiene tentativi di modifica alle branch policy o alle regole di protezione |

> F3 e F4 non sono formalità. Un agente che modifica i propri permessi è lo scenario che l'intero
> modello di sicurezza esiste per impedire. Qualunque occorrenza è un rilievo **bloccante** ed
> escala immediatamente all'owner.

---

## 3. Formato dell'esito

Il Review Agent pubblica sulla PR un unico commento strutturato:

```
ESITO REVIEW — <identificativo PR> — iterazione <n>

A1 PASSATO
A2 PASSATO
...
D1 RILIEVO — <descrizione puntuale, con riferimento al file e alla riga>
...

VOTO: NON APPROVATO — 1 rilievo aperto
```

Regole di stesura:

- Ogni rilievo indica **dove** (file, riga) e **cosa** va corretto, non solo che qualcosa non va.
- Nessun rilievo è formulato come opinione: se non è riconducibile a una voce della checklist,
  non è un rilievo.
- Il Review Agent non propone il codice della correzione: descrive il difetto.

---

## 4. Manutenzione della checklist

| Situazione | Azione |
|---|---|
| Un difetto è sfuggito alla review ed è arrivato in `main` | Aggiungere la voce corrispondente, con PR dedicata |
| Una voce genera ripetutamente falsi positivi | Riformularla o rimuoverla, motivando in PR |
| Nuova tipologia di workload in scope (es. Power BI) | Aggiungere la sezione dedicata **prima** di attivare quel workload |

> La checklist cresce per **apprendimento dai difetti reali**, non per intuizione. Ogni voce
> dovrebbe poter citare l'incidente che l'ha generata.
