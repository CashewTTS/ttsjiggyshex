from collections import defaultdict
import matplotlib.pyplot as plt
import pathlib


# Assumptions:
#   Polygonal piece extruded along y axis, above and below xz plane.
#   Quads used for all the extruded edges, and never elsewhere.
#   Single non-self-intersecting polygon.
# Returns clockwise 2D polygon.
def unextrude(filepath):
    # map points to neighbors
    vertices3 = []
    p2p = defaultdict(list)
    with open(filepath, 'r') as f:
        for line in f:
            a = line.split(' ')
            if a[0] == 'v':
                assert len(a) == 4
                vertices3.append([float(c) for c in a[1:]])
            elif a[0] == 'f' and len(a) == 5:
                q = [vertices3[int(v3s.split('/')[0]) - 1] for v3s in a[1:]]
                points2 = [(p3[0], p3[2]) for p3 in q if p3[1] > 0]
                assert len(points2) == 2
                p2p[points2[0]].append(points2[1])
                p2p[points2[1]].append(points2[0])
    assert len(p2p) >= 3
    assert all(len(_) == 2 for _ in p2p.values())
    # chain the points
    startp = next(iter(p2p.keys()))
    lastp = startp
    currp = p2p[startp][0]
    poly = [startp]
    while len(poly) < len(p2p):
        poly.append(currp)
        choices = p2p[currp]
        assert lastp in choices
        if choices[0] == lastp:
            nextp = choices[1]
        else:
            nextp = choices[0]
        lastp = currp
        currp = nextp
    assert currp == poly[0]
    # ensure clockwise
    area = 0
    for p1, p2 in zip(poly, poly[1:] + poly[:1]):
        area += (p2[0] - p1[0]) * (p2[1] + p1[1])
    if area < 0:
        poly.reverse()
    return poly


# Assumptions:
#   Poly is clockwise.
#   Piece is generally a square with vertical/horizontal sides, with a knob or hole on each of 2, 3, or 4 sides.
#   Piece may be rotated by a multiple of 90 deg, so we can't assume two particular sides are already being collected
#     from neighboring pieces.
#   A side with a knob/hole will have at least 6 points (incl corners), and a puzzle-boundary side will only have the
#     corners.
#   Sides shared by two pieces will be essentially identical, no overlap/underlap, so each is individually useful for
#     later recreation of both the knob and the hole.
#   Knobs are short enough to leave the four corners of the piece as the points with largest x+y, x+(-y), (-x)+y, and
#     (-x)+(-y).
#   Pieces are a bit oversized (as well as the grid, so no overlap) by about 0.18%.
#   Sides (imaginary lines connecting adjacent corners) are within 0.02% of unit length after scaling down by that
#     0.18%, and level (horizontal or vertical) within rounding error.
#   Center of side is within knob/hole neck, and knob/hole extends at least 0.15 from side.
# Returns only the knobs (any holes rotated to become knobs), not the straight puzzle boundaries, with the polylines
#   rotated by an appropriate multiple of 90 deg to convert outward to upward, translated such that its endpoints are
#   centered in ((0, 0), (1, 0)), and scaled to near unit length, and the endpoints then discarded (they can be assumed
#   to be (0, 0) and (1, 0)).
def get_knobs(poly):
    # identify corners
    corner_indexes = [
        max(range(len(poly)), key=lambda i: poly[i][0] + poly[i][1]),  # upper right
        max(range(len(poly)), key=lambda i: poly[i][0] - poly[i][1]),  # lower right
        max(range(len(poly)), key=lambda i: -poly[i][0] - poly[i][1]),  # lower left
        max(range(len(poly)), key=lambda i: -poly[i][0] + poly[i][1]),  # upper left
    ]
    # pair adjacent corners: (ur, lr), (lr, ll), (ll, ul), (ul, ur)
    side_index_pairs = zip(corner_indexes, corner_indexes[1:] + corner_indexes[:1])
    # subsets of points between corners inclusive, treating poly as a ring
    polylines = [(poly[ip[0]:ip[1]+1] if ip[1] >= ip[0] else poly[ip[0]:] + poly[:ip[1]+1]) for ip in side_index_pairs]
    # rotate all sides so outward -> upright
    polylines[0] = [(-p[1], p[0]) for p in polylines[0]]  # rotate right side 90 deg ccw
    polylines[1] = [(-p[0], -p[1]) for p in polylines[1]]  # rotate bottom side edge 180 deg
    polylines[2] = [(p[1], -p[0]) for p in polylines[2]]  # rotate left side 90 deg cw
    # translate to center (0.5, 0) between endpoints, and scale down by 0.18%
    for pl in polylines:
        mx = (pl[0][0] + pl[-1][0]) / 2
        my = (pl[0][1] + pl[-1][1]) / 2
        for pli in range(len(pl)):
            pl[pli] = ((pl[pli][0] - mx) / 1.0018 + 0.5, (pl[pli][1] - my) / 1.0018)
    # check endpoints are within 0.0001 of expected (so end-to-end is within 0.02%) and nearly level, and drop them
    for pl in polylines:
        assert abs(pl[0][0]) < 0.0001 and abs(pl[0][1]) < 0.000001
        assert abs(1 - pl[-1][0]) < 0.0001 and abs(pl[-1][1]) < 0.000001
        pl[:] = pl[1:-1]
    # discard straight puzzle boundaries
    assert all(len(pl) == 0 or len(pl) >= 4 for pl in polylines)
    polylines = [pl for pl in polylines if len(pl) > 0]
    # identify knob vs hole and flip holes to knobs
    for pl in polylines:
        # line segment that crosses line x=0.5
        cc = next(e for e in zip(pl[:-1], pl[1:]) if e[0][0] < 0.5 <= e[1][0])
        # y at crossing
        cy = (cc[1][1] - cc[0][1]) / (cc[1][0] - cc[0][0]) * (0.5 - cc[0][0]) + cc[0][1]
        # flip if hole
        assert abs(cy) >= 0.15
        if cy < 0:
            pl[:] = [(p[0], -p[1]) for p in pl]
    return polylines


def main(show_plot=False):
    knobs = []
    for filepath in pathlib.Path('../../ttsjigsawjoin/dist/jigsaw-templates').glob('jigsaw-*x*-3/piece.*.obj'):
        knobs.extend(get_knobs(unextrude(filepath)))
    if show_plot:
        for knob in knobs:
            knob_with_ends = [(0, 0)] + knob + [(1, 0)]
            plt.plot([p[0] for p in knob_with_ends], [p[1] for p in knob_with_ends])
        plt.show()
    with open('knobs.txt', 'w') as f:
        for knob in knobs:
            f.write(' '.join(f"{p[0]:.6f},{p[1]:.6f}" for p in knob) + '\n')


if __name__ == '__main__':
    main()
