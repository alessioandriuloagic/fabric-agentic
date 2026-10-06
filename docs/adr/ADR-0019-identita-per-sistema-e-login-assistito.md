# ADR-0019 - Identita' per sistema e login utente assistito

| Campo | Valore |
|---|---|
| Stato | Accettata - owner, sessione del 2026-10-06 |
| Data | 2026-10-06 |
| Integra | ADR-0007, ADR-0008, ADR-0013 e ADR-0017; non li supera integralmente |

## Contesto

I clienti spesso concedono un'utenza nominale o di servizio, non SP di esecuzione dedicati.
Richiedere SP per ciascun agente impedisce l'adozione da parte dei colleghi. L'owner accetta
login/MFA interattivi e operativita' solo mentre il collega lavora. Tracker AGIC e Fabric cliente
possono appartenere a organizzazioni e tenant diversi. GitHub Apps, SP Entra e licenze AI sono
oggetti distinti: un'identita' valida su uno non autorizza gli altri.

## Decisione

1. Configurare indipendentemente autenticazione del tracker, accesso Fabric e runtime AI.
2. Sul tracker AGIC conservare le identita' applicative distinte: GitHub Apps su GitHub,
   SP Entra nel percorso Azure DevOps esistente. Nessuna migrazione automatica dei login attivi.
3. Sul tracker cliente ammettere un'utenza autorizzata, con contesto CLI esplicito e verifica
   dell'account; per Azure DevOps verificare anche il tenant. Nessun fallback silenzioso ad App,
   nessun token in profili, task, argv, output o log dei provider.
4. Per Fabric il percorso base senza SP di esecuzione e' assistito: login/MFA dell'operatore,
   tenant/account/workspace verificati. Non promette disponibilita' unattended o elusione di CA.
5. Il publisher deterministico resta l'unico a pubblicare pacchetti ed esiti Review. Nel percorso
   nominale autore + marcatore di ruolo distinguono pubblicazioni automatiche da interventi umani.
6. Se autore della PR e reviewer coincidono, la submission nominale e' COMMENT, non APPROVE o
   REQUEST_CHANGES. Il risultato conserva il voto richiesto e dichiara l'assenza di identita'
   indipendente. Merge e approvazione finale restano umani.
7. Un riferimento d'inferenza descrive ownership/licenza; non autentica il runtime AI. Login,
   licenza aziendale e scelta del modello Review restano prerequisiti separati.

## Conseguenze

- Meno prerequisiti applicativi cliente; stessa installazione del kit, contesti per cliente e ruolo.
- Audit di ruolo possibile anche con utenza condivisa, ma i marcatori non sono firme crittografiche
  e non ricreano separazione dei permessi. Il token utente puo' avere privilegi piu' ampi delle App.
- Cache distinte evitano incroci accidentali; non isolano processi che girano come lo stesso utente OS.
  Il wrapper che blocca export token non costituisce una sandbox del modello.
- Scadenza, revoca, consenso o CA possono fermare il ciclo: si richiede login all'operatore, non una
  password in chat o un bypass MFA. Finito il lavoro, arrestare polling e fare logout.
- Issue e Review operativi rimangono GitHub-only. Il provider Azure DevOps nominale riguarda il
  tracker Dev; una catena completa Issue/Review su Azure Boards richiede un incremento separato.
- Deploy/carichi Fabric del Dev senza SP non sono abilitati da questa decisione. La creazione
  workspace collaudata dall'operatore non prova l'integrazione nel dispatcher. Le regole CI/CD
  di ADR-0007 e le protezioni del ramo principale non cambiano implicitamente.

## Alternative

| Alternativa | Perche' non scelta come baseline |
|---|---|
| SP obbligatorio per ogni ruolo cliente | Non compatibile con i permessi normalmente concessi |
| Un'identita' globale per tutti i clienti e sistemi | Confonde revoca, audit, tenant e impatto di un incidente |
| Password grant o disattivazione MFA | Incompatibile con il login autorizzato e le policy cliente |
| Review nominale condivisa presentata come indipendente | Non offre un confine di autorizzazione distinto |

## Verifica

Test automatici su provider, config, attribution, publisher, idempotenza, auto-review e schema.
Prova live del 2026-10-06: login nominale Fabric, riuso sessione e creazione workspace verificata
tramite GET. Nessuna prova live dei tracker cliente in questa sessione. Stato e istruzioni nella
[guida operativa](../technical/15-identita-e-autenticazione.md).