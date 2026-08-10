# PNCE full-text recoding schema (12 variables)

Recode each reviewed source from its cached full text at
`bib_audit/fulltext_cache/<ID>.txt`. Every coded value must be supported by a
locator taken from that text (section number, table number, figure number, or
page number printed in the text). Never infer a value from the title, the
abstract alone, or from outside knowledge.

## Allowed values

| Variable | Field name | Allowed values |
|---|---|---|
| P1 Application | `p1_application` | `irrigation_outdoor`, `greenhouse_microclimate`, `hydroponic_cea`, `ncs_generic_nonagricultural`, `not_stated` |
| P2 Dynamics model | `p2_dynamics_model` | `first_order`, `higher_order`, `nonlinear`, `data_driven`, `none_stated`, `not_applicable` |
| P3 Time constant | `p3_time_constant` | free text with unit, or `not_stated` |
| N1 Protocol | `n1_protocol` | `LoRa_LoRaWAN`, `ZigBee_802154`, `WiFi`, `NB_IoT_cellular`, `Ethernet_wired`, `mixed`, `none_no_network`, `not_stated` |
| N2 Latency | `n2_latency` | free text with unit, or `not_stated` |
| N3 Packet loss | `n3_packet_loss` | free text with unit, or `not_stated` |
| C1 Strategy | `c1_strategy` | `on_off_threshold`, `PID`, `Fuzzy`, `MPC`, `RL_ML`, `ETC_event_triggered`, `STC_self_triggered`, `optimal_control`, `hybrid`, `none_monitoring_only`, `not_stated` |
| C2 Trigger | `c2_trigger` | `time_triggered`, `event_triggered`, `self_triggered`, `adaptive`, `manual_remote`, `not_stated` |
| C3 Architecture | `c3_architecture` | `cloud`, `edge_local`, `hybrid_cloud_edge`, `standalone_embedded`, `simulation_only`, `not_stated` |
| E1 Control quality | `e1_control_quality` | free text with metric and unit, or `not_reported` |
| E2 Network resource | `e2_network_resource` | free text with metric and unit, or `not_reported` |
| E3 Energy | `e3_energy` | free text with metric and unit, or `not_reported` |

## Additional required fields

- `evidence_type`: one of `field_deployment`, `greenhouse_or_plot_experiment`,
  `lab_prototype_or_HIL`, `simulation_only`, `mixed_experiment_and_simulation`.
- `has_closed_loop_actuation`: `yes`, `partial`, `no`.
- `comparator_present`: `concurrent_experimental`, `within_model_comparison`,
  `literature_or_design_comparison`, `none`.
- `article_type_flag`: `primary_study`, `primary_with_review_framing`,
  `secondary_review`. Use the publisher's own article-type label when the text
  shows one, and say so in the locator.
- `locators`: object mapping each coded field name to its supporting locator
  string. Any field whose value is not `not_stated`/`not_reported`/
  `not_applicable` MUST have a locator.
- `corrections_vs_title_coding`: short note on where the full text contradicts
  the earlier title-based coding, or `none`.

## Output

Write one JSON file to `bib_audit/pnce_recode/<batch>.json`:

```json
{"records": [ { "id": "S02", "p1_application": "...", ... } ]}
```

Do not modify any other file.
