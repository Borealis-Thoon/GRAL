| case | group | screen | A/B by type | GPU situations | wall s (cpu/gpu/native) |
|---|---|---|---|---|---|
| transient_area | control | pass | con=1.82e-04 | 12 | 20.71/19.04/20.58 |
| transient_all_sources | control | pass | con=1.63e-04 | 12 | 18.25/18.38/18.05 |
| steady_rot_all_sources | feature | pass | con=5.16e-04 | 12 | 13.4/13.04/13.21 |
| steady_rot_nonfixed | feature | pass_statistical | con=1.08e+00 | 12 | 17.65/15.57/17.64 |
| wet_drift_terrain | feature | fail | con=1.54e-04, dep=1.00e-04 | 12 | 30.48/54.04/30.49 |
| wet_drift_all | feature | fail | con=2.09e-04, dep=1.10e-04 | 12 | 29.82/59.01/28.65 |
| odour | feature | fail | con=1.84e-04, odr_ch0=1.95e-04, odr_ch1=4.04e-03, odr_ch2=0.00e+00, odr_ch3=0.00e+00 | 12 | 23.55/23.8/23.51 |
| odour_all_sources | feature | fail | con=1.29e-04, odr_ch0=5.83e-04, odr_ch1=8.14e-03, odr_ch2=1.02e-04, odr_ch3=1.02e-04 | 12 | 20.73/22.94/20.85 |
| vertical_conc | feature | fail | con=1.87e-04, vertical=1.32e-04 | 13 | 25.67/22.69/25.51 |
| tunnel_entrance | feature | fail | con=3.42e-05, receptor_staterr=0.00e+00, receptor_steady=2.22e-05, receptor_transient=2.76e-05 | 12 | 11.08/16.06/20.49 |
| tunnel_opp_lane | feature | fail | con=3.46e-04 | 12 | 19.61/18.09/9.91 |
| steady_zr_terrain | feature | fail | con=9.70e-05, receptor_staterr=0.00e+00, receptor_steady=2.14e-05, receptor_transient=0.00e+00 | 12 | 16.47/16.86/16.44 |
| steady_eki_terrain | feature | fail | con=4.74e-05, receptor_staterr=0.00e+00, receptor_steady=7.14e-06, receptor_transient=0.00e+00 | 12 | 12.68/13.04/12.58 |
| steady_sonic_flat | feature | fail | con=3.14e-04, receptor_staterr=0.00e+00, receptor_steady=6.69e-05, receptor_transient=0.00e+00 | 12 | 36.68/35.92/36.46 |
| many_sg_slices | robust | pass | con=1.11e-04 | 12 | 101.37/31.68/99.8 |
| receptors51_vram_tight | robust | pass | con=1.83e-04, receptor_staterr=0.00e+00, receptor_steady=6.16e-05, receptor_transient=6.66e-05 | 12 | 97.53/602.87/24.06 |
| neg_eki_calm | negative | expected_negative_met:post_fix_fallback | con=7.02e-05 | 11 | 14.48/14.88/14.35 |
| neg_transient_zr | negative | expected_negative_met:post_fix_fallback | con=0.00e+00 | 0 | 17.47/17.49/17.47 |
