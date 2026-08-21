# GitHub App PEM file verification

**Date**: 2026-08-21 | **Context**: bootstrap della GitHub App del Dev Agent

## What happened
La presenza della key nella UI GitHub e' stata confusa con la disponibilita' del PEM locale richiesto dal dispatcher.

## Why it was wrong
La UI mostra il record/fingerprint della key, mentre la firma JWT richiede il file PEM privato scaricato una sola volta.

## What to do instead
Verificare solo esistenza, ACL, dimensione plausibile e caricamento crittografico del PEM; mai stamparne contenuto, hash o token.
Un file troppo piccolo e' un segnaposto o un download errato, anche se la key risulta presente nella UI GitHub.