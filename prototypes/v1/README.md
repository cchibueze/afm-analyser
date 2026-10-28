# Trench prototype v1

This is the preserved first implementation, using scikit-image for thresholding,
mask morphology, connected components, and region properties, plus explicit
cross-section and fitted-centerline calculations for trench dimensions.

The input dataset is in `data/`. From the repository root:

```bash
/Users/chimachibueze/.pyenv/versions/3.13.12/envs/nfi/bin/python prototypes/v1/trench_detection_prototype.py
/Users/chimachibueze/.pyenv/versions/3.13.12/envs/nfi/bin/python -m pytest prototypes/v1/test_trench_detection_prototype.py -q
```

The original run outputs are preserved in `trench_detection_output/`.
