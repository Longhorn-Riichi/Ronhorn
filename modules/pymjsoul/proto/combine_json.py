import json
from os.path import join, dirname

CURR_DIR = dirname(__file__)

# load the json files
liqi_json_path = join(CURR_DIR, "liqi.json")
liqi_admin_json_path = join(CURR_DIR, "liqi_admin.json")
with open(liqi_json_path, "r") as f:
    liqi_json = json.loads(f.read())
with open(liqi_admin_json_path, "r") as f:
    liqi_admin_json = json.loads(f.read())

liqi_json["nested"]["lq"]["nested"].update(liqi_admin_json["nested"]["lq"]["nested"])

with open("liqi_combined.json", "w") as f:
    json.dump(liqi_json, f, indent=4)
