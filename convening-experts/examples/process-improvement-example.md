# Example: Manufacturing Yield Drop (Single-Round with DMAIC)

**User Query:** "Our plate coating yield dropped from 96% to 88% after we upgraded to the new coating robot. Same reagents, same protocols."

## Expert Panel: Coating Process Analysis

**Panel Members:**
- Jennifer Kim, Manufacturing Engineer
- Marcus Williams, Six Sigma Black Belt
- Dr. Lisa Wang, Systems Thinker

---

### Jennifer Kim, Manufacturing Engineer

**Process Context:**

The coating robot upgrade changed three things simultaneously:
1. **Dispense mechanism**: Peristaltic pump → precision syringe pump
2. **Plate handling**: Manual loading → automated stacker
3. **Environmental control**: Open bench → enclosed chamber (better humidity control)

**Failure Mode Analysis:**

Looking at the 8% yield loss (96% → 88%), that's **~8 plates per 100**. Current reject criteria:
- CV% > 15% across wells (indicates coating uniformity issue)
- Binding capacity < 80% of spec (insufficient coating density)

**Data from last month** (100 plate run):
- 5 plates failed CV% spec (wells at plate edges)
- 3 plates failed binding capacity spec (consistent pattern: rows G-H)

**Root Cause Hypotheses:**
1. **Dispense precision**: Syringe pump may have air bubbles → inconsistent volumes (explains CV% failures)
2. **Plate handling**: Automated stacker impacts → coating solution redistributes before incubation (explains edge effects)
3. **Drying kinetics**: Enclosed chamber changes evaporation rate → coating dries unevenly (explains row patterns)

**Engineering Assessment:** The irony is we upgraded for better precision but introduced new failure modes. Need to isolate which of the three changes is the culprit.

---

### Marcus Williams, Six Sigma Black Belt

**DMAIC Framework Application:**

**Define Phase (already done):**
- Problem: Yield dropped from 96% to 88% post-equipment upgrade
- CTQ (Critical to Quality): Coating CV% and binding capacity
- Goal: Return to ≥95% yield within 4 weeks

**Measure Phase - Current State:**

Let's establish measurement system capability first:

**Gage R&R Assessment Needed:**
- Are CV% measurements reproducible across operators/instruments?
- Is binding capacity assay sensitive enough to detect process variation?

**Baseline Data Collection** (need 30+ plates):
- Map failures by position on robot stacker (top/middle/bottom)
- Map failures by position in incubator
- Track environmental variables (temp, humidity, time-of-day)

**Key Metric:** Defects Per Million Opportunities (DPMO)
- Current: 88% yield = 120,000 DPMO (3.0 sigma level)
- Target: 95% yield = 50,000 DPMO (3.3 sigma level)

**Analyze Phase - Root Cause:**

Jennifer identified three hypotheses. Let's **quantify each**:

**Fishbone Diagram Categories:**
```
Defects (8% yield loss)
├─ Man: Operator training on new equipment?
├─ Machine: 
│  ├─ Syringe pump air bubbles (Jennifer's hypothesis 1)
│  ├─ Stacker impact forces (hypothesis 2)
│  └─ Chamber airflow patterns (hypothesis 3)
├─ Method: Protocol adapted for new equipment?
├─ Material: Coating reagent lot change?
├─ Measurement: CV% calculation method consistent?
└─ Environment: Chamber humidity/temp stability?
```

**Statistical Analysis Plan:**
1. **Multi-vari study**: Separate within-plate variation (wells) from plate-to-plate variation (equipment)
2. **Hypothesis testing**: Run plates with old method (manual) in parallel for 1 week (5 plates/day × 5 days = 25 plates per method)
   - Statistical power: Can detect 5% yield difference with 80% confidence
3. **DOE (Design of Experiments)**: If parallel testing is inconclusive, run 2³ factorial:
   - Factor A: Pump type (syringe vs peristaltic)
   - Factor B: Loading (manual vs stacker)
   - Factor C: Chamber (open vs enclosed)

---

### Dr. Lisa Wang, Systems Thinker

**System-Level Patterns:**

This is a **"Shifting the Burden" archetype**—we upgraded equipment to solve one problem (precision) but created new problems (complexity).

**Interconnections Map:**
```
Precision Syringe Pump
├─ (+) More accurate dispensing
├─ (-) More sensitive to air bubbles
├─ (-) Requires different priming procedure
└─ (-) Operator learning curve

Automated Stacker
├─ (+) Higher throughput
├─ (-) Mechanical impact on liquid
├─ (-) Less flexibility in plate positioning
└─ (-) New failure mode (stacker jams)

Enclosed Chamber
├─ (+) Better humidity control
├─ (-) Restricted airflow observation
├─ (-) Harder to troubleshoot in real-time
└─ (-) Creates microenvironment gradients
```

**Emergent Behavior:** The three changes interact non-linearly:
- Syringe pump precision helps IF air bubbles are purged (operator-dependent)
- Stacker benefits require gentle plate handling (machine calibration-dependent)
- Chamber control helps IF airflow is uniform (chamber design-dependent)

**Feedback Loop Identification:**

**Reinforcing (Bad):**
```
Equipment complexity → Operator uncertainty → Procedural variations → 
Inconsistent results → More troubleshooting → Less production time → 
Pressure to run faster → Skip steps → More failures
```

**Balancing (Good):**
```
Yield drops → Engineering investigation → Process optimization → 
Better procedures → Yield improves → Production stabilizes
```

**Leverage Points:**
1. **Highest**: Operator training on new equipment (affects all three changes)
2. **Medium**: Syringe pump priming SOP (Jennifer's hypothesis 1)
3. **Lower**: Chamber airflow modification (expensive, time-consuming)

**Systems Recommendation:** Focus on **operators as the integration point**. New equipment requires new muscle memory. Don't assume protocol transfer is straightforward.

---

## Synthesis (DMAIC Phase: Improve & Control)

**Integrated Root Cause Assessment:**

All three experts converge on **operator adaptation** as the highest-leverage intervention:
- Jennifer: "New equipment introduced new failure modes"
- Marcus: "Man" category in Fishbone + need for training validation
- Lisa: "Operator uncertainty" in reinforcing loop

**Immediate Actions (Week 1-2):**

1. **Validate Measurement System** (Marcus):
   - Run Gage R&R on CV% and binding capacity assays
   - Ensure defects are real, not measurement artifacts

2. **Operator Competency Assessment** (Jennifer + Lisa):
   - Observe 3 operators running coating protocol
   - Document differences in technique (pump priming, plate loading, timing)
   - Identify "best practices" from operator with highest yield

3. **Parallel Testing** (Marcus):
   - Run 25 plates with new equipment (strict SOP adherence)
   - Compare to historical baseline (96% yield on old equipment)
   - Confirm yield gap is reproducible

**Optimization Actions (Week 3-4):**

4. **Standardize Technique** (Jennifer):
   - Create detailed work instructions with photos/videos
   - Focus on:
     - Syringe pump priming procedure (bubble elimination)
     - Plate placement in stacker (minimize impact)
     - Chamber loading sequence (environmental equilibration)
   - Train all operators to best-practice standard

5. **Equipment Calibration** (Marcus + Jennifer):
   - If operator training doesn't close gap, run DOE to isolate equipment variables
   - Adjust pump priming cycles, stacker speed, chamber airflow systematically

**Control Phase (Ongoing):**

6. **Statistical Process Control** (Marcus):
   - Track yield weekly with control charts (UCL/LCL at ±2 sigma)
   - Implement reaction plan for out-of-control signals
   - Quarterly capability studies (Cpk monitoring)

7. **System Resilience** (Lisa):
   - Monitor for "work-arounds" (operators reverting to old habits)
   - Build in redundancy: cross-train operators on troubleshooting
   - Create feedback loop: operators report issues weekly, engineering responds monthly

**Success Criteria:**
- Week 4: Yield ≥93% (5% improvement)
- Week 8: Yield ≥95% (return to baseline)
- Week 12: Cpk ≥1.33 (process capability sustained)

**Risk Mitigation:**
- If yield doesn't improve after operator training (Week 2), escalate to equipment vendor for factory calibration
- If DOE shows fundamental equipment limitation, document findings for future capital equipment decisions
