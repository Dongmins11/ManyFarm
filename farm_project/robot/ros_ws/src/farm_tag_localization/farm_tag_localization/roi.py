"""기존 시험과 같은 영상 ROI 판정."""
import math

def roi_fractions(config):
    """Explicit independent axes, or the legacy square fraction. Never mix."""
    if any(k in config for k in ('roi_horizontal_fraction','roi_vertical_fraction')):
        if 'roi_fraction' in config:
            raise ValueError('roi_scalar_and_axes_must_not_be_mixed')
        values=(config.get('roi_horizontal_fraction'),config.get('roi_vertical_fraction'))
    else:
        values=(config.get('roi_fraction'),)*2
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=1 for v in values):
        raise ValueError('both_finite_roi_fractions_required')
    return values


def roi_accept(detection, fraction, width=1280, height=720):
    try:
        fx,fy=roi_fractions({'roi_fraction':fraction}) if type(fraction) in (int,float) else roi_fractions(
            {'roi_horizontal_fraction':fraction[0],'roi_vertical_fraction':fraction[1]})
        if type(width) is not int or type(height) is not int or min(width,height)<=0:return False
        c=detection['corners']
        if len(c)!=4 or any(len(p)!=2 or not all(math.isfinite(float(v)) for v in p) for p in c):return False
        x0,y0=width*(1-fx)/2,height*(1-fy)/2
        return all(x0<=x<width-x0 and y0<=y<height-y0 for x,y in c)
    except (KeyError,ValueError,TypeError,IndexError):
        return False


