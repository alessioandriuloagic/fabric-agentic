# 12 — Console e avvio

> Cosa deve esistere sulla macchina perché la catena parta, come si verifica in un comando solo, e
> come si guarda lo stato senza aprire file di configurazione.

---

## 1. Il problema che risolve

I tre dispatcher hanno funzionato prima che esistesse una convenzione: ogni prova usava un file di
configurazione diverso, creato al momento e poi perso. Il risultato è che il sistema era
**riavviabile solo da chi lo aveva appena avviato**. Per un kit distribuito a colleghi questo è il
difetto principale, prima ancora delle funzionalità.

La console non aggiunge capacità agli agenti: rende **verificabile e ripetibile** l'avvio.

---

## 2. Layout canonico

Tutto vive sotto una sola cartella, per default `~/.fabric-agentic`, sovrascrivibile con la
variabile `FABRIC_AGENTIC_HOME` o con `--home`.

```
~/.fabric-agentic/
  issue-agent/
    dispatcher-config.json
    github-app-private-key.pem
    repository/            clone dedicato
    state.json             stato del dispatcher
    tasks/                 handoff verso la sessione
  dev-agent/     ...
  review-agent/  ...
```

Un agente è **pronto** quando esistono configurazione, identità provisionata, chiave privata
riservata al proprietario e clone dedicato. Il Dev Agent richiede anche il tracker dichiarato.

---

## 3. Verifica

```
python -m fabric_agentic doctor
```

Esce con codice `0` solo se tutti e tre gli agenti sono pronti, e per ognuno stampa il comando di
avvio già completo di percorsi.

I controlli rispecchiano ciò che il dispatcher **legge davvero**: se il `doctor` fosse più
tollerante del consumatore, un esito verde precederebbe un avvio rosso, ed è esattamente quello che
è successo la prima volta. Due difetti reali emersi così:

| Difetto | Effetto |
|---|---|
| Configurazione scritta da PowerShell con BOM | Il dispatcher rifiutava un JSON valido. Ora il lettore condiviso accetta il BOM |
| `dispatcher.tracker_type` non dichiarato | Il Dev Agent ripiegava in silenzio su Azure DevOps e pescava work item di un tracker dismesso. Ora il tracker va dichiarato |

L'attività osservata (ultimo ciclo registrato) è **informativa, non un requisito**: un agente appena
configurato è pronto, semplicemente non ha ancora girato.

---

## 4. Console

```
python -m fabric_agentic console
```

Pagina in sola lettura su `http://127.0.0.1:8765/` con lo stato dei tre agenti e il comando di
avvio di ciascuno.

Vincoli deliberati:

- ascolta solo su loopback e risponde solo a `GET`;
- rifiuta richieste il cui header `Host` non è di loopback, per non essere raggiungibile via DNS
  rebinding da una pagina remota;
- **non avvia processi, non chiama GitHub o Fabric, non legge materiale crittografico.** Verifica
  che la chiave privata esista, mai il suo contenuto.

L'assenza di pulsanti di avvio è una scelta: una pagina locale che lancia processi è una superficie
di esecuzione remota raggiungibile dal browser. Finché non c'è un runtime dedicato, l'avvio resta
un'azione esplicita da terminale.

---

## 5. Profilo di istanza

```
python -m fabric_agentic validate --config profiles/<cliente>/instance.json
python -m fabric_agentic render   --config profiles/<cliente>/instance.json --output .generated
```

`validate` rifiuta il profilo **prima** di qualsiasi chiamata esterna. `render` genera il piano di
deployment: `plan.json` per il consumo automatico e `README.md` per la lettura umana.

Il render è **riproducibile byte per byte**: nessun timestamp nell'output e newline fissi, così lo
stesso profilo produce gli stessi file su Windows e su Linux e un diff segnala solo cambiamenti
reali. Le capacità dei connector nel piano arrivano dal registry, non sono riscritte a mano.

Nel piano entrano solo **riferimenti** a credenziali: il profilo rifiuta valori inline, e qui non
viene generato alcun segreto.

`doctor --config <profilo>` unisce le due verifiche: identità provisionate **e** profilo valido.

---

## 6. Avvio

Il campo `claude_command` resta portabile (`claude`): il dispatcher lo risolve nel `PATH` della
macchina prima dell'avvio, incluso il suffisso `.exe` richiesto da Python su Windows. Non inserire
nel file di configurazione un percorso assoluto legato all'operatore.

Prima verifica, poi avvia. In tre terminali distinti:

```
python -m fabric_agentic doctor
python -m scripts.issue_dispatcher  --config ... --state ... --tasks ... --poll
python -m scripts.dev_dispatcher    --config ... --state ... --tasks ... --log ... --poll
python -m scripts.review_dispatcher --config ... --state ... --tasks ... --poll
```

Aggiungere `--once --dry-run` mostra cosa verrebbe raccolto senza avviare alcuna sessione e senza
scrivere su GitHub: è il modo corretto per la prima prova. `--cycles N` limita il numero di giri,
utile per una verifica breve.

### Perché il ciclo si ferma dopo tre fallimenti consecutivi

Lo stato anti-loop avanza **solo** quando un ciclo riesce. Un ciclo che fallisce non lo aggiorna,
quindi un errore persistente rilancerebbe la stessa sessione a ogni intervallo: un ciclo caldo e
costoso, non un semplice retry. Dopo tre fallimenti consecutivi il loop si arresta con errore. Un
ciclo riuscito azzera il contatore, così un errore transitorio non ferma l'agente.

La configurazione viene letta una sola volta all'avvio: un file invalido fallisce subito, non dopo
tre giri.

---

## Documenti correlati

- [02 — Dispatcher](02-dispatcher.md) — trigger e ciclo di vita delle sessioni
- [04 — Identità e permessi](04-identita-e-permessi.md) — provisioning delle GitHub App
