# Fallback and resilience

| Mechanism | Rule (plan) | Code | Test evidence |
|---|---|---|---|
| Data-class filter | merchant data → approved providers only | gateway.candidates | test_merchant_data_never_goes_to_unapproved_provider, test_no_approved_provider_queues_not_leaks |
| Backup admission | backup used only if admitted | candidates (i>0 and not admitted → skip) | test_unadmitted_backup_skipped |
| Breaker | open at 3 consecutive or >40% of last 50; probe 60 s; close after 2 | resilience.Breaker | test_breaker_open_probe_close, test_breaker_ratio_trip |
| Quota | bucket per model, header-fed, 30% interactive reserve | resilience.Bucket | test_quota_exhaustion_shifts_and_batch_respects_reserve |
| Triggers | 429/402/5xx/404/410/timeout/network; empty; truncated; bad JSON (1 repair); wrong language; CoT leak; invented number | providers.classify, validators.check | test_provider_errors_fail_over (6), test_http_classification (12), test_bad_output_rejected_then_fallback (4), test_json_repair_* , test_invented_numbers_rejected |
| Budgets | total 8/30/90 s | registry.TOTAL_S → httpx timeout | covered by timeout classification; first-token budget needs streaming (not built) |
| Hedging | interactive: backup starts at primary p90 | gateway._hedged | test_hedging_backup_wins_when_primary_slow |
| Safety | missing verdict fails closed; block → regen once → queue | gateway._deliver | test_safety_missing_fails_closed, test_safety_block_regenerates_once_then_queues |
| Judge | shadow until calibrated | registry.JUDGE_ENFORCED=False | not wired (shadow = not called) |
| Never-error ladder | live → last valid dated → queued 1/5/15 → NOT COMPUTED | gateway._ladder | test_all_fail_last_valid_then_queue_then_not_computed |
| Trace row | role, class, provider, model, attempt, trigger, latency, tokens, validation | gateway._attempt | test_trace_rows_complete_and_secret_free |

Gaps: no streaming (first-token budget), no queue worker executing jobs, no nightly precompute, no safety model call wired, 400/413/422 fall over instead of "fix request" (they're counted as failures and the next model is tried).
