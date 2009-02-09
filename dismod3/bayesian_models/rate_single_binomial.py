# model all observed rates as binomial draws from a single rate function

from dismod3.models.probabilistic_utils import *

def model_vars(asrf):
    vars = {}
    
    add_rate_stochs(vars, 'asrf', asrf.fit['age_mesh'], asrf.fit['out_age_mesh'])
    vars['logit(asrf)'].value = mc.logit(np.array(asrf.fit['normal_approx'])[asrf.fit['age_mesh']])

    tau_smooth = mc.InverseGamma('smoothing_tau', 0.1, 1.0, value=1.)
    vars['hyper params'] = [tau_smooth]

    @mc.potential
    def smooth(f=vars['logit(asrf)'], tau=tau_smooth):
        return mc.normal_like(np.diff(f), 0.0, tau)

    @mc.potential
    def initially_zero(f=vars['asrf'], age_start=0, age_end=5, tau=1./(1e-4)**2):
        return mc.normal_like(f[range(age_start, age_end)], 0.0, tau)

    vars['priors'] = [smooth, initially_zero]

    vars['observed_rates'] = observed_rates_stochs(asrf.rates.all(), vars['asrf'])

    return vars


def save_map(vars, asrf):
    asrf.fit['map'] = list(vars['asrf'].value)
    asrf.save()

def save_mcmc(vars, asrf):
    rate = vars['asrf'].trace()
    trace_len = len(rate)
    
    sr = []
    for ii in asrf.fit['out_age_mesh']:
        sr.append(sorted(rate[:,ii]))
    asrf.fit['mcmc_lower_cl'] = [sr[ii][int(.025*trace_len)] for ii in asrf.fit['out_age_mesh']]
    asrf.fit['mcmc_median'] = [sr[ii][int(.5*trace_len)] for ii in asrf.fit['out_age_mesh']]
    asrf.fit['mcmc_upper_cl'] = [sr[ii][int(.975*trace_len)] for ii in asrf.fit['out_age_mesh']]
    asrf.fit['mcmc_mean'] = list(np.mean(rate, 0))

    asrf.save()
