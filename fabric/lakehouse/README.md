# Lakehouse Artifacts

`lh_demo.Lakehouse` is the throwaway Lakehouse requested by work item #196. It exists so the
notebook `nb_demo_alessio` has somewhere to write the Delta table `demo_alessio` in the feature
workspace of that work item; it is a check of the chain, not an onboarded dataset, so it is
documented here and not under `docs/sources/`.

The artifact is versioned in the Fabric Git source format, like the notebooks: a folder named
`<display name>.Lakehouse` holding `.platform` — item type, display name, description and a
`logicalId` of its own — plus `lakehouse.metadata.json`. Git integration tracks Lakehouse
**metadata** only: tables and the content of `Files` are never versioned here, which is why the
rows of `demo_alessio` are written by the notebook and not by this folder.

The rail `sync_workspace` materializes the folder in the feature workspace through
`git/updateFromGit`. Authoring a Lakehouse folder by hand instead of letting Fabric serialize an
existing item is the one step of work item #196 that Microsoft Learn does not document explicitly;
decision D2 on that work item accepted the residual risk rather than requiring a manual round
trip. `nb_demo_alessio` carries the fallback: it looks the Lakehouse up by name and creates it with
`notebookutils.lakehouse.create` when it is missing, so a run does not depend on the folder having
materialized.

Items land in the workspace folder that mirrors their Git folder, so this directory is what puts
`lh_demo` under a `lakehouse` folder rather than at the workspace root, as decision D6 on work item
#196 asks. Reconciling that item-type layout with the medallion folders of `CONTEXT.md` §3.3 is a
separate decision and is not settled here.
