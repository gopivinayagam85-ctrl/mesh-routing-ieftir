# Control-Plane Overhead Model — Independent Implementation Audit

**Date:** 2026-10-11
**Auditor:** Automated independent recalculation from raw data
**Scope:** Verify [`control_plane_benchmark.json`](file:///c:/Project%20files/mesh-routing-research/research_results/control_plane_audit/control_plane_benchmark.json) against [`control_plane_report.md`](file:///c:/Project%20files/mesh-routing-research/research_results/control_plane_audit/control_plane_report.md)
**Engine:** [`backend/engine.py`](file:///c:/Project%20files/mesh-routing-research/backend/engine.py)
**Benchmark runner:** [`backend/run_control_plane_benchmark.py`](file:///c:/Project%20files/mesh-routing-research/backend/run_control_plane_benchmark.py)
**Verified Dataset:** [`research_results/control_plane_audit/control_plane_verified_results.json`](file:///c:/Project%20files/mesh-routing-research/research_results/control_plane_audit/control_plane_verified_results.json)

---

## 1. Test Suite Outcome

```text
============================= test session starts =============================
platform win32 -- Python 3.10.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Project files\mesh-routing-research
collected 55 items

backend/test_api.py ....................                                 [ 18%]
backend/test_connectivity.py ....                                        [ 25%]
backend/test_connectivity_extended.py ....                               [ 32%]
backend/test_engine.py ...                                               [ 38%]
backend/test_incremental.py ..............                               [ 63%]
backend/test_routing.py .......                                          [ 76%]
backend/test_simulation.py ............                                  [ 96%]
backend/tests/test_compare_stats.py .                                    [ 98%]
backend/tests/test_compare_stats_extended.py .                           [100%]

============================== 55 passed in 0.97s ==============================
PYTEST_EXIT_CODE=0
```

All 55 tests pass, recorded in [`control_plane_validation_tests.txt`](file:///c:/Project%20files/mesh-routing-research/research_results/control_plane_audit/control_plane_validation_tests.txt).

---

## 2. Raw Data Inventory

| Item | Claimed | Verified |
|:---|:---:|:---:|
| Total raw runs | 180 | **180** (3 scenarios x 3 algorithms x 20 seeds) |
| Scenarios defined | 3 | **3** |
| Summary rows | 9 | **9** (3 scenarios x 3 algorithms) |
| Paired comparisons (`energy − incremental`) | 3 | **3** (one per scenario) |
| Paired comparisons (`shortest − incremental`) | 3 | **3** (one per scenario, independently computed) |
| Sensitivity profiles | 3 | **3** |

**Verdict:** Raw run records match metadata exactly.

---

## 3. Recalculated Means vs. JSON Summaries

Every mean and standard deviation in the JSON `summaries` array was independently recalculated from the 180 raw run records using `sum(vals)/n` for mean and sample standard deviation `sqrt(sum((x-xbar)^2)/(n-1))`.

**Result: Zero discrepancy.** All 54 mean values and all 54 standard deviation values in the JSON match the recalculated values to 6+ decimal places. The benchmark runner's use of `np.mean()` and `np.std(ddof=1)` is numerically correct.

---

## 4. Paired Comparison Verification

Both baseline comparisons (`energy − incremental` and `shortest − incremental`) were independently calculated from the matching seed pairs ($n=20$ seeds per scenario). These are separate, distinct comparisons and must not be substituted for one another.

### 4.1 Comparison 1: `energy − incremental`

| Scenario | Metric | calc mean_diff | calc std_diff | calc t | p-value | Reduction | Status |
|:---|:---|---:|---:|---:|:---:|---:|:---:|
| N=20 random | recomputations | 460.90 | 43.04 | 47.89 | $< 10^{-15}$ | 77.57% | Verified |
| N=20 random | ctrl_messages | 659.20 | 139.60 | 21.12 | $< 10^{-15}$ | 64.51% | Verified |
| N=20 random | ctrl_bytes | 21,100.00 B | 4,469.04 B | 21.11 | $< 10^{-15}$ | 65.02% | Verified |
| N=20 random | ctrl_energy | 292.57 J | 62.67 J | 20.88 | $< 10^{-15}$ | 64.05% | Verified |
| N=20 random | data_energy | -1.79 J | 6.63 J | -1.21 | 0.2278 | -0.41% | Verified |
| N=20 random | pdr | -0.0027 | 0.0096 | -1.28 | 0.2008 | -0.29% | Verified |
| N=20 artic. | recomputations | 462.40 | 48.18 | 42.92 | $< 10^{-15}$ | 77.38% | Verified |
| N=20 artic. | ctrl_messages | 635.20 | 117.02 | 24.28 | $< 10^{-15}$ | 63.23% | Verified |
| N=20 artic. | ctrl_bytes | 20,348.80 B | 3,753.97 B | 24.24 | $< 10^{-15}$ | 63.80% | Verified |
| N=20 artic. | ctrl_energy | 281.71 J | 52.94 J | 23.80 | $< 10^{-15}$ | 62.72% | Verified |
| N=20 artic. | data_energy | -3.17 J | 8.55 J | -1.66 | 0.0974 | -0.72% | Verified |
| N=20 artic. | pdr | -0.0005 | 0.0116 | -0.18 | 0.8580 | -0.05% | Verified |
| N=50 random | recomputations | 1,068.85 | 265.34 | 18.01 | $< 10^{-15}$ | 67.52% | Verified |
| N=50 random | ctrl_messages | 2,001.35 | 641.27 | 13.96 | $< 10^{-15}$ | 49.02% | Verified |
| N=50 random | ctrl_bytes | 64,029.60 B | 20,518.35 B | 13.96 | $< 10^{-15}$ | 49.12% | Verified |
| N=50 random | ctrl_energy | 858.90 J | 277.90 J | 13.82 | $< 10^{-15}$ | 48.91% | Verified |
| N=50 random | data_energy | -9.02 J | 14.95 J | -2.70 | 0.0070 | -1.35% | Verified |
| N=50 random | pdr | 0.0000 | 0.0000 | 0.00 | 1.0000 | 0.00% | Verified |

### 4.2 Comparison 2: `shortest − incremental`

| Scenario | Metric | calc mean_diff | calc std_diff | calc t | p-value | Reduction | Status |
|:---|:---|---:|---:|---:|:---:|---:|:---:|
| N=20 random | recomputations | 466.25 | 47.35 | 44.03 | $< 10^{-15}$ | 77.77% | Verified |
| N=20 random | ctrl_messages | 673.30 | 141.45 | 21.29 | $< 10^{-15}$ | 64.99% | Verified |
| N=20 random | ctrl_bytes | 21,435.20 B | 4,453.47 B | 21.52 | $< 10^{-15}$ | 65.38% | Verified |
| N=20 random | ctrl_energy | 298.71 J | 64.11 J | 20.84 | $< 10^{-15}$ | 64.53% | Verified |
| N=20 random | data_energy | -0.17 J | 9.94 J | -0.08 | 0.9401 | -0.04% | Verified |
| N=20 random | pdr | -0.0037 | 0.0113 | -1.45 | 0.1463 | -0.40% | Verified |
| N=20 artic. | recomputations | 465.40 | 54.94 | 37.89 | $< 10^{-15}$ | 77.49% | Verified |
| N=20 artic. | ctrl_messages | 653.40 | 142.91 | 20.45 | $< 10^{-15}$ | 63.88% | Verified |
| N=20 artic. | ctrl_bytes | 20,803.20 B | 4,499.27 B | 20.68 | $< 10^{-15}$ | 64.31% | Verified |
| N=20 artic. | ctrl_energy | 290.25 J | 64.85 J | 20.01 | $< 10^{-15}$ | 63.41% | Verified |
| N=20 artic. | data_energy | -0.55 J | 12.99 J | -0.19 | 0.8491 | -0.12% | Verified |
| N=20 artic. | pdr | 0.0016 | 0.0170 | 0.43 | 0.6697 | 0.18% | Verified |
| N=50 random | recomputations | 1,110.40 | 237.64 | 20.90 | $< 10^{-15}$ | 68.36% | Verified |
| N=50 random | ctrl_messages | 2,444.10 | 692.41 | 15.79 | $< 10^{-15}$ | 54.01% | Verified |
| N=50 random | ctrl_bytes | 77,901.60 B | 21,936.64 B | 15.88 | $< 10^{-15}$ | 54.02% | Verified |
| N=50 random | ctrl_energy | 1,047.47 J | 298.85 J | 15.67 | $< 10^{-15}$ | 53.86% | Verified |
| N=50 random | data_energy | -1.16 J | 29.49 J | -0.18 | 0.8609 | -0.17% | Verified |
| N=50 random | pdr | 0.0000 | 0.0000 | 0.00 | 1.0000 | 0.00% | Verified |

> [!IMPORTANT]
> `energy − incremental` and `shortest − incremental` are distinct comparisons:
> - In Scenario 1, control message reduction is **64.51%** vs. `energy` (+659.2 msgs) and **64.99%** vs. `shortest` (+673.3 msgs).
> - In Scenario 3 ($N=50$), control message reduction is **49.02%** vs. `energy` (+2,001.4 msgs) and **54.01%** vs. `shortest` (+2,444.1 msgs).
> Neither comparison may be substituted for the other.

---

## 5. Reporting Error in Original Markdown Tables: Standard Deviations

> [!CAUTION]
> The original markdown report [`control_plane_report.md`](file:///c:/Project%20files/mesh-routing-research/research_results/control_plane_audit/control_plane_report.md) contained **incorrect standard deviation ($\pm$) values** in Sections 4.1–4.3. The means were correct, but the reported standard deviations did not match the raw data.

### 5.1 Corrected Summary Statistics — Scenario 1: N=20, Random Failure

| Metric | `shortest` | `energy` | `incremental` |
|:---|:---:|:---:|:---:|
| **Routing Recomputations** | 599.50 $\pm$ **10.33** | 594.15 $\pm$ **15.84** | 133.25 $\pm$ **51.72** |
| **Control Messages Sent** | 1,035.95 $\pm$ **218.17** | 1,021.85 $\pm$ **228.37** | 362.65 $\pm$ **189.91** |
| **Control Bytes Sent (B)** | 32,786.40 $\pm$ **6,896.79** | 32,451.20 $\pm$ **7,246.36** | 11,351.20 $\pm$ **5,949.70** |
| **Control Energy (J)** | 462.94 $\pm$ **97.38** | 456.79 $\pm$ **101.32** | 164.23 $\pm$ **86.19** |
| **Data Energy (J)** | 441.79 $\pm$ **80.89** | 440.17 $\pm$ **76.92** | 441.96 $\pm$ **76.28** |
| **PDR** | 0.9314 $\pm$ **0.0115** | 0.9323 $\pm$ **0.0153** | 0.9351 $\pm$ **0.0176** |

### 5.2 Corrected Summary Statistics — Scenario 2: N=20, Articulation Cut Failure

| Metric | `shortest` | `energy` | `incremental` |
|:---|:---:|:---:|:---:|
| **Routing Recomputations** | 600.60 $\pm$ **7.69** | 597.60 $\pm$ **12.21** | 135.20 $\pm$ **55.62** |
| **Control Messages Sent** | 1,022.80 $\pm$ **202.66** | 1,004.60 $\pm$ **201.07** | 369.40 $\pm$ **193.13** |
| **Control Bytes Sent (B)** | 32,350.40 $\pm$ **6,410.97** | 31,896.00 $\pm$ **6,410.22** | 11,547.20 $\pm$ **6,098.42** |
| **Control Energy (J)** | 457.72 $\pm$ **90.34** | 449.18 $\pm$ **88.64** | 167.47 $\pm$ **86.74** |
| **Data Energy (J)** | 442.28 $\pm$ **75.31** | 439.66 $\pm$ **71.04** | 442.83 $\pm$ **74.79** |
| **PDR** | 0.9282 $\pm$ **0.0072** | 0.9262 $\pm$ **0.0043** | 0.9266 $\pm$ **0.0110** |

### 5.3 Corrected Summary Statistics — Scenario 3: N=50, Random Failure

| Metric | `shortest` | `energy` | `incremental` |
|:---|:---:|:---:|:---:|
| **Routing Recomputations** | 1,624.50 $\pm$ **46.52** | 1,582.90 $\pm$ **47.16** | 514.05 $\pm$ **259.29** |
| **Control Messages Sent** | 4,525.50 $\pm$ **1,715.89** | 4,082.75 $\pm$ **1,446.72** | 2,081.40 $\pm$ **1,314.93** |
| **Control Bytes Sent (B)** | 144,221.60 $\pm$ **54,755.24** | 130,349.60 $\pm$ **46,357.75** | 66,320.00 $\pm$ **42,117.39** |
| **Control Energy (J)** | 1,944.79 $\pm$ **731.39** | 1,756.21 $\pm$ **614.73** | 897.31 $\pm$ **561.69** |
| **Data Energy (J)** | 674.84 $\pm$ **158.07** | 666.97 $\pm$ **151.72** | 675.99 $\pm$ **160.71** |
| **PDR** | 0.6269 $\pm$ **0.0407** | 0.6269 $\pm$ **0.0407** | 0.6269 $\pm$ **0.0407** |

---

## 6. Sensitivity Analysis Verification

Units are explicitly labeled in bytes (**B**) and modeled energy in joules (**J**).

| Profile | Parameters | `energy` Mean Bytes (B) | `incremental` Mean Bytes (B) | Byte Reduction (%) | `energy` Mean Energy (J) | `incremental` Mean Energy (J) | Energy Reduction (%) | Msg Reduction (%) |
|:---|:---:|---:|---:|:---:|---:|---:|:---:|:---:|
| **Lightweight** | 16 B ctrl / 8 B notif / 0.3x | 16,610.40 B | **5,695.20 B** | **65.71%** | 280.07 J | **98.51 J** | **64.83%** | **65.25%** |
| **Standard** | 32 B ctrl / 16 B notif / 0.5x | 33,220.80 B | **11,390.40 B** | **65.71%** | 466.78 J | **164.18 J** | **64.83%** | **65.25%** |
| **Heavy** | 64 B ctrl / 32 B notif / 0.8x | 66,441.60 B | **22,780.80 B** | **65.71%** | 746.84 J | **262.68 J** | **64.83%** | **65.25%** |

- **Percentage reductions**: Identical across all three profiles for byte reduction (65.71%), energy reduction (64.83%), and message reduction (65.25%).
- **p-value formatting**: All control-plane paired tests yield $|t| > 13$, resulting in $p < 10^{-15}$, formatted as a defensible upper bound.

---

## 7. Model Formulas and Accounting Specifications

From [`backend/engine.py`](file:///c:/Project%20files/mesh-routing-research/backend/engine.py#L170-L184):

### 7.1 Control-Plane Transmission Energy Formula
$$E_{\text{ctrl}} = \kappa_{\text{ctrl}} \times \left[ C_{\text{tx}} \times (1 + d^2) + C_{\text{rx}} \right]$$

- $\kappa_{\text{ctrl}} = 0.5$ (default): Scaling factor reflecting reduced frame length and transmission duration relative to maximum transmission unit (MTU) data packets.
- $C_{\text{tx}} = 0.65\text{ J}$: Base transmitter circuit energy cost.
- $C_{\text{rx}} = 0.18\text{ J}$: Receiver circuit energy cost.
- $d$: Euclidean distance between transmitter and receiver in normalized coordinate space $[0, 1]^2$.

### 7.2 Accounting Rules
1. **Initial Setup (Round 0)**: All operational nodes advertise their active routes hop-by-hop toward the gateway.
2. **Subsequent Rounds**:
   - `shortest` and `energy`: Full recomputation triggered; all surviving nodes re-advertise complete paths network-wide.
   - `incremental`: Initial paths maintained; re-advertisement generated **only** when an active route traverses a failed or battery-depleted node. Unaffected routes transmit 0 control frames.
3. **Failure Notifications**: 1-hop active neighbors of any failed node broadcast a 16 B notification frame identically across all algorithms.

---

## 8. Verified Artifacts

1. [`control_plane_verified_results.json`](file:///c:/Project%20files/mesh-routing-research/research_results/control_plane_audit/control_plane_verified_results.json): Contains the complete independently recalculated summaries, paired comparisons for both `energy − incremental` and `shortest − incremental`, and sensitivity profiles.
2. [`control_plane_validation_tests.txt`](file:///c:/Project%20files/mesh-routing-research/research_results/control_plane_audit/control_plane_validation_tests.txt): Actual pytest execution transcript (55 passed, exit code 0).
3. [`control_plane_report.md`](file:///c:/Project%20files/mesh-routing-research/research_results/control_plane_audit/control_plane_report.md): Research report with corrected standard deviations, separate paired comparisons, and verified units.
