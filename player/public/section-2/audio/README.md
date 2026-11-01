# Narration audio

Drop the 44 recordings in this folder, named exactly as below. The player
requests `audio/<file>` for the slide it is showing; nothing else needs changing.

The mapping lives in `voiceover.json` and is already complete. `approx` is the
source manifest's 140 wpm estimate, not a measured length.

| file | slide | source | part | approx |
|---|---|---|---|---|
| `m1_1_01_base.mp3` | slide_1_01 | 1.01 | base | 51s |
| `m1_1_02_base.mp3` | slide_1_02 | 1.02 | base | 24s |
| `m1_1_03_base.mp3` | slide_1_03 | 1.03 | base | 21s |
| `m1_1_04_base.mp3` | slide_1_04 | 1.04 | base | 56s |
| `m1_1_05_base.mp3` | slide_1_05 | 1.05 | base | 29s |
| `m1_1_06_base.mp3` | slide_1_06 | 1.06 | base | 29s |
| `m1_1_07_base.mp3` | slide_1_07 | 1.07 | base | 27s |
| `m1_1_08_base.mp3` | slide_1_08 | 1.08 | base | 39s |
| `m1_1_09_base.mp3` | slide_1_09 | 1.09 | base | 18s |
| `m1_1_10_base.mp3` | slide_1_10 | 1.10 | base | 35s |
| `m1_1_11_base.mp3` | slide_1_11 | 1.11 | base | 35s |
| `m1_1_12_base.mp3` | slide_1_12 | 1.12 | base | 36s |
| `m1_1_13_base.mp3` | slide_1_13 | 1.13 | base | 33s |
| `m1_1_14_base.mp3` | slide_1_14 | 1.14 | base | 29s |
| `m1_1_15_base.mp3` | slide_1_15 | 1.15 | base | 17s |
| `m1_1_16_base.mp3` | slide_1_16 | 1.16 | base | 35s |
| `m1_1_17_base.mp3` | slide_1_17 | 1.17 | base | 13s |
| `m1_1_18_base.mp3` | slide_1_18 | 1.18 | base | 12s |
| `m1_1_19_base.mp3` | slide_1_19 | 1.19 | base | 27s |
| `m2_2_01_base.mp3` | slide_2_01 | 2.01 | base | 32s |
| `m2_2_02_base.mp3` | slide_2_02 | 2.02 | base | 16s |
| `m2_2_03_base.mp3` | slide_2_03 | 2.03 | base | 28s |
| `m2_2_03_L1.mp3` | slide_2_03 | 2.03 | slide_2_03_layer_1 | 28s |
| `m2_2_03_L2.mp3` | slide_2_03 | 2.03 | slide_2_03_layer_2 | 31s |
| `m2_2_03_L3.mp3` | slide_2_03 | 2.03 | slide_2_03_layer_3 | 27s |
| `m2_2_03_L4.mp3` | slide_2_03 | 2.03 | slide_2_03_layer_4 | 22s |
| `m2_2_03_L5.mp3` | slide_2_03 | 2.03 | slide_2_03_layer_5 | 25s |
| `m2_2_05_base.mp3` | slide_2_05 | 2.05 | base | 28s |
| `m2_2_06_base.mp3` | slide_2_06 | 2.06 | base | 18s |
| `m2_2_07_base.mp3` | slide_2_07 | 2.07 | base | 26s |
| `m2_2_08_base.mp3` | slide_2_08 | 2.08 | base | 27s |
| `m2_2_09_base.mp3` | slide_2_09 | 2.09 | base | 35s |
| `m2_2_10_base.mp3` | slide_2_10 | 2.10 | base | 24s |
| `m2_2_11_base.mp3` | slide_2_11 | 2.11 | base | 21s |
| `m2_2_12_base.mp3` | slide_2_12 | 2.12 | base | 24s |
| `m2_2_13_base.mp3` | slide_2_13 | 2.13 | base | 35s |
| `m2_2_14_base.mp3` | slide_2_14 | 2.14 | base | 27s |
| `m2_2_15_base.mp3` | slide_2_15 | 2.15 | base | 24s |
| `m2_2_16_base.mp3` | slide_2_16 | 2.16 | base | 26s |
| `m2_2_17_base.mp3` | slide_2_17 | 2.17 | base | 45s |
| `m2_2_18_base.mp3` | slide_2_18 | 2.18 | base | 33s |
| `m2_2_19_base.mp3` | slide_2_19 | 2.19 | base | 34s |
| `m2_2_20_base.mp3` | slide_2_20 | 2.20 | base | 13s |
| `m2_2_21_base.mp3` | slide_2_21 | 2.21 | base | 63s |

Serve this folder from a static server that supports HTTP Range requests,
or seeking inside a track will not work.
