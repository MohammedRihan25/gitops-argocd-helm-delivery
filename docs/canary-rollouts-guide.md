# Progressive Canary Delivery with Argo Rollouts

This guide details how progressive canary deployments eliminate deployment risk through automated metric validation.

---

## 1. Canary Traffic Steps

```text
[New Release v1.1.0 Triggered]
             │
             ▼
[Step 1: Set Weight 20%] ──> 20% traffic routed to Canary pods, 80% to Stable pods
             │
             ▼
[Step 2: Pause 3 Minutes] ──> Run automated Prometheus AnalysisTemplate
             │
             ├── If Error Rate < 1%: PROCEED TO STEP 3
             └── If Error Rate >= 1%: ABORT & INSTANT ROLLBACK TO STABLE
             │
             ▼
[Step 3: Set Weight 50%] ──> 50% traffic routed to Canary pods
             │
             ▼
[Step 4: Pause 5 Minutes] ──> Continuous health check
             │
             ▼
[Step 5: Set Weight 100%] ──> 100% traffic routed to v1.1.0, retire v1.0.0
```

---

## 2. Abort & Rollback Criteria
The `payment-success-rate-check` AnalysisTemplate queries Prometheus continuously:
```promql
sum(rate(payment_transactions_successful_total[2m])) 
/ 
(sum(rate(payment_transactions_total[2m])) > 0 or vector(1))
```
If the success rate drops below 99% during any step, Argo Rollouts halts traffic progression immediately and restores all traffic back to stable pods.
