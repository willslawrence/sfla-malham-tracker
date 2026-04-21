#!/usr/bin/env python3
"""
Sync all 3 SFLA KMZ files + Urban VFR Routes + VRP files from OneDrive to shapes.js + routes.js
"""
import re, zipfile, json, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ONEDRIVE_BASE = "/Users/willy/Library/CloudStorage/OneDrive-TheHelicopterCompany/H125 Pilots - Documents/GPS and KMZ Resources/Riyadh UAM"

KMZ_FILES = {
    "SFLA Riyadh UAM.kmz": "Riyadh UAM",
    "SFLA MALHAM.kmz": "Malham",
    "SFLA NAJD.kmz": "NAJD",
}
ROUTES_FILE = "Urban VFR Routes.kmz"
VRP_FILES = ["VRPs & Waypoints.kmz", "NAJD VRPs.kmz"]

def parse_kml(kml):
    placemarks = re.findall(r'<Placemark>(.*?)</Placemark>', kml, re.DOTALL)
    shapes, points, routes = [], [], []
    for p in placemarks:
        name_m = re.search(r'<name>(.*?)</name>', p)
        name = name_m.group(1).strip() if name_m else 'unnamed'
        if '<Polygon>' in p:
            coords_raw = re.search(r'<coordinates>(.*?)</coordinates>', p, re.DOTALL)
            if coords_raw:
                coords = []
                for c in coords_raw.group(1).strip().split():
                    parts = c.split(',')
                    if len(parts) >= 2:
                        coords.append([float(parts[1]), float(parts[0])])
                if coords:
                    lats = [c[0] for c in coords]
                    lngs = [c[1] for c in coords]
                    shapes.append({
                        "name": name,
                        "coords": coords,
                        "center": [round(sum(lats)/len(lats), 6), round(sum(lngs)/len(lngs), 6)],
                        "source": "",
                        "_coordCount": len(coords)  # temp field for deduplication
                    })
        elif '<Point>' in p:
            coords_raw = re.search(r'<coordinates>(.*?)</coordinates>', p, re.DOTALL)
            if coords_raw:
                parts = coords_raw.group(1).strip().split(',')
                if len(parts) >= 2:
                    points.append({"name": name, "lat": float(parts[1]), "lng": float(parts[0])})
        elif '<LineString>' in p:
            coords_raw = re.search(r'<coordinates>(.*?)</coordinates>', p, re.DOTALL)
            if coords_raw:
                coords = []
                for c in coords_raw.group(1).strip().split():
                    parts = c.split(',')
                    if len(parts) >= 2:
                        coords.append([float(parts[1]), float(parts[0])])
                routes.append({"name": name, "coords": coords})
    return shapes, points, routes

def deduplicate_shapes(shapes):
    # Keep first shape for each unique name (avoids dict key collision)
    # For shapes with duplicate names, keep the one with more coordinates
    seen = {}
    result = []
    for s in shapes:
        if s['name'] not in seen:
            seen[s['name']] = s
            result.append(s)
        else:
            # If duplicate name, keep the one with more coordinate points
            if s['_coordCount'] > seen[s['name']]['_coordCount']:
                seen[s['name']] = s
    # Remove temp field
    for s in result:
        del s['_coordCount']
    return result

def main():
    all_shapes = []
    all_gps = []

    for fname, source_label in KMZ_FILES.items():
        path = os.path.join(ONEDRIVE_BASE, fname)
        if not os.path.exists(path):
            print(f"⚠️  Not found: {fname}", file=sys.stderr)
            continue
        with zipfile.ZipFile(path) as z:
            kml = z.read([n for n in z.namelist() if n.endswith('.kml')][0]).decode()
            sh, pt, rt = parse_kml(kml)
            for s in sh:
                s['source'] = source_label
            all_shapes.extend(sh)
            all_gps.extend(pt)
            print(f"✓ {source_label}: {len(sh)} shapes, {len(pt)} points")
    
    # Deduplicate shapes — KMZ may have duplicate names (e.g. N38)
    all_shapes = deduplicate_shapes(all_shapes)
    print(f"✓ After deduplication: {len(all_shapes)} shapes")

    # Routes
    routes_path = os.path.join(ONEDRIVE_BASE, ROUTES_FILE)
    route_data = []
    if os.path.exists(routes_path):
        with zipfile.ZipFile(routes_path) as z:
            kml = z.read([n for n in z.namelist() if n.endswith('.kml')][0]).decode()
            sh, pt, rt = parse_kml(kml)

        styles_raw = re.findall(r'<Style id="(style\d+)">(.*?)</Style>', kml, re.DOTALL)
        style_colors = {}
        for sid, body in styles_raw:
            color_m = re.search(r'<color>([^<]+)</color>', body)
            width_m = re.search(r'<width>([^<]+)</width>', body)
            style_colors[sid] = {
                'color': color_m.group(1) if color_m else 'ffff00ff',
                'width': int(width_m.group(1)) if width_m else 4
            }

        placemarks = re.findall(r'<Placemark>(.*?)</Placemark>', kml, re.DOTALL)
        for p in placemarks:
            name_m = re.search(r'<name>(.*?)</name>', p)
            style_m = re.search(r'<styleUrl>#([^<]+)</styleUrl>', p)
            name = name_m.group(1).strip() if name_m else ''
            style = style_m.group(1).strip() if style_m else ''
            if name and style in style_colors:
                not_approved = "NOT APPROVED" in name or "(Not approved)" in name
                sc = style_colors[style]
                # KML color is AABBGGRR (8 hex digits, no # prefix)
                # Convert to #RRGGBBAA for routes.js
                abgr = sc['color']
                if len(abgr) == 8:
                    a = abgr[0:2]
                    bb = abgr[2:4]
                    gg = abgr[4:6]
                    rr = abgr[6:8]
                    hex_color = f'#{rr}{gg}{bb}{a}'
                else:
                    hex_color = '#ffff00ff'

                rt_match = next((r for r in rt if r['name'] == name), None)
                if rt_match:
                    route_data.append({
                        "name": name,
                        "approved": not not_approved,
                        "color": hex_color,
                        "width": 3 if not_approved else sc['width'],
                        "dashArray": '5,5' if not_approved else None,
                        "coords": rt_match['coords']
                    })
        print(f"✓ Routes: {len(route_data)} ({sum(1 for r in route_data if not r['approved'])} not approved)")
    else:
        print(f"⚠️  Routes file not found: {ROUTES_FILE}", file=sys.stderr)

    # VRP / waypoint files
    all_vrp = []
    for vrp_fname in VRP_FILES:
        vrp_path = os.path.join(ONEDRIVE_BASE, vrp_fname)
        if not os.path.exists(vrp_path):
            print(f"⚠️  VRP file not found: {vrp_fname}", file=sys.stderr)
            continue
        with zipfile.ZipFile(vrp_path) as z:
            kml = z.read([n for n in z.namelist() if n.endswith('.kml')][0]).decode()
            sh, pt, rt = parse_kml(kml)
        all_vrp.extend(pt)
        print(f"✓ {vrp_fname}: {len(pt)} VRP points")

    # Deduplicate by name
    seen_vrp = set()
    all_vrp_deduped = []
    for p in all_vrp:
        if p['name'] not in seen_vrp:
            seen_vrp.add(p['name'])
            all_vrp_deduped.append(p)
    print(f"✓ VRP total (deduped): {len(all_vrp_deduped)}")

    # Write shapes.js
    shapes_path = os.path.join(SCRIPT_DIR, 'shapes.js')
    with open(shapes_path, 'w') as f:
        f.write(f"const SHAPES = {json.dumps(all_shapes)};\n")
    print(f"✓ shapes.js: {len(all_shapes)} shapes written ({os.path.getsize(shapes_path)} bytes)")

    # Write routes.js
    routes_path = os.path.join(SCRIPT_DIR, 'routes.js')
    with open(routes_path, 'w') as f:
        f.write(f"const ROUTES = {json.dumps(route_data)};\n")
        f.write(f"const GPS_POINTS = {json.dumps(all_vrp_deduped)};\n")
    print(f"✓ routes.js: {len(route_data)} routes + {len(all_vrp_deduped)} VRP points ({os.path.getsize(routes_path)} bytes)")

if __name__ == '__main__':
    main()
