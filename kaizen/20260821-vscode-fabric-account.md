# Account VS Code per Fabric

**Date**: 2026-08-21 | **Context**: cambio account nell'estensione Microsoft Fabric

## What happened
Il comando `Accounts: Add an Account` non e' disponibile nell'installazione VS Code corrente.

## Why it was wrong
L'estensione Fabric espone i comandi `vscode-fabric.signIn` e `vscode-fabric.switchTenant`, ma non un comando generico per aggiungere account.

## What to do instead
Usare il menu Account di VS Code per disconnettere l'account ACDA, quindi eseguire `Fabric: Sign in` e autenticarsi con l'account Agic Dev.
