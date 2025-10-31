#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import sys

NET = 'simple_network.net.xml'
TLL = 'tls.tll.xml'

try:
    net_tree = ET.parse(NET)
    net_root = net_tree.getroot()
except Exception as e:
    print(f"Error parsing {NET}: {e}")
    sys.exit(2)

try:
    tll_tree = ET.parse(TLL)
    tll_root = tll_tree.getroot()
except Exception as e:
    print(f"Error parsing {TLL}: {e}")
    sys.exit(2)

# gather junction incLanes
junctions = {}
for j in net_root.findall('junction'):
    jid = j.attrib.get('id')
    inc = j.attrib.get('incLanes','').strip()
    inc_list = [s for s in inc.split() if s]
    junctions[jid] = inc_list

print('Junction incoming lane counts:')
for jid in sorted(junctions.keys()):
    print(f'  {jid}: {len(junctions[jid])} lanes -> {junctions[jid]}')

print('\nTraffic light logic phases:')
for tl in tll_root.findall('tlLogic'):
    tid = tl.attrib.get('id')
    phases = tl.findall('phase')
    print(f'  {tid}: {len(phases)} phases')
    for i,p in enumerate(phases):
        state = p.attrib.get('state','')
        dur = p.attrib.get('duration','')
        print(f'    phase {i}: duration={dur} state="{state}" len={len(state)}')
    # compare to junction inc lanes if present
    jl = junctions.get(tid)
    if jl is not None:
        expected = len(jl)
        # SUMO expects state length == number of controlled links. We'll report mismatch
        lens = set(len(p.attrib.get('state','')) for p in phases)
        if any(l != expected for l in lens):
            print(f'    >>> MISMATCH: expected state length {expected} (from junction incLanes), found lengths {sorted(lens)}')
        else:
            print(f'    OK: all phase states length == {expected}')
    else:
        print('    Note: junction not found in net file')

print('\nDone')
