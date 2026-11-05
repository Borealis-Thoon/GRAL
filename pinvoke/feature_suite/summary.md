| case | group | screen | A/B by type | GPU situations | wall s (cpu/gpu/native) |
|---|---|---|---|---|---|
| transient_area | control | pass | con=1.82e-04 | 12 | 20.61/4.31/20.54 |
| transient_all_sources | control | pass | con=1.63e-04 | 12 | 18.1/4.25/18.18 |
| steady_rot_all_sources | feature | pass | con=5.17e-04 | 12 | 13.47/3.04/13.35 |
| steady_rot_nonfixed | feature | pass_statistical | con=1.08e+00 | 12 | 17.69/3.45/17.75 |
| wet_drift_terrain | feature | review | con=1.57e-04, dep=1.00e-04 | 12 | 30.72/13.78/30.85 |
| wet_drift_all | feature | pass | con=2.06e-04, dep=1.08e-04 | 12 | 113.68/17.26/108.56 |
| odour | feature | pass | con=1.83e-04, odr_ch0=1.98e-04, odr_ch1=4.05e-03, odr_ch2=0.00e+00, odr_ch3=0.00e+00 | 12 | 76.89/7.52/46.62 |
| odour_all_sources | feature | pass | con=1.29e-04, odr_ch0=5.86e-04, odr_ch1=8.07e-03, odr_ch2=1.02e-04, odr_ch3=1.02e-04 | 12 | 20.58/5.38/20.49 |
| vertical_conc | feature | fail | con=1.85e-04, vertical=1.33e-04 | 13 | 25.71/5.34/25.74 |
| tunnel_entrance | feature | pass | con=3.50e-05, receptor_staterr=0.00e+00, receptor_steady=2.16e-05, receptor_transient=2.69e-05 | 12 | 11.08/3.61/11.08 |
| tunnel_opp_lane | feature | pass | con=3.43e-04 | 12 | 9.96/4.07/9.97 |
| steady_zr_terrain | feature | review | con=9.75e-05, receptor_staterr=0.00e+00, receptor_steady=2.17e-05, receptor_transient=0.00e+00 | 12 | 16.66/3.67/16.41 |
| steady_eki_terrain | feature | review | con=4.77e-05, receptor_staterr=0.00e+00, receptor_steady=7.22e-06, receptor_transient=0.00e+00 | 12 | 12.75/3.0/12.67 |
| steady_sonic_flat | feature | review | con=3.12e-04, receptor_staterr=0.00e+00, receptor_steady=6.70e-05, receptor_transient=0.00e+00 | 12 | 36.73/6.93/36.36 |
| many_sg_slices | robust | pass | con=1.11e-04 | 12 | 24.14/6.14/24.05 |
| receptors51_vram_tight | robust | pass | con=1.83e-04, receptor_staterr=0.00e+00, receptor_steady=6.32e-05, receptor_transient=6.83e-05 | 12 | 23.96/575.92/70.95 |
| chunk256 | robust | pass | con=1.82e-04 | 12 | 62.4/197.79/62.75 |
| neg_eki_calm | negative | expected_negative_met:post_fix_fallback | con=7.08e-05 | 11 | 43.66/5.85/42.97 |
| neg_transient_zr | negative | expected_negative_met:post_fix_fallback | con=0.00e+00 | 0 | 52.43/52.82/51.45 |
| neg_vertical_inf | negative | negative_unexpected | con=0.00e+00, vertical=0.00e+00 | 0 | 83.44/87.36/91.54 |
