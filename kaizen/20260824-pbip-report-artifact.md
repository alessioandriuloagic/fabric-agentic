# PBIP manifest: report artifact only

**Date**: 2026-08-24 | **Context**: apertura di `powerbi/CRM Demo.pbip` con Power BI Desktop

## What happened
Il manifest è stato corretto prima a `dataset`, ma Power BI Desktop ha rifiutato anche quella forma:
`Property 'dataset' has not been defined`.

## Why it was wrong
Nel formato PBIP del Desktop l'array `artifacts` contiene l'artifact `report`. Il semantic model
non è un secondo artifact top-level: viene collegato dal `datasetReference` in `definition.pbir`.

## What to do instead
Mantenere un solo elemento `artifacts[].report` nel file `.pbip`.
Lasciare il collegamento al semantic model in `CRM Demo.Report/definition.pbir` e validare il manifest
con Power BI Desktop prima della pubblicazione.
