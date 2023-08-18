#!/bin/bash
set -x
python3 combine_json.py
# install protobufjs CLI locally if you don't have it:
# npm install protobufjs-cli
npx pbjs -t proto3 liqi_combined.json > liqi_combined.proto
protoc --python_out=. liqi_combined.proto