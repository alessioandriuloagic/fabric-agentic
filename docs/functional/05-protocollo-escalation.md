# 05 — Protocollo di escalation

> Regola cosa succede quando un agente **non sa cosa fare** o quando due agenti **non sono
> d'accordo**. È il documento che impedisce al sistema di girare a vuoto o di improvvisare.

---

## 1. Il principio

> **Un agente bloccato costa un'attesa. Un agente che indovina costa un difetto in produzione.**

Il sistema è progettato per preferire sempre la prima. Ogni volta che l'agente si trova davanti
a una decisione che il ticket e la knowledge base non coprono, il comportamento corretto è
fermarsi e chiedere — **non** scegliere l'interpretazione più probabile.

---

## 2. Classificazione dei blocchi

| Tipo | Descrizione | Comportamento |
|---|---|---|
| **B1 — Errore proprio** | L'implementazione è sbagliata, la specifica è corretta | Corregge autonomamente, max 3 tentativi |
| **B2 — Specifica ambigua o errata** | Il ticket non dice abbastanza, o dice qualcosa di falso | **Escala all'owner** |
| **B3 — Astrazione mancante** | Il ticket richiede qualcosa che il framework non prevede | **Escala all'owner**, con proposta architetturale |
| **B4 — Permesso mancante** | L'agente non è autorizzato a compiere un'azione necessaria | **Escala all'owner**. Non tenta percorsi alternativi |
| **B5 — Disaccordo con il Review Agent** | Rilievo che il Dev Agent ritiene infondato | Vedi sezione 5 |
| **B6 — Piattaforma indisponibile** | Errore transitorio dell'infrastruttura | Ritenta con attesa crescente, max 3 tentativi, poi escala come B6 |

**B4 merita attenzione particolare.** Se manca un permesso, l'agente non deve cercare una strada
laterale per ottenere lo stesso risultato: quel comportamento è indistinguibile da un tentativo
di aggirare un controllo di sicurezza. Si ferma e lo dichiara.

---

## 3. Come si escala

Quando un agente escala:

1. Mantiene il work item in **Doing** e aggiunge il tag `waiting-input`.
2. Pubblica **un solo** commento strutturato sul ticket.
3. **Termina la sessione.** Non resta in attesa, non ritenta più tardi.

### Formato del commento di blocco

```
STATO: BLOCCATO — <tipo di blocco>

COSA HO FATTO
<sintesi di ciò che è stato completato prima del blocco>

DOVE MI SONO FERMATO
<punto preciso, con riferimento al passo del runbook>

EVIDENZA
<dato oggettivo: messaggio d'errore, conteggio, esito del controllo, run id>

COSA MI SERVE PER PROSEGUIRE
<domanda singola e chiusa, con le opzioni se esistono>
```

### Regole di stesura

| Regola | Motivo |
|---|---|
| **Una sola domanda per commento** | Domande multiple producono risposte parziali e un secondo giro |
| **Domanda chiusa quando possibile** | "Le chiavi sono A+B o A+C?" è meglio di "quali sono le chiavi?" |
| **Sempre con l'evidenza** | L'owner deve poter decidere senza aprire Fabric |
| **Mai proporre un'ipotesi come fatto** | "Sembra che i dati siano duplicati" ≠ "i dati sono duplicati": va mostrato il conteggio |

---

## 4. Esempio reale

Ticket che dichiara come chiave primaria una sola colonna, su un dataset in cui non è univoca.

```
STATO: BLOCCATO — specifica da confermare

COSA HO FATTO
Configurazione creata, pipeline predisposta, carico avviato nel feature workspace.

DOVE MI SONO FERMATO
Passo 6 del runbook — controllo di unicità delle chiavi primarie, prima di qualsiasi scrittura.

EVIDENZA
Dataset: point_events. Righe totali 48.512, valori distinti di member_id 6.043.
La colonna dichiarata come chiave primaria non è univoca.
Le colonne member_id + event_seq risultano invece univoche su tutte le righe.

COSA MI SERVE PER PROSEGUIRE
Confermi che la chiave primaria sia member_id + event_seq, oppure indichi una diversa
combinazione di colonne?
```

Questo è il comportamento corretto: l'agente **non** ha rimosso i duplicati, **non** ha
disattivato il controllo, **non** ha dedotto da solo la chiave corretta pur avendola
individuata. L'ha proposta e ha aspettato.

---

## 5. Disaccordo tra Dev Agent e Review Agent

È il caso più delicato, perché può degenerare in un ping-pong costoso.

### Regole

| # | Regola |
|---|---|
| 1 | Il Dev Agent **deve** rispondere a ogni rilievo: correggendolo, oppure motivando perché lo ritiene infondato |
| 2 | Un rilievo si contesta **solo** citando la knowledge base o la documentazione ufficiale. Mai per opinione |
| 3 | Se un rilievo non è riconducibile ad alcuna voce della checklist, il Dev Agent lo segnala come tale e **non è tenuto ad applicarlo** |
| 4 | **Dopo due iterazioni senza convergenza, il caso escala all'owner.** Il ticket riceve il tag `waiting-input` |
| 5 | La decisione dell'owner è definitiva e, se ha valore generale, **va recepita nella knowledge base o nella checklist** |

> La regola 3 è deliberata e va compresa bene. Un Review Agent che solleva requisiti non
> documentati sta imponendo preferenze proprie, non standard condivisi. Se quel requisito è
> giusto, il posto in cui scriverlo è la checklist — non un commento su una singola PR.
>
> La regola 5 è ciò che rende il sistema capace di imparare: un disaccordo risolto dall'owner e
> non recepito nella documentazione **si ripresenterà identico** al ticket successivo.

### Esito atteso

| Iterazione | Chi agisce |
|---|---|
| 1 | Review Agent solleva i rilievi → Dev Agent corregge o motiva |
| 2 | Review Agent verifica → approva, oppure conferma il rilievo |
| 3 | **Non esiste**: si escala all'owner |

---

## 6. Limiti di sicurezza

Indipendentemente dal tipo di blocco, un agente **non**:

- disattiva, aggira o modifica un controllo di qualità dato per far passare un carico;
- modifica permessi, policy, branch policy o configurazioni di sicurezza;
- accede a risorse per cui non è stato esplicitamente autorizzato;
- inserisce credenziali in chiaro per superare un problema di autenticazione;
- riformula il ticket per adattarlo a ciò che è riuscito a fare.

Il tentativo di una di queste azioni non è un errore da correggere: è un **incidente** e va
trattato come tale dall'owner.

---

## 7. Cosa deve fare l'owner

| Situazione | Azione attesa |
|---|---|
| Blocco B2 (specifica) | Rispondi al commento sul ticket. La risposta risveglia l'agente automaticamente |
| Blocco B3 (astrazione) | Decidi se autorizzare un intervento architetturale, con ADR |
| Blocco B4 (permesso) | Valuta se il permesso vada concesso. **Non concederlo per sbloccare in fretta**: rivedi il perimetro |
| Blocco B6 (piattaforma) | Verifica lo stato dell'infrastruttura e rilancia |
| Disaccordo tra agenti | Decidi, e **recepisci la decisione nella documentazione** |

> Il rischio più concreto per l'owner è concedere permessi per sbloccare velocemente un ticket.
> Ogni permesso concesso in emergenza resta, e nessuno lo rivede più.
