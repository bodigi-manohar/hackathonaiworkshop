# Walk-forward backtest

Expanding window, daily 00:00 origin, 48 half-hour slots, 6 folds. Units: kW. Skill = 1 - MAE / MAE(seasonal naive). Headline level: **portfolio**.


## portfolio - oracle weather

| model | mae | rmse | nmae | skill |
|---|---|---|---|---|
| seasonal_naive | 26.085 | 51.075 | 0.122 | 0.000 |
| weekly_naive | 29.392 | 51.326 | 0.137 | -0.127 |
| moving_average | 24.670 | 41.560 | 0.115 | 0.054 |
| ridge | 21.332 | 34.596 | 0.099 | 0.182 |
| lgbm | 18.984 | 33.637 | 0.088 | 0.272 |
| ensemble | 18.786 | 32.785 | 0.088 | 0.280 |


Coverage P10-P90: 0.775 (target ~0.80) | pinball: 4.720 | peak MAE: 28.22 kW | peak timing error: 10.52 slots


**Ensemble beats seasonal-naive: YES** (skill 0.280).


Per fold:

| fold | ensemble_mae | seasonal_naive_mae | skill |
|---|---|---|---|
| 1 | 34.288 | 57.967 | 0.408 |
| 2 | 16.161 | 18.414 | 0.122 |
| 3 | 12.931 | 16.737 | 0.227 |
| 4 | 13.360 | 16.658 | 0.198 |
| 5 | 14.198 | 17.839 | 0.204 |
| 6 | 21.776 | 28.896 | 0.246 |


## portfolio - noisy weather

| model | mae | rmse | nmae | skill |
|---|---|---|---|---|
| seasonal_naive | 26.085 | 51.075 | 0.122 | 0.000 |
| weekly_naive | 29.392 | 51.326 | 0.137 | -0.127 |
| moving_average | 24.670 | 41.560 | 0.115 | 0.054 |
| ridge | 27.044 | 41.023 | 0.126 | -0.037 |
| lgbm | 20.346 | 35.135 | 0.095 | 0.220 |
| ensemble | 20.662 | 34.901 | 0.096 | 0.208 |


Coverage P10-P90: 0.774 (target ~0.80) | pinball: 4.875 | peak MAE: 32.95 kW | peak timing error: 11.69 slots


**Ensemble beats seasonal-naive: YES** (skill 0.208).


Per fold:

| fold | ensemble_mae | seasonal_naive_mae | skill |
|---|---|---|---|
| 1 | 36.309 | 57.967 | 0.374 |
| 2 | 19.064 | 18.414 | -0.035 |
| 3 | 16.698 | 16.737 | 0.002 |
| 4 | 13.930 | 16.658 | 0.164 |
| 5 | 14.639 | 17.839 | 0.179 |
| 6 | 23.334 | 28.896 | 0.192 |


## zone - oracle weather

| model | mae | rmse | nmae | skill |
|---|---|---|---|---|
| seasonal_naive | 3.959 | 7.168 | 0.203 | 0.000 |
| weekly_naive | 4.137 | 7.185 | 0.212 | -0.045 |
| moving_average | 3.345 | 5.710 | 0.172 | 0.155 |
| ridge | 3.187 | 5.152 | 0.163 | 0.195 |
| lgbm | 2.977 | 4.830 | 0.153 | 0.248 |
| ensemble | 2.976 | 4.823 | 0.153 | 0.248 |


Coverage P10-P90: 0.789 (target ~0.80) | pinball: 0.684 | peak MAE: 4.86 kW | peak timing error: 7.90 slots


**Ensemble beats seasonal-naive: YES** (skill 0.248).


Per fold:

| fold | ensemble_mae | seasonal_naive_mae | skill |
|---|---|---|---|
| 1 | 4.183 | 6.391 | 0.345 |
| 2 | 2.620 | 3.122 | 0.161 |
| 3 | 2.376 | 2.989 | 0.205 |
| 4 | 2.302 | 2.933 | 0.215 |
| 5 | 2.765 | 3.500 | 0.210 |
| 6 | 3.612 | 4.818 | 0.250 |


## zone - noisy weather

| model | mae | rmse | nmae | skill |
|---|---|---|---|---|
| seasonal_naive | 3.959 | 7.168 | 0.203 | 0.000 |
| weekly_naive | 4.137 | 7.185 | 0.212 | -0.045 |
| moving_average | 3.345 | 5.710 | 0.172 | 0.155 |
| ridge | 3.822 | 6.025 | 0.196 | 0.035 |
| lgbm | 3.067 | 4.982 | 0.157 | 0.225 |
| ensemble | 3.078 | 4.991 | 0.158 | 0.222 |


Coverage P10-P90: 0.787 (target ~0.80) | pinball: 0.697 | peak MAE: 4.89 kW | peak timing error: 8.26 slots


**Ensemble beats seasonal-naive: YES** (skill 0.222).


Per fold:

| fold | ensemble_mae | seasonal_naive_mae | skill |
|---|---|---|---|
| 1 | 4.280 | 6.391 | 0.330 |
| 2 | 2.824 | 3.122 | 0.096 |
| 3 | 2.512 | 2.989 | 0.160 |
| 4 | 2.328 | 2.933 | 0.206 |
| 5 | 2.789 | 3.500 | 0.203 |
| 6 | 3.736 | 4.818 | 0.225 |


## house - oracle weather

| model | mae | rmse | nmae | skill |
|---|---|---|---|---|
| seasonal_naive | 2.344 | 3.589 | 0.273 | 0.000 |
| weekly_naive | 2.432 | 3.644 | 0.283 | -0.037 |
| moving_average | 1.945 | 2.862 | 0.227 | 0.170 |
| ridge | 1.880 | 2.674 | 0.219 | 0.198 |
| lgbm | 1.793 | 2.592 | 0.209 | 0.235 |
| ensemble | 1.792 | 2.579 | 0.209 | 0.236 |


Coverage P10-P90: 0.793 (target ~0.80) | pinball: 0.404 | peak MAE: 2.96 kW | peak timing error: 9.13 slots


**Ensemble beats seasonal-naive: YES** (skill 0.236).


Per fold:

| fold | ensemble_mae | seasonal_naive_mae | skill |
|---|---|---|---|
| 1 | 2.278 | 3.307 | 0.311 |
| 2 | 1.575 | 1.915 | 0.177 |
| 3 | 1.497 | 1.866 | 0.198 |
| 4 | 1.451 | 1.846 | 0.214 |
| 5 | 1.724 | 2.204 | 0.218 |
| 6 | 2.228 | 2.929 | 0.239 |


## house - noisy weather

| model | mae | rmse | nmae | skill |
|---|---|---|---|---|
| seasonal_naive | 2.344 | 3.589 | 0.273 | 0.000 |
| weekly_naive | 2.432 | 3.644 | 0.283 | -0.037 |
| moving_average | 1.945 | 2.862 | 0.227 | 0.170 |
| ridge | 2.087 | 2.917 | 0.243 | 0.110 |
| lgbm | 1.822 | 2.634 | 0.212 | 0.223 |
| ensemble | 1.825 | 2.625 | 0.213 | 0.221 |


Coverage P10-P90: 0.791 (target ~0.80) | pinball: 0.410 | peak MAE: 2.98 kW | peak timing error: 9.18 slots


**Ensemble beats seasonal-naive: YES** (skill 0.221).


Per fold:

| fold | ensemble_mae | seasonal_naive_mae | skill |
|---|---|---|---|
| 1 | 2.319 | 3.307 | 0.299 |
| 2 | 1.632 | 1.915 | 0.148 |
| 3 | 1.533 | 1.866 | 0.178 |
| 4 | 1.460 | 1.846 | 0.209 |
| 5 | 1.733 | 2.204 | 0.214 |
| 6 | 2.275 | 2.929 | 0.223 |


Last-7-days MAE (portfolio): 20.824 kW, drift ratio 1.109
