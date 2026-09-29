"""Run with Isaac Sim's Python. --build-only also works with plain USD Python."""
import argparse
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('config.json'))
    parser.add_argument('--headless',action='store_true',help='Build, open in Isaac Sim, then exit')
    parser.add_argument('--build-only',action='store_true',help='Build USD without launching Isaac Sim')
    parser.add_argument('--open-only',action='store_true',help='Open existing output without rebuilding')
    args=parser.parse_args()
    if args.build_only:
        if args.open_only:parser.error('--build-only and --open-only are mutually exclusive')
        from placement import build
        build(args.config)
        return
    # SimulationApp must be created BEFORE importing pxr/omni/placement.
    from isaacsim import SimulationApp
    app=SimulationApp({'headless':args.headless,'width':1600,'height':900})
    try:
        import json
        import time
        import omni.usd
        from placement import build,ROOT
        if args.open_only:
            config=json.loads(args.config.read_text(encoding='utf-8'));output=(ROOT/config['output']).resolve()
            if not output.is_file():raise FileNotFoundError(output)
        else:output=build(args.config)
        ctx=omni.usd.get_context()
        if not ctx.open_stage(str(output)):raise RuntimeError('Could not open '+str(output))
        deadline=time.monotonic()+180
        while ctx.get_stage_loading_status()[2]>0:
            if time.monotonic()>deadline:raise TimeoutError('Stage loading exceeded 180 seconds')
            app.update()
        for _ in range(30):app.update()
        if not args.headless:
            try:
                from omni.kit.viewport.utility import get_active_viewport
                viewport=get_active_viewport()
                if viewport:viewport.set_active_camera('/World/Vegetation/ReviewCamera')
            except (ImportError,AttributeError) as e:print('Camera selection skipped:',e)
            print('Scene ready. Close the Isaac Sim window to exit.')
            while app.is_running():app.update()
    finally:app.close()
if __name__=='__main__':main()
