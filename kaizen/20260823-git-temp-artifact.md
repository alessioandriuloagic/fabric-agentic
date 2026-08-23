# Escludere gli artifact temporanei dai commit

**Date**: 2026-08-23 | **Context**: analisi artifact del run CRM e PR #38

## What happened
Il file temporaneo scaricato da GitHub per leggere `rail-result.json` è entrato accidentalmente nel commit del fix notebook.

## Why it was wrong
Gli artifact di diagnosi non fanno parte del prodotto e possono contenere evidenze operative non destinate al repository.

## What to do instead
Dopo ogni download locale usare una cartella fuori dal repository oppure verificare `git status` prima di `git add -A`.
Rimuovere sempre i temporanei prima del commit e controllare il diff staged, soprattutto quando si usa `git add -A`.
