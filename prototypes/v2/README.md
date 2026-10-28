# Fresh scikit-image prototype

This implementation starts from scikit-image's segmentation and region
measurement routines. It estimates rectangular trench width and length from
`regionprops` ellipse axes using the documented-in-code `sqrt(3)/2` correction.
That estimate assumes the segmented region is a uniformly filled rectangle;
review the overlay and compare it with the preserved first prototype before
treating the dimensions as physical measurements.

The input dataset is in `data/`. From the repository root:

```bash
/Users/chimachibueze/.pyenv/versions/3.13.12/envs/nfi/bin/python prototypes/v2/trench_detection_skimage.py
/Users/chimachibueze/.pyenv/versions/3.13.12/envs/nfi/bin/python -m pytest prototypes/v2/test_trench_detection_skimage.py -q
```

Outputs are written to this folder's `output/` directory by default.
