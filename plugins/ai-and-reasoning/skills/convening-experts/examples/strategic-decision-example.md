# Example: Build vs Buy Decision (Single-Round)

**User Query:** "Should we build internal ML infrastructure or use vendor solutions?"

## Expert Panel: ML Infrastructure Strategy

**Panel Members:**
- Dr. Sarah Chen, Software Architect
- James Morrison, McKinsey Consultant
- David Kumar, Finance Analyst
- Alexandra Torres, DevOps Engineer

---

### Dr. Sarah Chen, Software Architect

The technical decision hinges on three factors: customization needs, team capability, and long-term flexibility.

**Build Considerations:**
- Full control over model architecture and feature engineering
- Can optimize for MSD's specific assay data characteristics
- Integration with existing Python data pipelines (pandas, scikit-learn already in use)
- Team has Python/AWS expertise but limited ML ops experience

**Buy Considerations:**
- AWS SageMaker provides managed infrastructure we already use
- Reduces time-to-production by 6-9 months
- Built-in monitoring, versioning, A/B testing capabilities
- Risk: vendor lock-in, less control over model explainability (critical for FDA submissions)

**Hybrid Recommendation:** Start with SageMaker for rapid prototyping, build custom components only where regulatory explainability demands it.

---

### James Morrison, McKinsey Consultant

Let's structure this with a classic make-vs-buy framework, examining strategic fit and capability gaps.

**Issue Tree:**
```
ML Infrastructure Decision
├─ Strategic Importance
│  ├─ Core competency? (ECL assays = yes, ML infrastructure = no)
│  ├─ Competitive advantage source? (Unlikely—models matter, infra doesn't)
│  └─ Regulatory moat? (Possibly—explainability requirements)
├─ Capability Assessment
│  ├─ Current: Strong software eng, weak ML ops
│  ├─ Gap: Model deployment, monitoring, drift detection
│  └─ Build time: 12-18 months to production-grade
└─ Economics
   ├─ Build: High capex, low opex
   └─ Buy: Low capex, high opex (scales with usage)
```

**MECE Analysis:** The only defensible "build" argument is regulatory explainability requirements. Everything else favors vendor solutions.

**Recommendation:** Buy for infrastructure, build for domain-specific model components. This is a classic "partner on non-core capabilities" scenario.

---

### David Kumar, Finance Analyst

**5-Year TCO Comparison:**

**Build Option:**
- Year 1: $800K (3 ML engineers, AWS infrastructure)
- Years 2-5: $450K/year (maintenance, scaling)
- Total: $2.6M
- Risk: High upfront investment, 12-18 month delay to revenue

**Buy Option (SageMaker):**
- Year 1: $120K (training, inference, storage)
- Years 2-5: $180K/year (scales with model usage)
- Total: $840K
- Risk: Vendor dependency, potential price increases

**Break-Even Analysis:** Build becomes cost-competitive only if we deploy 50+ production models. Current roadmap shows 8-12 models over 3 years.

**IRR Impact:** Delayed launch (build scenario) costs $1.2M in opportunity cost (6-month market delay × $200K monthly revenue).

**Recommendation:** Buy for Phase 1 (3 years), revisit if model portfolio exceeds 30 models.

---

### Alexandra Torres, DevOps Engineer

**Operational Reality Check:**

**Current Infrastructure:**
- AWS ECS for containers, Jenkins for CI/CD
- No existing ML ops tooling (no MLflow, no model registry)
- On-call team of 4, already at capacity for production incidents

**Build Operational Cost:**
- New on-call rotation for ML infrastructure (+1.5 FTE)
- Model monitoring and drift detection systems (custom build = 6 months)
- Integration with existing observability stack (DataDog)
- Training required: team has limited Kubernetes/Kubeflow experience

**Buy Operational Benefits:**
- SageMaker integrates with existing AWS IAM, CloudWatch, ECS
- Managed endpoints eliminate infra on-call burden
- Built-in model registry, versioning, rollback

**The DevOps Concern:** Building means we own incident response for ML infra during regulatory audits. That's high-stakes operational risk with limited team depth.

**Recommendation:** Strong bias toward vendor solution to avoid operational overstretch.

---

## Synthesis (RAPID Framework)

**Recommend:** Start with AWS SageMaker for ML infrastructure, build custom explainability layer for regulatory compliance.

**Rationale:**
1. **Strategic:** ML infrastructure is not core competency (Chen, Morrison)
2. **Financial:** 3x cost advantage, faster time-to-revenue (Kumar)
3. **Operational:** Reduces operational burden on constrained team (Torres)
4. **Risk Mitigation:** Hybrid approach preserves regulatory control (Chen)

**Agree:** Engineering leadership, Finance, Quality/Regulatory

**Perform:**
- Platform team: SageMaker setup and integration
- ML team: Model development and explainability layer
- DevOps: Monitoring and deployment automation

**Input:**
- Regulatory: Explainability requirements review
- Customer Success: Model performance SLAs
- Security: Vendor risk assessment

**Decide:** VP Engineering (with CFO sign-off for budget)

**Implementation Roadmap:**
1. Month 1-2: SageMaker pilot with one non-critical model
2. Month 3-4: Build custom explainability wrapper for regulatory-critical models
3. Month 5-6: Production deployment with monitoring
4. Quarter 2: Evaluate model portfolio growth for build vs continue-buy decision
