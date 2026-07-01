import yaml
import json
import os

with open('/Users/alexandersolianin/Projects/gazzetta-di-kyiv/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

narratives_out = {
    "metadata": {
        "version": "4.0",
        "updated": "2026-07-01T16:00:00Z",
        "note": "12 master narratives"
    },
    "narratives": {}
}

for key, val in config['narratives'].items():
    narratives_out['narratives'][key] = {
        "display_name": val['label'],
        "tag": val['label'].split(' & ')[0], # Just a rough tag
        "description": val['description'],
        "tickers": [], # We don't have this in config.yaml, so empty list
        "invalidation_threshold": "",
        "subnarratives": val.get('subnarratives', {})
    }

out_path = '/Users/alexandersolianin/Projects/gazzetta-di-kyiv/data/narratives.json'
with open(out_path, 'w') as f:
    json.dump(narratives_out, f, indent=2)

print("Updated data/narratives.json")
