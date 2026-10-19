"""Finite native input/menu checks through the existing private control hook."""
from pathlib import Path
import argparse
import math
from launch_session import verify_lease
from live_protocol import Channel, ProtocolError, atomic_json, matched_pose
from live_compare import menu


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--session', type=Path, required=True)
    p.add_argument('--reserved-window', required=True)
    a = p.parse_args()
    w = Path(__file__).resolve().parents[2] / '.local/atlas2'
    s = a.session.resolve()
    s.relative_to(w.resolve())
    verify_lease(w, a.reserved_window)
    c = Channel(s / 'map-qa/trace.json.atlas2.json', w / 'Atlas2-test/bin/bb-probe.exe', max_age=30)
    menu(c, c.trace.parent / 'pad.txt')
    pose = c.read()['pose']
    rows = []

    def check(name, ok):
        rows.append(dict(check=name, passed=bool(ok)))
        atomic_json(s / 'full-input-checks.json', dict(schema=1, complete=False, checks=rows))
        if not ok:
            raise ProtocolError('Native input check failed: ' + name)

    def rendered(command):
        issued = c.command(command)
        return c.rendered(0, issued['sequence'])

    try:
        c.command('enable')
        c.command('atlas2-static')
        start = rendered('open')
        check('open_captures_input', start['open'] and start['capture'])
        start = rendered('recenter')
        zoomed = rendered('zoom-in')
        check('zoom_in_changes_scale', zoomed['zoom'] > start['zoom'])
        restored = rendered('recenter')
        check('recenter_restores_scale', math.isclose(restored['zoom'], start['zoom'], abs_tol=1e-5))
        issued = c.command('pan-right')
        moved = c.wait(lambda x: math.dist(x['center'], restored['center']) > .1, after=issued['sequence'])
        c.command('pan-stop')
        check('pan_changes_center', math.dist(moved['center'], restored['center']) > .1)
        centered = rendered('recenter')
        check('recenter_restores_center', math.dist(centered['center'], restored['center']) < 1e-4)
        strict = centered['render']['strict_layer']
        forced = rendered('atlas2-floor ' + str(strict))
        check('manual_floor_override', forced['manual_layer'] == strict and forced['render']['layer'] == strict)
        auto = rendered('atlas2-floor-auto')
        check('automatic_floor_restored', auto['manual_layer'] == -1 and auto['render']['layer'] == strict)
        for i in range(3):
            closed = c.command('close')
            check('close_releases_input_' + str(i), not closed['open'] and not closed['capture'])
            opened = rendered('open')
            check('reopen_captures_input_' + str(i), opened['open'] and opened['capture'])
        disabled = c.command('disable')
        check('ui_disable_releases_input', not disabled['open'] and not disabled['capture'])
        c.command('enable')
        opened = rendered('open')
        check('ui_reenable_opens', opened['open'] and opened['capture'])
        check('pose_unchanged', matched_pose(pose, opened['pose']))
        atomic_json(s / 'full-input-checks.json', dict(schema=1, complete=True, passed=True, checks=rows, natural_staircase_transition_tested=False))
        print('FULL_NATIVE_INPUT_PASS checks=' + str(len(rows)))
    finally:
        c.command('pan-stop')
        c.command('enable')
        c.command('atlas2-floor-auto')
        c.command('atlas2-static')
        c.command('close')


if __name__ == '__main__':
    main()
