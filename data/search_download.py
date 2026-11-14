"""
Search ASF for NISAR GCOV + SME2 and Sentinel-1 GRD granules over the
Calvos de Randin AOI.

GCOV and SME2 live on NISAR's fixed track/frame grid, so pre/post pairs
only make sense between matching track/frame. Sentinel-1 does not share
that grid with NISAR, and its revisit is dense enough (~6 days here) that
pairing isn't necessary -- we just list the time series.

Auth (only needed for download, not search): set EARTHDATA_TOKEN to an EDL
bearer token from your urs.earthdata.nasa.gov profile ("Generate Token"),
or EARTHDATA_USERNAME / EARTHDATA_PASSWORD, or just have a ~/.netrc entry
for urs.earthdata.nasa.gov -- see get_session() below for the fallback
order.
"""

import os
from collections import defaultdict

import asf_search as asf

from config import (
    AOI_WKT,
    DATASET,
    PROCESSING_LEVEL,
    SME2_PROCESSING_LEVEL,
    S1_DATASET,
    S1_PROCESSING_LEVEL,
    PRE_FIRE_START,
    PRE_FIRE_END,
    POST_FIRE_START,
    POST_FIRE_END,
    RAW_DIR,
)


def search_window(dataset, processing_level, start, end):
    return asf.search(
        dataset=dataset,
        processingLevel=processing_level,
        intersectsWith=AOI_WKT,
        start=start,
        end=end,
    )


def track_frame_key(result):
    props = result.properties
    return (props.get("pathNumber"), props.get("frameNumber"))


def find_matched_pairs(dataset, processing_level):
    pre = search_window(dataset, processing_level, PRE_FIRE_START, PRE_FIRE_END)
    post = search_window(dataset, processing_level, POST_FIRE_START, POST_FIRE_END)

    pre_by_key = defaultdict(list)
    for r in pre:
        pre_by_key[track_frame_key(r)].append(r)

    post_by_key = defaultdict(list)
    for r in post:
        post_by_key[track_frame_key(r)].append(r)

    common_keys = set(pre_by_key) & set(post_by_key)
    if not common_keys:
        print(f"  no matching track/frame for {dataset}/{processing_level}")
        print(f"    pre candidates: {len(pre)}  post candidates: {len(post)}")
        return []

    pairs = []
    for key in sorted(common_keys):
        pre_r = sorted(pre_by_key[key], key=lambda r: r.properties["startTime"])[-1]
        post_r = sorted(post_by_key[key], key=lambda r: r.properties["startTime"])[0]
        pairs.append((key, pre_r, post_r))
    return pairs


def list_sentinel1_series():
    results = search_window(S1_DATASET, S1_PROCESSING_LEVEL, PRE_FIRE_START, POST_FIRE_END)
    return sorted(results, key=lambda r: r.properties["startTime"])


def download_results(results, session):
    os.makedirs(RAW_DIR, exist_ok=True)
    for r in results:
        print(f"  downloading {r.properties['fileName']}")
        r.download(path=RAW_DIR, session=session)


def get_session():
    """
    Prefers an EDL bearer token (EARTHDATA_TOKEN) since that's what you get
    from "Generate Token" on your urs.earthdata.nasa.gov profile. Falls back
    to username/password, then to a bare session (requests reads ~/.netrc
    automatically if neither env var is set).
    """
    token = os.environ.get("EARTHDATA_TOKEN")
    if token:
        return asf.ASFSession().auth_with_token(token)

    username = os.environ.get("EARTHDATA_USERNAME")
    password = os.environ.get("EARTHDATA_PASSWORD")
    if username and password:
        return asf.ASFSession().auth_with_creds(username, password)

    return asf.ASFSession()


if __name__ == "__main__":
    print("NISAR GCOV:")
    gcov_pairs = find_matched_pairs(DATASET, PROCESSING_LEVEL)
    for key, pre_r, post_r in gcov_pairs:
        print(f"  {key}: {pre_r.properties['fileName']} / {post_r.properties['fileName']}")

    print("\nNISAR SME2:")
    sme2_pairs = find_matched_pairs(DATASET, SME2_PROCESSING_LEVEL)
    for key, pre_r, post_r in sme2_pairs:
        print(f"  {key}: {pre_r.properties['fileName']} / {post_r.properties['fileName']}")

    print("\nSentinel-1 GRD (time series, not paired):")
    s1_series = list_sentinel1_series()
    for r in s1_series:
        print(f"  {r.properties['startTime']}  {r.properties['fileName']}")
    print(f"  {len(s1_series)} scenes total -- these are ~1 GB+ each, pick specific")
    print("  dates to download rather than pulling all of them.")

    if gcov_pairs or sme2_pairs:
        session = get_session()
        for key, pre_r, post_r in gcov_pairs + sme2_pairs:
            download_results([pre_r, post_r], session)
