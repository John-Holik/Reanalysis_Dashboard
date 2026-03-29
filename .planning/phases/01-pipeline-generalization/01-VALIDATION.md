---
phase: 1
slug: pipeline-generalization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — no pytest.ini, no test/ directory. All validation is manual smoke-testing. |
| **Config file** | none |
| **Quick run command** | Manual: launch `streamlit run Reanalysis_Dashboard/app.py`, upload synthetic CSV, verify Step 0 renders |
| **Full suite command** | Manual end-to-end: upload synthetic CSV through all 5 wizard steps |
| **Estimated runtime** | ~5 minutes (manual) |

---

## Sampling Rate

- **After every task commit:** Manual — launch app, upload test CSV, verify Step 0 renders correctly
- **After every plan wave:** Full smoke-test — upload test CSVs and run full pipeline through all 5 steps
- **Before `/gsd:verify-work`:** Full end-to-end manual run must pass
- **Max feedback latency:** ~5 minutes (manual)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | REL-02 | unit | none — manual check that `build_model_df_generic()` exists in pipeline_bridge.py | ❌ no test file | ⬜ pending |
| 1-01-02 | 01 | 1 | UPLOAD-02 | unit | none — manual verify dropdowns show actual CSV columns | ❌ no test file | ⬜ pending |
| 1-02-01 | 02 | 2 | UPLOAD-01 | smoke | Manual — upload synthetic CSV; verify no "Missing required columns" error | ❌ no test file | ⬜ pending |
| 1-02-02 | 02 | 2 | UPLOAD-02 | smoke | Manual — verify dropdowns populated from uploaded CSV headers | ❌ no test file | ⬜ pending |
| 1-02-03 | 02 | 2 | UPLOAD-03 | smoke | Manual — verify 5-row st.dataframe preview renders immediately after upload | ❌ no test file | ⬜ pending |
| 1-03-01 | 03 | 3 | REL-02 | integration | Manual — run full pipeline with synthetic CSV `(timestamp, streamflow_cms)` and verify output CSVs contain `streamflow_cms` in filenames | ❌ no test file | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Create `tests/synthetic_model.csv` — synthetic non-Peace-River model CSV with columns `timestamp,streamflow_cms,nitrate_mgl`
- [ ] Create `tests/synthetic_obs.csv` — synthetic observation CSV with columns `obs_date,nitrate_value`

*Note: No automated test framework required for this phase. These are smoke-test data files only.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Model CSV upload does not reject non-Peace-River columns | UPLOAD-01 | No test framework; Streamlit UI requires browser interaction | Launch app, upload synthetic CSV with `timestamp,streamflow_cms` columns, verify Step 0 shows no "Missing required columns" error |
| Date and value dropdowns show uploaded CSV headers | UPLOAD-02 | Streamlit widget rendering requires browser | Upload synthetic CSV, verify dropdowns contain `timestamp` and `streamflow_cms`, not `["discharge", "TN", "TP"]` |
| 5-row preview renders inline on Step 0 | UPLOAD-03 | Streamlit widget rendering requires browser | Upload synthetic CSV, verify `st.dataframe` preview appears immediately below upload widget with 5 rows |
| Full pipeline completes without KeyError on synthetic CSV | REL-02 | End-to-end pipeline requires Streamlit session + TF runtime | Run complete 5-step wizard with synthetic CSVs; verify output files in results directory have `streamflow_cms` in filenames |

---

## Synthetic Test Data

Create these files before executing plans:

**`tests/synthetic_model.csv`**
```
timestamp,streamflow_cms,nitrate_mgl
2010-01-01 00:00:00,12.5,0.45
2010-01-01 06:00:00,13.1,0.48
2010-01-01 12:00:00,12.8,0.46
```

**`tests/synthetic_obs.csv`**
```
obs_date,nitrate_value
2010-01-15,0.47
2010-02-15,0.52
2010-03-15,0.44
```

---

## Validation Sign-Off

- [ ] All tasks have manual verification steps documented above
- [ ] Synthetic test CSVs created in tests/
- [ ] Wave 0 (test data creation) complete before Wave 1 execution begins
- [ ] No automated test stubs required (manual-only project scope)
- [ ] Full end-to-end smoke-test passes with synthetic CSVs
- [ ] `nyquist_compliant: true` set in frontmatter after sign-off

**Approval:** pending
