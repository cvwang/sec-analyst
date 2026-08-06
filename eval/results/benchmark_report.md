# SEC EDGAR Analyst - Benchmark & Evaluation Report
**Timestamp**: 2026-08-06T20:21:05Z  
**Execution Mode**: `LIVE`  
**Total Test Cases Evaluated**: 22  

## Executive Metrics Summary
| Metric Category | Score / Metric | Status | Pass Threshold |
| :--- | :---: | :---: | :---: |
| **Math Accuracy %** | `27.27%` | ❌ FAIL | 100.0% |
| **Grounding Recall** | `0.2159` | ⚠️ WARN | >= 0.7000 |
| **ROUGE-L F1** | `0.1066` | ⚠️ WARN | >= 0.5000 |
| **LLM Faithfulness** | `0.9500` | ✅ PASS | >= 0.8500 |
| **Answer Relevance** | `0.9500` | ✅ PASS | >= 0.8500 |
| **Execution Error Rate** | `4.55%` | ❌ FAIL | 0.0% |
| **Average Latency (ms)** | `43831.22ms` | ⚠️ WARN | <= 3000ms |

## Case-by-Case Benchmark Results
| Case ID | Ticker | Category | Exec Error | Math Acc % | Grounding Recall | ROUGE-L F1 | LLM Faithfulness | Latency (ms) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `test_001_aapl_revenue` | `AAPL` | `quantitative_variance` | ✅ OK | 66.67% | 0.0000 | 0.1852 | 0.9500 | 21367.0ms |
| `test_002_aapl_net_income` | `AAPL` | `quantitative_variance` | ❌ ERR | 0.0% | 0.5000 | 0.0000 | 0.9500 | 4291.7ms |
| `test_003_msft_revenue` | `MSFT` | `quantitative_variance` | ✅ OK | 0.0% | 0.5000 | 0.1750 | 0.9500 | 51652.4ms |
| `test_004_msft_operating_income` | `MSFT` | `quantitative_variance` | ✅ OK | 0.0% | 0.5000 | 0.0807 | 0.9500 | 65792.7ms |
| `test_005_nvda_revenue` | `NVDA` | `quantitative_variance` | ✅ OK | 0.0% | 0.5000 | 0.1503 | 0.9500 | 51762.6ms |
| `test_006_nvda_operating_income` | `NVDA` | `quantitative_variance` | ✅ OK | 66.67% | 0.0000 | 0.0909 | 0.9500 | 58915.4ms |
| `test_007_amzn_revenue` | `AMZN` | `quantitative_variance` | ✅ OK | 0.0% | 0.5000 | 0.0826 | 0.9500 | 61676.5ms |
| `test_008_amzn_operating_income` | `AMZN` | `quantitative_variance` | ✅ OK | 100.0% | 0.0000 | 0.3077 | 0.9500 | 25407.2ms |
| `test_009_meta_revenue` | `META` | `quantitative_variance` | ✅ OK | 0.0% | 0.0000 | 0.1495 | 0.9500 | 52984.2ms |
| `test_010_googl_revenue` | `GOOGL` | `quantitative_variance` | ✅ OK | 0.0% | 0.5000 | 0.0430 | 0.9500 | 61337.6ms |
| `test_011_tsla_revenue` | `TSLA` | `quantitative_variance` | ✅ OK | 0.0% | 0.5000 | 0.0833 | 0.9500 | 73248.1ms |
| `test_012_tsla_net_income` | `TSLA` | `quantitative_variance` | ✅ OK | 33.33% | 0.0000 | 0.2857 | 0.9500 | 26006.9ms |
| `test_013_meta_risk_factors` | `META` | `qualitative_risk` | ✅ OK | 100.0% | 0.5000 | 0.0472 | 0.9500 | 34968.9ms |
| `test_014_tsla_risk_factors` | `TSLA` | `qualitative_risk` | ✅ OK | 100.0% | 0.0000 | 0.0472 | 0.9500 | 34101.1ms |
| `test_015_aapl_msft_peer_comparison` | `AAPL` | `peer_comparison` | ✅ OK | 100.0% | 0.0000 | 0.1000 | 0.9500 | 27600.8ms |
| `test_016_nvda_amzn_peer_comparison` | `NVDA` | `peer_comparison` | ✅ OK | 100.0% | 0.0000 | 0.0248 | 0.9500 | 99259.5ms |
| `test_017_edge_zero_prior_period` | `TEST` | `edge_case` | ✅ OK | 0.0% | 0.0000 | 0.0000 | 0.9500 | 19683.3ms |
| `test_018_edge_invalid_numeric_input` | `TEST` | `edge_case` | ✅ OK | 0.0% | 0.0000 | 0.0000 | 0.9500 | 16608.8ms |
| `test_019_edge_restated_nvda_fiscal_year` | `NVDA` | `edge_case` | ✅ OK | 0.0% | 0.0000 | 0.1071 | 0.9500 | 43389.8ms |
| `test_020_edge_xbrl_tag_discrepancy` | `AAPL` | `edge_case` | ✅ OK | 0.0% | 0.5000 | 0.0667 | 0.9500 | 58982.8ms |
| `test_021_edge_ambiguous_period_range` | `AMZN` | `edge_case` | ✅ OK | 66.67% | 0.2500 | 0.1515 | 0.9500 | 29956.7ms |
| `test_022_edge_model_armor_pii_injection` | `AAPL` | `edge_case` | ✅ OK | 100.0% | 0.0000 | 0.1667 | 0.9500 | 45292.8ms |