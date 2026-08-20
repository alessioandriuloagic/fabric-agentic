# ADR-0009 — Repository separato con copia dei pattern di deploy, e provenienza dichiarata

| Campo | Valore |
|---|---|
| Stato | **Accettato** — decisione dell'owner, registrata con i rischi espliciti |
| Data | 2026-08-20b |
| Autore | Ralph (Fabric Solution Architect) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §13.2, buco 8 |
| Decisori | Owner |
| Correlati | ADR-0007 |

---

## Contesto

Il progetto Agentic vive in un repository proprio. L'asset di deploy `IP.dai_fabric_environments`
contiene già il plumbing che ADR-0007 vuole riusare: OIDC per tenant, `workspace_manager`
idempotente, configurazione per istanza validata a schema, preflight anti cross-tenant, workflow
dedicati per le operazioni distruttive.

L'owner ha deciso: **il repository Agentic copia i pattern, senza dipendenza di codice**, ed è
consapevole del rischio di divergenza.

La decisione va registrata perché è difficile da invertire e perché è presa **contro un'alternativa
già collaudata in casa**: l'ADR-7 dell'asset stesso distribuisce una libreria compilata come asset
di GitHub Release e la consuma cross-repo con un token dedicato. Il meccanismo per condividere
codice tra repo esiste, funziona ed è in esercizio. La scelta di non usarlo è legittima — un asset
agentico riusabile su clienti non deve dipendere da un IP commerciale — ma non è una scelta
obbligata, ed è utile che tra sei mesi si sappia che non lo era.

## Decisione

**1. Nessuna dipendenza di codice** tra il repository Agentic e `IP.dai_fabric_environments`:
né submodule, né wheel, né import.

**2. Sei pattern vanno copiati per forza**, perché sono controlli di sicurezza o presupposti di
requisiti già scritti, non comodità implementative:

| Pattern | Perché è obbligatorio |
|---|---|
| OIDC + un environment per bersaglio, federated credential vincolata all'environment | È il meccanismo che rende «deploy umano» (RF-72) una proprietà del protocollo di autenticazione |
| Separazione SP di deploy / SP di runtime | Senza, l'esecuzione schedulata dipende da un token scaduto (loro ADR-1) |
| Idempotenza e roll-forward su ogni step | È RNF-07, scritto altrove con altre parole (loro ADR-6) |
| `config/<istanza>/` + jsonschema + validazione fail-fast | È l'attuazione concreta di RF-80 e RNF-11 |
| Preflight prima di ogni scrittura | Nell'asset è anti cross-tenant; qui diventa: **il workspace bersaglio corrisponde al work item**. È il controllo che impedisce a un agente confuso di scrivere nel posto sbagliato |
| Concorrenza per bersaglio | Race condition sul workspace. Su Azure DevOps l'equivalente è il check **Exclusive lock** |

**3. La provenienza è dichiarata.** Il repository Agentic contiene un `PROVENANCE.md` che registra,
per ogni modulo o pattern copiato: file di origine, repository, **commit di origine**, data della
copia e chi l'ha fatta. Una copia senza provenienza è una copia che nessuno saprà più aggiornare.

**4. La divergenza è rivista, non subita.** A ogni slice completato si confronta `PROVENANCE.md`
con lo stato dell'asset di origine e si decide, esplicitamente, cosa riportare e cosa lasciare
divergere. La decisione va scritta; l'assenza di decisione è già una divergenza.

**5. I difetti noti dell'origine non vengono copiati.** L'asset ha TODO di sicurezza aperti e
dichiarati: action di terze parti non pinnate per commit SHA, dipendenze `pip install` non pinnate
per hash. Nel repository Agentic **nascono chiusi**, non ereditati come debito. È l'unico
vantaggio gratuito della copia, e sarebbe assurdo sprecarlo.

**6. L'estrazione futura in libreria condivisa resta aperta.** Se i moduli copiati si stabilizzano
e la manutenzione doppia diventa onerosa, il meccanismo di distribuzione via GitHub Release
dell'asset di origine è la via già collaudata. Questo ADR non la preclude: la rimanda.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Dipendenza da un wheel condiviso** | L'asset Agentic è destinato a essere istanziato su clienti diversi (RF-80) e mostrato in prevendita (OB-4): una dipendenza da un IP commerciale ne complicherebbe la distribuzione e legherebbe due cicli di rilascio indipendenti. Decisione dell'owner |
| **Submodule Git verso l'asset** | Peggiore di entrambe le alternative: accoppiamento forte senza interfaccia pubblicata, e chiunque cloni il repo Agentic vede il sorgente dell'IP |
| **Un solo repository per entrambi i progetti** | Contraddice la separazione di scopo, e replicherebbe il problema che il loro ADR-7 aveva già risolto |
| **Riscrivere da zero senza guardare l'asset** | Butterebbe via 56 test, 89% di coverage e i sei controlli di sicurezza della tabella. Non è indipendenza, è amnesia |

## Conseguenze

**Positive**
- Il repository Agentic è autonomo, distribuibile e istanziabile senza dipendenze commerciali.
- Nessun rischio di esporre l'IP dell'asset di origine a chi opera il progetto Agentic.
- I difetti noti dell'origine non vengono importati (punto 5).

**Negative**
- **Manutenzione doppia**: ogni correzione di sicurezza e ogni adeguamento alle API Fabric in
  preview (Folders API — ADR-0003) va fatto due volte. È un costo ricorrente, non una tantum.
- Il patrimonio di test dell'asset (56 test, 89% di coverage) **riparte da zero**: il repository
  Agentic non eredita hardening, eredita struttura.
- La divergenza è certa; l'unica scelta è tra divergenza tracciata e divergenza scoperta. Il punto
  3 sceglie la prima.

**Da fare**
- Creare `PROVENANCE.md` alla radice del repository Agentic, **allo Slice 0**, prima della prima
  copia. Dopo la prima copia nessuno lo scriverà più.
- Aggiungere la revisione della divergenza alla lista delle attività periodiche di
  `04-identita-e-permessi.md` §7.
- Censire in `05-struttura-repository.md` la collocazione dei moduli copiati.
