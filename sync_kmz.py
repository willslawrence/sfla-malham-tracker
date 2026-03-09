#!/usr/bin/env python3
"""
SFLA KMZ/KML Sync Tool
Diffs a KMZ/KML file against current shapes.js + Airtable.
Shows what would change, then applies with --apply flag.

Usage:
  python3 sync_kmz.py <path_to_kml_or_kmz>           # Dry run (show diff)
  python3 sync_kmz.py <path_to_kml_or_kmz> --apply    # Apply changes
"""

import json, sys, os, re, zipfile, tempfile
import urllib.request, urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHAPES_JS = os.path.join(SCRIPT_DIR, 'shapes.js')
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.json')

config = json.load(open(CONFIG_PATH))
BASE_ID = config['airtable']['baseId']
API_KEY = config['airtable']['apiKey']

def api_get(table, params=''):
    url = f'https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}?pageSize=100{params}'
    all_records = []
    while url:
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {API_KEY}'})
        resp = json.loads(urllib.request.urlopen(req).read())
        all_records.extend(resp.get('records', []))
        offset = resp.get('offset')
        url = f'https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}?pageSize=100&offset={offset}' if offset else None
    return all_records

def api_post(table, records):
    url = f'https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}'
    data = json.dumps({"records": records}).encode()
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    })
    return json.loads(urllib.request.urlopen(req).read())

def parse_kml(kml_text):
    """Parse KML text into shapes, points, and routes."""
    placemarks = re.findall(r'<Placemark>(.*?)</Placemark>', kml_text, re.DOTALL)
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
                    center = [round(sum(lats)/len(lats), 6), round(sum(lngs)/len(lngs), 6)]
                    shapes.append({"name": name, "coords": coords, "center": center})
        
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

def load_kml_from_file(path):
    """Load KML from a .kml or .kmz file."""
    if path.endswith('.kmz'):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith('.kml'):
                    return z.read(name).decode()
        raise ValueError("No .kml found in .kmz")
    else:
        return open(path).read()

def load_current_shapes():
    """Load current shapes from shapes.js."""
    js = open(SHAPES_JS).read()
    shapes = json.loads(re.search(r'const SHAPES = (\[.*?\]);', js, re.DOTALL).group(1))
    routes_m = re.search(r'const ROUTES = (\[.*?\]);', js, re.DOTALL)
    routes = json.loads(routes_m.group(1)) if routes_m else []
    gps_m = re.search(r'const GPS_POINTS = (\[.*?\]);', js, re.DOTALL)
    gps = json.loads(gps_m.group(1)) if gps_m else []
    return shapes, routes, gps

def coords_changed(old_coords, new_coords):
    """Check if coordinates have meaningfully changed."""
    if len(old_coords) != len(new_coords):
        return True
    for a, b in zip(old_coords, new_coords):
        if abs(a[0] - b[0]) > 0.000001 or abs(a[1] - b[1]) > 0.000001:
            return True
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sync_kmz.py <path> [--apply]")
        sys.exit(1)
    
    kml_path = sys.argv[1]
    apply = '--apply' in sys.argv
    
    print(f"{'APPLYING' if apply else 'DRY RUN'}: Syncing from {os.path.basename(kml_path)}")
    print("=" * 60)
    
    # Load new KML data
    kml_text = load_kml_from_file(kml_path)
    new_shapes, new_points, new_routes = parse_kml(kml_text)
    
    # Load current data
    cur_shapes, cur_routes, cur_gps = load_current_shapes()
    cur_dict = {s['name']: s for s in cur_shapes}
    new_dict = {s['name']: s for s in new_shapes}
    
    # Diff
    added = sorted(set(new_dict.keys()) - set(cur_dict.keys()))
    removed = sorted(set(cur_dict.keys()) - set(new_dict.keys()))
    common = sorted(set(cur_dict.keys()) & set(new_dict.keys()))
    modified = [n for n in common if coords_changed(cur_dict[n]['coords'], new_dict[n]['coords'])]
    unchanged = [n for n in common if n not in modified]
    
    print(f"\nShapes in KML:     {len(new_shapes)}")
    print(f"Shapes in current: {len(cur_shapes)}")
    print(f"  Added:     {len(added)}")
    print(f"  Removed:   {len(removed)}")
    print(f"  Modified:  {len(modified)}")
    print(f"  Unchanged: {len(unchanged)}")
    
    if new_points:
        print(f"\nGPS Points: {len(new_points)}")
        for p in new_points:
            print(f"  {p['name']} ({p['lat']:.6f}, {p['lng']:.6f})")
    
    if new_routes:
        print(f"\nRoutes: {len(new_routes)}")
        for r in new_routes:
            print(f"  {r['name']} ({len(r['coords'])} points)")
    
    if added:
        print(f"\n+ ADDED shapes:")
        for n in added:
            print(f"  + {n} ({len(new_dict[n]['coords'])} points)")
    
    if removed:
        print(f"\n- REMOVED shapes (will keep in shapes.js + Airtable, just flag):")
        for n in removed:
            print(f"  - {n}")
    
    if modified:
        print(f"\n~ MODIFIED shapes (coords updated, Airtable data preserved):")
        for n in modified:
            print(f"  ~ {n} ({len(cur_dict[n]['coords'])} -> {len(new_dict[n]['coords'])} points)")
    
    if not added and not modified and not new_points and not new_routes:
        if not removed:
            print("\nNo changes detected.")
        else:
            print(f"\nOnly removals detected. Shapes NOT auto-deleted (safety).")
            print("To remove, manually delete from Airtable and re-run with full KMZ.")
        return
    
    if not apply:
        print(f"\nRun with --apply to apply these changes.")
        return
    
    # === APPLY ===
    print("\nApplying changes...")
    
    # 1. Update shapes.js: merge new into current (never delete)
    merged = dict(cur_dict)  # Start with all current
    for name in added + modified:
        merged[name] = new_dict[name]
    
    # Update GPS points and routes if present in new KML
    final_gps = new_points if new_points else cur_gps
    final_routes = new_routes if new_routes else cur_routes
    
    output = f"const SHAPES = {json.dumps(list(merged.values()))};\n"
    output += f"const ROUTES = {json.dumps(final_routes)};\n"
    output += f"const GPS_POINTS = {json.dumps(final_gps)};\n"
    open(SHAPES_JS, 'w').write(output)
    print(f"  Updated shapes.js: {len(merged)} shapes, {len(final_routes)} routes, {len(final_gps)} GPS points")
    
    # 2. Add new shapes to Airtable
    if added:
        records = [{"fields": {"SFLA Name": n, "Status": "New SFLA"}} for n in added]
        # Batch in groups of 10
        for i in range(0, len(records), 10):
            batch = records[i:i+10]
            result = api_post('Sites', batch)
            for r in result.get('records', []):
                print(f"  Airtable: Created '{r['fields']['Name']}' as New SFLA")
    
    if removed:
        print(f"  Note: {len(removed)} shapes in current but not in KML (NOT deleted — safety)")
        print(f"  Remove manually from Airtable if no longer needed: {', '.join(removed)}")
    
    print("\nDone!")

if __name__ == '__main__':
    main()
