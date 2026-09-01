# ADR-0016 — Registry dei connector e capacità dichiarate

| Campo | Valore |
|---|---|
| Stato | Superata in parte da ADR-0018 |
| Data | 2026-08-31 |
| Contesto | Work item #123, #126 |

## Contesto

L'elenco dei connector ammessi era una tupla scritta a mano in `instance_profile`, e la costruzione
della richiesta OData viveva in `scripts/crm_framework`, legata all'entità `accounts`. Aggiungere una
sorgente avrebbe richiesto di toccare più punti scollegati, e nulla impediva a un profilo di
dichiarare una modalità di carico che la sorgente non è in grado di eseguire.

Il caso concreto è `pagamenti`: un CSV depositato non espone alcun marcatore di modifica lato
sorgente, quindi non può essere letto in modo incrementale. Finora questo vincolo esisteva solo
nella testa di chi aveva scritto il notebook.

## Decisione

1. `fabric_agentic/connectors.py` è l'unico registry degli adapter eseguibili. La decisione
   originaria di derivarne anche l'elenco dei connector ammessi è superata da ADR-0018.
2. Ogni connector dichiara le proprie **capacità**: lettura incrementale, conteggio alla sorgente,
   campi di connessione richiesti. Il profilo viene rifiutato se chiede una capacità assente.
3. `plan_request` risolve la lettura di un dataset passando dal registry, così l'orchestrazione non
   contiene rami per singola sorgente. Il planner OData è l'unica implementazione dell'URL
   Dataverse: `crm_framework` lo richiama invece di ricostruirlo.
4. Il contratto comune viaggia in `DatasetRequest` (nome, chiave primaria, colonne, colonna di
   watermark): dati che il profilo già conosce, senza specificità di connector.

## Decisione su `pagamenti`

`file` è un connector **supportato e registrato**, non un esempio isolato: è la seconda sorgente che
dimostra il confine. È però dichiarato `supports_incremental = False`, quindi un profilo che
chiedesse un carico incrementale su file viene rifiutato in validazione anziché fallire a runtime.

## Alternative scartate

| Alternativa | Motivo del rifiuto |
|---|---|
| Connector come sottoclassi con ereditarietà | Nessun comportamento condiviso da ereditare: capacità dichiarative e una funzione di planning bastano |
| Lasciare il planning in `crm_framework` | Due implementazioni dello stesso URL, e il core resterebbe dipendente da `scripts/` |
| `pagamenti` come esempio isolato | Con una sola sorgente registrata il confine resterebbe indimostrato |
| Capacità dedotte a runtime dal connector | Un profilo non valido fallirebbe a metà carico invece che in validazione |

## Conseguenze

- Aggiungere un adapter eseguibile significa registrare il planner in un punto solo; descrivere una
   nuova tecnologia sorgente non richiede invece codice (ADR-0018).
- Le combinazioni impossibili sono rifiutate prima dell'esecuzione.
- Il core resta senza dipendenze e senza valori di tenant o cliente.
- Un connector con esigenze di richiesta molto diverse potrebbe non essere coperto da
  `DatasetRequest`: in quel caso il contratto va esteso, non aggirato con rami locali.
