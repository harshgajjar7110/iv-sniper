"""
Scan Results Storage Module.

Handles saving and retrieving scanner results to/from the database.

Functions
--------
save_scan_result : Save scan results with a unique scan ID
get_scan_result : Retrieve a specific scan by ID
get_all_scans : Retrieve all scans (with optional limit)
delete_scan_result : Delete a scan by ID
"""

import json
import uuid
from datetime import datetime
from typing import Any

from db.connection import get_connection


def save_scan_result(
    candidates: list[dict[str, Any]],
    min_ivp: float,
    min_hv_rank: float,
    total_scanned: int,
) -> str:
    """
    Save scan results to the database.
    
    Parameters
    ----------
    candidates : list[dict]
        List of candidate dictionaries from the scanner.
    min_ivp : float
        Minimum IVP threshold used for the scan.
    min_hv_rank : float
        Minimum HV Rank threshold used for the scan.
    total_scanned : int
        Total number of stocks that were scanned.
    
    Returns
    -------
    str
        The generated scan_id (UUID) for the saved scan.
    """
    scan_id = str(uuid.uuid4())
    scan_time = datetime.now().isoformat()
    candidates_json = json.dumps(candidates)
    
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO scan_results 
            (scan_id, scan_time, min_ivp, min_hv_rank, total_scanned, candidates_found, candidates)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan_id,
                scan_time,
                min_ivp,
                min_hv_rank,
                total_scanned,
                len(candidates),
                candidates_json,
            ),
        )
    
    return scan_id


def get_scan_result(scan_id: str) -> dict[str, Any] | None:
    """
    Retrieve a specific scan result by ID.
    
    Parameters
    ----------
    scan_id : str
        The UUID of the scan to retrieve.
    
    Returns
    -------
    dict or None
        Dictionary containing scan metadata and candidates, or None if not found.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT scan_id, scan_time, min_ivp, min_hv_rank, 
                   total_scanned, candidates_found, candidates
            FROM scan_results
            WHERE scan_id = ?
            """,
            (scan_id,),
        )
        row = cursor.fetchone()
    
    if row is None:
        return None
    
    return {
        "scan_id": row[0],
        "scan_time": row[1],
        "min_ivp": row[2],
        "min_hv_rank": row[3],
        "total_scanned": row[4],
        "candidates_found": row[5],
        "candidates": json.loads(row[6]),
    }


def get_all_scans(limit: int = 50) -> list[dict[str, Any]]:
    """
    Retrieve all scan results, ordered by scan time descending.
    
    Parameters
    ----------
    limit : int
        Maximum number of scans to return (default: 50).
    
    Returns
    -------
    list[dict]
        List of scan result dictionaries (without full candidates data).
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT scan_id, scan_time, min_ivp, min_hv_rank, 
                   total_scanned, candidates_found
            FROM scan_results
            ORDER BY scan_time DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
    
    return [
        {
            "scan_id": row[0],
            "scan_time": row[1],
            "min_ivp": row[2],
            "min_hv_rank": row[3],
            "total_scanned": row[4],
            "candidates_found": row[5],
        }
        for row in rows
    ]


def delete_scan_result(scan_id: str) -> bool:
    """
    Delete a scan result by ID.
    
    Parameters
    ----------
    scan_id : str
        The UUID of the scan to delete.
    
    Returns
    -------
    bool
        True if a scan was deleted, False if not found.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM scan_results WHERE scan_id = ?",
            (scan_id,),
        )
        return cursor.rowcount > 0
