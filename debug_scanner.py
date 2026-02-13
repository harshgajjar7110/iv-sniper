import sys
sys.path.insert(0, '.')

from db.scan_store import get_all_scans, get_scan_result

scans = get_all_scans(limit=20)
print('Got scans:', len(scans))

if scans:
    print('First scan:', scans[0])
    
    # Test dropdown options creation
    scan_options = [
        f"{scan['scan_time'][:19]} - {scan['candidates_found']} candidates (IVP>={scan['min_ivp']:.0f}%)"
        for scan in scans
    ]
    print('Options:', scan_options)
    
    scan_options.insert(0, "-- Select a previous scan --")
    print('Options after insert:', scan_options)
    
    # Simulate selection
    selected_idx = 1
    if selected_idx > 0:
        selected_scan = scans[selected_idx - 1]
        scan_id = selected_scan['scan_id']
        scan_detail = get_scan_result(scan_id)
        print('Candidates found:', scan_detail['candidates_found'] if scan_detail else 'None')
        print('First candidate:', scan_detail['candidates'][0] if scan_detail and scan_detail['candidates'] else 'None')
sys.path.insert(0, '.')

from db.scan_store import get_all_scans, get_scan_result

scans = get_all_scans(limit=20)
print('Got scans:', len(scans))

if scans:
    print('First scan:', scans[0])
    
    # Test dropdown options creation
    scan_options = [
        f"{scan['scan_time'][:19]} - {scan['candidates_found']} candidates (IVP>={scan['min_ivp']:.0f}%)"
        for scan in scans
    ]
    print('Options:', scan_options)
    
    scan_options.insert(0, "-- Select a previous scan --")
    print('Options after insert:', scan_options)
    
    # Simulate selection
    selected_idx = 1
    if selected_idx > 0:
        selected_scan = scans[selected_idx - 1]
        scan_id = selected_scan['scan_id']
        scan_detail = get_scan_result(scan_id)
        print('Candidates found:', scan_detail['candidates_found'] if scan_detail else 'None')
        print('First candidate:', scan_detail['candidates'][0] if scan_detail and scan_detail['candidates'] else 'None')


from db.scan_store import get_all_scans, get_scan_result

scans = get_all_scans(limit=20)
print('Got scans:', len(scans))

if scans:
    print('First scan:', scans[0])
    
    # Test dropdown options creation
    scan_options = [
        f"{scan['scan_time'][:19]} - {scan['candidates_found']} candidates (IVP>={scan['min_ivp']:.0f}%)"
        for scan in scans
('Options:', scan    ]
    print_options)
    
    scan_options.insert(0, "-- Select a previous scan --")
    print('Options after insert:', scan_options)
    
    # Simulate selection
    selected_idx = 1
    if selected_idx > 0:
        selected_scan = scans[selected_idx - 1]
        scan_id = selected_scan['scan_id']
        scan_detail = get_scan_result(scan_id)
        print('Candidates found:', scan_detail['candidates_found'] if scan_detail else 'None')
        print('First candidate:', scan_detail['candidates'][0] if scan_detail and scan_detail['candidates'] else 'None')

