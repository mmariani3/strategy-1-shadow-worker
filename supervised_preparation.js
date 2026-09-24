/* Local planning arithmetic and draft download. No network or broker integration. */
"use strict";
const PilotPreparation = (() => {
  const scale = 100000000n;
  function decimal(value) {
    if (typeof value !== "string" || !/^\d{1,16}(\.\d{1,8})?$/.test(value.trim())) {
      throw new Error("Enter nonnegative decimal numbers (up to eight decimal places).");
    }
    const [whole, fraction = ""] = value.trim().split(".");
    return BigInt(whole) * scale + BigInt(fraction.padEnd(8, "0"));
  }
  function display(value) {
    const whole = value / scale;
    const fraction = (value % scale).toString().padStart(8, "0").replace(/0+$/, "");
    return whole.toString() + (fraction ? "." + fraction : "");
  }
  function calculate(input, limits) {
    const values = {};
    for (const key of ["entry", "stop", "target", "budget", "loss", "trades"]) values[key] = decimal(input[key]);
    const {entry, stop, target, budget, loss, trades} = values;
    if (!["LONG", "SHORT"].includes(input.direction)) throw new Error("Choose a direction.");
    if ([entry, stop, target, budget].some(v => v <= 0n)) throw new Error("Prices and risk budget must be positive.");
    if (trades % scale) throw new Error("Executed trade count must be a whole number.");
    if (budget > decimal(limits.max_risk)) throw new Error("Chosen risk exceeds the ruleset ceiling.");
    const risk = input.direction === "LONG" ? entry - stop : stop - entry;
    const reward = input.direction === "LONG" ? target - entry : entry - target;
    if (risk <= 0n || reward <= 0n) throw new Error("Stop and target must be on the correct sides of entry.");
    const blockers = [];
    if (loss >= decimal(limits.max_daily_loss)) blockers.push("Daily loss ceiling reached.");
    if (trades >= decimal(limits.max_trades)) blockers.push("Daily executed-trade ceiling reached.");
    if (reward * scale < decimal(limits.minimum_rr) * risk) blockers.push("Planned reward/risk is below 1.5R.");
    const riskQty = budget / risk;
    const notionalQty = decimal(limits.max_notional) / entry;
    const quantity = riskQty < notionalQty ? riskQty : notionalQty;
    if (quantity <= 0n) blockers.push("No whole share fits the chosen risk and notional ceilings.");
    const result = {
      classification: "PLANNING_ARITHMETIC_ONLY", eligible_for_handoff: false, execution_enabled: false,
      risk_per_share: display(risk), reward_per_share: display(reward),
      planned_rr_truncated_8dp: display(reward * scale / risk),
      blockers, current_approval: "NOT_ESTABLISHED",
      clean_structure_review_required: reward * scale >= decimal(limits.minimum_rr) * risk &&
                                      reward * scale < decimal(limits.preferred_rr) * risk,
      planning_quantity: blockers.length ? null : quantity.toString(),
      planned_dollar_risk: blockers.length ? null : display(quantity * risk),
      planned_notional: blockers.length ? null : display(quantity * entry)
    };
    return result;
  }
  function planningDraft(report, candidateIndex, input, reviewer, notes, savedAt) {
    if (!Number.isInteger(candidateIndex) || !report.candidates[candidateIndex]) throw new Error("Select a candidate.");
    if (!reviewer.trim() || !notes.trim()) throw new Error("Add your name, data source/timestamp and review notes.");
    if (!Number.isFinite(Date.parse(savedAt))) throw new Error("Invalid draft timestamp.");
    const candidate = report.candidates[candidateIndex];
    return {schema_version: 1, classification: "HUMAN_PLANNING_DRAFT", source_experiment_class: report.experiment_class,
      eligible_for_handoff: false, execution_enabled: false, journaled: false, trigger_confirmation: "NOT_ESTABLISHED",
      preparation_id: report.preparation_id, implementation_version: report.implementation_version,
      source_snapshot_digest: report.source_snapshot_digest, source_captured_at: report.source_captured_at,
      source_context: report.source_context, session_date: report.session_date,
      symbol: candidate.symbol, trace: {...candidate.trace}, packet_id: candidate.packet_id,
      entered_by: reviewer.trim(), recorded_at: savedAt, notes: notes.trim(), inputs: {...input},
      arithmetic: calculate(input, report.risk_limits)};
  }
  return {calculate, planningDraft};
})();
if (typeof module !== "undefined") module.exports = PilotPreparation;

if (typeof document !== "undefined") {
  const report = JSON.parse(document.getElementById("preparation-data").textContent);
  const byId = id => document.getElementById(id);
  const keys = ["direction", "entry", "stop", "target", "budget", "loss", "trades"];
  const inputs = () => Object.fromEntries(keys.map(key => [key, byId(key).value]));
  const show = value => {
    byId("calculation").textContent = typeof value === "string" ? value : [
      "Planning figures only — no trade approval.",
      "Risk per share: $" + value.risk_per_share,
      "Reward per share: $" + value.reward_per_share,
      "Planned reward/risk: approximately " + value.planned_rr_truncated_8dp + "R",
      ...(value.blockers.length ? ["Blocked:", ...value.blockers] : [
        "Planning quantity: " + value.planning_quantity + " whole shares",
        "Planned dollar risk: $" + value.planned_dollar_risk,
        "Planned position value: $" + value.planned_notional]),
      ...(value.clean_structure_review_required ? ["Explicit clean-structure review required for 1.5–2R."] : []),
      "Data, setup, target, confirmation and account state still require live review."
    ].join("\n");
  };
  const saveButton = byId("save-plan");
  for (const [index, candidate] of report.candidates.entries()) {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = candidate.symbol + " · record " + (index + 1);
    byId("candidate").appendChild(option);
  }
  function invalidate() {
    saveButton.disabled = true;
    show("Inputs changed. Recalculate before saving a draft.");
    byId("save-status").textContent = "Unsaved planning inputs. No approval or Journal write.";
  }
  for (const key of [...keys, "reviewer", "notes"]) byId(key).addEventListener("input", invalidate);
  byId("candidate").addEventListener("change", () => {
    // Avoid carrying another symbol's stop/target, notes or account assumptions across selections.
    for (const key of [...keys, "notes"]) byId(key).value = "";
    invalidate();
  });
  byId("calculate").addEventListener("click", () => {
    saveButton.disabled = true;
    try {
      if (byId("candidate").value === "") throw new Error("Select a candidate.");
      const result = PilotPreparation.calculate(inputs(), report.risk_limits);
      show(result);
      saveButton.disabled = false; // Failed arithmetic may still be preserved as an explicit blocked draft.
    } catch (error) { show(error.message); }
  });
  function download(value, name) {
    const blob = new Blob([JSON.stringify(value, null, 2) + "\n"], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  saveButton.addEventListener("click", () => {
    try {
      if (byId("candidate").value === "") throw new Error("Select a candidate.");
      const draft = PilotPreparation.planningDraft(report, Number(byId("candidate").value), inputs(),
        byId("reviewer").value, byId("notes").value, new Date().toISOString());
      download(draft, "planning-draft-" + draft.recorded_at.replace(/[:.]/g, "-") + ".json");
      byId("save-status").textContent = "Download requested. Confirm the file was saved. This is not an approval or Journal entry.";
    } catch (error) { byId("save-status").textContent = error.message; }
  });
  byId("save-journal").addEventListener("click", () => download({
    classification: "JOURNAL_DRAFT_ONLY", preparation_id: report.preparation_id,
    source_snapshot_digest: report.source_snapshot_digest, implementation_version: report.implementation_version,
    source_context: report.source_context, experiment_class: report.experiment_class,
    ...report.journal_draft
  }, "journal-draft-" + report.preparation_id + ".json"));
  const filter = () => {
    const query = byId("filter").value.trim().toUpperCase(); let shown = 0;
    for (const card of document.querySelectorAll(".candidate")) {
      card.hidden = !report.candidates[Number(card.dataset.index)].symbol.toUpperCase().includes(query);
      if (!card.hidden) shown++;
    }
    byId("shown").textContent = shown + " of " + report.candidates.length + " candidates shown. Filtering does not remove records.";
  };
  byId("filter").addEventListener("input", filter); filter();
}
