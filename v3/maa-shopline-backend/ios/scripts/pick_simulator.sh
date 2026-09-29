#!/usr/bin/env bash
# Prints an xcodebuild destination for the newest available iPhone simulator,
# so CI does not depend on a device name that changes between runner images.
set -euo pipefail
xcrun simctl list devices available -j | python3 -c '
import json, sys
d = json.load(sys.stdin)["devices"]
ios = sorted((k for k in d if "iOS" in k), key=lambda k: [int(x) for x in k.split("iOS-")[1].split("-")])
for rt in reversed(ios):
    phones = [x for x in d[rt] if x["name"].startswith("iPhone")]
    if phones:
        print("id=" + phones[0]["udid"]); break
else:
    sys.exit("no iPhone simulator available")'
