"use strict";

const elements = {
  form: document.querySelector("#profile-form"),
  displayName: document.querySelector("#display-name"),
  projectSlug: document.querySelector("#project-slug"),
  trackerType: document.querySelector("#tracker-type"),
  trackerOwner: document.querySelector("#tracker-owner"),
  trackerRepository: document.querySelector("#tracker-repository"),
  trackerOwnerLabel: document.querySelector("#tracker-owner-label"),
  trackerRepoLabel: document.querySelector("#tracker-repo-label"),
  connector: document.querySelector("#connector"),
  connectorOptions: document.querySelector("#connector-options"),
  connectorCapabilities: document.querySelector("#connector-capabilities"),
  supportsIncremental: document.querySelector("#supports-incremental"),
  supportsSourceCount: document.querySelector("#supports-source-count"),
  sourceName: document.querySelector("#source-name"),
  connectionRef: document.querySelector("#connection-ref"),
  datasetName: document.querySelector("#dataset-name"),
  primaryKey: document.querySelector("#primary-key"),
  loadMode: document.querySelector("#load-mode"),
  watermark: document.querySelector("#watermark"),
  watermarkLabel: document.querySelector("#watermark-label"),
  credentialName: document.querySelector("#credential-name"),
  credentialStore: document.querySelector("#credential-store"),
  credentialReference: document.querySelector("#credential-reference"),
  validationBadge: document.querySelector("#validation-badge"),
  validationSummary: document.querySelector("#validation-summary"),
  workspacePreview: document.querySelector("#workspace-preview"),
  featurePreview: document.querySelector("#feature-preview"),
  datasetPreview: document.querySelector("#dataset-preview"),
  adapterPreview: document.querySelector("#adapter-preview"),
  download: document.querySelector("#download-profile"),
  importBar: document.querySelector("#import-bar"),
  profileFile: document.querySelector("#profile-file"),
  schemaLabel: document.querySelector("#schema-label"),
};

let contract;
let importedProfile;

function fillSelect(select, values) {
  select.replaceChildren(...values.map(value => new Option(value.replaceAll("_", " "), value)));
}

function fillDatalist(datalist, values) {
  datalist.replaceChildren(...values.map(value => new Option(value, value)));
}

function value(id) {
  return elements[id].value.trim();
}

function buildProfile() {
  const environments = [...document.querySelectorAll("input[name='environment']:checked")].map(input => input.value);
  const tracker = { ...(importedProfile?.tracker || {}), type: value("trackerType") };
  if (tracker.type === "github_issues") {
    tracker.owner = value("trackerOwner");
    tracker.repository = value("trackerRepository");
  } else {
    tracker.organization = value("trackerOwner");
    tracker.project = value("trackerRepository");
  }
  const dataset = {
    name: value("datasetName"),
    primary_key: value("primaryKey").split(",").map(item => item.trim()).filter(Boolean),
    load_mode: value("loadMode"),
  };
  if (dataset.load_mode === "incremental") dataset.watermark_column = value("watermark");
  const firstImportedSource = importedProfile?.sources?.[0] || {};
  const firstImportedDataset = firstImportedSource.datasets?.[0] || {};
  const firstDataset = { ...firstImportedDataset, ...dataset };
  if (dataset.load_mode === "full") delete firstDataset.watermark_column;
  const source = {
    ...firstImportedSource,
    name: value("sourceName"),
    connector: value("connector"),
    connection_ref: value("connectionRef"),
    datasets: [firstDataset, ...(firstImportedSource.datasets?.slice(1) || [])],
  };
  if (contract["x-fabric-agentic"].connectors[source.connector]) {
    delete source.capabilities;
  } else {
    source.capabilities = {
      supports_incremental: elements.supportsIncremental.checked,
      supports_source_count: elements.supportsSourceCount.checked,
    };
  }
  return {
    ...(importedProfile || {}),
    schema_version: contract.properties.schema_version.const,
    project: { slug: value("projectSlug"), display_name: value("displayName") },
    tracker,
    environments,
    sources: [source, ...(importedProfile?.sources?.slice(1) || [])],
    credentials: [{
      ...(importedProfile?.credentials?.[0] || {}),
      name: value("credentialName"),
      store: value("credentialStore"),
      reference: value("credentialReference"),
    }, ...(importedProfile?.credentials?.slice(1) || [])],
  };
}

function validate(profile) {
  const errors = [];
  const slugPattern = new RegExp(contract.properties.project.properties.slug.pattern);
  if (!profile.project.display_name) errors.push("Inserisci il nome visualizzato.");
  if (!slugPattern.test(profile.project.slug)) errors.push("Lo slug non rispetta il formato del contratto.");
  if (!profile.tracker.owner && !profile.tracker.organization) errors.push("Completa il proprietario del tracker.");
  if (!profile.tracker.repository && !profile.tracker.project) errors.push("Completa repository o progetto.");
  if (!profile.environments.length) errors.push("Seleziona almeno un ambiente.");
  const datasetNames = new Set();
  profile.sources.forEach(source => {
    if (!source.name || !source.connection_ref) errors.push("Completa sorgente e riferimento connessione.");
    const connectorPattern = new RegExp(contract.$defs.source.properties.connector.pattern);
    if (!connectorPattern.test(source.connector)) errors.push("Il connector deve usare minuscole, numeri e underscore.");
    const capabilities = contract["x-fabric-agentic"].connectors[source.connector] || source.capabilities;
    source.datasets.forEach(dataset => {
      if (!dataset.name || !dataset.primary_key.length) errors.push("Completa dataset e chiave primaria.");
      if (datasetNames.has(dataset.name)) errors.push(`Il dataset ${dataset.name} è dichiarato più volte.`);
      datasetNames.add(dataset.name);
      if (dataset.load_mode === "incremental" && capabilities && !capabilities.supports_incremental) errors.push(`Il connector ${source.connector} non supporta carichi incrementali.`);
      if (dataset.load_mode === "incremental" && !dataset.watermark_column) errors.push(`Il dataset ${dataset.name} richiede una colonna watermark.`);
      if (dataset.load_mode === "full" && dataset.watermark_column) errors.push(`Il dataset ${dataset.name} full non può dichiarare un watermark.`);
    });
  });
  const forbidden = contract["x-fabric-agentic"].forbidden_credential_fields;
  profile.credentials.forEach(credential => {
    if (!credential.name || !credential.store || !credential.reference) errors.push("Completa il riferimento alla credenziale.");
    if (forbidden.some(field => credential.reference.toLowerCase().includes(`${field}=`))) errors.push("Il riferimento sembra contenere un valore segreto.");
  });
  return errors;
}

function updateTrackerLabels() {
  const github = elements.trackerType.value === "github_issues";
  elements.trackerOwnerLabel.firstChild.textContent = github ? "Owner" : "Organizzazione";
  elements.trackerRepoLabel.firstChild.textContent = github ? "Repository" : "Progetto";
}

function updateLoadModes() {
  const adapter = contract["x-fabric-agentic"].connectors[elements.connector.value];
  elements.connectorCapabilities.hidden = Boolean(adapter);
  const supportsIncremental = adapter
    ? adapter.supports_incremental
    : elements.supportsIncremental.checked;
  const modes = contract.$defs.dataset.properties.load_mode.enum.filter(mode => mode !== "incremental" || supportsIncremental);
  const previous = elements.loadMode.value;
  fillSelect(elements.loadMode, modes);
  if (modes.includes(previous)) elements.loadMode.value = previous;
  const incremental = elements.loadMode.value === "incremental";
  elements.watermarkLabel.hidden = !incremental;
  elements.watermark.required = incremental;
  if (!incremental) elements.watermark.value = "";
}

function render() {
  if (!contract) return;
  updateTrackerLabels();
  const profile = buildProfile();
  const errors = validate(profile);
  const slug = profile.project.slug;
  elements.workspacePreview.textContent = slug ? `ws_${slug}_${profile.environments[0] || "<ambiente>"}` : "—";
  elements.featurePreview.textContent = slug ? `ws_${slug}_feature_wi<work-item>` : "—";
  elements.datasetPreview.textContent = profile.sources[0].datasets[0].name || "—";
  elements.adapterPreview.textContent = contract["x-fabric-agentic"].connectors[profile.sources[0].connector]
    ? "disponibile"
    : "da implementare";
  elements.validationSummary.textContent = errors[0] || "";
  elements.validationBadge.textContent = errors.length ? `${errors.length} da completare` : "Profilo pronto";
  elements.validationBadge.className = `validation-badge ${errors.length ? "invalid" : "valid"}`;
  elements.download.disabled = errors.length > 0;
}

function loadProfile(profile) {
  importedProfile = profile;
  const source = profile.sources?.[0] || {};
  const dataset = source.datasets?.[0] || {};
  const credential = profile.credentials?.[0] || {};
  elements.displayName.value = profile.project?.display_name || "";
  elements.projectSlug.value = profile.project?.slug || "";
  elements.trackerType.value = profile.tracker?.type || elements.trackerType.value;
  elements.trackerOwner.value = profile.tracker?.owner || profile.tracker?.organization || "";
  elements.trackerRepository.value = profile.tracker?.repository || profile.tracker?.project || "";
  document.querySelectorAll("input[name='environment']").forEach(input => { input.checked = profile.environments?.includes(input.value) || false; });
  elements.sourceName.value = source.name || "";
  elements.connector.value = source.connector || elements.connector.value;
  elements.supportsIncremental.checked = source.capabilities?.supports_incremental || false;
  elements.supportsSourceCount.checked = source.capabilities?.supports_source_count ?? true;
  elements.connectionRef.value = source.connection_ref || "";
  elements.datasetName.value = dataset.name || "";
  elements.primaryKey.value = (dataset.primary_key || []).join(", ");
  updateLoadModes();
  elements.loadMode.value = dataset.load_mode || elements.loadMode.value;
  elements.watermark.value = dataset.watermark_column || "";
  elements.credentialName.value = credential.name || "";
  elements.credentialStore.value = credential.store || "";
  elements.credentialReference.value = credential.reference || "";
  updateLoadModes();
  render();
}

function downloadProfile() {
  const blob = new Blob([`${JSON.stringify(buildProfile(), null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "instance.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

async function start() {
  try {
    const [schemaResponse, starterResponse] = await Promise.all([fetch("instance-profile-v1.0.json"), fetch("starter-instance.json")]);
    if (!schemaResponse.ok || !starterResponse.ok) throw new Error("Contratto non disponibile");
    contract = await schemaResponse.json();
    const starter = await starterResponse.json();
    fillSelect(elements.trackerType, contract.properties.tracker.properties.type.enum);
    fillDatalist(elements.connectorOptions, contract["x-fabric-agentic"].suggested_connectors);
    fillSelect(elements.loadMode, contract.$defs.dataset.properties.load_mode.enum);
    document.querySelector(".schema-state").classList.add("ready");
    elements.schemaLabel.textContent = `Schema ${contract.properties.schema_version.const} · locale`;
    loadProfile(starter);
  } catch (error) {
    elements.schemaLabel.textContent = "Contratto non disponibile";
    elements.validationSummary.textContent = error.message;
  }
}

elements.form.addEventListener("input", render);
elements.trackerType.addEventListener("change", render);
elements.connector.addEventListener("input", () => { updateLoadModes(); render(); });
elements.supportsIncremental.addEventListener("change", () => { updateLoadModes(); render(); });
elements.supportsSourceCount.addEventListener("change", render);
elements.loadMode.addEventListener("change", () => { updateLoadModes(); render(); });
elements.download.addEventListener("click", downloadProfile);
elements.profileFile.addEventListener("change", async event => {
  try { loadProfile(JSON.parse(await event.target.files[0].text())); }
  catch { elements.validationSummary.textContent = "Il file selezionato non è JSON valido."; }
});
document.querySelectorAll(".mode").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".mode").forEach(item => { item.classList.toggle("active", item === button); item.setAttribute("aria-pressed", String(item === button)); });
  elements.importBar.hidden = button.dataset.mode !== "existing";
}));

start();