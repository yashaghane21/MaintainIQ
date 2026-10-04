"""Deterministic DEMO analysis provider (no AI model involved).

Lets reviewers exercise the full workflow without an API key. Output is
always labelled `is_simulated=True` in the API and UI. It follows the same
rules as the live model: hypotheses only, citations only to evidence that
exists in the catalogue, confidence never "high".
"""

import re

from app.schemas.analysis import AIAnalysisOutput
from app.services.ai_service import AIRunResult

# (keywords, cause, reasoning, inspection step, related sensors)
_CAUSE_LIBRARY: dict[str, list[tuple[tuple[str, ...], str, str, str, tuple[str, ...]]]] = {
    "pump": [
        (("vibration", "vibrat", "rattle", "grinding", "bearing", "noise", "noisy"),
         "Bearing wear or lubrication breakdown",
         "Reported vibration/noise symptoms are commonly associated with bearing degradation.",
         "Inspect pump bearings: check lubricant condition and level, feel/listen for roughness, compare housing temperature.",
         ("vibration", "temperature")),
        (("misalign", "coupling", "after maintenance", "realign", "vibration", "motor replaced"),
         "Shaft misalignment or loose coupling",
         "Vibration that appears after maintenance or coupling work can indicate misalignment.",
         "Check shaft alignment and coupling condition/bolt torque with the pump isolated.",
         ("vibration",)),
        (("cavitation", "gravel", "crackling", "suction", "flow drop", "low flow", "inlet", "strainer"),
         "Cavitation from insufficient suction head or a blocked inlet strainer",
         "Crackling noise and reduced flow are typical cavitation indicators.",
         "Inspect suction strainer and inlet valve position; verify suction pressure against the manual.",
         ("pressure", "vibration")),
        (("leak", "seal", "drip", "puddle", "water on floor"),
         "Mechanical seal wear",
         "Visible leakage near the shaft suggests seal face wear or damage.",
         "Inspect mechanical seal area for leakage rate and seal face damage.",
         ()),
        (("hot", "overheat", "temperature", "smell"),
         "Overheating from inadequate lubrication or operation against a closed discharge",
         "Elevated temperature can result from lubrication issues or dead-heading.",
         "Verify discharge valve position and lubrication; measure bearing housing temperature with a calibrated instrument.",
         ("temperature",)),
        (("pressure", "blocked", "valve", "restriction"),
         "Discharge restriction (partially closed valve or blockage)",
         "High discharge pressure may indicate a downstream restriction.",
         "Walk down the discharge line: valve positions, check valve, and any blockage.",
         ("pressure",)),
    ],
    "hvac": [
        (("not cooling", "warm", "cooling", "temperature", "hot"),
         "Low refrigerant charge or refrigerant leak",
         "Insufficient cooling with high supply temperature is consistent with low refrigerant charge.",
         "Have a certified technician check refrigerant pressures and inspect for leaks.",
         ("temperature", "pressure")),
        (("filter", "airflow", "dust", "weak air", "low air"),
         "Clogged air filter restricting airflow",
         "Restricted airflow reduces heat transfer and raises supply temperature.",
         "Inspect and replace air filters; check return air path for obstructions.",
         ("temperature",)),
        (("condenser", "coil", "dirty", "pressure", "trip", "high pressure"),
         "Condenser coil fouling or condenser fan fault causing high head pressure",
         "High refrigerant pressure and trips often follow poor condenser heat rejection.",
         "Inspect condenser coil cleanliness and confirm condenser fan operation.",
         ("pressure",)),
        (("noise", "vibration", "squeal", "belt", "fan", "rattle"),
         "Fan belt wear or fan bearing issue",
         "Squealing or vibration from the air handler is commonly belt- or bearing-related.",
         "Inspect fan belt tension/wear and fan bearings with power isolated.",
         ("vibration",)),
        (("cycling", "short cycle", "thermostat", "on and off"),
         "Control fault or short cycling",
         "Frequent start/stop behaviour can come from control or sensor faults.",
         "Review controller alarm log and thermostat/sensor calibration.",
         ()),
    ],
    "conveyor_motor": [
        (("overheat", "hot", "temperature", "trip", "overload"),
         "Motor overload from excessive belt tension or a jammed conveyor",
         "Overheating and overload trips commonly follow increased mechanical load.",
         "Check conveyor for jams and belt tension; compare motor current against nameplate.",
         ("temperature",)),
        (("vibration", "noise", "grinding", "bearing", "hum"),
         "Motor bearing wear",
         "Increasing vibration or grinding noise suggests bearing deterioration.",
         "Inspect motor bearings and lubrication; trend vibration readings.",
         ("vibration", "temperature")),
        (("misalign", "gearbox", "coupling", "vibration"),
         "Misalignment between motor and gearbox",
         "Misalignment produces vibration and accelerated bearing wear.",
         "Check motor-to-gearbox alignment and coupling condition.",
         ("vibration",)),
        (("breaker", "trip", "current", "phase", "voltage", "electrical"),
         "Electrical supply issue (phase imbalance or loose connection)",
         "Nuisance trips may result from supply imbalance or loose terminations.",
         "Have a qualified electrician check supply voltage balance and terminal tightness.",
         ()),
        (("slip", "belt", "speed", "slow"),
         "Drive belt slippage or worn pulley",
         "Reduced conveyor speed with normal motor operation suggests slippage.",
         "Inspect drive belt wear, tension and pulley lagging.",
         ()),
        (("burning", "smell", "smoke", "insulation"),
         "Winding insulation degradation",
         "A burning smell may indicate overheating windings or insulation breakdown.",
         "Isolate the motor and have insulation resistance tested by a qualified electrician.",
         ("temperature",)),
    ],
}

_URGENT_WORDS = ("smoke", "fire", "burning", "sparks", "shutdown", "shut down", "tripped", "trip")


def _matches(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for k in keywords if k in text)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower()))


class DemoProvider:
    name = "demo"
    model = "deterministic-demo-v1"
    is_simulated = True

    def generate(self, context: dict) -> AIRunResult:
        equipment = context["equipment"]
        issue = context["issue"]
        findings = context["threshold_findings"]
        catalogue = context["evidence_catalogue"]
        etype = equipment.get("equipment_type", "")

        events_text = " ".join(e["description"] for e in issue["operating_events"])
        alarm_sensors = {f["sensor"] for f in findings if f["severity"] in ("warning", "critical")}
        corpus = f"{issue['description']} {events_text} {issue.get('additional_context') or ''} {' '.join(alarm_sensors)}".lower()

        # Rank library causes by keyword hits (+ boost when a related sensor is alarming).
        scored = []
        for kw, cause, reasoning, step, sensors in _CAUSE_LIBRARY.get(etype, []):
            score = _matches(corpus, kw) + 2 * len(alarm_sensors.intersection(sensors))
            if score:
                scored.append((score, kw, cause, reasoning, step, sensors))
        scored.sort(key=lambda s: -s[0])
        top = scored[:3]

        manual_ev = [e for e in catalogue if e["evidence_type"] == "MANUAL"]
        user_ev = [e for e in catalogue if e["evidence_type"] == "USER_REPORT"]
        event_ev = [e for e in catalogue if e["evidence_type"] == "OPERATING_EVENT"]
        rule_ev = {e["metadata"].get("sensor"): e for e in catalogue
                   if e["evidence_type"] == "SENSOR_RULE" and e["metadata"].get("severity") in ("warning", "critical")}

        def cite(keywords: tuple[str, ...], sensors: tuple[str, ...]) -> list[str]:
            ids = []
            if user_ev and _matches(issue["description"].lower(), keywords):
                ids.append(user_ev[0]["evidence_id"])
            ids += [e["evidence_id"] for e in event_ev if _matches(e["excerpt"].lower(), keywords)]
            ids += [rule_ev[s]["evidence_id"] for s in sensors if s in rule_ev]
            # Cite a manual chunk only if it shares >= 2 symptom keywords (best overlap first).
            kw_words = {w for k in keywords for w in _words(k)}
            overlaps = sorted(((len(kw_words & _words(e["excerpt"])), e["evidence_id"]) for e in manual_ev), reverse=True)
            ids += [eid for n, eid in overlaps if n >= 2][:2]
            return list(dict.fromkeys(ids))

        causes, steps = [], []
        safety_manual = [e["evidence_id"] for e in manual_ev if re.search(r"lockout|tagout", e["excerpt"], re.I)][:1]
        steps.append({
            "step": "Apply lockout/tagout and confirm zero energy before any hands-on inspection.",
            "reason": "Standard isolation practice before inspecting rotating or pressurised equipment.",
            "evidence_ids": safety_manual,
        })
        for _, kw, cause, reasoning, step, sensors in top:
            evidence_ids = cite(kw, sensors)
            has_rule = any(s in rule_ev for s in sensors)
            has_manual = any(e.startswith("E-DOC") for e in evidence_ids)
            causes.append({
                "cause": cause,
                "reasoning": reasoning + " This is a hypothesis to verify, not a diagnosis.",
                "confidence": "medium" if (has_rule and has_manual) else "low",
                "evidence_ids": evidence_ids,
            })
            steps.append({"step": step, "reason": f"Tests the hypothesis: {cause.lower()}.", "evidence_ids": evidence_ids})

        if not causes:
            causes.append({
                "cause": "Undetermined - insufficient information to form a specific hypothesis",
                "reasoning": "The report did not match known symptom patterns for this equipment type.",
                "confidence": "low",
                "evidence_ids": [user_ev[0]["evidence_id"]] if user_ev else [],
            })
            steps.append({"step": "Perform a general visual and auditory inspection and record readings for all sensors.",
                          "reason": "Gather data needed to form hypotheses.", "evidence_ids": []})

        # Follow-up questions from gaps in the data.
        questions = []
        for f in findings:
            if f["status"] == "missing":
                questions.append(f"Can you provide a current {f['sensor'].replace('_', ' ')} reading?")
            elif f["is_stale"]:
                questions.append(f"The {f['sensor'].replace('_', ' ')} reading is stale - can you take a fresh measurement?")
            elif f["status"] == "conflict":
                questions.append(f"{f['sensor'].capitalize()} readings disagree - which sensor/instrument is calibrated?")
            elif f["status"] in ("invalid", "unsupported_unit"):
                questions.append(f"The {f['sensor'].replace('_', ' ')} value could not be evaluated - can you re-check the sensor and unit?")
        questions += ["When did the symptom first appear, and is it constant or intermittent?",
                      "Was any maintenance, part replacement or process change performed recently?"]

        highest = context["highest_rule_severity"]
        urgent = any(w in corpus for w in _URGENT_WORDS)
        if highest == "critical":
            priority, why = "high", "A deterministic rule reported a critical threshold exceedance."
        elif urgent:
            priority, why = "high", "The report mentions trips, shutdowns or burning/smoke indicators."
        elif highest == "warning":
            priority, why = "medium", "A deterministic rule reported a warning threshold exceedance."
        else:
            priority, why = "low", "No threshold exceedances were reported; symptoms should still be verified."

        observations = [f"Reported: {issue['description']}"]
        observations += [f"Operating event: {e['description']}" for e in issue["operating_events"]]
        observations += [f"Rule finding ({f['severity']}): {f['explanation']}" for f in findings if f["status"] in ("evaluated", "conflict")]

        limitations = ["SIMULATED ANALYSIS: produced by the deterministic demo provider, not by an AI model.",
                       "Possible causes are unconfirmed hypotheses and require technician verification."]
        missing = [f["sensor"] for f in findings if f["status"] == "missing"]
        if missing:
            limitations.append(f"Missing readings ({', '.join(missing)}) were not evaluated.")
        if context["retrieval_status"] != "ok":
            limitations.append(f"Manual retrieval: {context['retrieval_message']}")

        top_cause = causes[0]["cause"]
        output = {
            "summary": (f"{equipment['name']} ({equipment['equipment_id']}): {issue['description'][:220]} "
                        f"Rule engine highest severity: {highest}. Leading hypothesis: {top_cause.lower()}."),
            "observations": observations[:25],
            "possible_causes": causes,
            "follow_up_questions": list(dict.fromkeys(questions))[:8],
            "inspection_steps": steps[:15],
            "suggested_priority": priority,
            "priority_reason": why,
            "work_order": {
                "title": f"Inspect {equipment['equipment_id']}: {top_cause}"[:160],
                "description": (f"Triage draft for {equipment['name']} ({equipment['equipment_id']}). "
                                f"Reported symptom: {issue['description'][:600]} "
                                "Verify the hypotheses below; none are confirmed."),
                "checklist": [s["step"] for s in steps][:25],
            },
            "limitations": limitations,
        }
        return AIRunResult(AIAnalysisOutput.model_validate(output), self.name, self.model, True)
