# Riftbound dataset converter

The converter combines RiftCodex card data with a saved RiftDecks statistics page.
It excludes RAD cards and prefers a base printing over known alternate treatments.
Printing variants share one matching key, including when only a special printing is available.
Cards without matching statistics retain null play and win rates.

Download the RiftDecks Constructed card statistics page with **Last 15 Days** selected,
then save its HTML as `latest_stats` in this directory. Other or missing date ranges
are rejected before downloading cards or writing output.

With Python and `requests` installed, run from this directory:

```powershell
python "python coverter.py"
```

A successful run writes `riftbound_dataset.json` and `dataset_report.json`.
API request failures exit with status 1 and leave existing output files untouched.

Run the offline regression checks with:

```powershell
python -B -m unittest discover -v
```
