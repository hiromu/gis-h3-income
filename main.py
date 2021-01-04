#!/usr/bin/env python

import csv
import h3
import lxml.etree
import os
import shapely.errors
import shapely.geometry
import sys
import zipfile


H3_RESOLUTION = 8


def obtain_h3ratio(polygons):
    h3indices = set()

    for polygon in polygons:
        centroid = list(map(lambda x: x / len(polygon[0]), map(sum, zip(*polygon[0]))))
        h3indices.add(h3.geo_to_h3(centroid[0], centroid[1], H3_RESOLUTION))
        h3indices |= h3.polyfill({'type': 'Polygon', 'coordinates': polygon}, H3_RESOLUTION)

    for h3index in list(h3indices):
        h3indices |= h3.k_ring(h3index, 1)

    h3polygons = [(h3index, shapely.geometry.Polygon(h3.h3_to_geo_boundary(h3index))) for h3index in h3indices]
    polygon_areas = {}

    for polygon in polygons:
        polygon = shapely.geometry.Polygon(polygon[0], polygon[1:])
        for h3index, h3polygon in h3polygons:
            try:
                area = h3polygon.intersection(polygon).area
                if area:
                    polygon_areas[h3index] = area + polygon_areas.get(h3index, 0)
            except shapely.errors.TopologicalError:
                continue

    total_area = sum(polygon_areas.values())
    return dict(map(lambda x: (x[0], x[1] / total_area), polygon_areas.items()))


def process_stat(h3_dict, income_dict, polygon_dict, line):
    total, own, rent = line[-3:]
    if not total.isdigit():
        return
    print(line[2] + line[3])

    region_code = line[0][:5]
    for index in range(5, -1, -1):
        if region_code in income_dict:
            break
        region_code = region_code[:index] + '0' * (5 - index)

    own = float(0 if own == '-' else own)
    other = float(total) - own
    income = list(map(lambda x: own * x[0] + other * x[1], zip(*income_dict[region_code])))

    gassan_regions = [line[0]] + (list(map(lambda x: line[0][:5] + x, line[6].split(';'))) if line[6] else [])
    h3ratio = obtain_h3ratio([polygon_dict[region_code] for region_code in gassan_regions])

    for h3index, ratio in h3ratio.items():
        if h3index not in h3_dict:
            h3_dict[h3index] = [0.0] * len(income)
        for index in range(len(income)):
            h3_dict[h3index][index] += income[index] * ratio


def extract_coords(coordinates_elm):
    coordinates = []
    for line in coordinates_elm.text.strip().split('\n'):
        coordinates.append(list(map(float, line.strip().split(',')[:2][::-1])))
    return coordinates


def load_pref(h3_dict, income_dict, pref_code):
    kmz_file = os.path.join(os.path.dirname(__file__), 'data', 'region', 'h27ka{:02}.kmz'.format(pref_code))
    kml_ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    polygon_dict = {}

    with zipfile.ZipFile(kmz_file) as kmz:
        with kmz.open(kmz.namelist()[0]) as kml:
            for town in lxml.etree.parse(kml).findall('//kml:Placemark', namespaces=kml_ns):
                key_code = town.find('.//kml:SimpleData[@name="KEY_CODE"]', namespaces=kml_ns).text
                polygon_dict[key_code] = [extract_coords(polygon) for polygon in town.findall('.//kml:coordinates', namespaces=kml_ns)]

    csv_file = os.path.join(os.path.dirname(__file__), 'data', 'houseowner', 'tblT000852C{:02}.txt'.format(pref_code))
    last_level, last_line = 0, None

    for lineno, line in enumerate(csv.reader(open(csv_file, encoding='shift_jis'))):
        if lineno < 2:
            continue

        curr_level = int(line[1])
        if last_level >= curr_level:
            process_stat(h3_dict, income_dict, polygon_dict, last_line)

        last_level, last_line = curr_level, line
    else:
        process_stat(h3_dict, income_dict, polygon_dict, last_line)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('{} [out.csv]'.format(sys.argv[0]))
        sys.exit(1)

    csv_file = os.path.join(os.path.dirname(__file__), 'data', 'FEH_00200522_210104144455.csv')
    income_dict, headers = {}, []

    for lineno, line in enumerate(csv.reader(open(csv_file, encoding='shift_jis'))):
        if lineno < 13:
            if lineno == 12:
                headers = line[-7: -1]
            continue
        if line[7] not in (u'持ち家', u'持ち家以外'):
            continue

        region_code = line[4]
        if region_code not in income_dict:
            income_dict[region_code] = [[], []]

        income_dist = list(map(lambda s: float(s.replace(',', '').replace('-', '0')), line[-7: -1]))
        income_dict[region_code][line[7] == u'持ち家'] = list(map(lambda f: f / sum(income_dist), income_dist))

    h3_dict = {}

    for pref_code in range(1, 48):
        load_pref(h3_dict, income_dict, pref_code)

    with open(sys.argv[1], 'w', encoding='utf-8') as out_csv:
        writer = csv.writer(out_csv)
        writer.writerow(['h3index'] + headers)

        for h3index, income_dist in h3_dict.items():
            writer.writerow([h3index] + [str(round(num)) for num in income_dist])
