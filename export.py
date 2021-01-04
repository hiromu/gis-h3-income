#!/usr/bin/env python

import csv
import h3
import json
import os
import sys


H3_RESOLUTION = 4


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('{} [in.csv]'.format(sys.argv[0]))
        sys.exit(1)

    headers, grids = None, {}

    for lineno, line in enumerate(csv.reader(open(sys.argv[1]))):
        if lineno == 0:
            headers = line[1:]
            continue

        h3index = h3.h3_to_parent(line[0], H3_RESOLUTION)
        if h3index not in grids:
            grids[h3index] = []
        grids[h3index].append(line)

    for h3index in grids:
        features = []

        for line in grids[h3index]:
            if sum(map(int, line[1:])) == 0:
                continue

            features.append({
                'type': 'Feature',
                'properties': {
                    'name': line[0],
                    'distribution': dict(zip(headers, map(int, line[1:]))),
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [
                        h3.h3_to_geo_boundary(line[0], True)
                    ],
                }
            })

        if len(features) == 0:
            continue

        json_path = os.path.join(os.path.dirname(__file__), 'public', 'geojson', '{}.json'.format(h3index))
        with open(json_path, 'w') as out_json:
            json.dump({'type': 'FeatureCollection', 'features': features}, out_json)
